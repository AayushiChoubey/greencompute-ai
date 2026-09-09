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
        estimated_compute_cost_usd=round(metric.hourly_cost_usd * request.estimated_runtime_minutes / 60, 4),
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

    transparency = (
        "Carbon values are synthetic regional baselines (gCO2e/kWh) and do not represent "
        "live grid emissions or measured Google data-centre outputs. Pricing is a frozen GCP snapshot."
    )

    if not feasible:
        msg = "No candidate meets all hard constraints. Execution prevented."
        return OptimizeResponse(
            optimization_run_id=opt_run_id,
            workload_name=request.workload_name,
            start_mode=request.start_mode,
            candidate_count=len(candidates),
            feasible_candidate_count=0,
            selected_candidate=None,
            message=msg,
            transparency_notice=transparency,
            candidates=candidates,
        ), msg

    # Rank by cost first, breaking ties with lowest carbon baseline
    feasible.sort(key=lambda c: (c.estimated_compute_cost_usd, c.carbon_score))
    selected = feasible[0]
    reason = (
        f"Selected {selected.machine_type} ({selected.provisioning_model}) in {selected.region} "
        f"at ${selected.estimated_compute_cost_usd:.4f} USD and carbon baseline {selected.carbon_score:.1f} gCO2e/kWh."
    )

    return OptimizeResponse(
        optimization_run_id=opt_run_id,
        workload_name=request.workload_name,
        start_mode=request.start_mode,
        candidate_count=len(candidates),
        feasible_candidate_count=len(feasible),
        selected_candidate=selected,
        message=reason,
        transparency_notice=transparency,
        candidates=candidates,
    ), reason
