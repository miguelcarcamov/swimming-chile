import argparse
import sys
from pathlib import Path

import pandas as pd
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_pipeline_results as pipeline


def test_count_input_rows_for_load_run():
    data = {
        "club": pd.DataFrame([{"name": "Club A"}, {"name": "Club B"}]),
        "event": pd.DataFrame([{"event_name": "Event A"}]),
        "athlete": pd.DataFrame(),
        "result": pd.DataFrame([{"athlete_name": "Uno"}]),
        "relay_result": pd.DataFrame([{"relay_team_name": "Club A"}]),
        "relay_result_member": pd.DataFrame([{"athlete_name": "Dos"}, {"athlete_name": "Tres"}]),
    }

    assert pipeline.count_input_rows(data) == {
        "club": 2,
        "event": 1,
        "athlete": 0,
        "result": 1,
        "relay_result": 1,
        "relay_result_member": 2,
    }


def test_derive_source_document_name_prefers_pdf_metadata():
    args = argparse.Namespace(excel="manual.xlsx", input_dir="backend/data/raw/results_csv/demo")
    metadata = {"pdf_name": "resultados-demo.pdf", "competition_name": "Demo"}

    assert pipeline.derive_source_document_name(args, metadata) == "resultados-demo.pdf"


def test_derive_source_document_name_falls_back_to_input_dir():
    args = argparse.Namespace(excel=None, input_dir="backend/data/raw/results_csv/demo")

    assert pipeline.derive_source_document_name(args, {}) == "demo"


def test_normalize_competition_scope_accepts_snake_case():
    assert pipeline.normalize_competition_scope("fchmn_local") == "fchmn_local"


def test_normalize_competition_scope_rejects_free_text():
    with pytest.raises(SystemExit):
        pipeline.normalize_competition_scope("FCHMN Local")


def test_normalize_dataframe_derives_valid_status_from_result_time():
    df = pd.DataFrame(
        [
            {
                "event_name": "Event A",
                "athlete_name": "Nadador Uno",
                "club_name": "Club A",
                "rank_position": "1",
                "seed_time_text": None,
                "seed_time_ms": None,
                "result_time_text": "1:05.30",
                "result_time_ms": None,
                "age_at_event": "35",
                "birth_year_estimated": "1991",
                "points": None,
                "status": None,
                "source_id": "1",
            }
        ]
    )

    normalized = pipeline.normalize_dataframe(df, pipeline.EXPECTED_COLUMNS["result"], "result")

    assert normalized.loc[0, "result_time_text"] == "1:05,30"
    assert normalized.loc[0, "result_time_ms"] == "65300"
    assert normalized.loc[0, "status"] == "valid"


def test_normalize_dataframe_preserves_exhibition_times_as_valid_without_rank():
    df = pd.DataFrame(
        [
            {
                "event_name": "women 24 & Under 200 SC Meter freestyle",
                "athlete_name": "Nadadora Uno",
                "club_name": "Club A",
                "rank_position": "1",
                "seed_time_text": None,
                "seed_time_ms": None,
                "result_time_text": "X2:34,41",
                "result_time_ms": "154410",
                "age_at_event": "21",
                "birth_year_estimated": "2005",
                "points": None,
                "status": "valid",
                "source_id": "1",
            }
        ]
    )

    normalized = pipeline.normalize_dataframe(df, pipeline.EXPECTED_COLUMNS["result"], "result")

    assert normalized.loc[0, "rank_position"] is None
    assert normalized.loc[0, "result_time_text"] == "X2:34,41"
    assert normalized.loc[0, "result_time_ms"] == "154410"
    assert normalized.loc[0, "status"] == "valid"


def test_default_club_alias_csv_contains_audited_fchmn_mappings():
    aliases = pipeline.load_club_aliases(str(pipeline.DEFAULT_CLUB_ALIAS_CSV))

    assert pipeline.resolve_club_alias("Orinoco Swim 23", aliases) == "Orinoco Swim"
    assert pipeline.resolve_club_alias("Estadio Español Master-ZZ", aliases) == "Estadio Español"
    assert pipeline.resolve_club_alias("Manateam Swim-AN", aliases) == "Manateam Swim"
    assert pipeline.resolve_club_alias("Natacion Neurodivergentes", aliases) == "Natacion Neurodivergente"
    assert pipeline.resolve_club_alias("Club Ñuñoa Master", aliases) == "Ñuñoa Master"
    assert pipeline.resolve_club_alias("ÑUÑOA", aliases) == "Ñuñoa Master"
    assert pipeline.resolve_club_alias("Venimos por la Natacioén", aliases) == "Venimos por la Natacion"
    assert pipeline.resolve_club_alias("Master San Bernanrdo", aliases) == "Master San Bernardo"
    assert pipeline.resolve_club_alias("Toninas Swm Team", aliases) == "Toninas Swim Team"
    assert pipeline.resolve_club_alias("Camayo Copiapo", aliases) == "Camaygo Copiapo"
    assert pipeline.resolve_club_alias("Condictrios Team", aliases) == "Condrictios Team"
    assert pipeline.resolve_club_alias("Salmon Swim", aliases) == "Salmón Swim"
    assert pipeline.resolve_club_alias("Squadra Proswim", aliases) == "Squadra Pro Swim"
    assert pipeline.resolve_club_alias("Santiago Deportes", aliases) == "Santiago Deporte"
    assert pipeline.resolve_club_alias("GOURA", aliases) == "Goura Swim Team"
    assert pipeline.resolve_club_alias("Club de Natacion Mako´s", aliases) == "Club de Natacion Makos"
    assert pipeline.resolve_club_alias("Club Natacion Makos", aliases) == "Club de Natacion Makos"
    assert pipeline.resolve_club_alias("Vitacura Deportes", aliases) == "Master Vitacura"
    assert pipeline.resolve_club_alias("Club Elite Sport", aliases) == "Elite Sports"
    assert pipeline.resolve_club_alias("Club Estadio Español", aliases) == "Estadio Español"
    assert pipeline.resolve_club_alias("Club Golden Swim", aliases) == "Golden"
    assert pipeline.resolve_club_alias("Club Lozada Swim", aliases) == "Lozada Swim Team"
    assert pipeline.resolve_club_alias("Club Dpto Universidad Catolica", aliases) == "Club Deportivo UC"
    assert pipeline.resolve_club_alias("CDUC", aliases) == "Club Deportivo UC"
    assert pipeline.resolve_club_alias("Club Dpto Univ San Sebastian", aliases) == "Club Deportivo Universidad San Sebastian"
    assert pipeline.resolve_club_alias("Club Dep Master Magallanes", aliases) == "Master Magallanes"
    assert pipeline.resolve_club_alias("LAGOS", aliases) == "Natacion Los Lagos"
    assert pipeline.resolve_club_alias("Club Manquehue", aliases) == "Master Manquehue"
    assert pipeline.resolve_club_alias("SMART", aliases) == "Smart Swim Team"
    assert pipeline.resolve_club_alias("Club DE Natacion Buin", aliases) == "Natacion Master Buin"


