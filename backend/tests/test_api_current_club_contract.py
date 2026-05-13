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


def test_clubs_api_counts_current_athletes_from_current_club_view():
    source = normalized_source(CLUBS_ROUTER)

    assert "core.athlete_current_club acc" in source
    assert "where acc.club_id = c.id" in source
    assert "from core.athlete a where a.club_id = c.id" not in source
