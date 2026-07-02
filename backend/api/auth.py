import os
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

try:
    import jwt
    from jwt import PyJWKClient
except ImportError:  # pragma: no cover - exercised only when dependency is missing.
    jwt = None
    PyJWKClient = None


security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    provider: str
    subject: str
    email: str
    email_verified: bool
    claims: dict[str, Any]


def _jwt_decode_options(audience: Optional[str]) -> dict[str, bool]:
    return {
        "verify_aud": bool(audience),
        "verify_signature": True,
        "verify_exp": True,
    }


def verify_supabase_token(token: str) -> AuthenticatedUser:
    if jwt is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT validation dependency is not installed.",
        )

    audience = os.getenv("SUPABASE_JWT_AUDIENCE")
    issuer = os.getenv("SUPABASE_JWT_ISSUER")
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    jwks_url = os.getenv("SUPABASE_JWKS_URL")
    allowed_algorithms = [
        algorithm.strip()
        for algorithm in os.getenv("SUPABASE_JWT_ALGORITHMS", "RS256,ES256,HS256").split(",")
        if algorithm.strip()
    ]

    try:
        if jwt_secret:
            claims = jwt.decode(
                token,
                jwt_secret,
                algorithms=[algorithm for algorithm in allowed_algorithms if algorithm == "HS256"] or ["HS256"],
                audience=audience,
                issuer=issuer,
                options=_jwt_decode_options(audience),
            )
        elif jwks_url and PyJWKClient is not None:
            signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[algorithm for algorithm in allowed_algorithms if algorithm != "HS256"],
                audience=audience,
                issuer=issuer,
                options=_jwt_decode_options(audience),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Supabase JWT validation is not configured.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from exc

    subject = claims.get("sub")
    email = claims.get("email")
    if not subject or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing required user claims.",
        )

    return AuthenticatedUser(
        provider="supabase",
        subject=str(subject),
        email=str(email).strip().lower(),
        email_verified=bool(claims.get("email_verified")),
        claims=claims,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    return verify_supabase_token(credentials.credentials)
