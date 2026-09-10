"""Optimization and prompt ingestion router."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.models import OptimizeRequest, OptimizeResponse, Candidate
from app.optimizer import optimize
from app.dependencies import bq_client, explainer, prompt_parser, workflow_adapter
from pydantic import BaseModel

# Remove the internal prefix here as it is managed by the main app entrypoint
router = APIRouter(tags=["Optimization"])


class ExplainRequest(BaseModel):
    workload: OptimizeRequest
    selected_candidate: Candidate
    candidates: List[Candidate]


class ExplainResponse(BaseModel):
    workload_id: str
    optimization_run_id: str
    selected_region: str
    selected_provisioning_model: str
    explanation: str


class PromptIngestionRequest(BaseModel):
    prompt: str
    auto_optimize: bool = False


class PromptIngestionResponse(BaseModel):
    prompt: str
    parsed_spec: OptimizeRequest
    optimization_result: Optional[OptimizeResponse] = None
    gemini_explanation: Optional[str] = None
    workflow_execution: Optional[dict] = None


def candidate_evidence(
    candidates: List[Candidate],
    selected_candidate: Optional[Candidate],
    home_region: Optional[str] = None,
    limit: int = 8,
) -> List[Candidate]:
    """Return a diverse, compact audit sample instead of repeated time slots."""
    evidence: List[Candidate] = []
    seen = set()

    priority_candidates: List[Candidate] = []
    if selected_candidate:
        priority_candidates.append(selected_candidate)

    if home_region:
        home_candidate = next(
            (
                candidate
                for candidate in candidates
                if candidate.region == home_region and candidate.is_feasible
            ),
            None,
        )
        if home_candidate:
            priority_candidates.append(home_candidate)

    # Guarantee that users can compare at least one candidate for each
    # region/provisioning combination before lower-value shape variations.
    region_provisioning_seen = set()
    for candidate in candidates:
        key = (candidate.region, candidate.provisioning_model, candidate.is_feasible)
        if key not in region_provisioning_seen:
            region_provisioning_seen.add(key)
            priority_candidates.append(candidate)

    priority_ids = {candidate.candidate_id for candidate in priority_candidates}
    ordered = priority_candidates + [
        candidate for candidate in candidates if candidate.candidate_id not in priority_ids
    ]

    for candidate in ordered:
        reason_codes = tuple(
            reason.split(":", 1)[0] for reason in candidate.rejection_reasons
        )
        key = (
            candidate.region,
            candidate.machine_type,
            candidate.provisioning_model,
            candidate.is_feasible,
            reason_codes,
        )
        if key in seen:
            continue
        seen.add(key)
        evidence.append(candidate)
        if len(evidence) >= limit:
            break

    return evidence


@router.post("/optimize", response_model=OptimizeResponse)
def optimize_workload(request: OptimizeRequest) -> OptimizeResponse:
    """Read BigQuery options, optimize against hard constraints, and log complete audit trail."""
    try:
        metrics = request.region_metrics or bq_client.fetch_compute_options()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BigQuery fetch failed: {str(e)}")

    response, decision_reason = optimize(request, metrics)

    try:
        bq_client.record_full_optimization_run(
            optimization_run_id=response.optimization_run_id,
            decision_id=response.decision_id,
            workload_id=request.workload_id,
            policy_version_id=request.policy_version_id,
            selected_candidate=response.selected_candidate,
            all_candidates=response.candidates,
            reason=decision_reason,
            workload_input_dict=request.model_dump(mode="json"),
        )
    except Exception as e:
        print(f"Audit log warning: {e}")

    if response.candidates:
        response.candidates = candidate_evidence(
            response.candidates,
            response.selected_candidate,
            home_region=request.home_region,
        )
    return response


@router.post("/explain", response_model=ExplainResponse)
def explain_decision(request: ExplainRequest) -> ExplainResponse:
    alternatives = [c for c in request.candidates if c.candidate_id != request.selected_candidate.candidate_id]
    explanation_text = explainer.generate_explanation(
        request=request.workload,
        selected_candidate=request.selected_candidate,
        top_alternatives=alternatives,
    )
    prov_model = request.selected_candidate.provisioning_model
    prov_val = prov_model.value if hasattr(prov_model, "value") else str(prov_model)
    return ExplainResponse(
        workload_id=request.workload.workload_id,
        optimization_run_id=f"opt_exp_{uuid.uuid4().hex[:8]}",
        selected_region=request.selected_candidate.region,
        selected_provisioning_model=prov_val,
        explanation=explanation_text,
    )


@router.post("/workloads/from-prompt", response_model=PromptIngestionResponse)
def ingest_workload_prompt(
    request: PromptIngestionRequest,
    dispatch: bool = Query(False)
) -> PromptIngestionResponse:
    try:
        parsed_spec = prompt_parser.parse_workload_prompt(request.prompt)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse prompt spec: {str(e)}")

    opt_result = None
    gemini_exp = None
    if request.auto_optimize or dispatch:
        opt_result = optimize_workload(parsed_spec)
        if opt_result and opt_result.selected_candidate:
            try:
                alts = [c for c in opt_result.candidates if c.candidate_id != opt_result.selected_candidate.candidate_id]
                gemini_exp = explainer.generate_explanation(
                    request=parsed_spec,
                    selected_candidate=opt_result.selected_candidate,
                    top_alternatives=alts[:3]
                )
            except Exception as ex:
                print(f"Gemini explainer error: {ex}")
                cand = opt_result.selected_candidate
                prov = cand.provisioning_model.value if hasattr(cand.provisioning_model, "value") else str(cand.provisioning_model)
                gemini_exp = f"Selected {cand.region} on {prov} providing optimal carbon intensity ({cand.carbon_score:.1f} gCO2e) and cost (${cand.estimated_compute_cost_usd:.4f})."

    wf_result = None
    if dispatch:
        # An infeasible optimization is a valid business result, not a broken
        # HTTP request. Return the evidence so the dashboard can explain why
        # execution was prevented instead of replacing it with a generic 422.
        if opt_result and opt_result.selected_candidate:
            try:
                workload_dict = parsed_spec.model_dump(mode="json")
                wf_result = workflow_adapter.trigger_workflow(workload_dict)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to dispatch workflow: {str(e)}")

    return PromptIngestionResponse(
        prompt=request.prompt,
        parsed_spec=parsed_spec,
        optimization_result=opt_result,
        gemini_explanation=gemini_exp,
        workflow_execution=wf_result
    )
