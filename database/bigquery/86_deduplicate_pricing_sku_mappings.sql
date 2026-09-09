-- Keep one row for each exact mapping ID.
-- All removed rows are duplicate copies of the same mapping.

CREATE TEMP TABLE unique_mappings AS
SELECT
  ARRAY_AGG(mapping ORDER BY discovered_at DESC LIMIT 1)[OFFSET(0)] AS mapping
FROM `greencompute_config.pricing_sku_mappings` AS mapping
GROUP BY pricing_sku_mapping_id;

BEGIN TRANSACTION;

DELETE FROM `greencompute_config.pricing_sku_mappings`
WHERE TRUE;

INSERT INTO `greencompute_config.pricing_sku_mappings`
SELECT mapping.*
FROM unique_mappings;

COMMIT TRANSACTION;
