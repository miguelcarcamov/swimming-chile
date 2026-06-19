#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from natacion_chile.manifest import read_jsonl_manifest_entries
REQUIRED_PARSER_OUTPUTS = {
    "club": ["name", "short_name", "city", "region", "source_id"],
    "event": ["competition_id", "event_name", "stroke", "distance_m", "gender", "age_group", "round_type", "source_id"],
    "athlete": ["full_name", "gender", "club_name", "birth_year", "source_id"],
    "result": ["event_name", "athlete_name", "club_name", "rank_position", "seed_time_text", "seed_time_ms", "result_time_text", "result_time_ms", "age_at_event", "birth_year_estimated", "points", "status", "source_id"],
}

OPTIONAL_RELAY_OUTPUTS = {
    "relay_team": ["event_name", "relay_team_name", "rank_position", "seed_time_text", "seed_time_ms", "result_time_text", "result_time_ms", "points", "status", "source_id", "page_number", "line_number"],
    "relay_swimmer": ["event_name", "relay_team_name", "leg_order", "swimmer_name", "gender", "age_at_event", "birth_year_estimated", "page_number", "line_number"],
}

EVENT_GENDERS = {"women", "men", "mixed"}
ATHLETE_GENDERS = {"female", "male"}
STROKES = {
    "freestyle",
    "backstroke",
    "breaststroke",
    "butterfly",
    "individual_medley",
    "medley_relay",
    "freestyle_relay",
}
STATUSES = {"valid", "dns", "dnf", "dsq", "scratch", "unknown"}
VOWEL_PLUS_ACCENTED_VOWEL_RE = re.compile(r"[aeiouAEIOUáéíóúüÁÉÍÓÚÜ][áéíóúüÁÉÍÓÚÜ]")
SPLIT_ENYE_RE = re.compile(r"(?:ñ\s+ñ|n\s+ñ|ñ\s+n)", re.IGNORECASE)
EVENT_DISTANCE_RE = re.compile(r"\b(\d+)(?:x\d+)?\s+(?:LC|SC)\s+Meter\b", re.IGNORECASE)
UNPARSED_RELAY_EVENT_HEADER_RE = re.compile(
    r"^(?:Event|Evento)\s+\d+\b.*\b(?:Relay|Relevo)\b",
    re.IGNORECASE,
)
EVENT_AGE_GROUP_RE = re.compile(r"\b(?:women|men)\s+(\d{1,3})-(\d{1,3})\b", re.IGNORECASE)
ATHLETE_BOUNDARY_RESIDUE_RE = re.compile(r"[()]|(?:^|[\s,])-|-(?:$|[\s,])")
CLUB_LEADING_BOUNDARY_RESIDUE_RE = re.compile(r"^\s*[-(]")
CLUB_ALIAS_PATH = BACKEND_DIR / "data" / "reference" / "club_alias.csv"

DEFAULT_DEBUG_THRESHOLD = 0.20
DEFAULT_REQUIRED_COMPETITION_SCOPE = "fchmn_local"
MIN_VALID_RESULT_TIME_MS = 10000
MIN_VALID_RELAY_RESULT_TIME_MS = 25000
MAX_INDIVIDUAL_POINTS = 9.0
MAX_RELAY_POINTS = 18.0
PARSER_SCRIPT = BACKEND_DIR / "scripts" / "parse_results_pdf.py"
PIPELINE_SCRIPT = BACKEND_DIR / "scripts" / "run_pipeline_results.py"
PROJECT_DIR = BACKEND_DIR.parent


@dataclass
class BatchIssue:
    severity: str
    issue_key: str
    message: str
    count: int = 1


@dataclass
class BatchValidationResult:
    state: str
    input_dir: str
    source_url: str | None
    competition_scope: str | None
    governing_body_code: str | None
    governing_body_name: str | None
    counts: dict[str, int]
    issues: list[BatchIssue]
    metadata: dict[str, Any]
    commands: dict[str, list[str] | None]


