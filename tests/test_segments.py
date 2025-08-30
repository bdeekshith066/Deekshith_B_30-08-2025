# app/utils/segments.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, asc
from app.models import StoreStatus

UTC = ZoneInfo("UTC")

@dataclass(frozen=True)
class Seg:
    start: datetime
    end: datetime
    status: str  # "active" | "inactive"

def _aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

async def status_segments(session: AsyncSession, store_id: str, start: datetime, end: datetime) -> List[Seg]:
    # ✅ normalize window bounds as well
    start = _aware_utc(start)
    end   = _aware_utc(end)

    if start >= end:
        return []

    # pings inside window
    rows = (await session.execute(
        select(StoreStatus.timestamp_utc, StoreStatus.status)
        .where(StoreStatus.store_id == store_id)
        .where(StoreStatus.timestamp_utc >= start)
        .where(StoreStatus.timestamp_utc < end)
        .order_by(asc(StoreStatus.timestamp_utc))
    )).all()

    # normalize DB timestamps to UTC-aware
    rows = [(_aware_utc(ts), st) for ts, st in rows]

    # previous ping before start
    prev = (await session.execute(
        select(StoreStatus.timestamp_utc, StoreStatus.status)
        .where(StoreStatus.store_id == store_id)
        .where(StoreStatus.timestamp_utc < start)
        .order_by(desc(StoreStatus.timestamp_utc))
        .limit(1)
    )).first()
    prev_norm = (_aware_utc(prev[0]), prev[1]) if prev else None

    if prev_norm:
        curr = prev_norm[1].value if hasattr(prev_norm[1], "value") else prev_norm[1]
    elif rows:
        curr = rows[0][1].value if hasattr(rows[0][1], "value") else rows[0][1]
    else:
        return [Seg(start, end, "inactive")]

    segs: List[Seg] = []
    cursor = start
    for ts, st in rows:
        st_val = st.value if hasattr(st, "value") else st
        if ts > cursor:
            segs.append(Seg(cursor, ts, curr))
        cursor = ts
        curr = st_val
    if cursor < end:
        segs.append(Seg(cursor, end, curr))
    return segs
