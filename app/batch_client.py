"""Google Cloud Batch submission adapter and execution event recorder."""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from google.cloud import batch_v1
from google.cloud import bigquery
from app.models import Candidate, ProvisioningModel

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "greencompute-ai")
logger = logging.getLogger(__name__)


class CloudBatchAdapter:
    def __init__(self):
        self.batch_client = batch_v1.BatchServiceClient()
        self.bq_client = bigquery.Client(project=PROJECT_ID)

    def submit_batch_job(
        self,
        workload_id: str,
        candidate: Candidate,
    ) -> str:
        """Submits a minimal test batch job configured with candidate specs."""
        region = candidate.region
        parent = f"projects/{PROJECT_ID}/locations/{region}"
        job_id = f"gc-job-{uuid.uuid4().hex[:8]}"

        # 1. Runnable task (Monte Carlo prototype script)
        runnable = batch_v1.Runnable()
        runnable.script = batch_v1.Runnable.Script()
        runnable.script.text = (
            "echo 'GreenCompute AI Execution Starting...'; "
            f"echo 'Running on Region: {region}, Machine: {candidate.machine_type}, Provisioning: {candidate.provisioning_model}'; "
            "python3 -c 'import random; print(\"Monte Carlo Pi Estimate:\", 4 * sum(random.random()**2 + random.random()**2 <= 1 for _ in range(1_000_000)) / 1_000_000)'; "
            "echo 'Task Completed Successfully.'"
        )

        task = batch_v1.TaskSpec()
        task.runnables = [runnable]
        task.max_retry_count = 1

        task_group = batch_v1.TaskGroup()
        task_group.task_count = 1
        task_group.task_spec = task

        # 2. Allocation Policy (Region, Machine Type, Spot)
        allocation_policy = batch_v1.AllocationPolicy()
        instance_policy = batch_v1.AllocationPolicy.InstancePolicy()
        instance_policy.machine_type = candidate.machine_type

        if candidate.provisioning_model == ProvisioningModel.SPOT:
            instance_policy.provisioning_model = "SPOT"
        else:
            instance_policy.provisioning_model = "STANDARD"

        instance_policy_template = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
        instance_policy_template.policy = instance_policy
        allocation_policy.instances = [instance_policy_template]

        location_policy = batch_v1.AllocationPolicy.LocationPolicy()
        location_policy.allowed_locations = [f"regions/{region}"]
        allocation_policy.location = location_policy

        # 3. Assemble Job
        job = batch_v1.Job()
        job.task_groups = [task_group]
        job.allocation_policy = allocation_policy
        job.logs_policy = batch_v1.LogsPolicy()
        job.logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING

        create_request = batch_v1.CreateJobRequest(
            parent=parent,
            job_id=job_id,
            job=job,
        )

        response = self.batch_client.create_job(request=create_request)
        return response.name

    def record_execution_event(
        self,
        workload_id: str,
        decision_id: str,
        execution_attempt_id: str,
        batch_job_id: str,
        region: str,
        event_type: str,
        status: str,
        correlation_id: str,
        details: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
    ):
        """Writes execution trace directly to greencompute_events.execution_events."""
        now_iso = datetime.now(timezone.utc).isoformat()
        event_id = event_id or f"exec_ev_{uuid.uuid4().hex[:12]}"

        row = [{
            "event_id": event_id,
            "organization_id": "org-retail-demo",
            "workload_run_id": workload_id,
            "decision_id": decision_id,
            "execution_attempt_id": execution_attempt_id,
            "cloud_provider": "GCP",
            "batch_job_id": batch_job_id,
            "attempt_number": 1,
            "event_type": event_type,
            "execution_status": status,
            "event_timestamp": now_iso,
            "region": region,
            "actual_runtime_seconds": (details or {}).get("actual_runtime_seconds"),
            "actual_cost": (details or {}).get("actual_cost"),
            "currency_code": "USD",
            "retryable": True,
            "error_code": None,
            "error_message": None,
            "event_details": json.dumps(details or {}),
            "correlation_id": correlation_id,
            "schema_version": 1,
            "ingested_at": now_iso,
        }]

        errors = self.bq_client.insert_rows_json(
            f"{PROJECT_ID}.greencompute_events.execution_events",
            row,
            # The callback can be retried after a network failure. Supplying an
            # insert ID lets BigQuery de-duplicate immediate retried inserts.
            row_ids=[event_id],
        )
        if errors:
            logger.error("Failed to record execution event %s: %s", event_id, errors)
            raise RuntimeError(f"BigQuery rejected execution event {event_id}: {errors}")

        logger.info("Recorded execution event %s for job %s", event_id, batch_job_id)
