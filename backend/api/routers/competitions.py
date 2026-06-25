import math
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from ..database import get_db_connection

router = APIRouter()

@router.get("")
def list_competitions(
    search: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None, description="upcoming or past"),
    competition_scope: Optional[str] = Query(None, description="Curated competition scope, e.g. fchmn_local"),
    governing_body: Optional[str] = Query(None, description="Governing body code, e.g. fchmn or consada"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            offset = (page - 1) * page_size
            
            query = "SELECT id, name, start_date as date_start, end_date as date_end, city as location, region as country, course_type, competition_scope, governing_body_code, governing_body_name, organizer FROM core.competition WHERE 1=1"
            count_query = "SELECT COUNT(*) as total FROM core.competition WHERE 1=1"
            params = []
            
            if search:
                query += " AND (name ILIKE %s OR city ILIKE %s)"
                count_query += " AND (name ILIKE %s OR city ILIKE %s)"
                params.extend([f"%{search}%", f"%{search}%"])
                
            if year and year != 'all':
                query += " AND CAST(EXTRACT(YEAR FROM start_date) AS TEXT) = %s"
                count_query += " AND CAST(EXTRACT(YEAR FROM start_date) AS TEXT) = %s"
                params.append(year)

            if competition_scope and competition_scope != 'all':
                query += " AND competition_scope = %s"
                count_query += " AND competition_scope = %s"
                params.append(competition_scope)

            if governing_body and governing_body != 'all':
                query += " AND governing_body_code = %s"
                count_query += " AND governing_body_code = %s"
                params.append(governing_body)
                
            if timeframe == 'upcoming':
                query += " AND start_date >= CURRENT_DATE"
                count_query += " AND start_date >= CURRENT_DATE"
                query += " ORDER BY start_date ASC LIMIT %s OFFSET %s"
            elif timeframe == 'past':
                query += " AND start_date < CURRENT_DATE"
                count_query += " AND start_date < CURRENT_DATE"
                query += " ORDER BY start_date DESC LIMIT %s OFFSET %s"
            else:
                query += " ORDER BY start_date DESC LIMIT %s OFFSET %s"
            
            cur.execute(count_query, params)
            total_results = cur.fetchone()['total']
            
            params.extend([page_size, offset])
            cur.execute(query, params)
            competitions = cur.fetchall()
            
            total_pages = math.ceil(total_results / page_size) if total_results > 0 else 1
            
            return {
                "data": competitions,
                "meta": {
                    "total_results": total_results,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages
                }
            }

@router.get("/years")
def get_competition_years():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT CAST(EXTRACT(YEAR FROM start_date) AS INTEGER) as year 
                FROM core.competition 
                WHERE start_date < CURRENT_DATE
                ORDER BY year DESC
            """)
            years = [row['year'] for row in cur.fetchall()]
            return {"years": years}

@router.get("/filter-options")
def get_competition_filter_options(
    timeframe: Optional[str] = Query(None, description="upcoming or past"),
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            timeframe_filter = ""
            params = []
            if timeframe == "upcoming":
                timeframe_filter = " AND start_date >= CURRENT_DATE"
            elif timeframe == "past":
                timeframe_filter = " AND start_date < CURRENT_DATE"

            cur.execute("""
                SELECT DISTINCT CAST(EXTRACT(YEAR FROM start_date) AS INTEGER) as year
                FROM core.competition
                WHERE start_date IS NOT NULL
            """ + timeframe_filter + """
                ORDER BY year DESC
            """, params)
            years = [row['year'] for row in cur.fetchall()]

            cur.execute("""
                SELECT DISTINCT competition_scope
                FROM core.competition
                WHERE competition_scope IS NOT NULL
            """ + timeframe_filter + """
                ORDER BY competition_scope ASC
            """, params)
            scopes = [row['competition_scope'] for row in cur.fetchall()]

            cur.execute("""
                SELECT DISTINCT governing_body_code, governing_body_name
                FROM core.competition
                WHERE governing_body_code IS NOT NULL
            """ + timeframe_filter + """
                ORDER BY governing_body_name ASC NULLS LAST, governing_body_code ASC
            """, params)
            governing_bodies = cur.fetchall()

            return {
                "years": years,
                "scopes": scopes,
                "governing_bodies": governing_bodies,
            }

@router.get("/{competition_id}")
def get_competition(competition_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    c.id,
                    c.name,
                    c.start_date as date_start,
                    c.city as location,
                    c.course_type,
                    c.competition_scope,
                    c.governing_body_code,
                    c.governing_body_name,
                    c.organizer,
                    COALESCE(c.source_url, latest_doc.source_url) as source_url
                FROM core.competition c
                LEFT JOIN LATERAL (
                    SELECT sd.source_url
                    FROM core.load_run lr
                    JOIN core.source_document sd ON sd.id = lr.source_document_id
                    WHERE lr.competition_id = c.id
                      AND sd.source_url IS NOT NULL
                    ORDER BY lr.completed_at DESC NULLS LAST, lr.started_at DESC NULLS LAST, lr.id DESC
                    LIMIT 1
                ) latest_doc ON TRUE
                WHERE c.id = %s
            """, (competition_id,))
            competition = cur.fetchone()
            
            if not competition:
                raise HTTPException(status_code=404, detail="Competition not found")
                
            cur.execute("""
                SELECT 
                    id, distance_m, stroke, gender, age_group 
                FROM core.event 
                WHERE competition_id = %s
                ORDER BY distance_m ASC
            """, (competition_id,))
            events_rows = cur.fetchall()
            
            events = []
            for e in events_rows:
                age_grp = e['age_group']
                
                cur.execute("""
                    SELECT 
                        r.rank_position as rank, a.full_name as athlete_name, a.id as athlete_id,
                        c.name as club_name, r.result_time_text as time_text, r.status,
                        r.result_time_ms
                    FROM core.result r
                    JOIN core.athlete a ON r.athlete_id = a.id
                    LEFT JOIN core.club c ON r.club_id = c.id
                    WHERE r.event_id = %(event_id)s
                    
                    UNION ALL
                    
                    SELECT 
                        rr.rank_position as rank, rr.relay_team_name as athlete_name, NULL::bigint as athlete_id,
                        c.name as club_name, rr.result_time_text as time_text, rr.status,
                        rr.result_time_ms
                    FROM core.relay_result rr
                    LEFT JOIN core.club c ON rr.club_id = c.id
                    WHERE rr.event_id = %(event_id)s
                    
                    ORDER BY result_time_ms ASC NULLS LAST
                """, {'event_id': e['id']})
                results = cur.fetchall()
                
                events.append({
                    "id": e['id'],
                    "distance_m": e['distance_m'],
                    "stroke": e['stroke'],
                    "gender": e['gender'],
                    "age_group": age_grp or "Open",
                    "results": results
                })
                
            return {
                "competition": competition,
                "events": events
            }
