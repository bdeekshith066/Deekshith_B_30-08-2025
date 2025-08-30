# Unit tests for window utility functions (clip, merge, local→UTC, business windows).
# Validates overlap clipping and merging logic.
# Ensures overnight local windows (e.g. 23:00–02:00) convert correctly to UTC.
# Verifies 24x7 fallback and specific-day business hours produce correct intervals.


import math
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from app.utils.windows import (
    Interval, clip, merge_overlaps, local_window_to_utc, business_windows_utc
)

UTC = ZoneInfo("UTC")

def dt(y, m, d, hh, mm=0, ss=0, tz=UTC):
    return datetime(y, m, d, hh, mm, ss, tzinfo=tz)

def test_clip_and_merge():
    a = Interval(dt(2023,1,1,10), dt(2023,1,1,12))
    b = Interval(dt(2023,1,1,11), dt(2023,1,1,13))
    c = clip(a, b)
    assert c is not None
    assert c.start == dt(2023,1,1,11)
    assert c.end   == dt(2023,1,1,12)

    merged = merge_overlaps([a, b])
    assert len(merged) == 1
    assert merged[0].start == dt(2023,1,1,10)
    assert merged[0].end   == dt(2023,1,1,13)

def test_local_window_to_utc_overnight():
    # America/Chicago overnight window 23:00 -> 02:00 next day
    tz = ZoneInfo("America/Chicago")
    day_local = dt(2023,3,10,0,tz=tz)  # date is what matters
    ivs = local_window_to_utc(day_local, time(23,0), time(2,0), tz)
    assert len(ivs) == 2
    # total duration ~ 3h (180 min). Allow 1-second tolerance.
    total_sec = sum((iv.end - iv.start).total_seconds() for iv in ivs)
    assert abs(total_sec - 3*3600) < 2

def test_business_windows_24x7_returns_full_interval():
    start = dt(2023,1,2,9)
    end   = dt(2023,1,2,17)
    ivs = business_windows_utc(
        tzname="America/Chicago",
        hours_for_store={},  # missing => 24x7
        win_start_utc=start,
        win_end_utc=end,
    )
    assert len(ivs) == 1
    assert ivs[0].start == start and ivs[0].end == end

def test_business_windows_specific_day():
    # Store open 09:00–12:00 local on Monday only (0)
    tz = "America/Chicago"
    hours = {0: [(time(9,0), time(12,0))]}
    # Choose a UTC window that spans Monday local
    start = dt(2023,1,2,0)  # Monday UTC 00:00
    end   = dt(2023,1,3,0)  # Tuesday UTC 00:00
    ivs = business_windows_utc(tz, hours, start, end)
    # Expect exactly one interval of 3 hours in UTC (DST not involved here)
    total_hours = sum((iv.end - iv.start).total_seconds() for iv in ivs) / 3600
    assert abs(total_hours - 3.0) < 1e-6
