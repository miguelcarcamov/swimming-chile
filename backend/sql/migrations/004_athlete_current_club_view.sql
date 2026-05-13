-- Derive each athlete's current club from the latest observed competition.
-- This keeps core.athlete.club_id as a load/identity helper, not as current-club truth.

SET search_path TO core, public;

CREATE OR REPLACE VIEW athlete_current_club AS
WITH club_observations AS (
    SELECT
        r.athlete_id,
        r.club_id,
        e.competition_id,
        c.name AS competition_name,
        c.start_date AS competition_date,
        r.id AS observation_id,
        'individual'::TEXT AS observation_type
    FROM result r
    JOIN event e ON e.id = r.event_id
    JOIN competition c ON c.id = e.competition_id
    WHERE r.athlete_id IS NOT NULL
      AND r.club_id IS NOT NULL

    UNION ALL

    SELECT
        rrm.athlete_id,
        rr.club_id,
        e.competition_id,
        c.name AS competition_name,
        c.start_date AS competition_date,
        rr.id AS observation_id,
        'relay'::TEXT AS observation_type
    FROM relay_result_member rrm
    JOIN relay_result rr ON rr.id = rrm.relay_result_id
    JOIN event e ON e.id = rr.event_id
    JOIN competition c ON c.id = e.competition_id
    WHERE rrm.athlete_id IS NOT NULL
      AND rr.club_id IS NOT NULL
),
ranked AS (
    SELECT
        club_observations.*,
        ROW_NUMBER() OVER (
            PARTITION BY athlete_id
            ORDER BY
                competition_date DESC NULLS LAST,
                competition_id DESC,
                CASE observation_type WHEN 'individual' THEN 0 ELSE 1 END,
                observation_id DESC
        ) AS rn
    FROM club_observations
)
SELECT
    ranked.athlete_id,
    ranked.club_id,
    club.name AS club_name,
    ranked.competition_id,
    ranked.competition_name,
    ranked.competition_date,
    ranked.observation_type
FROM ranked
JOIN club ON club.id = ranked.club_id
WHERE ranked.rn = 1;
