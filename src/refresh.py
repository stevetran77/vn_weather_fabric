"""Choose the date ranges the refresh fetches and label each hour with its source."""

from datetime import UTC, date, datetime, timedelta

# Refresh window: the Forecast API covers the 7 days before today and all of today. Hours that
# are over are `provisional`, hours still to come are `forecast`. The historical API covers the
# 7 days before that (8 to 14 days ago); those hours are final (`archive`).
RECENT_FIRST_DAYS_AGO = 7
ARCHIVE_FIRST_DAYS_AGO = 14
ARCHIVE_LAST_DAYS_AGO = 8

ARCHIVE = "archive"
PROVISIONAL = "provisional"
FORECAST = "forecast"


def resolve_now(run_time: str = "") -> datetime:
    """Return `run_time` (ISO, UTC) as an aware UTC datetime, or the current time if empty."""
    if not run_time:
        return datetime.now(UTC)
    return datetime.fromisoformat(run_time).replace(tzinfo=UTC)


def _range(today: date, first_days_ago: int, last_days_ago: int) -> tuple[str, str]:
    start = today - timedelta(days=first_days_ago)
    end = today - timedelta(days=last_days_ago)
    return start.isoformat(), end.isoformat()


def refresh_windows(today: date) -> dict[str, tuple[str, str]]:
    """Return the inclusive (start, end) date range per API: `recent` includes today."""
    return {
        "recent": _range(today, RECENT_FIRST_DAYS_AGO, 0),
        "archive": _range(today, ARCHIVE_FIRST_DAYS_AGO, ARCHIVE_LAST_DAYS_AGO),
    }


def is_future(ts: datetime, now: datetime) -> bool:
    """True when the hour starting at `ts` has not finished yet at `now` (both timezone-aware)."""
    return ts + timedelta(hours=1) > now


def label_recent_source(ts: datetime, now: datetime) -> str:
    """Label an hour from the Forecast API: `forecast` if still to come, else `provisional`."""
    return FORECAST if is_future(ts, now) else PROVISIONAL


def drop_future_hours(rows: list[dict], now: datetime) -> list[dict]:
    """Keep only the rows whose hour is over (Silver holds no predictions)."""
    return [row for row in rows if not is_future(row["ts"], now)]
