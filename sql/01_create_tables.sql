CREATE TABLE IF NOT EXISTS `greencompute.workloads` (
  workload_id STRING,
  workload_name STRING,
  estimated_runtime_minutes INT64,
  deadline TIMESTAMP,
  allowed_regions ARRAY<STRING>,
  required_cpu INT64,
  required_memory_gb INT64,
  spot_allowed BOOLEAN,
  checkpointable BOOLEAN,
  reliability_requirement STRING,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `greencompute.policies` (
  policy_id STRING,
  policy_name STRING,
  allowed_regions ARRAY<STRING>,
  minimum_reliability_score FLOAT64,
  maximum_cost_increase_percent FLOAT64,
  prefer_lower_carbon BOOLEAN,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `greencompute.region_metrics` (
  region STRING,
  machine_type STRING,
  provisioning STRING,
  hourly_cost_usd FLOAT64,
  carbon_impact_score FLOAT64,
  reliability_score FLOAT64,
  metric_timestamp TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `greencompute.candidates` (
  candidate_id STRING,
  workload_id STRING,
  region STRING,
  machine_type STRING,
  provisioning STRING,
  proposed_start_time TIMESTAMP,
  predicted_finish_time TIMESTAMP,
  estimated_cost_usd FLOAT64,
  carbon_impact_score FLOAT64,
  reliability_score FLOAT64,
  feasible BOOLEAN,
  rejection_reason STRING,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `greencompute.recommendations` (
  recommendation_id STRING,
  workload_id STRING,
  selected_candidate_id STRING,
  selection_reason STRING,
  estimated_cost_usd FLOAT64,
  carbon_impact_score FLOAT64,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `greencompute.executions` (
  execution_id STRING,
  workload_id STRING,
  batch_job_id STRING,
  status STRING,
  actual_start_time TIMESTAMP,
  actual_end_time TIMESTAMP,
  actual_runtime_minutes INT64,
  created_at TIMESTAMP
);
