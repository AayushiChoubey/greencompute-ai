CREATE TABLE IF NOT EXISTS `greencompute_config.pricing_sku_mappings` (
  pricing_sku_mapping_id STRING NOT NULL,

  cloud_provider STRING NOT NULL,
  region STRING NOT NULL,
  machine_type STRING NOT NULL,
  provisioning_model STRING NOT NULL,

  component_type STRING NOT NULL,
  sku_id STRING NOT NULL,
  sku_display_name STRING NOT NULL,

  active BOOL NOT NULL,
  discovered_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL,
  schema_version INT64 NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY cloud_provider, region, machine_type, provisioning_model;

-- The SKU rows will be inserted in the next step.
