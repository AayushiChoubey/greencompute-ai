-- Time-series metric inputs used by the optimizer.
-- Synthetic values must always have is_synthetic = TRUE.

CREATE TABLE IF NOT EXISTS `greencompute_metrics.price_observations` (
  price_observation_id STRING NOT NULL,
  cloud_provider STRING NOT NULL,
  region STRING NOT NULL,
  machine_type STRING NOT NULL,
  provisioning_model STRING NOT NULL,
  operating_system STRING,
  currency_code STRING NOT NULL,
  billing_unit STRING NOT NULL,
  price_per_unit NUMERIC NOT NULL,

  observed_at TIMESTAMP NOT NULL,
  effective_from TIMESTAMP,
  effective_to TIMESTAMP,
  source_name STRING NOT NULL,
  source_version STRING,
  is_synthetic BOOL NOT NULL,
  raw_source_payload JSON,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(observed_at)
CLUSTER BY cloud_provider, region, machine_type, provisioning_model;

CREATE TABLE IF NOT EXISTS `greencompute_metrics.carbon_observations` (
  carbon_observation_id STRING NOT NULL,
  cloud_provider STRING NOT NULL,
  region STRING NOT NULL,
  carbon_score NUMERIC,
  estimated_co2e_per_kwh NUMERIC,
  carbon_unit STRING,
  observed_at TIMESTAMP NOT NULL,

  source_name STRING NOT NULL,
  source_version STRING,
  is_synthetic BOOL NOT NULL,
  confidence_level STRING,
  raw_source_payload JSON,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(observed_at)
CLUSTER BY cloud_provider, region, source_name;

CREATE TABLE IF NOT EXISTS `greencompute_metrics.reliability_observations` (
  reliability_observation_id STRING NOT NULL,
  cloud_provider STRING NOT NULL,
  region STRING NOT NULL,
  machine_type STRING,
  provisioning_model STRING,
  reliability_score NUMERIC NOT NULL,
  interruption_risk_score NUMERIC,
  observed_at TIMESTAMP NOT NULL,

  source_name STRING NOT NULL,
  source_version STRING,
  is_synthetic BOOL NOT NULL,
  raw_source_payload JSON,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(observed_at)
CLUSTER BY cloud_provider, region, machine_type, provisioning_model;

CREATE TABLE IF NOT EXISTS `greencompute_metrics.capacity_observations` (
  capacity_observation_id STRING NOT NULL,
  cloud_provider STRING NOT NULL,
  region STRING NOT NULL,
  machine_type STRING,
  provisioning_model STRING,
  capacity_available BOOL,
  capacity_score NUMERIC,
  observed_at TIMESTAMP NOT NULL,

  source_name STRING NOT NULL,
  source_version STRING,
  is_synthetic BOOL NOT NULL,
  raw_source_payload JSON,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(observed_at)
CLUSTER BY cloud_provider, region, machine_type, provisioning_model;

CREATE TABLE IF NOT EXISTS `greencompute_metrics.data_transfer_observations` (
  transfer_observation_id STRING NOT NULL,
  cloud_provider STRING NOT NULL,
  source_region STRING NOT NULL,
  destination_region STRING NOT NULL,
  estimated_transfer_cost NUMERIC,
  currency_code STRING,
  estimated_transfer_seconds INT64,
  observed_at TIMESTAMP NOT NULL,

  source_name STRING NOT NULL,
  source_version STRING,
  is_synthetic BOOL NOT NULL,
  raw_source_payload JSON,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(observed_at)
CLUSTER BY cloud_provider, source_region, destination_region;
