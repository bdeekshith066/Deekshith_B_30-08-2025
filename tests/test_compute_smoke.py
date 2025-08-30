# app/utils/test_compute_smoke.py

# Utility to build continuous status segments (active/inactive) within a time window.
# Normalizes all datetimes to UTC-aware to avoid timezone comparison issues.
# Converts raw status pings into step-function segments across [window_start, window_end).
# Used later to intersect with business-hour windows for uptime/downtime reporting.


from datetime import datetime
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")

def _to_utc_aware(dt: datetime) -> datetime:
    """
    Normalize datetime to UTC-aware.
    - If naive, assume it's already in UTC and attach tzinfo.
    - If aware, convert to UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def status_segments(statuses, window_start: datetime, window_end: datetime):
    """
    Build (start, end, status) segments from statuses within [window_start, window_end).
    All datetimes normalized to UTC-aware to avoid offset-naive vs offset-aware comparison errors.

    Args:
        statuses: Iterable of objects with .timestamp_utc and .status
        window_start (datetime): inclusive lower bound
        window_end (datetime): exclusive upper bound

    Returns:
        List of (start, end, status) tuples
    """
    window_start = _to_utc_aware(window_start)
    window_end   = _to_utc_aware(window_end)

    # Normalize all DB status timestamps to UTC
    norm_statuses = [
        (_to_utc_aware(s.timestamp_utc), s.status)
        for s in statuses
    ]
    norm_statuses.sort(key=lambda x: x[0])

    segments = []
    prev_time = window_start
    prev_status = None

    for ts, status in norm_statuses:
        if ts < window_start:
            prev_status = status
            continue
        if ts >= window_end:
            break
        if prev_status is not None:
            segments.append((prev_time, ts, prev_status))
        prev_time = ts
        prev_status = status

    if prev_status is not None and prev_time < window_end:
        segments.append((prev_time, window_end, prev_status))

    return segments
    