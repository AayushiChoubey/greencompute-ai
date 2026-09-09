"""HTTP API entrypoint for GreenCompute."""

import os
import uuid
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.models import OptimizeRequest, OptimizeResponse, Candidate
from app.optimizer import optimize
from app.bigquery_client import BigQueryClient
from app.batch_client import CloudBatchAdapter
from app.explainer import DecisionExplainer
from app.prompt_parser import PromptParser
from app.workflow_client import WorkflowExecutionAdapter

app = FastAPI(
    title="GreenCompute AI API",
    version="0.4.0",
    description="Deterministic optimization, Batch dispatch, Cloud Workflows orchestration, and Gemini explainability.",
)

templates = Jinja2Templates(directory="app/templates")

bq_client = BigQueryClient()
batch_adapter = CloudBatchAdapter()
explainer = DecisionExplainer()
prompt_parser = PromptParser()
workflow_adapter = WorkflowExecutionAdapter()


class ExecuteRequest(BaseModel):
    workload_id: str
    decision_id: str
    optimization_run_id: str
    selected_candidate: Candidate


class ExecuteResponse(BaseModel):
    execution_attempt_id: str
    batch_job_name: str
    status: str
    region: str
    machine_type: str
    provisioning_model: str
    message: str


class ExecutionCallbackRequest(BaseModel):
    workload_id: str
    decision_id: str
    execution_attempt_id: str
    batch_job_name: str
    region: str
    status: str
    actual_runtime_seconds: int = 45
    actual_cost: float = 0.0006
    correlation_id: str


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


@app.get("/", response_class=HTMLResponse)
def serve_dashboard(request: Request):
    """Serves the GreenCompute interactive UI dashboard."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "greencompute-api"}


@app.get("/api/v1/telemetry")
def get_telemetry() -> List[Dict[str, Any]]:
    """Returns top 10 latest executions from BigQuery summary view."""
    query = """
        SELECT 
            workload_run_id, 
            region, 
            execution_status, 
            actual_runtime_seconds, 
            actual_cost, 
            CAST(latest_status_at AS STRING) as latest_status_at
        FROM `greencompute-ai.greencompute_analytics.v_execution_summary` 
        ORDER BY latest_status_at DESC 
        LIMIT 10
    """
    try:
        results = bq_client.client.query(query).result()
        rows = [dict(row) for row in results]
        return rows
    except Exception as e:
        return []


@app.post("/api/v1/optimize", response_model=OptimizeResponse)
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
            workload_id=request.workload_id,
            policy_version_id=request.policy_version_id,
            selected_candidate=response.selected_candidate,
            all_candidates=response.candidates,
            reason=decision_reason,
            workload_input_dict=request.model_dump(mode="json"),
        )
    except Exception as e:
        print(f"Audit log warning: {e}")

    # TRUNCATE to prevent Cloud Workflows MemoryLimitExceededError
    if response.candidates:
        response.candidates = response.candidates[:3]

    return response


@app.post("/api/v1/execute", response_model=ExecuteResponse)
def execute_decision(request: ExecuteRequest) -> ExecuteResponse:
    """Submits the chosen candidate plan to Google Cloud Batch and records execution event."""
    execution_attempt_id = f"exec_att_{uuid.uuid4().hex[:12]}"
    candidate = request.selected_candidate

    try:
        batch_job_name = batch_adapter.submit_batch_job(
            workload_id=request.workload_id,
            candidate=candidate
        )
    except Exception as e:
        batch_adapter.record_execution_event(
            workload_id=request.workload_id,
            decision_id=request.decision_id,
            execution_attempt_id=execution_attempt_id,
            batch_job_id="SUBMISSION_FAILED",
            region=candidate.region,
            event_type="BATCH_SUBMISSION_FAILED",
            status="FAILED",
            correlation_id=request.optimization_run_id,
            details={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"Batch submission failed: {str(e)}")

    batch_adapter.record_execution_event(
        workload_id=request.workload_id,
        decision_id=request.decision_id,
        execution_attempt_id=execution_attempt_id,
        batch_job_id=batch_job_name,
        region=candidate.region,
        event_type="BATCH_SUBMITTED",
        status="SUBMITTED",
        correlation_id=request.optimization_run_id,
        details={
            "machine_type": candidate.machine_type,
            "provisioning_model": candidate.provisioning_model.value
        }
    )

    return ExecuteResponse(
        execution_attempt_id=execution_attempt_id,
        batch_job_name=batch_job_name,
        status="SUBMITTED",
        region=candidate.region,
        machine_type=candidate.machine_type,
        provisioning_model=candidate.provisioning_model.value,
        message=f"Job successfully dispatched to Google Cloud Batch in {candidate.region}"
    )


@app.post("/api/v1/execution-callback")
def execution_callback(request: ExecutionCallbackRequest):
    """Logs the final execution state returned by Google Cloud Workflows."""
    batch_adapter.record_execution_event(
        workload_id=request.workload_id,
        decision_id=request.decision_id,
        execution_attempt_id=request.execution_attempt_id,
        batch_job_id=request.batch_job_name,
        region=request.region,
        event_type=f"BATCH_{request.status}",
        status=request.status,
        correlation_id=request.correlation_id,
        details={
            "actual_runtime_seconds": request.actual_runtime_seconds,
            "actual_cost": request.actual_cost,
        }
    )
    return {"status": "recorded", "execution_status": request.status}


@app.post("/api/v1/explain", response_model=ExplainResponse)
def explain_decision(request: ExplainRequest) -> ExplainResponse:
    """Uses Gemini 2.5 Flash to synthesize an executive trade-off explanation."""
    alternatives = [c for c in request.candidates if c.candidate_id != request.selected_candidate.candidate_id]

    explanation_text = explainer.generate_explanation(
        request=request.workload,
        selected_candidate=request.selected_candidate,
        top_alternatives=alternatives,
    )

    return ExplainResponse(
        workload_id=request.workload.workload_id,
        optimization_run_id=f"opt_exp_{uuid.uuid4().hex[:8]}",
        selected_region=request.selected_candidate.region,
        selected_provisioning_model=request.selected_candidate.provisioning_model.value,
        explanation=explanation_text,
    )


@app.post("/api/v1/workloads/from-prompt", response_model=PromptIngestionResponse)
def ingest_workload_prompt(
    request: PromptIngestionRequest,
    dispatch: bool = Query(False, description="Whether to immediately trigger Cloud Workflow orchestration")
) -> PromptIngestionResponse:
    """Parses freeform prompt into structured spec, optionally optimizing and/or dispatching to Cloud Workflows."""
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
                cand = opt_result.selected_candidate
                gemini_exp = f"Selected {cand.region} on {cand.provisioning_model.value} providing optimal carbon intensity ({cand.carbon_score:.1f} gCO2e) and cost (${cand.estimated_compute_cost_usd:.4f})."

    wf_result = None
    if dispatch:
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
        workflow_execution=wf_result,
    )