from __future__ import annotations

import calendar
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSplitter, QVBoxLayout, QWidget

from ..schedule import d_day, d_day_label
from ..theme import status_color
from .month_timeline import MonthTimeline


class CalendarTaskCard(QFrame):
    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.setObjectName("CalendarTaskCard")
        layout = QVBoxLayout(self); layout.setContentsMargins(14, 10, 14, 10); layout.setSpacing(4)
        top = QHBoxLayout()
        name = QLabel(task["name"]); name.setObjectName("CalendarTaskName"); name.setWordWrap(True)
        fg, bg = status_color(task["status"])
        badge = QLabel(task["status"]); badge.setObjectName("StatusBadge"); badge.setStyleSheet(f"color:{fg};background:{bg};")
        top.addWidget(name, 1); top.addWidget(badge); layout.addLayout(top)
        due = date.fromisoformat(task["due_date"])
        suffix = "완료" if task["status"] == "완료" else d_day_label(d_day(due))
        meta = QLabel(f"{task['major']} · {task['planned_start']} ~ {task['due_date']} · {suffix}")
        meta.setObjectName("Muted"); layout.addWidget(meta)


class CalendarPage(QWidget):
    def __init__(self, service, db=None, parent=None):
        super().__init__(parent)
        self.service = service
        self.db = db or service.db
        self.event_id: int | None = None
        root = QVBoxLayout(self); root.setContentsMargins(32, 28, 32, 32); root.setSpacing(12)
        top = QHBoxLayout(); box = QVBoxLayout()
        title = QLabel("달력"); title.setObjectName("PageTitle")
        self.description = QLabel("업무 기간을 연속 막대로 확인합니다."); self.description.setObjectName("PageDescription")
        box.addWidget(title); box.addWidget(self.description); top.addLayout(box); top.addStretch()
        previous = QPushButton("‹"); previous.setFixedWidth(42); previous.clicked.connect(lambda: self._shift(-1))
        self.month_label = QLabel(""); self.month_label.setObjectName("SectionTitle"); self.month_label.setMinimumWidth(110); self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        following = QPushButton("›"); following.setFixedWidth(42); following.clicked.connect(lambda: self._shift(1))
        self.toggle = QPushButton("일정 목록 숨기기"); self.toggle.clicked.connect(self._toggle_side)
        top.addWidget(previous); top.addWidget(self.month_label); top.addWidget(following); top.addWidget(self.toggle)
        root.addLayout(top)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.calendar = MonthTimeline(); self.calendar.date_selected.connect(self.refresh_selected)
        self.splitter.addWidget(self.calendar)
        self.side = QFrame(); self.side.setObjectName("CalendarSide")
        side_layout = QVBoxLayout(self.side); side_layout.setContentsMargins(16, 16, 16, 16)
        head = QHBoxLayout(); self.selected_title = QLabel(""); self.selected_title.setObjectName("SectionTitle")
        self.selected_count = QLabel(""); self.selected_count.setObjectName("Muted")
        head.addWidget(self.selected_title, 1); head.addWidget(self.selected_count); side_layout.addLayout(head)
        self.list = QListWidget(); self.list.setObjectName("CalendarTaskList"); self.list.setSpacing(7); side_layout.addWidget(self.list, 1)
        self.empty = QLabel("이 날짜에 진행 중인 업무가 없습니다.")
        self.empty.setObjectName("EmptyState"); self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(self.empty, 1); self.empty.hide()
        self.splitter.addWidget(self.side); self.splitter.setSizes([850, 390]); self.splitter.setHandleWidth(7)
        root.addWidget(self.splitter, 1)
        visible = self.db.get_setting("calendar_list_visible", "1") != "0"
        self.side.setVisible(visible); self.toggle.setText("일정 목록 숨기기" if visible else "일정 목록 보기")
        self._update_month_label()

    def set_event(self, event_id):
        self.event_id = event_id
        event = self.service.get_event(event_id) if event_id else None
        self.description.setText(f"{event['name']}의 업무 기간을 확인합니다." if event else "행사를 선택하세요.")
        self.refresh()

    def refresh_events(self, selected_event_id=None):
        self.set_event(selected_event_id if selected_event_id is not None else self.event_id)

    def _shift(self, offset):
        self.calendar.shift_month(offset); self._update_month_label(); self.refresh_periods()

    def _update_month_label(self): self.month_label.setText(f"{self.calendar.year}년 {self.calendar.month}월")

    def _toggle_side(self):
        visible = not self.side.isVisible(); self.side.setVisible(visible)
        self.toggle.setText("일정 목록 숨기기" if visible else "일정 목록 보기")
        self.db.set_setting("calendar_list_visible", "1" if visible else "0")

    def refresh(self): self.refresh_periods(); self.refresh_selected(self.calendar.selected)

    def refresh_periods(self):
        first = date(self.calendar.year, self.calendar.month, 1)
        last = date(self.calendar.year, self.calendar.month, calendar.monthrange(self.calendar.year, self.calendar.month)[1])
        self.calendar.set_tasks(self.service.calendar_range(first, last, self.event_id) if self.event_id else [])

    def refresh_selected(self, selected=None):
        selected = selected or self.calendar.selected
        self.selected_title.setText(selected.strftime("%Y년 %m월 %d일")); self.list.clear()
        tasks = self.service.calendar_tasks(selected, self.event_id) if self.event_id else []
        self.selected_count.setText(f"{len(tasks)}개")
        if not tasks:
            self.list.hide(); self.empty.show(); return
        self.empty.hide(); self.list.show()
        for task in tasks:
            item = QListWidgetItem(); item.setSizeHint(item.sizeHint().__class__(0, 82)); self.list.addItem(item)
            self.list.setItemWidget(item, CalendarTaskCard(task, self.list))