@dataclass
class BatchManifestResult:
    state: str
    manifest_path: str
    state_counts: dict[str, int]
    documents: list[BatchValidationResult]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta parseo opcional, valida salidas y carga a core solo con --load."
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input-dir", help="Carpeta generada por parse_results_pdf.py")
    input_group.add_argument("--pdf", help="PDF de resultados a parsear antes de validar")
    input_group.add_argument("--manifest", help="Manifest JSONL con documentos a procesar uno a uno")
    parser.add_argument("--out-dir", help="Carpeta de salida requerida cuando se usa --pdf")
    parser.add_argument("--competition-id", type=int, help="competition_id que se pasara al parser")
    parser.add_argument("--source-url", help="URL original del documento para trazabilidad cuando exista.")
    parser.add_argument("--competition-scope", help="Ambito curado del documento; requerido para cargar a core.")
    parser.add_argument("--governing-body-code", help="Codigo snake_case del organismo deportivo rector, ej. fchmn o consada.")
    parser.add_argument("--governing-body-name", help="Nombre visible del organismo deportivo rector, ej. FCHMN o CONSADA.")
    parser.add_argument(
        "--required-competition-scope",
        default=DEFAULT_REQUIRED_COMPETITION_SCOPE,
        help="Ambito requerido para permitir --load. Por defecto: fchmn_local.",
    )
    parser.add_argument("--default-source-id", type=int, default=1, help="source_id por defecto que se pasara al parser")
    parser.add_argument("--excel-name", default="parsed_results.xlsx", help="Nombre del Excel consolidado que generara el parser")
    parser.add_argument("--load", action="store_true", help="Ejecuta run_pipeline_results.py solo si el batch queda validated.")
    parser.add_argument("--host", type=str, default="localhost", help="Host PostgreSQL para --load.")
    parser.add_argument("--port", type=int, default=5432, help="Puerto PostgreSQL para --load.")
    parser.add_argument("--dbname", type=str, default="natacion_chile", help="Base PostgreSQL para --load.")
    parser.add_argument("--user", type=str, help="Usuario PostgreSQL requerido para --load.")
    parser.add_argument("--password", type=str, help="Password PostgreSQL requerido para --load.")
    parser.add_argument("--schema", type=str, default="core", help="Schema PostgreSQL para --load.")
    parser.add_argument("--truncate-staging", action="store_true", help="Trunca staging durante --load.")
    parser.add_argument(
        "--allow-competition-source-revision",
        action="store_true",
        help="Permite cargar una fuente distinta para una competencia ya cargada. Usar solo con revisión explícita.",
    )
    parser.add_argument(
        "--debug-threshold",
        type=float,
        default=DEFAULT_DEBUG_THRESHOLD,
        help="Umbral maximo de debug_unparsed_lines sobre filas parseadas antes de requerir revision.",
    )
    parser.add_argument("--json", action="store_true", help="Imprime el resumen como JSON.")
    parser.add_argument("--summary-json", help="Ruta donde escribir un resumen auditable JSON de la corrida.")
    args = parser.parse_args()
    if args.pdf and not args.out_dir:
        parser.error("--out-dir es requerido cuando se usa --pdf")
    if args.load and (not args.user or not args.password):
        parser.error("--user y --password son requeridos cuando se usa --load")
    return args


def build_parse_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(PARSER_SCRIPT),
        "--pdf",
        str(Path(args.pdf)),
        "--out-dir",
        str(Path(args.out_dir)),
        "--default-source-id",
        str(args.default_source_id),
        "--excel-name",
        args.excel_name,
    ]
    if args.competition_id is not None:
        command.extend(["--competition-id", str(args.competition_id)])
    return command


def run_parser(args: argparse.Namespace) -> Path:
    pdf_path = Path(args.pdf)
    out_dir = Path(args.out_dir)
    if not pdf_path.exists() or not pdf_path.is_file():
        raise SystemExit(f"[ERROR] No existe el PDF: {pdf_path}")

    command = build_parse_command(args)
    subprocess.run(command, check=True)
    return out_dir


def read_manifest_entries(manifest_path: Path) -> list[dict[str, Any]]:
    return read_jsonl_manifest_entries(manifest_path)


def build_manifest_item_args(base_args: argparse.Namespace, entry: dict[str, Any]) -> argparse.Namespace:
    item = argparse.Namespace(**vars(base_args))
    item.manifest = None
    item.input_dir = resolve_manifest_path(entry.get("input_dir"))
    item.pdf = resolve_manifest_path(entry.get("pdf") or entry.get("pdf_path"))
    item.out_dir = resolve_manifest_path(entry.get("out_dir"))
    item.competition_id = entry.get("competition_id", base_args.competition_id)
    item.source_url = entry.get("source_url", getattr(base_args, "source_url", None))
    item.competition_scope = entry.get("competition_scope", getattr(base_args, "competition_scope", None))
    item.governing_body_code = entry.get("governing_body_code", getattr(base_args, "governing_body_code", None))
    item.governing_body_name = entry.get("governing_body_name", getattr(base_args, "governing_body_name", None))
    item.required_competition_scope = getattr(base_args, "required_competition_scope", DEFAULT_REQUIRED_COMPETITION_SCOPE)
    item.default_source_id = entry.get("default_source_id", base_args.default_source_id)
    item.excel_name = entry.get("excel_name", base_args.excel_name)

    has_input_dir = bool(item.input_dir)
    has_pdf = bool(item.pdf)
    if has_input_dir == has_pdf:
        raise SystemExit("[ERROR] Cada entrada del manifest debe tener exactamente uno de input_dir o pdf.")
    if has_pdf and not item.out_dir:
        raise SystemExit("[ERROR] Cada entrada con pdf debe incluir out_dir.")
    return item


