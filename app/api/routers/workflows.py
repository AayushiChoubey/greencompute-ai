from fastapi import APIRouter
import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
import requests

router = APIRouter()

@router.get("/status/{execution_id}")
def get_workflow_status(execution_id: str):
    try:
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(GoogleAuthRequest())
        headers = {"Authorization": f"Bearer {credentials.token}"}
        url = f"https://workflowexecutions.googleapis.com/v1/projects/greencompute-ai/locations/asia-south1/workflows/greencompute-orchestrator/executions/{execution_id}"
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return {"state": resp.json().get("state", "ACTIVE")}
        return {"state": "ACTIVE"}
    except Exception:
        return {"state": "ACTIVE"}