from __future__ import annotations

import calendar
from datetime import date, timedelta

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip, QWidget


CATEGORY_COLORS = {
    "시스템": "#D8E8F6", "시설": "#DCEFE3", "행사": "#FCE1D6",
    "홍보": "#E7DFF3", "운영": "#F5EACB",
}


class MonthTimeline(QWidget):
    date_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        today = date.today()
        self.year, self.month = today.year, today.month
        self.selected = today
        self.tasks = []
        self._weeks = []
        self._hits: list[tuple[QRectF, str]] = []
        self.setMouseTracking(True)
        self.setMinimumSize(680, 520)

    def set_month(self, year: int, month: int):
        self.year, self.month = year, month
        self.update()

    def shift_month(self, offset: int):
        value = self.year * 12 + self.month - 1 + offset
        self.set_month(value // 12, value % 12 + 1)

    def set_tasks(self, tasks):
        self.tasks = [dict(row) for row in tasks]
        self.update()

    def _calendar_weeks(self):
        weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(self.year, self.month)
        while len(weeks) < 6:
            start = weeks[-1][-1] + timedelta(days=1)
            weeks.append([start + timedelta(days=i) for i in range(7)])
        return weeks[:6]

    @staticmethod
    def _priority(task):
        return (task["status"] == "완료", date.fromisoformat(task["due_date"]),
                {"상": 0, "중": 1, "하": 2}.get(task["priority"], 3), task["sort_order"])

    def _week_segments(self, week, lane_capacity):
        start, end = week[0], week[-1]
        candidates = []
        for task in sorted(self.tasks, key=self._priority):
            task_start, task_end = date.fromisoformat(task["planned_start"]), date.fromisoformat(task["due_date"])
            if task_end < start or task_start > end:
                continue
            first, last = max(task_start, start), min(task_end, end)
            candidates.append((task, (first - start).days, (last - start).days,
                               task_start == first, task_end == last))
        lanes: list[list[tuple[int, int]]] = []
        visible, hidden = [], [0] * 7
        for segment in candidates:
            _, first, last, _, _ = segment
            lane = next((i for i, spans in enumerate(lanes)
                         if all(last < a or first > b for a, b in spans)), len(lanes))
            if lane >= lane_capacity:
                for day_index in range(first, last + 1): hidden[day_index] += 1
                continue
            if lane == len(lanes): lanes.append([])
            lanes[lane].append((first, last))
            visible.append((lane, *segment))
        return visible, hidden

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        self._hits.clear()
        self._weeks = self._calendar_weeks()
        header_h = 34
        cell_w = self.width() / 7
        row_h = (self.height() - header_h) / 6
        painter.setFont(QFont("Malgun Gothic", 9, QFont.Weight.DemiBold))
        for column, label in enumerate(["일", "월", "화", "수", "목", "금", "토"]):
            painter.setPen(QColor("#C9342C") if column in (0, 6) else QColor("#686B70"))
            painter.drawText(QRectF(column * cell_w, 0, cell_w, header_h), Qt.AlignmentFlag.AlignCenter, label)
        painter.setPen(QPen(QColor("#E9EBEE"), 1))
        for col in range(8): painter.drawLine(QPoint(int(col * cell_w), header_h), QPoint(int(col * cell_w), self.height()))
        for row in range(7): painter.drawLine(QPoint(0, int(header_h + row * row_h)), QPoint(self.width(), int(header_h + row * row_h)))

        lane_h, top_gap = 16, 29
        lane_capacity = max(1, int((row_h - top_gap - 17) // (lane_h + 2)))
        for week_index, week in enumerate(self._weeks):
            y = header_h + week_index * row_h
            for column, value in enumerate(week):
                x = column * cell_w
                if value == self.selected:
                    painter.fillRect(QRectF(x + 1, y + 1, cell_w - 2, row_h - 2), QColor("#FFF5EF"))
                color = "#B1B5BC" if value.month != self.month else ("#C9342C" if column in (0, 6) else "#212124")
                painter.setPen(QColor(color)); painter.setFont(QFont("Malgun Gothic", 9))
                painter.drawText(QRectF(x + 7, y + 5, cell_w - 14, 18), Qt.AlignmentFlag.AlignLeft, str(value.day))
            visible, hidden = self._week_segments(week, lane_capacity)
            for lane, task, first, last, is_start, is_end in visible:
                x = first * cell_w + (4 if is_start else 0)
                width = (last - first + 1) * cell_w - (8 if is_start and is_end else 4)
                bar = QRectF(x, y + top_gap + lane * (lane_h + 2), width, lane_h)
                base = QColor(CATEGORY_COLORS.get(task["major"], "#E5E7EB"))
                if task["status"] == "완료": base.setAlpha(120)
                painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(base)
                path = QPainterPath(); path.addRoundedRect(bar, 4 if is_start or is_end else 1, 4 if is_start or is_end else 1)
                painter.drawPath(path)
                painter.setPen(QColor("#394047")); painter.setFont(QFont("Malgun Gothic", 7))
                painter.drawText(bar.adjusted(5, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine, task["name"])
                tooltip = f"{task['name']}\n{task['planned_start']} ~ {task['due_date']}"
                self._hits.append((bar, tooltip))
            for column, count in enumerate(hidden):
                if count:
                    rect = QRectF(column * cell_w + 5, y + row_h - 19, cell_w - 10, 16)
                    painter.setPen(QColor("#686B70")); painter.setFont(QFont("Malgun Gothic", 7))
                    painter.drawText(rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"+{count}개 더보기")

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        header_h = 34
        if event.position().y() < header_h:
            return
        column = min(6, int(event.position().x() / (self.width() / 7)))
        row = min(5, int((event.position().y() - header_h) / ((self.height() - header_h) / 6)))
        self.selected = self._calendar_weeks()[row][column]
        self.date_selected.emit(self.selected)
        self.update()

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            for rect, text in self._hits:
                if rect.contains(event.position()):
                    QToolTip.showText(event.globalPosition().toPoint(), text, self)
                    return True
            QToolTip.hideText()
        return super().event(event)
