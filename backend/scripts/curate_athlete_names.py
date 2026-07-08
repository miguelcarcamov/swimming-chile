"""Curate athlete-name variants after parsing and before load.

This script is intentionally separate from the parser and loader. It consumes
parsed CSV folders from a manifest, groups likely OCR variants, and writes
auditable replacement proposals without loading data to core.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import pandas as pd

from audit_athlete_names import load_manifest, load_overrides, read_csv_if_exists, resolve_path
from audit_expected_athlete_identity import load_birth_year_evidence, load_partial_name_decisions
from run_pipeline_results import clean_extracted_text, infer_relay_club_name, normalize_match_text, normalize_string


NAME_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
FRAGMENTED_NAME_RE = re.compile(r"(?:^|\s)(?:[^\W\d_]\s+){2,}[^\W\d_](?:\s|$)", re.UNICODE)
NOISY_VOWEL_RUN_RE = re.compile(r"[aeiou]{2,}")
REPEATED_VOWEL_RUN_RE = re.compile(r"([aeiou])\1+")
OCR_VOWEL_RESIDUE_RE = re.compile(r"([aeiouAEIOUáéíóúüÁÉÍÓÚÜ])([áéíóúüÁÉÍÓÚÜ])")
OCR_SPLIT_ENYE_RE = re.compile(r"(?:ñ\s+ñ|n\s+ñ|ñ\s+n)", re.IGNORECASE)
OCR_ORPHAN_VOWEL_FRAGMENT_RE = re.compile(r"\b([AEIOUaeiou])\s+([a-zñ])")
EVENT_DISTANCE_RE = re.compile(r"\b(\d+)\s+(?:LC|SC)\s+Meter\b", re.IGNORECASE)
FUZZY_IDENTITY_DECISION_COLUMNS = [
    "decision",
    "suggested_canonical_full_name",
    "review_hint",
    "candidate_reason",
    "gender",
    "birth_year",
    "same_club",
    "left_athlete_id",
    "left_full_name",
    "left_club",
    "left_observations",
    "left_result_count",
    "left_relay_count",
    "right_athlete_id",
    "right_full_name",
    "right_club",
    "right_observations",
    "right_result_count",
    "right_relay_count",
    "surname_similarity",
    "given_similarity",
    "surname_edit_distance",
    "left_result_clubs",
    "left_relay_clubs",
    "right_result_clubs",
    "right_relay_clubs",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Curate athlete-name variants from parsed manifest CSV folders."
    )
    parser.add_argument("--manifest", required=True, help="Manifest JSONL with parsed input_dir entries.")
    parser.add_argument("--summary-json", required=True, help="Output JSON summary path.")
    parser.add_argument(
        "--review-csv",
        required=True,
        help="Output CSV with grouped athlete-name replacement proposals.",
    )
    parser.add_argument(
        "--override-input-dir",
        action="append",
        default=[],
        metavar="SOURCE_URL=INPUT_DIR",
        help="Override one manifest input_dir for a source_url, useful for scratch parser outputs.",
    )
    parser.add_argument(
        "--materialize-output-root",
        help="Optional output root for curated per-document CSV folders.",
    )
    parser.add_argument(
        "--materialized-manifest",
        help="Optional output manifest pointing to curated per-document CSV folders.",
    )
    parser.add_argument(
        "--birth-year-evidence-csv",
        help="Optional same-club delta-1 birth_year evidence CSV to apply during materialization.",
    )
    parser.add_argument(
        "--missing-birth-year-consolidation-csv",
        help="Optional reviewed/applied missing-birth_year consolidation CSV.",
    )
    parser.add_argument(
        "--partial-name-decisions-csv",
        action="append",
        default=[],
        help="Optional reviewed partial-name decisions CSV. Only decision=merge rows are applied.",
    )
    parser.add_argument(
        "--gender-corrections-csv",
        action="append",
        default=[],
        help="Optional reviewed gender corrections CSV with full_name, birth_year and gender.",
    )
    parser.add_argument(
        "--name-corrections-csv",
        action="append",
        default=[],
        help="Optional reviewed club-locked name corrections CSV with old_full_name, new_full_name, birth_year, club_key and gender.",
    )
    parser.add_argument(
        "--result-exclusions-csv",
        action="append",
        default=[],
        help="Optional reviewed result exclusions CSV with source_url, event_name, athlete_name, club_name and birth_year.",
    )
    parser.add_argument(
        "--result-event-corrections-csv",
        action="append",
        default=[],
        help="Optional reviewed result event corrections CSV with source_url, old_event_name, new_event_name, athlete_name, club_name and birth_year.",
    )
    parser.add_argument(
        "--relay-swimmer-corrections-csv",
        action="append",
        default=[],
        help="Optional reviewed relay corrections keyed by source_url, page_number and line_number.",
    )
    parser.add_argument(
        "--fuzzy-identity-decisions-csv",
        action="append",
        default=[],
        help="Optional reviewed fuzzy identity CSV. Only decision=merge rows are applied.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout.")
    return parser.parse_args()


def strip_accents(value: Optional[str]) -> Optional[str]:
    cleaned = clean_extracted_text(value)
    if not cleaned:
        return None
    normalized = unicodedata.normalize("NFKD", cleaned)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def flatten_visible_name(value: Optional[str]) -> Optional[str]:
    cleaned = strip_accents(value)
    if not cleaned:
        return None
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def repair_known_ocr_name_residue(value: Optional[str]) -> Optional[str]:
    cleaned = clean_extracted_text(value)
    if not cleaned:
        return cleaned

    repaired = OCR_SPLIT_ENYE_RE.sub("ñ", cleaned)

    def drop_extra_accented_vowel(match: re.Match[str]) -> str:
        first = match.group(1)
        if first in {"i", "I"} and match.group(2) in {"á", "Á"}:
            return match.group(0)
        if ord(first) > 127:
            return strip_accents(match.group(0)) or match.group(0)
        return strip_accents(first) or first

    previous = None
    while previous != repaired:
        previous = repaired
        repaired = OCR_VOWEL_RESIDUE_RE.sub(drop_extra_accented_vowel, repaired)

    repaired = OCR_ORPHAN_VOWEL_FRAGMENT_RE.sub(r"\1\2", repaired)
    # Swim It Up can truncate a sponsor annotation after an unmatched opening
    # parenthesis; that suffix is structural noise, not part of the athlete name.
    if repaired.count("(") > repaired.count(")"):
        repaired = repaired.split("(", 1)[0].rstrip(" ,")
    repaired = re.sub(r"\s+", " ", repaired).strip()
    return repaired or cleaned


def token_signature(token: str) -> str:
    normalized = normalize_match_text(token) or ""
    normalized = normalized.replace(" ", "")
    if not normalized:
        return ""
    collapsed = re.sub(r"([aeiou])\1+", r"\1", normalized)
    consonants = re.sub(r"[aeiou]", "", collapsed)
    core = consonants or collapsed
    return f"{collapsed[0]}|{core}|{collapsed[-1]}"


def athlete_name_signature(name: Optional[str]) -> Optional[str]:
    cleaned = clean_extracted_text(name)
    if not cleaned:
        return None
    sides = [side.strip() for side in cleaned.split(",")]
    signature_sides: List[str] = []
    for side in sides:
        tokens = NAME_TOKEN_RE.findall(side)
        if not tokens:
            continue
        token_signatures = [token_signature(token) for token in tokens if token_signature(token)]
        if token_signatures:
            signature_sides.append(".".join(token_signatures))
    if not signature_sides:
        return None
    return ",".join(signature_sides)


def athlete_name_noise_score(name: Optional[str]) -> int:
    cleaned = clean_extracted_text(name) or ""
    if not cleaned:
        return 100

    score = 0
    if "," not in cleaned:
        score += 3
    if re.search(r"\d", cleaned):
        score += 10
    if FRAGMENTED_NAME_RE.search(cleaned):
        score += 6
    if "ñ ñ" in cleaned.lower():
        score += 6

    flat = flatten_visible_name(cleaned) or ""
    for token in NAME_TOKEN_RE.findall(flat):
        token_lower = token.lower()
        if NOISY_VOWEL_RUN_RE.search(token_lower):
            score += 2
        if len(re.findall(r"[ÁÉÍÓÚáéíóú]", token)) > 1:
            score += 2
    score += len(re.findall(r"[ÁÉÍÓÚáéíóúÜüÑñ]", cleaned))
    return score



def relay_swimmer_club_context_by_index(input_dir: Path, relay_swimmer_df) -> Dict[int, str]:
    """Infer relay swimmer club context without changing relay_swimmer.csv schema.

    Parser relay swimmers carry relay_team_name, not club_name. Name-curation
    rules are club-locked, so derive the same club context later used by the
    loader from relay_team.csv + club.csv.
    """
    if relay_swimmer_df.empty or "relay_team_name" not in relay_swimmer_df.columns:
        return {}
    relay_team_path = input_dir / "relay_team.csv"
    club_path = input_dir / "club.csv"
    if not relay_team_path.exists():
        return {}
    relay_team_df = read_csv_if_exists(relay_team_path)
    if relay_team_df.empty or not {"event_name", "relay_team_name"}.issubset(set(relay_team_df.columns)):
        return {}

    club_df = read_csv_if_exists(club_path)
    club_names = [name for name in club_df.get("name", pd.Series(dtype=str)).tolist() if normalize_string(name)]
    relay_team_df = relay_team_df.copy()
    explicit_club_names = (
        relay_team_df["club_name"].map(clean_extracted_text)
        if "club_name" in relay_team_df.columns
        else pd.Series([None] * len(relay_team_df), index=relay_team_df.index, dtype=object)
    )
    relay_team_df["club_name"] = explicit_club_names.combine_first(
        relay_team_df["relay_team_name"].map(lambda value: infer_relay_club_name(value, club_names))
    )
    relay_team_df["_event_key"] = relay_team_df["event_name"].map(normalize_match_text)
    relay_team_df["_team_key"] = relay_team_df["relay_team_name"].map(normalize_match_text)
    relay_team_df["_page_number_int"] = pd.to_numeric(relay_team_df.get("page_number"), errors="coerce")
    relay_team_df["_line_number_int"] = pd.to_numeric(relay_team_df.get("line_number"), errors="coerce")
    relay_team_df["_document_order"] = range(len(relay_team_df))

    context: Dict[int, str] = {}
    for index, row in relay_swimmer_df.iterrows():
        event_key = normalize_match_text(row.get("event_name"))
        team_key = normalize_match_text(row.get("relay_team_name"))
        candidates = relay_team_df[(relay_team_df["_event_key"] == event_key) & (relay_team_df["_team_key"] == team_key)]
        selected = None
        if not candidates.empty:
            swimmer_page = pd.to_numeric(pd.Series([row.get("page_number")]), errors="coerce").iloc[0]
            swimmer_line = pd.to_numeric(pd.Series([row.get("line_number")]), errors="coerce").iloc[0]
            if pd.notna(swimmer_page) and pd.notna(swimmer_line):
                same_page_previous = candidates[
                    (candidates["_page_number_int"] == swimmer_page)
                    & (candidates["_line_number_int"].notna())
                    & (candidates["_line_number_int"] <= swimmer_line)
                ]
                if not same_page_previous.empty:
                    selected = same_page_previous.sort_values(["_line_number_int", "_document_order"]).iloc[-1]
            if selected is None:
                selected = candidates.sort_values("_document_order").iloc[-1]
        club_name = (
            clean_extracted_text(selected.get("club_name")) if selected is not None else None
        ) or infer_relay_club_name(row.get("relay_team_name"), club_names)
        if club_name:
            context[index] = club_name
    return context

def collect_name_rows(document: dict, input_dir: Path) -> List[dict]:
    source_url = clean_extracted_text(document.get("source_url")) or ""
    rows: List[dict] = []
    table_specs = (
        ("athlete", "athlete.csv", "full_name", "club_name", "gender", "birth_year"),
        ("result", "result.csv", "athlete_name", "club_name", None, "birth_year_estimated"),
        ("relay_swimmer", "relay_swimmer.csv", "swimmer_name", "club_name", "gender", "birth_year_estimated"),
    )

    for table_name, filename, name_column, club_column, gender_column, birth_year_column in table_specs:
        df = read_csv_if_exists(input_dir / filename)
        if df.empty or name_column not in df.columns:
            continue
        relay_club_context = relay_swimmer_club_context_by_index(input_dir, df) if table_name == "relay_swimmer" else {}
        for index, row in df.iterrows():
            athlete_name = clean_extracted_text(row.get(name_column))
            if not athlete_name:
                continue
            club_name = relay_club_context.get(index) or clean_extracted_text(row.get(club_column)) or ""
            rows.append(
                {
                    "source_url": source_url,
                    "input_dir": str(input_dir),
                    "table": table_name,
                    "athlete_name": athlete_name,
                    "club_name": club_name,
                    "gender": clean_extracted_text(row.get(gender_column)) or "" if gender_column else "",
                    "birth_year": clean_extracted_text(row.get(birth_year_column)) or "",
                }
            )
    return rows


def normalize_birth_year(value: Optional[str]) -> str:
    cleaned = clean_extracted_text(value)
    if not cleaned:
        return ""
    match = re.match(r"^(\d{4})(?:\.0)?$", cleaned)
    # Category-derived ranges such as 1962-1966 are evidence only; never
    # materialize them into integer birth_year fields consumed by the loader.
    return match.group(1) if match else ""


def curation_group_key(row: dict) -> Optional[Tuple[str, str, str, str]]:
    signature = athlete_name_signature(row.get("athlete_name"))
    birth_year = normalize_birth_year(row.get("birth_year"))
    club_key = normalize_match_text(row.get("club_name")) or ""
    gender = normalize_match_text(row.get("gender")) or ""
    if not signature or not birth_year or not club_key:
        return None
    return signature, birth_year, club_key, gender


def choose_canonical_name(group_rows: Sequence[dict]) -> str:
    counts = Counter(row["athlete_name"] for row in group_rows)
    candidates = sorted(
        counts.keys(),
        key=lambda name: (
            -counts[name],
            athlete_name_noise_score(name),
            sum(1 for ch in name if ord(ch) > 127),
            len(flatten_visible_name(name) or name),
            flatten_visible_name(name) or name,
        ),
    )
    chosen = candidates[0]
    chosen_flat = flatten_visible_name(chosen)
    return chosen_flat or chosen


def _name_tokens(value: Optional[str]) -> List[str]:
    flat = flatten_visible_name(value)
    if not flat:
        return []
    return [token.lower() for token in NAME_TOKEN_RE.findall(flat)]


def _single_vowel_deletion_distance(original: str, canonical: str) -> Optional[int]:
    """Return deleted vowel count when canonical is original minus only vowels."""
    if original == canonical:
        return 0
    i = 0
    j = 0
    deletions = 0
    while i < len(original) and j < len(canonical):
        if original[i] == canonical[j]:
            i += 1
            j += 1
            continue
        if original[i] in "aeiou":
            deletions += 1
            i += 1
            continue
        return None
    while i < len(original):
        if original[i] not in "aeiou":
            return None
        deletions += 1
        i += 1
    if j != len(canonical):
        return None
    return deletions


def is_safe_ocr_replacement(original_name: str, canonical_name: str, counts: Counter) -> bool:
    original_tokens = _name_tokens(original_name)
    canonical_tokens = _name_tokens(canonical_name)
    if not original_tokens or len(original_tokens) != len(canonical_tokens):
        return False
    if not any(ord(ch) > 127 for ch in original_name) and not any(
        REPEATED_VOWEL_RUN_RE.search(token) for token in original_tokens
    ):
        return False

    changed_tokens = 0
    for original_token, canonical_token in zip(original_tokens, canonical_tokens):
        if original_token == canonical_token:
            continue
        if token_signature(original_token) != token_signature(canonical_token):
            return False
        deleted_vowels = _single_vowel_deletion_distance(original_token, canonical_token)
        if deleted_vowels is None or deleted_vowels > 1:
            return False
        changed_tokens += 1

    if changed_tokens == 0:
        return False

    original_count = counts[original_name]
    canonical_count = counts.get(canonical_name, 0)
    return canonical_count >= original_count or athlete_name_noise_score(original_name) > athlete_name_noise_score(canonical_name)


def build_review_rows(rows: Sequence[dict]) -> Tuple[List[dict], Dict[Tuple[str, str, str, str], str]]:
    grouped: Dict[Tuple[str, str, str, str], List[dict]] = defaultdict(list)
    for row in rows:
        group_key = curation_group_key(row)
        if group_key:
            grouped[group_key].append(row)

    review_rows: List[dict] = []
    replacement_map: Dict[Tuple[str, str, str, str], str] = {}
    for group_key, group_rows in grouped.items():
        signature, birth_year, club_key, gender = group_key
        distinct_names = sorted({row["athlete_name"] for row in group_rows})
        if len(distinct_names) < 2:
            continue

        canonical_name = choose_canonical_name(group_rows)
        counts = Counter(row["athlete_name"] for row in group_rows)
        source_urls = sorted({row["source_url"] for row in group_rows if row["source_url"]})
        club_names = sorted({row["club_name"] for row in group_rows if row["club_name"]})

        for original_name in distinct_names:
            flattened_original = flatten_visible_name(original_name) or original_name
            replacement_needed = flattened_original != canonical_name and is_safe_ocr_replacement(
                original_name,
                canonical_name,
                counts,
            )
            if replacement_needed:
                replacement_map[(original_name, birth_year, club_key, gender)] = canonical_name
            review_rows.append(
                {
                    "signature": signature,
                    "birth_year": birth_year,
                    "club_key": club_key,
                    "gender": gender,
                    "canonical_name": canonical_name,
                    "original_name": original_name,
                    "original_name_flat": flattened_original,
                    "needs_replacement": "yes" if replacement_needed else "no",
                    "occurrence_count": counts[original_name],
                    "group_size": len(distinct_names),
                    "source_urls": " | ".join(source_urls),
                    "club_names": " | ".join(club_names[:10]),
                }
            )

    review_rows.sort(key=lambda row: (row["canonical_name"], row["signature"], row["original_name"]))
    return review_rows, replacement_map


def write_csv(path: Path, rows: Sequence[dict], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_dict_rows(path: Path) -> List[dict]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return []
    first_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    rows = text.splitlines()
    reader = csv.reader(rows, delimiter=delimiter)
    first_row = next(reader, [])
    normalized_first = [normalize_match_text(value) or "" for value in first_row]
    # normalize_match_text folds underscores to spaces, so compare normalized
    # header tokens instead of raw snake_case names. Otherwise 26-column
    # semicolon review files can be mistaken for legacy headerless fuzzy CSVs.
    has_header = "decision" in normalized_first and (
        "suggested canonical full name" in normalized_first
        or "canonical full name" in normalized_first
        or "shorter full name" in normalized_first
    )
    if has_header:
        return list(csv.DictReader(rows, delimiter=delimiter))
    if len(first_row) == len(FUZZY_IDENTITY_DECISION_COLUMNS):
        return [dict(zip(FUZZY_IDENTITY_DECISION_COLUMNS, first_row))] + [
            dict(zip(FUZZY_IDENTITY_DECISION_COLUMNS, row))
            for row in reader
            if row
        ]
    return list(csv.DictReader(rows, delimiter=delimiter))


def ordered_name_key(value: Optional[str]) -> str:
    return normalize_match_text(value) or ""


def canonicalize_space_ordered_name(value: Optional[str]) -> Optional[str]:
    cleaned = clean_extracted_text(value)
    if cleaned and "," not in cleaned:
        # Sudamericanos-style rows can append team qualifiers to the swimmer
        # name, e.g. "CAIO CUNHA FRANCO (FORTALEZA RAIA 4)". Strip that
        # qualifier before the digit guard so the athlete name can be ordered.
        cleaned = re.sub(r"\s+\([^)]*\)?$", "", cleaned).strip()
    if not cleaned or "," in cleaned or re.search(r"\d", cleaned):
        return cleaned
    tokens = NAME_TOKEN_RE.findall(cleaned)
    if len(tokens) < 2:
        return cleaned

    surname_start = len(tokens) - 1
    if len(tokens) >= 4 and tokens[-3].lower() == "de" and tokens[-2].lower() == "la":
        surname_start = len(tokens) - 3
    elif len(tokens) >= 3 and tokens[-2].lower() in {"de", "del"}:
        surname_start = len(tokens) - 2

    given_tokens = tokens[:surname_start]
    surname_tokens = tokens[surname_start:]
    if not given_tokens or not surname_tokens:
        return cleaned
    return f"{' '.join(surname_tokens)}, {' '.join(given_tokens)}"


def normalize_person_name_case(value: Optional[str]) -> Optional[str]:
    cleaned = clean_extracted_text(value)
    if not cleaned:
        return cleaned
    particles = {"da", "das", "de", "del", "do", "dos", "e", "la", "las", "los", "y"}

    def normalize_token(match: re.Match[str]) -> str:
        token = match.group(0)
        lowered = token.lower()
        if lowered in particles:
            return lowered
        if len(token) == 1:
            return token.upper()
        return lowered[:1].upper() + lowered[1:]

    return NAME_TOKEN_RE.sub(normalize_token, cleaned)


def load_missing_birth_year_consolidations(path: Path) -> List[dict]:
    rows: List[dict] = []
    if not path.exists():
        raise FileNotFoundError(path)
    for row in read_dict_rows(path):
        old_name = clean_extracted_text(row.get("old_full_name"))
        new_name = clean_extracted_text(row.get("new_full_name"))
        birth_year = normalize_birth_year(row.get("new_birth_year"))
        club_key = normalize_match_text(row.get("club_key")) or ""
        gender = normalize_match_text(row.get("gender")) or ""
        if old_name and new_name and birth_year and club_key:
            rows.append(
                {
                    "old_name": old_name,
                    "old_key": ordered_name_key(old_name),
                    "new_name": new_name,
                    "new_key": ordered_name_key(new_name),
                    "birth_year": birth_year,
                    "club_key": club_key,
                    "gender": gender,
                }
            )
    return rows


def normalize_gender_rule_value(value: Optional[str]) -> str:
    gender = normalize_match_text(value) or ""
    if gender in {"female", "mujer", "women", "w", "f"}:
        return "female"
    if gender in {"male", "hombre", "men", "m"}:
        return "male"
    return ""


def load_gender_corrections(path: Path) -> List[dict]:
    rows: List[dict] = []
    if not path.exists():
        raise FileNotFoundError(path)
    for row in read_dict_rows(path):
        name = clean_extracted_text(row.get("full_name") or row.get("athlete_name") or row.get("name"))
        birth_year = normalize_birth_year(row.get("birth_year") or row.get("birth_year_estimated"))
        gender = normalize_gender_rule_value(row.get("gender") or row.get("corrected_gender") or row.get("new_gender"))
        if name and birth_year and gender:
            rows.append(
                {
                    "name_key": ordered_name_key(name),
                    "birth_year": birth_year,
                    "gender": gender,
                }
            )
    return rows


def load_name_corrections(path: Path) -> List[dict]:
    rows: List[dict] = []
    if not path.exists():
        raise FileNotFoundError(path)
    for row in read_dict_rows(path):
        decision = normalize_match_text(row.get("decision")) or "merge"
        if decision != "merge":
            continue
        old_name = clean_extracted_text(row.get("old_full_name") or row.get("old_name"))
        new_name = clean_extracted_text(row.get("new_full_name") or row.get("new_name"))
        birth_year = normalize_birth_year(row.get("birth_year") or row.get("new_birth_year"))
        club_key = normalize_match_text(row.get("club_key")) or ""
        gender = normalize_match_text(row.get("gender")) or ""
        if old_name and new_name and birth_year and club_key:
            rows.append(
                {
                    "old_key": ordered_name_key(old_name),
                    "new_name": new_name,
                    "new_key": ordered_name_key(new_name),
                    "birth_year": birth_year,
                    "club_key": club_key,
                    "gender": gender,
                }
            )
    return rows


def load_result_exclusions(path: Path) -> List[dict]:
    rows: List[dict] = []
    if not path.exists():
        raise FileNotFoundError(path)
    for row in read_dict_rows(path):
        decision = normalize_match_text(row.get("decision")) or "exclude"
        if decision not in {"exclude", "drop"}:
            continue
        source_url = clean_extracted_text(row.get("source_url")) or ""
        event_name = clean_extracted_text(row.get("event_name")) or ""
        athlete_name = clean_extracted_text(row.get("athlete_name")) or ""
        club_name = clean_extracted_text(row.get("club_name")) or ""
        birth_year = normalize_birth_year(row.get("birth_year") or row.get("birth_year_estimated"))
        if source_url and event_name and athlete_name and club_name and birth_year:
            rows.append(
                {
                    "source_url": source_url,
                    "event_key": ordered_name_key(event_name),
                    "athlete_key": ordered_name_key(athlete_name),
                    "club_key": normalize_match_text(club_name) or "",
                    "birth_year": birth_year,
                }
            )
    return rows


def load_result_event_corrections(path: Path) -> List[dict]:
    rows: List[dict] = []
    if not path.exists():
        raise FileNotFoundError(path)
    for row in read_dict_rows(path):
        decision = normalize_match_text(row.get("decision")) or "correct"
        if decision not in {"correct", "move", "reclassify"}:
            continue
        source_url = clean_extracted_text(row.get("source_url")) or ""
        old_event_name = clean_extracted_text(row.get("old_event_name") or row.get("event_name")) or ""
        new_event_name = clean_extracted_text(row.get("new_event_name")) or ""
        athlete_name = clean_extracted_text(row.get("athlete_name")) or ""
        club_name = clean_extracted_text(row.get("club_name")) or ""
        birth_year = normalize_birth_year(row.get("birth_year") or row.get("birth_year_estimated"))
        if source_url and old_event_name and new_event_name and athlete_name and club_name and birth_year:
            rows.append(
                {
                    "source_url": source_url,
                    "old_event_key": ordered_name_key(old_event_name),
                    "new_event_name": new_event_name,
                    "athlete_key": ordered_name_key(athlete_name),
                    "club_key": normalize_match_text(club_name) or "",
                    "birth_year": birth_year,
                }
            )
    return rows



def decision_birth_year(row: dict) -> str:
    bucket = normalize_match_text(row.get("confidence_bucket")) or ""
    kind = normalize_match_text(row.get("source_identity_kind")) or ""
    if bucket == "suda 2026 birth year range" or kind == "suda name range 2026":
        return normalize_birth_year(row.get("core_birth_year"))
    return normalize_birth_year(row.get("birth_year") or row.get("core_birth_year"))

def load_fuzzy_identity_decisions(path: Path) -> List[dict]:
    rows: List[dict] = []
    if not path.exists():
        raise FileNotFoundError(path)
    for row in read_dict_rows(path):
        decision = normalize_match_text(row.get("decision")) or ""
        if decision != "merge":
            continue
        canonical_name = clean_extracted_text(
            row.get("suggested_canonical_full_name")
            or row.get("canonical_full_name")
            or row.get("core_full_name")
            or row.get("target_full_name")
        )
        birth_year = decision_birth_year(row)
        gender = normalize_match_text(row.get("gender") or row.get("suda_gender") or row.get("core_gender")) or ""
        if not canonical_name:
            continue
        old_name_fields = (
            "left_full_name",
            "right_full_name",
            "source_full_name",
            "target_full_name",
            "suda_full_name",
            "core_full_name",
        )
        for field in old_name_fields:
            old_name = clean_extracted_text(row.get(field))
            if not old_name or ordered_name_key(old_name) == ordered_name_key(canonical_name):
                continue
            # Some Sudamericanos 2026 rows only have an age-group range, not an exact
            # result birth_year. Keep the reviewed name merge applicable to result.csv
            # rows with empty birth_year, without inventing a year in the source row.
            rows.append(
                {
                    "old_key": ordered_name_key(old_name),
                    "new_name": canonical_name,
                    "new_key": ordered_name_key(canonical_name),
                    "birth_year": birth_year,
                    "club_key": "",
                    "gender": gender,
                }
            )
    return rows


def load_fuzzy_identity_birth_year_decisions(path: Path) -> List[dict]:
    rows: List[dict] = []
    if not path.exists():
        raise FileNotFoundError(path)
    for row in read_dict_rows(path):
        decision = normalize_match_text(row.get("decision")) or ""
        if decision != "merge":
            continue
        canonical_name = clean_extracted_text(
            row.get("suggested_canonical_full_name") or row.get("canonical_full_name")
        )
        canonical_birth_year = decision_birth_year(row)
        gender = normalize_match_text(row.get("gender")) or ""
        if not canonical_name or not canonical_birth_year:
            continue
        for side in ("left", "right"):
            old_name = clean_extracted_text(row.get(f"{side}_full_name"))
            old_birth_year = normalize_birth_year(row.get(f"{side}_birth_year"))
            if not old_name or not old_birth_year or old_birth_year == canonical_birth_year:
                continue
            rows.append(
                {
                    "old_key": ordered_name_key(old_name),
                    "old_birth_year": old_birth_year,
                    "new_name": canonical_name,
                    "new_key": ordered_name_key(canonical_name),
                    "birth_year": canonical_birth_year,
                    "club_key": "",
                    "gender": gender,
                }
            )
    return rows


def load_fuzzy_identity_merge_keys(path: Path) -> List[dict]:
    rows: List[dict] = []
    if not path.exists():
        raise FileNotFoundError(path)
    for row in read_dict_rows(path):
        decision = normalize_match_text(row.get("decision")) or ""
        if decision != "merge":
            continue
        canonical_name = clean_extracted_text(
            row.get("suggested_canonical_full_name")
            or row.get("canonical_full_name")
            or row.get("core_full_name")
            or row.get("target_full_name")
        )
        birth_year = decision_birth_year(row)
        gender = normalize_match_text(row.get("gender") or row.get("suda_gender") or row.get("core_gender")) or ""
        if canonical_name and birth_year:
            rows.append(
                {
                    "name_key": ordered_name_key(canonical_name),
                    "birth_year": birth_year,
                    "gender": gender,
                }
            )
    return rows


def load_partial_name_consolidations(path: Path) -> List[dict]:
    decisions = load_partial_name_decisions(path)
    rows: List[dict] = []
    for decision in decisions:
        rows.append(
            {
                "old_key": ordered_name_key(decision["shorter_athlete_key"]),
                "new_name": clean_extracted_text(decision["canonical_full_name"]) or "",
                "new_key": ordered_name_key(decision["canonical_full_name"]),
                "birth_year": normalize_birth_year(decision["birth_year"]),
                "club_key": normalize_match_text(decision["club_key"]) or "",
                "gender": normalize_match_text(decision["gender"]) or "",
            }
        )
    return [row for row in rows if row["old_key"] and row["new_name"] and row["birth_year"] and row["club_key"]]


def resolve_partial_name_rule_chains(rules: Sequence[dict]) -> List[dict]:
    by_context = {
        (rule["old_key"], rule["birth_year"], rule["club_key"], rule["gender"]): rule
        for rule in rules
    }
    resolved: List[dict] = []
    for rule in rules:
        current = dict(rule)
        seen = {current["old_key"]}
        while True:
            next_rule = by_context.get(
                (current["new_key"], current["birth_year"], current["club_key"], current["gender"])
            )
            if not next_rule or next_rule["new_key"] in seen:
                break
            seen.add(next_rule["new_key"])
            current["new_name"] = next_rule["new_name"]
            current["new_key"] = next_rule["new_key"]
        resolved.append(current)
    return resolved


def build_partial_name_identity_rules(rules: Sequence[dict]) -> List[dict]:
    grouped: Dict[Tuple[str, str, str], set[Tuple[str, str]]] = defaultdict(set)
    for rule in rules:
        grouped[(rule["old_key"], rule["birth_year"], rule["gender"])].add((rule["new_name"], rule["new_key"]))

    identity_rules: List[dict] = []
    for (old_key, birth_year, gender), replacements in grouped.items():
        if len(replacements) != 1:
            continue
        new_name, new_key = next(iter(replacements))
        identity_rules.append(
            {
                "old_key": old_key,
                "new_name": new_name,
                "new_key": new_key,
                "birth_year": birth_year,
                "club_key": "",
                "gender": gender,
            }
        )
    return identity_rules


def build_comma_order_rules(rows: Sequence[dict]) -> List[dict]:
    surname_token_counts = Counter()
    given_token_counts = Counter()
    contexts: Dict[Tuple[str, str, str, str], dict] = {}
    for row in rows:
        name = clean_extracted_text(row.get("athlete_name"))
        if not name or "," not in name:
            continue
        left, right = [side.strip() for side in name.split(",", 1)]
        left_tokens = NAME_TOKEN_RE.findall(flatten_visible_name(left) or "")
        right_tokens = NAME_TOKEN_RE.findall(flatten_visible_name(right) or "")
        if len(left_tokens) == 1:
            surname_token_counts[left_tokens[0].lower()] += 1
        for token in right_tokens:
            given_token_counts[token.lower()] += 1
        if len(left_tokens) == 1 and len(right_tokens) == 1:
            key = (
                ordered_name_key(name),
                normalize_birth_year(row.get("birth_year")),
                normalize_match_text(row.get("club_name")) or "",
                normalize_match_text(row.get("gender")) or "",
            )
            contexts[key] = {
                "old_key": key[0],
                "old_name": name,
                "birth_year": key[1],
                "club_key": key[2],
                "gender": key[3],
                "left_token": left_tokens[0].lower(),
                "right_token": right_tokens[0].lower(),
                "new_name": f"{right_tokens[0]}, {left_tokens[0]}",
            }

    rules: List[dict] = []
    for context in contexts.values():
        left_token = context["left_token"]
        right_token = context["right_token"]
        if not context["birth_year"] or not context["club_key"]:
            continue
        left_as_given = given_token_counts[left_token]
        left_as_surname = surname_token_counts[left_token]
        right_as_surname = surname_token_counts[right_token]
        right_as_given = given_token_counts[right_token]
        if left_as_given < 10 or right_as_surname < 10:
            continue
        if left_as_given < max(3, left_as_surname * 5):
            continue
        if right_as_surname <= right_as_given:
            continue
        rules.append(
            {
                "old_key": context["old_key"],
                "new_name": context["new_name"],
                "new_key": ordered_name_key(context["new_name"]),
                "birth_year": context["birth_year"],
                "club_key": context["club_key"],
                "gender": context["gender"],
            }
        )
    return rules


def build_comma_order_identity_rules(rules: Sequence[dict]) -> List[dict]:
    grouped: Dict[Tuple[str, str, str], set[Tuple[str, str]]] = defaultdict(set)
    for rule in rules:
        grouped[(rule["old_key"], rule["birth_year"], rule["gender"])].add((rule["new_name"], rule["new_key"]))

    identity_rules: List[dict] = []
    for (old_key, birth_year, gender), replacements in grouped.items():
        if len(replacements) != 1:
            continue
        new_name, new_key = next(iter(replacements))
        identity_rules.append(
            {
                "old_key": old_key,
                "new_name": new_name,
                "new_key": new_key,
                "birth_year": birth_year,
                "club_key": "",
                "gender": gender,
            }
        )
    return identity_rules


def load_materialization_rules(
    args: argparse.Namespace,
    name_replacement_map: Optional[Dict[Tuple[str, str, str, str], str]] = None,
    name_rows: Optional[Sequence[dict]] = None,
) -> dict:
    ocr_name_rules = []
    for (old_name, birth_year, club_key, gender), new_name in (name_replacement_map or {}).items():
        old_name_clean = clean_extracted_text(old_name)
        new_name_clean = clean_extracted_text(new_name)
        if old_name_clean and new_name_clean:
            ocr_name_rules.append(
                {
                    "old_key": ordered_name_key(old_name_clean),
                    "new_name": new_name_clean,
                    "new_key": ordered_name_key(new_name_clean),
                    "birth_year": normalize_birth_year(birth_year),
                    "club_key": normalize_match_text(club_key) or "",
                    "gender": normalize_match_text(gender) or "",
                }
            )

    birth_year_rules = {}
    if args.birth_year_evidence_csv:
        for (athlete_key, gender, club_key), new_year in load_birth_year_evidence(
            resolve_path(args.birth_year_evidence_csv)
        ).items():
            birth_year_rules[(athlete_key, gender, club_key)] = new_year
            birth_year_rules.setdefault((athlete_key, "", club_key), new_year)

    missing_rules = (
        load_missing_birth_year_consolidations(resolve_path(args.missing_birth_year_consolidation_csv))
        if args.missing_birth_year_consolidation_csv
        else []
    )
    partial_rules = []
    for decisions_csv in args.partial_name_decisions_csv:
        partial_rules.extend(load_partial_name_consolidations(resolve_path(decisions_csv)))
    partial_rules = resolve_partial_name_rule_chains(partial_rules)
    fuzzy_identity_rules = []
    fuzzy_identity_birth_year_rules = []
    athlete_identity_merge_keys = []
    for decisions_csv in getattr(args, "fuzzy_identity_decisions_csv", []):
        decisions_path = resolve_path(decisions_csv)
        fuzzy_identity_rules.extend(load_fuzzy_identity_decisions(decisions_path))
        fuzzy_identity_birth_year_rules.extend(load_fuzzy_identity_birth_year_decisions(decisions_path))
        athlete_identity_merge_keys.extend(load_fuzzy_identity_merge_keys(decisions_path))
    fuzzy_identity_rules = resolve_partial_name_rule_chains(fuzzy_identity_rules)
    gender_correction_rules = []
    for gender_corrections_csv in getattr(args, "gender_corrections_csv", []):
        gender_correction_rules.extend(load_gender_corrections(resolve_path(gender_corrections_csv)))
    name_correction_rules = []
    for name_corrections_csv in getattr(args, "name_corrections_csv", []):
        name_correction_rules.extend(load_name_corrections(resolve_path(name_corrections_csv)))
    result_exclusion_rules = []
    for result_exclusions_csv in getattr(args, "result_exclusions_csv", []):
        result_exclusion_rules.extend(load_result_exclusions(resolve_path(result_exclusions_csv)))
    result_event_correction_rules = []
    for result_event_corrections_csv in getattr(args, "result_event_corrections_csv", []):
        result_event_correction_rules.extend(load_result_event_corrections(resolve_path(result_event_corrections_csv)))
    relay_swimmer_correction_rules = []
    for corrections_csv in getattr(args, "relay_swimmer_corrections_csv", []):
        relay_swimmer_correction_rules.extend(read_dict_rows(resolve_path(corrections_csv)))
    comma_order_rules = build_comma_order_rules(name_rows or [])
    return {
        "ocr_name_rules": ocr_name_rules,
        "name_correction_rules": name_correction_rules,
        "result_exclusion_rules": result_exclusion_rules,
        "result_event_correction_rules": result_event_correction_rules,
        "relay_swimmer_correction_rules": relay_swimmer_correction_rules,
        "birth_year_rules": birth_year_rules,
        "missing_birth_year_rules": missing_rules,
        "partial_name_rules": partial_rules,
        "partial_name_identity_rules": build_partial_name_identity_rules(partial_rules),
        "fuzzy_identity_rules": fuzzy_identity_rules,
        "fuzzy_identity_birth_year_rules": fuzzy_identity_birth_year_rules,
        "athlete_identity_merge_keys": athlete_identity_merge_keys,
        "gender_correction_rules": gender_correction_rules,
        "comma_order_rules": comma_order_rules,
        "comma_order_identity_rules": build_comma_order_identity_rules(comma_order_rules),
    }


def apply_relay_swimmer_line_corrections(
    relay_df,
    source_url: str,
    corrections: Sequence[dict],
    competition_year: Optional[int] = None,
) -> Tuple[object, int]:
    applicable = [
        row for row in corrections
        if normalize_match_text(row.get("source_url")) == normalize_match_text(source_url)
        and (normalize_match_text(row.get("decision")) or "replace") in {"replace", "correct"}
    ]
    if not applicable:
        return relay_df, 0

    grouped: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for row in applicable:
        grouped[(str(row.get("page_number") or "").strip(), str(row.get("line_number") or "").strip())].append(row)

    corrected_df = relay_df.copy()
    corrected_groups = 0
    for (page_number, line_number), reviewed_rows in grouped.items():
        leg_orders = sorted(int(row.get("leg_order") or 0) for row in reviewed_rows)
        if leg_orders != [1, 2, 3, 4]:
            raise ValueError(
                f"Relay correction must contain legs 1-4: {source_url} page={page_number} line={line_number}"
            )
        mask = (
            corrected_df["page_number"].astype(str).eq(page_number)
            & corrected_df["line_number"].astype(str).eq(line_number)
        )
        existing = corrected_df.loc[mask]
        if existing.empty:
            raise ValueError(
                f"Relay correction did not match parsed rows: {source_url} page={page_number} line={line_number}"
            )
        template = existing.iloc[0].to_dict()
        replacements = []
        for reviewed in sorted(reviewed_rows, key=lambda row: int(row["leg_order"])):
            replacement = dict(template)
            age = str(reviewed.get("age_at_event") or "").strip()
            birth_year = str(reviewed.get("birth_year_estimated") or "").strip()
            if not birth_year and competition_year is not None and age.isdigit():
                birth_year = str(competition_year - int(age))
            replacement.update(
                leg_order=str(reviewed["leg_order"]),
                swimmer_name=clean_extracted_text(reviewed.get("swimmer_name")) or "",
                gender=normalize_match_text(reviewed.get("gender")) or "",
                age_at_event=age,
                birth_year_estimated=birth_year,
                page_number=page_number,
                line_number=line_number,
            )
            replacements.append(replacement)
        corrected_df = pd.concat(
            [corrected_df.loc[~mask], pd.DataFrame(replacements, columns=corrected_df.columns)],
            ignore_index=True,
        )
        corrected_groups += 1

    corrected_df = corrected_df.sort_values(
        ["page_number", "line_number", "leg_order"], kind="stable"
    ).reset_index(drop=True)
    return corrected_df, corrected_groups


def _row_context(
    row,
    name_column: str,
    club_column: str,
    birth_year_column: str,
    gender_column: Optional[str],
    club_name_override: Optional[str] = None,
) -> dict:
    name = clean_extracted_text(row.get(name_column))
    club_key = normalize_match_text(club_name_override if club_name_override else row.get(club_column)) or ""
    birth_year = normalize_birth_year(row.get(birth_year_column))
    gender = normalize_match_text(row.get(gender_column)) or "" if gender_column else ""
    return {
        "name": name,
        "name_key": ordered_name_key(name),
        "club_key": club_key,
        "birth_year": birth_year,
        "gender": gender,
    }


def _rule_matches_context(rule: dict, context: dict, allow_empty_birth_year: bool = False) -> bool:
    if rule["old_key"] != context["name_key"]:
        return False
    if rule["club_key"] != context["club_key"]:
        return False
    if rule.get("gender") and context.get("gender") and rule["gender"] != context["gender"]:
        return False
    if allow_empty_birth_year and not context["birth_year"]:
        return True
    return rule["birth_year"] == context["birth_year"]


def _identity_rule_matches_context(rule: dict, context: dict) -> bool:
    if rule["old_key"] != context["name_key"]:
        return False
    if rule.get("gender") and context.get("gender") and rule["gender"] != context["gender"]:
        return False
    if not rule.get("birth_year"):
        return not context["birth_year"]
    if not context["birth_year"]:
        return True
    return rule["birth_year"] == context["birth_year"]


def _fuzzy_birth_year_rule_matches_context(rule: dict, context: dict) -> bool:
    if rule["old_key"] != context["name_key"]:
        return False
    if rule.get("gender") and context.get("gender") and rule["gender"] != context["gender"]:
        return False
    return rule["old_birth_year"] == context["birth_year"]


def _apply_identity_merge_missing_birth_year(output, index: int, birth_year_column: str, context: dict, rules: dict) -> bool:
    if context["birth_year"]:
        return False
    for rule in rules.get("athlete_identity_merge_keys", []):
        if rule["name_key"] != context["name_key"]:
            continue
        if rule.get("gender") and context.get("gender") and rule["gender"] != context["gender"]:
            continue
        output.at[index, birth_year_column] = rule["birth_year"]
        context["birth_year"] = rule["birth_year"]
        return True
    return False


def apply_athlete_curations_to_df(
    df,
    table_name: str,
    rules: dict,
    preserve_source_name_order: bool = False,
    club_context_by_index: Optional[Dict[int, str]] = None,
) -> Tuple[object, dict]:
    specs = {
        "athlete": ("full_name", "club_name", "birth_year", "gender"),
        "result": ("athlete_name", "club_name", "birth_year_estimated", None),
        "relay_swimmer": ("swimmer_name", "club_name", "birth_year_estimated", "gender"),
    }
    if table_name not in specs or df.empty:
        return df, {}

    name_column, club_column, birth_year_column, gender_column = specs[table_name]
    if name_column not in df.columns:
        return df, {}

    output = df.copy()
    counts = Counter()
    for index, row in output.iterrows():
        current_name = clean_extracted_text(row.get(name_column))
        repaired_name = repair_known_ocr_name_residue(current_name)
        if repaired_name and current_name and repaired_name != current_name:
            output.at[index, name_column] = repaired_name
            row = output.loc[index]
            counts["known_ocr_name_residue_repairs"] += 1

        if birth_year_column not in output.columns:
            continue

        club_name_override = (club_context_by_index or {}).get(index)
        context = _row_context(row, name_column, club_column, birth_year_column, gender_column, club_name_override)
        if not context["name_key"]:
            continue

        if gender_column and gender_column in output.columns:
            for rule in rules.get("gender_correction_rules", []):
                if rule["name_key"] == context["name_key"] and rule["birth_year"] == context["birth_year"]:
                    current_gender = normalize_gender_rule_value(row.get(gender_column))
                    if current_gender != rule["gender"]:
                        output.at[index, gender_column] = rule["gender"]
                        context["gender"] = rule["gender"]
                        counts["gender_corrections"] += 1
                    break

        for rule in rules.get("name_correction_rules", []):
            if _rule_matches_context(rule, context):
                output.at[index, name_column] = rule["new_name"]
                context["name"] = rule["new_name"]
                context["name_key"] = rule["new_key"]
                counts["name_corrections"] += 1
                break

        for rule in rules["ocr_name_rules"]:
            if _rule_matches_context(rule, context):
                output.at[index, name_column] = rule["new_name"]
                context["name"] = rule["new_name"]
                context["name_key"] = rule["new_key"]
                counts["ocr_name_replacements"] += 1
                break

        birth_year_key = (context["name_key"], context["gender"], context["club_key"])
        new_year = rules["birth_year_rules"].get(birth_year_key) or rules["birth_year_rules"].get(
            (context["name_key"], "", context["club_key"])
        )
        if new_year and context["birth_year"] and context["birth_year"] != new_year:
            output.at[index, birth_year_column] = new_year
            context["birth_year"] = new_year
            counts["birth_year_corrections"] += 1

        for rule in rules.get("fuzzy_identity_birth_year_rules", []):
            if _fuzzy_birth_year_rule_matches_context(rule, context):
                output.at[index, name_column] = rule["new_name"]
                output.at[index, birth_year_column] = rule["birth_year"]
                context["name"] = rule["new_name"]
                context["name_key"] = rule["new_key"]
                context["birth_year"] = rule["birth_year"]
                counts["fuzzy_identity_birth_year_corrections"] += 1
                break

        if _apply_identity_merge_missing_birth_year(output, index, birth_year_column, context, rules):
            counts["identity_merge_missing_birth_year_consolidations"] += 1

        for rule in rules["missing_birth_year_rules"]:
            if _rule_matches_context(rule, context, allow_empty_birth_year=True):
                output.at[index, name_column] = rule["new_name"]
                output.at[index, birth_year_column] = rule["birth_year"]
                context["name"] = rule["new_name"]
                context["name_key"] = rule["new_key"]
                context["birth_year"] = rule["birth_year"]
                counts["missing_birth_year_consolidations"] += 1
                break

        for rule in rules.get("comma_order_rules", []):
            if _rule_matches_context(rule, context):
                output.at[index, name_column] = rule["new_name"]
                context["name"] = rule["new_name"]
                context["name_key"] = rule["new_key"]
                counts["comma_order_corrections"] += 1
                break
        for rule in rules.get("comma_order_identity_rules", []):
            if _identity_rule_matches_context(rule, context):
                output.at[index, name_column] = rule["new_name"]
                context["name"] = rule["new_name"]
                context["name_key"] = rule["new_key"]
                counts["comma_order_corrections"] += 1
                break

        for rule in rules["partial_name_rules"]:
            if _rule_matches_context(rule, context):
                output.at[index, name_column] = rule["new_name"]
                context["name"] = rule["new_name"]
                context["name_key"] = rule["new_key"]
                counts["partial_name_consolidations"] += 1
                break

        for rule in rules.get("partial_name_identity_rules", []):
            if _identity_rule_matches_context(rule, context):
                output.at[index, name_column] = rule["new_name"]
                context["name"] = rule["new_name"]
                context["name_key"] = rule["new_key"]
                if not context["birth_year"] and rule.get("birth_year"):
                    output.at[index, birth_year_column] = rule["birth_year"]
                    context["birth_year"] = rule["birth_year"]
                    counts["partial_name_missing_birth_year_consolidations"] += 1
                else:
                    counts["partial_name_identity_consolidations"] += 1
                break

        for rule in rules.get("fuzzy_identity_rules", []):
            if _identity_rule_matches_context(rule, context):
                output.at[index, name_column] = rule["new_name"]
                context["name"] = rule["new_name"]
                context["name_key"] = rule["new_key"]
                counts["fuzzy_identity_consolidations"] += 1
                break

        repaired_context_name = repair_known_ocr_name_residue(context["name"])
        if repaired_context_name and repaired_context_name != context["name"]:
            output.at[index, name_column] = repaired_context_name
            context["name"] = repaired_context_name
            context["name_key"] = ordered_name_key(repaired_context_name)
            counts["known_ocr_name_residue_repairs"] += 1

        canonical_order_name = (
            None
            if context["birth_year"] or preserve_source_name_order
            else canonicalize_space_ordered_name(context["name"])
        )
        if canonical_order_name and canonical_order_name != context["name"]:
            output.at[index, name_column] = canonical_order_name
            context["name"] = canonical_order_name
            context["name_key"] = ordered_name_key(canonical_order_name)
            counts["space_order_name_canonicalizations"] += 1
            for rule in rules.get("partial_name_identity_rules", []):
                if _identity_rule_matches_context(rule, context):
                    output.at[index, name_column] = rule["new_name"]
                    context["name"] = rule["new_name"]
                    context["name_key"] = rule["new_key"]
                    if not context["birth_year"] and rule.get("birth_year"):
                        output.at[index, birth_year_column] = rule["birth_year"]
                        context["birth_year"] = rule["birth_year"]
                        counts["partial_name_missing_birth_year_consolidations"] += 1
                    else:
                        counts["partial_name_identity_consolidations"] += 1
                    break
            for rule in rules.get("fuzzy_identity_rules", []):
                if _identity_rule_matches_context(rule, context):
                    output.at[index, name_column] = rule["new_name"]
                    context["name"] = rule["new_name"]
                    context["name_key"] = rule["new_key"]
                    counts["fuzzy_identity_consolidations"] += 1
                    break

        if _apply_identity_merge_missing_birth_year(output, index, birth_year_column, context, rules):
            counts["identity_merge_missing_birth_year_consolidations"] += 1

        if preserve_source_name_order:
            normalized_case = normalize_person_name_case(context["name"])
            if normalized_case and normalized_case != context["name"]:
                output.at[index, name_column] = normalized_case
                context["name"] = normalized_case
                context["name_key"] = ordered_name_key(normalized_case)
                counts["person_name_case_normalizations"] += 1

    return output, dict(counts)


def athlete_gender_from_event_name(event_name: object) -> str:
    event_key = normalize_match_text(event_name) or ""
    if event_key.startswith("women "):
        return "female"
    if event_key.startswith("men "):
        return "male"
    return ""


def event_distance_meters(event_name: object) -> Optional[int]:
    cleaned = clean_extracted_text(event_name) or ""
    match = EVENT_DISTANCE_RE.search(cleaned)
    return int(match.group(1)) if match else None


def result_time_ms_value(value: object) -> Optional[float]:
    cleaned = clean_extracted_text(value)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def is_implausibly_short_distance_result(row: object) -> bool:
    distance = event_distance_meters(row.get("event_name"))
    result_time_ms = result_time_ms_value(row.get("result_time_ms"))
    status = normalize_match_text(row.get("status")) or ""
    if status and status != "valid":
        return False
    return distance is not None and distance >= 200 and result_time_ms is not None and result_time_ms < 90000


def result_exclusion_rule_matches(rule: dict, row: object, source_url: str) -> bool:
    if rule["source_url"] != source_url:
        return False
    return (
        rule["event_key"] == ordered_name_key(row.get("event_name"))
        and rule["athlete_key"] == ordered_name_key(row.get("athlete_name"))
        and rule["club_key"] == (normalize_match_text(row.get("club_name")) or "")
        and rule["birth_year"] == normalize_birth_year(row.get("birth_year_estimated"))
    )


def drop_result_rows_with_reviewed_exclusions(result_df, source_url: str, rules: dict) -> Tuple[object, int]:
    exclusion_rules = rules.get("result_exclusion_rules", [])
    if result_df.empty or not exclusion_rules:
        return result_df, 0

    keep_indexes = []
    dropped = 0
    for index, row in result_df.iterrows():
        if any(result_exclusion_rule_matches(rule, row, source_url) for rule in exclusion_rules):
            dropped += 1
            continue
        keep_indexes.append(index)
    if dropped == 0:
        return result_df, 0
    return result_df.loc[keep_indexes].reset_index(drop=True), dropped


def result_event_correction_rule_matches(rule: dict, row: object, source_url: str) -> bool:
    if rule["source_url"] != source_url:
        return False
    return (
        rule["old_event_key"] == ordered_name_key(row.get("event_name"))
        and rule["athlete_key"] == ordered_name_key(row.get("athlete_name"))
        and rule["club_key"] == (normalize_match_text(row.get("club_name")) or "")
        and rule["birth_year"] == normalize_birth_year(row.get("birth_year_estimated"))
    )


def apply_result_event_corrections(result_df, source_url: str, rules: dict) -> Tuple[object, int]:
    correction_rules = rules.get("result_event_correction_rules", [])
    if result_df.empty or not correction_rules or "event_name" not in result_df.columns:
        return result_df, 0

    corrected_df = result_df.copy()
    corrected = 0
    for index, row in corrected_df.iterrows():
        for rule in correction_rules:
            if result_event_correction_rule_matches(rule, row, source_url):
                corrected_df.at[index, "event_name"] = rule["new_event_name"]
                corrected += 1
                break
    return corrected_df, corrected




# Corrección curada para un corte de línea del Sudamericano 2026:
# el parser separa "INTERIOR DE PE" como club, pero el equipo real es ADAIP.
ADAIP_RELAY_TEAM_NAME = 'ASSOCIAÇÃO DE DESPORTOS AQUÁTICOS DO INTERIOR DE PE "A"'
ADAIP_RELAY_CLUB_NAME = "ADAIP"


def apply_adaip_relay_line_wrap_correction(output_dir: Path) -> int:
    relay_team_path = output_dir / "relay_team.csv"
    relay_swimmer_path = output_dir / "relay_swimmer.csv"
    club_path = output_dir / "club.csv"
    if not relay_team_path.exists():
        return 0
    relay_team_df = read_csv_if_exists(relay_team_path)
    if relay_team_df.empty or not {"club_name", "relay_team_name", "event_name", "page_number", "line_number"}.issubset(relay_team_df.columns):
        return 0

    team_mask = (
        relay_team_df["club_name"].map(normalize_match_text).eq("interioradaip")
        & relay_team_df["relay_team_name"].map(normalize_match_text).eq("associacao de desportos aquaticos do")
    )
    if not team_mask.any():
        return 0

    corrected = int(team_mask.sum())
    team_rows = relay_team_df.loc[team_mask, ["event_name", "page_number", "line_number"]].copy()
    relay_team_df.loc[team_mask, "club_name"] = ADAIP_RELAY_CLUB_NAME
    relay_team_df.loc[team_mask, "relay_team_name"] = ADAIP_RELAY_TEAM_NAME
    relay_team_df.to_csv(relay_team_path, index=False, encoding="utf-8-sig")

    if relay_swimmer_path.exists():
        relay_swimmer_df = read_csv_if_exists(relay_swimmer_path)
        required = {"event_name", "relay_team_name", "page_number", "line_number"}
        if not relay_swimmer_df.empty and required.issubset(relay_swimmer_df.columns):
            swimmer_line = pd.to_numeric(relay_swimmer_df["line_number"], errors="coerce")
            for _, team_row in team_rows.iterrows():
                team_line = pd.to_numeric(pd.Series([team_row.get("line_number")]), errors="coerce").iloc[0]
                if pd.isna(team_line):
                    continue
                swimmer_mask = (
                    relay_swimmer_df["event_name"].eq(team_row.get("event_name"))
                    & relay_swimmer_df["page_number"].astype(str).eq(str(team_row.get("page_number")))
                    & relay_swimmer_df["relay_team_name"].map(normalize_match_text).eq("associacao de desportos aquaticos do")
                    & swimmer_line.gt(team_line)
                    & swimmer_line.le(team_line + 8)
                )
                relay_swimmer_df.loc[swimmer_mask, "relay_team_name"] = ADAIP_RELAY_TEAM_NAME
            relay_swimmer_df.to_csv(relay_swimmer_path, index=False, encoding="utf-8-sig")

    if club_path.exists():
        club_df = read_csv_if_exists(club_path)
        if "name" in club_df.columns and not club_df["name"].map(normalize_match_text).eq("adaip").any():
            source_id = "1"
            if "source_id" in club_df.columns and not club_df.empty:
                source_id = clean_extracted_text(club_df["source_id"].dropna().astype(str).iloc[0]) or "1"
            club_df.loc[len(club_df)] = {
                "name": ADAIP_RELAY_CLUB_NAME,
                "short_name": None,
                "city": None,
                "region": None,
                "source_id": source_id,
            }
            club_df.to_csv(club_path, index=False, encoding="utf-8-sig")
    return corrected

def drop_invalid_relay_swimmer_leg_order(relay_swimmer_df) -> Tuple[object, int]:
    if relay_swimmer_df.empty or "leg_order" not in relay_swimmer_df.columns:
        return relay_swimmer_df, 0
    leg_order = pd.to_numeric(relay_swimmer_df["leg_order"], errors="coerce")
    valid_mask = leg_order.between(1, 4)
    dropped = int((~valid_mask).sum())
    if dropped == 0:
        return relay_swimmer_df, 0
    return relay_swimmer_df.loc[valid_mask].reset_index(drop=True), dropped

def result_identity_key(row: object) -> Optional[Tuple[str, str, str]]:
    key = (
        ordered_name_key(row.get("athlete_name")),
        normalize_match_text(row.get("club_name")) or "",
        normalize_birth_year(row.get("birth_year_estimated")),
    )
    return key if all(key) else None


def drop_result_rows_with_athlete_gender_conflict(result_df, athlete_df) -> Tuple[object, int]:
    if result_df.empty:
        return result_df, 0
    required_result = {"event_name", "athlete_name", "club_name", "birth_year_estimated"}
    required_athlete = {"full_name", "gender", "club_name", "birth_year"}
    if not required_result.issubset(set(result_df.columns)):
        return result_df, 0

    genders_by_identity: Dict[Tuple[str, str, str], set[str]] = defaultdict(set)
    if not athlete_df.empty and required_athlete.issubset(set(athlete_df.columns)):
        for _, row in athlete_df.iterrows():
            gender = normalize_match_text(row.get("gender")) or ""
            if gender not in {"female", "male"}:
                continue
            key = (
                ordered_name_key(row.get("full_name")),
                normalize_match_text(row.get("club_name")) or "",
                normalize_birth_year(row.get("birth_year")),
            )
            if all(key):
                genders_by_identity[key].add(gender)

    gender_by_identity = {
        key: next(iter(genders))
        for key, genders in genders_by_identity.items()
        if len(genders) == 1
    }

    filtered_df = result_df
    dropped = 0
    result_genders_by_identity: Dict[Tuple[str, str, str], set[str]] = defaultdict(set)
    for _, row in filtered_df.iterrows():
        key = result_identity_key(row)
        event_gender = athlete_gender_from_event_name(row.get("event_name"))
        if key and event_gender in {"female", "male"}:
            result_genders_by_identity[key].add(event_gender)

    short_mixed_drop_identities = set()
    keep_indexes = []
    for index, row in filtered_df.iterrows():
        key = result_identity_key(row)
        if (
            key
            and result_genders_by_identity.get(key) == {"female", "male"}
            and is_implausibly_short_distance_result(row)
        ):
            dropped += 1
            short_mixed_drop_identities.add(key)
            continue
        keep_indexes.append(index)

    filtered_df = filtered_df.loc[keep_indexes].reset_index(drop=True) if dropped else filtered_df

    # In two-column HY-TEK PDFs, a page continuation can place a short sprint row
    # under a 200m header. Prefer coherent same-document result gender after
    # removing those impossible rows, because athlete.csv inherits the bad header.
    result_gender_by_identity: Dict[Tuple[str, str, str], str] = {}
    result_genders_by_identity = defaultdict(set)
    for _, row in filtered_df.iterrows():
        key = result_identity_key(row)
        event_gender = athlete_gender_from_event_name(row.get("event_name"))
        if key and event_gender in {"female", "male"}:
            result_genders_by_identity[key].add(event_gender)
    for key, genders in result_genders_by_identity.items():
        if len(genders) == 1:
            result_gender_by_identity[key] = next(iter(genders))

    keep_indexes = []
    for index, row in filtered_df.iterrows():
        event_gender = athlete_gender_from_event_name(row.get("event_name"))
        if not event_gender:
            keep_indexes.append(index)
            continue
        key = result_identity_key(row)
        if key in short_mixed_drop_identities:
            inferred_gender = result_gender_by_identity.get(key) or gender_by_identity.get(key)
        else:
            inferred_gender = gender_by_identity.get(key)
        if inferred_gender and inferred_gender != event_gender:
            dropped += 1
            continue
        keep_indexes.append(index)

    if dropped == 0:
        return result_df, 0
    return filtered_df.loc[keep_indexes].reset_index(drop=True), dropped


def sync_athlete_rows_from_result_identities(athlete_df, result_df, rules: dict) -> Tuple[object, int]:
    if athlete_df.empty or result_df.empty:
        return athlete_df, 0
    required_athlete = {"full_name", "club_name", "birth_year", "gender"}
    required_result = {"event_name", "athlete_name", "club_name", "birth_year_estimated"}
    if not required_athlete.issubset(set(athlete_df.columns)) or not required_result.issubset(set(result_df.columns)):
        return athlete_df, 0

    result_gender_by_identity: Dict[Tuple[str, str, str], str] = {}
    observed_genders: Dict[Tuple[str, str, str], set[str]] = defaultdict(set)
    for _, row in result_df.iterrows():
        key = (
            ordered_name_key(row.get("athlete_name")),
            normalize_match_text(row.get("club_name")) or "",
            normalize_birth_year(row.get("birth_year_estimated")),
        )
        event_gender = athlete_gender_from_event_name(row.get("event_name"))
        if all(key) and event_gender in {"female", "male"}:
            observed_genders[key].add(event_gender)
    for key, genders in observed_genders.items():
        if len(genders) == 1:
            result_gender_by_identity[key] = next(iter(genders))

    candidate_rules = []
    for rule_group in (
        "fuzzy_identity_rules",
        "partial_name_identity_rules",
        "comma_order_identity_rules",
        "partial_name_rules",
        "comma_order_rules",
    ):
        candidate_rules.extend(rules.get(rule_group, []))

    output = athlete_df.copy()
    updated = 0
    for index, row in output.iterrows():
        context = _row_context(row, "full_name", "club_name", "birth_year", "gender")
        if not context["name_key"] or not context["birth_year"] or not context["club_key"]:
            continue
        for rule in candidate_rules:
            if rule["old_key"] != context["name_key"] or rule["birth_year"] != context["birth_year"]:
                continue
            if rule.get("club_key") and rule["club_key"] != context["club_key"]:
                continue
            result_key = (rule["new_key"], context["club_key"], context["birth_year"])
            result_gender = result_gender_by_identity.get(result_key)
            if rule.get("gender") and result_gender and rule["gender"] != result_gender:
                continue
            if not result_gender:
                continue
            if context["name_key"] == rule["new_key"] and context["gender"] == result_gender:
                break
            output.at[index, "full_name"] = rule["new_name"]
            output.at[index, "gender"] = result_gender
            updated += 1
            break

    return output, updated


def _observed_athlete_identities(result_df, relay_swimmer_df) -> Set[Tuple[str, str, str, str]]:
    observed: Set[Tuple[str, str, str, str]] = set()
    if result_df is not None and not result_df.empty:
        required = {"event_name", "athlete_name", "club_name", "birth_year_estimated"}
        if required.issubset(set(result_df.columns)):
            for _, row in result_df.iterrows():
                name_key = ordered_name_key(row.get("athlete_name"))
                birth_year = normalize_birth_year(row.get("birth_year_estimated"))
                club_key = normalize_match_text(row.get("club_name")) or ""
                gender = athlete_gender_from_event_name(row.get("event_name"))
                if name_key and birth_year:
                    observed.add((name_key, club_key, birth_year, gender))

    if relay_swimmer_df is not None and not relay_swimmer_df.empty:
        required = {"swimmer_name", "birth_year_estimated"}
        if required.issubset(set(relay_swimmer_df.columns)):
            for _, row in relay_swimmer_df.iterrows():
                name_key = ordered_name_key(row.get("swimmer_name"))
                birth_year = normalize_birth_year(row.get("birth_year_estimated"))
                club_key = normalize_match_text(row.get("club_name")) or ""
                gender = normalize_match_text(row.get("gender")) or ""
                if name_key and birth_year:
                    observed.add((name_key, club_key, birth_year, gender))
    return observed


def _athlete_row_has_observation(row, observed: Set[Tuple[str, str, str, str]]) -> bool:
    name_key = ordered_name_key(row.get("full_name"))
    birth_year = normalize_birth_year(row.get("birth_year"))
    club_key = normalize_match_text(row.get("club_name")) or ""
    gender = normalize_match_text(row.get("gender")) or ""
    if not name_key or not birth_year:
        return True
    for observed_name, observed_club, observed_year, observed_gender in observed:
        if observed_name != name_key or observed_year != birth_year:
            continue
        if observed_gender and gender and observed_gender != gender:
            continue
        if observed_club and club_key and observed_club != club_key:
            continue
        return True
    return False


def prune_athlete_rows_without_observations(athlete_df, result_df, relay_swimmer_df) -> Tuple[object, int]:
    if athlete_df.empty:
        return athlete_df, 0
    required = {"full_name", "birth_year"}
    if not required.issubset(set(athlete_df.columns)):
        return athlete_df, 0
    observed = _observed_athlete_identities(result_df, relay_swimmer_df)
    if not observed:
        return athlete_df, 0
    keep_indexes = [index for index, row in athlete_df.iterrows() if _athlete_row_has_observation(row, observed)]
    dropped = len(athlete_df) - len(keep_indexes)
    if dropped == 0:
        return athlete_df, 0
    return athlete_df.loc[keep_indexes].reset_index(drop=True), dropped


def _matches_identity_merge_key(row, rules: dict) -> bool:
    name_key = ordered_name_key(row.get("full_name"))
    birth_year = normalize_birth_year(row.get("birth_year"))
    gender = normalize_match_text(row.get("gender")) or ""
    if not name_key or not birth_year:
        return False
    for rule in rules.get("athlete_identity_merge_keys", []):
        if rule["name_key"] != name_key or rule["birth_year"] != birth_year:
            continue
        if rule.get("gender") and gender and rule["gender"] != gender:
            continue
        return True
    return False


def prune_duplicate_athlete_rows_for_reviewed_identity_merges(
    athlete_df,
    rules: dict,
) -> Tuple[object, int]:
    if athlete_df.empty or not rules.get("athlete_identity_merge_keys"):
        return athlete_df, 0
    keep_indexes = []
    dropped = 0
    local_seen: Set[Tuple[str, str, str]] = set()
    for index, row in athlete_df.iterrows():
        name_key = ordered_name_key(row.get("full_name"))
        birth_year = decision_birth_year(row)
        gender = normalize_match_text(row.get("gender") or row.get("suda_gender") or row.get("core_gender")) or ""
        merge_key = (name_key, birth_year, gender)
        if _matches_identity_merge_key(row, rules):
            if merge_key in local_seen:
                dropped += 1
                continue
            local_seen.add(merge_key)
        keep_indexes.append(index)
    if dropped == 0:
        return athlete_df, 0
    return athlete_df.loc[keep_indexes].reset_index(drop=True), dropped


def materialized_input_dir(source_input_dir: Path, output_root: Path) -> Path:
    parts = list(source_input_dir.parts)
    if "results_csv" in parts:
        relative = Path(*parts[parts.index("results_csv") + 1 :])
        if relative.parts and (
            relative.parts[0].startswith("fchmn_curated")
            or relative.parts[0].startswith("fc_fix")
            or relative.parts[0].startswith("fchmn_parser")
        ):
            relative = Path(*relative.parts[1:])
        if relative.parts and (
            relative.parts[0].startswith("suda")
            or relative.parts[0].startswith("sudamericanos")
        ):
            for index, part in enumerate(relative.parts):
                if re.fullmatch(r"20\d{2}", part):
                    relative = Path(*relative.parts[index:])
                    break
    else:
        relative = Path(source_input_dir.name)
    return output_root / relative


def materialize_document_inputs(
    document: dict,
    input_dir: Path,
    output_root: Path,
    rules: dict,
) -> Tuple[dict, dict]:
    output_dir = materialized_input_dir(input_dir, output_root)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(input_dir, output_dir)

    counts = Counter()
    curated_tables = {}
    source_url = clean_extracted_text(document.get("source_url")) or ""
    source_metadata = {}
    metadata_path = input_dir / "metadata.json"
    if metadata_path.exists():
        source_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    preserve_source_name_order = source_metadata.get("athlete_name_order") == "given_family"
    for table_name, filename in [
        ("athlete", "athlete.csv"),
        ("result", "result.csv"),
        ("relay_swimmer", "relay_swimmer.csv"),
    ]:
        csv_path = output_dir / filename
        if not csv_path.exists():
            continue
        df = read_csv_if_exists(csv_path)
        club_context_by_index = (
            relay_swimmer_club_context_by_index(output_dir, df) if table_name == "relay_swimmer" else None
        )
        curated_df, table_counts = apply_athlete_curations_to_df(
            df,
            table_name,
            rules,
            preserve_source_name_order=preserve_source_name_order,
            club_context_by_index=club_context_by_index,
        )
        if table_name == "relay_swimmer":
            curated_df, corrected_lines = apply_relay_swimmer_line_corrections(
                curated_df,
                source_url,
                rules.get("relay_swimmer_correction_rules", []),
            )
            if corrected_lines:
                counts["relay_swimmer_reviewed_lines_corrected"] += corrected_lines
            curated_df, dropped = drop_invalid_relay_swimmer_leg_order(curated_df)
            if dropped:
                counts["relay_swimmer_invalid_leg_order_dropped"] += dropped
        for key, value in table_counts.items():
            counts[f"{table_name}_{key}"] += value
        curated_tables[table_name] = (csv_path, curated_df)
        curated_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    adaip_fixed = apply_adaip_relay_line_wrap_correction(output_dir)
    if adaip_fixed:
        counts["adaip_relay_line_wrap_corrections"] += adaip_fixed

    if "athlete" in curated_tables and "result" in curated_tables:
        result_path, result_df = curated_tables["result"]
        athlete_path, athlete_df = curated_tables["athlete"]
        relay_path, relay_swimmer_df = curated_tables.get("relay_swimmer", (None, None))
        filtered_result_df, corrected = apply_result_event_corrections(result_df, source_url, rules)
        if corrected:
            counts["result_event_correction_rows"] += corrected
            filtered_result_df.to_csv(result_path, index=False, encoding="utf-8-sig")

        filtered_result_df, dropped = drop_result_rows_with_reviewed_exclusions(filtered_result_df, source_url, rules)
        if dropped:
            counts["result_reviewed_exclusion_rows_dropped"] += dropped
            filtered_result_df.to_csv(result_path, index=False, encoding="utf-8-sig")

        filtered_result_df, dropped = drop_result_rows_with_athlete_gender_conflict(filtered_result_df, athlete_df)
        if dropped:
            counts["result_gender_conflict_rows_dropped"] += dropped
            filtered_result_df.to_csv(result_path, index=False, encoding="utf-8-sig")
        synced_athlete_df, synced = sync_athlete_rows_from_result_identities(
            athlete_df,
            filtered_result_df,
            rules,
        )
        if synced:
            counts["athlete_result_identity_synchronizations"] += synced
            synced_athlete_df.to_csv(athlete_path, index=False, encoding="utf-8-sig")
        pruned_athlete_df, pruned = prune_athlete_rows_without_observations(
            synced_athlete_df,
            filtered_result_df,
            relay_swimmer_df,
        )
        if pruned:
            counts["athlete_rows_without_observations_dropped"] += pruned
            pruned_athlete_df.to_csv(athlete_path, index=False, encoding="utf-8-sig")
        # Deduplicate reviewed identities only inside this document. Each
        # manifest entry must remain independently loadable if another fails.
        deduped_athlete_df, deduped = prune_duplicate_athlete_rows_for_reviewed_identity_merges(
            pruned_athlete_df,
            rules,
        )
        if deduped:
            counts["athlete_reviewed_identity_duplicate_rows_dropped"] += deduped
            deduped_athlete_df.to_csv(athlete_path, index=False, encoding="utf-8-sig")

    output_document = dict(document)
    output_document.pop("pdf", None)
    output_document["input_dir"] = str(output_dir)
    output_document["out_dir"] = str(output_dir)
    metadata_path = output_dir / "metadata.json"
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            metadata = {}
        metadata.setdefault("curation", {})
        metadata["curation"]["athlete_materialized"] = True
        metadata["curation"]["source_input_dir"] = str(input_dir)
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_document, dict(counts)


def write_manifest(path: Path, documents: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for document in documents:
            fh.write(json.dumps(document, ensure_ascii=False) + "\n")


def materialize_manifest_inputs(
    documents: Sequence[dict],
    input_dirs_by_source_url: Dict[str, Path],
    output_root: Path,
    rules: dict,
) -> Tuple[List[dict], dict]:
    materialized_documents: List[dict] = []
    total_counts = Counter()
    for document in documents:
        source_url = clean_extracted_text(document.get("source_url")) or ""
        input_dir = input_dirs_by_source_url.get(source_url)
        if input_dir is None:
            continue
        output_document, counts = materialize_document_inputs(
            document,
            input_dir,
            output_root,
            rules,
        )
        materialized_documents.append(output_document)
        for key, value in counts.items():
            total_counts[key] += value
    return materialized_documents, dict(total_counts)


def main() -> int:
    args = parse_args()
    manifest_path = resolve_path(args.manifest)
    summary_path = resolve_path(args.summary_json)
    review_path = resolve_path(args.review_csv)
    overrides = load_overrides(args.override_input_dir)

    documents = load_manifest(manifest_path)
    input_dirs_by_source_url: Dict[str, Path] = {}
    all_rows: List[dict] = []
    override_hits = 0
    missing_input_dirs: List[str] = []
    for document in documents:
        source_url = clean_extracted_text(document.get("source_url")) or ""
        input_dir_value = document.get("input_dir") or document.get("out_dir")
        if source_url in overrides:
            input_dir = overrides[source_url]
            override_hits += 1
        elif input_dir_value:
            input_dir = resolve_path(str(input_dir_value))
        else:
            missing_input_dirs.append(source_url)
            continue
        input_dirs_by_source_url[source_url] = input_dir
        all_rows.extend(collect_name_rows(document, input_dir))

    review_rows, replacement_map = build_review_rows(all_rows)
    fieldnames = [
        "signature",
        "birth_year",
        "club_key",
        "gender",
        "canonical_name",
        "original_name",
        "original_name_flat",
        "needs_replacement",
        "occurrence_count",
        "group_size",
        "source_urls",
        "club_names",
    ]
    write_csv(review_path, review_rows, fieldnames)

    summary = {
        "state": "curated",
        "manifest_documents": len(documents),
        "override_input_dir_hits": override_hits,
        "observed_name_rows": len(all_rows),
        "variant_groups": len({row["signature"] for row in review_rows}),
        "replacement_rows": sum(1 for row in review_rows if row["needs_replacement"] == "yes"),
        "unique_replacements": len(replacement_map),
        "missing_input_dirs": missing_input_dirs,
        "review_csv": str(review_path),
    }
    if args.materialize_output_root or args.materialized_manifest:
        if not args.materialize_output_root or not args.materialized_manifest:
            raise SystemExit("--materialize-output-root y --materialized-manifest deben usarse juntos.")
        materialize_root = resolve_path(args.materialize_output_root)
        materialized_manifest_path = resolve_path(args.materialized_manifest)
        rules = load_materialization_rules(args, replacement_map, all_rows)
        materialized_documents, materialization_counts = materialize_manifest_inputs(
            documents,
            input_dirs_by_source_url,
            materialize_root,
            rules,
        )
        write_manifest(materialized_manifest_path, materialized_documents)
        summary.update(
            {
                "state": "materialized",
                "materialized_documents": len(materialized_documents),
                "materialize_output_root": str(materialize_root),
                "materialized_manifest": str(materialized_manifest_path),
                "materialization_counts": materialization_counts,
            }
        )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
