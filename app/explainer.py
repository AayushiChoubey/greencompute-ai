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
        """Generate a grounded explanation without asking Gemini to invent savings."""
        
        alt_summary = []
        for alt in top_alternatives[:3]:
            status = "Feasible" if alt.is_feasible else f"Rejected ({', '.join(alt.rejection_reasons)})"
            alt_summary.append(
                f"- Region: {alt.region}, Machine: {alt.machine_type}, Model: {alt.provisioning_model.value}, "
                f"Cost: ${alt.estimated_compute_cost_usd:.4f}, Carbon: {alt.carbon_score} gCO2e/kWh, Status: {status}"
            )

        all_candidates = [selected_candidate] + list(top_alternatives)
        home_candidates = [
            candidate
            for candidate in all_candidates
            if candidate.region == request.home_region and candidate.is_feasible
        ]
        comparable_home = [
            candidate
            for candidate in home_candidates
            if candidate.machine_type == selected_candidate.machine_type
            and candidate.provisioning_model == selected_candidate.provisioning_model
        ]
        baseline_pool = comparable_home or home_candidates
        home_baseline = (
            min(baseline_pool, key=lambda candidate: candidate.estimated_compute_cost_usd)
            if baseline_pool
            else None
        )

        if home_baseline:
            selected_cost = selected_candidate.estimated_compute_cost_usd
            baseline_cost = home_baseline.estimated_compute_cost_usd
            cost_delta = (
                ((baseline_cost - selected_cost) / baseline_cost) * 100
                if baseline_cost > 0
                else 0.0
            )
            baseline_carbon = home_baseline.carbon_score
            carbon_delta = (
                ((baseline_carbon - selected_candidate.carbon_score) / baseline_carbon) * 100
                if baseline_carbon > 0
                else 0.0
            )
            baseline_facts = (
                f"Home-region comparison candidate: {home_baseline.region}, "
                f"{home_baseline.machine_type}, {home_baseline.provisioning_model.value}, "
                f"cost ${baseline_cost:.6f}, static grid intensity {baseline_carbon:.1f} gCO2e/kWh.\n"
                f"Exact modeled cost change versus that candidate: {cost_delta:+.1f}% "
                "(positive means selected candidate is cheaper).\n"
                f"Exact static grid-intensity reduction versus that candidate: {carbon_delta:+.1f}%."
            )
        else:
            baseline_facts = (
                "No feasible home-region comparison candidate is present in the supplied evidence. "
                "Cost and carbon percentage savings are unavailable and must not be estimated."
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
- Weighted Score: {selected_candidate.final_score}

Objective Weights:
- Cost: {request.objective_weights.cost}
- Carbon: {request.objective_weights.carbon}
- Reliability: {request.objective_weights.reliability}
- SLA Buffer: {request.objective_weights.sla_buffer}

Top Competitors & Alternatives:
{chr(10).join(alt_summary)}

Authoritative Comparison Facts:
{baseline_facts}

Instructions:
1. Explain in 3-4 bullet points:
   - Why this specific region and provisioning model won under the configured objective weights.
   - Why it was permitted by the supplied data-locality and checkpointing policy.
   - State cost or carbon differences only when supplied in Authoritative Comparison Facts.
2. Maintain a concise, professional cloud architecture tone.
3. Treat carbon as a static regional grid-intensity baseline, not measured workload emissions.
4. Never invent, approximate, recalculate, or alter a percentage or baseline value.
5. Do not describe policy compliance as a legal conclusion and do not describe execution near an existing replica as data migration.
6. Keep the output under 150 words. Do not trail off."""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
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
