MERGE `greencompute_config.machine_profiles` AS target
USING (
  SELECT * FROM UNNEST([
    STRUCT(
      'gcp-n2-standard-4-v1' AS machine_profile_id,
      'GCP' AS cloud_provider,
      'n2-standard-4' AS machine_type,
      'N2' AS machine_series,
      4 AS vcpu_count,
      CAST(16 AS NUMERIC) AS memory_gb,
      'LINUX' AS operating_system,
      TRUE AS supports_spot,
      'CPU_AND_MEMORY_COMPONENTS' AS price_calculation_method,
      TRUE AS active,
      1 AS schema_version
    ),
    STRUCT(
      'gcp-n2-standard-16-v1',
      'GCP',
      'n2-standard-16',
      'N2',
      16,
      CAST(64 AS NUMERIC),
      'LINUX',
      TRUE,
      'CPU_AND_MEMORY_COMPONENTS',
      TRUE,
      1
    ),
    STRUCT(
      'gcp-n2-standard-32-v1',
      'GCP',
      'n2-standard-32',
      'N2',
      32,
      CAST(128 AS NUMERIC),
      'LINUX',
      TRUE,
      'CPU_AND_MEMORY_COMPONENTS',
      TRUE,
      1
    )
  ])
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

