ALTER TABLE `greencompute_metrics.capacity_observations`
ADD COLUMN IF NOT EXISTS zone STRING;

ALTER TABLE `greencompute_metrics.capacity_observations`
ADD COLUMN IF NOT EXISTS requested_vm_count INT64;

ALTER TABLE `greencompute_metrics.capacity_observations`
ADD COLUMN IF NOT EXISTS obtainability_score NUMERIC;

ALTER TABLE `greencompute_metrics.capacity_observations`
ADD COLUMN IF NOT EXISTS estimated_uptime_seconds INT64;

ALTER TABLE `greencompute_metrics.price_observations`
ADD COLUMN IF NOT EXISTS sku_id STRING;

ALTER TABLE `greencompute_metrics.price_observations`
ADD COLUMN IF NOT EXISTS pricing_tier_start_amount NUMERIC;

ALTER TABLE `greencompute_metrics.price_observations`
ADD COLUMN IF NOT EXISTS contract_pricing_applied BOOL;