def test_transform_parser_relay_outputs_prefers_relay_team_club_name_with_empty_club_csv():
    relay_team_df = pd.DataFrame(
        [
            {
                "event_name": "Mixed 200 SC Meter Medley Relay",
                "club_name": "Associacao Master",
                "relay_team_name": "Equipe A",
                "rank_position": "1",
                "seed_time_text": None,
                "seed_time_ms": None,
                "result_time_text": "2:05.10",
                "result_time_ms": "125100",
                "points": "18",
                "status": "valid",
                "source_id": "1",
                "page_number": "3",
                "line_number": "42",
            }
        ]
    )
    relay_swimmer_df = pd.DataFrame(
        [
            {
                "event_name": "Mixed 200 SC Meter Medley Relay",
                "relay_team_name": "Equipe A",
                "leg_order": "1",
                "swimmer_name": "Nadador Uno",
                "gender": "male",
                "age_at_event": "35",
                "birth_year_estimated": "1991",
                "page_number": "3",
                "line_number": "43",
            }
        ]
    )
    club_df = pd.DataFrame(columns=pipeline.EXPECTED_COLUMNS["club"])

    transformed = pipeline.transform_parser_relay_outputs(
        relay_team_df,
        relay_swimmer_df,
        club_df,
        default_source_id=1,
    )

    assert transformed["relay_result"].loc[0, "club_name"] == "Associacao Master"
    assert transformed["relay_result_member"].loc[0, "club_name"] == "Associacao Master"


def test_insert_core_athlete_deduplicates_staging_by_normalized_identity():
    class Cursor:
        def __init__(self):
            self.statements = []

        def execute(self, statement, params=None):
            self.statements.append((statement, params))

    cursor = Cursor()

    pipeline.insert_core_athlete(cursor, "core", 1)

    insert_statements = [statement for statement, _ in cursor.statements if "INSERT INTO core.athlete" in statement]
    assert len(insert_statements) == 2
    assert all("SELECT DISTINCT ON" in statement for statement in insert_statements)
    assert all("athlete_key" in statement for statement in insert_statements)


def test_result_and_relay_member_match_athletes_by_normalized_key():
    class Cursor:
        def __init__(self):
            self.statements = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, statement, params=None):
            self.statements.append((statement, params))

        def fetchone(self):
            return [0]

    class Conn:
        def __init__(self, cursor):
            self._cursor = cursor

        def cursor(self):
            return self._cursor

    cursor = Cursor()

    pipeline.insert_core_result(cursor, "core", 1, 1)
    pipeline.insert_core_relay_result_member(cursor, "core", 1)
    pipeline.collect_validations(Conn(cursor), argparse.Namespace(schema="core", competition_id=1))

    joined_sql = "\n".join(statement for statement, _ in cursor.statements)

    assert "LOWER(TRIM(at.full_name)) = LOWER(TRIM(r.athlete_name))" not in joined_sql
    assert "LOWER(TRIM(at.full_name)) = LOWER(TRIM(m.athlete_name))" not in joined_sql
    assert "TRANSLATE(LOWER(TRIM(at.full_name))" in joined_sql
    assert "TRANSLATE(LOWER(TRIM(r.athlete_name))" in joined_sql
    assert "TRANSLATE(LOWER(TRIM(m.athlete_name))" in joined_sql


def test_expected_points_case_uses_fchmn_scoring_rules():
    individual_sql = pipeline.expected_points_case_sql("rank_position", relay=False)
    relay_sql = pipeline.expected_points_case_sql("rank_position", relay=True)

    assert "WHEN 1 THEN 9.00" in individual_sql
    assert "WHEN 8 THEN 1.00" in individual_sql
    assert "WHEN 1 THEN 18.00" in relay_sql
    assert "WHEN 8 THEN 2.00" in relay_sql


def test_result_and_relay_insert_populate_expected_points():
    class Cursor:
        def __init__(self):
            self.statements = []

        def execute(self, statement, params=None):
            self.statements.append((statement, params))

    cursor = Cursor()

    pipeline.insert_core_result(cursor, "core", 1, 1)
    pipeline.insert_core_relay_result(cursor, "core", 1, 1)

    joined_sql = "\n".join(statement for statement, _ in cursor.statements)

    assert "points, expected_points," in joined_sql
    assert "WHEN 1 THEN 9.00" in joined_sql
    assert "WHEN 1 THEN 18.00" in joined_sql
