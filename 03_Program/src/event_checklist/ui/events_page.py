from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDateEdit, QDoubleSpinBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ..choices import load_master_choice_catalog
from ..theme import status_color
from .dialogs import CustomTaskDialog, MasterImportDialog, TaskDetailsDialog
from .widgets import (
    GROUP_MAJOR_ROLE, GROUP_MINOR_ROLE, AppComboBox, FastEditableTable, configure_editable_table,
    fit_table_to_view,
)

STATUSES = ["미착수", "진행중", "확인요청", "완료", "보류", "해당없음"]


class EventsPage(QWidget):
    edit_requested = Signal(int)
    changed = Signal(int)

    def __init__(self, service, db, parent=None):
        super().__init__(parent)
        self.service = service
        self.db = db
        self.event_id: int | None = None
        self.loading = False
        self._loaded_event_id: int | None = None
        self._current_tasks = []
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 32)
        root.setSpacing(14)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("체크리스트")
        title.setObjectName("PageTitle")
        self.description = QLabel("선택한 행사의 업무 상태와 일정을 관리합니다.")
        self.description.setObjectName("PageDescription")
        title_box.addWidget(title)
        title_box.addWidget(self.description)
        top.addLayout(title_box)
        top.addStretch()
        self.remove_button = None
        for text, callback, primary in [
            ("기본항목 가져오기", self.import_master, False),
            ("직접 항목 추가", self.add_custom, True),
            ("선택 항목 제외", self.remove_selected, False),
        ]:
            button = QPushButton(text)
            button.setProperty("primary", primary)
            button.clicked.connect(callback)
            top.addWidget(button)
            if text == "선택 항목 제외":
                self.remove_button = button
        self.removed_toggle = QCheckBox("제외 항목 보기")
        self.removed_toggle.toggled.connect(self._removed_view_toggled)
        top.addWidget(self.removed_toggle)
        root.addLayout(top)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("항목·세부내용·메모 검색")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh_tasks)
        self.status_filter = AppComboBox()
        self.status_filter.addItem("모든 상태", "")
        for status in STATUSES:
            self.status_filter.addItem(status, status)
        self.status_filter.currentIndexChanged.connect(self.refresh_tasks)
        self.major_filter = AppComboBox()
        self.major_filter.addItem("모든 대분류", "")
        for major in load_master_choice_catalog(self.db).majors:
            self.major_filter.addItem(major, major)
        self.major_filter.currentIndexChanged.connect(self.refresh_tasks)
        self.summary = QLabel("")
        self.summary.setObjectName("Muted")
        edit_event = QPushButton("행사 정보 수정")
        edit_event.clicked.connect(lambda: self.event_id and self.edit_requested.emit(self.event_id))
        fit = QPushButton("열 너비 맞춤")
        fit.clicked.connect(lambda: fit_table_to_view(self.table))
        filters.addWidget(self.search, 1)
        filters.addWidget(self.status_filter)
        filters.addWidget(self.major_filter)
        filters.addWidget(self.summary)
        filters.addWidget(edit_event)
        filters.addWidget(fit)
        root.addLayout(filters)

        self.table = FastEditableTable(0, 12)
        self.table.setHorizontalHeaderLabels([
            "순서", "대분류", "중분류", "항목", "세부내용", "상태", "작업 시작일", "마감일",
            "담당자(PM)", "업체", "업체담당자", "업체담당자 전화번호",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        configure_editable_table(
            self.table, [52, 92, 116, 190, 260, 112, 125, 125, 155, 145, 165, 150], grouped=True
        )
        self.table.set_fixed_columns({0: 52})
        self.table.cellClicked.connect(self._open_cell_editor)
        self.table.doubleClicked.connect(self.edit_task_details)
        root.addWidget(self.table, 1)

    def set_event(self, event_id: int | None, *, force: bool = False):
        if not force and self._loaded_event_id == event_id:
            return
        self.event_id = event_id
        event = self.service.get_event(event_id) if event_id else None
        self.description.setText(f"{event['name']}의 업무 상태와 일정을 관리합니다." if event else "행사를 선택하세요.")
        self.refresh_tasks()
        self._loaded_event_id = event_id

    def invalidate(self):
        self._loaded_event_id = None

    def refresh_events(self, selected_event_id: int | None = None):
        self.set_event(selected_event_id if selected_event_id is not None else self.event_id)

    def import_master(self):
        if not self.event_id:
            return
        masters = self.db.query(
            """SELECT m.*, COALESCE(t.is_removed,0) is_removed FROM master_items m
               LEFT JOIN event_tasks t ON t.event_id=? AND t.master_item_id=m.id
               WHERE t.id IS NULL OR t.is_removed=1 ORDER BY m.sort_order""", (self.event_id,))
        if not masters:
            total = self.db.one("SELECT COUNT(*) count FROM master_items")["count"]
            QMessageBox.information(
                self,
                "기본항목",
                f"현재 행사에 기본 항목 {total}개가 모두 포함되어 있습니다.\n\n"
                "설정 > 기본 항목에서 새 항목을 추가하거나, 체크리스트에서 항목을 제외하면 다시 가져올 수 있습니다.",
            )
            return
        dialog = MasterImportDialog(masters, self)
        if dialog.exec():
            try:
                added, restored = self.service.add_master_tasks(self.event_id, dialog.selected_ids())
            except Exception as exc:
                QMessageBox.critical(self, "가져오기 실패", f"기본 항목을 가져오지 못했습니다.\n\n{exc}")
                return
            QMessageBox.information(self, "가져오기 완료", f"새로 추가 {added}개 · 기존 기록 복원 {restored}개")
            self.removed_toggle.setChecked(False)
            self.refresh_tasks()
            self.changed.emit(self.event_id)

    def add_custom(self):
        if not self.event_id:
            return
        choices = load_master_choice_catalog(self.db)
        dialog = CustomTaskDialog(
            self.service.get_event(self.event_id), self,
            category_choices=choices, unit_choices=choices.units,
        )
        if dialog.exec():
            try:
                self.service.add_custom_task(self.event_id, **dialog.values())
            except Exception as exc:
                QMessageBox.critical(self, "항목 추가 실패", f"항목을 추가하지 못했습니다.\n\n{exc}")
                return
            self.refresh_tasks()
            self.changed.emit(self.event_id)

    def remove_selected(self):
        ids = self._selected_task_ids()
        if not ids:
            action = "복원" if self.removed_toggle.isChecked() else "제외"
            QMessageBox.information(self, "항목 선택", f"{action}할 항목 행을 선택하세요.")
            return
        removed_view = self.removed_toggle.isChecked()
        action = "복원" if removed_view else "제외"
        answer = QMessageBox.question(
            self, f"항목 {action}", f"선택한 {len(ids)}개 항목을 {action}할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.set_task_removed(ids, not removed_view)
        except Exception as exc:
            QMessageBox.critical(self, f"항목 {action} 실패", str(exc))
            return
        self.refresh_tasks()
        self.changed.emit(self.event_id or 0)

    def _removed_view_toggled(self, checked: bool):
        if self.remove_button is not None:
            self.remove_button.setText("선택 항목 복원" if checked else "선택 항목 제외")
        self.refresh_tasks()

    def _selected_task_ids(self):
        ids = []
        for index in self.table.selectionModel().selectedRows():
            item = self.table.item(index.row(), 3)
            if item:
                ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return ids

    def edit_task_details(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._current_tasks):
            return
        task = self._current_tasks[row]
        dialog = TaskDetailsDialog(task, self, unit_choices=load_master_choice_catalog(self.db).units)
        if dialog.exec():
            try:
                self.service.update_task(task["id"], **dialog.values())
            except Exception as exc:
                QMessageBox.critical(self, "항목 수정 실패", str(exc))
                return
            self.refresh_tasks()
            self.changed.emit(self.event_id or 0)

    def refresh_tasks(self):
        self.loading = True
        self._sync_major_filter()
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table.reset_spans()
        self.table.setRowCount(0)
        if not self.event_id:
            self.summary.setText("행사를 선택하세요")
            self.loading = False
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            return
        tasks = [dict(row) for row in self.service.list_tasks(
            self.event_id, self.search.text().strip(), self.status_filter.currentData() or "",
            self.major_filter.currentData() or "", include_removed=self.removed_toggle.isChecked())]
        if self.removed_toggle.isChecked():
            tasks = [row for row in tasks if row["is_removed"]]
        self._current_tasks = tasks
        event = self.service.get_event(self.event_id)
        # 설정에서 추가한 업체와 담당자를 별도의 행사 참여자 편집 없이 바로
        # 선택할 수 있도록 전체 연락처를 한 번 읽고 업체별로 나눈다.
        vendors = self.db.query("SELECT * FROM contacts WHERE kind='VENDOR' ORDER BY name,id")
        all_assignees = self.db.query(
            """SELECT p.*,v.name company_name FROM contacts p
               LEFT JOIN contacts v ON v.id=p.company_id
               WHERE p.kind='PERSON' ORDER BY p.name,COALESCE(v.name,''),p.id"""
        )
        assignees_by_vendor = {
            int(vendor["id"]): [row for row in all_assignees if row["company_id"] == vendor["id"]]
            for vendor in vendors
        }
        pm_assignees = [
            row for row in all_assignees
            if event and event["pm_vendor_id"] and row["company_id"] == event["pm_vendor_id"]
        ]
        self.table.clearContents(); self.table.setRowCount(len(tasks))
        self._vendors = vendors
        self._all_assignees = all_assignees
        self._assignees_by_vendor = assignees_by_vendor
        self._pm_assignees = pm_assignees
        for row_index, task in enumerate(tasks):
            task_id = int(task["id"])
            order = QTableWidgetItem(str(row_index + 1))
            order.setData(Qt.ItemDataRole.UserRole, task_id)
            order.setFlags(order.flags() & ~(Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsUserCheckable))
            self.table.setItem(row_index, 0, order)
            for column, text in ((1, task["major"]), (2, task["minor"])):
                group = QTableWidgetItem(text)
                group.setData(GROUP_MAJOR_ROLE, task["major"])
                group.setData(GROUP_MINOR_ROLE, task["minor"])
                group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, column, group)
            name = QTableWidgetItem(task["name"]); name.setData(Qt.ItemDataRole.UserRole, task_id)
            tooltip = task["detail"] or "세부내용 없음"
            if task["is_removed"]: tooltip += f"\n제외 사유: {task['removed_reason'] or '미입력'}"
            name.setToolTip(tooltip); self.table.setItem(row_index, 3, name)
            detail = QTableWidgetItem(task["detail"] or "")
            detail.setData(Qt.ItemDataRole.UserRole, task_id)
            detail.setFlags(detail.flags() & ~Qt.ItemFlag.ItemIsEditable)
            detail.setToolTip(task["detail"] or "세부내용 없음")
            self.table.setItem(row_index, 4, detail)
            status = QTableWidgetItem(task["status"]); status.setData(Qt.ItemDataRole.UserRole, task_id)
            status.setFlags(status.flags() & ~Qt.ItemFlag.ItemIsEditable); self._style_status_item(status, task["status"])
            self.table.setItem(row_index, 5, status)
            assignee_name = next(
                (self._assignee_label(x) for x in all_assignees if x["id"] == task["assignee_id"]),
                "미지정",
            )
            pm_name = next((x["name"] for x in pm_assignees if x["id"] == task["pm_assignee_id"]), "미지정")
            for column, text, data in [
                (6, task["planned_start"] or "미입력", task["planned_start"]),
                (7, task["due_date"] or "미입력", task["due_date"]),
                (8, pm_name, task["pm_assignee_id"]),
            ]:
                cell = QTableWidgetItem(text); cell.setData(Qt.ItemDataRole.UserRole, task_id)
                cell.setData(int(Qt.ItemDataRole.UserRole) + 1, data); cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, column, cell)
            vendor = QTableWidgetItem(task["vendor_name"] or "미지정")
            vendor.setData(Qt.ItemDataRole.UserRole, task_id)
            vendor.setData(int(Qt.ItemDataRole.UserRole) + 1, task["vendor_id"])
            vendor.setFlags(vendor.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_index, 9, vendor)
            contact = QTableWidgetItem(assignee_name); contact.setData(Qt.ItemDataRole.UserRole, task_id)
            contact.setData(int(Qt.ItemDataRole.UserRole) + 1, task["assignee_id"])
            contact.setFlags(contact.flags() & ~Qt.ItemFlag.ItemIsEditable); self.table.setItem(row_index, 10, contact)
            phone = QTableWidgetItem(task["assignee_phone"] or "")
            phone.setData(Qt.ItemDataRole.UserRole, task_id); phone.setFlags(phone.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_index, 11, phone)
            self.table.setRowHeight(row_index, 48)
        self.table.apply_category_spans(1, 2)
        self.summary.setText(f"{len(tasks)}개 항목" + (" · 제외 기록" if self.removed_toggle.isChecked() else ""))
        self.loading = False
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)
        self.table.viewport().update()

    def _sync_major_filter(self):
        current = self.major_filter.currentData() or ""
        majors = load_master_choice_catalog(self.db).majors
        existing = tuple(self.major_filter.itemData(index) for index in range(1, self.major_filter.count()))
        if existing == majors:
            return
        self.major_filter.blockSignals(True)
        self.major_filter.clear()
        self.major_filter.addItem("모든 대분류", "")
        for major in majors:
            self.major_filter.addItem(major, major)
        self.major_filter.setCurrentIndex(max(0, self.major_filter.findData(current)))
        self.major_filter.blockSignals(False)

    @staticmethod
    def _style_status_item(item: QTableWidgetItem, status: str) -> None:
        fg, bg = status_color(status)
        item.setForeground(QColor(fg)); item.setBackground(QColor(bg))
        font = item.font(); font.setBold(True); item.setFont(font)

    def _task_for_row(self, row: int):
        return self._current_tasks[row] if 0 <= row < len(self._current_tasks) else None

    @staticmethod
    def _assignee_label(person) -> str:
        company = str(person["company_name"] or "").strip()
        return f"{person['name']} · {company}" if company else f"{person['name']} · 프리랜서"

    def _open_cell_editor(self, row: int, column: int) -> None:
        if self.loading or column not in {5, 6, 7, 8, 9, 10}:
            return
        task = self._task_for_row(row)
        if not task or task["is_removed"]:
            return
        task_id = int(task["id"])
        if column == 5:
            choices = [(status, status) for status in STATUSES]
            self.table.open_choice_editor(row, column, choices, task["status"],
                                          lambda value: self._commit_status(row, task, value))
        elif column in {6, 7}:
            field = "planned_start" if column == 6 else "due_date"
            self.table.open_date_editor(row, column, task[field],
                                        lambda value: self._commit_date(row, task, column, field, value))
        elif column == 8:
            choices = [("미지정", None)] + [(x["name"], x["id"]) for x in self._pm_assignees]
            self.table.open_choice_editor(row, column, choices, task["pm_assignee_id"],
                                          lambda value: self._commit_simple(row, task, column, "pm_assignee_id", value, choices))
        elif column == 9:
            choices = [("미지정", None)] + [(x["name"], x["id"]) for x in self._vendors]
            self.table.open_choice_editor(row, column, choices, task["vendor_id"],
                                          lambda value: self._commit_vendor(row, task, value, choices))
        elif column == 10:
            rows = self._assignees_by_vendor.get(int(task["vendor_id"]), []) if task["vendor_id"] else []
            choices = [("미지정", None)] + [(self._assignee_label(x), x["id"]) for x in rows]
            self.table.open_choice_editor(row, column, choices, task["assignee_id"],
                                          lambda value: self._commit_vendor_contact(row, task, value, choices))

    def _commit_simple(self, row, task, column, field, value, choices):
        self.service.update_task(int(task["id"]), **{field: value}); task[field] = value
        text = next((label for label, data in choices if data == value), "미지정")
        cell = self.table.item(row, column); cell.setText(text); cell.setData(int(Qt.ItemDataRole.UserRole) + 1, value)
        self.changed.emit(self.event_id or 0)

    def _commit_status(self, row, task, value):
        self.service.update_task(int(task["id"]), status=value); task["status"] = value
        cell = self.table.item(row, 5); cell.setText(value); self._style_status_item(cell, value)
        self.changed.emit(self.event_id or 0)

    def _commit_date(self, row, task, column, field, value):
        try:
            self.service.update_task(int(task["id"]), **{field: value})
        except ValueError as exc:
            QMessageBox.warning(self, "날짜 확인", str(exc)); return False
        task[field] = value
        self.table.item(row, column).setText(value or "미입력")
        self.changed.emit(self.event_id or 0)

    def _commit_vendor_contact(self, row, task, value, choices):
        self._commit_simple(row, task, 10, "assignee_id", value, choices)
        person = next((x for x in self._all_assignees if x["id"] == value), None)
        task["assignee_phone"] = person["phone"] if person else ""
        self.table.item(row, 11).setText(task["assignee_phone"] or "")

    def _commit_vendor(self, row, task, vendor_id, choices):
        task_id = int(task["id"]); assignee_id = task["assignee_id"]
        fields = {"vendor_id": vendor_id}
        if assignee_id:
            rows = self._assignees_by_vendor.get(int(vendor_id), []) if vendor_id else []
            allowed = {int(x["id"]) for x in rows}
            if int(assignee_id) not in allowed:
                QMessageBox.information(self, "담당자 변경 안내", "새 업체 소속과 맞지 않는 기존 담당자를 미지정으로 전환합니다.")
                fields["assignee_id"] = None; task["assignee_id"] = None
                task["assignee_phone"] = ""; self.table.item(row, 10).setText("미지정"); self.table.item(row, 11).setText("")
        self.service.update_task(task_id, **fields); task["vendor_id"] = vendor_id
        cell = self.table.item(row, 9); cell.setText(next((x for x, data in choices if data == vendor_id), "미지정"))
        cell.setData(int(Qt.ItemDataRole.UserRole) + 1, vendor_id); self.changed.emit(self.event_id or 0)

    def _update(self, task_id, **values):
        if self.loading: return
        self.service.update_task(task_id, **values); self.changed.emit(self.event_id or 0)
