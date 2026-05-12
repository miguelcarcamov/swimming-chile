from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import athletes, clubs, competitions

app = FastAPI(title="Natación Chile API", version="0.1.0")

# Permitir CORS para desarrollo local del frontend (Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(athletes.router, prefix="/api/athletes", tags=["athletes"])
app.include_router(clubs.router, prefix="/api/clubs", tags=["clubs"])
app.include_router(competitions.router, prefix="/api/competitions", tags=["competitions"])

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "API running"}
