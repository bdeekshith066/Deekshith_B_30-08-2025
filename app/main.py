# app/main.py

# FastAPI application entrypoint for the store monitoring system.
# Includes health and report routers, and sets up database tables on startup.
# Uses SQLAlchemy Base metadata to auto-create tables if they don’t exist.
# Root endpoint shows available API routes for quick reference.

from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.report import router as report_router
from app.db import Base, engine
import app.models  # important: registers tables

app = FastAPI(title="Loop Store Monitor", version="0.1.0")
app.include_router(health_router, tags=["health"])
app.include_router(report_router, tags=["report"])

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def root():
    return {"status": "ok", "see": ["/healthz", "/trigger_report", "/get_report?report_id=..."]}
