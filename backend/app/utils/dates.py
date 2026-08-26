# app/utils/dates.py

from datetime import datetime, timezone, timedelta


def resolve_date_range(range_key, date_from_arg, date_to_arg):
    """
    Turns a `range` shortcut (today/this_week/this_month) OR explicit
    date_from/date_to query params into concrete UTC datetime bounds.

    Server-clock-based -- a known simplification for a single-timezone
    campus deployment; a multi-timezone deployment would need the
    client's local day boundary instead.

    Shared by any endpoint offering a "today / this week / this month"
    filter (e.g. vitals, health file forward counts) so the day/week/
    month boundary logic only lives in one place.
    """
    now = datetime.now(timezone.utc)

    if range_key == "today":
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        return start, start + timedelta(days=1)

    if range_key == "this_week":
        start_of_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        start = start_of_today - timedelta(days=start_of_today.weekday())  # Monday
        return start, start + timedelta(days=7)

    if range_key == "this_month":
        start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        next_month, next_year = (start.month % 12) + 1, start.year + (start.month == 12)
        return start, datetime(next_year, next_month, 1, tzinfo=timezone.utc)

    if range_key == "this_year":
        start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
        return start, datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)

    date_from = datetime.fromisoformat(date_from_arg) if date_from_arg else None
    date_to   = datetime.fromisoformat(date_to_arg) if date_to_arg else None
    return date_from, date_to