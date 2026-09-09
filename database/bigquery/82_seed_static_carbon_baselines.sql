-- Static carbon-intensity baseline for MVP decisions.
-- Unit: grams CO2e per kWh.
-- These are rounded, fact-informed comparative estimates.
-- They are NOT live forecasts or measured Google data-centre emissions.

MERGE `greencompute_metrics.carbon_observations` AS target
USING (
  SELECT * FROM UNNEST([
    STRUCT('carbon-static-asia-south1-v1' AS carbon_observation_id, 'GCP' AS cloud_provider, 'asia-south1' AS region, CAST(650 AS NUMERIC) AS carbon_value),
    STRUCT('carbon-static-asia-south2-v1', 'GCP', 'asia-south2', CAST(650 AS NUMERIC)),
    STRUCT('carbon-static-asia-southeast1-v1', 'GCP', 'asia-southeast1', CAST(410 AS NUMERIC)),
    STRUCT('carbon-static-asia-southeast2-v1', 'GCP', 'asia-southeast2', CAST(720 AS NUMERIC)),
    STRUCT('carbon-static-asia-northeast1-v1', 'GCP', 'asia-northeast1', CAST(430 AS NUMERIC)),
    STRUCT('carbon-static-asia-northeast2-v1', 'GCP', 'asia-northeast2', CAST(430 AS NUMERIC)),
    STRUCT('carbon-static-australia-southeast1-v1', 'GCP', 'australia-southeast1', CAST(550 AS NUMERIC)),
    STRUCT('carbon-static-us-central1-v1', 'GCP', 'us-central1', CAST(520 AS NUMERIC)),
    STRUCT('carbon-static-us-east4-v1', 'GCP', 'us-east4', CAST(370 AS NUMERIC)),
    STRUCT('carbon-static-europe-west1-v1', 'GCP', 'europe-west1', CAST(170 AS NUMERIC))
  ])
) AS source
ON target.carbon_observation_id = source.carbon_observation_id

WHEN NOT MATCHED THEN
  INSERT (
    carbon_observation_id,
    cloud_provider,
    region,
    carbon_score,
    estimated_co2e_per_kwh,
    carbon_unit,
    observed_at,
    source_name,
    source_version,
    is_synthetic,
    confidence_level,
    raw_source_payload,
    ingested_at
  )
  VALUES (
    source.carbon_observation_id,
    source.cloud_provider,
    source.region,
    source.carbon_value,
    source.carbon_value,
    'gCO2e/kWh',
    CURRENT_TIMESTAMP(),
    'STATIC_GRID_INTENSITY_BASELINE',
    'v1',
    TRUE,
    'LOW',
    JSON '{"method":"constant fact-informed MVP baseline","live_forecast":false,"measured_google_datacenter_emissions":false}',
    CURRENT_TIMESTAMP()
  );
