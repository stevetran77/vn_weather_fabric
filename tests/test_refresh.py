from datetime import UTC, date, datetime

import refresh

NOW = datetime(2026, 11, 12, 10, 30, tzinfo=UTC)


def test_resolve_now_returns_the_current_utc_time_when_run_time_is_empty():
    before = datetime.now(UTC)
    now = refresh.resolve_now()
    assert before <= now <= datetime.now(UTC)
    assert now.utcoffset().total_seconds() == 0


def test_resolve_now_parses_run_time_as_utc():
    assert refresh.resolve_now("2026-11-12T10:30") == NOW


def test_refresh_windows_for_a_normal_day():
    windows = refresh.refresh_windows(date(2026, 11, 12))
    assert windows["recent"] == ("2026-11-05", "2026-11-12")
    assert windows["archive"] == ("2026-10-29", "2026-11-04")


def test_recent_window_includes_today_and_archive_ends_before_it_starts():
    windows = refresh.refresh_windows(date(2026, 11, 12))
    assert windows["recent"][1] == "2026-11-12"
    assert windows["archive"][1] < windows["recent"][0]


def test_refresh_windows_are_contiguous():
    windows = refresh.refresh_windows(date(2026, 11, 12))
    archive_end = date.fromisoformat(windows["archive"][1])
    recent_start = date.fromisoformat(windows["recent"][0])
    assert archive_end.toordinal() + 1 == recent_start.toordinal()


def test_refresh_windows_cross_a_month_boundary():
    windows = refresh.refresh_windows(date(2026, 3, 1))
    assert windows["recent"] == ("2026-02-22", "2026-03-01")
    assert windows["archive"] == ("2026-02-15", "2026-02-21")


def test_is_future_for_finished_current_and_coming_hours():
    assert not refresh.is_future(datetime(2026, 11, 12, 9, tzinfo=UTC), NOW)  # ended 10:00
    assert refresh.is_future(datetime(2026, 11, 12, 10, tzinfo=UTC), NOW)  # 10:00-11:00 running
    assert refresh.is_future(datetime(2026, 11, 12, 23, tzinfo=UTC), NOW)


def test_hour_that_ends_exactly_now_is_over():
    assert not refresh.is_future(datetime(2026, 11, 12, 9, 30, tzinfo=UTC), NOW)


def test_label_recent_source():
    assert refresh.label_recent_source(datetime(2026, 11, 11, 23, tzinfo=UTC), NOW) == "provisional"
    assert refresh.label_recent_source(datetime(2026, 11, 12, 15, tzinfo=UTC), NOW) == "forecast"


def test_drop_future_hours_keeps_only_finished_hours():
    rows = [
        {"ts": datetime(2026, 11, 12, 8, tzinfo=UTC)},
        {"ts": datetime(2026, 11, 12, 10, tzinfo=UTC)},
        {"ts": datetime(2026, 11, 12, 20, tzinfo=UTC)},
    ]
    assert refresh.drop_future_hours(rows, NOW) == rows[:1]