def resolve_manifest_path(value: Any) -> str | None:
    if not value:
        return None
    path = Path(str(value))
    if path.is_absolute():
        return str(path)
    return str(PROJECT_DIR / path)


def build_load_command(args: argparse.Namespace, input_dir: Path) -> list[str]:
    command = [
        sys.executable,
        str(PIPELINE_SCRIPT),
        "--input-dir",
        str(input_dir),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--dbname",
        args.dbname,
        "--user",
        args.user,
        "--password",
        args.password,
        "--schema",
        args.schema,
        "--default-source-id",
        str(args.default_source_id),
    ]
    if args.competition_id is not None:
        command.extend(["--competition-id", str(args.competition_id)])
    if getattr(args, "source_url", None):
        command.extend(["--competition-source-url", str(args.source_url)])
    if getattr(args, "competition_scope", None):
        command.extend(["--competition-scope", str(args.competition_scope)])
    if getattr(args, "governing_body_code", None):
        command.extend(["--governing-body-code", str(args.governing_body_code)])
    if getattr(args, "governing_body_name", None):
        command.extend(["--governing-body-name", str(args.governing_body_name)])
    if args.truncate_staging:
        command.append("--truncate-staging")
    if getattr(args, "allow_competition_source_revision", False):
        command.append("--allow-competition-source-revision")
    return command


def redact_command(command: list[str]) -> list[str]:
    redacted = list(command)
    for index, token in enumerate(redacted[:-1]):
        if token == "--password":
            redacted[index + 1] = "***"
    return redacted


def run_pipeline(args: argparse.Namespace, input_dir: Path) -> None:
    command = build_load_command(args, input_dir)
    subprocess.run(command, check=True)


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def read_metadata(input_dir: Path, issues: list[BatchIssue]) -> dict[str, Any]:
    metadata_path = input_dir / "metadata.json"
    if not metadata_path.exists():
        issues.append(BatchIssue("error", "missing_metadata", "Falta metadata.json."))
        return {}
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(BatchIssue("error", "invalid_metadata_json", f"metadata.json no es JSON valido: {exc}."))
        return {}

    if metadata.get("pdf_name") and not metadata.get("pdf_sha256"):
        issues.append(BatchIssue("error", "missing_pdf_sha256", "metadata.json tiene pdf_name pero no pdf_sha256."))
    if metadata.get("pdf_sha256") and not isinstance(metadata["pdf_sha256"], str):
        issues.append(BatchIssue("error", "invalid_pdf_sha256", "pdf_sha256 debe ser texto hexadecimal."))
    if isinstance(metadata.get("pdf_sha256"), str) and len(metadata["pdf_sha256"]) != 64:
        issues.append(BatchIssue("error", "invalid_pdf_sha256", "pdf_sha256 debe tener 64 caracteres."))
    if metadata.get("pdf_name") and not metadata.get("parser_version"):
        issues.append(BatchIssue("error", "missing_parser_version", "metadata.json tiene pdf_name pero no parser_version."))
    return metadata


def add_missing_file_issues(input_dir: Path, issues: list[BatchIssue]) -> None:
    for key in REQUIRED_PARSER_OUTPUTS:
        if not (input_dir / f"{key}.csv").exists():
            issues.append(BatchIssue("error", f"missing_{key}_csv", f"Falta {key}.csv."))

    relay_team_exists = (input_dir / "relay_team.csv").exists()
    relay_swimmer_exists = (input_dir / "relay_swimmer.csv").exists()
    if relay_team_exists != relay_swimmer_exists:
        issues.append(
            BatchIssue(
                "error",
                "incomplete_relay_outputs",
                "Los relevos requieren relay_team.csv y relay_swimmer.csv juntos.",
            )
        )


def validate_columns(key: str, actual: list[str], expected: list[str], issues: list[BatchIssue]) -> None:
    missing = [col for col in expected if col not in actual]
    if missing:
        issues.append(BatchIssue("error", f"missing_{key}_columns", f"Faltan columnas en {key}.csv: {missing}.", len(missing)))


