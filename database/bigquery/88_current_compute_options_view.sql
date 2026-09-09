CREATE OR REPLACE VIEW `greencompute_analytics.v_current_compute_options` AS

WITH latest_price AS (
  SELECT * EXCEPT(row_number)
  FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY region, machine_type, provisioning_model
        ORDER BY observed_at DESC, ingested_at DESC
      ) AS row_number
    FROM `greencompute_metrics.price_observations`
    WHERE source_name = 'GCP_PRICING_API'
  )
  WHERE row_number = 1
),

latest_carbon AS (
  SELECT * EXCEPT(row_number)
  FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY region
        ORDER BY observed_at DESC, ingested_at DESC
      ) AS row_number
    FROM `greencompute_metrics.carbon_observations`
    WHERE source_name = 'STATIC_GRID_INTENSITY_BASELINE'
  )
  WHERE row_number = 1
),

latest_capacity AS (
  SELECT * EXCEPT(row_number)
  FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY region, machine_type, provisioning_model
        ORDER BY observed_at DESC, ingested_at DESC
      ) AS row_number
    FROM `greencompute_metrics.capacity_observations`
    WHERE source_name = 'STATIC_MVP_CAPACITY_BASELINE'
  )
  WHERE row_number = 1
),

latest_reliability AS (
  SELECT * EXCEPT(row_number)
  FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY region, machine_type, provisioning_model
        ORDER BY observed_at DESC, ingested_at DESC
      ) AS row_number
    FROM `greencompute_metrics.reliability_observations`
    WHERE source_name = 'STATIC_MVP_RELIABILITY_BASELINE'
  )
  WHERE row_number = 1
)

SELECT
  region_catalog.region,
  region_catalog.country_code,
  region_catalog.metro_area,

  machine.machine_type,
  machine.vcpu_count,
  machine.memory_gb,

  price.provisioning_model,
  price.price_per_unit AS hourly_price_usd,
  price.currency_code,
  price.observed_at AS price_snapshot_at,

  carbon.estimated_co2e_per_kwh AS carbon_intensity_gco2e_per_kwh,
  carbon.is_synthetic AS carbon_is_synthetic,

  capacity.capacity_available,
  capacity.capacity_score,
  reliability.reliability_score,
  reliability.interruption_risk_score,

  price.is_synthetic AS price_is_synthetic,
  capacity.is_synthetic AS capacity_is_synthetic,
  reliability.is_synthetic AS reliability_is_synthetic

FROM latest_price AS price
JOIN `greencompute_config.machine_profiles` AS machine
  ON price.cloud_provider = machine.cloud_provider
  AND price.machine_type = machine.machine_type
JOIN `greencompute_config.cloud_region_catalog` AS region_catalog
  ON price.cloud_provider = region_catalog.cloud_provider
  AND price.region = region_catalog.region
JOIN latest_carbon AS carbon
  ON price.cloud_provider = carbon.cloud_provider
  AND price.region = carbon.region
JOIN latest_capacity AS capacity
  ON price.cloud_provider = capacity.cloud_provider
  AND price.region = capacity.region
  AND price.machine_type = capacity.machine_type
  AND price.provisioning_model = capacity.provisioning_model
JOIN latest_reliability AS reliability
  ON price.cloud_provider = reliability.cloud_provider
  AND price.region = reliability.region
  AND price.machine_type = reliability.machine_type
  AND price.provisioning_model = reliability.provisioning_model
WHERE machine.active = TRUE
  AND region_catalog.active = TRUE;
