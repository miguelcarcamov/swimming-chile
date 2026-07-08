"""Generate guarded SQL for reviewed duplicate core.athlete merges.

The generated SQL is intentionally separate from the loader: it rewires only
human-reviewed duplicate athlete ids in core and keeps the operation guarded by
the names, gender and birth year observed during review.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = {
    "decision",
    "canonical_athlete_id",
    "duplicate_athlete_id",
    "proposed_canonical_full_name",
    "current_canonical_full_name",
    "current_duplicate_full_name",
    "gender",
    "birth_year",
}


@dataclass(frozen=True)
class DuplicateAthleteMerge:
    canonical_athlete_id: int
    duplicate_athlete_id: int
    proposed_canonical_full_name: str
    current_canonical_full_name: str
    current_duplicate_full_name: str
    gender: str
    birth_year: int


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo decodificar {path} como UTF-8 ni CP1252.")


def load_duplicate_merges(path: Path) -> list[DuplicateAthleteMerge]:
    text = _read_text(path)
    first_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    missing = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {sorted(missing)}")

    merges: dict[tuple[int, int], DuplicateAthleteMerge] = {}
    for line_number, row in enumerate(reader, start=2):
        decision = (row.get("decision") or "").strip().lower()
        if decision != "merge":
            continue
        try:
            canonical_id = int((row.get("canonical_athlete_id") or "").strip())
            duplicate_id = int((row.get("duplicate_athlete_id") or "").strip())
            birth_year = int((row.get("birth_year") or "").strip())
        except ValueError as exc:
            raise ValueError(f"Fila {line_number}: ids o birth_year invalidos.") from exc
        if canonical_id == duplicate_id:
            raise ValueError(f"Fila {line_number}: canonical y duplicate no pueden ser el mismo id.")

        merge = DuplicateAthleteMerge(
            canonical_athlete_id=canonical_id,
            duplicate_athlete_id=duplicate_id,
            proposed_canonical_full_name=(row.get("proposed_canonical_full_name") or "").strip(),
            current_canonical_full_name=(row.get("current_canonical_full_name") or "").strip(),
            current_duplicate_full_name=(row.get("current_duplicate_full_name") or "").strip(),
            gender=(row.get("gender") or "").strip().lower(),
            birth_year=birth_year,
        )
        if not all(
            (
                merge.proposed_canonical_full_name,
                merge.current_canonical_full_name,
                merge.current_duplicate_full_name,
                merge.gender,
            )
        ):
            raise ValueError(f"Fila {line_number}: identidad incompleta.")
        previous = merges.get((canonical_id, duplicate_id))
        if previous and previous != merge:
            raise ValueError(f"Fila {line_number}: decisiones contradictorias para {canonical_id}/{duplicate_id}.")
        merges[(canonical_id, duplicate_id)] = merge
    return sorted(merges.values(), key=lambda item: (item.canonical_athlete_id, item.duplicate_athlete_id))


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def render_sql(merges: Iterable[DuplicateAthleteMerge]) -> str:
    rows = list(merges)
    if not rows:
        raise ValueError("No hay merges de atletas duplicados para generar.")

    values = []
    for idx, merge in enumerate(rows, start=1):
        values.append(
            "    ("
            f"{idx}, {merge.duplicate_athlete_id}, {merge.canonical_athlete_id}, "
            f"{_sql_literal(merge.current_duplicate_full_name)}, "
            f"{_sql_literal(merge.current_canonical_full_name)}, "
            f"{_sql_literal(merge.proposed_canonical_full_name)}, "
            f"{_sql_literal(merge.gender)}, {merge.birth_year}"
            ")"
        )
    rendered_values = ",\n".join(values)

    return f"""-- Generated from reviewed duplicate athlete merge decisions. Do not edit manually.
BEGIN;

