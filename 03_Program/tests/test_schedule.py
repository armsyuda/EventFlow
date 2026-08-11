from __future__ import annotations

from datetime import date

import pytest

from event_checklist.schedule import calculate_schedule, d_day_label


def test_start_anchor_and_leap_year():
    result = calculate_schedule(date(2028, 3, 1), None, "START", -2, 0)
    assert result.planned_start == date(2028, 2, 28)
    assert result.due_date == date(2028, 3, 1)


def test_end_anchor_uses_event_end():
    result = calculate_schedule(date(2026, 10, 2), date(2026, 10, 3), "END", 1, 30)
    assert result.planned_start == date(2026, 10, 4)
    assert result.due_date == date(2026, 11, 2)


def test_end_anchor_falls_back_to_start():
    result = calculate_schedule(date(2026, 5, 1), None, "END", 1, 2)
    assert result.planned_start == date(2026, 5, 2)


def test_preparation_window_compresses_template_offsets_to_final_event_day():
    result = calculate_schedule(date(2026, 8, 10), date(2026, 10, 2), "START", -120, -30)
    assert result.planned_start == date(2026, 8, 10)
    assert date(2026, 8, 10) <= result.due_date < date(2026, 10, 2)


def test_short_preparation_window_keeps_tasks_inside_window():
    result = calculate_schedule(date(2026, 8, 10), date(2026, 10, 2), "START", -60, -3)
    assert result.planned_start == date(2026, 9, 6)
    assert result.due_date == date(2026, 10, 1)


def test_invalid_ranges_are_rejected():
    with pytest.raises(ValueError):
        calculate_schedule(date(2026, 5, 2), date(2026, 5, 1), "START", -1, 0)
    with pytest.raises(ValueError):
        calculate_schedule(date(2026, 5, 1), None, "START", 1, 0)


def test_d_day_labels():
    assert d_day_label(3) == "D-3"
    assert d_day_label(0) == "D-DAY"
    assert d_day_label(-2) == "D+2 지연"
