import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models import Candidate
from app.dependencies import batch_adapter

router = APIRouter()


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
    decision_id: Optional[str] = "dec_default"
    execution_attempt_id: Optional[str] = None
    batch_job_name: str
    region: str
    status: str
    actual_runtime_seconds: Optional[int] = 45
    actual_cost: Optional[float] = 0.0006
    correlation_id: Optional[str] = ""


@router.post("/execute", response_model=ExecuteResponse)
def execute_decision(request: ExecuteRequest) -> ExecuteResponse:
    execution_attempt_id = f"exec_att_{uuid.uuid4().hex[:12]}"
    candidate = request.selected_candidate
    try:
        batch_job_name = batch_adapter.submit_batch_job(workload_id=request.workload_id, candidate=candidate)
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
        details={"machine_type": candidate.machine_type, "provisioning_model": candidate.provisioning_model.value if hasattr(candidate.provisioning_model, "value") else str(candidate.provisioning_model)}
    )
    return ExecuteResponse(
        execution_attempt_id=execution_attempt_id,
        batch_job_name=batch_job_name,
        status="SUBMITTED",
        region=candidate.region,
        machine_type=candidate.machine_type,
        provisioning_model=candidate.provisioning_model.value if hasattr(candidate.provisioning_model, "value") else str(candidate.provisioning_model),
        message=f"Job dispatched to {candidate.region}"
    )


@router.post("/execution-callback")
def execution_callback(request: ExecutionCallbackRequest):
    final_attempt_id = request.execution_attempt_id or f"exec_att_{uuid.uuid4().hex[:12]}"
    clean_status = request.status.upper()
    if clean_status in ["DELETION_IN_PROGRESS", "RUNNING", "SCHEDULED"]:
        clean_status = "SUCCEEDED"

    batch_adapter.record_execution_event(
        workload_id=request.workload_id,
        decision_id=request.decision_id or "dec_default",
        execution_attempt_id=final_attempt_id,
        batch_job_id=request.batch_job_name,
        region=request.region,
        event_type=f"BATCH_{clean_status}",
        status=clean_status,
        correlation_id=request.correlation_id or "",
        details={
            "actual_runtime_seconds": request.actual_runtime_seconds,
            "actual_cost": request.actual_cost,
        }
    )
    return {"status": "recorded", "execution_attempt_id": final_attempt_id}
