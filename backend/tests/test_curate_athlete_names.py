import shutil
import sys
import uuid
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import curate_athlete_names as curate


def _workspace_tmp_dir() -> Path:
    path = BACKEND_DIR / "data" / "raw" / "batch_summaries" / f"test_curate_athlete_names_{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path




def test_decision_birth_year_uses_core_year_for_suda_range_evidence():
    row = {
        "confidence_bucket": "suda_2026_birth_year_range",
        "source_identity_kind": "suda_name_range_2026",
        "birth_year": "1962-1966",
        "core_birth_year": "1962",
    }

    assert curate.decision_birth_year(row) == "1962"


def test_decision_birth_year_does_not_materialize_suda_range_without_core_year():
    row = {
        "confidence_bucket": "suda_2026_birth_year_range",
        "source_identity_kind": "suda_name_range_2026",
        "birth_year": "1962-1966",
        "core_birth_year": "",
    }

    assert curate.decision_birth_year(row) == ""


def test_fuzzy_identity_merge_keys_use_core_year_for_suda_range_rows():
    tmp_dir = _workspace_tmp_dir()
    try:
        decisions_path = tmp_dir / "suda_range.csv"
        decisions_path.write_text(
            "decision;confidence_bucket;suda_full_name;suda_gender;birth_year;core_full_name;core_gender;core_birth_year\n"
            'merge;suda_2026_birth_year_range;"DE QUEIROZ, MANOEL ELPIDIO PEREIRA";male;1962-1966;"Queiroz, Manoel";male;1962\n',
            encoding="utf-8",
        )

        assert curate.load_fuzzy_identity_merge_keys(decisions_path) == [
            {"name_key": "queiroz manoel", "birth_year": "1962", "gender": "male"}
        ]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_fuzzy_identity_decisions_accepts_headered_fechida_core_candidates():
    tmp_dir = _workspace_tmp_dir()
    try:
        decisions_path = tmp_dir / "fechida_core_candidates.csv"
        decisions_path.write_text(
            "decision;suggested_canonical_full_name;canonical_birth_year;review_hint;candidate_reason;gender;birth_year;club_key;shorter_full_name;longer_full_name;shorter_athlete_key;longer_athlete_key;source_full_name;source_athlete_key;source_club_name;source_club_key;source_table;source_urls;core_athlete_id;core_full_name;core_athlete_key;core_base_club_name;core_current_club_name;core_historical_club_names;club_context_match;candidate_count_for_source\n"
            "merge;Abarca Guzman, Pablo Ernesto;1999;cross_club_review;partial_name_match;male;1999;;Abarca, Pablo;Abarca Guzman, Pablo Ernesto;abarca pablo;abarca guzman pablo ernesto;Abarca, Pablo;abarca pablo;Club Deportivo Altis;club deportivo altis;athlete;https://fechida.cl/campeonato-info/?id=149;2079;Abarca Guzman, Pablo Ernesto;abarca guzman pablo ernesto;Goura Swim Team;Goura Swim Team;Goura Swim Team;no_contextual_club_match;1\n",
            encoding="utf-8",
        )

        rules = curate.load_fuzzy_identity_decisions(decisions_path)
        merge_keys = curate.load_fuzzy_identity_merge_keys(decisions_path)

        assert {
            "old_key": "abarca pablo",
            "new_name": "Abarca Guzman, Pablo Ernesto",
            "new_key": "abarca guzman pablo ernesto",
            "birth_year": "1999",
            "club_key": "",
            "gender": "male",
        } in rules
        assert merge_keys == [
            {"name_key": "abarca guzman pablo ernesto", "birth_year": "1999", "gender": "male"}
        ]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_normalize_birth_year_rejects_category_ranges():
    assert curate.normalize_birth_year("1962") == "1962"
    assert curate.normalize_birth_year("1962.0") == "1962"
    assert curate.normalize_birth_year("1962-1966") == ""

def test_athlete_name_signature_groups_common_ocr_variants():
    assert curate.athlete_name_signature("Pasarin, Claudia") == curate.athlete_name_signature(
        "Pasar\u00ed\u00f3n, Claudia"
    )
    assert curate.athlete_name_signature("Gomez, Francisco") == curate.athlete_name_signature(
        "Go\u00e1mez, Francisco"
    )
    assert curate.athlete_name_signature("Muller, Bettina") == curate.athlete_name_signature(
        "Mu\u00fcller, Bettina"
    )


def test_known_ocr_repair_drops_incomplete_trailing_parenthetical():
    assert curate.repair_known_ocr_name_residue(
        "RENE DE ALMEIDA LEITE (CENTRO NUTRICIONAL RL,"
    ) == "RENE DE ALMEIDA LEITE"


def test_build_review_rows_prefers_cleaner_canonical_names():
    rows = [
        {"athlete_name": "Pasarin, Claudia", "source_url": "a", "club_name": "Club A", "birth_year": "1964", "gender": "female"},
        {"athlete_name": "Pasar\u00ed\u00e1n, Claudia", "source_url": "b", "club_name": "Club A", "birth_year": "1964", "gender": "female"},
        {"athlete_name": "Pasar\u00ed\u00f3n, Claudia", "source_url": "c", "club_name": "Club A", "birth_year": "1964", "gender": "female"},
        {"athlete_name": "Mu\u00fcller, Bettina", "source_url": "d", "club_name": "Club B", "birth_year": "1964", "gender": "female"},
        {"athlete_name": "Muller, Bettina", "source_url": "e", "club_name": "Club B", "birth_year": "1964", "gender": "female"},
    ]

    review_rows, replacement_map = curate.build_review_rows(rows)

    canonical_by_signature = {row["signature"]: row["canonical_name"] for row in review_rows}
    assert "Pasarin, Claudia" in canonical_by_signature.values()
    assert "Muller, Bettina" in canonical_by_signature.values()
    assert replacement_map[("Pasar\u00ed\u00f3n, Claudia", "1964", "club a", "female")] == "Pasarin, Claudia"
    assert replacement_map[("Mu\u00fcller, Bettina", "1964", "club b", "female")] == "Muller, Bettina"


def test_build_review_rows_requires_birth_year_and_club_context():
    rows = [
        {"athlete_name": "Gomez, Francisco", "source_url": "a", "club_name": "Club A", "birth_year": "1987", "gender": "male"},
        {"athlete_name": "Go\u00e1mez, Francisco", "source_url": "b", "club_name": "Club A", "birth_year": "1987", "gender": "male"},
        {"athlete_name": "Go\u00e9mez, Francisco", "source_url": "c", "club_name": "Club B", "birth_year": "1987", "gender": "male"},
        {"athlete_name": "Go\u00f3mez, Francisco", "source_url": "d", "club_name": "Club A", "birth_year": "1988", "gender": "male"},
        {"athlete_name": "Go\u00famez, Francisco", "source_url": "e", "club_name": "Club A", "birth_year": "", "gender": "male"},
    ]

    _, replacement_map = curate.build_review_rows(rows)

    assert replacement_map == {
        ("Go\u00e1mez, Francisco", "1987", "club a", "male"): "Gomez, Francisco",
    }


