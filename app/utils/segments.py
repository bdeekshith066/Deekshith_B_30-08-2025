# app/utils/segments.py

# Builds continuous status segments (active/inactive) for a store over a time window.
# Uses last ping before the window to seed initial status, else defaults to inactive.
# Converts sparse ping data into step-function segments covering [start, end).
# Output segments are later intersected with business-hour windows for uptime/downtime.

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, asc
from app.models import StoreStatus

@dataclass(frozen=True)
class Seg:
    start: datetime
    end: datetime
    status: str  # "active" | "inactive"

async def status_segments(session: AsyncSession, store_id: str, start: datetime, end: datetime) -> List[Seg]:
    """Step function from pings across [start, end). Seeds from previous ping; backfills; persists last."""
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

    # previous ping
    prev = (await session.execute(
        select(StoreStatus.timestamp_utc, StoreStatus.status)
        .where(StoreStatus.store_id == store_id)
        .where(StoreStatus.timestamp_utc < start)
        .order_by(desc(StoreStatus.timestamp_utc))
        .limit(1)
    )).first()

    segs: List[Seg] = []
    if prev:
        curr = prev[1].value if hasattr(prev[1], "value") else prev[1]
    elif rows:
        curr = rows[0][1].value if hasattr(rows[0][1], "value") else rows[0][1]
    else:
        return [Seg(start, end, "inactive")]

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
