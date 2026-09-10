CREATE OR REPLACE VIEW `greencompute_analytics.v_optimization_summary` AS
SELECT
  o.organization_id,
  o.workload_run_id,
  o.optimization_run_id,
  o.optimizer_version,
  o.optimization_status,
  o.started_at,
  o.completed_at,

  d.decision_id,
  d.decision_type,
  d.decision_reason,
  d.decision_timestamp,
  d.estimated_total_cost,
  d.currency_code,
  d.carbon_score,
  d.reliability_score,
  d.sla_buffer_seconds,

  c.region,
  c.machine_type,
  c.provisioning_model,
  c.proposed_start_at,
  c.predicted_finish_at
FROM `greencompute_events.optimization_runs` o
LEFT JOIN `greencompute_events.optimization_decisions` d
  ON o.optimization_run_id = d.optimization_run_id
  AND d.is_selected = TRUE
LEFT JOIN `greencompute_events.candidate_evaluations` c
  ON d.candidate_evaluation_id = c.candidate_evaluation_id;

CREATE OR REPLACE VIEW `greencompute_analytics.v_candidate_comparison` AS
SELECT
  c.organization_id,
  c.workload_run_id,
  c.optimization_run_id,
  c.candidate_evaluation_id,
  c.region,
  c.machine_type,
  c.provisioning_model,
  c.proposed_start_at,
  c.predicted_finish_at,
  c.estimated_compute_cost,
  c.estimated_transfer_cost,
  c.currency_code,
  c.carbon_score,
  c.reliability_score,
  c.capacity_score,
  c.sla_buffer_seconds,
  c.is_feasible,
  c.rejection_reasons,
  c.pareto_rank,
  c.candidate_rank,
  d.decision_type,
  d.is_selected
FROM `greencompute_events.candidate_evaluations` c
LEFT JOIN `greencompute_events.optimization_decisions` d
  ON c.candidate_evaluation_id = d.candidate_evaluation_id;

CREATE OR REPLACE VIEW `greencompute_analytics.v_execution_summary` AS
WITH latest_event AS (
  SELECT *
  FROM `greencompute_events.execution_events`
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY execution_attempt_id
    ORDER BY event_timestamp DESC, ingested_at DESC
  ) = 1
),
workflow_link AS (
  SELECT
    execution_attempt_id,
    ARRAY_AGG(
      JSON_VALUE(event_details, '$.workflow_execution_id')
      IGNORE NULLS
      ORDER BY event_timestamp DESC, ingested_at DESC
      LIMIT 1
    )[SAFE_OFFSET(0)] AS workflow_execution_id
  FROM `greencompute_events.execution_events`
  GROUP BY execution_attempt_id
)
SELECT
  e.organization_id,
  e.workload_run_id,
  e.decision_id,
  e.execution_attempt_id,
  e.batch_job_id,
  e.cloud_provider,
  e.region,
  e.attempt_number,
  e.execution_status,
  e.event_timestamp AS latest_status_at,
  e.actual_runtime_seconds,
  e.actual_cost,
  e.currency_code,
  e.retryable,
  e.error_code,
  e.error_message,
  e.event_details,
  w.workflow_execution_id
FROM latest_event e
LEFT JOIN workflow_link w USING (execution_attempt_id);

CREATE OR REPLACE VIEW `greencompute_analytics.v_daily_decision_metrics` AS
SELECT
  DATE(decision_timestamp) AS decision_date,
  organization_id,
  COUNTIF(is_selected) AS selected_decision_count,
  SUM(IF(is_selected, estimated_total_cost, CAST(0 AS NUMERIC))) AS selected_estimated_cost,
  AVG(IF(is_selected, carbon_score, NULL)) AS average_selected_carbon_score,
  AVG(IF(is_selected, reliability_score, NULL)) AS average_selected_reliability_score,
  COUNTIF(is_selected AND decision_type = 'FALLBACK') AS fallback_count
FROM `greencompute_events.optimization_decisions`
GROUP BY decision_date, organization_id;
