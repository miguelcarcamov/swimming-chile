"""Generate guarded SQL for reviewed Ñuñoa person-athlete links.

The generated SQL is based only on review rows with decision=link. It contains
person-athlete associations and must remain in ignored local paths.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_PREVIEW_DIR = Path("backend/data/staging/nunoa_master_identity_preview")
DEFAULT_CANDIDATES = DEFAULT_PREVIEW_DIR / "athlete_link_candidates.csv"
DEFAULT_SQL_OUTPUT = DEFAULT_PREVIEW_DIR / "load_nunoa_master_athlete_links.sql"


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def load_link_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    link_rows = [
        row for row in rows if (row.get("decision") or "").strip().lower() == "link"
    ]
    if not link_rows:
        raise ValueError("No hay filas con decision=link.")

    person_ids = [row["person_id"] for row in link_rows]
    if len(person_ids) != len(set(person_ids)):
        raise ValueError("Hay mas de un link aprobado para la misma persona.")

    athlete_ids = [row["athlete_id"] for row in link_rows]
    if len(athlete_ids) != len(set(athlete_ids)):
        raise ValueError("Hay mas de una persona aprobada para el mismo atleta.")

    return link_rows


def render_values(rows: list[dict[str, str]]) -> str:
    values: list[str] = []
    for row in rows:
        values.append(
            "    ("
            + ", ".join(
                [
                    row["person_id"],
                    row["athlete_id"],
                    sql_literal(row.get("confidence") or "reviewed"),
                    sql_literal(row.get("person_name") or ""),
                    sql_literal(row.get("athlete_full_name") or ""),
                ]
            )
            + ")"
        )
    return ",\n".join(values)


def render_sql(rows: list[dict[str, str]]) -> str:
    values = render_values(rows)
    return f"""-- Generated from reviewed Ñuñoa Master athlete link decisions.
-- Contains person-athlete associations. Do not commit this file.

BEGIN;

CREATE TEMP TABLE reviewed_nunoa_athlete_link (
    person_id BIGINT PRIMARY KEY,
    athlete_id BIGINT NOT NULL UNIQUE,
    confidence_label TEXT NOT NULL,
    expected_person_name TEXT NOT NULL,
    expected_athlete_name TEXT NOT NULL
) ON COMMIT DROP;

INSERT INTO reviewed_nunoa_athlete_link (
    person_id,
    athlete_id,
    confidence_label,
    expected_person_name,
    expected_athlete_name
)
VALUES
{values};

DO $$
DECLARE
    missing_people INTEGER;
    missing_athletes INTEGER;
    not_active_nunoa_members INTEGER;
    duplicate_existing_person_links INTEGER;
    duplicate_existing_athlete_links INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO missing_people
    FROM reviewed_nunoa_athlete_link l
    LEFT JOIN identity.person p ON p.id = l.person_id
    WHERE p.id IS NULL;

    IF missing_people > 0 THEN
        RAISE EXCEPTION 'Reviewed links reference missing people: %', missing_people;
    END IF;

    SELECT COUNT(*)
    INTO missing_athletes
    FROM reviewed_nunoa_athlete_link l
    LEFT JOIN core.athlete a ON a.id = l.athlete_id
    WHERE a.id IS NULL;

    IF missing_athletes > 0 THEN
        RAISE EXCEPTION 'Reviewed links reference missing athletes: %', missing_athletes;
    END IF;

    SELECT COUNT(*)
    INTO not_active_nunoa_members
    FROM reviewed_nunoa_athlete_link l
    WHERE NOT EXISTS (
        SELECT 1
        FROM club_ops.membership m
        WHERE m.person_id = l.person_id
          AND m.club_id = 26
          AND m.status = 'active'
    );

    IF not_active_nunoa_members > 0 THEN
        RAISE EXCEPTION 'Reviewed links reference non-active Ñuñoa members: %', not_active_nunoa_members;
    END IF;

    SELECT COUNT(*)
    INTO duplicate_existing_person_links
    FROM reviewed_nunoa_athlete_link l
    JOIN core.athlete_person_link existing
      ON existing.person_id = l.person_id
     AND existing.athlete_id <> l.athlete_id;

    IF duplicate_existing_person_links > 0 THEN
        RAISE EXCEPTION 'Some people already link to a different athlete: %', duplicate_existing_person_links;
    END IF;

    SELECT COUNT(*)
    INTO duplicate_existing_athlete_links
    FROM reviewed_nunoa_athlete_link l
    JOIN core.athlete_person_link existing
      ON existing.athlete_id = l.athlete_id
     AND existing.person_id <> l.person_id;

    IF duplicate_existing_athlete_links > 0 THEN
        RAISE EXCEPTION 'Some athletes already link to a different person: %', duplicate_existing_athlete_links;
    END IF;
END $$;

INSERT INTO core.athlete_person_link (
    athlete_id,
    person_id,
    link_source,
    confidence,
    verified_at
)
SELECT
    athlete_id,
    person_id,
    'manual_club_registry',
    CASE confidence_label
        WHEN 'high' THEN 1.0000
        WHEN 'medium' THEN 0.8500
        ELSE 0.7500
    END,
    NOW()
FROM reviewed_nunoa_athlete_link l
WHERE NOT EXISTS (
    SELECT 1
    FROM core.athlete_person_link existing
    WHERE existing.athlete_id = l.athlete_id
      AND existing.person_id = l.person_id
);

COMMIT;
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare reviewed Ñuñoa athlete link SQL.")
    parser.add_argument("--candidates-csv", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--sql-output", default=str(DEFAULT_SQL_OUTPUT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_link_rows(Path(args.candidates_csv))
    output = Path(args.sql_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_sql(rows), encoding="utf-8")
    print(f"Generated {output} with {len(rows)} reviewed links. Do not commit.")


if __name__ == "__main__":
    main()
