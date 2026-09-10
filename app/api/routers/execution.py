import logging
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException
from google.cloud import bigquery
from pydantic import BaseModel

from app.models import Candidate
from app.dependencies import batch_adapter, bq_client

router = APIRouter()
logger = logging.getLogger(__name__)

TERMINAL_STATUS_MAP = {
    "SUCCEEDED": "SUCCEEDED",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
    # Batch uses this state when a job has been deleted before completion.
    # Record it as a failed attempt; it must never be represented as success.
    "DELETION_IN_PROGRESS": "FAILED",
}


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
    actual_runtime_seconds: Optional[int] = None
    actual_cost: Optional[float] = None
    correlation_id: Optional[str] = ""
    workflow_execution_id: Optional[str] = None


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
    received_status = request.status.upper()
    clean_status = TERMINAL_STATUS_MAP.get(received_status)
    if clean_status is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Execution callback accepts only terminal Batch states: "
                "SUCCEEDED, FAILED, CANCELLED, or DELETION_IN_PROGRESS."
            ),
        )

    final_attempt_id = request.execution_attempt_id
    if not final_attempt_id:
        # A retrying Workflow can lose a response value. Recover the submission
        # attempt rather than creating an unrelated telemetry chain.
        lookup_query = """
            SELECT execution_attempt_id
            FROM `greencompute-ai.greencompute_events.execution_events`
            WHERE workload_run_id = @workload_id
              AND batch_job_id = @batch_job_id
              AND execution_status = 'SUBMITTED'
            ORDER BY event_timestamp DESC, ingested_at DESC
            LIMIT 1
        """
        try:
            config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("workload_id", "STRING", request.workload_id),
                    bigquery.ScalarQueryParameter("batch_job_id", "STRING", request.batch_job_name),
                ]
            )
            row = next(iter(bq_client.client.query(lookup_query, job_config=config).result()), None)
            if row:
                final_attempt_id = row["execution_attempt_id"]
        except Exception:
            logger.exception(
                "Could not recover execution attempt id for Batch job %s",
                request.batch_job_name,
            )

    if not final_attempt_id:
        final_attempt_id = f"exec_att_{uuid.uuid4().hex[:12]}"
        logger.warning(
            "Recording terminal callback without a matching submission attempt for Batch job %s",
            request.batch_job_name,
        )

    try:
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
                "workflow_execution_id": request.workflow_execution_id,
            },
            event_id=f"exec_ev_{final_attempt_id}_{clean_status.lower()}",
        )
    except RuntimeError as exc:
        logger.exception("Could not persist terminal Batch status for %s", request.batch_job_name)
        raise HTTPException(
            status_code=503,
            detail="Execution telemetry write failed; retry the callback.",
        ) from exc

    return {"status": "recorded", "execution_attempt_id": final_attempt_id}
