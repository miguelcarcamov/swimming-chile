import math
from typing import Optional

from fastapi import APIRouter, Query

from ..database import get_db_connection

router = APIRouter()


@router.get("/clubs/participation")
def list_club_participation(
    year: Optional[int] = Query(None, ge=1900),
    competition_scope: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            filters = [
                "r.club_id IS NOT NULL",
                "COALESCE(r.status, 'unknown') NOT IN ('dns', 'scratch')",
            ]
            params = {}

            if year is not None:
                filters.append("EXTRACT(YEAR FROM comp.start_date)::INTEGER = %(year)s")
                params["year"] = year
            if competition_scope and competition_scope != "all":
                filters.append("comp.competition_scope = %(competition_scope)s")
                params["competition_scope"] = competition_scope

            where_clause = " AND ".join(filters)
            offset = (page - 1) * page_size
            params.update({"page_size": page_size, "offset": offset})

            base_cte = f"""
                WITH club_participation AS (
                    SELECT
                        club.id AS club_id,
                        club.name AS club_name,
                        COUNT(DISTINCT r.athlete_id)::INTEGER AS unique_athletes,
                        COUNT(DISTINCT comp.id)::INTEGER AS competitions_count,
                        COUNT(*)::INTEGER AS entries_count
                    FROM core.result r
                    JOIN core.event e ON e.id = r.event_id
                    JOIN core.competition comp ON comp.id = e.competition_id
                    JOIN core.club club ON club.id = r.club_id
                    WHERE {where_clause}
                    GROUP BY club.id, club.name
                )
            """

            cur.execute(base_cte + "SELECT COUNT(*) AS total FROM club_participation", params)
            total_results = cur.fetchone()["total"]

            cur.execute(
                base_cte
                + """
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY unique_athletes DESC, competitions_count DESC, entries_count DESC, club_name ASC
                    ) AS rank,
                    club_id,
                    club_name,
                    unique_athletes,
                    competitions_count,
                    entries_count
                FROM club_participation
                ORDER BY rank ASC
                LIMIT %(page_size)s OFFSET %(offset)s
                """,
                params,
            )
            clubs = cur.fetchall()

            total_pages = math.ceil(total_results / page_size) if total_results > 0 else 1
            return {
                "data": clubs,
                "meta": {
                    "total_results": total_results,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                },
            }
