-- =====================================================
-- Schema v0.1 - Natacion Chile
-- Database: natacion_chile
-- Schema: core
-- Estado actual: incluye resultados individuales, relevos
-- y tablas staging para cargas desde Excel/CSV/PDF parser.
-- =====================================================

CREATE SCHEMA IF NOT EXISTS core;
SET search_path TO core, public;

-- =====================================================
-- TABLE: source
-- =====================================================

CREATE TABLE source (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    base_url TEXT,
    notes TEXT,
    last_checked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- TABLE: source_document
-- =====================================================

CREATE TABLE source_document (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES source(id),
    document_name TEXT NOT NULL,
    document_type TEXT NOT NULL DEFAULT 'results_pdf',
    source_url TEXT,
    storage_path TEXT,
    checksum_sha256 TEXT,
    parser_version TEXT,
    metadata JSONB,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_source_document_checksum_sha256 CHECK (
        checksum_sha256 IS NULL OR checksum_sha256 ~ '^[0-9a-f]{64}$'
    )
);

-- =====================================================
-- TABLE: club
-- =====================================================

CREATE TABLE club (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    short_name TEXT,
    city TEXT,
    region TEXT,
    association_name TEXT,
    website TEXT,
    instagram TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    source_id BIGINT REFERENCES source(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- TABLE: pool
-- =====================================================

CREATE TABLE pool (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT,
    region TEXT,
    address TEXT,
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    pool_length_m INTEGER CHECK (pool_length_m > 0),
    lanes_count INTEGER CHECK (lanes_count > 0),
    indoor_outdoor TEXT CHECK (indoor_outdoor IN ('indoor', 'outdoor', 'mixed', 'unknown')),
    heated BOOLEAN,
    public_access_type TEXT CHECK (public_access_type IN ('public', 'municipal', 'club', 'private', 'school', 'university', 'unknown')),
    website TEXT,
    contact_info TEXT,
    notes TEXT,
    source_id BIGINT REFERENCES source(id),
    last_verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_pool_latitude CHECK (latitude IS NULL OR (latitude BETWEEN -90 AND 90)),
    CONSTRAINT chk_pool_longitude CHECK (longitude IS NULL OR (longitude BETWEEN -180 AND 180))
);

-- =====================================================
-- TABLE: competition
-- =====================================================

CREATE TABLE competition (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    season_year INTEGER CHECK (season_year IS NULL OR season_year >= 1900),
    start_date DATE,
    end_date DATE,
    city TEXT,
    region TEXT,
    venue_name TEXT,
    pool_id BIGINT REFERENCES pool(id),
    organizer TEXT,
    governing_body_code TEXT CHECK (
        governing_body_code IS NULL OR governing_body_code ~ '^[a-z][a-z0-9_]*$'
    ),
    governing_body_name TEXT,
    competition_type TEXT CHECK (
        competition_type IN ('national', 'regional', 'master', 'open', 'school', 'other')
    ),
    competition_scope TEXT CHECK (
        competition_scope IS NULL OR competition_scope ~ '^[a-z][a-z0-9_]*$'
    ),
    course_type TEXT CHECK (
        course_type IN ('scm', 'lcm', 'unknown')
    ),
    status TEXT CHECK (
        status IN ('planned', 'finished', 'cancelled', 'postponed')
    ),
    source_id BIGINT REFERENCES source(id),
    source_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_competition_date_range CHECK (
        start_date IS NULL
        OR end_date IS NULL
        OR end_date >= start_date
    )
);

-- =====================================================
-- TABLE: load_run
-- =====================================================

CREATE TABLE load_run (
    id BIGSERIAL PRIMARY KEY,
    source_document_id BIGINT REFERENCES source_document(id),
    competition_id BIGINT REFERENCES competition(id),
    input_dir TEXT,
    parser_version TEXT,
    status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
    rows_club INTEGER NOT NULL DEFAULT 0 CHECK (rows_club >= 0),
    rows_event INTEGER NOT NULL DEFAULT 0 CHECK (rows_event >= 0),
    rows_athlete INTEGER NOT NULL DEFAULT 0 CHECK (rows_athlete >= 0),
    rows_result INTEGER NOT NULL DEFAULT 0 CHECK (rows_result >= 0),
    rows_relay_result INTEGER NOT NULL DEFAULT 0 CHECK (rows_relay_result >= 0),
    rows_relay_result_member INTEGER NOT NULL DEFAULT 0 CHECK (rows_relay_result_member >= 0),
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- =====================================================
-- TABLE: validation_issue
-- =====================================================

CREATE TABLE validation_issue (
    id BIGSERIAL PRIMARY KEY,
    load_run_id BIGINT REFERENCES load_run(id),
    competition_id BIGINT REFERENCES competition(id),
    issue_key TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'warning' CHECK (severity IN ('info', 'warning', 'error')),
    issue_count INTEGER NOT NULL CHECK (issue_count >= 0),
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- TABLE: event
-- =====================================================

CREATE TABLE event (
    id BIGSERIAL PRIMARY KEY,
    competition_id BIGINT NOT NULL REFERENCES competition(id),
    event_name TEXT NOT NULL,
    stroke TEXT CHECK (
        stroke IN (
            'freestyle',
            'backstroke',
            'breaststroke',
            'butterfly',
            'individual_medley',
            'medley_relay',
            'freestyle_relay'
        )
    ),
    distance_m INTEGER CHECK (distance_m IS NULL OR distance_m > 0),
    gender TEXT CHECK (
        gender IN ('women', 'men', 'mixed')
    ),
    age_group TEXT,
    round_type TEXT CHECK (
        round_type IN ('heats', 'final', 'timed_final', 'semifinal', 'unknown')
    ),
    event_order INTEGER CHECK (event_order IS NULL OR event_order > 0),
    scheduled_date DATE,
    source_id BIGINT REFERENCES source(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- TABLE: athlete
-- =====================================================

CREATE TABLE athlete (
    id BIGSERIAL PRIMARY KEY,
    full_name TEXT NOT NULL,
    gender TEXT CHECK (
        gender IN ('male', 'female')
    ),
    birth_year INTEGER CHECK (
        birth_year IS NULL OR birth_year >= 1900
    ),
    nationality TEXT,
    club_id BIGINT REFERENCES club(id),
    source_id BIGINT REFERENCES source(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- TABLE: result
-- =====================================================

CREATE TABLE result (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES event(id),
    athlete_id BIGINT NOT NULL REFERENCES athlete(id),
    club_id BIGINT REFERENCES club(id),
    lane INTEGER CHECK (lane IS NULL OR lane > 0),
    heat_number INTEGER CHECK (heat_number IS NULL OR heat_number > 0),
    rank_position INTEGER CHECK (rank_position IS NULL OR rank_position > 0),
    result_time_text TEXT,
    result_time_ms BIGINT CHECK (result_time_ms IS NULL OR result_time_ms >= 0),
    seed_time_text TEXT,
    seed_time_ms BIGINT CHECK (seed_time_ms IS NULL OR seed_time_ms >= 0),
    points NUMERIC(10,2),
    expected_points NUMERIC(10,2),
    age_at_event INTEGER CHECK (age_at_event IS NULL OR age_at_event > 0),
    birth_year_estimated INTEGER CHECK (birth_year_estimated IS NULL OR birth_year_estimated >= 1900),
    record_flag TEXT,
    status TEXT CHECK (
        status IN ('valid', 'dns', 'dnf', 'dsq', 'scratch', 'unknown')
    ),
    source_id BIGINT REFERENCES source(id),
    source_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- TABLE: relay_result
-- =====================================================

CREATE TABLE relay_result (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES event(id),
    club_id BIGINT REFERENCES club(id),
    relay_team_name TEXT NOT NULL,
    lane INTEGER CHECK (lane IS NULL OR lane > 0),
    heat_number INTEGER CHECK (heat_number IS NULL OR heat_number > 0),
    rank_position INTEGER CHECK (rank_position IS NULL OR rank_position > 0),
    result_time_text TEXT,
    result_time_ms BIGINT CHECK (result_time_ms IS NULL OR result_time_ms >= 0),
    seed_time_text TEXT,
    seed_time_ms BIGINT CHECK (seed_time_ms IS NULL OR seed_time_ms >= 0),
    points NUMERIC(10,2),
    expected_points NUMERIC(10,2),
    reaction_time NUMERIC(6,3) CHECK (reaction_time IS NULL OR reaction_time >= 0),
    record_flag TEXT,
    status TEXT CHECK (
        status IN ('valid', 'dns', 'dnf', 'dsq', 'scratch', 'unknown')
    ),
    source_id BIGINT REFERENCES source(id),
    source_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- TABLE: relay_result_member
-- =====================================================

CREATE TABLE relay_result_member (
    id BIGSERIAL PRIMARY KEY,
    relay_result_id BIGINT NOT NULL REFERENCES relay_result(id),
    athlete_id BIGINT REFERENCES athlete(id),
    leg_order INTEGER NOT NULL CHECK (leg_order BETWEEN 1 AND 4),
    athlete_name_raw TEXT,
    gender TEXT CHECK (gender IN ('male', 'female')),
    age_at_event INTEGER CHECK (age_at_event IS NULL OR age_at_event > 0),
    birth_year_estimated INTEGER CHECK (birth_year_estimated IS NULL OR birth_year_estimated >= 1900),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (relay_result_id, leg_order)
);

-- =====================================================
-- TABLE: record
-- =====================================================

CREATE TABLE record (
    id BIGSERIAL PRIMARY KEY,
    record_type TEXT NOT NULL,
    stroke TEXT CHECK (
        stroke IN (
            'freestyle',
            'backstroke',
            'breaststroke',
            'butterfly',
            'individual_medley',
            'medley_relay',
            'freestyle_relay'
        )
    ),
    distance_m INTEGER NOT NULL CHECK (distance_m > 0),
    gender TEXT NOT NULL CHECK (
        gender IN ('male', 'female', 'mixed', 'unknown')
    ),
    age_group TEXT,
    course_type TEXT NOT NULL CHECK (
        course_type IN ('scm', 'lcm', 'unknown')
    ),
    result_time_text TEXT NOT NULL,
    result_time_ms BIGINT CHECK (result_time_ms IS NULL OR result_time_ms >= 0),
    athlete_name TEXT,
    club_name TEXT,
    record_date DATE,
    competition_name TEXT,
    city TEXT,
    source_id BIGINT REFERENCES source(id),
    source_url TEXT,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- STAGING TABLES
-- =====================================================

CREATE TABLE stg_club (
    name TEXT,
    short_name TEXT,
    city TEXT,
    region TEXT,
    source_id TEXT
);

CREATE TABLE stg_event (
    competition_id TEXT,
    event_name TEXT,
    stroke TEXT,
    distance_m TEXT,
    gender TEXT,
    age_group TEXT,
    round_type TEXT,
    source_id TEXT
);

CREATE TABLE stg_athlete (
    full_name TEXT,
    gender TEXT,
    club_name TEXT,
    birth_year TEXT,
    source_id TEXT
);

CREATE TABLE stg_result (
    event_name TEXT,
    athlete_name TEXT,
    club_name TEXT,
    rank_position TEXT,
    result_time_text TEXT,
    result_time_ms TEXT,
    age_at_event TEXT,
    birth_year_estimated TEXT,
    points TEXT,
    seed_time_text TEXT,
    seed_time_ms TEXT,
    status TEXT,
    source_id TEXT
);

CREATE TABLE stg_relay_result (
    event_name TEXT,
    club_name TEXT,
    relay_team_name TEXT,
    lane TEXT,
    heat_number TEXT,
    rank_position TEXT,
    result_time_text TEXT,
    result_time_ms TEXT,
    points TEXT,
    reaction_time TEXT,
    record_flag TEXT,
    status TEXT,
    source_id TEXT,
    source_url TEXT,
    seed_time_text TEXT,
    seed_time_ms TEXT
);

CREATE TABLE stg_relay_result_member (
    event_name TEXT,
    club_name TEXT,
    relay_team_name TEXT,
    relay_rank_position TEXT,
    relay_result_time_ms TEXT,
    leg_order TEXT,
    athlete_name TEXT,
    gender TEXT,
    age_at_event TEXT,
    birth_year_estimated TEXT
);

-- =====================================================
-- INDICES
-- =====================================================

CREATE INDEX idx_club_source_id ON club(source_id);
CREATE INDEX idx_source_document_source_id ON source_document(source_id);
CREATE INDEX idx_source_document_checksum_sha256 ON source_document(checksum_sha256);
CREATE UNIQUE INDEX ux_source_document_checksum_sha256
    ON source_document(checksum_sha256)
    WHERE checksum_sha256 IS NOT NULL;
CREATE UNIQUE INDEX ux_source_document_source_url
    ON source_document(source_url)
    WHERE source_url IS NOT NULL;
CREATE INDEX idx_load_run_source_document_id ON load_run(source_document_id);
CREATE INDEX idx_load_run_competition_id ON load_run(competition_id);
CREATE INDEX idx_load_run_status ON load_run(status);
CREATE INDEX idx_validation_issue_load_run_id ON validation_issue(load_run_id);
CREATE INDEX idx_validation_issue_competition_id ON validation_issue(competition_id);
CREATE INDEX idx_validation_issue_issue_key ON validation_issue(issue_key);
CREATE INDEX idx_pool_source_id ON pool(source_id);
CREATE INDEX idx_pool_region_city ON pool(region, city);

CREATE INDEX idx_competition_pool_id ON competition(pool_id);
CREATE INDEX idx_competition_source_id ON competition(source_id);
CREATE INDEX idx_competition_scope ON competition(competition_scope);
CREATE INDEX idx_competition_start_date ON competition(start_date);
CREATE INDEX idx_competition_season_year ON competition(season_year);

CREATE INDEX idx_event_competition_id ON event(competition_id);
CREATE INDEX idx_event_source_id ON event(source_id);
CREATE INDEX idx_event_scheduled_date ON event(scheduled_date);
CREATE UNIQUE INDEX ux_event_competition_event_name ON event(
    competition_id,
    LOWER(TRIM(event_name))
);

CREATE INDEX idx_athlete_club_id ON athlete(club_id);
CREATE INDEX idx_athlete_source_id ON athlete(source_id);
CREATE INDEX idx_athlete_full_name ON athlete(full_name);

CREATE INDEX idx_result_event_id ON result(event_id);
CREATE INDEX idx_result_athlete_id ON result(athlete_id);
CREATE INDEX idx_result_club_id ON result(club_id);
CREATE INDEX idx_result_source_id ON result(source_id);
CREATE INDEX idx_result_rank_position ON result(rank_position);
CREATE INDEX idx_result_status ON result(status);
CREATE UNIQUE INDEX ux_result_observed_identity ON result(
    event_id,
    athlete_id,
    COALESCE(club_id, -1),
    COALESCE(rank_position, -1),
    COALESCE(result_time_ms, -1),
    COALESCE(status, '')
);

CREATE INDEX idx_relay_result_event_id ON relay_result(event_id);
CREATE INDEX idx_relay_result_club_id ON relay_result(club_id);
CREATE INDEX idx_relay_result_source_id ON relay_result(source_id);
CREATE INDEX idx_relay_result_rank_position ON relay_result(rank_position);
CREATE INDEX idx_relay_result_status ON relay_result(status);
CREATE UNIQUE INDEX ux_relay_result_observed_identity ON relay_result(
    event_id,
    COALESCE(club_id, -1),
    LOWER(TRIM(relay_team_name)),
    COALESCE(rank_position, -1),
    COALESCE(result_time_ms, -1),
    COALESCE(status, '')
);

CREATE INDEX idx_relay_result_member_relay_result_id ON relay_result_member(relay_result_id);
CREATE INDEX idx_relay_result_member_athlete_id ON relay_result_member(athlete_id);

CREATE INDEX idx_record_source_id ON record(source_id);
CREATE INDEX idx_record_is_current ON record(is_current);

-- =====================================================
-- VIEW: athlete_current_club
-- =====================================================

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
CREATE INDEX idx_record_gender_course_type ON record(gender, course_type);
CREATE INDEX idx_record_distance_stroke ON record(distance_m, stroke);
