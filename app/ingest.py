# app/ingest.py

# Ingestion script to load CSV data into the database.
# Reads and normalizes store_status, business_hours, and store_timezone CSVs.
# Bulk inserts rows into tables with cleanup/replacement as needed.
# Automatically detects CSV files if env vars are missing.
# Prints row counts and the max timestamp (used as "now" in report generation).

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Iterable

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import engine, SessionLocal
import app.models as models  # ensure models are registered


# ---------- helpers ----------

DEFAULT_TZ = "America/Chicago"

def _norm_status(val: str) -> str:
    s = str(val).strip().lower()
    if s in {"active", "1", "up", "online", "true"}:
        return "active"
    return "inactive"

def _read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV not found: {path}")
    return pd.read_csv(path)

def _ensure_time_str(x: str) -> str:
    """Return HH:MM:SS string from 'H:M'/'H:M:S'."""
    try:
        return pd.to_datetime(str(x)).strftime("%H:%M:%S")
    except Exception:
        # last resort: append :00 if just HH:MM
        return pd.to_datetime(f"{x}:00").strftime("%H:%M:%S")


async def _bulk_insert_store_status(session: AsyncSession, df: pd.DataFrame, chunk: int = 50_000) -> int:
    df = df.copy()
    # normalize columns
    df.columns = [c.strip().lower() for c in df.columns]
    if "timestamp_utc" not in df.columns:
        if "timestamp" in df.columns:
            df.rename(columns={"timestamp": "timestamp_utc"}, inplace=True)
        else:
            raise ValueError("store_status CSV must have 'timestamp_utc' (UTC).")

    # normalize values
    df["store_id"] = df["store_id"].astype(str)
    df["status"] = df["status"].map(_norm_status)
    # timezone-aware UTC
    ts = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["timestamp_utc"] = ts.dt.strftime("%Y-%m-%d %H:%M:%S%z")  # pass as string to SQL

    total = 0
    for i in range(0, len(df), chunk):
        sub = df.iloc[i : i + chunk]
        # NOTE: using parameterized executemany for speed & compatibility
        await session.execute(
            text("""
                INSERT INTO store_status (store_id, timestamp_utc, status)
                VALUES (:store_id, :timestamp_utc, :status)
            """),
            sub[["store_id", "timestamp_utc", "status"]].to_dict(orient="records"),
        )
        await session.commit()
        total += len(sub)
        print(f"Inserted store_status rows: {total}/{len(df)}")
    return total


async def _bulk_insert_business_hours(session: AsyncSession, df: pd.DataFrame) -> int:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    if "dayofweek" not in df.columns:
        for c in ("day_of_week", "day", "dow"):
            if c in df.columns:
                df.rename(columns={c: "dayofweek"}, inplace=True)
                break
    if "dayofweek" not in df.columns:
        raise ValueError("business hours CSV must contain 'dayOfWeek' (0=Mon..6=Sun).")

    df["store_id"] = df["store_id"].astype(str)
    df["dayofweek"] = df["dayofweek"].astype(int)
    df["start_time_local"] = df["start_time_local"].map(_ensure_time_str)
    df["end_time_local"] = df["end_time_local"].map(_ensure_time_str)

    # Insert
    await session.execute(
        text("""
            DELETE FROM business_hours
        """)
    )
    await session.commit()

    await session.execute(
        text("""
            INSERT INTO business_hours (store_id, day_of_week, start_time_local, end_time_local)
            VALUES (:store_id, :day_of_week, :start_time_local, :end_time_local)
        """),
        df.rename(columns={"dayofweek":"day_of_week"})[
            ["store_id","day_of_week","start_time_local","end_time_local"]
        ].to_dict(orient="records"),
    )
    await session.commit()
    print(f"Inserted business_hours rows: {len(df)}")
    return len(df)


async def _bulk_insert_timezones(session: AsyncSession, df: pd.DataFrame) -> int:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    if "timezone_str" not in df.columns and "timezone" in df.columns:
        df.rename(columns={"timezone": "timezone_str"}, inplace=True)

    df["store_id"] = df["store_id"].astype(str)
    df["timezone_str"] = df["timezone_str"].fillna(DEFAULT_TZ).astype(str)

    # Replace (upsert simple)
    await session.execute(text("DELETE FROM store_timezone"))
    await session.commit()

    await session.execute(
        text("""
            INSERT INTO store_timezone (store_id, timezone_str)
            VALUES (:store_id, :timezone_str)
        """),
        df[["store_id","timezone_str"]].to_dict(orient="records"),
    )
    await session.commit()
    print(f"Inserted store_timezone rows: {len(df)}")
    return len(df)


# ---------- public entrypoint ----------

async def ingest(status_csv: str, hours_csv: str, tz_csv: str) -> None:
    # create tables if not present (safe)
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

    async with SessionLocal() as session:
        # read
        df_status = _read_csv(status_csv)
        df_hours  = _read_csv(hours_csv)
        df_tz     = _read_csv(tz_csv)

        # insert
        n1 = await _bulk_insert_store_status(session, df_status)
        n2 = await _bulk_insert_business_hours(session, df_hours)
        n3 = await _bulk_insert_timezones(session, df_tz)

        # show max timestamp ("now" per spec)
        res = await session.execute(text("SELECT MAX(timestamp_utc) FROM store_status"))
        max_ts = res.scalar()
        print(f"\nIngest complete. Rows => status:{n1} hours:{n2} tz:{n3}")
        print(f"Spec 'now' (max timestamp_utc): {max_ts}")


def _auto_find(csvs: Iterable[str]) -> dict[str,str]:
    """
    If env vars are not set, try to resolve the three CSVs by common names in cwd.
    """
    names = {os.path.basename(p).lower(): p for p in csvs}
    found = {"status": None, "hours": None, "tz": None}
    for path in csvs:
        low = os.path.basename(path).lower()
        if "status" in low:
            found["status"] = path
        elif ("menu" in low and "hour" in low) or ("business" in low and "hour" in low) or low.endswith("hours.csv"):
            found["hours"] = path
        elif "timezone" in low or ("time" in low and "zone" in low):
            found["tz"] = path
    return found  # may contain None values


if __name__ == "__main__":
    # Prefer env vars; else try to locate CSVs in current folder.
    status_csv = settings.STATUS_CSV or ""
    hours_csv  = settings.HOURS_CSV or ""
    tz_csv     = settings.TZ_CSV or ""

    if not (status_csv and hours_csv and tz_csv):
        # search current directory for csvs
        cwd_csvs = [os.path.join(os.getcwd(), f) for f in os.listdir(os.getcwd()) if f.lower().endswith(".csv")]
        guess = _auto_find(cwd_csvs)
        status_csv = status_csv or (guess["status"] or "")
        hours_csv  = hours_csv or (guess["hours"]  or "")
        tz_csv     = tz_csv or (guess["tz"]       or "")

    if not (status_csv and hours_csv and tz_csv):
        raise SystemExit(
            "Set CSV paths via .env (STATUS_CSV, HOURS_CSV, TZ_CSV) or place the three CSVs in this folder "
            "with recognizable names (status / hours / timezone)."
        )

    print(f"Using:\n  STATUS_CSV={status_csv}\n  HOURS_CSV={hours_csv}\n  TZ_CSV={tz_csv}\n")
    asyncio.run(ingest(status_csv, hours_csv, tz_csv))
