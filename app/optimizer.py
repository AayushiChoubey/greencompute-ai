"""Deterministic, explainable MVP optimizer connected to data-layer rules."""

from datetime import timedelta
from uuid import uuid4
from typing import Tuple, List, Set

from app.models import (
    Candidate,
    OptimizeRequest,
    OptimizeResponse,
    ProvisioningModel,
    StartMode,
    DataLocationType,
    RegionMetric,
)


def _lower_is_better(value: float, values: List[float]) -> float:
    """Normalize a minimization metric to a 0..1 benefit score."""
    low, high = min(values), max(values)
    return 1.0 if high == low else (high - value) / (high - low)


def _higher_is_better(value: float, values: List[float]) -> float:
    """Normalize a maximization metric to a 0..1 benefit score."""
    low, high = min(values), max(values)
    return 1.0 if high == low else (value - low) / (high - low)


def _score_feasible_candidates(request: OptimizeRequest, candidates: List[Candidate]) -> None:
    """Apply the user-supplied multi-objective weights to feasible candidates."""
    costs = [c.estimated_compute_cost_usd for c in candidates]
    carbons = [c.carbon_score for c in candidates]
    reliabilities = [c.reliability_score for c in candidates]
    sla_buffers = [float(c.sla_buffer_minutes) for c in candidates]
    weights = request.objective_weights

    for candidate in candidates:
        candidate.final_score = round(
            weights.cost * _lower_is_better(candidate.estimated_compute_cost_usd, costs)
            + weights.carbon * _lower_is_better(candidate.carbon_score, carbons)
            + weights.reliability * _higher_is_better(candidate.reliability_score, reliabilities)
            + weights.sla_buffer * _higher_is_better(float(candidate.sla_buffer_minutes), sla_buffers),
            6,
        )


def _apply_cost_increase_guardrail(
    request: OptimizeRequest, candidates: List[Candidate]
) -> None:
    """Reject options exceeding the permitted premium over the cheapest valid plan."""
    if request.maximum_cost_increase_percent is None or not candidates:
        return

    cheapest_cost = min(c.estimated_compute_cost_usd for c in candidates)
    maximum_cost = cheapest_cost * (1 + request.maximum_cost_increase_percent / 100.0)
    for candidate in candidates:
        if candidate.estimated_compute_cost_usd > maximum_cost:
            candidate.is_feasible = False
            candidate.rejection_reasons.append(
                "COST_INCREASE_ABOVE_POLICY_THRESHOLD: "
                f"${candidate.estimated_compute_cost_usd:.6f} exceeds ${maximum_cost:.6f}"
            )


def _possible_start_times(request: OptimizeRequest):
    if request.start_mode == StartMode.EXACT:
        return [request.earliest_start_at]

    latest_start = request.deadline_at - timedelta(
        minutes=request.estimated_runtime_minutes + request.minimum_sla_buffer_minutes
    )
    current = request.earliest_start_at
    start_times = []
    while current <= latest_start:
        start_times.append(current)
        current += timedelta(hours=1)
    return start_times or [request.earliest_start_at]


def _resolve_target_regions(request: OptimizeRequest) -> Set[str]:
    if request.data_location_type == DataLocationType.DATA_LOCAL:
        return {request.home_region}
    if request.data_location_type == DataLocationType.REPLICATED:
        replica_pool = set(request.approved_replica_regions) | {request.home_region}
        return replica_pool.intersection(set(request.allowed_regions)) if request.allowed_regions else replica_pool
    return set(request.allowed_regions) if request.allowed_regions else {request.home_region}


