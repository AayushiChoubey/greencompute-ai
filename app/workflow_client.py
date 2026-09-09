"""Client adapter to trigger Google Cloud Workflows."""

import json
import os
from google.cloud import workflows_v1
from google.cloud.workflows import executions_v1
from google.cloud.workflows.executions_v1.types import Execution

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "greencompute-ai")
LOCATION = os.getenv("WORKFLOW_LOCATION", "asia-south1")
WORKFLOW_NAME = os.getenv("WORKFLOW_NAME", "greencompute-orchestrator")
API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "https://greencompute-api-877509863043.asia-south1.run.app"
)


class WorkflowExecutionAdapter:
    def __init__(self):
        self.client = executions_v1.ExecutionsClient()
        self.parent = (
            f"projects/{PROJECT_ID}/locations/{LOCATION}/workflows/{WORKFLOW_NAME}"
        )

    def trigger_workflow(self, workload_dict: dict) -> dict:
        """Triggers greencompute-orchestrator with the parsed workload payload."""
        payload = {
            "api_base_url": API_BASE_URL,
            "workload": workload_dict
        }

        execution = Execution(argument=json.dumps(payload))
        response = self.client.create_execution(
            parent=self.parent,
            execution=execution
        )

        return {
            "workflow_execution_name": response.name,
            "state": response.state.name,
            "start_time": response.start_time.isoformat() if response.start_time else None
        }
