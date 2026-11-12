"""Choose the date ranges the daily refresh fetches."""

from datetime import date, timedelta

# Refresh window: the 7 complete days before today come from the Forecast API (provisional).
# The 7 days before that (8 to 14 days ago) come from the historical API (final values).
FORECAST_FIRST_DAYS_AGO = 7
ARCHIVE_FIRST_DAYS_AGO = 14
ARCHIVE_LAST_DAYS_AGO = 8


def _range(today: date, first_days_ago: int, last_days_ago: int) -> tuple[str, str]:
    start = today - timedelta(days=first_days_ago)
    end = today - timedelta(days=last_days_ago)
    return start.isoformat(), end.isoformat()


def refresh_windows(today: date) -> dict[str, tuple[str, str]]:
    """Return the inclusive (start, end) date range per source; today itself is excluded."""
    return {
        "forecast": _range(today, FORECAST_FIRST_DAYS_AGO, 1),
        "archive": _range(today, ARCHIVE_FIRST_DAYS_AGO, ARCHIVE_LAST_DAYS_AGO),
    }
