import math
from typing import Optional

from fastapi import APIRouter, Query

from ..database import get_db_connection
from ..search import normalized_search_sql, search_tokens

router = APIRouter()


CURRENT_CATEGORY_SQL = """
    CASE
        WHEN a.birth_year IS NULL THEN 'Sin categoría'
        WHEN EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - a.birth_year < 25 THEN 'premaster'
        ELSE (
            ((EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - a.birth_year - 25) / 5)::INTEGER * 5 + 25
        )::TEXT || '-' || (
            ((EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - a.birth_year - 25) / 5)::INTEGER * 5 + 29
        )::TEXT
    END
"""

CURRENT_CATEGORY_MIN_AGE_SQL = """
    CASE
        WHEN a.birth_year IS NULL THEN NULL
        WHEN EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - a.birth_year < 25 THEN 0
        ELSE ((EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - a.birth_year - 25) / 5)::INTEGER * 5 + 25
    END
"""


@router.get("")
def list_rankings(
    distance_m: Optional[int] = Query(None, gt=0),
    stroke: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    age_group: Optional[str] = Query(None),
    course_type: Optional[str] = Query(None),
    year: Optional[int] = Query(None, ge=1900),
    competition_scope: Optional[str] = Query(None),
    athlete_search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            filters = [
                "r.status = 'valid'",
                "r.result_time_ms IS NOT NULL",
            ]
            params = {}

            if distance_m is not None:
                filters.append("e.distance_m = %(distance_m)s")
                params["distance_m"] = distance_m
            if stroke and stroke != "all":
                filters.append("e.stroke = %(stroke)s")
                params["stroke"] = stroke
            if gender and gender != "all":
                filters.append("e.gender = %(gender)s")
                params["gender"] = gender
            if age_group and age_group != "all":
                filters.append(f"({CURRENT_CATEGORY_SQL}) = %(age_group)s")
                params["age_group"] = age_group
            if course_type and course_type != "all":
                filters.append("comp.course_type = %(course_type)s")
                params["course_type"] = course_type
            if year is not None:
                filters.append("EXTRACT(YEAR FROM comp.start_date)::INTEGER = %(year)s")
                params["year"] = year
            else:
                filters.append("comp.start_date >= CURRENT_DATE - INTERVAL '1 year'")
            if competition_scope and competition_scope != "all":
                filters.append("comp.competition_scope = %(competition_scope)s")
                params["competition_scope"] = competition_scope

            ranked_filters = []
            for index, token in enumerate(search_tokens(athlete_search or "")):
                key = f"athlete_search_{index}"
                ranked_filters.append(f"{normalized_search_sql('athlete_name')} LIKE %({key})s")
                params[key] = f"%{token}%"
            ranked_where_clause = f"WHERE {' AND '.join(ranked_filters)}" if ranked_filters else ""

            where_clause = " AND ".join(filters)
            offset = (page - 1) * page_size
            params.update({"page_size": page_size, "offset": offset})

            base_cte = f"""
                WITH filtered AS (
                    SELECT
                        r.id,
                        r.athlete_id,
                        a.full_name AS athlete_name,
                        r.club_id,
                        club.name AS club_name,
                        REGEXP_REPLACE(r.result_time_text, '^[Xx]\\s*', '') AS time_text,
                        r.result_time_ms AS time_ms,
                        comp.id AS competition_id,
                        comp.name AS competition_name,
                        comp.start_date AS date,
                        e.distance_m,
                        e.stroke,
                        comp.course_type,
                        e.gender,
                        {CURRENT_CATEGORY_SQL} AS age_group,
                        COALESCE(e.age_group, 'Open') AS event_age_group,
                        a.birth_year,
                        EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - a.birth_year AS current_age,
                        ROW_NUMBER() OVER (
                            PARTITION BY r.athlete_id
                            ORDER BY r.result_time_ms ASC, comp.start_date DESC NULLS LAST, r.id DESC
                        ) AS athlete_best_rank
                    FROM core.result r
                    JOIN core.athlete a ON a.id = r.athlete_id
                    JOIN core.event e ON e.id = r.event_id
                    JOIN core.competition comp ON comp.id = e.competition_id
                    LEFT JOIN core.club club ON club.id = r.club_id
                    WHERE {where_clause}
                ),
                best_by_athlete AS (
                    SELECT *
                    FROM filtered
                    WHERE athlete_best_rank = 1
                ),
                ranked AS (
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY time_ms ASC, date DESC NULLS LAST, id DESC) AS rank,
                        *
                    FROM best_by_athlete
                ),
                searched AS (
                    SELECT *
                    FROM ranked
                    {ranked_where_clause}
                )
            """

            cur.execute(base_cte + "SELECT COUNT(*) AS total FROM searched", params)
            total_results = cur.fetchone()["total"]

            cur.execute(
                base_cte
                + """
                SELECT
                    rank,
                    athlete_name,
                    athlete_id,
                    club_name,
                    time_text,
                    time_ms,
                    competition_id,
                    competition_name,
                    date,
                    distance_m,
                    stroke,
                    course_type,
                    gender,
                    age_group,
                    event_age_group,
                    birth_year,
                    current_age
                FROM searched
                ORDER BY rank ASC
                LIMIT %(page_size)s OFFSET %(offset)s
                """,
                params,
            )
            rankings = cur.fetchall()

            total_pages = math.ceil(total_results / page_size) if total_results > 0 else 1
            return {
                "data": rankings,
                "meta": {
                    "total_results": total_results,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                },
            }


@router.get("/filter-options")
def get_ranking_filter_options():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT e.distance_m, e.stroke
                FROM core.event e
                JOIN core.result r ON r.event_id = e.id
                WHERE e.distance_m IS NOT NULL
                  AND e.stroke IS NOT NULL
                  AND e.stroke NOT LIKE '%_relay'
                  AND r.status = 'valid'
                  AND r.result_time_ms IS NOT NULL
                ORDER BY e.distance_m ASC, e.stroke ASC
            """)
            event_options = cur.fetchall()

            cur.execute("""
                SELECT DISTINCT e.distance_m
                FROM core.event e
                JOIN core.result r ON r.event_id = e.id
                WHERE e.distance_m IS NOT NULL
                  AND r.status = 'valid'
                  AND r.result_time_ms IS NOT NULL
                ORDER BY e.distance_m ASC
            """)
            distances = [row["distance_m"] for row in cur.fetchall()]

            cur.execute("""
                SELECT DISTINCT e.stroke
                FROM core.event e
                JOIN core.result r ON r.event_id = e.id
                WHERE e.stroke IS NOT NULL
                  AND e.stroke NOT LIKE '%_relay'
                  AND r.status = 'valid'
                  AND r.result_time_ms IS NOT NULL
                ORDER BY e.stroke ASC
            """)
            strokes = [row["stroke"] for row in cur.fetchall()]

            cur.execute(f"""
                WITH current_categories AS (
                    SELECT DISTINCT
                        {CURRENT_CATEGORY_SQL} AS age_group,
                        {CURRENT_CATEGORY_MIN_AGE_SQL} AS category_min_age
                    FROM core.result r
                    JOIN core.athlete a ON a.id = r.athlete_id
                    WHERE a.birth_year IS NOT NULL
                      AND r.status = 'valid'
                      AND r.result_time_ms IS NOT NULL
                )
                SELECT age_group
                FROM current_categories
                ORDER BY category_min_age ASC, age_group ASC
            """)
            age_groups = [row["age_group"] for row in cur.fetchall()]

            cur.execute("""
                SELECT DISTINCT EXTRACT(YEAR FROM comp.start_date)::INTEGER AS year
                FROM core.competition comp
                JOIN core.event e ON e.competition_id = comp.id
                JOIN core.result r ON r.event_id = e.id
                WHERE comp.start_date IS NOT NULL
                  AND r.status = 'valid'
                  AND r.result_time_ms IS NOT NULL
                ORDER BY year DESC
            """)
            years = [row["year"] for row in cur.fetchall()]

            cur.execute("""
                SELECT DISTINCT comp.competition_scope
                FROM core.competition comp
                JOIN core.event e ON e.competition_id = comp.id
                JOIN core.result r ON r.event_id = e.id
                WHERE comp.competition_scope IS NOT NULL
                  AND r.status = 'valid'
                  AND r.result_time_ms IS NOT NULL
                ORDER BY comp.competition_scope ASC
            """)
            scopes = [row["competition_scope"] for row in cur.fetchall()]

            return {
                "distances": distances,
                "strokes": strokes,
                "event_options": event_options,
                "age_groups": age_groups,
                "years": years,
                "scopes": scopes,
            }
