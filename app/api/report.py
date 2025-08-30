# app/api/report.py

# Report API endpoints for store monitoring system.
# /trigger_report → creates a new report job, stores it in DB, and starts background CSV computation.
# Background job (_run_job) runs compute_and_write_csv, then updates job status (Complete/Failed).
# /get_report → polls job status: returns "Running", "Failed", or streams the generated CSV.
# Implements trigger + poll architecture for asynchronous report generations

from __future__ import annotations
import os
from uuid import uuid4
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.models import ReportJob
from sqlalchemy import select
from app.services.compute import compute_and_write_csv

REPORT_DIR = "reports"
os.makedirs(REPORT_DIR, exist_ok=True)

router = APIRouter()

async def _run_job(report_id: str, session_factory):
    # new session for background work
    async for session in session_factory():
        try:
            csv_path = os.path.join(REPORT_DIR, f"{report_id}.csv")
            await compute_and_write_csv(session, csv_path)
            job = await session.get(ReportJob, report_id)
            if job:
                job.status = "Complete"
                job.csv_path = csv_path
                await session.commit()
        except Exception:
            job = await session.get(ReportJob, report_id)
            if job:
                job.status = "Failed"
                await session.commit()
        finally:
            break

@router.post("/trigger_report")
async def trigger_report(background: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    report_id = uuid4().hex
    session.add(ReportJob(report_id=report_id, status="Running", csv_path=None))
    await session.commit()
    background.add_task(_run_job, report_id, get_session)
    return {"report_id": report_id}

@router.get("/get_report")
async def get_report(report_id: str, status_only: bool = False, session: AsyncSession = Depends(get_session)):
    job = await session.get(ReportJob, report_id)
    if not job:
        raise HTTPException(status_code=404, detail="report_id not found")
    if job.status == "Running":
        return PlainTextResponse("Running")
    if job.status == "Failed":
        return PlainTextResponse("Failed")
    if status_only:
        return PlainTextResponse("Complete")
    if not job.csv_path or not os.path.exists(job.csv_path):
        raise HTTPException(status_code=500, detail="CSV not found")
    return FileResponse(job.csv_path, media_type="text/csv", filename="store_uptime_report.csv")

