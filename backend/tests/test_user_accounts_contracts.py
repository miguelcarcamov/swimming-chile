from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
AUTH_MODULE = BACKEND_DIR / "api" / "auth.py"
ACCOUNT_ROUTER = BACKEND_DIR / "api" / "routers" / "account.py"
MAIN_API = BACKEND_DIR / "api" / "main.py"
USER_INTERACTIONS_MIGRATION = BACKEND_DIR / "sql" / "migrations" / "008_user_profile_interactions.sql"


def normalized_source(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_user_interactions_migration_declares_private_account_tables():
    sql = normalized_source(USER_INTERACTIONS_MIGRATION)

    for fragment in [
        "alter table auth.user_account",
        "add column if not exists external_provider text",
        "add column if not exists external_subject text",
        "create table if not exists auth.user_athlete_favorite",
        "create table if not exists auth.user_club_favorite",
        "create table if not exists auth.athlete_claim_request",
        "create table if not exists auth.profile_contribution",
    ]:
        assert fragment in sql


def test_user_interactions_migration_keeps_favorites_private_and_unique():
    sql = normalized_source(USER_INTERACTIONS_MIGRATION)

    assert "primary key (user_id, athlete_id)" in sql
    assert "primary key (user_id, club_id)" in sql
    assert "references auth.user_account(id) on delete cascade" in sql
    assert "references core.athlete(id) on delete cascade" in sql
    assert "references core.club(id) on delete cascade" in sql


def test_claim_requests_are_manual_until_reviewed():
    sql = normalized_source(USER_INTERACTIONS_MIGRATION)
    router = normalized_source(ACCOUNT_ROUTER)

    assert "status text not null default 'pending'" in sql
    assert "ux_athlete_claim_request_pending_user_athlete" in sql
    assert "pending requests deliberately do not create core.athlete_person_link rows" in sql
    assert "def create_athlete_claim" in router
    create_section = router.split("def create_athlete_claim", 1)[1].split("def review_athlete_claim", 1)[0]
    assert "core.athlete_person_link" not in create_section
    assert "insert into core.athlete_person_link" in router


def test_auth_router_is_protected_by_supabase_jwt_dependency():
    auth_source = normalized_source(AUTH_MODULE)
    router_source = normalized_source(ACCOUNT_ROUTER)
    main_source = normalized_source(MAIN_API)

    assert "def verify_supabase_token" in auth_source
    assert "supabase_jwks_url" in auth_source
    assert "supabase_jwt_secret" in auth_source
    assert "invalid authentication token" in auth_source
    assert "status.http_401_unauthorized" in auth_source
    assert "depends(get_current_user)" in router_source
    assert 'prefix="/api/me"' in main_source


def test_me_sync_creates_local_account_linked_to_identity_person():
    router = normalized_source(ACCOUNT_ROUTER)

    assert "insert into identity.person" in router
    assert "insert into auth.user_account" in router
    assert "external_provider, external_subject" in router
    assert "insert into identity.contact_point" in router
    assert "person_id" in router


def test_profile_contributions_are_reviewable_suggestions():
    sql = normalized_source(USER_INTERACTIONS_MIGRATION)
    router = normalized_source(ACCOUNT_ROUTER)

    assert "create table if not exists auth.profile_contribution" in sql
    assert "payload jsonb not null" in sql
    assert "status text not null default 'pending'" in sql
    assert "chk_profile_contribution_single_target" in sql
    assert "def create_contribution" in router
