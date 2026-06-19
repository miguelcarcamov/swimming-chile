import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import prepare_athlete_canonical_updates as prepare


def test_load_updates_keeps_only_real_canonical_name_changes(tmp_path):
    review = tmp_path / "review.csv"
    review.write_text(
        "target_athlete_id;current_core_names;proposed_canonical_full_name\n"
        '10;"Sayago, Alexis";"Sayago Moreno, Alexis Saul"\n'
        '11;"Torres, Sergio";"Torres, Sergio"\n',
        encoding="utf-8",
    )

    updates = prepare.load_canonical_updates(review)

    assert updates == [
        prepare.CanonicalNameUpdate(
            athlete_id=10,
            expected_names=("Sayago, Alexis",),
            canonical_full_name="Sayago Moreno, Alexis Saul",
        )
    ]


def test_load_updates_preserves_all_reviewed_current_names_for_guard(tmp_path):
    review = tmp_path / "review.csv"
    review.write_text(
        "target_athlete_id;current_core_names;proposed_canonical_full_name\n"
        '54;"Carrasco, Barbara | Venegas, Barbara Carolina";"Venegas, Barbara Carolina"\n',
        encoding="utf-8",
    )

    [update] = prepare.load_canonical_updates(review)

    assert update.expected_names == ("Carrasco, Barbara", "Venegas, Barbara Carolina")


def test_render_sql_is_guarded_idempotent_and_does_not_assume_updated_at():
    sql = prepare.render_sql(
        [
            prepare.CanonicalNameUpdate(
                athlete_id=10,
                expected_names=("Sayago, Alexis",),
                canonical_full_name="Sayago Moreno, Alexis Saul",
            )
        ]
    )

    assert "BEGIN;" in sql
    assert "missing_or_mismatched" in sql
    assert "canonical_name_collision" in sql
    assert "UPDATE core.athlete" in sql
    assert "updated_at" not in sql
    assert "COMMIT;" in sql
