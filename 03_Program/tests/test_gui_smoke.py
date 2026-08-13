from __future__ import annotations

import os
from datetime import date, timedelta
from time import perf_counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QItemSelectionModel, QRect, Qt
from PySide6.QtWidgets import QApplication, QAbstractItemView, QCalendarWidget, QHeaderView, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QStyleOptionViewItem, QTableWidgetSelectionRange
from PySide6.QtWidgets import QAbstractSpinBox, QDoubleSpinBox
from PySide6.QtTest import QTest

from event_checklist import __version__
from event_checklist.database import Database
from event_checklist.choices import load_master_choice_catalog
from event_checklist.services import EventService
from event_checklist.pdf_export import PdfOptions
from event_checklist.ui.calendar_page import CalendarPage, CalendarTaskCard
from event_checklist.ui.contacts_page import ContactsPage
from event_checklist.ui.dashboard_page import EventCard
from event_checklist.ui.dialogs import (
    BulkAssignmentDialog, ContactDialog, CustomTaskDialog, EventDialog, MasterItemDialog,
    PreviousEventImportDialog,
)
from event_checklist.ui.main_window import MainWindow
from event_checklist.ui.events_page import EventsPage, STATUSES
from event_checklist.ui.excel_export_dialog import ExcelExportDialog
from event_checklist.ui.master_page import MasterPage
from event_checklist.ui.pdf_export_dialog import CalendarPdfExportDialog, ChecklistPdfExportDialog, PdfExportDialog
from event_checklist.ui.month_timeline import MonthTimeline
from event_checklist.ui.settlement_page import SettlementPage
from event_checklist.ui.settings_page import SettingsPage
from event_checklist.ui.startup_splash import StartupSplash
from event_checklist.theme import ComboPopupPolisher, InteractionCursorPolisher, application_stylesheet
from event_checklist.ui.widgets import (
    GROUP_MAJOR_ROLE, GROUP_MINOR_ROLE, AppComboBox, DirectDateEdit, FastEditableTable, UnitComboBox,
    SpreadsheetItemDelegate, configure_money_spin, configure_quantity_spin, fit_table_to_view,
)
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


def test_hamburger_button_toggles_sidebar_and_expands_content(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "sidebar-toggle.db"); window = MainWindow(db, enable_update_check=False)
    window.resize(1440, 900); window.show(); app.processEvents()
    sidebar_width = window.sidebar.width()
    initial_content_width = window.stack.width()
    assert sidebar_width == 212
    assert window.sidebar.isVisible()
    assert window.title_bar.menu_button.accessibleName() == "좌측 메뉴 숨기기"

    window.title_bar.menu_button.click(); app.processEvents()
    assert not window.sidebar.isVisible()
    assert window.stack.width() >= initial_content_width + sidebar_width - 2
    assert window.title_bar.menu_button.accessibleName() == "좌측 메뉴 보기"

    window.title_bar.menu_button.click(); app.processEvents()
    assert window.sidebar.isVisible()
    assert window.stack.width() == initial_content_width
    window.close(); db.close()


def test_title_bar_shows_current_public_version_and_release_date(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "update-meta.db"); window = MainWindow(db, enable_update_check=False)
    info = UpdateInfo("0.3.3", "v0.3.3", "", "", None, "", "", "2026-08-11T00:41:19Z")
    window._update_check_finished(info)
    assert f"현재 {__version__}" in window.title_bar.update_meta.text()
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


def test_direct_task_dialog_uses_detail_label_and_starts_without_dates(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "custom-task-dialog.db"); service = EventService(db)
    event_id = service.create_event(
        "직접 추가 창", date.today(), date.today() + timedelta(days=30),
        [db.one("SELECT id FROM master_items ORDER BY sort_order LIMIT 1")["id"]],
    )
    dialog = CustomTaskDialog(
        service.get_event(event_id), category_choices=load_master_choice_catalog(db),
    )
    labels = {dialog.layout().itemAt(0).layout().labelForField(dialog.detail).text()}
    assert labels == {"세부내용"}
    dialog.name.setText("새 업무")
    values = dialog.values()
    assert values["planned_start"] is None and values["due_date"] is None
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
        {"id":1,"name":"먼 마감","major":"운영","sort_order":1,"planned_start":"2026-09-01","due_date":"2026-09-20","status":"미착수"},
        {"id":2,"name":"가까운 마감","major":"행사","sort_order":2,"planned_start":"2026-09-01","due_date":"2026-09-05","status":"미착수"},
        {"id":3,"name":"완료 업무","major":"시설","sort_order":3,"planned_start":"2026-09-01","due_date":"2026-09-03","status":"완료"},
        {"id":4,"name":"첫 번째","major":"홍보","sort_order":4,"planned_start":"2026-09-01","due_date":"2026-09-06","status":"미착수"},
        {"id":5,"name":"두 번째","major":"시스템","sort_order":5,"planned_start":"2026-09-01","due_date":"2026-09-07","status":"미착수"},
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


def test_narrow_unit_popup_keeps_full_labels_and_uses_slim_scrollbar():
    app = QApplication.instance() or QApplication([])
    combo = AppComboBox(); combo.setEditable(True); combo.addItems(COMMON_UNITS); combo.resize(80, 44)
    combo._polish_popup()
    assert combo.view().minimumWidth() >= 112
    assert combo.view().textElideMode() == Qt.TextElideMode.ElideNone
    assert "width: 5px" in combo.view().styleSheet()
    assert combo.view().minimumWidth() - 30 > combo.view().fontMetrics().horizontalAdvance("세트")
    combo.close()


def test_quantity_input_uses_whole_number_without_arrows():
    app = QApplication.instance() or QApplication([])
    quantity = configure_quantity_spin(QDoubleSpinBox())
    quantity.setValue(12)
    assert quantity.decimals() == 0
    assert quantity.text() == "12"
    assert quantity.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
    assert quantity.alignment() & Qt.AlignmentFlag.AlignHCenter


def test_calendar_card_completion_and_quick_postpone_actions():
    app = QApplication.instance() or QApplication([])
    today = date.today()
    task = {
        "id": 11, "name": "긴급 업무", "major": "운영", "status": "진행중",
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
        "id": 12, "name": "내일 업무", "major": "운영", "status": "미착수",
        "planned_start": date.today().isoformat(), "due_date": future.isoformat(),
    }
    card = CalendarTaskCard(task)
    labels = {button.text() for button in card.findChildren(QPushButton)}
    assert "완료 처리" in labels
    assert "내일까지" not in labels
    assert "모레까지" not in labels
    assert "날짜 선택" not in labels


def test_checklist_loads_new_global_contacts_and_creates_calendars_lazily(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "checklist-performance.db")
    service = EventService(db)
    master_ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY sort_order")]
    event_id = service.create_event("성능 행사", date.today(), date.today() + timedelta(days=5), master_ids)
    vendor_id = db.execute("INSERT INTO contacts(kind,name) VALUES ('VENDOR','새 업체')").lastrowid
    person_id = db.execute(
        "INSERT INTO contacts(kind,name,company_id) VALUES ('PERSON','새 담당자',?)", (vendor_id,)
    ).lastrowid
    page = EventsPage(service, db)
    page.set_event(event_id)
    assert page.table.rowCount() == 120
    assert any(row["id"] == vendor_id for row in page._vendors)
    assert any(row["id"] == person_id for row in page._all_assignees)
    assert page.table.findChildren(QCalendarWidget) == []
    page.close(); db.close()


