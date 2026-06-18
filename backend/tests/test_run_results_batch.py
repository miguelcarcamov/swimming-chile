import sys
from argparse import Namespace
import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "batch_runner"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_results_batch as batch


def test_validate_input_dir_returns_validated_for_minimal_parser_output():
    result = batch.validate_input_dir(FIXTURES_DIR / "valid")

    assert result.state == "validated"
    assert result.counts["event"] == 1
    assert result.counts["result"] == 1
    assert result.issues == []
    assert result.commands == {}


def test_validate_input_dir_requires_review_when_required_csv_is_missing():
    result = batch.validate_input_dir(FIXTURES_DIR / "missing_result")

    assert result.state == "requires_review"
    assert {issue.issue_key for issue in result.issues} >= {"missing_result_csv", "no_results_found"}


def test_validate_input_dir_requires_review_for_invalid_canon():
    result = batch.validate_input_dir(FIXTURES_DIR / "invalid_canon")

    assert result.state == "requires_review"
    assert any(issue.issue_key == "invalid_event_stroke" for issue in result.issues)


def test_validate_input_dir_requires_review_when_debug_ratio_is_high():
    result = batch.validate_input_dir(FIXTURES_DIR / "high_debug", debug_threshold=0.20)

    assert result.state == "requires_review"
    assert any(issue.issue_key == "debug_unparsed_ratio_exceeded" for issue in result.issues)


def test_validate_input_dir_requires_review_for_unparsed_relay_event_header():
    input_dir = BACKEND_DIR / "data" / "staging" / "csv" / f"test_unparsed_relay_header_{uuid.uuid4().hex}"
    try:
        shutil.copytree(FIXTURES_DIR / "valid", input_dir)
        (input_dir / "debug_unparsed_lines.csv").write_text(
            "page_number,line_number,event_name_context,raw_line,reason\n"
            '15,3,men 75-79 50 SC Meter butterfly,"Event 10 Women 400 SC Meter Freestyle Relay 240 a 279",unparsed_inside_event\n',
            encoding="utf-8",
        )

        result = batch.validate_input_dir(input_dir)
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)

    assert result.state == "requires_review"
    assert result.counts["debug_unparsed_relay_event_headers"] == 1
    assert any(issue.issue_key == "unparsed_relay_event_headers" for issue in result.issues)


def test_validate_input_dir_requires_review_for_athlete_name_residues():
    input_dir = BACKEND_DIR / "data" / "staging" / "csv" / f"test_name_quality_{uuid.uuid4().hex}"
    try:
        shutil.copytree(FIXTURES_DIR / "valid", input_dir)
        (input_dir / "athlete.csv").write_text(
            "full_name,gender,club_name,birth_year,source_id\n"
            '"Cofreá, Patricio",male,Club A,1980,1\n'
            '"Briceñ ño, Dañiel",male,Club A,1981,1\n'
            "Nombre Apellido,male,Club A,1982,1\n",
            encoding="utf-8",
        )
        (input_dir / "result.csv").write_text(
            "event_name,athlete_name,club_name,rank_position,seed_time_text,seed_time_ms,result_time_text,result_time_ms,age_at_event,birth_year_estimated,points,status,source_id\n"
            'men 35-39 100 LC Meter freestyle,"Yañ ñez, Roberto",Club A,1,1:05.30,65300,1:03.21,63210,35,1991,9,valid,1\n',
            encoding="utf-8",
        )

        result = batch.validate_input_dir(input_dir)
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)

    assert result.state == "requires_review"
    issue_keys = {issue.issue_key for issue in result.issues}
    assert "athlete_vowel_plus_accented_vowel" in issue_keys
    assert "athlete_split_enye" in issue_keys
    assert "athlete_name_without_comma" in issue_keys
    assert "result_split_enye" in issue_keys


def test_validate_input_dir_requires_review_for_implausibly_short_valid_times():
    input_dir = BACKEND_DIR / "data" / "staging" / "csv" / f"test_time_quality_{uuid.uuid4().hex}"
    try:
        shutil.copytree(FIXTURES_DIR / "valid", input_dir)
        (input_dir / "result.csv").write_text(
            "event_name,athlete_name,club_name,rank_position,seed_time_text,seed_time_ms,result_time_text,result_time_ms,age_at_event,birth_year_estimated,points,status,source_id\n"
            'men 35-39 100 LC Meter freestyle,Juan Perez,Club A,8,,,"1,00",1000,35,1991,,valid,1\n',
            encoding="utf-8",
        )

        result = batch.validate_input_dir(input_dir)
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)

    assert result.state == "requires_review"
    assert any(issue.issue_key == "result_implausibly_short_result_time" for issue in result.issues)


