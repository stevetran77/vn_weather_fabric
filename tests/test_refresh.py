from datetime import date

import refresh


def test_refresh_windows_for_a_normal_day():
    windows = refresh.refresh_windows(date(2026, 11, 12))
    assert windows["forecast"] == ("2026-11-05", "2026-11-11")
    assert windows["archive"] == ("2026-10-29", "2026-11-04")


def test_refresh_windows_exclude_today_and_do_not_overlap():
    today = date(2026, 11, 12)
    windows = refresh.refresh_windows(today)
    assert windows["forecast"][1] < today.isoformat()
    assert windows["archive"][1] < windows["forecast"][0]


def test_refresh_windows_are_contiguous():
    windows = refresh.refresh_windows(date(2026, 11, 12))
    assert date.fromisoformat(windows["archive"][1]).toordinal() + 1 == (
        date.fromisoformat(windows["forecast"][0]).toordinal()
    )


def test_refresh_windows_each_cover_seven_days():
    windows = refresh.refresh_windows(date(2026, 3, 1))  # crosses February
    for start, end in windows.values():
        assert (date.fromisoformat(end) - date.fromisoformat(start)).days + 1 == 7
    assert windows["archive"] == ("2026-02-15", "2026-02-21")