def _evaluate_candidate(
    request: OptimizeRequest, metric: RegionMetric, scheduled_start_at, target_regions: Set[str]
) -> Candidate:
    reasons: List[str] = []
    predicted_finish = scheduled_start_at + timedelta(minutes=request.estimated_runtime_minutes)
    sla_buffer = int((request.deadline_at - predicted_finish).total_seconds() // 60)

    # 1. Data Locality Check
    if metric.region not in target_regions:
        reasons.append(f"REGION_NOT_ALLOWED: Incompatible with {request.data_location_type.value} policy")

    # 2. Compute/Memory Specs
    if metric.vcpus < request.required_vcpus:
        reasons.append("INSUFFICIENT_VCPUS")
    if metric.memory_gb < request.required_memory_gb:
        reasons.append("INSUFFICIENT_MEMORY")

    # 3. Capacity & Spot Rules
    if not metric.capacity_available:
        reasons.append("CAPACITY_UNAVAILABLE")
    if metric.provisioning_model == ProvisioningModel.SPOT:
        if not request.spot_allowed:
            reasons.append("SPOT_NOT_ALLOWED")
        if not request.checkpointable:
            reasons.append("SPOT_REQUIRES_CHECKPOINTABLE_WORKLOAD")

    # 4. Deadline & Reliability
    if predicted_finish > request.deadline_at:
        reasons.append("DEADLINE_MISSED")
    if sla_buffer < request.minimum_sla_buffer_minutes:
        reasons.append("SLA_BUFFER_BELOW_POLICY_THRESHOLD")
    if metric.reliability_score < request.minimum_reliability_score:
        reasons.append("RELIABILITY_BELOW_POLICY_THRESHOLD")

    return Candidate(
        candidate_id=str(uuid4()),
        region=metric.region,
        machine_type=metric.machine_type,
        provisioning_model=metric.provisioning_model,
        scheduled_start_at=scheduled_start_at,
        predicted_finish_at=predicted_finish,
        # Preserve enough precision for short jobs; presentation formatting is
        # a UI concern and must not change ranking outcomes.
        estimated_compute_cost_usd=round(
            metric.hourly_cost_usd * request.estimated_runtime_minutes / 60,
            9,
        ),
        carbon_score=metric.carbon_score,
        reliability_score=metric.reliability_score,
        sla_buffer_minutes=sla_buffer,
        is_feasible=not reasons,
        rejection_reasons=reasons,
    )


def optimize(request: OptimizeRequest, metrics: List[RegionMetric]) -> Tuple[OptimizeResponse, str]:
    target_regions = _resolve_target_regions(request)
    candidates = [
        _evaluate_candidate(request, metric, start_time, target_regions)
        for metric in metrics
        for start_time in _possible_start_times(request)
    ]
    feasible = [c for c in candidates if c.is_feasible]
    opt_run_id = f"opt_{uuid4().hex[:12]}"
    decision_id = f"dec_{uuid4().hex[:12]}"

    _apply_cost_increase_guardrail(request, feasible)
    feasible = [c for c in feasible if c.is_feasible]

    transparency = (
        "Carbon values are synthetic regional baselines (gCO2e/kWh) and do not represent "
        "live grid emissions or measured Google data-centre outputs. Pricing is a frozen GCP snapshot."
    )

    if not feasible:
        msg = "No candidate meets all hard constraints. Execution prevented."
        return OptimizeResponse(
            optimization_run_id=opt_run_id,
            decision_id=decision_id,
            workload_name=request.workload_name,
            start_mode=request.start_mode,
            candidate_count=len(candidates),
            feasible_candidate_count=0,
            selected_candidate=None,
            message=msg,
            transparency_notice=transparency,
            candidates=candidates,
        ), msg

    _score_feasible_candidates(request, feasible)
    feasible.sort(
        key=lambda c: (
            -(c.final_score or 0.0),
            c.estimated_compute_cost_usd,
            c.carbon_score,
            -c.reliability_score,
            -c.sla_buffer_minutes,
        )
    )
    selected = feasible[0]
    weights = request.objective_weights
    reason = (
        f"Selected {selected.machine_type} ({selected.provisioning_model}) in {selected.region} "
        f"with weighted score {selected.final_score:.4f}, estimated compute cost "
        f"${selected.estimated_compute_cost_usd:.6f} USD, and carbon baseline "
        f"{selected.carbon_score:.1f} gCO2e/kWh. Weights: cost={weights.cost:.2f}, "
        f"carbon={weights.carbon:.2f}, reliability={weights.reliability:.2f}, "
        f"SLA buffer={weights.sla_buffer:.2f}."
    )

    ranked_candidates = feasible + [c for c in candidates if not c.is_feasible]

    return OptimizeResponse(
        optimization_run_id=opt_run_id,
        decision_id=decision_id,
        workload_name=request.workload_name,
        start_mode=request.start_mode,
        candidate_count=len(candidates),
        feasible_candidate_count=len(feasible),
        selected_candidate=selected,
        message=reason,
        transparency_notice=transparency,
        candidates=ranked_candidates,
    ), reason
