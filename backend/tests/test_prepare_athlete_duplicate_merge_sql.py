import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import prepare_athlete_duplicate_merge_sql as prepare


def test_load_duplicate_merges_keeps_only_merge_decisions(tmp_path):
    review = tmp_path / "duplicate_merges.csv"
    review.write_text(
        "decision;canonical_athlete_id;duplicate_athlete_id;proposed_canonical_full_name;"
        "current_canonical_full_name;current_duplicate_full_name;gender;birth_year;reason\n"
        "merge;2603;474;Riquelme Figueroa, Gipsy Andrea;"
        "Riquelme Figueroa, Gipsy Andrea;Riquelme, Andrea;female;1990;reviewed\n"
        "review;1404;678;Gimeno, Vicente Pablo;Gimeno, Vicente;Gimeno, Pablo;male;1980;pending\n",
        encoding="utf-8-sig",
    )

    merges = prepare.load_duplicate_merges(review)

    assert merges == [
        prepare.DuplicateAthleteMerge(
            canonical_athlete_id=2603,
            duplicate_athlete_id=474,
            proposed_canonical_full_name="Riquelme Figueroa, Gipsy Andrea",
            current_canonical_full_name="Riquelme Figueroa, Gipsy Andrea",
            current_duplicate_full_name="Riquelme, Andrea",
            gender="female",
            birth_year=1990,
        )
    ]


def test_render_sql_rewires_all_athlete_references_and_guards_expected_identity():
    sql = prepare.render_sql(
        [
            prepare.DuplicateAthleteMerge(
                canonical_athlete_id=2603,
                duplicate_athlete_id=474,
                proposed_canonical_full_name="Riquelme Figueroa, Gipsy Andrea",
                current_canonical_full_name="Riquelme Figueroa, Gipsy Andrea",
                current_duplicate_full_name="Riquelme, Andrea",
                gender="female",
                birth_year=1990,
            )
        ]
    )

    assert "BEGIN;" in sql
    assert "reviewed_duplicate_athlete_merge" in sql
    assert "core.result" in sql
    assert "core.relay_result_member" in sql
    assert "core.athlete_person_link" in sql
    assert "ON CONFLICT (athlete_id, person_id) DO NOTHING" in sql
    assert "src.full_name IS DISTINCT FROM m.source_expected_name" in sql
    assert "tgt.full_name IS DISTINCT FROM m.target_expected_name" in sql
    assert "src.gender IS DISTINCT FROM m.expected_gender" in sql
    assert "src.birth_year IS DISTINCT FROM m.canonical_birth_year" in sql
    assert "DELETE FROM core.athlete src" in sql
    assert "COMMIT;" in sql