def test_build_review_rows_does_not_apply_broad_name_collisions():
    rows = [
        {"athlete_name": "Alfaro, Mauricio", "source_url": "a", "club_name": "Club A", "birth_year": "1990", "gender": "male"},
        {"athlete_name": "Alfaro, Marco", "source_url": "b", "club_name": "Club A", "birth_year": "1990", "gender": "male"},
        {"athlete_name": "Augusto, Gloria", "source_url": "c", "club_name": "Club C", "birth_year": "1971", "gender": "female"},
        {"athlete_name": "Agusto, Gloria", "source_url": "d", "club_name": "Club C", "birth_year": "1971", "gender": "female"},
        {"athlete_name": "Augusto, Gloria", "source_url": "e", "club_name": "Club C", "birth_year": "1971", "gender": "female"},
        {"athlete_name": "Barrios, Sergio", "source_url": "f", "club_name": "Club D", "birth_year": "1998", "gender": "male"},
        {"athlete_name": "Barros, Sergio", "source_url": "g", "club_name": "Club D", "birth_year": "1998", "gender": "male"},
    ]

    _, replacement_map = curate.build_review_rows(rows)

    assert "Alfaro, Mauricio" not in [key[0] for key in replacement_map]
    assert "Augusto, Gloria" not in [key[0] for key in replacement_map]
    assert "Agusto, Gloria" not in [key[0] for key in replacement_map]
    assert "Barrios, Sergio" not in [key[0] for key in replacement_map]


def test_collect_name_rows_reads_parser_tables():
    tmp_dir = _workspace_tmp_dir()
    try:
        input_dir = tmp_dir / "parsed"
        input_dir.mkdir()
        pd.DataFrame(
            [{"full_name": "Cofre\u00e1, Patricio", "club_name": "Club Test", "gender": "male", "birth_year": "1980"}]
        ).to_csv(input_dir / "athlete.csv", index=False)
        pd.DataFrame(
            [{"athlete_name": "Go\u00e1mez, Francisco", "club_name": "Club Test", "birth_year_estimated": "1975"}]
        ).to_csv(input_dir / "result.csv", index=False)
        pd.DataFrame(
            [{"swimmer_name": "Mu\u00fcller, Bettina", "club_name": "Club Test", "gender": "female", "birth_year_estimated": "1982"}]
        ).to_csv(input_dir / "relay_swimmer.csv", index=False)

        rows = curate.collect_name_rows({"source_url": "https://example.test/resultados.pdf"}, input_dir)

        assert [row["table"] for row in rows] == ["athlete", "result", "relay_swimmer"]
        assert rows[0]["athlete_name"] == "Cofre\u00e1, Patricio"
        assert rows[1]["athlete_name"] == "Go\u00e1mez, Francisco"
        assert rows[2]["athlete_name"] == "Mu\u00fcller, Bettina"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_apply_athlete_curations_to_df_updates_names_and_birth_years():
    df = pd.DataFrame(
        [
            {
                "full_name": "Go\u00e1mez, Francisco",
                "club_name": "Club Test",
                "gender": "male",
                "birth_year": "1975",
            },
            {
                "full_name": "Acevedo, Luis A",
                "club_name": "Natacion Master Recoleta",
                "gender": "male",
                "birth_year": "1969",
            },
            {
                "full_name": "Arantxa Aranguren",
                "club_name": "Lozada Swim Team",
                "gender": "female",
                "birth_year": "",
            },
            {
                "full_name": "Abbott, Andres",
                "club_name": "Efecto Peruga",
                "gender": "male",
                "birth_year": "1985",
            },
        ]
    )
    rules = {
        "ocr_name_rules": [
            {
                "old_key": "goamez francisco",
                "new_name": "Gomez, Francisco",
                "new_key": "gomez francisco",
                "birth_year": "1975",
                "club_key": "club test",
                "gender": "male",
            }
        ],
        "name_correction_rules": [
            {
                "old_key": "cabello tilleria jorge",
                "new_name": "Cabello, Jorge T",
                "new_key": "cabello jorge t",
                "birth_year": "1958",
                "club_key": "iron swim master",
                "gender": "male",
            }
        ],
        "birth_year_rules": {("abbott andres", "male", "efecto peruga"): "1984"},
        "missing_birth_year_rules": [
            {
                "old_key": "arantxa aranguren",
                "new_name": "Aranguren, Arantxa",
                "new_key": "aranguren arantxa",
                "birth_year": "1994",
                "club_key": "lozada swim team",
                "gender": "female",
            }
        ],
        "partial_name_rules": [
            {
                "old_key": "acevedo luis a",
                "new_name": "Acevedo, Luis Alberto",
                "new_key": "acevedo luis alberto",
                "birth_year": "1969",
                "club_key": "natacion master recoleta",
                "gender": "male",
            }
        ],
        "gender_correction_rules": [
            {
                "name_key": "molero vianny",
                "birth_year": "1990",
                "gender": "female",
            }
        ],
    }
    df.loc[len(df)] = {
        "full_name": "Molero, Vianny",
        "club_name": "Club Nunoa Master",
        "gender": "male",
        "birth_year": "1990",
    }
    df.loc[len(df)] = {
        "full_name": "Cabello Tilleria, Jorge",
        "club_name": "Iron Swim Master",
        "gender": "male",
        "birth_year": "1958",
    }

    curated, counts = curate.apply_athlete_curations_to_df(df, "athlete", rules)

    assert curated.loc[0, "full_name"] == "Gomez, Francisco"
    assert curated.loc[1, "full_name"] == "Acevedo, Luis Alberto"
    assert curated.loc[2, "full_name"] == "Aranguren, Arantxa"
    assert curated.loc[2, "birth_year"] == "1994"
    assert curated.loc[3, "birth_year"] == "1984"
    assert curated.loc[4, "gender"] == "female"
    assert curated.loc[5, "full_name"] == "Cabello, Jorge T"
    assert counts == {
        "known_ocr_name_residue_repairs": 1,
        "name_corrections": 1,
        "birth_year_corrections": 1,
        "missing_birth_year_consolidations": 1,
        "partial_name_consolidations": 1,
        "gender_corrections": 1,
    }


