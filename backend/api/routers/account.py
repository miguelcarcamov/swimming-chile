from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb

from ..auth import AuthenticatedUser, get_current_user
from ..database import get_db_connection

router = APIRouter()


class AccountResponse(BaseModel):
    id: int
    email: str
    status: str
    person_id: int
    roles: list[dict[str, Any]] = Field(default_factory=list)


class FavoritesResponse(BaseModel):
    athletes: list[dict[str, Any]] = Field(default_factory=list)
    clubs: list[dict[str, Any]] = Field(default_factory=list)


class AthleteClaimRequestIn(BaseModel):
    athlete_id: int
    evidence_message: str = Field(min_length=1)
    declared_club_name: Optional[str] = None
    contact_hint: Optional[str] = None


class AthleteClaimReviewIn(BaseModel):
    status: Literal["approved", "rejected"]
    review_notes: Optional[str] = None


class ProfileContributionIn(BaseModel):
    athlete_id: Optional[int] = None
    club_id: Optional[int] = None
    contribution_type: Literal["athlete_profile", "club_profile", "result_correction", "other"]
    payload: dict[str, Any]


def _ensure_user_account(cur, current_user: AuthenticatedUser) -> dict[str, Any]:
    cur.execute(
        """
        SELECT id, person_id, email, status
        FROM auth.user_account
        WHERE external_provider = %s
          AND external_subject = %s
        """,
        (current_user.provider, current_user.subject),
    )
    account = cur.fetchone()
    if account:
        if account["email"] != current_user.email:
            cur.execute(
                """
                UPDATE auth.user_account
                SET email = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (current_user.email, account["id"]),
            )
            account["email"] = current_user.email
        return account

    cur.execute(
        """
        INSERT INTO identity.person (data_source)
        VALUES (%s)
        RETURNING id
        """,
        ("supabase_auth",),
    )
    person_id = cur.fetchone()["id"]

    cur.execute(
        """
        INSERT INTO auth.user_account (
            person_id, email, status, external_provider, external_subject
        )
        VALUES (%s, %s, 'active', %s, %s)
        RETURNING id, person_id, email, status
        """,
        (person_id, current_user.email, current_user.provider, current_user.subject),
    )
    account = cur.fetchone()

    cur.execute(
        """
        INSERT INTO identity.contact_point (
            person_id, contact_type, contact_value, is_primary, verified_at
        )
        VALUES (%s, 'email', %s, TRUE, CASE WHEN %s THEN NOW() ELSE NULL END)
        ON CONFLICT (person_id, contact_type, LOWER(TRIM(contact_value))) DO NOTHING
        """,
        (person_id, current_user.email, current_user.email_verified),
    )

    return account


def _current_account(cur, current_user: AuthenticatedUser) -> dict[str, Any]:
    account = _ensure_user_account(cur, current_user)
    cur.execute(
        """
        SELECT id, club_id, role
        FROM auth.user_role
        WHERE user_id = %s
        ORDER BY role, club_id
        """,
        (account["id"],),
    )
    account["roles"] = cur.fetchall()
    return account


def _require_review_permission(cur, reviewer_account: dict[str, Any], claim_id: int) -> None:
    roles = reviewer_account.get("roles", [])
    if any(role["role"] == "platform_admin" for role in roles):
        return

    club_role_ids = {
        role["club_id"]
        for role in roles
        if role["role"] in ("club_admin", "club_manager") and role["club_id"] is not None
    }
    if not club_role_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer role required.")

    cur.execute(
        """
        SELECT acc.club_id
        FROM auth.athlete_claim_request acr
        JOIN core.athlete_current_club acc ON acc.athlete_id = acr.athlete_id
        WHERE acr.id = %s
        """,
        (claim_id,),
    )
    row = cur.fetchone()
    if not row or row["club_id"] not in club_role_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer role required.")


@router.get("", response_model=AccountResponse)
def get_me(current_user: AuthenticatedUser = Depends(get_current_user)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            account = _current_account(cur, current_user)
            conn.commit()
            return account


@router.get("/favorites", response_model=FavoritesResponse)
def get_favorites(current_user: AuthenticatedUser = Depends(get_current_user)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            account = _ensure_user_account(cur, current_user)

            cur.execute(
                """
                SELECT a.id, a.full_name, a.gender, a.birth_year,
                       acc.club_id AS current_club_id,
                       acc.club_name AS current_club_name,
                       fav.created_at
                FROM auth.user_athlete_favorite fav
                JOIN core.athlete a ON a.id = fav.athlete_id
                LEFT JOIN core.athlete_current_club acc ON acc.athlete_id = a.id
                WHERE fav.user_id = %s
                ORDER BY fav.created_at DESC
                """,
                (account["id"],),
            )
            athletes = cur.fetchall()

            cur.execute(
                """
                SELECT c.id, c.name, c.city, c.region AS country, fav.created_at
                FROM auth.user_club_favorite fav
                JOIN core.club c ON c.id = fav.club_id
                WHERE fav.user_id = %s
                ORDER BY fav.created_at DESC
                """,
                (account["id"],),
            )
            clubs = cur.fetchall()
            conn.commit()
            return {"athletes": athletes, "clubs": clubs}


@router.post("/favorites/athletes/{athlete_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_athlete_favorite(athlete_id: int, current_user: AuthenticatedUser = Depends(get_current_user)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            account = _ensure_user_account(cur, current_user)
            cur.execute("SELECT 1 FROM core.athlete WHERE id = %s", (athlete_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Athlete not found")
            cur.execute(
                """
                INSERT INTO auth.user_athlete_favorite (user_id, athlete_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (account["id"], athlete_id),
            )
            conn.commit()


@router.delete("/favorites/athletes/{athlete_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_athlete_favorite(athlete_id: int, current_user: AuthenticatedUser = Depends(get_current_user)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            account = _ensure_user_account(cur, current_user)
            cur.execute(
                "DELETE FROM auth.user_athlete_favorite WHERE user_id = %s AND athlete_id = %s",
                (account["id"], athlete_id),
            )
            conn.commit()


@router.post("/favorites/clubs/{club_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_club_favorite(club_id: int, current_user: AuthenticatedUser = Depends(get_current_user)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            account = _ensure_user_account(cur, current_user)
            cur.execute("SELECT 1 FROM core.club WHERE id = %s", (club_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Club not found")
            cur.execute(
                """
                INSERT INTO auth.user_club_favorite (user_id, club_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (account["id"], club_id),
            )
            conn.commit()


@router.delete("/favorites/clubs/{club_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_club_favorite(club_id: int, current_user: AuthenticatedUser = Depends(get_current_user)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            account = _ensure_user_account(cur, current_user)
            cur.execute(
                "DELETE FROM auth.user_club_favorite WHERE user_id = %s AND club_id = %s",
                (account["id"], club_id),
            )
            conn.commit()


@router.get("/athlete-claims")
def list_athlete_claims(current_user: AuthenticatedUser = Depends(get_current_user)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            account = _ensure_user_account(cur, current_user)
            cur.execute(
                """
                SELECT acr.id, acr.athlete_id, a.full_name AS athlete_name,
                       acr.status, acr.evidence_message, acr.declared_club_name,
                       acr.contact_hint, acr.review_notes, acr.created_at, acr.reviewed_at
                FROM auth.athlete_claim_request acr
                JOIN core.athlete a ON a.id = acr.athlete_id
                WHERE acr.user_id = %s
                ORDER BY acr.created_at DESC
                """,
                (account["id"],),
            )
            conn.commit()
            return {"data": cur.fetchall()}


@router.post("/athlete-claims", status_code=status.HTTP_201_CREATED)
def create_athlete_claim(
    payload: AthleteClaimRequestIn,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            account = _ensure_user_account(cur, current_user)
            cur.execute("SELECT 1 FROM core.athlete WHERE id = %s", (payload.athlete_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Athlete not found")
            cur.execute(
                """
                INSERT INTO auth.athlete_claim_request (
                    user_id, athlete_id, evidence_message, declared_club_name, contact_hint
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, athlete_id, status, evidence_message, declared_club_name,
                          contact_hint, created_at
                """,
                (
                    account["id"],
                    payload.athlete_id,
                    payload.evidence_message.strip(),
                    payload.declared_club_name,
                    payload.contact_hint,
                ),
            )
            claim = cur.fetchone()
            conn.commit()
            return claim


@router.patch("/athlete-claims/{claim_id}/review")
def review_athlete_claim(
    claim_id: int,
    payload: AthleteClaimReviewIn,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            reviewer = _current_account(cur, current_user)
            _require_review_permission(cur, reviewer, claim_id)

            cur.execute(
                """
                SELECT acr.id, acr.user_id, acr.athlete_id, ua.person_id
                FROM auth.athlete_claim_request acr
                JOIN auth.user_account ua ON ua.id = acr.user_id
                WHERE acr.id = %s
                  AND acr.status = 'pending'
                FOR UPDATE
                """,
                (claim_id,),
            )
            claim = cur.fetchone()
            if not claim:
                raise HTTPException(status_code=404, detail="Pending claim not found")

            cur.execute(
                """
                UPDATE auth.athlete_claim_request
                SET status = %s,
                    reviewed_by_user_id = %s,
                    reviewed_at = NOW(),
                    review_notes = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, athlete_id, status, reviewed_at, review_notes
                """,
                (payload.status, reviewer["id"], payload.review_notes, claim_id),
            )
            reviewed = cur.fetchone()

            if payload.status == "approved":
                cur.execute(
                    """
                    INSERT INTO core.athlete_person_link (
                        athlete_id, person_id, link_source, confidence, verified_at
                    )
                    VALUES (%s, %s, 'self_claim', 1.0, NOW())
                    ON CONFLICT (athlete_id, person_id)
                    DO UPDATE SET
                        link_source = 'admin_verified',
                        confidence = 1.0,
                        verified_at = NOW()
                    """,
                    (claim["athlete_id"], claim["person_id"]),
                )

            conn.commit()
            return reviewed


@router.get("/contributions")
def list_contributions(current_user: AuthenticatedUser = Depends(get_current_user)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            account = _ensure_user_account(cur, current_user)
            cur.execute(
                """
                SELECT id, athlete_id, club_id, contribution_type, payload, status,
                       review_notes, created_at, reviewed_at
                FROM auth.profile_contribution
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (account["id"],),
            )
            conn.commit()
            return {"data": cur.fetchall()}


@router.post("/contributions", status_code=status.HTTP_201_CREATED)
def create_contribution(
    payload: ProfileContributionIn,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    if (payload.athlete_id is None) == (payload.club_id is None):
        raise HTTPException(status_code=422, detail="Provide exactly one contribution target.")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            account = _ensure_user_account(cur, current_user)
            if payload.athlete_id is not None:
                cur.execute("SELECT 1 FROM core.athlete WHERE id = %s", (payload.athlete_id,))
            else:
                cur.execute("SELECT 1 FROM core.club WHERE id = %s", (payload.club_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Contribution target not found")

            cur.execute(
                """
                INSERT INTO auth.profile_contribution (
                    user_id, athlete_id, club_id, contribution_type, payload
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, athlete_id, club_id, contribution_type, payload, status, created_at
                """,
                (
                    account["id"],
                    payload.athlete_id,
                    payload.club_id,
                    payload.contribution_type,
                    Jsonb(payload.payload),
                ),
            )
            contribution = cur.fetchone()
            conn.commit()
            return contribution
