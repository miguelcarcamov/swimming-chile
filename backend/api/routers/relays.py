from io import BytesIO

from fastapi import APIRouter, Body, HTTPException, Query

from natacion_chile.relays import (
    COMPETITION_YEAR,
    STROKES,
    RelayAthlete,
    RelayTime,
    analyze_athletes,
    analyze_upload,
    best_time_key,
    normalize_name,
    normalize_name_match_key,
    normalize_rut,
    parse_entries_workbook,
    relay_distance_m,
    roster_response,
)
from ..database import get_db_connection

router = APIRouter()


def has_membership_schema(cur) -> bool:
    cur.execute("""
        SELECT
            to_regclass('club_ops.membership') IS NOT NULL
            AND to_regclass('core.athlete_person_link') IS NOT NULL AS available
    """)
    return bool(cur.fetchone()["available"])


def empty_times() -> dict[str, RelayTime]:
    return {stroke: RelayTime(ms=None, source="missing") for stroke in STROKES}


def load_club_roster(club_id: int) -> list[RelayAthlete]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if has_membership_schema(cur):
                cur.execute(
                    """
                    SELECT DISTINCT ON (a.id)
                        a.id,
                        a.full_name,
                        a.gender,
                        a.birth_year,
                        p.rut_normalized
                    FROM core.athlete a
                    JOIN (
                        SELECT DISTINCT apl.athlete_id, m.person_id
                        FROM club_ops.membership m
                        JOIN core.athlete_person_link apl ON apl.person_id = m.person_id
                        WHERE m.club_id = %(club_id)s
                          AND m.status = 'active'

                        UNION

                        SELECT acc.athlete_id, apl.person_id
                        FROM core.athlete_current_club acc
                        LEFT JOIN core.athlete_person_link apl ON apl.athlete_id = acc.athlete_id
                        WHERE acc.club_id = %(club_id)s
                          AND NOT EXISTS (
                              SELECT 1
                              FROM club_ops.membership mx
                              WHERE mx.club_id = %(club_id)s
                          )
                    ) roster ON roster.athlete_id = a.id
                    LEFT JOIN identity.person p ON p.id = roster.person_id
                    WHERE a.gender IN ('female', 'male')
                    ORDER BY a.id, a.full_name, p.rut_normalized NULLS LAST
                    """,
                    {"club_id": club_id},
                )
            else:
                cur.execute(
                    """
                    SELECT
                        a.id,
                        a.full_name,
                        a.gender,
                        a.birth_year,
                        p.rut_normalized
                    FROM core.athlete a
                    JOIN core.athlete_current_club acc ON acc.athlete_id = a.id
                    LEFT JOIN core.athlete_person_link apl ON apl.athlete_id = a.id
                    LEFT JOIN identity.person p ON p.id = apl.person_id
                    WHERE acc.club_id = %s
                      AND a.gender IN ('female', 'male')
                    ORDER BY a.full_name, p.rut_normalized NULLS LAST
                    """,
                    (club_id,),
                )
            rows = cur.fetchall()

    athletes: list[RelayAthlete] = []
    seen_ids: set[int] = set()
    for row in rows:
        if row["id"] in seen_ids:
            continue
        seen_ids.add(row["id"])
        birth_year = row["birth_year"]
        athletes.append(
            RelayAthlete(
                id=str(row["id"]),
                full_name=row["full_name"],
                normalized_name=normalize_name(row["full_name"]),
                gender=row["gender"],
                birth_date=None,
                birth_year=birth_year,
                age=COMPETITION_YEAR - birth_year if birth_year else None,
                rut=row["rut_normalized"],
                core_athlete_id=row["id"],
                times=empty_times(),
            )
        )
    return athletes