def test_validate_input_dir_requires_review_for_implausibly_short_relay_times():
    input_dir = BACKEND_DIR / "data" / "staging" / "csv" / f"test_relay_time_quality_{uuid.uuid4().hex}"
    try:
        shutil.copytree(FIXTURES_DIR / "valid", input_dir)
        (input_dir / "relay_team.csv").write_text(
            "event_name,relay_team_name,rank_position,seed_time_text,seed_time_ms,result_time_text,result_time_ms,points,status,source_id,page_number,line_number\n"
            'mixed 120-159 200 SC Meter freestyle_relay,Club A,1,"2:00,32",120320,"18,00",18000,,valid,1,1,15\n',
            encoding="utf-8",
        )

        result = batch.validate_input_dir(input_dir)
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)

    assert result.state == "requires_review"
    assert any(issue.issue_key == "relay_team_implausibly_short_result_time" for issue in result.issues)


def test_validate_input_dir_requires_review_for_duplicate_relay_rows():
    input_dir = BACKEND_DIR / "data" / "staging" / "csv" / f"test_relay_duplicates_{uuid.uuid4().hex}"
    try:
        shutil.copytree(FIXTURES_DIR / "valid", input_dir)
        (input_dir / "relay_team.csv").write_text(
            "event_name,relay_team_name,rank_position,seed_time_text,seed_time_ms,result_time_text,result_time_ms,points,status,source_id,page_number,line_number\n"
            'mixed 120-159 200 SC Meter freestyle_relay,Club A,1,,,"2:00,32",120320,"18",valid,1,24,7\n'
            'mixed 120-159 200 SC Meter freestyle_relay,Club A,1,,,"2:00,32",120320,"18",valid,1,27,7\n',
            encoding="utf-8",
        )
        (input_dir / "relay_swimmer.csv").write_text(
            "event_name,relay_team_name,leg_order,swimmer_name,gender,age_at_event,birth_year_estimated,page_number,line_number\n"
            'mixed 120-159 200 SC Meter freestyle_relay,Club A,1,"Meza, Valentina",female,28,1997,24,8\n'
            'mixed 120-159 200 SC Meter freestyle_relay,Club A,1,"Meza, Valentina",female,28,1997,27,8\n',
            encoding="utf-8",
        )

        result = batch.validate_input_dir(input_dir)
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)

    issue_keys = {issue.issue_key for issue in result.issues}
    assert result.state == "requires_review"
    assert "relay_team_duplicate_rows" in issue_keys
    assert "relay_swimmer_duplicate_rows" in issue_keys


def test_validate_input_dir_requires_review_for_invalid_relay_leg_order():
    input_dir = BACKEND_DIR / "data" / "staging" / "csv" / f"test_relay_leg_order_{uuid.uuid4().hex}"
    try:
        shutil.copytree(FIXTURES_DIR / "valid", input_dir)
        (input_dir / "relay_swimmer.csv").write_text(
            "event_name,relay_team_name,leg_order,swimmer_name,gender,age_at_event,birth_year_estimated,page_number,line_number\n"
            'mixed 120-159 200 SC Meter freestyle_relay,Club A,5,"Sturion, Carla Stein",female,,,125,7\n',
            encoding="utf-8",
        )

        result = batch.validate_input_dir(input_dir)
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)

    assert result.state == "requires_review"
    assert any(issue.issue_key == "invalid_relay_swimmer_leg_order" for issue in result.issues)