def test_settings_contacts_refresh_checklist_choices_and_vendor_precedes_assignee(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "contact-refresh.db")
    service = EventService(db)
    master_ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY sort_order")]
    event_id = service.create_event("연락처 즉시 반영", date.today(), date.today() + timedelta(days=3), master_ids)
    window = MainWindow(db, enable_update_check=False)
    window.select_event(event_id)
    QTest.qWait(80)

    first_vendor = db.execute("INSERT INTO contacts(kind,name) VALUES ('VENDOR','첫 업체')").lastrowid
    second_vendor = db.execute("INSERT INTO contacts(kind,name) VALUES ('VENDOR','둘째 업체')").lastrowid
    first_person = db.execute(
        "INSERT INTO contacts(kind,name,company_id) VALUES ('PERSON','같은 이름',?)", (first_vendor,)
    ).lastrowid
    second_person = db.execute(
        "INSERT INTO contacts(kind,name,company_id) VALUES ('PERSON','같은 이름',?)", (second_vendor,)
    ).lastrowid
    db.execute("UPDATE contacts SET job_title='실장',role_note='무대 운영' WHERE id=?", (first_person,))
    db.execute("UPDATE contacts SET job_title='팀장',role_note='영상 관리' WHERE id=?", (second_person,))
    window.settings.contacts_changed.emit()
    QTest.qWait(100)

    assert window.events.table.horizontalHeaderItem(4).text() == "세부내용"
    assert window.events.table.horizontalHeaderItem(8).text() == "담당자(PM)"
    assert window.events.table.horizontalHeaderItem(9).text() == "업체"
    assert window.events.table.horizontalHeaderItem(10).text() == "업체담당자"
    assert window.events.table.horizontalHeaderItem(11).text() == "업체담당자 전화번호"
    assert {first_vendor, second_vendor} <= {row["id"] for row in window.events._vendors}
    assert {first_person, second_person} <= {row["id"] for row in window.events._all_assignees}
    labels = {window.events._assignee_label(row) for row in window.events._all_assignees if row["name"] == "같은 이름"}
    assert labels == {"같은 이름 · 실장 · 무대 운영", "같은 이름 · 팀장 · 영상 관리"}

    window.events._open_cell_editor(0, 9)
    editor = window.events.table.cellWidget(0, 9)
    assert editor.findData(first_vendor) >= 0 and editor.findData(second_vendor) >= 0
    window.events.table.close_cell_editor()
    window.close(); db.close()


def test_checklist_header_is_compacted_into_two_rows(tmp_path):
    app = QApplication.instance() or QApplication([])
    previous_style = app.styleSheet(); app.setStyleSheet(application_stylesheet())
    db = Database(tmp_path / "checklist-actions.db")
    page = EventsPage(EventService(db), db)
    page.resize(1400, 800); page.show(); app.processEvents()

    assert page.import_button.property("quiet") is True
    assert page.edit_event_button.property("quiet") is True
    assert page.removed_toggle.property("quiet") is True
    assert page.removed_toggle.isCheckable()
    assert page.add_button.property("primary") is True
    assert page.remove_button.property("attention") is True
    assert page.import_button.x() < page.edit_event_button.x() < page.fit_button.x()
    top_centers = [
        button.y() + button.height() // 2
        for button in (page.import_button, page.edit_event_button, page.fit_button)
    ]
    assert max(top_centers) - min(top_centers) <= 1
    assert page.search.y() > page.import_button.y()
    action_centers = [
        widget.y() + widget.height() // 2
        for widget in (
            page.search, page.status_filter, page.major_filter, page.bulk_assign_button,
            page.add_button, page.remove_button, page.removed_toggle, page.pdf_button,
        )
    ]
    assert max(action_centers) - min(action_centers) <= 1
    assert page.summary.y() < page.search.y()
    action_heights = {
        page.bulk_assign_button.height(), page.add_button.height(), page.remove_button.height(),
        page.removed_toggle.height(), page.pdf_button.height(),
    }
    assert action_heights == {44}
    page.close(); db.close(); app.setStyleSheet(previous_style)


def test_pdf_export_uses_icon_only_buttons_and_a4_portrait_defaults(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "pdf-buttons.db")
    service = EventService(db)
    checklist = EventsPage(service, db)
    settlement = SettlementPage(service, db)
    for button in (checklist.pdf_button, settlement.pdf_button):
        assert button.text() == ""
        assert not button.icon().isNull()
        assert button.toolTip() == "PDF로 내보내기"
        assert button.accessibleName() == "PDF로 내보내기"
    assert checklist.pdf_button.size().width() == checklist.pdf_button.size().height() == 44
    assert settlement.pdf_button.size().width() == settlement.pdf_button.size().height() == 42
    dialog = PdfExportDialog()
    assert dialog.options() == PdfOptions("A4", "PORTRAIT")
    dialog.a3.setChecked(True); dialog.landscape.setChecked(True)
    assert dialog.options() == PdfOptions("A3", "LANDSCAPE")
    dialog.close(); settlement.close(); checklist.close(); db.close()


def test_excel_export_dialog_selects_document_scope_and_all_page_formats(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "excel-dialog.db")
    service = EventService(db)
    master_ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY id LIMIT 2")]
    event_id = service.create_event("엑셀 테스트 행사", date(2026, 9, 1), date(2026, 9, 3), master_ids)
    tasks = db.query("SELECT id FROM event_tasks WHERE event_id=? ORDER BY id", (event_id,))
    db.execute("UPDATE event_tasks SET major='시스템',minor='음향' WHERE id=?", (tasks[0]["id"],))
    db.execute("UPDATE event_tasks SET major='시설',minor='안전' WHERE id=?", (tasks[1]["id"],))
    dialog = ExcelExportDialog(db)
    assert dialog.values() == {
        "event_id": event_id, "kind": "checklist", "options": PdfOptions("A4", "PORTRAIT"),
        "major": "", "minor": "",
    }
    dialog.scope_combo.setCurrentIndex(dialog.scope_combo.findData("MINOR"))
    dialog.major_combo.setCurrentIndex(dialog.major_combo.findData("시스템"))
    assert dialog.values()["major"] == "시스템"
    assert dialog.values()["minor"] == "음향"
    dialog.a3.setChecked(True); dialog.landscape.setChecked(True)
    assert dialog.values()["options"] == PdfOptions("A3", "LANDSCAPE")
    dialog.settlement.setChecked(True)
    assert dialog.values()["kind"] == "settlement"
    assert dialog.values()["major"] == dialog.values()["minor"] == ""
    assert not dialog.scope_panel.isEnabled()
    dialog.close(); db.close()


def test_settings_export_section_has_excel_only(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "settings-export.db")
    page = SettingsPage(db, tmp_path / "backups")
    button_texts = {button.text() for button in page.findChildren(QPushButton)}
    assert "Excel 내보내기" in button_texts
    assert all("CSV" not in text for text in button_texts)
    assert all("CSV" not in label.text() for label in page.findChildren(QLabel))
    page.close(); db.close()


def test_calendar_pdf_dialog_filters_current_event_categories():
    app = QApplication.instance() or QApplication([])
    dialog = CalendarPdfExportDialog([("행사", ["연출", "공연"]), ("운영", ["안전"])])
    assert dialog.options() == PdfOptions("A4", "LANDSCAPE")
    assert dialog.filters() == ("", "")
    dialog.scope_combo.setCurrentIndex(dialog.scope_combo.findData("MAJOR"))
    dialog.major_combo.setCurrentIndex(dialog.major_combo.findData("운영"))
    assert dialog.filters() == ("운영", "")
    dialog.scope_combo.setCurrentIndex(dialog.scope_combo.findData("MINOR"))
    assert dialog.filters() == ("운영", "안전")
    dialog.close()


