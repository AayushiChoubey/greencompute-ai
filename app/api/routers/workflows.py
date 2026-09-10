import logging

from fastapi import APIRouter, HTTPException
import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
import requests

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/status/{execution_id}")
def get_workflow_status(execution_id: str):
    """Return the Workflow execution record used by the dashboard detail view."""
    try:
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(GoogleAuthRequest())
        headers = {"Authorization": f"Bearer {credentials.token}"}
        url = f"https://workflowexecutions.googleapis.com/v1/projects/greencompute-ai/locations/asia-south1/workflows/greencompute-orchestrator/executions/{execution_id}"
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            execution = resp.json()
            return {
                "name": execution.get("name"),
                "state": execution.get("state", "ACTIVE"),
                "start_time": execution.get("startTime"),
                "end_time": execution.get("endTime"),
                "argument": execution.get("argument"),
                "result": execution.get("result"),
                "error": execution.get("error"),
                "call_log_level": execution.get("callLogLevel"),
            }
        logger.error("Workflow execution lookup failed: %s %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail="Could not retrieve Workflow execution details.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Workflow execution lookup failed for %s", execution_id)
        raise HTTPException(
            status_code=503,
            detail="Workflow execution details are temporarily unavailable.",
        ) from exc