def test_validate_input_dir_requires_review_for_known_adaip_line_wrap_residue():
    input_dir = BACKEND_DIR / "data" / "staging" / "csv" / f"test_adaip_line_wrap_{uuid.uuid4().hex}"
    try:
        shutil.copytree(FIXTURES_DIR / "valid", input_dir)
        (input_dir / "relay_team.csv").write_text(
            "event_name,club_name,relay_team_name,rank_position,seed_time_text,seed_time_ms,result_time_text,result_time_ms,points,status,source_id,page_number,line_number\n"
            'men 120+ 4x50 SC Meter freestyle_relay,INTERIORADAIP,ASSOCIAÇÃO DE DESPORTOS AQUÁTICOS DO,6,,,"1:52,04",112040,"0,00",valid,1,147,73\n',
            encoding="utf-8",
        )

        result = batch.validate_input_dir(input_dir)
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)

    assert result.state == "requires_review"
    assert any(issue.issue_key == "relay_team_known_line_wrap_residue" for issue in result.issues)


def test_validate_input_dir_requires_review_for_identity_boundary_residue():
    input_dir = BACKEND_DIR / "data" / "staging" / "csv" / f"test_identity_boundary_{uuid.uuid4().hex}"
    try:
        shutil.copytree(FIXTURES_DIR / "valid", input_dir)
        (input_dir / "athlete.csv").write_text(
            "full_name,gender,club_name,birth_year,source_id\n"
            '"MELO, MARINA PALMEIRA SOBRAL AZEVEDO (ACQUA R1FEAP",female,- PARAIBA MASTER,,1\n',
            encoding="utf-8",
        )
        (input_dir / "result.csv").write_text(
            "event_name,athlete_name,club_name,rank_position,seed_time_text,seed_time_ms,result_time_text,result_time_ms,age_at_event,birth_year_estimated,points,status,source_id\n"
            'women 70+ 400 SC Meter individual_medley,"MELO, MARINA PALMEIRA SOBRAL AZEVEDO (ACQUA R1FEAP",- PARAIBA MASTER,1,,,"8:10,74",490740,,,"0,00",valid,1\n',
            encoding="utf-8",
        )

        result = batch.validate_input_dir(input_dir)
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)

    issue_keys = {issue.issue_key for issue in result.issues}
    assert result.state == "requires_review"
    assert "athlete_athlete_boundary_residue" in issue_keys
    assert "athlete_club_boundary_residue" in issue_keys
    assert "result_identity_boundary_residue" in issue_keys


def test_validate_input_dir_requires_review_for_implausibly_short_seed_time():
    input_dir = BACKEND_DIR / "data" / "staging" / "csv" / f"test_seed_quality_{uuid.uuid4().hex}"
    try:
        shutil.copytree(FIXTURES_DIR / "valid", input_dir)
        (input_dir / "result.csv").write_text(
            "event_name,athlete_name,club_name,rank_position,seed_time_text,seed_time_ms,result_time_text,result_time_ms,age_at_event,birth_year_estimated,points,status,source_id\n"
            'men 35-39 100 LC Meter freestyle,Juan Perez,Club A,8,"23,00",23000,"1:03,21",63210,35,1991,,valid,1\n'
            'men 35-39 50 LC Meter freestyle,Juan Perez,Club A,8,"41,00",41000,"40,35",40350,35,1991,"39,90",valid,1\n',
            encoding="utf-8",
        )

        result = batch.validate_input_dir(input_dir)
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)

    issue_keys = {issue.issue_key for issue in result.issues}
    assert result.state == "requires_review"
    assert "result_implausibly_short_seed_time" in issue_keys
    assert "result_time_like_points" not in issue_keys


def test_validate_input_dir_requires_review_for_event_age_and_gender_mismatch():
    input_dir = BACKEND_DIR / "data" / "staging" / "csv" / f"test_event_consistency_{uuid.uuid4().hex}"
    try:
        shutil.copytree(FIXTURES_DIR / "valid", input_dir)
        (input_dir / "athlete.csv").write_text(
            "full_name,gender,club_name,birth_year,source_id\n"
            '"Saldias, Alfredo",male,MSBDO,1989,1\n'
            '"Hernandez, Salvador",male,Team Pili Caviedes,1991,1\n',
            encoding="utf-8",
        )
        (input_dir / "result.csv").write_text(
            "event_name,athlete_name,club_name,rank_position,seed_time_text,seed_time_ms,result_time_text,result_time_ms,age_at_event,birth_year_estimated,points,status,source_id\n"
            '"men 55-59 100 SC Meter individual_medley","Saldias, Alfredo",MSBDO,14,,,"35,84",35840,34,1989,,valid,1\n'
            '"women 30-34 100 LC Meter freestyle","Hernandez, Salvador",Team Pili Caviedes,5,"1:17,00",77000,"1:19,32",79320,34,1991,,valid,1\n',
            encoding="utf-8",
        )

        result = batch.validate_input_dir(input_dir)
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)

    issue_keys = {issue.issue_key for issue in result.issues}
    assert result.state == "requires_review"
    assert "result_event_age_mismatch" in issue_keys
    assert "result_event_gender_mismatch" in issue_keys


