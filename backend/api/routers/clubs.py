import math
from fastapi import APIRouter, Query
from typing import Optional
from ..database import get_db_connection

router = APIRouter()

@router.get("")
def list_clubs(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            offset = (page - 1) * page_size
            
            query = """
                SELECT c.id, c.name, c.short_name as city, c.region as country, c.association_name,
                       (SELECT count(*) FROM core.athlete a WHERE a.club_id = c.id) as total_athletes
                FROM core.club c 
                WHERE EXISTS (SELECT 1 FROM core.athlete a WHERE a.club_id = c.id)
            """
            count_query = "SELECT COUNT(*) as total FROM core.club c WHERE EXISTS (SELECT 1 FROM core.athlete a WHERE a.club_id = c.id)"
            params = []
            
            if search:
                query += " AND (c.name ILIKE %s OR c.short_name ILIKE %s)"
                count_query += " AND (c.name ILIKE %s OR c.short_name ILIKE %s)"
                params.extend([f"%{search}%", f"%{search}%"])
                
            query += " ORDER BY c.name LIMIT %s OFFSET %s"
            
            cur.execute(count_query, params)
            total_results = cur.fetchone()['total']
            
            params.extend([page_size, offset])
            cur.execute(query, params)
            clubs = cur.fetchall()
            
            total_pages = math.ceil(total_results / page_size) if total_results > 0 else 1
            
            return {
                "data": clubs,
                "meta": {
                    "total_results": total_results,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages
                }
            }

from fastapi import HTTPException

@router.get("/{club_id}")
def get_club(club_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.name, c.short_name as city, c.region as country, c.association_name,
                       (SELECT count(*) FROM core.athlete a WHERE a.club_id = c.id) as total_athletes
                FROM core.club c
                WHERE c.id = %s
            """, (club_id,))
            club = cur.fetchone()
            
            if not club:
                raise HTTPException(status_code=404, detail="Club not found")
            
            return club
