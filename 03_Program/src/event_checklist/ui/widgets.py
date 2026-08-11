from __future__ import annotations

from collections import defaultdict
from datetime import date

from PySide6.QtCore import QDate, QLocale, QRect, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QAbstractSpinBox, QCalendarWidget, QDateEdit, QDoubleSpinBox, QFrame, QHeaderView, QLabel, QTableWidget, QVBoxLayout

from ..theme import TOKENS


class DirectDateEdit(QDateEdit):
    """입력창 어디를 눌러도 즉시 달력을 여는 날짜 입력창."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("directCalendar", True)
        self.setDisplayFormat("yyyy-MM-dd")
        self._direct_calendar = QCalendarWidget()
        self._direct_calendar.setWindowFlags(Qt.WindowType.Popup)
        self._direct_calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self._direct_calendar.setGridVisible(True)
        self._direct_calendar.setFixedSize(340, 270)
        self._direct_calendar.clicked.connect(self._choose_date)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled(): self._open_calendar()

    def _open_calendar(self):
        self._direct_calendar.setSelectedDate(self.date())
        self._direct_calendar.move(self.mapToGlobal(self.rect().bottomLeft()))
        self._direct_calendar.show(); self._direct_calendar.raise_(); self._direct_calendar.activateWindow()

    def _choose_date(self, value: QDate):
        self.setDate(value); self._direct_calendar.hide()

    def calendarWidget(self):
        return self._direct_calendar


def configure_money_spin(widget: QDoubleSpinBox, suffix: str = " 원") -> QDoubleSpinBox:
    """금액 입력을 쉼표 단위로 표시하고 불필요한 증감 화살표를 없앤다."""
    widget.setDecimals(0)
    widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    widget.setGroupSeparatorShown(True)
    widget.setLocale(QLocale(QLocale.Language.Korean, QLocale.Country.SouthKorea))
    widget.setSuffix(suffix)
    widget.setAlignment(Qt.AlignmentFlag.AlignRight)
    return widget


class KpiCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("Muted")
        self.value_label = QLabel("0")
        self.value_label.setObjectName("KpiValue")
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str | int) -> None:
        self.value_label.setText(str(value))


class PeriodCalendar(QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dates: dict[date, list[dict]] = defaultdict(list)
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setMinimumWidth(620)
        self.setMinimumHeight(520)

    def set_periods(self, rows) -> None:
        self._dates.clear()
        for row in rows:
            current = date.fromisoformat(row["planned_start"])
            end = date.fromisoformat(row["due_date"])
            period = dict(row)
            while current <= end:
                self._dates[current].append(period)
                current = current.fromordinal(current.toordinal() + 1)
        self.updateCells()

    def periods_for_day(self, day: date) -> list[dict]:
        """완료되지 않았고 마감이 가까운 업무부터 달력 라벨 순서를 정한다."""
        unique = {int(period["id"]): period for period in self._dates.get(day, [])}
        priority_order = {"상": 0, "중": 1, "하": 2}
        return sorted(
            unique.values(),
            key=lambda period: (
                period["status"] == "완료",
                period["due_date"],
                priority_order.get(period.get("priority"), 3),
                int(period.get("sort_order") or 0),
                int(period["id"]),
            ),
        )

    def visible_periods(self, day: date, max_slots: int) -> tuple[list[dict], int]:
        ordered = self.periods_for_day(day)
        if len(ordered) <= max_slots:
            return ordered, 0
        visible_count = max(1, max_slots - 1)
        return ordered[:visible_count], len(ordered) - visible_count

    def paintCell(self, painter: QPainter, rect, qdate: QDate) -> None:
        super().paintCell(painter, rect, qdate)
        day = date(qdate.year(), qdate.month(), qdate.day())
        periods = self._dates.get(day)
        if not periods:
            return
        painter.save()
        # 기본 달력은 날짜 숫자를 셀 중앙에 그린다. 일정 라벨이 많은 날에는
        # 겹치므로 해당 셀을 다시 칠하고 날짜를 위쪽에 고정한다.
        selected = qdate == self.selectedDate()
        cell_bg = QColor(TOKENS["brand_weak"] if selected else TOKENS["bg_layer"])
        painter.fillRect(rect.adjusted(1, 1, -1, -1), cell_bg)
        if qdate.month() != self.monthShown():
            day_color = QColor(TOKENS["fg_subtle"])
        elif qdate.dayOfWeek() in (6, 7):
            day_color = QColor(TOKENS["critical"])
        else:
            day_color = QColor(TOKENS["fg_neutral"])
        day_font = painter.font()
        day_font.setPointSizeF(9)
        painter.setFont(day_font)
        painter.setPen(day_color)
        painter.drawText(
            QRect(rect.left() + 2, rect.top() + 4, rect.width() - 4, 20),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            str(qdate.day()),
        )
        palette = {
            "시스템": "#F25B24", "시설": "#8B5CF6", "행사": "#1769AA",
            "홍보": "#D97706", "운영": "#18864B",
        }
        label_height = 14
        label_gap = 1
        max_slots = min(4, max(2, (rect.height() - 34) // (label_height + label_gap)))
        visible, hidden_count = self.visible_periods(day, max_slots)
        lane_count = len(visible) + (1 if hidden_count else 0)
        start_y = rect.bottom() - 3 - lane_count * label_height - max(0, lane_count - 1) * label_gap

        font = painter.font()
        font.setPointSizeF(7.5)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        for lane, period in enumerate(visible):
            color = QColor(TOKENS["positive"] if period["status"] == "완료" else palette.get(period["major"], TOKENS["brand"]))
            fill = QColor(color)
            fill.setAlpha(38)
            painter.setPen(QPen(color, 1))
            painter.setBrush(fill)
            y = start_y + lane * (label_height + label_gap)
            label_rect = QRect(rect.left() + 4, y, rect.width() - 8, label_height)
            painter.drawRoundedRect(label_rect, 2, 2)
            painter.setPen(color.darker(125))
            text = metrics.elidedText(str(period["name"]), Qt.TextElideMode.ElideRight, label_rect.width() - 7)
            painter.drawText(label_rect.adjusted(4, 0, -3, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)

        if hidden_count:
            lane = len(visible)
            y = start_y + lane * (label_height + label_gap)
            more_rect = QRect(rect.left() + 4, y, rect.width() - 8, label_height)
            more_bg = QColor(TOKENS["bg_weak"])
            painter.setPen(QPen(QColor(TOKENS["fg_subtle"]), 1))
            painter.setBrush(more_bg)
            painter.drawRoundedRect(more_rect, 2, 2)
            painter.setPen(QColor(TOKENS["fg_muted"]))
            painter.drawText(
                more_rect.adjusted(4, 0, -3, 0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"+{hidden_count}개 더보기",
            )
        painter.restore()


def configure_resizable_table(table: QTableWidget, widths: list[int]) -> None:
    """모든 열을 직접 늘이거나 이동할 수 있게 하고 초기 너비만 지정한다."""
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setSectionsMovable(True)
    header.setMinimumSectionSize(44)
    header.setStretchLastSection(False)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    for column, width in enumerate(widths):
        table.setColumnWidth(column, width)


def fit_table_to_view(table: QTableWidget, minimum: int = 58) -> None:
    """현재 창 너비에 맞춰 표시 중인 모든 열을 비례 조정한다."""
    visible = [column for column in range(table.columnCount()) if not table.isColumnHidden(column)]
    if not visible:
        return
    available = max(1, table.viewport().width() - 4)
    current = [max(minimum, table.columnWidth(column)) for column in visible]
    total = sum(current)
    if total <= 0:
        return
    widths = [max(minimum, int(width * available / total)) for width in current]
    # 반올림 오차는 마지막 열에 반영하되 최소 너비를 지킨다.
    if sum(widths) < available:
        widths[-1] += available - sum(widths)
    for column, width in zip(visible, widths):
        table.setColumnWidth(column, width)
