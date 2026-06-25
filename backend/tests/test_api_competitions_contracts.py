from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
COMPETITIONS_ROUTER = BACKEND_DIR / "api" / "routers" / "competitions.py"
GOVERNING_BODY_MIGRATION = BACKEND_DIR / "sql" / "migrations" / "005_competition_governing_body.sql"


def normalized_source(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_competitions_api_filters_by_scope_and_governing_body():
    source = normalized_source(COMPETITIONS_ROUTER)

    assert "competition_scope: optional[str]" in source
    assert "governing_body: optional[str]" in source
    assert "and competition_scope = %s" in source
    assert "and governing_body_code = %s" in source
    assert "governing_body_scope_fallbacks" not in source
    assert "governing_body_code is null and competition_scope" not in source
    assert "competition_scope," in source
    assert "governing_body_code" in source
    assert "governing_body_name" in source
    assert "organizer" in source
    assert "coalesce(c.source_url, latest_doc.source_url) as source_url" in source
    assert "join core.source_document sd on sd.id = lr.source_document_id" in source


def test_competitions_api_exposes_filter_options_from_database():
    source = normalized_source(COMPETITIONS_ROUTER)

    assert '@router.get("/filter-options")' in COMPETITIONS_ROUTER.read_text(encoding="utf-8")
    assert "timeframe: optional[str]" in source
    assert "start_date >= current_date" in source
    assert "start_date < current_date" in source
    assert "select distinct competition_scope" in source
    assert "select distinct governing_body_code, governing_body_name" in source
    assert "when 'sudamericano_master'" not in source
    assert '"governing_bodies": governing_bodies' in source


def test_governing_body_migration_keeps_source_scope_and_organizer_separate():
    source = normalized_source(GOVERNING_BODY_MIGRATION)

    assert "add column if not exists governing_body_code text" in source
    assert "add column if not exists governing_body_name text" in source
    assert "chk_competition_governing_body_code" in source
    assert "idx_competition_governing_body_code" in source
    assert "where competition_scope = 'fchmn_local'" in source