def test_checklist_pdf_dialog_selects_all_or_one_major_category():
    app = QApplication.instance() or QApplication([])
    dialog = ChecklistPdfExportDialog(["시스템", "시설", "행사"])
    assert dialog.options() == PdfOptions("A4", "PORTRAIT")
    assert dialog.major_filter() == ""
    dialog.scope_combo.setCurrentIndex(dialog.scope_combo.findData("MAJOR"))
    dialog.major_combo.setCurrentIndex(dialog.major_combo.findData("시설"))
    assert dialog.major_filter() == "시설"
    dialog.close()


def test_contact_dialog_separates_person_title_role_and_vendor_industry(tmp_path):
    app = QApplication.instance() or QApplication([])
    person = ContactDialog("PERSON")
    person.name_edit.setText("이유경")
    person.job_title_edit.setText("실장")
    person.phone_edit.setText("010-1111-2222")
    person.note_edit.setText("현장 총괄")
    assert person.values() == {
        "name": "이유경", "job_title": "실장", "phone": "010-1111-2222", "role_note": "현장 총괄",
    }
    person_labels = {label.text() for label in person.findChildren(QLabel)}
    assert {"이름 *", "직책", "연락처", "역할"} <= person_labels

    vendor = ContactDialog("VENDOR")
    vendor.name_edit.setText("최작기획")
    vendor.phone_edit.setText("저장되면 안 되는 번호")
    vendor.note_edit.setText("행사 기획")
    assert vendor.values() == {
        "name": "최작기획", "job_title": "", "phone": "", "role_note": "행사 기획",
    }
    vendor_labels = {label.text() for label in vendor.findChildren(QLabel)}
    assert {"업체명 *", "업종"} <= vendor_labels
    assert "연락처" not in vendor_labels

    db = Database(tmp_path / "contact-columns.db")
    page = ContactsPage(db)
    assert [page.vendor_table.horizontalHeaderItem(i).text() for i in range(2)] == ["업체명", "업종"]
    assert [page.company_people.horizontalHeaderItem(i).text() for i in range(4)] == [
        "담당자", "직책", "연락처", "역할",
    ]
    person.close(); vendor.close(); page.close(); db.close()


def test_title_bar_keeps_detailed_update_failure_reason(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "update-error.db"); window = MainWindow(db, enable_update_check=False)
    message = "확인된 원인\nGitHub 응답 시간이 초과되었습니다.\n\n확인 방법\n인터넷 연결을 확인하세요."
    window.title_bar.set_update_error(message)
    assert window.title_bar.update_button.text() == "다시 확인"
    assert window.title_bar.update_button.toolTip() == message
    assert "확인 실패" in window.title_bar.update_meta.text()
    window.close(); db.close()


def test_missing_release_zip_explains_why_update_cannot_start(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "missing-update-zip.db"); window = MainWindow(db, enable_update_check=False)
    window.available_update = UpdateInfo(
        "0.3.25", "v0.3.25", "", "", None,
        "https://github.com/armsyuda/EventFlow/releases/tag/v0.3.25", "", "2026-08-12T00:00:00Z",
    )
    shown = {}
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, title, message: shown.update(title=title, message=message))
    window.install_available_update()
    assert shown["title"] == "업데이트 파일 누락"
    assert "EventFlow-Windows.zip" in shown["message"]
    assert "Release 주소" in shown["message"]
    window.close(); db.close()


def test_pm_and_vendor_contacts_are_filtered_and_phone_is_shown(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "pm-contacts.db"); service = EventService(db)
    pm_vendor = db.execute("INSERT INTO contacts(kind,name) VALUES ('VENDOR','PM 업체')").lastrowid
    work_vendor = db.execute("INSERT INTO contacts(kind,name) VALUES ('VENDOR','실행 업체')").lastrowid
    other_vendor = db.execute("INSERT INTO contacts(kind,name) VALUES ('VENDOR','다른 업체')").lastrowid
    pm_person = db.execute(
        "INSERT INTO contacts(kind,name,phone,company_id) VALUES ('PERSON','PM 담당','010-1111-2222',?)", (pm_vendor,)
    ).lastrowid
    work_person = db.execute(
        "INSERT INTO contacts(kind,name,phone,company_id) VALUES ('PERSON','업체 담당','010-3333-4444',?)", (work_vendor,)
    ).lastrowid
    other_person = db.execute(
        "INSERT INTO contacts(kind,name,phone,company_id) VALUES ('PERSON','다른 담당','010-5555-6666',?)", (other_vendor,)
    ).lastrowid
    master = db.one("SELECT id FROM master_items ORDER BY sort_order LIMIT 1")
    event_id = service.create_event(
        "PM 선택", date.today(), date.today() + timedelta(days=2), [master["id"]], pm_vendor_id=pm_vendor,
    )
    page = EventsPage(service, db); page.set_event(event_id)

    page._open_cell_editor(0, 8)
    pm_editor = page.table.cellWidget(0, 8)
    assert pm_editor.findData(pm_person) >= 0
    assert pm_editor.findData(work_person) < 0 and pm_editor.findData(other_person) < 0
    page.table.close_cell_editor()

    vendor_choices = [("미지정", None)] + [(row["name"], row["id"]) for row in page._vendors]
    page._commit_vendor(0, page._current_tasks[0], work_vendor, vendor_choices)
    page._open_cell_editor(0, 10)
    contact_editor = page.table.cellWidget(0, 10)
    assert contact_editor.findData(work_person) >= 0
    assert contact_editor.findData(pm_person) < 0 and contact_editor.findData(other_person) < 0
    page.table.close_cell_editor()
    contact_choices = [("미지정", None)] + [(page._assignee_label(row), row["id"])
                                             for row in page._assignees_by_vendor[work_vendor]]
    page._commit_vendor_contact(0, page._current_tasks[0], work_person, contact_choices)
    assert page.table.item(0, 11).text() == "010-3333-4444"
    page.close(); db.close()


def test_bulk_assignment_dialog_filters_pm_and_vendor_people_and_tables_select_multiple_rows(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "bulk-assignment-ui.db"); service = EventService(db)
    pm_vendor = db.execute("INSERT INTO contacts(kind,name) VALUES ('VENDOR','일괄 PM')").lastrowid
    work_vendor = db.execute("INSERT INTO contacts(kind,name) VALUES ('VENDOR','일괄 업체')").lastrowid
    other_vendor = db.execute("INSERT INTO contacts(kind,name) VALUES ('VENDOR','제외 업체')").lastrowid
    pm_person = db.execute(
        "INSERT INTO contacts(kind,name,company_id) VALUES ('PERSON','PM 사람',?)", (pm_vendor,)
    ).lastrowid
    work_person = db.execute(
        "INSERT INTO contacts(kind,name,company_id) VALUES ('PERSON','업체 사람',?)", (work_vendor,)
    ).lastrowid
    other_person = db.execute(
        "INSERT INTO contacts(kind,name,company_id) VALUES ('PERSON','제외 사람',?)", (other_vendor,)
    ).lastrowid
    masters = db.query("SELECT id FROM master_items ORDER BY sort_order LIMIT 3")
    event_id = service.create_event(
        "일괄 선택 UI", date.today(), None, [row["id"] for row in masters], pm_vendor_id=pm_vendor,
    )
    event = service.get_event(event_id)
    vendors = db.query("SELECT * FROM contacts WHERE kind='VENDOR' ORDER BY name,id")
    people = db.query("SELECT * FROM contacts WHERE kind='PERSON' ORDER BY name,id")
    dialog = BulkAssignmentDialog(event, vendors, people, 2)
    assert dialog.pm_assignee.findData(pm_person) >= 0
    assert dialog.pm_assignee.findData(work_person) < 0
    dialog.vendor.setCurrentIndex(dialog.vendor.findData(work_vendor)); app.processEvents()
    assert dialog.vendor_assignee.findData(work_person) >= 0
    assert dialog.vendor_assignee.findData(pm_person) < 0
    assert dialog.vendor_assignee.findData(other_person) < 0
    dialog.pm_assignee.setCurrentIndex(dialog.pm_assignee.findData(pm_person))
    dialog.vendor_assignee.setCurrentIndex(dialog.vendor_assignee.findData(work_person))
    assert dialog.values() == {
        "pm_assignee_id": pm_person, "vendor_id": work_vendor, "assignee_id": work_person,
    }

    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    checklist = EventsPage(service, db); checklist.set_event(event_id)
    checklist.table.selectionModel().select(checklist.table.model().index(0, 0), flags)
    checklist.table.selectionModel().select(checklist.table.model().index(1, 0), flags)
    assert len(checklist._selected_task_ids()) == 2

    settlement = SettlementPage(service, db); settlement.set_event(event_id)
    rows = list(settlement._task_rows.values())[:2]
    for row in rows:
        settlement.table.selectionModel().select(settlement.table.model().index(row, 0), flags)
    assert len(settlement._selected_task_ids()) == 2
    dialog.close(); settlement.close(); checklist.close(); db.close()


