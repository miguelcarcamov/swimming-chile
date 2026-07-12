-- Add relay-result disambiguation fields to staging members.
-- Needed when a source has multiple relay rows with same event/team/club.

CREATE SCHEMA IF NOT EXISTS core;
SET search_path TO core, public;

ALTER TABLE stg_relay_result_member
    ADD COLUMN IF NOT EXISTS relay_rank_position TEXT,
    ADD COLUMN IF NOT EXISTS relay_result_time_ms TEXT;
