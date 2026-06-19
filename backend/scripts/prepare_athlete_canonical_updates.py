"""Generate guarded SQL for reviewed canonical athlete-name updates.

The generated SQL is intentionally separate from the loader: it previews and
applies only human-reviewed canonical names to an already loaded core schema.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = {
    "target_athlete_id",
    "current_core_names",
    "proposed_canonical_full_name",
}


@dataclass(frozen=True)
class CanonicalNameUpdate:
    athlete_id: int
    expected_names: tuple[str, ...]
    canonical_full_name: str


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo decodificar {path} como UTF-8 ni CP1252.")


def load_canonical_updates(path: Path) -> list[CanonicalNameUpdate]:
    text = _read_text(path)
    dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    missing = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {sorted(missing)}")

    updates: dict[int, CanonicalNameUpdate] = {}
    for line_number, row in enumerate(reader, start=2):
        raw_id = (row.get("target_athlete_id") or "").strip()
        current_names = (row.get("current_core_names") or "").strip()
        canonical_name = (row.get("proposed_canonical_full_name") or "").strip()
        if not raw_id or not current_names or not canonical_name:
            raise ValueError(f"Fila {line_number}: identidad incompleta.")
        try:
            athlete_id = int(raw_id)
        except ValueError as exc:
            raise ValueError(f"Fila {line_number}: target_athlete_id invalido: {raw_id!r}.") from exc

        # The reviewed preview may show names absorbed into the same target.
        expected_names = tuple(dict.fromkeys(name.strip() for name in current_names.split(" | ") if name.strip()))
        if current_names == canonical_name:
            continue
        update = CanonicalNameUpdate(athlete_id, expected_names, canonical_name)
        previous = updates.get(athlete_id)
        if previous and previous != update:
            raise ValueError(f"Fila {line_number}: decisiones contradictorias para athlete_id={athlete_id}.")
        updates[athlete_id] = update
    return sorted(updates.values(), key=lambda item: item.athlete_id)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def render_sql(updates: Iterable[CanonicalNameUpdate]) -> str:
    rows = list(updates)
    if not rows:
        raise ValueError("No hay cambios de nombre canonico para generar.")
    values = []
    for update in rows:
        expected_json = json.dumps(update.expected_names, ensure_ascii=False)
        values.append(
            f"    ({update.athlete_id}, {_sql_literal(expected_json)}::jsonb, "
            f"{_sql_literal(update.canonical_full_name)})"
        )
    rendered_values = ",\n".join(values)

    return f"""-- Generated from reviewed athlete identity decisions. Do not edit manually.
BEGIN;

CREATE TEMP TABLE reviewed_athlete_canonical_name (
    athlete_id BIGINT PRIMARY KEY,
    expected_names JSONB NOT NULL,
    canonical_full_name TEXT NOT NULL
) ON COMMIT DROP;

INSERT INTO reviewed_athlete_canonical_name (athlete_id, expected_names, canonical_full_name)
VALUES
{rendered_values};

DO $$
DECLARE
    missing_or_mismatched INTEGER;
    canonical_name_collision INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO missing_or_mismatched
    FROM reviewed_athlete_canonical_name m
    LEFT JOIN core.athlete a ON a.id = m.athlete_id
    WHERE a.id IS NULL
       OR (
            a.full_name <> m.canonical_full_name
            AND NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements_text(m.expected_names) expected(name)
                WHERE expected.name = a.full_name
            )
       );

    IF missing_or_mismatched > 0 THEN
        RAISE EXCEPTION 'Reviewed athlete canonical names have missing/mismatched ids: %', missing_or_mismatched;
    END IF;

    SELECT COUNT(*)
    INTO canonical_name_collision
    FROM reviewed_athlete_canonical_name m
    JOIN core.athlete target ON target.id = m.athlete_id
    JOIN core.athlete other
      ON other.id <> target.id
     AND LOWER(TRIM(other.full_name)) = LOWER(TRIM(m.canonical_full_name))
     AND other.gender IS NOT DISTINCT FROM target.gender
     AND other.birth_year IS NOT DISTINCT FROM target.birth_year;

    IF canonical_name_collision > 0 THEN
        RAISE EXCEPTION 'Reviewed athlete canonical names collide with another identity: %', canonical_name_collision;
    END IF;
END $$;

UPDATE core.athlete a
SET full_name = m.canonical_full_name
FROM reviewed_athlete_canonical_name m
WHERE a.id = m.athlete_id
  AND a.full_name IS DISTINCT FROM m.canonical_full_name;

COMMIT;
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare guarded canonical athlete-name updates.")
    parser.add_argument("--review-csv", required=True)
    parser.add_argument("--sql-output", required=True)
    parser.add_argument("--summary-json", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    review_path = Path(args.review_csv)
    sql_path = Path(args.sql_output)
    summary_path = Path(args.summary_json)
    updates = load_canonical_updates(review_path)
    sql_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    sql_path.write_text(render_sql(updates), encoding="utf-8")
    summary_path.write_text(
        json.dumps(
            {
                "state": "generated",
                "review_csv": str(review_path),
                "sql_output": str(sql_path),
                "canonical_name_update_count": len(updates),
                "updates": [asdict(update) for update in updates],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