def test_bulk_assignment_applies_to_every_row_touched_by_a_selected_cell_range(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "bulk-cell-range.db"); service = EventService(db)
    vendor_id = db.execute("INSERT INTO contacts(kind,name) VALUES ('VENDOR','범위 선택 업체')").lastrowid
    person_id = db.execute(
        "INSERT INTO contacts(kind,name,company_id) VALUES ('PERSON','범위 선택 담당',?)", (vendor_id,)
    ).lastrowid
    masters = db.query("SELECT id FROM master_items ORDER BY sort_order LIMIT 4")
    event_id = service.create_event("셀 범위 일괄 지정", date.today(), None, [row["id"] for row in masters])
    page = EventsPage(service, db); page.set_event(event_id)
    target_ids = [int(page._current_tasks[row]["id"]) for row in range(3)]

    # 항목 열의 셀 3개만 드래그한 상황을 재현한다. 완전한 행 선택으로
    # 판정되지 않더라도 세 셀이 닿은 세 행은 모두 일괄 변경 대상이어야 한다.
    page.table.clearSelection()
    page.table.setRangeSelected(QTableWidgetSelectionRange(0, 3, 2, 3), True)
    assert page._selected_task_ids() == target_ids
    monkeypatch.setattr(BulkAssignmentDialog, "exec", lambda _dialog: True)
    monkeypatch.setattr(
        BulkAssignmentDialog, "values",
        lambda _dialog: {"vendor_id": vendor_id, "assignee_id": person_id},
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *_args, **_kwargs: None)
    page.bulk_assign_button.click(); app.processEvents()

    rows = db.query(
        "SELECT vendor_id,assignee_id FROM event_tasks WHERE id IN (?,?,?) ORDER BY id", target_ids,
    )
    assert len(rows) == 3
    assert all((row["vendor_id"], row["assignee_id"]) == (vendor_id, person_id) for row in rows)
    untouched = db.one("SELECT vendor_id,assignee_id FROM event_tasks WHERE id=?", (page._current_tasks[3]["id"],))
    assert tuple(untouched) == (None, None)
    page.close(); db.close()


def test_master_has_no_dday_columns_and_settlement_uses_all_registered_vendors(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "manual-dates-settlement-vendors.db"); service = EventService(db)
    master = db.one("SELECT id FROM master_items ORDER BY sort_order LIMIT 1")
    event_id = service.create_event("직접 일정", date.today(), date.today() + timedelta(days=2), [master["id"]])
    master_page = MasterPage(db)
    headers = [master_page.table.horizontalHeaderItem(index).text() for index in range(master_page.table.columnCount())]
    assert "일정 기준" not in headers and "시작 D±" not in headers and "마감 D±" not in headers
    checklist = EventsPage(service, db); checklist.set_event(event_id)
    assert checklist.table.item(0, 4).text() == db.one("SELECT detail FROM master_items WHERE id=?", (master["id"],))["detail"]
    assert checklist.table.item(0, 6).text() == "미입력"
    assert checklist.table.item(0, 7).text() == "미입력"
    checklist._open_cell_editor(0, 6)
    assert checklist.table.cellWidget(0, 6) is None
    assert checklist.table._date_popup is not None
    assert "날짜 비우기" in {button.text() for button in checklist.table._date_popup.findChildren(QPushButton)}
    checklist.table.close_cell_editor()
    assert checklist._commit_date(0, checklist._current_tasks[0], 6, "planned_start", "2026-08-20") is None
    assert checklist.table.item(0, 6).text() == "2026-08-20"
    assert checklist._commit_date(0, checklist._current_tasks[0], 6, "planned_start", None) is None
    assert checklist.table.item(0, 6).text() == "미입력"

    new_vendor = db.execute("INSERT INTO contacts(kind,name) VALUES ('VENDOR','정산 즉시 업체')").lastrowid
    settlement = SettlementPage(service, db); settlement.set_event(event_id)
    assert new_vendor in {row["id"] for row in settlement._vendors}
    task_row = next(iter(settlement._task_rows.values()))
    settlement._open_cell_editor(task_row, 10)
    editor = settlement.table.cellWidget(task_row, 10)
    assert editor.findData(new_vendor) >= 0
    settlement.table.close_cell_editor()
    settlement.close(); checklist.close(); master_page.close(); db.close()


def test_merged_master_category_edit_renames_the_whole_group(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "master-group-edit.db"); page = MasterPage(db)
    cell = page.table.item(0, 1)
    old_major = cell.data(GROUP_MAJOR_ROLE)
    group_count = db.one("SELECT COUNT(*) count FROM master_items WHERE major=?", (old_major,))["count"]
    assert page.table.rowSpan(0, 1) > 1 and group_count > 1
    cell.setText("통합 분류 수정")
    assert db.one("SELECT COUNT(*) count FROM master_items WHERE major=?", (old_major,))["count"] == 0
    assert db.one("SELECT COUNT(*) count FROM master_items WHERE major='통합 분류 수정'")["count"] == group_count
    page.close(); db.close()


