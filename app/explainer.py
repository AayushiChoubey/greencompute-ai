"""Gemini-powered Explainability Layer for GreenCompute decisions."""

import os
from typing import List
from google import genai
from google.genai import types
from app.models import Candidate, OptimizeRequest

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "greencompute-ai")


class DecisionExplainer:
    def __init__(self):
        self.client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="us-central1"
        )
        self.model_name = "gemini-2.5-flash"

    def generate_explanation(
        self,
        request: OptimizeRequest,
        selected_candidate: Candidate,
        top_alternatives: List[Candidate],
    ) -> str:
        """Generates a complete executive trade-off explanation comparing the winning choice to alternatives."""
        
        alt_summary = []
        for alt in top_alternatives[:3]:
            status = "Feasible" if alt.is_feasible else f"Rejected ({', '.join(alt.rejection_reasons)})"
            alt_summary.append(
                f"- Region: {alt.region}, Machine: {alt.machine_type}, Model: {alt.provisioning_model.value}, "
                f"Cost: ${alt.estimated_compute_cost_usd:.4f}, Carbon: {alt.carbon_score} gCO2e/kWh, Status: {status}"
            )

        prompt = f"""You are the GreenCompute AI optimization explainability engine.
Provide an executive, deterministic summary explaining why the selected compute candidate was chosen over the alternative options.

Workload Specifications:
- Name: {request.workload_name} (ID: {request.workload_id})
- Data Locality: {request.data_location_type.value}
- Home Region: {request.home_region}
- Allowed Regions: {', '.join(request.allowed_regions)}
- Required vCPUs: {request.required_vcpus}, Memory: {request.required_memory_gb}GB
- Checkpointable: {request.checkpointable}
- Spot Allowed: {request.spot_allowed}

Selected Winner:
- Region: {selected_candidate.region}
- Machine Type: {selected_candidate.machine_type}
- Provisioning Model: {selected_candidate.provisioning_model.value}
- Estimated Compute Cost: ${selected_candidate.estimated_compute_cost_usd:.4f} USD
- Carbon Score (Grid Intensity): {selected_candidate.carbon_score} gCO2e/kWh
- Reliability Score: {selected_candidate.reliability_score}
- SLA Buffer: {selected_candidate.sla_buffer_minutes} minutes

Top Competitors & Alternatives:
{chr(10).join(alt_summary)}

Instructions:
1. Explain in 3-4 bullet points:
   - Why this specific region and provisioning model won on cost and carbon efficiency.
   - Why it was legally permissible (referencing data portability and checkpointability).
   - How much cost or carbon was saved compared to running on the home region baseline.
2. Maintain a concise, professional cloud architecture tone.
3. Keep the output under 150 words. Do not trail off."""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=1024,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            
            if response.text:
                return response.text.strip()
            elif response.candidates and response.candidates[0].content:
                parts = [p.text for p in response.candidates[0].content.parts if hasattr(p, 'text') and p.text]
                if parts:
                    return "".join(parts).strip()

            return f"Selected {selected_candidate.machine_type} ({selected_candidate.provisioning_model.value}) in {selected_candidate.region} at ${selected_candidate.estimated_compute_cost_usd:.4f} and {selected_candidate.carbon_score} gCO2e/kWh."
        except Exception as e:
            return f"Explainability generation fallback: Selected {selected_candidate.machine_type} ({selected_candidate.provisioning_model.value}) in {selected_candidate.region}. Error: {str(e)}"
