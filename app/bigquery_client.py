"""BigQuery adapter for reading compute options and persisting complete audit trails."""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from google.cloud import bigquery
from app.models import RegionMetric, ProvisioningModel, Candidate

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "greencompute-ai")


class BigQueryClient:
    def __init__(self):
        self.client = bigquery.Client(project=PROJECT_ID)

    def fetch_compute_options(self) -> List[RegionMetric]:
        query = f"""
            SELECT 
                region, machine_type, provisioning_model, vcpu_count, memory_gb,
                hourly_price_usd, carbon_intensity_gco2e_per_kwh, carbon_is_synthetic,
                capacity_available, reliability_score
            FROM `{PROJECT_ID}.greencompute_analytics.v_current_compute_options`
        """
        results = self.client.query(query).result()
        metrics = []
        for row in results:
            metrics.append(
                RegionMetric(
                    region=row["region"],
                    machine_type=row["machine_type"],
                    provisioning_model=ProvisioningModel(row["provisioning_model"]),
                    vcpus=int(row["vcpu_count"]),
                    memory_gb=float(row["memory_gb"]),
                    hourly_cost_usd=float(row["hourly_price_usd"]),
                    carbon_score=float(row["carbon_intensity_gco2e_per_kwh"]),
                    reliability_score=float(row["reliability_score"]),
                    capacity_available=bool(row["capacity_available"]),
                    carbon_is_synthetic=bool(row["carbon_is_synthetic"]),
                )
            )
        return metrics

    def record_full_optimization_run(
        self,
        optimization_run_id: str,
        decision_id: str,
        workload_id: str,
        policy_version_id: str,
        selected_candidate: Optional[Candidate],
        all_candidates: List[Candidate],
        reason: str,
        workload_input_dict: dict,
    ):
        now_iso = datetime.now(timezone.utc).isoformat()
        org_id = "org-retail-demo"
        workload_def_ver_id = f"wdv_{workload_id}_v1"

        # 1. Optimization Run Header
        run_rows = [{
            "optimization_run_id": optimization_run_id,
            "organization_id": org_id,
            "workload_run_id": workload_id,
            "workload_definition_version_id": workload_def_ver_id,
            "policy_version_id": policy_version_id,
            "correlation_id": optimization_run_id,
            "optimizer_version": "optimizer-mvp-v2-weighted",
            "optimization_status": "COMPLETED" if selected_candidate else "FAILED",
            "objective_configuration": json.dumps(
                workload_input_dict.get("objective_weights", {})
            ),
            "metric_snapshot_references": ["v_current_compute_options_snapshot"],
            "started_at": now_iso,
            "completed_at": now_iso,
            "input_snapshot": json.dumps(workload_input_dict, default=str),
            "schema_version": 1,
            "ingested_at": now_iso,
        }]

        # 2. Selected decision and explainable alternatives
        feasible_candidates = [c for c in all_candidates if c.is_feasible]
        decision_roles = []
        if selected_candidate:
            decision_roles.append(("SELECTED", selected_candidate, True, decision_id))
            decision_roles.extend([
                (
                    "CHEAPEST",
                    min(feasible_candidates, key=lambda c: c.estimated_compute_cost_usd),
                    False,
                    f"dec_{uuid.uuid4().hex[:12]}",
                ),
                (
                    "GREENEST",
                    min(feasible_candidates, key=lambda c: c.carbon_score),
                    False,
                    f"dec_{uuid.uuid4().hex[:12]}",
                ),
                (
                    "SAFEST",
                    max(feasible_candidates, key=lambda c: c.reliability_score),
                    False,
                    f"dec_{uuid.uuid4().hex[:12]}",
                ),
            ])
        else:
            decision_roles.append(("INFEASIBLE", None, False, decision_id))

        safest_candidate = (
            max(feasible_candidates, key=lambda c: c.reliability_score)
            if feasible_candidates
            else None
        )
        decision_rows = []
        for selection_rank, (decision_type, candidate, is_selected, row_decision_id) in enumerate(
            decision_roles, start=1
        ):
            decision_rows.append({
                "decision_id": row_decision_id,
                "optimization_run_id": optimization_run_id,
                "candidate_evaluation_id": candidate.candidate_id if candidate else "none",
                "organization_id": org_id,
                "workload_run_id": workload_id,
                "decision_type": decision_type,
                "is_selected": is_selected,
                "selection_rank": selection_rank,
                "decision_reason": (
                    reason
                    if is_selected or not candidate
                    else f"Retained {decision_type.lower()} feasible alternative."
                ),
                "decision_explanation": json.dumps({
                    "selection_reason": reason,
                    "role": decision_type,
                    "final_score": candidate.final_score if candidate else None,
                    "total_candidates": len(all_candidates),
                    "feasible_candidates": len(feasible_candidates),
                }),
                "fallback_candidate_evaluation_id": (
                    safest_candidate.candidate_id if safest_candidate else None
                ),
                "estimated_total_cost": (
                    float(candidate.estimated_compute_cost_usd) if candidate else 0.0
                ),
                "currency_code": "USD",
                "carbon_score": float(candidate.carbon_score) if candidate else 0.0,
                "reliability_score": float(candidate.reliability_score) if candidate else 0.0,
                "sla_buffer_seconds": int(candidate.sla_buffer_minutes * 60) if candidate else 0,
                "decision_timestamp": now_iso,
                "schema_version": 1,
                "ingested_at": now_iso,
            })

        # 3. Candidate & Policy Evaluations
        candidate_rows = []
        policy_rows = []

        for rank_idx, c in enumerate(all_candidates, start=1):
            candidate_rows.append({
                "candidate_evaluation_id": c.candidate_id,
                "optimization_run_id": optimization_run_id,
                "organization_id": org_id,
                "workload_run_id": workload_id,
                "region": c.region,
                "proposed_start_at": c.scheduled_start_at.isoformat(),
                "predicted_finish_at": c.predicted_finish_at.isoformat(),
                "machine_type": c.machine_type,
                "provisioning_model": c.provisioning_model.value,
                "estimated_compute_cost": float(c.estimated_compute_cost_usd),
                "estimated_transfer_cost": 0.0,
                "currency_code": "USD",
                "carbon_score": float(c.carbon_score),
                "estimated_co2e": None,
                "reliability_score": float(c.reliability_score),
                "capacity_score": 1.0,
                "sla_buffer_seconds": int(c.sla_buffer_minutes * 60),
                "is_feasible": c.is_feasible,
                "rejection_reasons": c.rejection_reasons,
                "pareto_rank": None,
                "final_score": c.final_score,
                "candidate_rank": rank_idx if c.is_feasible else None,
                "metric_snapshot": None,
                "evaluated_at": now_iso,
                "schema_version": 1,
                "ingested_at": now_iso,
            })

            if c.rejection_reasons:
                for reason_code in c.rejection_reasons:
                    policy_rows.append({
                        "policy_evaluation_id": f"pol_eval_{uuid.uuid4().hex[:12]}",
                        "candidate_evaluation_id": c.candidate_id,
                        "optimization_run_id": optimization_run_id,
                        "policy_version_id": policy_version_id,
                        "organization_id": org_id,
                        "rule_name": reason_code.split(":")[0].strip(),
                        "rule_category": "HARD_CONSTRAINT",
                        "passed": False,
                        "expected_value": None,
                        "actual_value": None,
                        "evaluation_reason": reason_code,
                        "evaluated_at": now_iso,
                        "schema_version": 1,
                        "ingested_at": now_iso,
                    })
            else:
                policy_rows.append({
                    "policy_evaluation_id": f"pol_eval_{uuid.uuid4().hex[:12]}",
                    "candidate_evaluation_id": c.candidate_id,
                    "optimization_run_id": optimization_run_id,
                    "policy_version_id": policy_version_id,
                    "organization_id": org_id,
                    "rule_name": "ALL_HARD_CONSTRAINTS",
                    "rule_category": "HARD_CONSTRAINT",
                    "passed": True,
                    "expected_value": None,
                    "actual_value": None,
                    "evaluation_reason": "All hard constraints satisfied",
                    "evaluated_at": now_iso,
                    "schema_version": 1,
                    "ingested_at": now_iso,
                })

        err0 = self.client.insert_rows_json(f"{PROJECT_ID}.greencompute_events.optimization_runs", run_rows)
        err1 = self.client.insert_rows_json(f"{PROJECT_ID}.greencompute_events.optimization_decisions", decision_rows)
        err2 = self.client.insert_rows_json(f"{PROJECT_ID}.greencompute_events.candidate_evaluations", candidate_rows)
        err3 = self.client.insert_rows_json(f"{PROJECT_ID}.greencompute_events.policy_evaluations", policy_rows)

        if err0 or err1 or err2 or err3:
            print(f"BigQuery warnings: runs={err0}, decisions={err1}, candidates={err2}, policies={err3}")
        else:
            print(f"Logged run header, decision, {len(candidate_rows)} candidate evals, and {len(policy_rows)} policy evals.")

    def estimate_runtime_from_history(self, workload_name: str, default_minutes: int = 60) -> int:
        """Estimates workload runtime in minutes using execution history, falling back to optimization history."""
        slug = workload_name.split()[0].lower() if workload_name else "sim"

        # 1. Use a conservative p90 of successful observed runtimes.
        exec_query = """
        SELECT 
          CAST(
            CEIL(APPROX_QUANTILES(actual_runtime_seconds, 100)[OFFSET(90)] / 60.0)
            AS INT64
          ) AS p90_runtime_minutes
        FROM `greencompute-ai.greencompute_analytics.v_execution_summary`
        WHERE execution_status = 'SUCCEEDED'
          AND actual_runtime_seconds IS NOT NULL
          AND actual_runtime_seconds > 0
          AND LOWER(workload_run_id) LIKE CONCAT('%', @workload_slug, '%')
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("workload_slug", "STRING", slug)]
        )
        try:
            results = list(self.client.query(exec_query, job_config=job_config).result())
            if results and results[0].p90_runtime_minutes and results[0].p90_runtime_minutes > 0:
                return max(int(results[0].p90_runtime_minutes), 5)
        except Exception as e:
            print(f"Execution history lookup notice: {e}")

        # 2. Fall back to planned durations in v_optimization_summary
        opt_query = """
        SELECT 
          CAST(CEIL(AVG(TIMESTAMP_DIFF(predicted_finish_at, proposed_start_at, MINUTE))) AS INT64) AS avg_runtime_minutes
        FROM `greencompute-ai.greencompute_analytics.v_optimization_summary`
        WHERE optimization_status = 'COMPLETED'
          AND proposed_start_at IS NOT NULL
          AND predicted_finish_at IS NOT NULL
          AND LOWER(workload_run_id) LIKE CONCAT('%', @workload_slug, '%')
        """
        try:
            results = list(self.client.query(opt_query, job_config=job_config).result())
            if results and results[0].avg_runtime_minutes and results[0].avg_runtime_minutes > 0:
                return max(int(results[0].avg_runtime_minutes), 5)
        except Exception as e:
            print(f"Optimization history lookup notice: {e}")

        return default_minutes