def test_validate_input_dir_requires_review_for_impossible_points():
    input_dir = BACKEND_DIR / "data" / "staging" / "csv" / f"test_points_quality_{uuid.uuid4().hex}"
    try:
        shutil.copytree(FIXTURES_DIR / "valid", input_dir)
        (input_dir / "result.csv").write_text(
            "event_name,athlete_name,club_name,rank_position,seed_time_text,seed_time_ms,result_time_text,result_time_ms,age_at_event,birth_year_estimated,points,status,source_id\n"
            'men 35-39 50 LC Meter freestyle,Juan Perez,Club A,,"41,00",41000,DQ,,35,1991,"39,90",dsq,1\n'
            'men 35-39 50 LC Meter freestyle,Pedro Perez,Club A,1,"41,00",41000,"40,35",40350,35,1991,"9",valid,1\n',
            encoding="utf-8",
        )

        result = batch.validate_input_dir(input_dir)
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)

    issue_keys = {issue.issue_key for issue in result.issues}
    assert result.state == "requires_review"
    assert "result_points_without_rank" in issue_keys
    assert "result_points_over_max" in issue_keys


def test_build_parse_command_uses_current_python_and_parser_args():
    args = Namespace(
        pdf="backend/data/raw/results_pdf/demo.pdf",
        out_dir="backend/data/raw/results_csv/demo",
        competition_id=42,
        default_source_id=7,
        excel_name="parsed_demo.xlsx",
    )

    command = batch.build_parse_command(args)

    assert command[0] == sys.executable
    assert command[1].endswith("parse_results_pdf.py")
    assert command[2:] == [
        "--pdf",
        str(Path(args.pdf)),
        "--out-dir",
        str(Path(args.out_dir)),
        "--default-source-id",
        "7",
        "--excel-name",
        "parsed_demo.xlsx",
        "--competition-id",
        "42",
    ]


def test_build_load_command_uses_pipeline_args():
    args = Namespace(
        host="localhost",
        port=5432,
        dbname="natacion_chile",
        user="postgres",
        password="secret",
        schema="core",
        default_source_id=7,
        competition_id=42,
        source_url=None,
        truncate_staging=True,
    )

    command = batch.build_load_command(args, Path("backend/data/raw/results_csv/demo"))

    assert command[0] == sys.executable
    assert command[1].endswith("run_pipeline_results.py")
    assert command[2:] == [
        "--input-dir",
        str(Path("backend/data/raw/results_csv/demo")),
        "--host",
        "localhost",
        "--port",
        "5432",
        "--dbname",
        "natacion_chile",
        "--user",
        "postgres",
        "--password",
        "secret",
        "--schema",
        "core",
        "--default-source-id",
        "7",
        "--competition-id",
        "42",
        "--truncate-staging",
    ]


def test_build_load_command_passes_source_url_to_pipeline_when_available():
    args = Namespace(
        host="localhost",
        port=5432,
        dbname="natacion_chile",
        user="postgres",
        password="secret",
        schema="core",
        default_source_id=7,
        competition_id=42,
        source_url="https://fchmn.cl/wp-content/uploads/2026/03/resultados-demo.pdf",
        competition_scope="fchmn_local",
        governing_body_code="fchmn",
        governing_body_name="FCHMN",
        truncate_staging=False,
    )

    command = batch.build_load_command(args, Path("backend/data/raw/results_csv/demo"))

    assert command[-8:] == [
        "--competition-source-url",
        "https://fchmn.cl/wp-content/uploads/2026/03/resultados-demo.pdf",
        "--competition-scope",
        "fchmn_local",
        "--governing-body-code",
        "fchmn",
        "--governing-body-name",
        "FCHMN",
    ]


