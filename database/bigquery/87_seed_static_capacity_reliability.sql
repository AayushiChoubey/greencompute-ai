-- Static MVP capacity and reliability baseline.
-- Standard is treated as highly reliable.
-- Spot is treated as lower reliability because it can be interrupted.
-- These values are estimates, not live provider measurements.

MERGE `greencompute_metrics.capacity_observations` AS target
USING (
  SELECT DISTINCT
    CONCAT(
      'static-capacity-', region, '-', machine_type, '-',
      LOWER(provisioning_model), '-v1'
    ) AS capacity_observation_id,
    cloud_provider,
    region,
    machine_type,
    provisioning_model,
    TRUE AS capacity_available,
    CAST(
      CASE
        WHEN provisioning_model = 'STANDARD' THEN 0.98
        ELSE 0.75
      END AS NUMERIC
    ) AS capacity_score
  FROM `greencompute_metrics.price_observations`
  WHERE source_name = 'GCP_PRICING_API'
) AS source
ON target.capacity_observation_id = source.capacity_observation_id

WHEN NOT MATCHED THEN
  INSERT (
    capacity_observation_id,
    cloud_provider,
    region,
    machine_type,
    provisioning_model,
    capacity_available,
    capacity_score,
    observed_at,
    source_name,
    source_version,
    is_synthetic,
    raw_source_payload,
    ingested_at
  )
  VALUES (
    source.capacity_observation_id,
    source.cloud_provider,
    source.region,
    source.machine_type,
    source.provisioning_model,
    source.capacity_available,
    source.capacity_score,
    CURRENT_TIMESTAMP(),
    'STATIC_MVP_CAPACITY_BASELINE',
    'v1',
    TRUE,
    JSON '{"live_provider_check":false,"standard_capacity_score":0.98,"spot_capacity_score":0.75}',
    CURRENT_TIMESTAMP()
  );

MERGE `greencompute_metrics.reliability_observations` AS target
USING (
  SELECT DISTINCT
    CONCAT(
      'static-reliability-', region, '-', machine_type, '-',
      LOWER(provisioning_model), '-v1'
    ) AS reliability_observation_id,
    cloud_provider,
    region,
    machine_type,
    provisioning_model,
    CAST(
      CASE
        WHEN provisioning_model = 'STANDARD' THEN 0.99
        ELSE 0.85
      END AS NUMERIC
    ) AS reliability_score,
    CAST(
      CASE
        WHEN provisioning_model = 'STANDARD' THEN 0.01
        ELSE 0.15
      END AS NUMERIC
    ) AS interruption_risk_score
  FROM `greencompute_metrics.price_observations`
  WHERE source_name = 'GCP_PRICING_API'
) AS source
ON target.reliability_observation_id = source.reliability_observation_id

WHEN NOT MATCHED THEN
  INSERT (
    reliability_observation_id,
    cloud_provider,
    region,
    machine_type,
    provisioning_model,
    reliability_score,
    interruption_risk_score,
    observed_at,
    source_name,
    source_version,
    is_synthetic,
    raw_source_payload,
    ingested_at
  )
  VALUES (
    source.reliability_observation_id,
    source.cloud_provider,
    source.region,
    source.machine_type,
    source.provisioning_model,
    source.reliability_score,
    source.interruption_risk_score,
    CURRENT_TIMESTAMP(),
    'STATIC_MVP_RELIABILITY_BASELINE',
    'v1',
    TRUE,
    JSON '{"live_provider_check":false,"standard_reliability":0.99,"spot_reliability":0.85}',
    CURRENT_TIMESTAMP()
  );
