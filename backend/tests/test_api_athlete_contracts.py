from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
ATHLETES_ROUTER = BACKEND_DIR / "api" / "routers" / "athletes.py"
CLUBS_ROUTER = BACKEND_DIR / "api" / "routers" / "clubs.py"


def normalized_source(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_athletes_api_uses_current_club_view_not_static_athlete_club():
    source = normalized_source(ATHLETES_ROUTER)

    assert "core.athlete_current_club acc" in source
    assert "acc.club_id = %s" in source
    assert "current_club_name" in source
    assert "left join core.club c on a.club_id = c.id" not in source


def test_athletes_api_uses_shared_token_search():
    source = normalized_source(ATHLETES_ROUTER)

    assert "search_tokens" in source
    assert "build_token_search_clause" in source


def test_athlete_search_text_normalization_removes_accents_for_search():
    import sys

    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from api.routers.athletes import normalize_search_text

    assert normalize_search_text("Daniel Briceño") == "daniel briceno"


def test_partial_non_contiguous_athlete_name_builds_all_token_conditions():
    import sys

    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from api.search import build_token_search_clause, search_tokens

    tokens = search_tokens("Alexis Sayago")
    clause, params = build_token_search_clause(["a.full_name"], tokens)

    assert tokens == ["alexis", "sayago"]
    assert clause.count("LIKE %s") == 2
    assert " AND " in clause
    assert params == ["%alexis%", "%sayago%"]


def test_clubs_api_counts_current_athletes_from_current_club_view():
    source = normalized_source(CLUBS_ROUTER)

    assert "core.athlete_current_club acc" in source
    assert "where acc.club_id = c.id" in source
    assert "c.city" in source
    assert "c.short_name as city" not in source
    assert "from core.athlete a where a.club_id = c.id" not in source


def test_clubs_api_uses_shared_token_search():
    source = normalized_source(CLUBS_ROUTER)

    assert "search_tokens" in source
    assert "build_token_search_clause" in source


def test_club_search_requires_every_token_across_name_fields():
    import sys

    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from api.search import build_token_search_clause, search_tokens

    tokens = search_tokens("Natacion San Bernardo")
    clause, params = build_token_search_clause(
        ["c.name", "COALESCE(c.city, '')", "COALESCE(c.region, '')"], tokens
    )

    assert clause.count("LIKE %s") == 9
    assert clause.count(" AND ") == 2
    assert params == [
        "%natacion%", "%natacion%", "%natacion%",
        "%san%", "%san%", "%san%",
        "%bernardo%", "%bernardo%", "%bernardo%",
    ]
