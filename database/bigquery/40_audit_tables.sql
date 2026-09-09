-- Append-only security, user-action, and data-quality audit evidence.

CREATE TABLE IF NOT EXISTS `greencompute_audit.audit_events` (
  audit_event_id STRING NOT NULL,
  organization_id STRING NOT NULL,

  actor_type STRING NOT NULL,
  actor_id STRING,
  action_name STRING NOT NULL,
  action_outcome STRING NOT NULL,

  resource_type STRING,
  resource_id STRING,
  correlation_id STRING,
  idempotency_key STRING,

  occurred_at TIMESTAMP NOT NULL,
  client_ip_hash STRING,
  request_metadata JSON,
  event_details JSON,

  schema_version INT64 NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(occurred_at)
CLUSTER BY organization_id, actor_id, action_name, resource_type;

CREATE TABLE IF NOT EXISTS `greencompute_audit.data_quality_events` (
  data_quality_event_id STRING NOT NULL,
  organization_id STRING,

  severity STRING NOT NULL,
  quality_category STRING NOT NULL,
  affected_dataset STRING,
  affected_table STRING,
  affected_record_id STRING,

  status STRING NOT NULL,
  detected_at TIMESTAMP NOT NULL,
  resolved_at TIMESTAMP,
  detection_source STRING NOT NULL,
  event_details JSON,

  schema_version INT64 NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(detected_at)
CLUSTER BY organization_id, severity, quality_category, status;