def test_build_load_command_forwards_source_revision_override():
    args = Namespace(
        host="localhost",
        port=5432,
        dbname="natacion_chile",
        user="postgres",
        password="secret",
        schema="core",
        default_source_id=7,
        competition_id=42,
        source_url=None,
        competition_scope="fchmn_local",
        truncate_staging=False,
        allow_competition_source_revision=True,
    )

    command = batch.build_load_command(args, Path("backend/data/raw/results_csv/demo"))

    assert "--allow-competition-source-revision" in command


def test_redact_command_hides_password_value():
    command = ["python", "script.py", "--user", "postgres", "--password", "secret", "--schema", "core"]

    assert batch.redact_command(command) == [
        "python",
        "script.py",
        "--user",
        "postgres",
        "--password",
        "***",
        "--schema",
        "core",
    ]


def test_main_does_not_load_when_batch_requires_review(monkeypatch):
    called = {"load": False}

    def fake_run_pipeline(args, input_dir):
        called["load"] = True

    monkeypatch.setattr(batch, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_results_batch.py",
            "--input-dir",
            str(FIXTURES_DIR / "missing_result"),
            "--load",
            "--user",
            "postgres",
            "--password",
            "secret",
            "--competition-scope",
            "fchmn_local",
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        batch.main()

    assert excinfo.value.code == 1
    assert called["load"] is False


def test_main_loads_only_after_validated_batch(monkeypatch):
    called = {"load": False}

    def fake_run_pipeline(args, input_dir):
        called["load"] = True

    monkeypatch.setattr(batch, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_results_batch.py",
            "--input-dir",
            str(FIXTURES_DIR / "valid"),
            "--load",
            "--user",
            "postgres",
            "--password",
            "secret",
            "--competition-scope",
            "fchmn_local",
        ],
    )

    batch.main()

    assert called["load"] is True


