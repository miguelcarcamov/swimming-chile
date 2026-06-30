"""Preview candidate links between Ñuñoa Master people and core athletes.

This script is read-only. It generates a local ignored review tray for the
human-reviewed bridge identity.person -> core.athlete.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


DEFAULT_PREVIEW_DIR = Path("backend/data/staging/nunoa_master_identity_preview")
DATA_SOURCE = "nunoa_master_2026"


@dataclass(frozen=True)
class PersonPreview:
    row_number: int
    person_id: int
    rut_normalized: str | None
    first_name: str
    last_name: str
    competition_name: str
    date_of_birth: str | None
    birth_year: int | None
    gender: str | None


@dataclass(frozen=True)
class Athlete:
    athlete_id: int
    full_name: str
    gender: str | None
    birth_year: int | None
    current_club_id: int
    current_club_name: str


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z0-9]+", " ", ascii_text).lower()).strip()


def token_set(value: str) -> set[str]:
    return {token for token in normalize_text(value).split() if token}


def parse_birth_year(value: str | None) -> int | None:
    if not value:
        return None
    return datetime.fromisoformat(value).date().year


def load_preview_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def connect() -> psycopg.Connection:
    backend_dir = Path(__file__).resolve().parents[1]
    load_dotenv(backend_dir / ".env")
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg.connect(database_url, row_factory=dict_row)
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        row_factory=dict_row,
    )


def resolve_people(preview_rows: list[dict[str, str]]) -> list[PersonPreview]:
    with connect() as conn, conn.cursor() as cur:
        resolved: list[PersonPreview] = []
        for row in preview_rows:
            rut = clean(row.get("rut_normalized")) or None
            first_name = clean(row.get("first_name"))
            last_name = clean(row.get("last_name"))
            dob = clean(row.get("date_of_birth")) or None
            if rut:
                cur.execute(
                    """
                    SELECT id
                    FROM identity.person
                    WHERE rut_normalized = %s
                    """,
                    (rut,),
                )
            else:
                cur.execute(
                    """
                    SELECT id
                    FROM identity.person
                    WHERE rut_normalized IS NULL
                      AND data_source = %s
                      AND LOWER(TRIM(first_name)) = LOWER(TRIM(%s))
                      AND LOWER(TRIM(last_name)) = LOWER(TRIM(%s))
                      AND date_of_birth IS NOT DISTINCT FROM %s
                    """,
                    (DATA_SOURCE, first_name, last_name, dob),
                )
            matches = cur.fetchall()
            if len(matches) != 1:
                raise ValueError(
                    f"Fila {row.get('row_number')}: resolucion person ambigua: {len(matches)}"
                )
            resolved.append(
                PersonPreview(
                    row_number=int(row["row_number"]),
                    person_id=int(matches[0]["id"]),
                    rut_normalized=rut,
                    first_name=first_name,
                    last_name=last_name,
                    competition_name=clean(row.get("competition_name")),
                    date_of_birth=dob,
                    birth_year=parse_birth_year(dob),
                    gender=clean(row.get("gender")) or None,
                )
            )
    return resolved


def load_current_club_athletes(club_id: int) -> list[Athlete]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                a.id AS athlete_id,
                a.full_name,
                a.gender,
                a.birth_year,
                acc.club_id AS current_club_id,
                acc.club_name AS current_club_name
            FROM core.athlete a
            JOIN core.athlete_current_club acc ON acc.athlete_id = a.id
            WHERE acc.club_id = %s
            ORDER BY a.full_name, a.id
            """,
            (club_id,),
        )
        return [
            Athlete(
                athlete_id=int(row["athlete_id"]),
                full_name=str(row["full_name"]),
                gender=row["gender"],
                birth_year=row["birth_year"],
                current_club_id=int(row["current_club_id"]),
                current_club_name=str(row["current_club_name"]),
            )
            for row in cur.fetchall()
        ]


def person_aliases(person: PersonPreview) -> list[str]:
    first_given = person.first_name.split()[0] if person.first_name.split() else ""
    first_surname = person.last_name.split()[0] if person.last_name.split() else ""
    aliases = [
        person.competition_name,
        f"{person.last_name}, {person.first_name}",
        f"{first_surname}, {first_given}",
        f"{person.first_name} {person.last_name}",
    ]
    return [alias for alias in dict.fromkeys(aliases) if alias.strip()]


def name_score(person: PersonPreview, athlete: Athlete) -> tuple[float, str]:
    athlete_norm = normalize_text(athlete.full_name)
    best_score = 0.0
    best_alias = ""
    athlete_tokens = token_set(athlete.full_name)
    for alias in person_aliases(person):
        alias_norm = normalize_text(alias)
        ratio = SequenceMatcher(None, alias_norm, athlete_norm).ratio()
        alias_tokens = token_set(alias)
        coverage = len(alias_tokens & athlete_tokens) / max(len(alias_tokens), 1)
        score = max(ratio, coverage)
        if score > best_score:
            best_score = score
            best_alias = alias
    return best_score, best_alias


