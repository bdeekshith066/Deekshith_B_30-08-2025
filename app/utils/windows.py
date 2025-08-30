# app/utils/windows.py

# Utilities for building UTC business-hour windows from local store schedules.
# Handles same-day and overnight windows, with proper timezone conversion (ZoneInfo).
# Provides helpers to clip intervals to a range and merge overlapping intervals.
# Used to generate business-hour intervals for uptime/downtime calculations.

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import Iterable, List, Tuple
from zoneinfo import ZoneInfo

@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

def clip(a: Interval, b: Interval) -> Interval | None:
    s = max(a.start, b.start)
    e = min(a.end, b.end)
    return None if s >= e else Interval(s, e)

def merge_overlaps(intervals: Iterable[Interval]) -> List[Interval]:
    xs = sorted(intervals, key=lambda i: i.start)
    out: List[Interval] = []
    for iv in xs:
        if not out or iv.start > out[-1].end:
            out.append(iv)
        else:
            out[-1] = Interval(out[-1].start, max(out[-1].end, iv.end))
    return out

def local_window_to_utc(day_local: datetime, st: time, et: time, tz: ZoneInfo) -> List[Interval]:
    """
    Return 1–2 UTC intervals for a single *local* day business window.
    Handles overnight spans (e.g., 23:00 -> 02:00 next day).
    """
    base = day_local.date()
    start_local = datetime.combine(base, st).replace(tzinfo=tz)
    end_same    = datetime.combine(base, et).replace(tzinfo=tz)

    if st <= et:
        # same-day window
        return [Interval(start_local.astimezone(ZoneInfo("UTC")),
                         end_same.astimezone(ZoneInfo("UTC")))]
    else:
        # overnight window: split across day boundary
        end_of_day_local   = datetime.combine(base, time(23, 59, 59, 999_999)).replace(tzinfo=tz)
        start_next_local   = datetime.combine(base + timedelta(days=1), time(0, 0)).replace(tzinfo=tz)
        end_same_next      = datetime.combine(base + timedelta(days=1), et).replace(tzinfo=tz)  # ✅ was missing

        return [
            Interval(start_local.astimezone(ZoneInfo("UTC")),
                     end_of_day_local.astimezone(ZoneInfo("UTC"))),
            Interval(start_next_local.astimezone(ZoneInfo("UTC")),
                     end_same_next.astimezone(ZoneInfo("UTC"))),
        ]

def business_windows_utc(
    tzname: str | None,
    hours_for_store: dict[int, list[tuple[time, time]]] | None,
    win_start_utc: datetime,
    win_end_utc: datetime,
) -> List[Interval]:
    """Build UTC business windows for [win_start_utc, win_end_utc). If hours missing → 24x7."""
    if win_start_utc >= win_end_utc:
        return []
    if not hours_for_store:
        return [Interval(win_start_utc, win_end_utc)]
    tz = ZoneInfo(tzname or "America/Chicago")
    out: list[Interval] = []
    cur_local = win_start_utc.astimezone(tz)
    end_local = win_end_utc.astimezone(tz)
    day = cur_local.replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= end_local:
        dow = day.weekday()  # 0=Mon
        for st, et in hours_for_store.get(dow, []):
            for iv in local_window_to_utc(day, st, et, tz):
                clipped = clip(iv, Interval(win_start_utc, win_end_utc))
                if clipped:
                    out.append(clipped)
        day += timedelta(days=1)
    return merge_overlaps(out)
