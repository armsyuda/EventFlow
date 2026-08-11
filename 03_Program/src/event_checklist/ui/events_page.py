from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QHBoxLayout,
    QLabel, QInputDialog, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ..schedule import d_day, d_day_label
from ..theme import status_color
from .dialogs import CustomTaskDialog, MasterImportDialog, TaskDetailsDialog
from .widgets import (
    GROUP_MAJOR_ROLE, GROUP_MINOR_ROLE, DirectDateEdit, configure_editable_table,
    configure_money_spin, fit_table_to_view,
)

STATUSES = ["미착수", "진행중", "확인요청", "완료", "보류", "해당없음"]
PRIORITIES = ["상", "중", "하"]


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
        for text, callback, primary in [
            ("기본항목 가져오기", self.import_master, False),
            ("직접 항목 추가", self.add_custom, True),
            ("선택 항목 제외", self.remove_selected, False),
        ]:
            button = QPushButton(text)
            button.setProperty("primary", primary)
            button.clicked.connect(callback)
            top.addWidget(button)
        self.removed_toggle = QCheckBox("제외 항목 보기")
        self.removed_toggle.toggled.connect(self.refresh_tasks)
        top.addWidget(self.removed_toggle)
        root.addLayout(top)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("항목·확인 포인트·메모 검색")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh_tasks)
        self.status_filter = QComboBox()
        self.status_filter.addItem("모든 상태", "")
        for status in STATUSES:
            self.status_filter.addItem(status, status)
        self.status_filter.currentIndexChanged.connect(self.refresh_tasks)
        self.major_filter = QComboBox()
        self.major_filter.addItem("모든 대분류", "")
        for major in ["시스템", "시설", "행사", "홍보", "운영"]:
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

        self.table = QTableWidget(0, 12)
        self.table.setHorizontalHeaderLabels([
            "완료", "분류", "항목", "상태", "우선순위", "담당", "작업 시작일", "마감일",
            "D-Day", "일정", "행사 단가", "업체",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        configure_editable_table(
            self.table, [58, 130, 210, 112, 88, 125, 125, 125, 72, 65, 135, 140], grouped=True
        )
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
               WHERE m.active=1 AND (t.id IS NULL OR t.is_removed=1) ORDER BY m.sort_order""", (self.event_id,))
        if not masters:
            QMessageBox.information(self, "기본항목", "가져올 수 있는 기본항목이 없습니다.")
            return
        dialog = MasterImportDialog(masters, self)
        if dialog.exec():
            added, restored = self.service.add_master_tasks(self.event_id, dialog.selected_ids())
            QMessageBox.information(self, "가져오기 완료", f"새로 추가 {added}개 · 기존 기록 복원 {restored}개")
            self.removed_toggle.setChecked(False)
            self.refresh_tasks()
            self.changed.emit(self.event_id)

    def add_custom(self):
        if not self.event_id:
            return
        dialog = CustomTaskDialog(self.service.get_event(self.event_id), self)
        if dialog.exec():
            self.service.add_custom_task(self.event_id, **dialog.values())
            self.refresh_tasks()
            self.changed.emit(self.event_id)

    def remove_selected(self):
        ids = self._selected_task_ids()
        if not ids:
            QMessageBox.information(self, "항목 선택", "제외할 항목 행을 선택하세요.")
            return
        removed_view = self.removed_toggle.isChecked()
        reason = ""
        if not removed_view:
            reason, accepted = QInputDialog.getText(self, "선택 항목 제외", "제외 사유를 입력하세요.")
            if not accepted: return
        self.service.set_task_removed(ids, not removed_view, reason)
        self.refresh_tasks()
        self.changed.emit(self.event_id or 0)

    def _selected_task_ids(self):
        ids = []
        for index in self.table.selectionModel().selectedRows():
            item = self.table.item(index.row(), 2)
            if item:
                ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return ids

    def edit_task_details(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._current_tasks):
            return
        task = self._current_tasks[row]
        dialog = TaskDetailsDialog(task, self)
        if dialog.exec():
            self.service.update_task(task["id"], **dialog.values())
            self.refresh_tasks()
            self.changed.emit(self.event_id or 0)

    def refresh_tasks(self):
        self.loading = True
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if not self.event_id:
            self.summary.setText("행사를 선택하세요")
            self.loading = False
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            return
        tasks = self.service.list_tasks(
            self.event_id, self.search.text().strip(), self.status_filter.currentData() or "",
            self.major_filter.currentData() or "", include_removed=self.removed_toggle.isChecked())
        if self.removed_toggle.isChecked():
            tasks = [row for row in tasks if row["is_removed"]]
        self._current_tasks = tasks
        participants = self.service.event_participants(self.event_id)
        vendors = participants["vendors"]
        # 전체 담당자를 한 번만 읽고 업체별로 메모리에서 나눈다. 기존에는
        # 항목마다 같은 DB 조회를 반복해 120개 항목에서 큰 지연이 발생했다.
        all_assignees = self.service.available_assignees(self.event_id)
        freelancers = [row for row in all_assignees if not row["company_id"]]
        assignees_by_vendor = {
            int(vendor["id"]): freelancers + [row for row in all_assignees if row["company_id"] == vendor["id"]]
            for vendor in vendors
        }
        self.table.setRowCount(len(tasks))
        for row_index, task in enumerate(tasks):
            task_id = int(task["id"])
            check = QCheckBox()
            check.setChecked(task["status"] == "완료")
            check.setEnabled(not task["is_removed"])
            check.stateChanged.connect(lambda state, tid=task_id: self._set_completed(tid, state == Qt.CheckState.Checked.value))
            holder = QWidget(); holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0); holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            holder_layout.addWidget(check); self.table.setCellWidget(row_index, 0, holder)
            group = QTableWidgetItem(f"{task['major']} / {task['minor']}")
            group.setData(GROUP_MAJOR_ROLE, task["major"])
            group.setData(GROUP_MINOR_ROLE, task["minor"])
            self.table.setItem(row_index, 1, group)
            name = QTableWidgetItem(task["name"]); name.setData(Qt.ItemDataRole.UserRole, task_id)
            tooltip = task["detail"] or "확인 포인트 없음"
            if task["is_removed"]: tooltip += f"\n제외 사유: {task['removed_reason'] or '미입력'}"
            name.setToolTip(tooltip); self.table.setItem(row_index, 2, name)
            status = QComboBox(); status.addItems(STATUSES); status.setCurrentText(task["status"])
            fg, bg = status_color(task["status"]); status.setStyleSheet(f"QComboBox{{color:{fg};background:{bg};font-weight:700;}}")
            status.setEnabled(not task["is_removed"])
            status.currentTextChanged.connect(lambda value, tid=task_id, widget=status: self._update_status(tid, value, widget))
            self.table.setCellWidget(row_index, 3, status)
            priority = QComboBox(); priority.addItems(PRIORITIES); priority.setCurrentText(task["priority"])
            priority.currentTextChanged.connect(lambda value, tid=task_id: self._update(tid, priority=value))
            self.table.setCellWidget(row_index, 4, priority)
            assignees = (assignees_by_vendor.get(int(task["vendor_id"]), freelancers)
                         if task["vendor_id"] else all_assignees)
            self.table.setCellWidget(row_index, 5, self._contact_combo(assignees, task["assignee_id"], task_id, "assignee_id"))
            self.table.setCellWidget(row_index, 6, self._date_edit(task["planned_start"], task_id, "planned_start"))
            self.table.setCellWidget(row_index, 7, self._date_edit(task["due_date"], task_id, "due_date"))
            days = d_day(date.fromisoformat(task["due_date"]))
            self.table.setItem(row_index, 8, QTableWidgetItem("완료" if task["status"] == "완료" else d_day_label(days)))
            self.table.setItem(row_index, 9, QTableWidgetItem("자동" if task["schedule_mode"] == "auto" else "수동"))
            price = QDoubleSpinBox(); price.setRange(0, 999_999_999_999); configure_money_spin(price)
            price.setValue(task["unit_price"] or 0)
            price.editingFinished.connect(lambda tid=task_id, w=price: self._update(tid, unit_price=int(w.value()) or None))
            self.table.setCellWidget(row_index, 10, price)
            self.table.setCellWidget(row_index, 11, self._vendor_combo(vendors, task))
            self.table.setRowHeight(row_index, 48)
        self.summary.setText(f"{len(tasks)}개 항목" + (" · 제외 기록" if self.removed_toggle.isChecked() else ""))
        self.loading = False
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)
        self.table.viewport().update()

    def _contact_combo(self, rows, current, task_id, field):
        combo = QComboBox(); combo.addItem("미지정", None)
        for row in rows: combo.addItem(row["name"], row["id"])
        combo.setCurrentIndex(max(0, combo.findData(current)))
        combo.currentIndexChanged.connect(lambda _=0, tid=task_id, f=field, w=combo: self._update(tid, **{f: w.currentData()}))
        return combo

    def _vendor_combo(self, rows, task):
        combo = QComboBox(); combo.addItem("미지정", None)
        for row in rows: combo.addItem(row["name"], row["id"])
        combo.setCurrentIndex(max(0, combo.findData(task["vendor_id"])))
        combo.currentIndexChanged.connect(lambda _=0, tid=int(task["id"]), w=combo: self._update_vendor(tid, w.currentData()))
        return combo

    def _update_vendor(self, task_id, vendor_id):
        if self.loading: return
        task = next((row for row in self._current_tasks if int(row["id"]) == task_id), None)
        assignee_id = task["assignee_id"] if task else None
        fields = {"vendor_id": vendor_id}
        if assignee_id:
            allowed = {int(row["id"]) for row in self.service.available_assignees(self.event_id, vendor_id)}
            if int(assignee_id) not in allowed:
                QMessageBox.information(self, "담당자 변경 안내", "새 업체 소속과 맞지 않는 기존 담당자를 미지정으로 전환합니다.")
                fields["assignee_id"] = None
        self.service.update_task(task_id, **fields); self.refresh_tasks(); self.changed.emit(self.event_id or 0)

    def _date_edit(self, value, task_id, field):
        widget = DirectDateEdit()
        widget.setDate(QDate.fromString(value, "yyyy-MM-dd"))
        widget.dateChanged.connect(lambda qdate, tid=task_id, f=field: self._update_date(tid, f, qdate))
        return widget

    def _set_completed(self, task_id, completed):
        if self.loading: return
        self.service.set_completed(task_id, completed); self.refresh_tasks(); self.changed.emit(self.event_id or 0)

    def _update_status(self, task_id, value, widget):
        if self.loading: return
        self.service.update_task(task_id, status=value)
        fg, bg = status_color(value); widget.setStyleSheet(f"QComboBox{{color:{fg};background:{bg};font-weight:700;}}")
        self.refresh_tasks(); self.changed.emit(self.event_id or 0)

    def _update_date(self, task_id, field, qdate):
        if self.loading: return
        try: self.service.update_task(task_id, **{field: qdate.toString("yyyy-MM-dd")})
        except ValueError as exc:
            QMessageBox.warning(self, "날짜 확인", str(exc)); self.refresh_tasks(); return
        self.refresh_tasks(); self.changed.emit(self.event_id or 0)

    def _update(self, task_id, **values):
        if self.loading: return
        self.service.update_task(task_id, **values); self.changed.emit(self.event_id or 0)
