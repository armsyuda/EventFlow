from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


# 기본 일정표는 최대 D-120을 기준으로 작성되어 있다. 준비 기간이 더 짧으면
# 모든 사전 업무를 준비 시작일~최종 행사일 안에 같은 비율로 압축한다.
TEMPLATE_LOOKBACK_DAYS = 120


@dataclass(frozen=True)
class Schedule:
    planned_start: date
    due_date: date


def anchor_date(event_start: date, event_end: date | None, anchor: str) -> date:
    if anchor == "END":
        return event_end or event_start
    if anchor != "START":
        raise ValueError(f"지원하지 않는 기준일: {anchor}")
    return event_start


def calculate_schedule(
    event_start: date,
    event_end: date | None,
    anchor: str,
    start_offset: int,
    due_offset: int,
) -> Schedule:
    if event_end and event_end < event_start:
        raise ValueError("행사 종료일은 시작일보다 빠를 수 없습니다.")
    if start_offset > due_offset:
        raise ValueError("작업 시작 오프셋은 마감 오프셋보다 클 수 없습니다.")
    base = anchor_date(event_start, event_end, anchor)
    scaled_start = start_offset
    scaled_due = due_offset
    if event_end is not None and anchor == "START":
        preparation_days = (event_end - event_start).days

        def fit_to_preparation_window(offset: int) -> int:
            if offset >= 0 or preparation_days >= TEMPLATE_LOOKBACK_DAYS:
                return offset
            if preparation_days <= 0:
                return 0
            # D-1 같은 행사 직전 일정은 압축 후에도 최소 하루 전을 유지한다.
            compressed = round(offset * preparation_days / TEMPLATE_LOOKBACK_DAYS)
            return max(-preparation_days, min(-1, compressed))

        scaled_start = fit_to_preparation_window(start_offset)
        scaled_due = fit_to_preparation_window(due_offset)
        # 별도 최종 행사일을 입력한 경우 start_date는 준비 시작일이다.
        base = event_end
    return Schedule(base + timedelta(days=scaled_start), base + timedelta(days=scaled_due))


def d_day(due_date: date, today: date | None = None) -> int:
    return (due_date - (today or date.today())).days


def d_day_label(days: int) -> str:
    if days > 0:
        return f"D-{days}"
    if days == 0:
        return "D-DAY"
    return f"D+{abs(days)} 지연"