def test_checklist_status_choice_updates_database_and_keeps_order_number(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "status-choice.db"); service = EventService(db)
    ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY sort_order")]
    event_id = service.create_event("상태 변경", date.today(), date.today() + timedelta(days=2), ids)
    page = EventsPage(service, db); page.set_event(event_id)
    assert isinstance(page._current_tasks[0], dict)
    task_id = int(page._current_tasks[0]["id"])
    page._open_cell_editor(0, 5)
    editor = page.table.cellWidget(0, 5)
    target = STATUSES.index("완료")
    editor.setCurrentIndex(target); editor.activated.emit(target); app.processEvents()
    assert db.one("SELECT status FROM event_tasks WHERE id=?", (task_id,))["status"] == "완료"
    assert page.table.item(0, 5).text() == "완료"
    assert page.table.item(0, 0).text() == "1"
    assert not (page.table.item(0, 0).flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert page.table.cellWidget(0, 5) is None
    del editor
    page.close(); db.close()


def test_spreadsheet_checkbox_indicator_is_centered_in_its_cell():
    app = QApplication.instance() or QApplication([])
    table = FastEditableTable(1, 1); table.resize(100, 70); table.show(); app.processEvents()
    option = QStyleOptionViewItem(); option.rect = QRect(0, 0, 80, 48); option.widget = table
    indicator = SpreadsheetItemDelegate.check_indicator_rect(option, table.style())
    assert abs(indicator.center().x() - option.rect.center().x()) <= 1
    assert abs(indicator.center().y() - option.rect.center().y()) <= 1
    table.close()


def test_checklist_order_column_stays_fixed_when_columns_fit(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "fixed-order.db"); service = EventService(db)
    ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY sort_order")]
    event_id = service.create_event("순서 열", date.today(), date.today() + timedelta(days=2), ids)
    page = EventsPage(service, db); page.set_event(event_id); page.resize(1600, 800); page.show(); app.processEvents()
    before = page.table.columnWidth(0)
    fit_table_to_view(page.table)
    assert before == 52 == page.table.columnWidth(0)
    assert page.table.horizontalHeader().sectionResizeMode(0) == page.table.horizontalHeader().ResizeMode.Fixed
    assert [page.table.item(row, 0).text() for row in range(3)] == ["1", "2", "3"]
    page.close(); db.close()


def test_master_order_column_matches_checklist_fixed_component(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "master-order.db")
    page = MasterPage(db); page.resize(1600, 800); page.show(); app.processEvents()
    fit_table_to_view(page.table)
    assert page.table.horizontalHeaderItem(0).text() == "순서"
    assert page.table.columnWidth(0) == 52
    assert page.table.horizontalHeader().sectionResizeMode(0) == page.table.horizontalHeader().ResizeMode.Fixed
    assert [page.table.item(row, 0).text() for row in range(3)] == ["1", "2", "3"]
    assert not (page.table.item(0, 0).flags() & Qt.ItemFlag.ItemIsUserCheckable)
    page.close(); db.close()


def test_import_master_explains_when_every_master_is_already_in_event(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "all-master-imported.db"); service = EventService(db)
    ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY sort_order")]
    event_id = service.create_event("모두 포함", date.today(), date.today() + timedelta(days=2), ids)
    page = EventsPage(service, db); page.set_event(event_id)
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda _parent, title, text: messages.append((title, text)))
    page.import_master()
    assert messages and "기본 항목 120개가 모두 포함" in messages[0][1]
    page.close(); db.close()


def test_checklist_excludes_immediately_and_restores_from_removed_view(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "exclude-restore.db"); service = EventService(db)
    master = db.one("SELECT id FROM master_items ORDER BY sort_order LIMIT 1")
    event_id = service.create_event("제외 복원", date.today(), None, [master["id"]])
    page = EventsPage(service, db); page.set_event(event_id)
    task_id = int(page._current_tasks[0]["id"])
    monkeypatch.setattr(QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes)

    page.table.selectRow(0)
    page.remove_selected()
    removed = db.one("SELECT is_removed,removed_reason FROM event_tasks WHERE id=?", (task_id,))
    assert tuple(removed) == (1, "")
    assert page.table.rowCount() == 0

    page.removed_toggle.setChecked(True)
    assert page.remove_button.text() == "선택 항목 복원"
    assert page.table.rowCount() == 1
    page.table.selectRow(0)
    page.remove_selected()
    assert db.one("SELECT is_removed FROM event_tasks WHERE id=?", (task_id,))["is_removed"] == 0
    assert page.table.rowCount() == 0
    page.close(); db.close()


def test_master_item_dialog_uses_shared_dynamic_categories_and_units(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "dynamic-master-choices.db")
    db.execute(
        "UPDATE master_items SET major=?,minor=?,unit=? WHERE id=(SELECT MIN(id) FROM master_items)",
        ("신규 대분류", "신규 중분류", "회차"),
    )
    catalog = load_master_choice_catalog(db)
    assert "신규 대분류" in catalog.majors
    assert catalog.minors_by_major["신규 대분류"] == ("신규 중분류",)
    assert "회차" in catalog.units

    dialog = MasterItemDialog(category_choices=catalog)
    major_index = dialog.major.findText("신규 대분류")
    dialog.major.setCurrentIndex(major_index)
    dialog.major.combo.activated.emit(major_index)
    assert dialog.minor.findText("신규 중분류") >= 0
    assert dialog.unit.findText("회차") >= 0
    assert dialog.major.add_button.text() == "+ 새 대분류"
    assert dialog.minor.add_button.text() == "+ 새 중분류"
    assert dialog.unit.add_button.text() == "+ 새 단위"
    assert dialog.major.open_button.text() == "▾"
    assert not dialog.major.combo.isEditable()
    assert not dialog.minor.combo.isEditable()
    assert not dialog.unit.combo.isEditable()
    dialog.major.combo.showPopup()
    assert dialog.major.combo.popup_is_open()
    assert dialog.major.combo.view().model().rowCount() == len(catalog.majors)
    dialog.major.combo.hidePopup()

    dialog.major.add_value("직접 추가 대분류")
    dialog.minor.add_value("직접 추가 중분류")
    dialog.unit.add_value("직접 추가 단위")
    dialog.name.setText("새 업무")
    values = dialog.values()
    assert values["major"] == "직접 추가 대분류"
    assert values["minor"] == "직접 추가 중분류"
    assert values["unit"] == "직접 추가 단위"
    dialog.close(); db.close()


def test_new_master_unit_is_available_in_all_spreadsheet_unit_editors(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "shared-unit-editors.db"); service = EventService(db)
    db.execute(
        "UPDATE master_items SET unit=? WHERE id=(SELECT MIN(id) FROM master_items)",
        ("회차",),
    )
    ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY sort_order")]
    event_id = service.create_event("공통 단위", date.today(), date.today() + timedelta(days=2), ids)
    master = MasterPage(db); settlement = SettlementPage(service, db); settlement.set_event(event_id)

    master._open_cell_editor(0, 6)
    assert master.table.cellWidget(0, 6).findText("회차") >= 0
    master.table.close_cell_editor()
    task_row = next(row for row in range(settlement.table.rowCount()) if settlement.table.item(row, 4).data(Qt.ItemDataRole.UserRole))
    settlement._open_cell_editor(task_row, 4)
    assert settlement.table.cellWidget(task_row, 4).findText("회차") >= 0
    settlement.table.close_cell_editor()
    master.close(); settlement.close(); db.close()


def test_checklist_and_master_editors_stay_inside_rows_and_show_group_boundaries(tmp_path):
    app = QApplication.instance() or QApplication([])
    previous_style = app.styleSheet()
    app.setStyleSheet(application_stylesheet())
    db = Database(tmp_path / "table-layout.db")
    service = EventService(db)
    master_ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY sort_order")]
    event_id = service.create_event("표 검증 행사", date.today(), date.today() + timedelta(days=5), master_ids)
    checklist = EventsPage(service, db)
    master = MasterPage(db)
    for page in (checklist, master):
        page.resize(1800, 800)
        page.show()
    checklist.set_event(event_id)
    app.processEvents()

    for table, editor_column in ((checklist.table, 5), (master.table, 6)):
        cell_rect = table.visualRect(table.model().index(0, editor_column))
        assert table.rowHeight(0) == 48
        assert table.cellWidget(0, editor_column) is None
        QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=cell_rect.center())
        app.processEvents()
        assert table.cellWidget(0, editor_column) is None
        QTest.mouseDClick(table.viewport(), Qt.MouseButton.LeftButton, pos=cell_rect.center())
        app.processEvents()
        editor_rect = table.cellWidget(0, editor_column).geometry()
        assert editor_rect.top() >= cell_rect.top()
        assert editor_rect.bottom() <= cell_rect.bottom()
        table.close_cell_editor()

        model = table.model()
        delegate = table.itemDelegate()
        levels = [delegate.separator_level(model, row) for row in range(1, table.rowCount())]
        assert 2 in levels  # 대분류 변경: 굵은 주황색 경계
        assert 1 in levels  # 중분류 변경: 중간 굵기의 회색 경계

    anchor = checklist.table.item(0, 1)
    assert anchor.data(GROUP_MAJOR_ROLE)
    assert anchor.data(GROUP_MINOR_ROLE)
    assert checklist.table.horizontalHeaderItem(1).text() == "대분류"
    assert checklist.table.horizontalHeaderItem(2).text() == "중분류"
    assert master.table.rowSpan(0, 1) > 1
    assert master.table.rowSpan(0, 2) > 1
    checklist.close(); master.close(); db.close()
    app.setStyleSheet(previous_style)


