"""Plan the Backfill requests and build the date dimension."""

from datetime import date, timedelta

# Open-Meteo counts one API call per location for up to 140 (variables x days); longer ranges
# count as several calls. This is FITTED to X-RateLimit-Cost headers measured on 2026-11-12
# (see ticket 03: 1 var x 365 d = 2.607, 4 vars x 365 d = 10.43, 4 vars x 1522 d = 43.49,
# 7 d = 1, 3 locations = 3); it is not documented by Open-Meteo, so treat estimates as a plan only.
FITTED_VARIABLE_DAYS_PER_CALL = 140

MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _parse_range(start_date: str, end_date: str) -> tuple[date, date]:
    """Parse an inclusive YYYY-MM-DD range and reject a reversed one."""
    first, last = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if last < first:
        raise ValueError("end_date is before start_date")
    return first, last


def date_chunks(start_date: str, end_date: str, days_per_chunk: int) -> list[tuple[str, str]]:
    """Split an inclusive YYYY-MM-DD range into consecutive chunks of at most N days."""
    if days_per_chunk < 1:
        raise ValueError("days_per_chunk must be at least 1")
    cursor, last = _parse_range(start_date, end_date)
    chunks = []
    while cursor <= last:
        chunk_end = min(cursor + timedelta(days=days_per_chunk - 1), last)
        chunks.append((cursor.isoformat(), chunk_end.isoformat()))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def plan_requests(
    cities: list[dict],
    start_date: str,
    end_date: str,
    days_per_chunk: int,
    cities_per_request: int,
) -> list[dict]:
    """List the requests that cover every City and day: one per (city batch, date chunk)."""
    if cities_per_request < 1:
        raise ValueError("cities_per_request must be at least 1")
    chunks = date_chunks(start_date, end_date, days_per_chunk)
    batches = [
        cities[index : index + cities_per_request]
        for index in range(0, len(cities), cities_per_request)
    ]
    return [
        {"cities": batch, "start_date": chunk_start, "end_date": chunk_end}
        for batch in batches
        for chunk_start, chunk_end in chunks
    ]


def estimate_cost(location_count: int, variable_count: int, day_count: int) -> float:
    """Estimate the Open-Meteo calls one request costs (at least 1 per location)."""
    return location_count * max(1.0, variable_count * day_count / FITTED_VARIABLE_DAYS_PER_CALL)


def estimate_plan_cost(plan: list[dict], variable_count: int) -> float:
    """Estimate the total Open-Meteo calls of a request plan for one API."""
    total = 0.0
    for request in plan:
        days = (
            date.fromisoformat(request["end_date"]) - date.fromisoformat(request["start_date"])
        ).days + 1
        total += estimate_cost(len(request["cities"]), variable_count, days)
    return total


def build_dim_date(start_date: str, end_date: str) -> list[dict]:
    """Build one dim_date row per local calendar day in the inclusive range."""
    first, last = _parse_range(start_date, end_date)
    rows = []
    for offset in range((last - first).days + 1):
        day = first + timedelta(days=offset)
        weekday = day.weekday()
        rows.append(
            {
                "date_key": day.year * 10000 + day.month * 100 + day.day,
                "date": day,
                "year": day.year,
                "quarter": (day.month - 1) // 3 + 1,
                "month": day.month,
                "month_name": MONTH_NAMES[day.month - 1],
                "day": day.day,
                "day_of_week": weekday + 1,
                "day_name": DAY_NAMES[weekday],
                "is_weekend": weekday >= 5,
            }
        )
    return rows