def load_db_best_times_for_athlete_ids(athlete_ids: list[int], distance_m: int) -> dict[int, dict[str, RelayTime]]:
    if not athlete_ids:
        return {}
    best_times: dict[int, dict[str, RelayTime]] = {}
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    a.id AS athlete_core_id,
                    e.stroke,
                    r.result_time_ms,
                    r.result_time_text,
                    c.name AS competition_name,
                    c.start_date AS competition_date
                FROM core.result r
                JOIN core.athlete a ON a.id = r.athlete_id
                JOIN core.event e ON e.id = r.event_id
                JOIN core.competition c ON c.id = e.competition_id
                WHERE r.result_time_ms IS NOT NULL
                  AND r.status = 'valid'
                  AND e.distance_m = %s
                  AND e.stroke = ANY(%s)
                  AND a.id = ANY(%s)
                ORDER BY r.result_time_ms ASC
                """,
                (distance_m, list(STROKES), athlete_ids),
            )
            rows = cur.fetchall()

    for row in rows:
        athlete_id = row["athlete_core_id"]
        stroke = row["stroke"]
        if stroke in best_times.get(athlete_id, {}):
            continue
        competition_date = row["competition_date"]
        best_times.setdefault(athlete_id, {})[stroke] = RelayTime(
            ms=row["result_time_ms"],
            text=row["result_time_text"],
            source="db",
            athlete_core_id=athlete_id,
            competition_name=row["competition_name"],
            competition_date=competition_date.isoformat() if competition_date else None,
        )
    return best_times


def apply_db_times_to_roster(athletes: list[RelayAthlete], relay_type: str) -> list[RelayAthlete]:
    best_times = load_db_best_times_for_athlete_ids([
        athlete.core_athlete_id for athlete in athletes if athlete.core_athlete_id is not None
    ], relay_distance_m(relay_type))
    enriched: list[RelayAthlete] = []
    for athlete in athletes:
        times = empty_times()
        if athlete.core_athlete_id is not None:
            times.update(best_times.get(athlete.core_athlete_id, {}))
        enriched.append(
            RelayAthlete(
                id=athlete.id,
                full_name=athlete.full_name,
                normalized_name=athlete.normalized_name,
                gender=athlete.gender,
                birth_date=athlete.birth_date,
                birth_year=athlete.birth_year,
                age=athlete.age,
                rut=athlete.rut,
                core_athlete_id=athlete.core_athlete_id,
                times=times,
            )
        )
    return enriched


def attendance_keys_from_excel(file_bytes: bytes) -> tuple[set[str], set[tuple[str, str, int | None]]]:
    if not file_bytes:
        return set(), set()
    participants = parse_entries_workbook(BytesIO(file_bytes))
    rut_keys = {normalize_rut(athlete.rut) for athlete in participants if normalize_rut(athlete.rut)}
    fallback_keys = {
        (normalize_name_match_key(athlete.full_name), athlete.gender, athlete.birth_year)
        for athlete in participants
        if athlete.gender in {"female", "male"}
    }
    return rut_keys, fallback_keys


def filter_roster_by_attendance(athletes: list[RelayAthlete], attendance: tuple[set[str], set[tuple[str, str, int | None]]]) -> list[RelayAthlete]:
    rut_keys, fallback_keys = attendance
    if not rut_keys and not fallback_keys:
        return athletes
    rut_matched = [athlete for athlete in athletes if athlete.rut and normalize_rut(athlete.rut) in rut_keys]
    if rut_matched:
        return rut_matched
    return [
        athlete
        for athlete in athletes
        if (normalize_name_match_key(athlete.full_name), athlete.gender, athlete.birth_year) in fallback_keys
    ]


def filter_roster_by_athlete_ids(athletes: list[RelayAthlete], athlete_ids: list[int]) -> list[RelayAthlete]:
    if not athlete_ids:
        return athletes
    allowed = {str(athlete_id) for athlete_id in athlete_ids}
    return [athlete for athlete in athletes if athlete.id in allowed]


def load_db_best_times(file_bytes: bytes, relay_type: str) -> dict[tuple[str, str, int | None, str], RelayTime]:
    participants = parse_entries_workbook(BytesIO(file_bytes))
    genders = sorted({athlete.gender for athlete in participants if athlete.gender in {"female", "male"}})
    birth_years = sorted({athlete.birth_year for athlete in participants if athlete.birth_year is not None})
    if not genders or not birth_years:
        return {}

    participant_keys = {
        (normalize_name_match_key(athlete.full_name), athlete.gender, athlete.birth_year)
        for athlete in participants
        if athlete.gender in {"female", "male"} and athlete.birth_year is not None
    }
    best_times: dict[tuple[str, str, int | None, str], RelayTime] = {}
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    a.id AS athlete_core_id,
                    a.full_name,
                    a.gender,
                    a.birth_year,
                    e.stroke,
                    r.result_time_ms,
                    r.result_time_text,
                    c.name AS competition_name,
                    c.start_date AS competition_date
                FROM core.result r
                JOIN core.athlete a ON a.id = r.athlete_id
                JOIN core.event e ON e.id = r.event_id
                JOIN core.competition c ON c.id = e.competition_id
                WHERE r.result_time_ms IS NOT NULL
                  AND r.status = 'valid'
                  AND e.distance_m = %s
                  AND e.stroke = ANY(%s)
                  AND a.gender = ANY(%s)
                  AND a.birth_year = ANY(%s)
                ORDER BY r.result_time_ms ASC
                """,
                (relay_distance_m(relay_type), list(STROKES), genders, birth_years),
            )
            rows = cur.fetchall()

    for row in rows:
        participant_key = best_time_key(row["full_name"], row["gender"], row["birth_year"], row["stroke"])
        identity_key = participant_key[:3]
        if identity_key not in participant_keys or participant_key in best_times:
            continue
        competition_date = row["competition_date"]
        best_times[participant_key] = RelayTime(
            ms=row["result_time_ms"],
            text=row["result_time_text"],
            source="db",
            athlete_core_id=row["athlete_core_id"],
            competition_name=row["competition_name"],
            competition_date=competition_date.isoformat() if competition_date else None,
        )
    return best_times