def count_invalid_values(rows: list[dict[str, str]], column: str, allowed: set[str]) -> int:
    invalid = 0
    for row in rows:
        value = (row.get(column) or "").strip()
        if value and value not in allowed:
            invalid += 1
    return invalid


def validate_canons(data: dict[str, list[dict[str, str]]], issues: list[BatchIssue]) -> None:
    checks = [
        ("event", "gender", EVENT_GENDERS),
        ("event", "stroke", STROKES),
        ("athlete", "gender", ATHLETE_GENDERS),
        ("result", "status", STATUSES),
        ("relay_team", "status", STATUSES),
        ("relay_swimmer", "gender", ATHLETE_GENDERS),
    ]
    for key, column, allowed in checks:
        rows = data.get(key, [])
        if not rows:
            continue
        invalid_count = count_invalid_values(rows, column, allowed)
        if invalid_count:
            issues.append(
                BatchIssue(
                    "error",
                    f"invalid_{key}_{column}",
                    f"{key}.csv tiene valores fuera de canon en {column}.",
                    invalid_count,
                )
            )


def validate_required_identities(data: dict[str, list[dict[str, str]]], issues: list[BatchIssue]) -> None:
    result_missing = sum(
        1
        for row in data.get("result", [])
        if not (row.get("event_name") or "").strip() or not (row.get("athlete_name") or "").strip()
    )
    if result_missing:
        issues.append(BatchIssue("error", "result_missing_identity", "Hay resultados sin event_name o athlete_name.", result_missing))

    relay_missing = sum(
        1
        for row in data.get("relay_team", [])
        if not (row.get("event_name") or "").strip() or not (row.get("relay_team_name") or "").strip()
    )
    if relay_missing:
        issues.append(BatchIssue("error", "relay_missing_identity", "Hay relevos sin event_name o relay_team_name.", relay_missing))


def validate_relay_swimmer_leg_order(data: dict[str, list[dict[str, str]]], issues: list[BatchIssue]) -> None:
    invalid = 0
    for row in data.get("relay_swimmer", []):
        leg_order = parse_int_or_none(row.get("leg_order"))
        # core.relay_result_member solo admite postas 1..4; detectarlo aca evita fallos tardios en PostgreSQL.
        if leg_order is None or leg_order < 1 or leg_order > 4:
            invalid += 1
    if invalid:
        issues.append(
            BatchIssue(
                "error",
                "invalid_relay_swimmer_leg_order",
                "relay_swimmer.csv tiene leg_order fuera del rango permitido 1..4.",
                invalid,
            )
        )


def has_vowel_plus_accented_vowel_residue(name: str) -> bool:
    for match in VOWEL_PLUS_ACCENTED_VOWEL_RE.finditer(name):
        if match.group(0) in {"iá", "IÁ"}:
            continue
        return True
    return False


def validate_athlete_name_quality(data: dict[str, list[dict[str, str]]], issues: list[BatchIssue]) -> None:
    specs = [
        ("athlete", "full_name", True),
        ("result", "athlete_name", False),
        ("relay_swimmer", "swimmer_name", False),
    ]
    for table_key, column, require_comma in specs:
        rows = data.get(table_key, [])
        if not rows:
            continue

        vowel_plus_accented = 0
        split_enye = 0
        missing_comma = 0
        for row in rows:
            name = (row.get(column) or "").strip()
            if not name:
                continue
            if has_vowel_plus_accented_vowel_residue(name):
                vowel_plus_accented += 1
            if SPLIT_ENYE_RE.search(name):
                split_enye += 1
            if require_comma and "," not in name:
                missing_comma += 1

        if vowel_plus_accented:
            issues.append(
                BatchIssue(
                    "error",
                    f"{table_key}_vowel_plus_accented_vowel",
                    f"{table_key}.csv tiene nombres con residuo OCR vocal+vocal acentuada.",
                    vowel_plus_accented,
                )
            )
        if split_enye:
            issues.append(
                BatchIssue(
                    "error",
                    f"{table_key}_split_enye",
                    f"{table_key}.csv tiene nombres con residuo OCR de ene/eñe separada.",
                    split_enye,
                )
            )
        if missing_comma:
            issues.append(
                BatchIssue(
                    "error",
                    f"{table_key}_name_without_comma",
                    f"{table_key}.csv tiene nombres de atleta sin formato Apellido, Nombre.",
                    missing_comma,
                )
            )


