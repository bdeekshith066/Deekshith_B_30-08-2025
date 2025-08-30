# Core computation service: generates uptime/downtime metrics per store.
# Converts business hours (local) to UTC, builds status segments from pings.
# Intersects status with business-hour windows to accumulate active/inactive durations.
# Writes final report rows into a CSV with last hour/day/week uptime & downtime. 


from __future__ import annotations
from datetime import datetime, timedelta, time
from typing import Dict, List, Tuple
import csv
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import BusinessHours, StoreTimezone, StoreStatus
from app.utils.windows import business_windows_utc, Interval
from app.utils.segments import status_segments

DEFAULT_TZ = "America/Chicago"

async def _max_now(session: AsyncSession) -> datetime:
    now = (await session.execute(select(func.max(StoreStatus.timestamp_utc)))).scalar()
    if now is None:
        raise RuntimeError("No observations in store_status.")
    # ensure UTC-aware
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("UTC"))
    else:
        now = now.astimezone(ZoneInfo("UTC"))
    return now

async def _store_ids(session: AsyncSession) -> list[str]:
    rows = (await session.execute(select(StoreStatus.store_id).distinct())).scalars().all()
    tz_only = (await session.execute(select(StoreTimezone.store_id))).scalars().all()
    return sorted(set(rows) | set(tz_only))

async def _hours_map(session: AsyncSession, store_id: str) -> Dict[int, List[Tuple[time, time]]]:
    rows = (await session.execute(
        select(BusinessHours.day_of_week, BusinessHours.start_time_local, BusinessHours.end_time_local)
        .where(BusinessHours.store_id == store_id)
    )).all()
    out: Dict[int, List[Tuple[time, time]]] = {}
    for dow, st, et in rows:
        st_t = time.fromisoformat(st) if ":" in st else time.fromisoformat(f"{st}:00")
        et_t = time.fromisoformat(et) if ":" in et else time.fromisoformat(f"{et}:00")
        out.setdefault(dow, []).append((st_t, et_t))
    return out  # empty => 24x7

async def _tz_for(session: AsyncSession, store_id: str) -> str:
    tz = await session.get(StoreTimezone, store_id)
    return tz.timezone_str if tz else DEFAULT_TZ

def _accumulate(segs, biz: list[Interval]) -> tuple[float, float]:
    """Return (active_minutes, inactive_minutes) intersected with business windows."""
    active = 0.0; inactive = 0.0
    for bw in biz:
        for s in segs:
            # intersection
            start = max(bw.start, s.start); end = min(bw.end, s.end)
            if start >= end: 
                continue
            mins = (end - start).total_seconds() / 60.0
            if s.status == "active": active += mins
            else: inactive += mins
    return active, inactive

async def compute_and_write_csv(session: AsyncSession, csv_path: str) -> None:
    now = await _max_now(session)

    last_hour = (now - timedelta(hours=1), now)
    last_day  = (now - timedelta(days=1),  now)
    last_week = (now - timedelta(days=7),  now)

    stores = await _store_ids(session)

    rows = []
    for sid in stores:
        tzname = await _tz_for(session, sid)
        hours = await _hours_map(session, sid)

        # business windows
        bw_h = business_windows_utc(tzname, hours, *last_hour)
        bw_d = business_windows_utc(tzname, hours, *last_day)
        bw_w = business_windows_utc(tzname, hours, *last_week)

        # status segments
        seg_h = await status_segments(session, sid, *last_hour)
        seg_d = await status_segments(session, sid, *last_day)
        seg_w = await status_segments(session, sid, *last_week)

        a_m_h, i_m_h = _accumulate(seg_h, bw_h)
        a_h_d, i_h_d = _accumulate(seg_d, bw_d)
        a_h_w, i_h_w = _accumulate(seg_w, bw_w)

        rows.append({
            "store_id": sid,
            "uptime_last_hour(in minutes)": round(a_m_h, 2),
            "uptime_last_day(in hours)": round(a_h_d/60.0, 2),
            "update_last_week(in hours)": round(a_h_w/60.0, 2),  # keep exact spec key
            "downtime_last_hour(in minutes)": round(i_m_h, 2),
            "downtime_last_day(in hours)": round(i_h_d/60.0, 2),
            "downtime_last_week(in hours)": round(i_h_w/60.0, 2),
        })

    # write CSV
    if rows:
        fieldnames = list(rows[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