def club_roster(club_id: int, relay_type: str, attendance_file_bytes: bytes = b"", athlete_ids: list[int] | None = None) -> list[RelayAthlete]:
    roster = load_club_roster(club_id)
    if athlete_ids:
        roster = filter_roster_by_athlete_ids(roster, athlete_ids)
    if attendance_file_bytes:
        roster = filter_roster_by_attendance(roster, attendance_keys_from_excel(attendance_file_bytes))
    return apply_db_times_to_roster(roster, relay_type)


def analyze_club_roster(
    club_id: int,
    relay_type: str,
    attendance_file_bytes: bytes = b"",
    athlete_ids: list[int] | None = None,
    excluded_category_keys: set[str] | None = None,
):
    return analyze_athletes(
        club_roster(club_id, relay_type, attendance_file_bytes, athlete_ids),
        relay_type,
        excluded_category_keys=excluded_category_keys,
    )


@router.get("/club-roster")
def get_club_relay_roster(
    club_id: int = Query(..., ge=1),
    relay_type: str = Query("4x50_medley_mixed"),
):
    try:
        return roster_response(club_roster(club_id, relay_type), relay_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/club-roster")
async def get_filtered_club_relay_roster(
    club_id: int = Query(..., ge=1),
    relay_type: str = Query("4x50_medley_mixed"),
    file_bytes: bytes = Body(default=b"", media_type="application/octet-stream"),
):
    try:
        return roster_response(club_roster(club_id, relay_type, attendance_file_bytes=file_bytes), relay_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/analyze")
async def analyze_relays(
    filename: str = Query("entries.xlsx"),
    relay_type: str = Query("4x50_medley_mixed"),
    club_id: int | None = Query(None, ge=1),
    athlete_ids: list[int] = Query(default=[]),
    excluded_category_keys: list[str] = Query(default=[]),
    file_bytes: bytes = Body(default=b"", media_type="application/octet-stream"),
):
    try:
        excluded_categories = set(excluded_category_keys)
        if club_id is not None:
            return analyze_club_roster(club_id, relay_type, file_bytes, athlete_ids, excluded_categories)
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Debes seleccionar un club o subir un Excel de asistencia")
        if not filename.lower().endswith((".xlsx", ".xlsm")):
            raise HTTPException(status_code=400, detail="El archivo debe ser Excel .xlsx o .xlsm")
        db_best_times = load_db_best_times(file_bytes, relay_type)
        return analyze_upload(filename, BytesIO(file_bytes), relay_type=relay_type, db_best_times=db_best_times, excluded_category_keys=excluded_categories)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
