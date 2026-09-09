CREATE TABLE IF NOT EXISTS `greencompute_config.machine_profiles` (
  machine_profile_id STRING NOT NULL,
  cloud_provider STRING NOT NULL,
  machine_type STRING NOT NULL,
  machine_series STRING NOT NULL,

  vcpu_count INT64 NOT NULL,
  memory_gb NUMERIC NOT NULL,
  operating_system STRING NOT NULL,

  supports_spot BOOL NOT NULL,
  price_calculation_method STRING NOT NULL,

  active BOOL NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  schema_version INT64 NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY cloud_provider, machine_series, machine_type;

MERGE `greencompute_config.machine_profiles` AS target
USING (
  SELECT
    'gcp-n2-standard-8-v1' AS machine_profile_id,
    'GCP' AS cloud_provider,
    'n2-standard-8' AS machine_type,
    'N2' AS machine_series,
    8 AS vcpu_count,
    CAST(32 AS NUMERIC) AS memory_gb,
    'LINUX' AS operating_system,
    TRUE AS supports_spot,
    'CPU_AND_MEMORY_COMPONENTS' AS price_calculation_method,
    TRUE AS active,
    1 AS schema_version
) AS source
ON target.machine_profile_id = source.machine_profile_id

WHEN NOT MATCHED THEN
  INSERT (
    machine_profile_id, cloud_provider, machine_type, machine_series,
    vcpu_count, memory_gb, operating_system,
    supports_spot, price_calculation_method,
    active, created_at, updated_at, schema_version
  )
  VALUES (
    source.machine_profile_id, source.cloud_provider,
    source.machine_type, source.machine_series,
    source.vcpu_count, source.memory_gb, source.operating_system,
    source.supports_spot, source.price_calculation_method,
    source.active, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(),
    source.schema_version
  );