def classify(person: PersonPreview, athlete: Athlete, score: float) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if person.gender and athlete.gender and person.gender == athlete.gender:
        reasons.append("gender_match")
    elif person.gender and athlete.gender:
        reasons.append("gender_mismatch")

    if person.birth_year and athlete.birth_year and person.birth_year == athlete.birth_year:
        reasons.append("birth_year_match")
    elif person.birth_year and athlete.birth_year:
        reasons.append("birth_year_mismatch")
    elif not person.birth_year:
        reasons.append("person_birth_year_missing")
    elif not athlete.birth_year:
        reasons.append("athlete_birth_year_missing")

    if score >= 0.98:
        reasons.append("name_exact_or_near_exact")
    elif score >= 0.82:
        reasons.append("name_similar")
    else:
        reasons.append("name_weak")

    if "gender_mismatch" in reasons or "birth_year_mismatch" in reasons:
        return "review", reasons
    if score >= 0.98 and "gender_match" in reasons and (
        "birth_year_match" in reasons or "person_birth_year_missing" in reasons
    ):
        return "high", reasons
    if score >= 0.82 and "gender_match" in reasons:
        return "medium", reasons
    return "review", reasons


def build_candidates(people: list[PersonPreview], athletes: list[Athlete]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for person in people:
        scored: list[dict[str, Any]] = []
        for athlete in athletes:
            if person.gender and athlete.gender and person.gender != athlete.gender:
                continue
            if person.birth_year and athlete.birth_year and person.birth_year != athlete.birth_year:
                continue
            score, matched_alias = name_score(person, athlete)
            if score < 0.70:
                continue
            confidence, reasons = classify(person, athlete, score)
            scored.append(
                {
                    "person_id": person.person_id,
                    "person_row_number": person.row_number,
                    "person_has_rut": "yes" if person.rut_normalized else "no",
                    "person_name": f"{person.last_name}, {person.first_name}",
                    "person_competition_name": person.competition_name,
                    "person_birth_year": person.birth_year,
                    "person_gender": person.gender,
                    "athlete_id": athlete.athlete_id,
                    "athlete_full_name": athlete.full_name,
                    "athlete_birth_year": athlete.birth_year,
                    "athlete_gender": athlete.gender,
                    "current_club_id": athlete.current_club_id,
                    "current_club_name": athlete.current_club_name,
                    "matched_alias": matched_alias,
                    "name_score": round(score, 4),
                    "confidence": confidence,
                    "reasons": "|".join(reasons),
                    "decision": "",
                    "review_notes": "",
                }
            )
        scored.sort(key=lambda row: (-row["name_score"], row["athlete_full_name"]))
        rows.extend(scored[:5])
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "person_id",
        "person_row_number",
        "person_has_rut",
        "person_name",
        "person_competition_name",
        "person_birth_year",
        "person_gender",
        "athlete_id",
        "athlete_full_name",
        "athlete_birth_year",
        "athlete_gender",
        "current_club_id",
        "current_club_name",
        "matched_alias",
        "name_score",
        "confidence",
        "reasons",
        "decision",
        "review_notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview Ñuñoa Master athlete-person links.")
    parser.add_argument("--club-id", type=int, default=26)
    parser.add_argument(
        "--people-preview",
        default=str(DEFAULT_PREVIEW_DIR / "people_preview.csv"),
    )
    parser.add_argument(
        "--output-csv",
        default=str(DEFAULT_PREVIEW_DIR / "athlete_link_candidates.csv"),
    )
    parser.add_argument(
        "--summary-json",
        default=str(DEFAULT_PREVIEW_DIR / "athlete_link_candidates_summary.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    people = resolve_people(load_preview_rows(Path(args.people_preview)))
    athletes = load_current_club_athletes(args.club_id)
    candidates = build_candidates(people, athletes)
    output_csv = Path(args.output_csv)
    summary_json = Path(args.summary_json)
    write_csv(output_csv, candidates)
    summary = {
        "state": "candidate_links_generated",
        "people": len(people),
        "current_club_athletes": len(athletes),
        "candidate_rows": len(candidates),
        "people_with_candidates": len({row["person_id"] for row in candidates}),
        "high_candidates": sum(1 for row in candidates if row["confidence"] == "high"),
        "medium_candidates": sum(1 for row in candidates if row["confidence"] == "medium"),
        "review_candidates": sum(1 for row in candidates if row["confidence"] == "review"),
        "output_csv": str(output_csv),
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