def test_combo_popup_container_has_no_opaque_square_corners():
    app = QApplication.instance() or QApplication([])
    previous_style = app.styleSheet(); app.setStyleSheet(application_stylesheet())
    polisher = ComboPopupPolisher(app)
    app.installEventFilter(polisher)
    combo = AppComboBox(); combo.addItems(["미착수", "진행중", "확인요청", "완료", "보류", "해당없음"]); combo.resize(150, 44); combo.show(); combo.showPopup()
    app.processEvents()
    container = combo.view().window()
    assert container.metaObject().className() == "QComboBoxPrivateContainer"
    assert container.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    image = container.grab().toImage()
    light_pixels = sum(
        image.pixelColor(x, y).value() >= 200
        for x in range(image.width())
        for y in range(image.height())
    )
    assert light_pixels / (image.width() * image.height()) > 0.6
    combo.hidePopup(); combo.close(); app.removeEventFilter(polisher); app.setStyleSheet(previous_style)


def test_editable_table_combo_stays_open_when_popup_moves_line_edit_focus():
    app = QApplication.instance() or QApplication([])
    table = FastEditableTable(1, 1); table.resize(300, 120); table.show()
    committed = []
    table.open_choice_editor(
        0, 0, [("식", "식"), ("개", "개"), ("명", "명")], "식",
        lambda value: committed.append(value), editable=True,
    )
    editor = table.cellWidget(0, 0)
    # Model the focus-out signal Qt emits while the native Windows popup is
    # open.  Opening a second native popup in the offscreen test backend can
    # corrupt that backend after the popup is destroyed.
    editor._popup_open = True
    editor.lineEdit().editingFinished.emit(); app.processEvents()
    assert table.cellWidget(0, 0) is editor
    assert committed == []
    editor._popup_open = False
    editor.setCurrentIndex(1); editor.activated.emit(1); app.processEvents()
    assert committed == ["개"]
    assert table.cellWidget(0, 0) is None
    del editor
    app.processEvents()
    table.close()


def test_dismissed_dropdown_closes_without_committing_and_single_click_only_selects(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "double-click-edit.db"); service = EventService(db)
    master_id = db.one("SELECT id FROM master_items ORDER BY sort_order LIMIT 1")["id"]
    event_id = service.create_event("더블클릭 편집", date.today(), date.today(), [master_id])
    page = EventsPage(service, db); page.set_event(event_id); page.resize(1500, 700); page.show()
    app.processEvents()

    status_rect = page.table.visualRect(page.table.model().index(0, 5))
    QTest.mouseClick(page.table.viewport(), Qt.MouseButton.LeftButton, pos=status_rect.center())
    app.processEvents()
    assert page.table.currentRow() == 0 and page.table.currentColumn() == 5
    assert page.table.cellWidget(0, 5) is None

    QTest.mouseDClick(page.table.viewport(), Qt.MouseButton.LeftButton, pos=status_rect.center())
    app.processEvents()
    editor = page.table.cellWidget(0, 5)
    assert isinstance(editor, AppComboBox)
    original = page._current_tasks[0]["status"]
    page.table.setCurrentCell(0, 4)
    app.processEvents()
    assert page.table.cellWidget(0, 5) is None
    assert page._current_tasks[0]["status"] == original
    assert db.one("SELECT status FROM event_tasks WHERE event_id=?", (event_id,))["status"] == original

    detail_rect = page.table.visualRect(page.table.model().index(0, 4))
    QTest.mouseClick(page.table.viewport(), Qt.MouseButton.LeftButton, pos=detail_rect.center())
    app.processEvents()
    QTest.mouseDClick(page.table.viewport(), Qt.MouseButton.LeftButton, pos=detail_rect.center())
    app.processEvents()
    detail_editor = page.table.cellWidget(0, 4)
    assert isinstance(detail_editor, QLineEdit)
    detail_editor.setText("더블클릭으로 수정한 세부내용")
    detail_editor.editingFinished.emit(); app.processEvents()
    assert db.one("SELECT detail FROM event_tasks WHERE event_id=?", (event_id,))["detail"] == "더블클릭으로 수정한 세부내용"
    assert page.table.cellWidget(0, 4) is None
    page.close(); db.close()


def test_all_spreadsheet_pages_use_cell_selection_and_double_click_editing(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "all-double-click.db"); service = EventService(db)
    master_id = db.one("SELECT id FROM master_items ORDER BY sort_order LIMIT 1")["id"]
    event_id = service.create_event("전체 표 편집", date.today(), date.today(), [master_id])
    vendor_id = db.execute(
        "INSERT INTO contacts(kind,name,role_note) VALUES ('VENDOR','더블클릭 업체','기존 업종')"
    ).lastrowid
    checklist = EventsPage(service, db); checklist.set_event(event_id)
    settlement = SettlementPage(service, db); settlement.set_event(event_id)
    master = MasterPage(db)
    contacts = ContactsPage(db)
    for page in (checklist, settlement, master, contacts):
        page.resize(1500, 700); page.show()
    app.processEvents()

    tables = [
        checklist.table, settlement.table, master.table,
        contacts.vendor_table, contacts.company_people, contacts.freelancer_table,
    ]
    assert all(table.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectItems for table in tables)
    assert not (master.table.item(0, 1).flags() & Qt.ItemFlag.ItemIsEditable)
    assert not (master.table.item(0, 2).flags() & Qt.ItemFlag.ItemIsEditable)

    task_row = next(iter(settlement._task_rows.values()))
    item_rect = settlement.table.visualRect(settlement.table.model().index(task_row, 2))
    QTest.mouseClick(settlement.table.viewport(), Qt.MouseButton.LeftButton, pos=item_rect.center())
    app.processEvents(); assert settlement.table.cellWidget(task_row, 2) is None
    QTest.mouseDClick(settlement.table.viewport(), Qt.MouseButton.LeftButton, pos=item_rect.center())
    app.processEvents(); item_editor = settlement.table.cellWidget(task_row, 2)
    assert isinstance(item_editor, QLineEdit)
    item_editor.setText("정산표에서 수정한 항목")
    item_editor.editingFinished.emit(); app.processEvents()
    assert db.one("SELECT name FROM event_tasks WHERE event_id=?", (event_id,))["name"] == "정산표에서 수정한 항목"

    vendor_row = next(
        row for row in range(contacts.vendor_table.rowCount())
        if contacts.vendor_table.item(row, 0).data(Qt.ItemDataRole.UserRole) == vendor_id
    )
    industry_rect = contacts.vendor_table.visualRect(contacts.vendor_table.model().index(vendor_row, 1))
    QTest.mouseClick(contacts.vendor_table.viewport(), Qt.MouseButton.LeftButton, pos=industry_rect.center())
    app.processEvents()
    QTest.mouseDClick(contacts.vendor_table.viewport(), Qt.MouseButton.LeftButton, pos=industry_rect.center())
    app.processEvents(); industry_editor = contacts.vendor_table.cellWidget(vendor_row, 1)
    assert isinstance(industry_editor, QLineEdit)
    industry_editor.setText("수정된 업종")
    industry_editor.editingFinished.emit(); app.processEvents()
    assert db.one("SELECT role_note FROM contacts WHERE id=?", (vendor_id,))["role_note"] == "수정된 업종"

    for page in (checklist, settlement, master, contacts):
        page.close()
    db.close()


