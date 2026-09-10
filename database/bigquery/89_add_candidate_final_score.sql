-- Adds the weighted optimizer score to existing candidate ledgers.
-- Safe to run repeatedly.
ALTER TABLE `greencompute_events.candidate_evaluations`
ADD COLUMN IF NOT EXISTS final_score NUMERIC;
