"""Gemini-powered Natural Language Workload Ingestion Layer with BigQuery Telemetry."""

import json
import os
import re
from datetime import datetime, timezone
from typing import Optional
from google import genai
from google.genai import types
from app.models import OptimizeRequest
from app.bigquery_client import BigQueryClient

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "greencompute-ai")


class PromptParser:
    def __init__(self, bq_client: Optional[BigQueryClient] = None):
        self.client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="us-central1",
        )
        self.model_name = "gemini-2.5-flash"
        self.bq_client = bq_client or BigQueryClient()

    def parse_workload_prompt(self, prompt_text: str) -> OptimizeRequest:
        """Parses freeform prompt into a validated OptimizeRequest instance, backed by execution history."""
        current_time_iso = datetime.now(timezone.utc).isoformat()

        prompt = f"""You are the GreenCompute AI workload parser. Convert natural language compute requirements into a valid JSON object matching the schema below.

Target JSON Schema Structure:
{{
  "workload_name": string,
  "workload_id": string,
  "policy_version_id": "pol_v1_default",
  "data_location_type": "PORTABLE" | "STRICT_LOCAL",
  "home_region": string,
  "allowed_regions": [string],
  "required_vcpus": integer,
  "required_memory_gb": integer,
  "estimated_runtime_minutes": integer or null,
  "earliest_start_at": string (ISO-8601 UTC),
  "deadline_at": string (ISO-8601 UTC),
  "minimum_reliability_score": float (between 0.0 and 1.0),
  "spot_allowed": boolean,
  "checkpointable": boolean
}}

Reference Time (UTC): {current_time_iso}

Rules:
1. "workload_id": If unspecified, create a slug prefixed with "wr_" (e.g., "wr_monte_carlo").
2. "estimated_runtime_minutes": Extract if mentioned. If NOT specified by the user, return null.
3. "required_vcpus" and "required_memory_gb": Default to 4 and 16 if omitted.
4. "home_region": Default to "asia-south1".
5. "allowed_regions": If data_location_type is "PORTABLE", default to ["asia-south1", "europe-west1"]. If "STRICT_LOCAL", allow only [home_region].
6. "data_location_type": Use "STRICT_LOCAL" if data must remain local/compliant; otherwise "PORTABLE".
7. Timestamps: Compute ISO-8601 UTC timestamps relative to reference time. "earliest_start_at" defaults to reference time.
8. Reliability: If spot/preemptible is accepted, set spot_allowed=true, checkpointable=true, minimum_reliability_score=0.80. Otherwise set spot_allowed=false, checkpointable=false, minimum_reliability_score=0.99.
9. Return ONLY the raw JSON object. No Markdown code fences or extra text.

User Workload Request:
"{prompt_text}"
"""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=1024,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )

        cleaned_json = response.text.strip()
        cleaned_json = re.sub(r"^```json\s*", "", cleaned_json)
        cleaned_json = re.sub(r"\s*```$", "", cleaned_json)
        data = json.loads(cleaned_json)

        # Fallback to BigQuery historical runtime if not specified in prompt
        if not data.get("estimated_runtime_minutes"):
            workload_title = data.get("workload_name", "")
            historical_estimate = self.bq_client.estimate_runtime_from_history(workload_title, default_minutes=60)
            data["estimated_runtime_minutes"] = historical_estimate

        if not data.get("required_vcpus"):
            data["required_vcpus"] = 4
        if not data.get("required_memory_gb"):
            data["required_memory_gb"] = 16.0

        return OptimizeRequest.model_validate(data)