def test_all_spreadsheet_headers_show_column_resize_guides(tmp_path):
    app = QApplication.instance() or QApplication([])
    previous_style = app.styleSheet(); app.setStyleSheet(application_stylesheet())
    db = Database(tmp_path / "header-guides.db"); service = EventService(db)
    master_id = db.one("SELECT id FROM master_items ORDER BY sort_order LIMIT 1")["id"]
    event_id = service.create_event("열 너비 안내", date.today(), date.today(), [master_id])
    pages = [EventsPage(service, db), SettlementPage(service, db), MasterPage(db), ContactsPage(db)]
    pages[0].set_event(event_id); pages[1].set_event(event_id)
    tables = [
        pages[0].table, pages[1].table, pages[2].table,
        pages[3].vendor_table, pages[3].company_people, pages[3].freelancer_table,
    ]
    for table in tables:
        header = table.horizontalHeader()
        assert header.property("columnResizeGuides") is True
        assert "세로선" in header.toolTip() and "열 너비" in header.toolTip()
        assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Interactive
    assert 'QHeaderView[columnResizeGuides="true"]::section:horizontal' in app.styleSheet()
    assert "border-right: 1px solid #C9CDD3" in app.styleSheet()
    for page in pages:
        page.close()
    db.close(); app.setStyleSheet(previous_style)


def test_spreadsheet_pages_share_editor_table_contract(tmp_path):
    app = QApplication.instance() or QApplication([])
    previous_style = app.styleSheet(); app.setStyleSheet(application_stylesheet())
    db = Database(tmp_path / "shared-table.db"); service = EventService(db)
    master_ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY sort_order")]
    event_id = service.create_event("공통 표 검증", date.today(), date.today() + timedelta(days=3), master_ids)
    pages = [EventsPage(service, db), MasterPage(db), SettlementPage(service, db)]
    pages[0].set_event(event_id); pages[2].set_event(event_id)
    for page in pages:
        page.resize(1800, 850); page.show()
    app.processEvents()
    assert all(page.table.property("embeddedEditors") is True for page in pages)
    assert all(page.table.verticalHeader().defaultSectionSize() == 48 for page in pages)
    assert all(all(page.table.cellWidget(row, column) is None for row in range(page.table.rowCount()) for column in range(page.table.columnCount())) for page in pages)
    settlement = pages[2]
    target = settlement.table.visualRect(settlement.table.model().index(0, 3))
    QTest.mouseClick(settlement.table.viewport(), Qt.MouseButton.LeftButton, pos=target.center())
    app.processEvents()
    assert settlement.table.cellWidget(0, 3) is None
    QTest.mouseDClick(settlement.table.viewport(), Qt.MouseButton.LeftButton, pos=target.center())
    app.processEvents()
    editor_rect = settlement.table.cellWidget(0, 3).geometry()
    cell_rect = settlement.table.visualRect(settlement.table.model().index(0, 3))
    assert editor_rect.top() >= cell_rect.top()
    assert editor_rect.bottom() <= cell_rect.bottom()
    subtotal_row = next(row for row in range(settlement.table.rowCount()) if "소계" in settlement.table.item(row, 0).text())
    assert settlement.table.item(subtotal_row, 0).font().pointSize() > settlement.table.item(0, 0).font().pointSize()
    assert settlement.table.rowSpan(0, 0) > 1
    assert settlement.table.rowSpan(0, 1) > 1
    assert pages[0].table.item(0, 3).textAlignment() & Qt.AlignmentFlag.AlignHCenter
    assert pages[0].table.columnCount() == 12
    assert pages[0].table.horizontalHeaderItem(4).text() == "세부내용"
    assert pages[0].table.horizontalHeaderItem(11).text() == "업체담당자 전화번호"
    assert pages[1].table.item(0, 3).textAlignment() & Qt.AlignmentFlag.AlignHCenter
    assert pages[1].table.item(0, 7).textAlignment() & Qt.AlignmentFlag.AlignRight
    assert pages[2].table.item(0, 2).textAlignment() & Qt.AlignmentFlag.AlignHCenter
    assert pages[2].table.item(0, 5).textAlignment() & Qt.AlignmentFlag.AlignRight
    for page in pages: page.close()
    db.close(); app.setStyleSheet(previous_style)


def test_contact_spreadsheets_use_shared_center_alignment(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "contact-alignment.db"); page = ContactsPage(db)
    for table in (page.vendor_table, page.company_people, page.freelancer_table):
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                assert table.item(row, column).textAlignment() & Qt.AlignmentFlag.AlignHCenter
    page.close(); db.close()


def test_settings_is_separated_and_calendar_header_is_compact(tmp_path):
    app = QApplication.instance() or QApplication([])
    previous_style = app.styleSheet(); app.setStyleSheet(application_stylesheet())
    db = Database(tmp_path / "layout.db"); window = MainWindow(db, enable_update_check=False)
    window.resize(1440, 900); window.show(); app.processEvents()
    assert window.nav_buttons[4].y() > window.nav_buttons[3].y() + window.nav_buttons[3].height() + 100
    calendar = CalendarPage(window.service, db)
    calendar.resize(1200, 780); calendar.show(); app.processEvents()
    header_centers = [
        widget.mapToGlobal(widget.rect().center()).y()
        for widget in (
            calendar.previous_button, calendar.month_label, calendar.following_button,
            calendar.today_button, calendar.toggle, calendar.export_button,
        )
    ]
    assert max(header_centers) - min(header_centers) <= 1
    calendar_top = calendar.calendar.mapToGlobal(calendar.calendar.rect().topLeft()).y()
    side_top = calendar.side.mapToGlobal(calendar.side.rect().topLeft()).y()
    assert calendar_top == side_top
    navigation_center = calendar.navigation.mapToGlobal(calendar.navigation.rect().center()).x()
    timeline_center = calendar.calendar.mapToGlobal(calendar.calendar.rect().center()).x()
    assert abs(navigation_center - timeline_center) <= 1
    following_right = calendar.following_button.mapToGlobal(calendar.following_button.rect().topRight()).x()
    today_left = calendar.today_button.mapToGlobal(calendar.today_button.rect().topLeft()).x()
    assert 1 <= today_left - following_right <= 10
    assert not hasattr(calendar, "description")
    assert calendar.export_button.x() > calendar.toggle.x()
    assert calendar.export_button.height() == calendar.toggle.height() == 42
    assert not calendar.export_button.icon().isNull()
    assert calendar.export_button.toolTip() == "달력 PDF로 내보내기"
    calendar.close(); window.close(); db.close(); app.setStyleSheet(previous_style)