def test_load_gender_corrections_accepts_reviewed_csv():
    tmp_dir = _workspace_tmp_dir()
    try:
        corrections_path = tmp_dir / "gender_corrections.csv"
        corrections_path.write_text(
            "full_name,birth_year,gender\n"
            '"Molero, Vianny",1990,female\n',
            encoding="utf-8",
        )

        rules = curate.load_gender_corrections(corrections_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    assert rules == [{"name_key": "molero vianny", "birth_year": "1990", "gender": "female"}]


def test_load_name_corrections_accepts_club_locked_csv():
    tmp_dir = _workspace_tmp_dir()
    try:
        corrections_path = tmp_dir / "name_corrections.csv"
        corrections_path.write_text(
            "decision;old_full_name;new_full_name;birth_year;club_key;gender\n"
            'merge;"Cabello Tilleria, Jorge";"Cabello, Jorge T";1958;iron swim master;male\n',
            encoding="utf-8",
        )

        rules = curate.load_name_corrections(corrections_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    assert rules == [
        {
            "old_key": "cabello tilleria jorge",
            "new_name": "Cabello, Jorge T",
            "new_key": "cabello jorge t",
            "birth_year": "1958",
            "club_key": "iron swim master",
            "gender": "male",
        }
    ]


def test_load_result_exclusions_accepts_reviewed_csv():
    tmp_dir = _workspace_tmp_dir()
    try:
        exclusions_path = tmp_dir / "result_exclusions.csv"
        exclusions_path.write_text(
            "decision;source_url;event_name;athlete_name;club_name;birth_year;reason\n"
            'exclude;https://example.test/result.pdf;"men 25-29 100 LC Meter backstroke";"Lopez Acevedo, Job";"Peñalolen Master";1997;implausible source row\n',
            encoding="utf-8",
        )

        rules = curate.load_result_exclusions(exclusions_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    assert rules == [
        {
            "source_url": "https://example.test/result.pdf",
            "event_key": "men 25 29 100 lc meter backstroke",
            "athlete_key": "lopez acevedo job",
            "club_key": "penalolen master",
            "birth_year": "1997",
        }
    ]


def test_load_result_event_corrections_accepts_reviewed_csv():
    tmp_dir = _workspace_tmp_dir()
    try:
        corrections_path = tmp_dir / "result_event_corrections.csv"
        corrections_path.write_text(
            "decision;source_url;old_event_name;new_event_name;athlete_name;club_name;birth_year;reason\n"
            'correct;https://example.test/lqblo.pdf;"men 55-59 100 SC Meter individual_medley";"men 30-34 50 SC Meter butterfly";"Saldias, Alfredo";MSBDO;1989;column continuation\n',
            encoding="utf-8",
        )

        rules = curate.load_result_event_corrections(corrections_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    assert rules == [
        {
            "source_url": "https://example.test/lqblo.pdf",
            "old_event_key": "men 55 59 100 sc meter individual medley",
            "new_event_name": "men 30-34 50 SC Meter butterfly",
            "athlete_key": "saldias alfredo",
            "club_key": "msbdo",
            "birth_year": "1989",
        }
    ]


def test_load_fuzzy_identity_decisions_accepts_headerless_semicolon_cp1252_csv():
    tmp_dir = _workspace_tmp_dir()
    try:
        decisions_path = tmp_dir / "fuzzy_decisions.csv"
        row = [
            "merge",
            "Zonza, Marcela",
            "same_club_high_confidence",
            "surname_edit_distance_le1_first_given_compatible",
            "female",
            "1979",
            "yes",
            "4635",
            "Zonsa, Marcela",
            "Fullmar Vi\u00f1a del Mar",
            "2",
            "2",
            "0",
            "1",
            "Zonza, Marcela",
            "Delfines de Villa Alemana",
            "52",
            "50",
            "2",
            "800",
            "1000",
            "1",
            "Fullmar Vi\u00f1a del Mar",
            "",
            "Delfines de Villa Alemana",
            "Delfines de Villa Alemana",
        ]
        decisions_path.write_text(";".join(row) + "\n", encoding="cp1252")

        rules = curate.load_fuzzy_identity_decisions(decisions_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    assert rules == [
        {
            "old_key": "zonsa marcela",
            "new_name": "Zonza, Marcela",
            "new_key": "zonza marcela",
            "birth_year": "1979",
            "club_key": "",
            "gender": "female",
        }
    ]


def test_fuzzy_identity_rules_apply_by_birth_year_and_gender_without_club_lock():
    df = pd.DataFrame(
        [
            {
                "full_name": "Zonsa, Marcela",
                "club_name": "Fullmar Vi\u00f1a del Mar",
                "gender": "female",
                "birth_year": "1979",
            },
            {
                "full_name": "Zonsa, Marcela",
                "club_name": "Fullmar Vi\u00f1a del Mar",
                "gender": "female",
                "birth_year": "1980",
            },
        ]
    )
    rules = {
        "ocr_name_rules": [],
        "birth_year_rules": {},
        "missing_birth_year_rules": [],
        "partial_name_rules": [],
        "fuzzy_identity_rules": [
            {
                "old_key": "zonsa marcela",
                "new_name": "Zonza, Marcela",
                "new_key": "zonza marcela",
                "birth_year": "1979",
                "club_key": "",
                "gender": "female",
            }
        ],
    }

    curated, counts = curate.apply_athlete_curations_to_df(df, "athlete", rules)

    assert curated.loc[0, "full_name"] == "Zonza, Marcela"
    assert curated.loc[1, "full_name"] == "Zonsa, Marcela"
    assert counts == {"fuzzy_identity_consolidations": 1}





def test_apply_adaip_relay_line_wrap_correction_updates_team_swimmers_and_club():
    tmp_dir = _workspace_tmp_dir()
    try:
        pd.DataFrame(
            [{"name": "ANMPE", "short_name": None, "city": None, "region": None, "source_id": "1"}]
        ).to_csv(tmp_dir / "club.csv", index=False)
        pd.DataFrame(
            [
                {
                    "event_name": "men 120+ 4x50 SC Meter freestyle_relay",
                    "club_name": "INTERIORADAIP",
                    "relay_team_name": "ASSOCIAÇÃO DE DESPORTOS AQUÁTICOS DO",
                    "rank_position": "6",
                    "seed_time_text": None,
                    "seed_time_ms": None,
                    "result_time_text": "1:52,04",
                    "result_time_ms": "112040",
                    "points": "0,00",
                    "status": "valid",
                    "source_id": "1",
                    "page_number": "147",
                    "line_number": "73",
                }
            ]
        ).to_csv(tmp_dir / "relay_team.csv", index=False)
        pd.DataFrame(
            [
                {"event_name": "men 120+ 4x50 SC Meter freestyle_relay", "relay_team_name": "ASSOCIAÇÃO DE DESPORTOS AQUÁTICOS DO", "leg_order": "1", "swimmer_name": "Uno", "gender": None, "age_at_event": None, "birth_year_estimated": None, "page_number": "147", "line_number": "77"},
                {"event_name": "men 120+ 4x50 SC Meter freestyle_relay", "relay_team_name": "ASSOCIAÇÃO DOS NADADORES MASTERS DE", "leg_order": "1", "swimmer_name": "Otro", "gender": None, "age_at_event": None, "birth_year_estimated": None, "page_number": "147", "line_number": "48"},
            ]
        ).to_csv(tmp_dir / "relay_swimmer.csv", index=False)

        corrected = curate.apply_adaip_relay_line_wrap_correction(tmp_dir)
        relay_team = pd.read_csv(tmp_dir / "relay_team.csv", dtype=str, encoding="utf-8-sig")
        relay_swimmer = pd.read_csv(tmp_dir / "relay_swimmer.csv", dtype=str, encoding="utf-8-sig")
        club = pd.read_csv(tmp_dir / "club.csv", dtype=str, encoding="utf-8-sig")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    assert corrected == 1
    assert relay_team.loc[0, "club_name"] == "ADAIP"
    assert relay_team.loc[0, "relay_team_name"] == curate.ADAIP_RELAY_TEAM_NAME
    assert relay_swimmer.loc[0, "relay_team_name"] == curate.ADAIP_RELAY_TEAM_NAME
    assert relay_swimmer.loc[1, "relay_team_name"] == "ASSOCIAÇÃO DOS NADADORES MASTERS DE"
    assert "ADAIP" in club["name"].tolist()

def test_drop_invalid_relay_swimmer_leg_order_removes_non_swimmer_rows():
    df = pd.DataFrame(
        [
            {"leg_order": "1", "swimmer_name": "Uno"},
            {"leg_order": "4", "swimmer_name": "Cuatro"},
            {"leg_order": "5", "swimmer_name": "Footer"},
            {"leg_order": "", "swimmer_name": "Header"},
        ]
    )

    filtered, dropped = curate.drop_invalid_relay_swimmer_leg_order(df)

    assert dropped == 2
    assert filtered["swimmer_name"].tolist() == ["Uno", "Cuatro"]

def test_suda_range_identity_decisions_apply_to_result_rows_without_birth_year():
    tmp_dir = _workspace_tmp_dir()
    try:
        decisions_path = tmp_dir / "suda_range_decisions.csv"
        decisions_path.write_text(
            "decision;status;suda_full_name;suda_gender;suda_birth_year_range;suda_clubs;core_athlete_id;core_full_name;core_gender;core_birth_year\n"
            'merge;no_birth_year_2026_range_candidate;"GALLEGUILLOS, ROSARIO SOLEDAD PINTO";female;1957-1961;"PE?ALOLEN MASTER";1138;"Pinto Galleguillos, Rosario Soledad";female;1959\n',
            encoding="utf-8",
        )
        rules = curate.load_fuzzy_identity_decisions(decisions_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    result_df = pd.DataFrame(
        [
            {
                "athlete_name": "GALLEGUILLOS, ROSARIO SOLEDAD PINTO",
                "club_name": "PE?ALOLEN MASTER",
                "birth_year_estimated": "",
            }
        ]
    )
    curated, counts = curate.apply_athlete_curations_to_df(
        result_df,
        "result",
        {
            "ocr_name_rules": [],
            "birth_year_rules": {},
            "missing_birth_year_rules": [],
            "partial_name_rules": [],
            "fuzzy_identity_rules": rules,
        },
    )

    assert curated.loc[0, "athlete_name"] == "Pinto Galleguillos, Rosario Soledad"
    assert curated.loc[0, "birth_year_estimated"] in {"", None}
    assert counts == {"fuzzy_identity_consolidations": 1}

def test_fuzzy_identity_birth_year_decisions_correct_same_name_delta_one():
    tmp_dir = _workspace_tmp_dir()
    try:
        decisions_path = tmp_dir / "fuzzy_delta_one.csv"
        decisions_path.write_text(
            "\n".join(
                [
                    ";".join(
                        [
                            "decision",
                            "suggested_canonical_full_name",
                            "review_hint",
                            "candidate_reason",
                            "gender",
                            "birth_year",
                            "left_birth_year",
                            "right_birth_year",
                            "birth_year_delta",
                            "same_club",
                            "left_athlete_id",
                            "left_full_name",
                            "left_club",
                            "right_athlete_id",
                            "right_full_name",
                            "right_club",
                        ]
                    ),
                    ";".join(
                        [
                            "merge",
                            "Acosta, Andres",
                            "birth_year_delta_1_review",
                            "birth_year_delta_1_name_compatible",
                            "male",
                            "1987",
                            "1987",
                            "1988",
                            "1",
                            "no",
                            "2190",
                            "Acosta, Andres",
                            "Nunoa Master",
                            "4513",
                            "Acosta, Andres",
                            "Pura Vida Pichilemu",
                        ]
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        rules = curate.load_fuzzy_identity_birth_year_decisions(decisions_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    assert rules == [
        {
            "old_key": "acosta andres",
            "old_birth_year": "1988",
            "new_name": "Acosta, Andres",
            "new_key": "acosta andres",
            "birth_year": "1987",
            "club_key": "",
            "gender": "male",
        }
    ]

    df = pd.DataFrame(
        [
            {
                "full_name": "Acosta, Andres",
                "club_name": "Pura Vida Pichilemu",
                "gender": "male",
                "birth_year": "1988",
            }
        ]
    )
    curated, counts = curate.apply_athlete_curations_to_df(
        df,
        "athlete",
        {
            "ocr_name_rules": [],
            "birth_year_rules": {},
            "missing_birth_year_rules": [],
            "partial_name_rules": [],
            "fuzzy_identity_rules": [],
            "fuzzy_identity_birth_year_rules": rules,
        },
    )

    assert curated.loc[0, "full_name"] == "Acosta, Andres"
    assert curated.loc[0, "birth_year"] == "1987"
    assert counts == {"fuzzy_identity_birth_year_corrections": 1}


def test_partial_name_rules_chain_and_apply_by_identity_when_unambiguous():
    rules = {
        "ocr_name_rules": [],
        "birth_year_rules": {},
        "missing_birth_year_rules": [],
        "partial_name_rules": curate.resolve_partial_name_rule_chains(
            [
                {
                    "old_key": "acevedo luis",
                    "new_name": "Acevedo, Luis A",
                    "new_key": "acevedo luis a",
                    "birth_year": "1969",
                    "club_key": "natacion master recoleta",
                    "gender": "male",
                },
                {
                    "old_key": "acevedo luis a",
                    "new_name": "Acevedo, Luis Alberto",
                    "new_key": "acevedo luis alberto",
                    "birth_year": "1969",
                    "club_key": "natacion master recoleta",
                    "gender": "male",
                },
            ]
        ),
        "comma_order_rules": [],
    }
    rules["partial_name_identity_rules"] = curate.build_partial_name_identity_rules(rules["partial_name_rules"])
    df = pd.DataFrame(
        [
            {
                "full_name": "Acevedo, Luis",
                "club_name": "Natacion Recoleta",
                "birth_year": "1969",
                "gender": "male",
            },
            {
                "full_name": "Acevedo, Luis A",
                "club_name": "Master Recoleta",
                "birth_year": "1969",
                "gender": "male",
            },
        ]
    )

    curated, counts = curate.apply_athlete_curations_to_df(df, "athlete", rules)

    assert curated["full_name"].tolist() == ["Acevedo, Luis Alberto", "Acevedo, Luis Alberto"]
    assert counts == {"partial_name_identity_consolidations": 2}


def test_repair_known_ocr_name_residue_materializes_known_patterns():
    assert curate.repair_known_ocr_name_residue("A\u00c1lvarez, Alex") == "Alvarez, Alex"
    assert curate.repair_known_ocr_name_residue("Cofre\u00e1, Patricio") == "Cofre, Patricio"
    assert curate.repair_known_ocr_name_residue("Brice\u00f1 \u00f1o, Da\u00f1iel") == "Brice\u00f1o, Da\u00f1iel"
    assert curate.repair_known_ocr_name_residue("Ya\u00f1 \u00f1ez, Roberto") == "Ya\u00f1ez, Roberto"
    assert curate.repair_known_ocr_name_residue("Mar\u00ed\u00e1 Jos\u00e9, Bocaz") == "Maria Jos\u00e9, Bocaz"
    assert curate.repair_known_ocr_name_residue("Olivares O\u00c1 rdenes, Cristi\u00e1n") == "Olivares Ordenes, Cristi\u00e1n"


def test_canonicalize_space_ordered_name_preserves_surname_particles():
    assert curate.canonicalize_space_ordered_name("Eduardo Nuñez") == "Nuñez, Eduardo"
    assert (
        curate.canonicalize_space_ordered_name("Maria Antonieta de La Maza")
        == "de La Maza, Maria Antonieta"
    )
    assert (
        curate.canonicalize_space_ordered_name("CAIO CUNHA FRANCO (FORTALEZA RAIA 4)")
        == "FRANCO, CAIO CUNHA"
    )
    assert curate.canonicalize_space_ordered_name("Rojas, Jorge") == "Rojas, Jorge"


def test_portuguese_name_tokens_and_case_are_preserved():
    assert curate.NAME_TOKEN_RE.findall("GONÇALVES CORRÊA CONCEIÇÃO") == [
        "GONÇALVES",
        "CORRÊA",
        "CONCEIÇÃO",
    ]
    assert (
        curate.normalize_person_name_case("MARIA MADALENA NUNES CONCEIÇÃO")
        == "Maria Madalena Nunes Conceição"
    )


def test_apply_curations_preserves_reviewed_given_family_source_order():
    df = pd.DataFrame(
        [{"full_name": "VICTOR HUGO HORDONES ABDO", "club_name": "TNT SP", "birth_year": "", "gender": "male"}]
    )

    curated, counts = curate.apply_athlete_curations_to_df(
        df,
        "athlete",
        {"ocr_name_rules": [], "birth_year_rules": {}, "missing_birth_year_rules": [], "partial_name_rules": []},
        preserve_source_name_order=True,
    )

    assert curated.iloc[0]["full_name"] == "Victor Hugo Hordones Abdo"
    assert counts.get("space_order_name_canonicalizations", 0) == 0


def test_apply_athlete_curations_to_df_canonicalizes_space_ordered_names():
    df = pd.DataFrame(
        [
            {
                "full_name": "Jennifer Gomez",
                "club_name": "Delfines",
                "birth_year": "",
                "gender": "female",
            }
        ]
    )
    rules = {
        "ocr_name_rules": [],
        "birth_year_rules": {},
        "missing_birth_year_rules": [],
        "partial_name_rules": [],
    }

    curated, counts = curate.apply_athlete_curations_to_df(df, "athlete", rules)

    assert curated.loc[0, "full_name"] == "Gomez, Jennifer"
    assert counts == {"space_order_name_canonicalizations": 1}


def test_apply_athlete_curations_to_df_does_not_flip_space_ordered_names_with_birth_year():
    df = pd.DataFrame(
        [
            {
                "full_name": "Herrera Adriana",
                "club_name": "Turquesa",
                "birth_year": "1974",
                "gender": "female",
            }
        ]
    )
    rules = {
        "ocr_name_rules": [],
        "birth_year_rules": {},
        "missing_birth_year_rules": [],
        "partial_name_rules": [],
    }

    curated, counts = curate.apply_athlete_curations_to_df(df, "athlete", rules)

    assert curated.loc[0, "full_name"] == "Herrera Adriana"
    assert counts == {}


def test_apply_athlete_curations_to_df_corrects_likely_comma_order_from_corpus_rule():
    df = pd.DataFrame(
        [
            {
                "full_name": "Adriana, Herrera",
                "club_name": "Turquesa",
                "birth_year": "1974",
                "gender": "female",
            }
        ]
    )
    rules = {
        "ocr_name_rules": [],
        "birth_year_rules": {},
        "missing_birth_year_rules": [],
        "partial_name_rules": [],
        "comma_order_rules": [
            {
                "old_key": "adriana herrera",
                "new_name": "Herrera, Adriana",
                "new_key": "herrera adriana",
                "birth_year": "1974",
                "club_key": "turquesa",
                "gender": "female",
            }
        ],
    }

    curated, counts = curate.apply_athlete_curations_to_df(df, "athlete", rules)

    assert curated.loc[0, "full_name"] == "Herrera, Adriana"
    assert counts == {"comma_order_corrections": 1}


def test_apply_athlete_curations_to_df_corrects_comma_order_without_club_when_unambiguous():
    rules = {
        "ocr_name_rules": [],
        "birth_year_rules": {},
        "missing_birth_year_rules": [],
        "partial_name_rules": [],
        "comma_order_rules": [
            {
                "old_key": "natalia silva",
                "new_name": "Silva, Natalia",
                "new_key": "silva natalia",
                "birth_year": "1985",
                "club_key": "agua plena san rafael",
                "gender": "female",
            }
        ],
    }
    rules["comma_order_identity_rules"] = curate.build_comma_order_identity_rules(rules["comma_order_rules"])
    df = pd.DataFrame(
        [
            {
                "event_name": "women 120-159 4x50 SC Meter medley_relay",
                "relay_team_name": "Agua Plena San Rafael A",
                "leg_order": "2",
                "swimmer_name": "Natalia, Silva",
                "gender": "female",
                "birth_year_estimated": "1985",
            }
        ]
    )

    curated, counts = curate.apply_athlete_curations_to_df(df, "relay_swimmer", rules)

    assert curated.loc[0, "swimmer_name"] == "Silva, Natalia"
    assert counts == {"comma_order_corrections": 1}


def test_drop_result_rows_with_athlete_gender_conflict():
    athlete_df = pd.DataFrame(
        [
            {
                "full_name": "Henriquez, Soledad",
                "gender": "female",
                "club_name": "MSBDO",
                "birth_year": "1984",
            },
            {
                "full_name": "Rivera, Pedro Pablo",
                "gender": "male",
                "club_name": "SIMAS",
                "birth_year": "1980",
            },
            {
                "full_name": "Perez, Paulina",
                "gender": "male",
                "club_name": "RECOL",
                "birth_year": "1970",
            },
        ]
    )
    result_df = pd.DataFrame(
        [
            {
                "event_name": "men 35-39 50 LC Meter breaststroke",
                "athlete_name": "Henriquez, Soledad",
                "club_name": "MSBDO",
                "birth_year_estimated": "1984",
                "result_time_ms": "252110",
            },
            {
                "event_name": "men 40-44 50 LC Meter breaststroke",
                "athlete_name": "Rivera, Pedro Pablo",
                "club_name": "SIMAS",
                "birth_year_estimated": "1980",
                "result_time_ms": "32000",
            },
            {
                "event_name": "men 50-54 200 LC Meter backstroke",
                "athlete_name": "Perez Pacheco, Paulina",
                "club_name": "RECOL",
                "birth_year_estimated": "1970",
                "result_time_ms": "48450",
            },
            {
                "event_name": "women 50-54 50 LC Meter butterfly",
                "athlete_name": "Perez Pacheco, Paulina",
                "club_name": "RECOL",
                "birth_year_estimated": "1970",
                "result_time_ms": "61160",
            },
        ]
    )

    filtered, dropped = curate.drop_result_rows_with_athlete_gender_conflict(result_df, athlete_df)

    assert dropped == 2
    assert filtered["athlete_name"].tolist() == ["Rivera, Pedro Pablo", "Perez Pacheco, Paulina"]
    assert filtered["event_name"].tolist() == [
        "men 40-44 50 LC Meter breaststroke",
        "women 50-54 50 LC Meter butterfly",
    ]


def test_drop_result_rows_with_reviewed_exclusions():
    result_df = pd.DataFrame(
        [
            {
                "event_name": "men 25-29 100 LC Meter backstroke",
                "athlete_name": "Lopez Acevedo, Job",
                "club_name": "Peñalolen Master",
                "birth_year_estimated": "1997",
            },
            {
                "event_name": "men 25-29 100 LC Meter backstroke",
                "athlete_name": "Other, Swimmer",
                "club_name": "Peñalolen Master",
                "birth_year_estimated": "1997",
            },
        ]
    )
    rules = {
        "result_exclusion_rules": [
            {
                "source_url": "https://example.test/result.pdf",
                "event_key": "men 25 29 100 lc meter backstroke",
                "athlete_key": "lopez acevedo job",
                "club_key": "penalolen master",
                "birth_year": "1997",
            }
        ]
    }

    filtered, dropped = curate.drop_result_rows_with_reviewed_exclusions(
        result_df,
        "https://example.test/result.pdf",
        rules,
    )

    assert dropped == 1
    assert filtered["athlete_name"].tolist() == ["Other, Swimmer"]


def test_apply_result_event_corrections_reclassifies_reviewed_rows_without_dropping():
    result_df = pd.DataFrame(
        [
            {
                "event_name": "men 55-59 100 SC Meter individual_medley",
                "athlete_name": "Saldias, Alfredo",
                "club_name": "MSBDO",
                "birth_year_estimated": "1989",
                "result_time_text": "35,84",
            },
            {
                "event_name": "men 55-59 100 SC Meter individual_medley",
                "athlete_name": "Fuenzalida, Carlos",
                "club_name": "PTOMO",
                "birth_year_estimated": "1966",
                "result_time_text": "1:24,28",
            },
        ]
    )
    rules = {
        "result_event_correction_rules": [
            {
                "source_url": "https://example.test/lqblo.pdf",
                "old_event_key": "men 55 59 100 sc meter individual medley",
                "new_event_name": "men 30-34 50 SC Meter butterfly",
                "athlete_key": "saldias alfredo",
                "club_key": "msbdo",
                "birth_year": "1989",
            }
        ]
    }

    corrected, count = curate.apply_result_event_corrections(result_df, "https://example.test/lqblo.pdf", rules)

    assert count == 1
    assert len(corrected) == 2
    assert corrected.loc[0, "event_name"] == "men 30-34 50 SC Meter butterfly"
    assert corrected.loc[1, "event_name"] == "men 55-59 100 SC Meter individual_medley"


def test_sync_athlete_rows_from_result_identities_uses_surviving_result_gender():
    athlete_df = pd.DataFrame(
        [
            {
                "full_name": "Perez, Paulina",
                "gender": "male",
                "club_name": "RECOL",
                "birth_year": "1970",
            }
        ]
    )
    result_df = pd.DataFrame(
        [
            {
                "event_name": "women 50-54 50 LC Meter butterfly",
                "athlete_name": "Perez Pacheco, Paulina",
                "club_name": "RECOL",
                "birth_year_estimated": "1970",
            }
        ]
    )
    rules = {
        "fuzzy_identity_rules": [
            {
                "old_key": "perez paulina",
                "new_name": "Perez Pacheco, Paulina",
                "new_key": "perez pacheco paulina",
                "birth_year": "1970",
                "club_key": "",
                "gender": "female",
            }
        ],
    }

    synced, count = curate.sync_athlete_rows_from_result_identities(athlete_df, result_df, rules)

    assert count == 1
    assert synced.loc[0, "full_name"] == "Perez Pacheco, Paulina"
    assert synced.loc[0, "gender"] == "female"


def test_prune_athlete_rows_without_observations_after_result_exclusion():
    athlete_df = pd.DataFrame(
        [
            {
                "full_name": "Cabello, Jorge T",
                "gender": "male",
                "club_name": "Iron Swim Master",
                "birth_year": "1958",
            },
            {
                "full_name": "Torres, Sergio",
                "gender": "male",
                "club_name": "Condrictios Team",
                "birth_year": "1994",
            },
        ]
    )
    result_df = pd.DataFrame(
        [
            {
                "event_name": "men 30-34 400 LC Meter freestyle",
                "athlete_name": "Torres, Sergio",
                "club_name": "Condrictios Team",
                "birth_year_estimated": "1994",
            }
        ]
    )
    relay_swimmer_df = pd.DataFrame()

    pruned, dropped = curate.prune_athlete_rows_without_observations(
        athlete_df,
        result_df,
        relay_swimmer_df,
    )

    assert dropped == 1
    assert pruned["full_name"].tolist() == ["Torres, Sergio"]


def test_prune_duplicate_athlete_rows_for_reviewed_identity_merges_keeps_homonyms_without_rule():
    athlete_df = pd.DataFrame(
        [
            {
                "full_name": "Leal, Rene",
                "gender": "male",
                "club_name": "Fullmar Viña del Mar",
                "birth_year": "1964",
            },
            {
                "full_name": "Leal, Rene",
                "gender": "male",
                "club_name": "Delfines de Villa Alemana",
                "birth_year": "1964",
            },
            {
                "full_name": "Torres, Sergio",
                "gender": "male",
                "club_name": "Lozada Swim Team",
                "birth_year": "1994",
            },
            {
                "full_name": "Torres, Sergio",
                "gender": "male",
                "club_name": "Condrictios Team",
                "birth_year": "1994",
            },
        ]
    )
    rules = {
        "athlete_identity_merge_keys": [
            {
                "name_key": "leal rene",
                "birth_year": "1964",
                "gender": "male",
            }
        ]
    }

    pruned, dropped = curate.prune_duplicate_athlete_rows_for_reviewed_identity_merges(
        athlete_df,
        rules,
    )

    assert dropped == 1
    assert pruned["full_name"].tolist() == ["Leal, Rene", "Torres, Sergio", "Torres, Sergio"]
    assert pruned["club_name"].tolist() == ["Fullmar Viña del Mar", "Lozada Swim Team", "Condrictios Team"]


def test_reviewed_identity_deduplication_is_independent_for_each_document():
    athlete_df = pd.DataFrame(
        [
            {
                "full_name": "Sayago Moreno, Alexis Saul",
                "gender": "male",
                "club_name": "Nunoa Master",
                "birth_year": "1993",
            }
        ]
    )
    rules = {
        "athlete_identity_merge_keys": [
            {
                "name_key": "sayago moreno alexis saul",
                "birth_year": "1993",
                "gender": "male",
            }
        ]
    }

    first_document, first_dropped = curate.prune_duplicate_athlete_rows_for_reviewed_identity_merges(
        athlete_df,
        rules,
    )
    second_document, second_dropped = curate.prune_duplicate_athlete_rows_for_reviewed_identity_merges(
        athlete_df,
        rules,
    )

    assert first_dropped == second_dropped == 0
    assert first_document["full_name"].tolist() == second_document["full_name"].tolist() == [
        "Sayago Moreno, Alexis Saul"
    ]


def test_identity_merge_key_fills_missing_birth_year_without_merging_homonyms():
    df = pd.DataFrame(
        [
            {
                "full_name": "Leal, Rene",
                "club_name": "DELVA",
                "birth_year": "",
                "gender": "male",
            },
            {
                "full_name": "Torres, Sergio",
                "club_name": "CONDT",
                "birth_year": "",
                "gender": "male",
            },
        ]
    )
    rules = {
        "ocr_name_rules": [],
        "birth_year_rules": {},
        "missing_birth_year_rules": [],
        "partial_name_rules": [],
        "athlete_identity_merge_keys": [
            {
                "name_key": "leal rene",
                "birth_year": "1964",
                "gender": "male",
            }
        ],
    }

    curated, counts = curate.apply_athlete_curations_to_df(df, "athlete", rules)

    assert curated.loc[0, "birth_year"] == "1964"
    assert curated.loc[1, "birth_year"] == ""
    assert counts == {"identity_merge_missing_birth_year_consolidations": 1}


def test_apply_athlete_curations_to_df_repairs_relay_swimmer_without_club_column():
    df = pd.DataFrame(
        [
            {
                "event_name": "mixed 200 LC Meter freestyle_relay",
                "relay_team_name": "Club A",
                "swimmer_name": "A\u00c1lvarez, Alonso",
                "birth_year_estimated": "1987",
                "gender": "male",
            }
        ]
    )
    rules = {
        "ocr_name_rules": [],
        "birth_year_rules": {},
        "missing_birth_year_rules": [],
        "partial_name_rules": [],
    }

    curated, counts = curate.apply_athlete_curations_to_df(df, "relay_swimmer", rules)

    assert curated.loc[0, "swimmer_name"] == "Alvarez, Alonso"
    assert counts == {"known_ocr_name_residue_repairs": 1}


def test_apply_athlete_curations_to_df_applies_identity_rule_to_relay_swimmer_without_club_column():
    df = pd.DataFrame(
        [
            {
                "event_name": "mixed 200 LC Meter freestyle_relay",
                "relay_team_name": "Master Recoleta A",
                "swimmer_name": "Acevedo, Luis A",
                "birth_year_estimated": "1969",
                "gender": "male",
            }
        ]
    )
    rules = {
        "ocr_name_rules": [],
        "birth_year_rules": {},
        "missing_birth_year_rules": [],
        "partial_name_rules": [],
        "partial_name_identity_rules": [
            {
                "old_key": "acevedo luis a",
                "new_name": "Acevedo, Luis Alberto",
                "new_key": "acevedo luis alberto",
                "birth_year": "1969",
                "club_key": "",
                "gender": "male",
            }
        ],
        "comma_order_rules": [],
    }

    curated, counts = curate.apply_athlete_curations_to_df(df, "relay_swimmer", rules)

    assert curated.loc[0, "swimmer_name"] == "Acevedo, Luis Alberto"
    assert counts == {"partial_name_identity_consolidations": 1}


def test_apply_athlete_curations_to_df_applies_identity_rule_to_missing_birth_year():
    df = pd.DataFrame(
        [
            {
                "full_name": "Acevedo, Luis",
                "club_name": "NRECO",
                "birth_year": "",
                "gender": "male",
            }
        ]
    )
    rules = {
        "ocr_name_rules": [],
        "birth_year_rules": {},
        "missing_birth_year_rules": [],
        "partial_name_rules": [],
        "partial_name_identity_rules": [
            {
                "old_key": "acevedo luis",
                "new_name": "Acevedo, Luis Alberto",
                "new_key": "acevedo luis alberto",
                "birth_year": "1969",
                "club_key": "",
                "gender": "male",
            }
        ],
        "comma_order_rules": [],
    }

    curated, counts = curate.apply_athlete_curations_to_df(df, "athlete", rules)

    assert curated.loc[0, "full_name"] == "Acevedo, Luis Alberto"
    assert curated.loc[0, "birth_year"] == "1969"
    assert counts == {"partial_name_missing_birth_year_consolidations": 1}


def test_materialized_input_dir_drops_generated_results_root():
    source = BACKEND_DIR / "data" / "raw" / "results_csv" / "fchmn_curated_final_identity_20260503" / "fchmn_auto" / "2025" / "doc"
    output_root = BACKEND_DIR / "data" / "raw" / "results_csv" / "fc_next"

    assert curate.materialized_input_dir(source, output_root) == output_root / "fchmn_auto" / "2025" / "doc"


def test_materialized_input_dir_drops_parser_reparse_root():
    source = BACKEND_DIR / "data" / "raw" / "results_csv" / "fchmn_parser020_20260510" / "fchmn_auto" / "2025" / "doc"
    output_root = BACKEND_DIR / "data" / "raw" / "results_csv" / "fchmn_parser020_curated_20260510"

    assert curate.materialized_input_dir(source, output_root) == output_root / "fchmn_auto" / "2025" / "doc"


def test_apply_athlete_curations_to_df_applies_identity_after_space_order_canonicalization():
    df = pd.DataFrame(
        [
            {
                "full_name": "Luis Acevedo",
                "club_name": "NRECO",
                "birth_year": "",
                "gender": "male",
            }
        ]
    )
    rules = {
        "ocr_name_rules": [],
        "birth_year_rules": {},
        "missing_birth_year_rules": [],
        "partial_name_rules": [],
        "partial_name_identity_rules": [
            {
                "old_key": "acevedo luis",
                "new_name": "Acevedo, Luis Alberto",
                "new_key": "acevedo luis alberto",
                "birth_year": "1969",
                "club_key": "",
                "gender": "male",
            }
        ],
        "comma_order_rules": [],
    }

    curated, counts = curate.apply_athlete_curations_to_df(df, "athlete", rules)

    assert curated.loc[0, "full_name"] == "Acevedo, Luis Alberto"
    assert curated.loc[0, "birth_year"] == "1969"
    assert counts == {
        "space_order_name_canonicalizations": 1,
        "partial_name_missing_birth_year_consolidations": 1,
    }


def test_apply_athlete_curations_to_df_repairs_rule_outputs():
    df = pd.DataFrame(
        [
            {
                "full_name": "Barahona, Manuel",
                "club_name": "Pe\u00f1alolen Master",
                "gender": "male",
                "birth_year": "1972",
            }
        ]
    )
    rules = {
        "ocr_name_rules": [
            {
                "old_key": "barahona manuel",
                "new_name": "Barahona Ligu\u00fce\u00f1o, Manuel",
                "new_key": "barahona ligueno manuel",
                "birth_year": "1972",
                "club_key": "penalolen master",
                "gender": "male",
            }
        ],
        "birth_year_rules": {},
        "missing_birth_year_rules": [],
        "partial_name_rules": [],
    }

    curated, counts = curate.apply_athlete_curations_to_df(df, "athlete", rules)

    assert curated.loc[0, "full_name"] == "Barahona Ligue\u00f1o, Manuel"
    assert counts == {"ocr_name_replacements": 1, "known_ocr_name_residue_repairs": 1}


def test_materialize_document_inputs_writes_curated_copy_and_manifest_document():
    tmp_dir = _workspace_tmp_dir()
    try:
        input_dir = tmp_dir / "results_csv" / "fchmn_auto" / "2024" / "sample"
        input_dir.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "full_name": "Acevedo, Luis A",
                    "gender": "male",
                    "club_name": "Natacion Master Recoleta",
                    "birth_year": "1969",
                    "source_id": "1",
                }
            ]
        ).to_csv(input_dir / "athlete.csv", index=False)
        pd.DataFrame(
            [
                {
                    "event_name": "50 Free",
                    "athlete_name": "Acevedo, Luis A",
                    "club_name": "Natacion Master Recoleta",
                    "rank_position": "1",
                    "seed_time_text": "",
                    "seed_time_ms": "",
                    "result_time_text": "30.00",
                    "result_time_ms": "30000",
                    "age_at_event": "55",
                    "birth_year_estimated": "1969",
                    "points": "",
                    "status": "valid",
                    "source_id": "1",
                }
            ]
        ).to_csv(input_dir / "result.csv", index=False)
        pd.DataFrame([{"name": "Natacion Master Recoleta"}]).to_csv(input_dir / "club.csv", index=False)
        pd.DataFrame([{"event_name": "50 Free"}]).to_csv(input_dir / "event.csv", index=False)
        (input_dir / "metadata.json").write_text('{"parser_version":"test"}\n', encoding="utf-8")

        rules = {
            "ocr_name_rules": [],
            "birth_year_rules": {},
            "missing_birth_year_rules": [],
            "partial_name_rules": [
                {
                    "old_key": "acevedo luis a",
                    "new_name": "Acevedo, Luis Alberto",
                    "new_key": "acevedo luis alberto",
                    "birth_year": "1969",
                    "club_key": "natacion master recoleta",
                    "gender": "male",
                }
            ],
        }
        document = {"source_url": "https://example.test/a.pdf", "pdf": "source.pdf", "input_dir": str(input_dir)}

        output_document, counts = curate.materialize_document_inputs(
            document,
            input_dir,
            tmp_dir / "curated",
            rules,
        )

        output_dir = Path(output_document["input_dir"])
        athlete_df = pd.read_csv(output_dir / "athlete.csv", dtype=str)
        result_df = pd.read_csv(output_dir / "result.csv", dtype=str)
        metadata = (output_dir / "metadata.json").read_text(encoding="utf-8")

        assert athlete_df.loc[0, "full_name"] == "Acevedo, Luis Alberto"
        assert result_df.loc[0, "athlete_name"] == "Acevedo, Luis Alberto"
        assert counts["athlete_partial_name_consolidations"] == 1
        assert counts["result_partial_name_consolidations"] == 1
        assert "pdf" not in output_document
        assert '"athlete_materialized": true' in metadata
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_load_materialization_rules_accepts_multiple_partial_decision_files():
    tmp_dir = _workspace_tmp_dir()
    try:
        first = tmp_dir / "first.csv"
        second = tmp_dir / "second.csv"
        first.write_text(
            "decision;suggested_canonical_full_name;gender;birth_year;club_key;shorter_full_name;longer_full_name\n"
            "merge;Acevedo, Luis Alberto;male;1969;club a;Acevedo, Luis A;Acevedo, Luis Alberto\n",
            encoding="utf-8",
        )
        second.write_text(
            "decision;suggested_canonical_full_name;gender;birth_year;club_key;shorter_full_name;longer_full_name\n"
            "merge;Garay Carrasco, Victor;male;1963;club b;Garay C, Victor;Garay Carrasco, Victor\n",
            encoding="utf-8",
        )

        class Args:
            birth_year_evidence_csv = None
            missing_birth_year_consolidation_csv = None
            partial_name_decisions_csv = [str(first), str(second)]

        rules = curate.load_materialization_rules(Args(), {})

        assert [row["new_name"] for row in rules["partial_name_rules"]] == [
            "Acevedo, Luis Alberto",
            "Garay Carrasco, Victor",
        ]
        assert rules["ocr_name_rules"] == []
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
def test_reviewed_relay_line_correction_replaces_all_extracted_members():
    import pandas as pd

    relay_df = pd.DataFrame(
        [
            {
                "event_name": "mixed 120-159 4x50 LC Meter medley_relay",
                "relay_team_name": "Formativo Nautico B",
                "leg_order": "1",
                "swimmer_name": "Apolo Gaibor, Ramiro Andres",
                "gender": "male",
                "age_at_event": "29",
                "birth_year_estimated": "1995",
                "page_number": "46",
                "line_number": "57",
            },
            {
                "event_name": "mixed 120-159 4x50 LC Meter medley_relay",
                "relay_team_name": "Formativo Nautico B",
                "leg_order": "3",
                "swimmer_name": "3Arguello Almeida, Andrea Alexan4d)rCaa Wde3n1a Escobar, Mery Fernanda",
                "gender": "female",
                "age_at_event": "66",
                "birth_year_estimated": "1958",
                "page_number": "46",
                "line_number": "57",
            },
        ]
    )
    corrections = [
        {
            "source_url": "https://example.test/buenos-aires.pdf",
            "page_number": "46",
            "line_number": "57",
            "leg_order": str(leg),
            "swimmer_name": name,
            "gender": gender,
            "age_at_event": str(age),
        }
        for leg, name, gender, age in [
            (1, "Apolo Gaibor, Ramiro Andres", "male", 29),
            (2, "Estrella Cadena, José Fernando", "male", 33),
            (3, "Arguello Almeida, Andrea Alexandra", "female", 31),
            (4, "Cadena Escobar, Mery Fernanda", "female", 66),
        ]
    ]

    corrected, count = curate.apply_relay_swimmer_line_corrections(
        relay_df,
        "https://example.test/buenos-aires.pdf",
        corrections,
        competition_year=2024,
    )

    assert count == 1
    assert corrected["leg_order"].astype(str).tolist() == ["1", "2", "3", "4"]
    assert corrected["swimmer_name"].tolist()[-1] == "Cadena Escobar, Mery Fernanda"
    assert corrected["birth_year_estimated"].astype(str).tolist() == ["1995", "1991", "1993", "1958"]


def test_reviewed_relay_corrections_reference_preserves_unicode_names():
    corrections_path = BACKEND_DIR / "data" / "reference" / "suda_relay_swimmer_corrections.csv"
    rows = curate.read_dict_rows(corrections_path)
    names = {row["swimmer_name"] for row in rows}

    assert len(rows) == 64
    assert all("?" not in name for name in names)
    assert {
        "Simbaña Escobar, Maria José",
        "Castillejo Rivero, Víctor Leopoldo",
        "Manrique Carreño, Luis Cristobal",
        "Estrella Cadena, José Fernando",
        "Saca Tejada, José",
    } <= names
