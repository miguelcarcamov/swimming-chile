import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import athletes, clubs, competitions, relays

app = FastAPI(title="SwimStats Chile API", version="0.1.0")


def get_allowed_origins() -> list[str]:
    raw_origins = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


# CORS is restricted through ALLOWED_ORIGINS for deploys; keep localhost as the dev default.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(athletes.router, prefix="/api/athletes", tags=["athletes"])
app.include_router(clubs.router, prefix="/api/clubs", tags=["clubs"])
app.include_router(competitions.router, prefix="/api/competitions", tags=["competitions"])
app.include_router(relays.router, prefix="/api/relays", tags=["relays"])


@app.get("/")
def root():
    return {"status": "ok", "service": "SwimStats Chile API"}


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "API running"}
