CREATE TABLE IF NOT EXISTS `greencompute_config.cloud_region_catalog` (
  cloud_region_id STRING NOT NULL,
  cloud_provider STRING NOT NULL,
  region STRING NOT NULL,
  country_code STRING NOT NULL,
  metro_area STRING NOT NULL,

  -- Approximate city coordinates for carbon-provider lookup.
  -- These are NOT physical Google datacentre coordinates.
  carbon_query_latitude NUMERIC,
  carbon_query_longitude NUMERIC,
  carbon_mapping_method STRING NOT NULL,
  carbon_mapping_confidence STRING NOT NULL,

  active BOOL NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  schema_version INT64 NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY cloud_provider, country_code, region;

MERGE `greencompute_config.cloud_region_catalog` AS target
USING (
  SELECT * FROM UNNEST([
    STRUCT('gcp-asia-south1' AS cloud_region_id, 'GCP' AS cloud_provider, 'asia-south1' AS region, 'IN' AS country_code, 'Mumbai' AS metro_area, CAST(19.0760 AS NUMERIC) AS carbon_query_latitude, CAST(72.8777 AS NUMERIC) AS carbon_query_longitude),
    STRUCT('gcp-asia-south2', 'GCP', 'asia-south2', 'IN', 'Delhi', CAST(28.6139 AS NUMERIC), CAST(77.2090 AS NUMERIC)),
    STRUCT('gcp-asia-southeast1', 'GCP', 'asia-southeast1', 'SG', 'Singapore', CAST(1.3521 AS NUMERIC), CAST(103.8198 AS NUMERIC)),
    STRUCT('gcp-asia-southeast2', 'GCP', 'asia-southeast2', 'ID', 'Jakarta', CAST(-6.2088 AS NUMERIC), CAST(106.8456 AS NUMERIC)),
    STRUCT('gcp-asia-northeast1', 'GCP', 'asia-northeast1', 'JP', 'Tokyo', CAST(35.6762 AS NUMERIC), CAST(139.6503 AS NUMERIC)),
    STRUCT('gcp-asia-northeast2', 'GCP', 'asia-northeast2', 'JP', 'Osaka', CAST(34.6937 AS NUMERIC), CAST(135.5023 AS NUMERIC)),
    STRUCT('gcp-australia-southeast1', 'GCP', 'australia-southeast1', 'AU', 'Sydney', CAST(-33.8688 AS NUMERIC), CAST(151.2093 AS NUMERIC)),
    STRUCT('gcp-us-central1', 'GCP', 'us-central1', 'US', 'Iowa', CAST(41.8780 AS NUMERIC), CAST(-93.0977 AS NUMERIC)),
    STRUCT('gcp-us-east4', 'GCP', 'us-east4', 'US', 'Northern Virginia', CAST(38.8048 AS NUMERIC), CAST(-77.0469 AS NUMERIC)),
    STRUCT('gcp-europe-west1', 'GCP', 'europe-west1', 'BE', 'Belgium', CAST(50.4500 AS NUMERIC), CAST(3.8200 AS NUMERIC))
  ])
) AS source
ON target.cloud_region_id = source.cloud_region_id
WHEN NOT MATCHED THEN
  INSERT (
    cloud_region_id, cloud_provider, region, country_code, metro_area,
    carbon_query_latitude, carbon_query_longitude,
    carbon_mapping_method, carbon_mapping_confidence,
    active, created_at, updated_at, schema_version
  )
  VALUES (
    source.cloud_region_id, source.cloud_provider, source.region,
    source.country_code, source.metro_area,
    source.carbon_query_latitude, source.carbon_query_longitude,
    'METRO_APPROXIMATION', 'MEDIUM',
    TRUE, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), 1
  );
