from __future__ import annotations

import os
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCalendarWidget, QPushButton
from PySide6.QtWidgets import QAbstractSpinBox, QDoubleSpinBox
from PySide6.QtTest import QTest

from event_checklist.database import Database
from event_checklist.services import EventService
from event_checklist.ui.calendar_page import CalendarTaskCard
from event_checklist.ui.dashboard_page import EventCard
from event_checklist.ui.dialogs import EventDialog
from event_checklist.ui.main_window import MainWindow
from event_checklist.ui.events_page import EventsPage
from event_checklist.ui.master_page import MasterPage
from event_checklist.ui.month_timeline import MonthTimeline
from event_checklist.ui.widgets import DirectDateEdit, UnitComboBox, configure_money_spin, configure_quantity_spin
from event_checklist.units import COMMON_UNITS
from event_checklist.update_service import UpdateInfo


def test_main_window_initializes(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "gui.db"); window = MainWindow(db)
    assert window.windowTitle() == "이벤트 플로우"
    assert window.stack.count() == 5
    assert not window.nav_buttons[1].isEnabled()
    assert window.nav_buttons[4].isEnabled()
    window.close(); db.close()


def test_title_bar_shows_current_public_version_and_release_date(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "update-meta.db"); window = MainWindow(db, enable_update_check=False)
    info = UpdateInfo("0.3.3", "v0.3.3", "", "", None, "", "", "2026-08-11T00:41:19Z")
    window._update_check_finished(info)
    assert "현재 0.3.7" in window.title_bar.update_meta.text()
    assert "공개 0.3.3" in window.title_bar.update_meta.text()
    assert "2026-08-11" in window.title_bar.update_meta.text()
    assert window.title_bar.update_button.text() == "다시 확인"
    assert window.title_bar.update_button.isEnabled()
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
    assert date_edit.findChildren(QCalendarWidget) == []
    date_edit.show()
    QTest.mouseClick(date_edit, Qt.MouseButton.LeftButton)
    app.processEvents()
    money_edit = configure_money_spin(QDoubleSpinBox())
    money_edit.setRange(0, 999_999_999); money_edit.setValue(50_000_000)
    assert date_edit.property("directCalendar") is True
    assert date_edit.calendarWidget().isVisible()
    assert date_edit.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
    assert money_edit.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
    assert "50,000,000" in money_edit.text()


def test_event_card_is_selected_by_click_without_separate_button():
    app = QApplication.instance() or QApplication([])
    card = EventCard({"id": 7, "name": "클릭 행사", "start_date": "2026-08-01", "end_date": "2026-08-03"}, 25)
    selected = []
    card.selected.connect(selected.append)
    card.resize(600, 80); card.show()
    QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=card.rect().center())
    assert selected == [7]
    assert all(button.text() != "선택" for button in card.findChildren(QPushButton))
    card.close()


def test_unit_combo_matches_excel_list_and_allows_custom_value():
    app = QApplication.instance() or QApplication([])
    combo = UnitComboBox("식")
    assert [combo.itemText(index) for index in range(combo.count())] == COMMON_UNITS
    committed = []
    combo.value_committed.connect(committed.append)
    combo.setEditText("롤")
    combo._commit()
    assert committed == ["롤"]


def test_quantity_input_uses_whole_number_without_arrows():
    app = QApplication.instance() or QApplication([])
    quantity = configure_quantity_spin(QDoubleSpinBox())
    quantity.setValue(12)
    assert quantity.decimals() == 0
    assert quantity.text() == "12"
    assert quantity.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons


def test_calendar_card_completion_and_quick_postpone_actions():
    app = QApplication.instance() or QApplication([])
    today = date.today()
    task = {
        "id": 11, "name": "긴급 업무", "major": "운영", "priority": "상", "status": "진행중",
        "planned_start": today.isoformat(), "due_date": today.isoformat(),
    }
    card = CalendarTaskCard(task)
    completed, postponed = [], []
    card.completion_requested.connect(lambda task_id, value: completed.append((task_id, value)))
    card.postpone_requested.connect(lambda task_id, value: postponed.append((task_id, value)))
    buttons = {button.text(): button for button in card.findChildren(QPushButton)}
    buttons["완료 처리"].click()
    buttons["내일까지"].click()
    assert completed == [(11, True)]
    assert postponed == [(11, today + timedelta(days=1))]


def test_calendar_postpone_actions_only_appear_for_today_deadline():
    app = QApplication.instance() or QApplication([])
    future = date.today() + timedelta(days=1)
    task = {
        "id": 12, "name": "내일 업무", "major": "운영", "priority": "중", "status": "미착수",
        "planned_start": date.today().isoformat(), "due_date": future.isoformat(),
    }
    card = CalendarTaskCard(task)
    labels = {button.text() for button in card.findChildren(QPushButton)}
    assert "완료 처리" in labels
    assert "내일까지" not in labels
    assert "모레까지" not in labels
    assert "날짜 선택" not in labels


def test_checklist_prefetches_assignees_once_and_creates_calendars_lazily(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "checklist-performance.db")
    service = EventService(db)
    master_ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY sort_order")]
    event_id = service.create_event("성능 행사", date.today(), date.today() + timedelta(days=5), master_ids)
    calls = 0
    original = service.available_assignees

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "available_assignees", counted)
    page = EventsPage(service, db)
    page.set_event(event_id)
    assert page.table.rowCount() == 120
    assert calls == 1
    assert page.table.findChildren(QCalendarWidget) == []
    page.close(); db.close()
