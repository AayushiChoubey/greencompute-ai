-- All values are SYNTHETIC MVP data, not live provider measurements.

INSERT INTO `greencompute_metrics.price_observations` VALUES
  ('price-mumbai-standard-v1', 'GCP', 'asia-south1', 'n2-standard-8', 'STANDARD',
   'LINUX', 'USD', 'HOUR', 0.40, CURRENT_TIMESTAMP(), NULL, NULL,
   'MVP_SYNTHETIC', 'v1', TRUE, NULL, CURRENT_TIMESTAMP()),
  ('price-mumbai-spot-v1', 'GCP', 'asia-south1', 'n2-standard-8', 'SPOT',
   'LINUX', 'USD', 'HOUR', 0.16, CURRENT_TIMESTAMP(), NULL, NULL,
   'MVP_SYNTHETIC', 'v1', TRUE, NULL, CURRENT_TIMESTAMP()),
  ('price-delhi-standard-v1', 'GCP', 'asia-south2', 'n2-standard-8', 'STANDARD',
   'LINUX', 'USD', 'HOUR', 0.36, CURRENT_TIMESTAMP(), NULL, NULL,
   'MVP_SYNTHETIC', 'v1', TRUE, NULL, CURRENT_TIMESTAMP());

INSERT INTO `greencompute_metrics.carbon_observations` VALUES
  ('carbon-mumbai-v1', 'GCP', 'asia-south1', 60, NULL, 'NORMALIZED_SCORE',
   CURRENT_TIMESTAMP(), 'MVP_SYNTHETIC', 'v1', TRUE, 'DEMO_ONLY', NULL, CURRENT_TIMESTAMP()),
  ('carbon-delhi-v1', 'GCP', 'asia-south2', 45, NULL, 'NORMALIZED_SCORE',
   CURRENT_TIMESTAMP(), 'MVP_SYNTHETIC', 'v1', TRUE, 'DEMO_ONLY', NULL, CURRENT_TIMESTAMP());

INSERT INTO `greencompute_metrics.reliability_observations` VALUES
  ('reliability-mumbai-standard-v1', 'GCP', 'asia-south1', 'n2-standard-8', 'STANDARD',
   0.99, 0.01, CURRENT_TIMESTAMP(), 'MVP_SYNTHETIC', 'v1', TRUE, NULL, CURRENT_TIMESTAMP()),
  ('reliability-mumbai-spot-v1', 'GCP', 'asia-south1', 'n2-standard-8', 'SPOT',
   0.85, 0.15, CURRENT_TIMESTAMP(), 'MVP_SYNTHETIC', 'v1', TRUE, NULL, CURRENT_TIMESTAMP()),
  ('reliability-delhi-standard-v1', 'GCP', 'asia-south2', 'n2-standard-8', 'STANDARD',
   0.99, 0.01, CURRENT_TIMESTAMP(), 'MVP_SYNTHETIC', 'v1', TRUE, NULL, CURRENT_TIMESTAMP());

INSERT INTO `greencompute_metrics.capacity_observations` VALUES
  ('capacity-mumbai-standard-v1', 'GCP', 'asia-south1', 'n2-standard-8', 'STANDARD',
   TRUE, 0.95, CURRENT_TIMESTAMP(), 'MVP_SYNTHETIC', 'v1', TRUE, NULL, CURRENT_TIMESTAMP()),
  ('capacity-mumbai-spot-v1', 'GCP', 'asia-south1', 'n2-standard-8', 'SPOT',
   TRUE, 0.75, CURRENT_TIMESTAMP(), 'MVP_SYNTHETIC', 'v1', TRUE, NULL, CURRENT_TIMESTAMP()),
  ('capacity-delhi-standard-v1', 'GCP', 'asia-south2', 'n2-standard-8', 'STANDARD',
   TRUE, 0.98, CURRENT_TIMESTAMP(), 'MVP_SYNTHETIC', 'v1', TRUE, NULL, CURRENT_TIMESTAMP());

INSERT INTO `greencompute_metrics.data_transfer_observations` VALUES
  ('transfer-mumbai-delhi-v1', 'GCP', 'asia-south1', 'asia-south2',
   0.02, 'USD', 900, CURRENT_TIMESTAMP(), 'MVP_SYNTHETIC', 'v1', TRUE, NULL, CURRENT_TIMESTAMP());