def load_reviewed_club_aliases(path: Path = CLUB_ALIAS_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    _, rows = read_csv_rows(path)
    return {
        (row.get("alias_name") or "").strip().casefold(): (row.get("canonical_name") or "").strip()
        for row in rows
        if (row.get("alias_name") or "").strip() and (row.get("canonical_name") or "").strip()
    }


def validate_identity_boundary_quality(data: dict[str, list[dict[str, str]]], issues: list[BatchIssue]) -> None:
    reviewed_club_aliases = load_reviewed_club_aliases()
    specs = [
        ("athlete", "full_name", "club_name"),
        ("result", "athlete_name", "club_name"),
        ("relay_swimmer", "swimmer_name", None),
    ]
    for table_key, athlete_column, club_column in specs:
        rows = data.get(table_key, [])
        if not rows:
            continue

        athlete_residue = 0
        club_residue = 0
        boundary_residue = 0
        for row in rows:
            athlete_name = (row.get(athlete_column) or "").strip()
            club_name = (row.get(club_column) or "").strip() if club_column else ""
            canonical_club_name = reviewed_club_aliases.get(club_name.casefold(), club_name)
            has_athlete_residue = bool(athlete_name and ATHLETE_BOUNDARY_RESIDUE_RE.search(athlete_name))
            has_club_residue = bool(
                canonical_club_name and CLUB_LEADING_BOUNDARY_RESIDUE_RE.search(canonical_club_name)
            )
            if has_athlete_residue:
                athlete_residue += 1
            if has_club_residue:
                club_residue += 1
            if has_athlete_residue or has_club_residue:
                boundary_residue += 1

        if athlete_residue:
            issues.append(
                BatchIssue(
                    "error",
                    f"{table_key}_athlete_boundary_residue",
                    f"{table_key}.csv tiene nombres de atleta con residuos estructurales de solapamiento.",
                    athlete_residue,
                )
            )
        if club_residue:
            issues.append(
                BatchIssue(
                    "error",
                    f"{table_key}_club_boundary_residue",
                    f"{table_key}.csv tiene nombres de club con residuos estructurales de solapamiento.",
                    club_residue,
                )
            )
        if boundary_residue:
            issues.append(
                BatchIssue(
                    "error",
                    f"{table_key}_identity_boundary_residue",
                    f"{table_key}.csv tiene posible contaminacion entre nombre de atleta y club.",
                    boundary_residue,
                )
            )


def parse_int_or_none(value: str | None) -> int | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def parse_float_or_none(value: str | None) -> float | None:
    cleaned = (value or "").strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def event_distance_meters(event_name: str | None) -> int | None:
    match = EVENT_DISTANCE_RE.search(event_name or "")
    return int(match.group(1)) if match else None


def event_age_group_range(event_name: str | None) -> tuple[int, int] | None:
    match = EVENT_AGE_GROUP_RE.search(event_name or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def event_gender_from_name(event_name: str | None) -> str | None:
    normalized = (event_name or "").strip().lower()
    if normalized.startswith("women "):
        return "female"
    if normalized.startswith("men "):
        return "male"
    return None


def athlete_identity_key(name: str | None, club_name: str | None, birth_year: str | None) -> tuple[str, str, str]:
    return ((name or "").strip().lower(), (club_name or "").strip().lower(), (birth_year or "").strip())


def validate_result_event_consistency(data: dict[str, list[dict[str, str]]], issues: list[BatchIssue]) -> None:
    result_rows = data.get("result", [])
    if not result_rows:
        return

    athlete_gender_by_key = {
        athlete_identity_key(row.get("full_name"), row.get("club_name"), row.get("birth_year")): (row.get("gender") or "").strip()
        for row in data.get("athlete", [])
    }
    age_mismatches = 0
    gender_mismatches = 0
    for row in result_rows:
        event_name = row.get("event_name")
        event_range = event_age_group_range(event_name)
        age = parse_int_or_none(row.get("age_at_event"))
        if event_range is not None and age is not None:
            min_age, max_age = event_range
            if age < min_age or age > max_age:
                age_mismatches += 1

        expected_gender = event_gender_from_name(event_name)
        if expected_gender is None:
            continue
        athlete_gender = athlete_gender_by_key.get(
            athlete_identity_key(row.get("athlete_name"), row.get("club_name"), row.get("birth_year_estimated"))
        )
        if athlete_gender and athlete_gender != expected_gender:
            gender_mismatches += 1

    if age_mismatches:
        issues.append(
            BatchIssue(
                "error",
                "result_event_age_mismatch",
                "result.csv tiene filas cuya age_at_event no calza con el rango etario del evento.",
                age_mismatches,
            )
        )
    if gender_mismatches:
        issues.append(
            BatchIssue(
                "error",
                "result_event_gender_mismatch",
                "result.csv tiene filas cuyo atleta no calza con el genero del evento.",
                gender_mismatches,
            )
        )


def validate_result_time_quality(data: dict[str, list[dict[str, str]]], issues: list[BatchIssue]) -> None:
    for table_key in ["result", "relay_team"]:
        rows = data.get(table_key, [])
        if not rows:
            continue
        min_result_time_ms = MIN_VALID_RELAY_RESULT_TIME_MS if table_key == "relay_team" else MIN_VALID_RESULT_TIME_MS
        impossible_times = 0
        for row in rows:
            status = (row.get("status") or "").strip()
            result_time_ms = parse_int_or_none(row.get("result_time_ms"))
            if status == "valid" and result_time_ms is not None and result_time_ms < min_result_time_ms:
                impossible_times += 1
        if impossible_times:
            issues.append(
                BatchIssue(
                    "error",
                    f"{table_key}_implausibly_short_result_time",
                    f"{table_key}.csv tiene tiempos validos bajo {min_result_time_ms} ms.",
                    impossible_times,
                )
            )

        impossible_seed_times = 0
        for row in rows:
            seed_time_ms = parse_int_or_none(row.get("seed_time_ms"))
            distance_m = event_distance_meters(row.get("event_name"))
            if seed_time_ms is not None and distance_m is not None and distance_m >= 100 and seed_time_ms < 25000:
                impossible_seed_times += 1
        if impossible_seed_times:
            issues.append(
                BatchIssue(
                    "error",
                    f"{table_key}_implausibly_short_seed_time",
                    f"{table_key}.csv tiene seed_time bajo 25000 ms en pruebas de 100m o mas.",
                    impossible_seed_times,
                )
            )


def validate_points_quality(data: dict[str, list[dict[str, str]]], issues: list[BatchIssue]) -> None:
    table_limits = {"result": MAX_INDIVIDUAL_POINTS, "relay_team": MAX_RELAY_POINTS}
    for table_key, max_points in table_limits.items():
        rows = data.get(table_key, [])
        if not rows:
            continue
        points_without_rank = 0
        points_over_max = 0
        for row in rows:
            points_raw = (row.get("points") or "").strip()
            if not points_raw:
                continue
            if parse_int_or_none(row.get("rank_position")) is None:
                points_without_rank += 1
            points = parse_float_or_none(points_raw)
            if points is not None and points > max_points:
                points_over_max += 1
        if points_without_rank:
            issues.append(
                BatchIssue(
                    "error",
                    f"{table_key}_points_without_rank",
                    f"{table_key}.csv tiene points en filas sin rank_position.",
                    points_without_rank,
                )
            )
        if points_over_max:
            issues.append(
                BatchIssue(
                    "error",
                    f"{table_key}_points_over_max",
                    f"{table_key}.csv tiene points sobre el maximo esperado ({max_points:g}).",
                    points_over_max,
                )
            )


def validate_relay_duplicate_quality(data: dict[str, list[dict[str, str]]], issues: list[BatchIssue]) -> None:
    specs = {
        "relay_team": [
            "event_name",
            "club_name",
            "relay_team_name",
            "rank_position",
            "seed_time_ms",
            "result_time_ms",
            "points",
            "status",
        ],
        "relay_swimmer": [
            "event_name",
            "relay_team_name",
            "leg_order",
            "swimmer_name",
            "gender",
            "age_at_event",
            "birth_year_estimated",
        ],
    }
    for table_key, key_columns in specs.items():
        rows = data.get(table_key, [])
        if not rows:
            continue
        seen = set()
        duplicate_rows = 0
        for row in rows:
            key = tuple((row.get(column) or "").strip() for column in key_columns)
            if key in seen:
                duplicate_rows += 1
                continue
            seen.add(key)
        if duplicate_rows:
            issues.append(
                BatchIssue(
                    "error",
                    f"{table_key}_duplicate_rows",
                    f"{table_key}.csv tiene filas duplicadas de relevos.",
                    duplicate_rows,
                )
            )


def validate_known_relay_line_wrap_residue(data: dict[str, list[dict[str, str]]], issues: list[BatchIssue]) -> None:
    bad_adaip_rows = sum(
        1
        for row in data.get("relay_team", [])
        if (row.get("club_name") or "").strip().lower() == "interioradaip"
    )
    if bad_adaip_rows:
        issues.append(
            BatchIssue(
                "error",
                "relay_team_known_line_wrap_residue",
                "relay_team.csv conserva un corte de linea conocido: INTERIORADAIP debe corregirse a ADAIP antes de cargar.",
                bad_adaip_rows,
            )
        )


def validate_debug_ratio(input_dir: Path, parsed_rows: int, threshold: float, counts: dict[str, int], issues: list[BatchIssue]) -> None:
    debug_path = input_dir / "debug_unparsed_lines.csv"
    if not debug_path.exists():
        issues.append(BatchIssue("warning", "missing_debug_unparsed_lines", "Falta debug_unparsed_lines.csv."))
        return

    _, debug_rows = read_csv_rows(debug_path)
    counts["debug_unparsed_lines"] = len(debug_rows)
    unparsed_relay_headers = sum(
        1
        for row in debug_rows
        if UNPARSED_RELAY_EVENT_HEADER_RE.search((row.get("raw_line") or "").strip())
    )
    counts["debug_unparsed_relay_event_headers"] = unparsed_relay_headers
    if unparsed_relay_headers:
        issues.append(
            BatchIssue(
                "error",
                "unparsed_relay_event_headers",
                "Hay encabezados de relevo sin parsear en debug_unparsed_lines.csv.",
                unparsed_relay_headers,
            )
        )
    if parsed_rows <= 0:
        return
    ratio = len(debug_rows) / parsed_rows
    if ratio > threshold:
        issues.append(
            BatchIssue(
                "error",
                "debug_unparsed_ratio_exceeded",
                f"debug_unparsed_lines.csv supera el umbral: {ratio:.3f} > {threshold:.3f}.",
                len(debug_rows),
            )
        )


def validate_input_dir(input_dir: Path, debug_threshold: float = DEFAULT_DEBUG_THRESHOLD, source_url: str | None = None) -> BatchValidationResult:
    issues: list[BatchIssue] = []
    counts: dict[str, int] = {}
    data: dict[str, list[dict[str, str]]] = {}

    if not input_dir.exists() or not input_dir.is_dir():
        return BatchValidationResult(
            state="failed",
            input_dir=str(input_dir),
            source_url=source_url,
            competition_scope=None,
            governing_body_code=None,
            governing_body_name=None,
            counts=counts,
            issues=[BatchIssue("error", "input_dir_not_found", f"No existe la carpeta: {input_dir}.")],
            metadata={},
            commands={},
        )

    metadata = read_metadata(input_dir, issues)
    add_missing_file_issues(input_dir, issues)

    for key, expected_columns in {**REQUIRED_PARSER_OUTPUTS, **OPTIONAL_RELAY_OUTPUTS}.items():
        path = input_dir / f"{key}.csv"
        if not path.exists():
            continue
        columns, rows = read_csv_rows(path)
        validate_columns(key, columns, expected_columns, issues)
        data[key] = rows
        counts[key] = len(rows)

    if counts.get("event", 0) == 0:
        issues.append(BatchIssue("error", "no_events_found", "El parser no encontro eventos."))

    parsed_result_rows = counts.get("result", 0) + counts.get("relay_team", 0)
    if parsed_result_rows == 0:
        issues.append(BatchIssue("error", "no_results_found", "El parser no encontro resultados individuales ni relevos."))

    validate_canons(data, issues)
    validate_required_identities(data, issues)
    validate_relay_swimmer_leg_order(data, issues)
    validate_athlete_name_quality(data, issues)
    validate_identity_boundary_quality(data, issues)
    validate_result_time_quality(data, issues)
    validate_result_event_consistency(data, issues)
    validate_points_quality(data, issues)
    validate_relay_duplicate_quality(data, issues)
    validate_known_relay_line_wrap_residue(data, issues)
    validate_debug_ratio(input_dir, parsed_result_rows, debug_threshold, counts, issues)

    state = "requires_review" if any(issue.severity == "error" for issue in issues) else "validated"
    return BatchValidationResult(
        state=state,
        input_dir=str(input_dir),
        source_url=source_url,
        competition_scope=None,
        governing_body_code=None,
        governing_body_name=None,
        counts=counts,
        issues=issues,
        metadata=metadata,
        commands={},
    )


def print_text_summary(result: BatchValidationResult) -> None:
    print(f"Estado batch: {result.state}")
    print(f"Input dir: {result.input_dir}")
    if result.source_url:
        print(f"Source URL: {result.source_url}")
    if result.competition_scope:
        print(f"Competition scope: {result.competition_scope}")
    if result.governing_body_code:
        print(f"Governing body: {result.governing_body_code}")
    print("Conteos:")
    for key in sorted(result.counts):
        print(f"  {key}: {result.counts[key]}")
    if not result.issues:
        print("Issues: ninguno")
        return
    print("Issues:")
    for issue in result.issues:
        print(f"  [{issue.severity}] {issue.issue_key}: {issue.message} ({issue.count})")


def write_summary_json(result: BatchValidationResult, summary_path: Path) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")


def write_manifest_summary_json(result: BatchManifestResult, summary_path: Path) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")


def process_one(args: argparse.Namespace) -> BatchValidationResult:
    parse_command = build_parse_command(args) if args.pdf else None
    try:
        input_dir = run_parser(args) if args.pdf else Path(args.input_dir)
    except subprocess.CalledProcessError as exc:
        input_dir = Path(args.out_dir) if args.pdf else Path(args.input_dir)
        return BatchValidationResult(
            state="failed",
            input_dir=str(input_dir),
            source_url=getattr(args, "source_url", None),
            competition_scope=getattr(args, "competition_scope", None),
            governing_body_code=getattr(args, "governing_body_code", None),
            governing_body_name=getattr(args, "governing_body_name", None),
            counts={},
            issues=[
                BatchIssue(
                    "error",
                    "parser_failed",
                    f"El parser fallo con codigo de salida {exc.returncode}.",
                )
            ],
            metadata={},
            commands={"parse": parse_command, "load": None},
        )
    result = validate_input_dir(input_dir, args.debug_threshold, getattr(args, "source_url", None))
    result.competition_scope = getattr(args, "competition_scope", None)
    result.governing_body_code = getattr(args, "governing_body_code", None)
    result.governing_body_name = getattr(args, "governing_body_name", None)
    result.commands["parse"] = parse_command
    result.commands["load"] = redact_command(build_load_command(args, input_dir)) if args.load else None
    apply_load_scope_gate(result, args)
    if args.load and result.state == "validated":
        run_pipeline(args, input_dir)
        result.state = "loaded"
    return result


def apply_load_scope_gate(result: BatchValidationResult, args: argparse.Namespace) -> None:
    if not args.load:
        return
    required_scope = getattr(args, "required_competition_scope", DEFAULT_REQUIRED_COMPETITION_SCOPE)
    competition_scope = getattr(args, "competition_scope", None)
    if not required_scope or competition_scope == required_scope:
        return
    result.issues.append(
        BatchIssue(
            "error",
            "competition_scope_not_allowed",
            f"--load requiere competition_scope={required_scope}; recibido: {competition_scope or 'sin_scope'}.",
        )
    )
    result.state = "requires_review"


def summarize_manifest_state(documents: list[BatchValidationResult], load_enabled: bool) -> str:
    states = {document.state for document in documents}
    if "failed" in states:
        return "failed"
    if "requires_review" in states:
        return "requires_review"
    if load_enabled and states == {"loaded"}:
        return "loaded"
    return "validated"


def count_manifest_states(documents: list[BatchValidationResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for document in documents:
        counts[document.state] = counts.get(document.state, 0) + 1
    return counts


def process_manifest(args: argparse.Namespace) -> BatchManifestResult:
    manifest_path = Path(args.manifest)
    if not manifest_path.exists() or not manifest_path.is_file():
        raise SystemExit(f"[ERROR] No existe el manifest: {manifest_path}")

    entries = read_manifest_entries(manifest_path)
    if not entries:
        return BatchManifestResult("failed", str(manifest_path), {}, [])

    documents: list[BatchValidationResult] = []
    for entry in entries:
        item_args = build_manifest_item_args(args, entry)
        documents.append(process_one(item_args))

    state = summarize_manifest_state(documents, args.load)
    return BatchManifestResult(state=state, manifest_path=str(manifest_path), state_counts=count_manifest_states(documents), documents=documents)


def print_manifest_summary(result: BatchManifestResult) -> None:
    print(f"Estado manifest: {result.state}")
    print(f"Manifest: {result.manifest_path}")
    print(f"Documentos: {len(result.documents)}")
    print("Estados:")
    for state, count in sorted(result.state_counts.items()):
        print(f"  {state}: {count}")
    for index, document in enumerate(result.documents, start=1):
        print(f"  {index}. {document.state} - {document.input_dir}")


def main() -> None:
    args = parse_args()
    if args.manifest:
        manifest_result = process_manifest(args)
        if args.summary_json:
            write_manifest_summary_json(manifest_result, Path(args.summary_json))
        if args.json:
            print(json.dumps(asdict(manifest_result), ensure_ascii=False, indent=2))
        else:
            print_manifest_summary(manifest_result)
        if manifest_result.state in {"failed", "requires_review"}:
            raise SystemExit(1)
        return

    result = process_one(args)
    if args.summary_json:
        write_summary_json(result, Path(args.summary_json))
    if args.json:
        payload = asdict(result)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_text_summary(result)

    if result.state in {"failed", "requires_review"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