def test_calendar_marks_today_and_today_button_restores_current_date(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "calendar-today.db"); service = EventService(db)
    page = CalendarPage(service, db); page.resize(1200, 780); page.show(); app.processEvents()
    today = date.today()
    page.calendar.set_month(today.year - 1, today.month)
    page.calendar.selected = date(today.year - 1, today.month, 1)
    page.today_button.click(); app.processEvents()
    assert (page.calendar.year, page.calendar.month) == (today.year, today.month)
    assert page.calendar.selected == today
    assert page.month_label.text() == f"{today.year}년 {today.month}월"

    timeline = page.calendar
    image = timeline.grab().toImage()
    weeks = timeline._calendar_weeks()
    week_index, column = next(
        (week_index, column)
        for week_index, week in enumerate(weeks)
        for column, value in enumerate(week)
        if value == today
    )
    cell_w = timeline.width() / 7
    row_h = (timeline.height() - 34) / 6
    left = int(column * cell_w + 5); top = int(34 + week_index * row_h + 3)
    orange_pixels = sum(
        image.pixelColor(x, y).name().upper() == "#F25B24"
        for x in range(left, min(left + 27, image.width()))
        for y in range(top, min(top + 23, image.height()))
    )
    assert orange_pixels > 100
    page.close(); db.close()


def test_event_dialog_places_master_items_on_right_and_shows_freelancer_role(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "event-dialog-layout.db")
    masters = db.query("SELECT * FROM master_items WHERE active=1 ORDER BY sort_order")
    freelancers = [{"id": 991, "name": "홍길동", "role_note": "영상 촬영", "phone": ""}]
    dialog = EventDialog(masters, freelancers=freelancers)
    dialog.show(); app.processEvents()
    assert dialog.freelancer_list.item(0).text() == "홍길동 · 영상 촬영"
    assert isinstance(dialog.budget_tax_mode, AppComboBox)
    tree_left = dialog.tree.mapToGlobal(dialog.tree.rect().topLeft()).x()
    participants_right = dialog.freelancer_list.mapToGlobal(dialog.freelancer_list.rect().topRight()).x()
    assert tree_left > participants_right
    dialog.close(); db.close()


def test_event_dialog_can_switch_item_tree_to_previous_event(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "previous-event-dialog.db")
    service = EventService(db)
    masters = db.query("SELECT * FROM master_items ORDER BY sort_order LIMIT 2")
    source_id = service.create_event(
        "지난 시민의 날", date(2026, 7, 1), date(2026, 7, 2), [row["id"] for row in masters]
    )
    events = service.list_events()
    dialog = EventDialog(
        masters, previous_events=events, previous_task_loader=service.list_tasks,
    )
    assert dialog.previous_button.isEnabled()
    dialog._populate_previous_tree(service.list_tasks(source_id), source_id, True)
    values = dialog.import_values()
    assert values["source_event_id"] == source_id
    assert values["copy_settlement_prices"] is True
    assert values["source_task_ids"] == [row["id"] for row in service.list_tasks(source_id)]
    assert "지난 시민의 날" in dialog.tree.headerItem().text(0)
    dialog.close(); db.close()


def test_previous_event_import_dialog_defaults_to_items_only(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "previous-event-choice.db")
    service = EventService(db)
    master = db.one("SELECT id FROM master_items ORDER BY sort_order LIMIT 1")
    event_id = service.create_event("기준 행사", date(2026, 7, 1), None, [master["id"]])
    chooser = PreviousEventImportDialog(service.list_events())
    assert chooser.values() == (event_id, False)
    chooser.with_settlement.setChecked(True)
    assert chooser.values() == (event_id, True)
    chooser.close(); db.close()


def test_calendar_cards_use_soft_category_border_colors():
    app = QApplication.instance() or QApplication([])
    base = {
        "id": 21, "name": "일정 카드", "status": "미착수",
        "planned_start": date.today().isoformat(), "due_date": (date.today() + timedelta(days=3)).isoformat(),
    }
    system = CalendarTaskCard({**base, "major": "시스템"})
    promotion = CalendarTaskCard({**base, "id": 22, "major": "홍보"})
    assert "#B8D4EA" in system.styleSheet()
    assert "#D4C8E6" in promotion.styleSheet()
    assert system.styleSheet() != promotion.styleSheet()


def test_clickable_controls_use_hand_cursor_but_text_input_does_not():
    app = QApplication.instance() or QApplication([])
    polisher = InteractionCursorPolisher(app); app.installEventFilter(polisher)
    button, combo, selectable, text = QPushButton("확인"), AppComboBox(), QListWidget(), QLineEdit()
    combo.addItem("선택"); selectable.addItem("항목")
    for widget in (button, combo, selectable, text): widget.ensurePolished()
    assert button.cursor().shape() == Qt.CursorShape.PointingHandCursor
    assert combo.cursor().shape() == Qt.CursorShape.PointingHandCursor
    assert selectable.viewport().cursor().shape() == Qt.CursorShape.PointingHandCursor
    assert text.cursor().shape() != Qt.CursorShape.PointingHandCursor
    app.removeEventFilter(polisher)


def test_selected_event_checklist_is_preloaded_before_menu_click(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "preload.db"); service = EventService(db)
    ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY sort_order")]
    event_id = service.create_event("사전 로딩", date.today(), date.today() + timedelta(days=3), ids)
    window = MainWindow(db, enable_update_check=False); window.show(); window.select_event(event_id)
    QTest.qWait(300)
    assert window.events._loaded_event_id == event_id
    calls = 0
    original = window.events.refresh_tasks

    def counted():
        nonlocal calls
        calls += 1
        return original()

    window.events.refresh_tasks = counted
    window.nav_buttons[1].click(); app.processEvents()
    assert calls == 0
    assert window.settlement._loaded_event_id == event_id
    window.close(); db.close()


def test_startup_splash_appears_with_progress_and_status():
    app = QApplication.instance() or QApplication([])
    splash = StartupSplash(); splash.show(); app.processEvents()
    assert splash.isVisible()
    assert splash.progress.minimum() == 0 and splash.progress.maximum() == 0
    splash.set_status("대시보드를 구성하고 있습니다…")
    assert splash.status.text() == "대시보드를 구성하고 있습니다…"
    assert splash.width() >= 400 and splash.height() >= 200
    splash.close()


def test_spreadsheet_pages_have_no_priority_ui_and_remain_immediately_scrollable(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "fast-tables.db"); service = EventService(db)
    ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY sort_order")]
    event_id = service.create_event("성능 검증", date.today(), date.today() + timedelta(days=3), ids)

    page_specs = [
        ("checklist", lambda: EventsPage(service, db)),
        ("master", lambda: MasterPage(db)),
        ("settlement", lambda: SettlementPage(service, db)),
    ]
    pages = []
    for name, factory in page_specs:
        started = perf_counter(); page = factory()
        if name != "master":
            page.set_event(event_id)
        app.processEvents()
        assert perf_counter() - started < 0.75
        assert "우선순위" not in [page.table.horizontalHeaderItem(i).text() for i in range(page.table.columnCount())]
        assert all(
            page.table.cellWidget(row, column) is None
            for row in range(page.table.rowCount())
            for column in range(page.table.columnCount())
        )
        started = perf_counter()
        page.table.verticalScrollBar().setValue(page.table.verticalScrollBar().maximum())
        app.processEvents()
        assert perf_counter() - started < 0.25
        pages.append(page)

    settlement = pages[2]
    task_id = next(iter(settlement._items))
    rows_before = settlement.table.rowCount()
    refresh_calls = 0
    original_refresh = settlement.refresh

    def counted_refresh():
        nonlocal refresh_calls
        refresh_calls += 1
        return original_refresh()

    settlement.refresh = counted_refresh
    started = perf_counter()
    settlement._commit_value(task_id, 3, "quantity", 2)
    app.processEvents()
    assert perf_counter() - started < 0.25
    assert refresh_calls == 0
    assert settlement.table.rowCount() == rows_before

    for page in pages:
        page.close()
    db.close()
