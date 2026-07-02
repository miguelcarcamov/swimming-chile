-- =====================================================
-- Migration 008 - User profile interactions
-- Adds authenticated-user interactions without leaking private identity data
-- into core.athlete, which remains the public sports identity.
-- =====================================================

CREATE SCHEMA IF NOT EXISTS auth;

-- Supabase Auth is the initial provider. Keep password_hash for the future
-- hybrid path, but persist the external subject now so email changes do not
-- break the local account mapping.
ALTER TABLE auth.user_account
    ADD COLUMN IF NOT EXISTS external_provider TEXT,
    ADD COLUMN IF NOT EXISTS external_subject TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS ux_user_account_external_identity
    ON auth.user_account(external_provider, external_subject)
    WHERE external_provider IS NOT NULL AND external_subject IS NOT NULL;

-- =====================================================
-- TABLE: auth.user_athlete_favorite
-- Private list of athlete profiles followed by an authenticated user.
-- =====================================================

CREATE TABLE IF NOT EXISTS auth.user_athlete_favorite (
    user_id BIGINT NOT NULL REFERENCES auth.user_account(id) ON DELETE CASCADE,
    athlete_id BIGINT NOT NULL REFERENCES core.athlete(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, athlete_id)
);

CREATE INDEX IF NOT EXISTS idx_user_athlete_favorite_athlete_id
    ON auth.user_athlete_favorite(athlete_id);

-- =====================================================
-- TABLE: auth.user_club_favorite
-- Private list of clubs followed by an authenticated user.
-- =====================================================

CREATE TABLE IF NOT EXISTS auth.user_club_favorite (
    user_id BIGINT NOT NULL REFERENCES auth.user_account(id) ON DELETE CASCADE,
    club_id BIGINT NOT NULL REFERENCES core.club(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, club_id)
);

CREATE INDEX IF NOT EXISTS idx_user_club_favorite_club_id
    ON auth.user_club_favorite(club_id);

-- =====================================================
-- TABLE: auth.athlete_claim_request
-- Manual review queue for linking a civil person/account to a sports profile.
-- Pending requests deliberately do NOT create core.athlete_person_link rows.
-- =====================================================

CREATE TABLE IF NOT EXISTS auth.athlete_claim_request (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES auth.user_account(id) ON DELETE CASCADE,
    athlete_id BIGINT NOT NULL REFERENCES core.athlete(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    evidence_message TEXT NOT NULL,
    declared_club_name TEXT,
    contact_hint TEXT,
    reviewed_by_user_id BIGINT REFERENCES auth.user_account(id),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_athlete_claim_status CHECK (
        status IN ('pending', 'approved', 'rejected')
    ),
    CONSTRAINT chk_athlete_claim_evidence_not_blank CHECK (
        LENGTH(TRIM(evidence_message)) > 0
    ),
    CONSTRAINT chk_athlete_claim_review_state CHECK (
        (status = 'pending' AND reviewed_at IS NULL)
        OR (status <> 'pending' AND reviewed_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_athlete_claim_request_user_id
    ON auth.athlete_claim_request(user_id);

CREATE INDEX IF NOT EXISTS idx_athlete_claim_request_athlete_id
    ON auth.athlete_claim_request(athlete_id);

CREATE INDEX IF NOT EXISTS idx_athlete_claim_request_status
    ON auth.athlete_claim_request(status);

CREATE UNIQUE INDEX IF NOT EXISTS ux_athlete_claim_request_pending_user_athlete
    ON auth.athlete_claim_request(user_id, athlete_id)
    WHERE status = 'pending';

-- =====================================================
-- TABLE: auth.profile_contribution
-- User-suggested corrections/completions. These are reviewable suggestions,
-- not direct writes to public sports data.
-- =====================================================

CREATE TABLE IF NOT EXISTS auth.profile_contribution (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES auth.user_account(id) ON DELETE CASCADE,
    athlete_id BIGINT REFERENCES core.athlete(id) ON DELETE CASCADE,
    club_id BIGINT REFERENCES core.club(id) ON DELETE CASCADE,
    contribution_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reviewed_by_user_id BIGINT REFERENCES auth.user_account(id),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_profile_contribution_status CHECK (
        status IN ('pending', 'accepted', 'rejected')
    ),
    CONSTRAINT chk_profile_contribution_type CHECK (
        contribution_type IN ('athlete_profile', 'club_profile', 'result_correction', 'other')
    ),
    CONSTRAINT chk_profile_contribution_single_target CHECK (
        (athlete_id IS NOT NULL AND club_id IS NULL)
        OR (athlete_id IS NULL AND club_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_profile_contribution_user_id
    ON auth.profile_contribution(user_id);

CREATE INDEX IF NOT EXISTS idx_profile_contribution_athlete_id
    ON auth.profile_contribution(athlete_id);

CREATE INDEX IF NOT EXISTS idx_profile_contribution_club_id
    ON auth.profile_contribution(club_id);

CREATE INDEX IF NOT EXISTS idx_profile_contribution_status
    ON auth.profile_contribution(status);
