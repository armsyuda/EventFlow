from __future__ import annotations

import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QAbstractSpinBox, QDoubleSpinBox
from PySide6.QtTest import QTest

from event_checklist.database import Database
from event_checklist.ui.dialogs import EventDialog
from event_checklist.ui.main_window import MainWindow
from event_checklist.ui.master_page import MasterPage
from event_checklist.ui.month_timeline import MonthTimeline
from event_checklist.ui.widgets import DirectDateEdit, configure_money_spin


def test_main_window_initializes(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "gui.db"); window = MainWindow(db)
    assert window.windowTitle() == "이벤트 플로우"
    assert window.stack.count() == 5
    assert not window.nav_buttons[1].isEnabled()
    assert window.nav_buttons[4].isEnabled()
    window.close(); db.close()


def test_new_event_dialog_builds_without_native_crash(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "dialog.db")
    dialog = EventDialog(db.query("SELECT * FROM master_items WHERE active=1 ORDER BY sort_order"))
    assert dialog.tree.topLevelItemCount() == 5
    assert len(dialog.selected_ids()) == 120
    dialog.close(); db.close()


def test_master_item_cell_can_be_edited_directly(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "master-edit.db"); page = MasterPage(db)
    item = page.table.item(0, 3); item_id = item.data(Qt.ItemDataRole.UserRole); item.setText("직접 수정 항목")
    assert db.one("SELECT name FROM master_items WHERE id=?", (item_id,))["name"] == "직접 수정 항목"
    page.close(); db.close()


def test_calendar_lanes_prioritize_nearest_incomplete_deadlines():
    app = QApplication.instance() or QApplication([]); timeline = MonthTimeline(); timeline.set_month(2026, 9)
    rows = [
        {"id":1,"name":"먼 마감","major":"운영","priority":"중","sort_order":1,"planned_start":"2026-09-01","due_date":"2026-09-20","status":"미착수"},
        {"id":2,"name":"가까운 마감","major":"행사","priority":"중","sort_order":2,"planned_start":"2026-09-01","due_date":"2026-09-05","status":"미착수"},
        {"id":3,"name":"완료 업무","major":"시설","priority":"상","sort_order":3,"planned_start":"2026-09-01","due_date":"2026-09-03","status":"완료"},
        {"id":4,"name":"첫 번째","major":"홍보","priority":"상","sort_order":4,"planned_start":"2026-09-01","due_date":"2026-09-06","status":"미착수"},
        {"id":5,"name":"두 번째","major":"시스템","priority":"상","sort_order":5,"planned_start":"2026-09-01","due_date":"2026-09-07","status":"미착수"},
    ]
    timeline.set_tasks(rows)
    week = next(week for week in timeline._calendar_weeks() if date(2026, 9, 2) in week)
    visible, hidden = timeline._week_segments(week, 3)
    assert [segment[1]["name"] for segment in visible] == ["가까운 마감", "첫 번째", "두 번째"]
    assert sum(hidden) > 0
    timeline.close()


def test_direct_date_and_money_inputs_have_no_arrow_buttons():
    app = QApplication.instance() or QApplication([])
    date_edit = DirectDateEdit()
    date_edit.show()
    QTest.mouseClick(date_edit, Qt.MouseButton.LeftButton)
    app.processEvents()
    money_edit = configure_money_spin(QDoubleSpinBox())
    money_edit.setRange(0, 999_999_999); money_edit.setValue(50_000_000)
    assert date_edit.property("directCalendar") is True
    assert date_edit.calendarWidget().isVisible()
    assert money_edit.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
    assert "50,000,000" in money_edit.text()