def test_main_does_not_load_without_required_competition_scope(monkeypatch):
    called = {"load": False}

    def fake_run_pipeline(args, input_dir):
        called["load"] = True

    monkeypatch.setattr(batch, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_results_batch.py",
            "--input-dir",
            str(FIXTURES_DIR / "valid"),
            "--load",
            "--user",
            "postgres",
            "--password",
            "secret",
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        batch.main()

    assert excinfo.value.code == 1
    assert called["load"] is False


def test_process_manifest_uses_competition_scope_per_document_for_load(monkeypatch):
    manifest_path = BACKEND_DIR / "data" / "staging" / "csv" / "test_batch_scope_manifest.jsonl"
    manifest_path.write_text(
        "\n".join(
            [
                json.dumps({"input_dir": "backend/tests/fixtures/batch_runner/valid", "competition_scope": "fchmn_local"}),
                json.dumps({"input_dir": "backend/tests/fixtures/batch_runner/valid", "competition_scope": "international"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    loaded = []

    def fake_run_pipeline(args, input_dir):
        loaded.append(str(input_dir))

    monkeypatch.setattr(batch, "run_pipeline", fake_run_pipeline)
    args = Namespace(
        manifest=str(manifest_path),
        input_dir=None,
        pdf=None,
        out_dir=None,
        competition_id=None,
        source_url=None,
        competition_scope=None,
        required_competition_scope="fchmn_local",
        default_source_id=1,
        excel_name="parsed_results.xlsx",
        load=True,
        host="localhost",
        port=5432,
        dbname="natacion_chile",
        user="postgres",
        password="secret",
        schema="core",
        truncate_staging=False,
        debug_threshold=0.20,
    )

    try:
        result = batch.process_manifest(args)
    finally:
        manifest_path.unlink(missing_ok=True)

    assert result.state == "requires_review"
    assert result.state_counts == {"loaded": 1, "requires_review": 1}
    assert loaded == [str(BACKEND_DIR.parent / "backend/tests/fixtures/batch_runner/valid")]
    assert result.documents[1].issues[-1].issue_key == "competition_scope_not_allowed"


def test_main_writes_summary_json_with_redacted_load_command(monkeypatch):
    summary_path = BACKEND_DIR / "data" / "staging" / "csv" / "test_batch_summary.json"
    summary_path.unlink(missing_ok=True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_results_batch.py",
            "--input-dir",
            str(FIXTURES_DIR / "missing_result"),
            "--load",
            "--user",
            "postgres",
            "--password",
            "secret",
            "--summary-json",
            str(summary_path),
        ],
    )

    with pytest.raises(SystemExit):
        try:
            batch.main()
        finally:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            summary_path.unlink(missing_ok=True)

    assert payload["state"] == "requires_review"
    assert payload["commands"]["parse"] is None
    assert "--password" in payload["commands"]["load"]
    assert "secret" not in payload["commands"]["load"]
    assert "***" in payload["commands"]["load"]


def test_process_manifest_continues_across_valid_and_review_documents():
    args = Namespace(
        manifest=str(FIXTURES_DIR / "manifest_input_dirs.jsonl"),
        input_dir=None,
        pdf=None,
        out_dir=None,
        competition_id=None,
        source_url=None,
        default_source_id=1,
        excel_name="parsed_results.xlsx",
        load=False,
        host="localhost",
        port=5432,
        dbname="natacion_chile",
        user=None,
        password=None,
        schema="core",
        truncate_staging=False,
        debug_threshold=0.20,
    )

    result = batch.process_manifest(args)

    assert result.state == "requires_review"
    assert result.state_counts == {"validated": 1, "requires_review": 1}
    assert [document.state for document in result.documents] == ["validated", "requires_review"]


def test_process_manifest_fails_when_manifest_has_no_documents():
    manifest_path = BACKEND_DIR / "data" / "staging" / "csv" / "test_batch_empty_manifest.jsonl"
    manifest_path.write_text("\n# no documents\n", encoding="utf-8")
    args = Namespace(
        manifest=str(manifest_path),
        input_dir=None,
        pdf=None,
        out_dir=None,
        competition_id=None,
        source_url=None,
        default_source_id=1,
        excel_name="parsed_results.xlsx",
        load=False,
        host="localhost",
        port=5432,
        dbname="natacion_chile",
        user=None,
        password=None,
        schema="core",
        truncate_staging=False,
        debug_threshold=0.20,
    )

    try:
        result = batch.process_manifest(args)
    finally:
        manifest_path.unlink(missing_ok=True)

    assert result.state == "failed"
    assert result.state_counts == {}
    assert result.documents == []


def test_process_manifest_supports_pdf_entries_without_cross_document_contamination(monkeypatch):
    parsed = []

    def fake_run_parser(args):
        parsed.append(
            {
                "pdf": args.pdf,
                "out_dir": args.out_dir,
                "competition_id": args.competition_id,
                "default_source_id": args.default_source_id,
            }
        )
        return Path(args.out_dir)

    monkeypatch.setattr(batch, "run_parser", fake_run_parser)
    args = Namespace(
        manifest=str(FIXTURES_DIR / "manifest_pdfs.jsonl"),
        input_dir=None,
        pdf=None,
        out_dir=None,
        competition_id=None,
        source_url=None,
        default_source_id=1,
        excel_name="parsed_results.xlsx",
        load=False,
        host="localhost",
        port=5432,
        dbname="natacion_chile",
        user=None,
        password=None,
        schema="core",
        truncate_staging=False,
        debug_threshold=0.20,
    )

    result = batch.process_manifest(args)

    assert result.state == "requires_review"
    assert result.state_counts == {"validated": 1, "requires_review": 1}
    assert [document.state for document in result.documents] == ["validated", "requires_review"]
    assert [document.input_dir for document in result.documents] == [
        str(BACKEND_DIR.parent / "backend/tests/fixtures/batch_runner/valid"),
        str(BACKEND_DIR.parent / "backend/tests/fixtures/batch_runner/missing_result"),
    ]
    assert parsed == [
        {
            "pdf": str(BACKEND_DIR.parent / "backend/tests/fixtures/batch_runner/pdf_inputs/fixture_a.pdf"),
            "out_dir": str(BACKEND_DIR.parent / "backend/tests/fixtures/batch_runner/valid"),
            "competition_id": 42,
            "default_source_id": 7,
        },
        {
            "pdf": str(BACKEND_DIR.parent / "backend/tests/fixtures/batch_runner/pdf_inputs/fixture_b.pdf"),
            "out_dir": str(BACKEND_DIR.parent / "backend/tests/fixtures/batch_runner/missing_result"),
            "competition_id": 43,
            "default_source_id": 1,
        },
    ]
    assert result.documents[0].commands["parse"] is not None
    assert result.documents[1].commands["parse"] is not None


def test_process_manifest_preserves_source_url_per_document():
    manifest_path = BACKEND_DIR / "data" / "staging" / "csv" / "test_batch_source_url_manifest.jsonl"
    source_url = "https://fchmn.cl/wp-content/uploads/2026/03/resultados-demo.pdf"
    manifest_path.write_text(
        json.dumps({"input_dir": "backend/tests/fixtures/batch_runner/valid", "source_url": source_url}) + "\n",
        encoding="utf-8",
    )
    args = Namespace(
        manifest=str(manifest_path),
        input_dir=None,
        pdf=None,
        out_dir=None,
        competition_id=None,
        source_url=None,
        default_source_id=1,
        excel_name="parsed_results.xlsx",
        load=False,
        host="localhost",
        port=5432,
        dbname="natacion_chile",
        user=None,
        password=None,
        schema="core",
        truncate_staging=False,
        debug_threshold=0.20,
    )

    try:
        result = batch.process_manifest(args)
    finally:
        manifest_path.unlink(missing_ok=True)

    assert result.state == "validated"
    assert result.state_counts == {"validated": 1}
    assert result.documents[0].source_url == source_url


def test_process_manifest_marks_parser_failure_without_stopping_other_documents(monkeypatch):
    manifest_path = BACKEND_DIR / "data" / "staging" / "csv" / "test_batch_parser_failure_manifest.jsonl"
    manifest_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "pdf": "backend/tests/fixtures/batch_runner/pdf_inputs/broken.pdf",
                        "out_dir": "backend/tests/fixtures/batch_runner/missing_result",
                    }
                ),
                json.dumps({"input_dir": "backend/tests/fixtures/batch_runner/valid"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_run_parser(args):
        raise subprocess.CalledProcessError(1, ["parse_results_pdf.py"])

    monkeypatch.setattr(batch, "run_parser", fake_run_parser)
    args = Namespace(
        manifest=str(manifest_path),
        input_dir=None,
        pdf=None,
        out_dir=None,
        competition_id=None,
        source_url=None,
        default_source_id=1,
        excel_name="parsed_results.xlsx",
        load=False,
        host="localhost",
        port=5432,
        dbname="natacion_chile",
        user=None,
        password=None,
        schema="core",
        truncate_staging=False,
        debug_threshold=0.20,
    )

    try:
        result = batch.process_manifest(args)
    finally:
        manifest_path.unlink(missing_ok=True)

    assert result.state == "failed"
    assert result.state_counts == {"failed": 1, "validated": 1}
    assert [document.state for document in result.documents] == ["failed", "validated"]
    assert result.documents[0].issues[0].issue_key == "parser_failed"


def test_read_manifest_entries_accepts_utf8_bom():
    manifest_path = BACKEND_DIR / "data" / "staging" / "csv" / "test_batch_bom_manifest.jsonl"
    manifest_path.write_text(
        "\ufeff" + json.dumps({"input_dir": "backend/tests/fixtures/batch_runner/valid"}) + "\n",
        encoding="utf-8",
    )

    try:
        entries = batch.read_manifest_entries(manifest_path)
    finally:
        manifest_path.unlink(missing_ok=True)

    assert entries == [{"input_dir": "backend/tests/fixtures/batch_runner/valid"}]


def test_main_writes_manifest_summary_json(monkeypatch):
    summary_path = BACKEND_DIR / "data" / "staging" / "csv" / "test_manifest_summary.json"
    summary_path.unlink(missing_ok=True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_results_batch.py",
            "--manifest",
            str(FIXTURES_DIR / "manifest_input_dirs.jsonl"),
            "--summary-json",
            str(summary_path),
        ],
    )

    with pytest.raises(SystemExit):
        try:
            batch.main()
        finally:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            summary_path.unlink(missing_ok=True)

    assert payload["state"] == "requires_review"
    assert payload["state_counts"] == {"validated": 1, "requires_review": 1}
    assert len(payload["documents"]) == 2
    assert [document["state"] for document in payload["documents"]] == ["validated", "requires_review"]
