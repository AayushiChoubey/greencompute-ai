-- Immutable workload, optimization, decision, and execution evidence.

CREATE TABLE IF NOT EXISTS `greencompute_events.workload_run_events` (
  event_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  workload_run_id STRING NOT NULL,
  workload_definition_version_id STRING NOT NULL,
  policy_version_id STRING NOT NULL,
  idempotency_key STRING,
  correlation_id STRING,

  event_type STRING NOT NULL,
  run_state STRING NOT NULL,
  event_timestamp TIMESTAMP NOT NULL,
  requested_local_timezone STRING,
  requested_start_at TIMESTAMP,
  deadline_at TIMESTAMP,

  actor_type STRING,
  actor_id STRING,
  payload JSON,
  schema_version INT64 NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(event_timestamp)
CLUSTER BY organization_id, workload_run_id, event_type;

CREATE TABLE IF NOT EXISTS `greencompute_events.optimization_runs` (
  optimization_run_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  workload_run_id STRING NOT NULL,
  workload_definition_version_id STRING NOT NULL,
  policy_version_id STRING NOT NULL,
  correlation_id STRING,

  optimizer_version STRING NOT NULL,
  optimization_status STRING NOT NULL,
  objective_configuration JSON,
  metric_snapshot_references ARRAY<STRING>,
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP,
  input_snapshot JSON,

  schema_version INT64 NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(started_at)
CLUSTER BY organization_id, workload_run_id, optimization_status;

CREATE TABLE IF NOT EXISTS `greencompute_events.candidate_evaluations` (
  candidate_evaluation_id STRING NOT NULL,
  optimization_run_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  workload_run_id STRING NOT NULL,

  region STRING NOT NULL,
  proposed_start_at TIMESTAMP NOT NULL,
  predicted_finish_at TIMESTAMP,
  machine_type STRING NOT NULL,
  provisioning_model STRING NOT NULL,

  estimated_compute_cost NUMERIC,
  estimated_transfer_cost NUMERIC,
  currency_code STRING,
  carbon_score NUMERIC,
  estimated_co2e NUMERIC,
  reliability_score NUMERIC,
  capacity_score NUMERIC,
  sla_buffer_seconds INT64,

  is_feasible BOOL NOT NULL,
  rejection_reasons ARRAY<STRING>,
  pareto_rank INT64,
  final_score NUMERIC,
  candidate_rank INT64,
  metric_snapshot JSON,

  evaluated_at TIMESTAMP NOT NULL,
  schema_version INT64 NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(evaluated_at)
CLUSTER BY organization_id, optimization_run_id, is_feasible, region;

CREATE TABLE IF NOT EXISTS `greencompute_events.policy_evaluations` (
  policy_evaluation_id STRING NOT NULL,
  candidate_evaluation_id STRING NOT NULL,
  optimization_run_id STRING NOT NULL,
  policy_version_id STRING NOT NULL,
  organization_id STRING NOT NULL,

  rule_name STRING NOT NULL,
  rule_category STRING NOT NULL,
  passed BOOL NOT NULL,
  expected_value JSON,
  actual_value JSON,
  evaluation_reason STRING,

  evaluated_at TIMESTAMP NOT NULL,
  schema_version INT64 NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(evaluated_at)
CLUSTER BY organization_id, optimization_run_id, candidate_evaluation_id, passed;

CREATE TABLE IF NOT EXISTS `greencompute_events.optimization_decisions` (
  decision_id STRING NOT NULL,
  optimization_run_id STRING NOT NULL,
  candidate_evaluation_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  workload_run_id STRING NOT NULL,

  decision_type STRING NOT NULL,
  is_selected BOOL NOT NULL,
  selection_rank INT64,
  decision_reason STRING NOT NULL,
  decision_explanation JSON,
  fallback_candidate_evaluation_id STRING,

  estimated_total_cost NUMERIC,
  currency_code STRING,
  carbon_score NUMERIC,
  reliability_score NUMERIC,
  sla_buffer_seconds INT64,

  decision_timestamp TIMESTAMP NOT NULL,
  schema_version INT64 NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(decision_timestamp)
CLUSTER BY organization_id, workload_run_id, decision_type, is_selected;

CREATE TABLE IF NOT EXISTS `greencompute_events.execution_events` (
  event_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  workload_run_id STRING NOT NULL,
  decision_id STRING NOT NULL,
  execution_attempt_id STRING NOT NULL,
  cloud_provider STRING NOT NULL,
  batch_job_id STRING,

  attempt_number INT64 NOT NULL,
  event_type STRING NOT NULL,
  execution_status STRING NOT NULL,
  event_timestamp TIMESTAMP NOT NULL,

  region STRING,
  actual_runtime_seconds INT64,
  actual_cost NUMERIC,
  currency_code STRING,
  retryable BOOL,
  error_code STRING,
  error_message STRING,
  event_details JSON,

  correlation_id STRING,
  schema_version INT64 NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(event_timestamp)
CLUSTER BY organization_id, workload_run_id, execution_attempt_id, execution_status;