CREATE TEMP TABLE reviewed_duplicate_athlete_merge (
    merge_no INTEGER PRIMARY KEY,
    source_id BIGINT NOT NULL,
    target_id BIGINT NOT NULL,
    source_expected_name TEXT NOT NULL,
    target_expected_name TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    expected_gender TEXT NOT NULL,
    canonical_birth_year INTEGER NOT NULL
) ON COMMIT DROP;

INSERT INTO reviewed_duplicate_athlete_merge (
    merge_no,
    source_id,
    target_id,
    source_expected_name,
    target_expected_name,
    canonical_name,
    expected_gender,
    canonical_birth_year
)
VALUES
{rendered_values};

DO $$
DECLARE
    bad_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO bad_count
    FROM reviewed_duplicate_athlete_merge m
    LEFT JOIN core.athlete src ON src.id = m.source_id
    LEFT JOIN core.athlete tgt ON tgt.id = m.target_id
    WHERE src.id IS NULL
       OR tgt.id IS NULL
       OR src.full_name IS DISTINCT FROM m.source_expected_name
       OR tgt.full_name IS DISTINCT FROM m.target_expected_name
       OR src.gender IS DISTINCT FROM m.expected_gender
       OR tgt.gender IS DISTINCT FROM m.expected_gender
       OR src.birth_year IS DISTINCT FROM m.canonical_birth_year
       OR tgt.birth_year IS DISTINCT FROM m.canonical_birth_year;

    IF bad_count <> 0 THEN
        RAISE EXCEPTION 'Reviewed duplicate athlete merge guard failed for % rows', bad_count;
    END IF;
END $$;

UPDATE core.result r
SET athlete_id = m.target_id
FROM reviewed_duplicate_athlete_merge m
WHERE r.athlete_id = m.source_id;

UPDATE core.relay_result_member rrm
SET athlete_id = m.target_id
FROM reviewed_duplicate_athlete_merge m
WHERE rrm.athlete_id = m.source_id;

INSERT INTO core.athlete_person_link (
    athlete_id,
    person_id,
    link_source,
    confidence,
    verified_at,
    created_at
)
SELECT
    m.target_id,
    apl.person_id,
    apl.link_source,
    apl.confidence,
    apl.verified_at,
    apl.created_at
FROM core.athlete_person_link apl
JOIN reviewed_duplicate_athlete_merge m ON m.source_id = apl.athlete_id
ON CONFLICT (athlete_id, person_id) DO NOTHING;

DELETE FROM core.athlete_person_link apl
USING reviewed_duplicate_athlete_merge m
WHERE apl.athlete_id = m.source_id;

UPDATE core.athlete tgt
SET full_name = m.canonical_name,
    birth_year = m.canonical_birth_year,
    updated_at = now()
FROM reviewed_duplicate_athlete_merge m
WHERE tgt.id = m.target_id;

DELETE FROM core.athlete src
USING reviewed_duplicate_athlete_merge m
WHERE src.id = m.source_id;

DO $$
DECLARE
    remaining_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO remaining_count
    FROM core.athlete a
    JOIN reviewed_duplicate_athlete_merge m ON m.source_id = a.id;

    IF remaining_count <> 0 THEN
        RAISE EXCEPTION 'Reviewed duplicate athlete merge left % source ids', remaining_count;
    END IF;
END $$;

COMMIT;
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare guarded duplicate athlete merge SQL.")
    parser.add_argument("--review-csv", required=True)
    parser.add_argument("--sql-output", required=True)
    parser.add_argument("--summary-json", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    review_path = Path(args.review_csv)
    sql_path = Path(args.sql_output)
    summary_path = Path(args.summary_json)
    merges = load_duplicate_merges(review_path)
    sql_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    sql_path.write_text(render_sql(merges), encoding="utf-8")
    summary_path.write_text(
        json.dumps(
            {
                "state": "generated",
                "review_csv": str(review_path),
                "sql_output": str(sql_path),
                "duplicate_merge_count": len(merges),
                "merges": [asdict(merge) for merge in merges],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
