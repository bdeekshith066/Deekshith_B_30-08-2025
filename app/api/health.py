# app/api/health.py

# Health check and debug endpoints.
# /healthz → verifies DB connectivity by running "SELECT 1".
# /debug/tables → lists all current SQLite tables for quick inspection.

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db import get_session

router = APIRouter()

@router.get("/healthz")
async def healthz(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"ok": True}

@router.get("/debug/tables")
async def debug_tables(session: AsyncSession = Depends(get_session)):
    q = text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    rows = (await session.execute(q)).scalars().all()
    return {"tables": rows}
