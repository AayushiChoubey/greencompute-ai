-- Immutable snapshots used to reproduce an optimization decision.
-- The operational source of truth will later be PostgreSQL.

CREATE TABLE IF NOT EXISTS `greencompute_config.workload_definition_versions` (
  workload_definition_version_id STRING NOT NULL,
  workload_definition_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  team_id STRING,
  cost_center_id STRING,
  version_number INT64 NOT NULL,

  workload_name STRING NOT NULL,
  workload_type STRING NOT NULL,
  estimated_runtime_seconds INT64,
  required_cpu_millicores INT64,
  required_memory_mb INT64,
  checkpointable BOOL,
  spot_eligible BOOL,
  allowed_regions ARRAY<STRING>,
  requested_timezone STRING,
  data_residency_requirement STRING,
  baseline_execution_profile JSON,

  valid_from TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING,
  schema_version INT64 NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY organization_id, workload_definition_id;

CREATE TABLE IF NOT EXISTS `greencompute_config.policy_versions` (
  policy_version_id STRING NOT NULL,
  policy_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  version_number INT64 NOT NULL,

  policy_name STRING NOT NULL,
  allowed_regions ARRAY<STRING>,
  minimum_reliability_score FLOAT64,
  maximum_cost_increase_percent NUMERIC,
  spot_allowed BOOL,
  lower_carbon_preference BOOL,
  fallback_execution_profile JSON,
  policy_rules JSON,

  effective_from TIMESTAMP NOT NULL,
  effective_to TIMESTAMP,
  created_at TIMESTAMP NOT NULL,
  created_by STRING,
  schema_version INT64 NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY organization_id, policy_id;

CREATE TABLE IF NOT EXISTS `greencompute_config.data_asset_versions` (
  data_asset_version_id STRING NOT NULL,
  data_asset_id STRING NOT NULL,
  organization_id STRING NOT NULL,
  version_number INT64 NOT NULL,

  asset_name STRING NOT NULL,
  data_classification STRING,
  residency_regions ARRAY<STRING>,
  source_region STRING,
  transfer_allowed BOOL,
  transfer_constraints JSON,

  valid_from TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING,
  schema_version INT64 NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY organization_id, data_asset_id;
