-- Read-only checks. Every check should return PASS and 0 violations.

SELECT
  'selected_decision_must_reference_feasible_candidate' AS check_name,
  COUNTIF(c.candidate_evaluation_id IS NULL OR c.is_feasible IS NOT TRUE) AS violation_count,
  IF(COUNTIF(c.candidate_evaluation_id IS NULL OR c.is_feasible IS NOT TRUE) = 0, 'PASS', 'FAIL') AS status
FROM `greencompute_events.optimization_decisions` d
LEFT JOIN `greencompute_events.candidate_evaluations` c
  ON d.candidate_evaluation_id = c.candidate_evaluation_id
WHERE d.is_selected = TRUE

UNION ALL

SELECT
  'decision_cost_must_have_currency',
  COUNTIF(estimated_total_cost IS NOT NULL AND currency_code IS NULL),
  IF(COUNTIF(estimated_total_cost IS NOT NULL AND currency_code IS NULL) = 0, 'PASS', 'FAIL')
FROM `greencompute_events.optimization_decisions`

UNION ALL

SELECT
  'candidate_must_reference_optimization_run',
  COUNTIF(o.optimization_run_id IS NULL),
  IF(COUNTIF(o.optimization_run_id IS NULL) = 0, 'PASS', 'FAIL')
FROM `greencompute_events.candidate_evaluations` c
LEFT JOIN `greencompute_events.optimization_runs` o
  ON c.optimization_run_id = o.optimization_run_id

UNION ALL

SELECT
  'policy_evaluation_must_reference_candidate',
  COUNTIF(c.candidate_evaluation_id IS NULL),
  IF(COUNTIF(c.candidate_evaluation_id IS NULL) = 0, 'PASS', 'FAIL')
FROM `greencompute_events.policy_evaluations` p
LEFT JOIN `greencompute_events.candidate_evaluations` c
  ON p.candidate_evaluation_id = c.candidate_evaluation_id

UNION ALL

SELECT
  'synthetic_carbon_must_have_source',
  COUNTIF(is_synthetic = TRUE AND (source_name IS NULL OR source_name = '')),
  IF(COUNTIF(is_synthetic = TRUE AND (source_name IS NULL OR source_name = '')) = 0, 'PASS', 'FAIL')
FROM `greencompute_metrics.carbon_observations`

UNION ALL

SELECT
  'workload_run_event_must_have_policy_version',
  COUNTIF(policy_version_id IS NULL OR policy_version_id = ''),
  IF(COUNTIF(policy_version_id IS NULL OR policy_version_id = '') = 0, 'PASS', 'FAIL')
FROM `greencompute_events.workload_run_events`;
