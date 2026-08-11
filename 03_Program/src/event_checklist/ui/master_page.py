from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .dialogs import MasterItemDialog
from .widgets import (
    GROUP_MAJOR_ROLE, GROUP_MINOR_ROLE, UnitComboBox, configure_editable_table,
    fit_table_to_view,
)


class MasterPage(QWidget):
    def __init__(self, db, parent=None, embedded: bool = False):
        super().__init__(parent)
        self.db = db
        self.loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(12 if embedded else 32, 12 if embedded else 28, 12 if embedded else 32, 12 if embedded else 32)
        root.setSpacing(16)
        title = QLabel("기본 항목")
        title.setObjectName("PageTitle")
        description = QLabel("새 행사에 복사될 기본 업무와 권장 일정을 관리합니다. 기존 행사는 바뀌지 않습니다.")
        description.setObjectName("PageDescription")
        if not embedded:
            root.addWidget(title)
            root.addWidget(description)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("분류·항목 검색")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.count = QLabel()
        self.count.setObjectName("Muted")
        add_button = QPushButton("+ 항목 추가")
        add_button.setProperty("primary", True)
        add_button.clicked.connect(self.add_item)
        delete_button = QPushButton("선택 삭제")
        delete_button.setProperty("danger", True)
        delete_button.clicked.connect(self.delete_selected)
        fit_columns = QPushButton("열 너비 맞춤")
        fit_columns.setToolTip("현재 창 크기에 맞춰 열 너비를 자동으로 정리합니다.")
        fit_columns.clicked.connect(lambda: fit_table_to_view(self.table))
        top.addWidget(self.search, 1)
        top.addWidget(self.count)
        top.addWidget(fit_columns)
        top.addWidget(delete_button)
        top.addWidget(add_button)
        root.addLayout(top)
        self.table = QTableWidget(0, 15)
        self.table.setHorizontalHeaderLabels([
            "사용", "대분류", "중분류", "항목", "확인 포인트", "수량", "단위", "기준 단가", "VAT",
            "업체", "담당", "일정 기준", "시작 D±", "마감 D±", "우선순위",
        ])
        self.table.horizontalHeaderItem(11).setToolTip("행사 시작일 또는 행사 종료일 중 자동 일정의 기준일입니다.")
        self.table.horizontalHeaderItem(12).setToolTip("D-30은 기준일 30일 전, D+1은 기준일 1일 후에 작업을 시작한다는 뜻입니다.")
        self.table.horizontalHeaderItem(13).setToolTip("D-7은 기준일 7일 전, D+1은 기준일 1일 후가 마감이라는 뜻입니다.")
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        configure_editable_table(
            self.table, [60, 92, 116, 160, 240, 76, 88, 120, 90, 136, 126, 116, 88, 88, 90], grouped=True
        )
        self.table.cellChanged.connect(self._cell_changed)
        root.addWidget(self.table, 1)
        note = QLabel(
            "일정 기준이 ‘행사 시작일’이고 시작 D-30·마감 D-7이면 행사 30일 전부터 7일 전까지의 업무입니다. "
            "D+1은 기준일 다음 날을 뜻합니다. 셀을 한 번 누르면 바로 수정할 수 있습니다."
        )
        note.setObjectName("InfoGuide"); note.setWordWrap(True)
        root.addWidget(note)
        self.refresh()

    def rows(self):
        text = self.search.text().strip()
        if text:
            value = f"%{text}%"
            return self.db.query(
                """SELECT m.*,v.name default_vendor_name,p.name default_assignee_name
                   FROM master_items m
                   LEFT JOIN contacts v ON v.id=m.default_vendor_id
                   LEFT JOIN contacts p ON p.id=m.default_assignee_id
                   WHERE m.major LIKE ? OR m.minor LIKE ? OR m.name LIKE ? ORDER BY m.sort_order""",
                (value, value, value),
            )
        return self.db.query(
            """SELECT m.*,v.name default_vendor_name,p.name default_assignee_name
               FROM master_items m
               LEFT JOIN contacts v ON v.id=m.default_vendor_id
               LEFT JOIN contacts p ON p.id=m.default_assignee_id
               ORDER BY m.sort_order"""
        )

    def refresh(self):
        self.loading = True
        self.table.blockSignals(True)
        rows = self.rows()
        self.table.setRowCount(len(rows))
        people, vendors = self._contacts()
        for r, item in enumerate(rows):
            check = QCheckBox()
            check.setChecked(bool(item["active"]))
            check.toggled.connect(lambda value, item_id=item["id"]: self.db.execute("UPDATE master_items SET active=? WHERE id=?", (1 if value else 0, item_id)))
            holder = QWidget()
            h = QHBoxLayout(holder)
            h.setContentsMargins(0, 0, 0, 0)
            h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            h.addWidget(check)
            self.table.setCellWidget(r, 0, holder)
            quantity = "" if item["quantity"] is None else f"{item['quantity']:g}"
            values = [item["major"], item["minor"], item["name"], item["detail"], quantity]
            for c, value in enumerate(values, 1):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, item["id"])
                self.table.setItem(r, c, cell)
            group = self.table.item(r, 1)
            group.setData(GROUP_MAJOR_ROLE, item["major"])
            group.setData(GROUP_MINOR_ROLE, item["minor"])
            unit = UnitComboBox(item["unit"] or "식")
            unit.value_committed.connect(lambda value, item_id=item["id"]: self._update_field(item_id, "unit", value))
            self.table.setCellWidget(r, 6, unit)
            price = QTableWidgetItem("" if item["base_unit_price"] is None else f"{item['base_unit_price']:,}")
            price.setData(Qt.ItemDataRole.UserRole, item["id"])
            self.table.setItem(r, 7, price)
            vat = QComboBox()
            vat.addItem("10%", "TAXABLE")
            vat.addItem("면세", "EXEMPT")
            vat.setCurrentIndex(max(0, vat.findData(item["default_vat_type"])))
            vat.currentIndexChanged.connect(lambda _=0, item_id=item["id"], widget=vat: self._update_field(item_id, "default_vat_type", widget.currentData()))
            self.table.setCellWidget(r, 8, vat)
            self.table.setCellWidget(r, 9, self._choice_combo(vendors, item["default_vendor_id"], item["id"], "default_vendor_id"))
            self.table.setCellWidget(r, 10, self._choice_combo(people, item["default_assignee_id"], item["id"], "default_assignee_id"))
            anchor = QComboBox()
            anchor.addItem("행사일 기준", "START")
            anchor.addItem("행사 종료 기준", "END")
            anchor.setCurrentIndex(max(0, anchor.findData(item["anchor"])))
            anchor.currentIndexChanged.connect(
                lambda _=0, item_id=item["id"], widget=anchor: self._update_field(item_id, "anchor", widget.currentData())
            )
            self.table.setCellWidget(r, 11, anchor)
            for c, value in [(12, f"D{item['start_offset']:+d}"), (13, f"D{item['due_offset']:+d}")]:
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, item["id"])
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, c, cell)
            priority = QComboBox()
            priority.addItems(["상", "중", "하"])
            priority.setCurrentText(item["priority"])
            priority.currentTextChanged.connect(
                lambda value, item_id=item["id"]: self._update_field(item_id, "priority", value)
            )
            self.table.setCellWidget(r, 14, priority)
            self.table.setRowHeight(r, 48)
        self.count.setText(f"{len(rows)}개 항목")
        self.table.blockSignals(False)
        self.loading = False

    def _choice_combo(self, rows, current, item_id: int, field: str):
        combo = QComboBox()
        combo.addItem("미지정", None)
        for row in rows:
            combo.addItem(row["name"], row["id"])
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.currentIndexChanged.connect(
            lambda _=0, iid=item_id, f=field, widget=combo: self._update_field(iid, f, widget.currentData())
        )
        return combo

    def _update_field(self, item_id: int, field: str, value) -> None:
        if self.loading:
            return
        allowed = {"default_vendor_id", "default_assignee_id", "default_vat_type", "anchor", "priority", "unit"}
        if field not in allowed:
            return
        self.db.execute(f"UPDATE master_items SET {field}=? WHERE id=?", (value, item_id))

    def _cell_changed(self, row: int, column: int) -> None:
        if self.loading or column not in {1, 2, 3, 4, 5, 7, 12, 13}:
            return
        cell = self.table.item(row, column)
        if cell is None:
            return
        item_id = cell.data(Qt.ItemDataRole.UserRole)
        fields = {1: "major", 2: "minor", 3: "name", 4: "detail", 5: "quantity", 7: "base_unit_price", 12: "start_offset", 13: "due_offset"}
        field = fields[column]
        raw = cell.text().strip()
        try:
            if field in {"major", "minor", "name"} and not raw:
                raise ValueError("대분류, 중분류와 항목명은 비워둘 수 없습니다.")
            value = raw
            if field == "quantity":
                value = None if not raw else float(raw.replace(",", ""))
                if value is not None and value < 0:
                    raise ValueError("수량은 0 이상으로 입력하세요.")
            elif field == "base_unit_price":
                value = None if not raw else int(raw.replace(",", ""))
                if value is not None and value < 0:
                    raise ValueError("기준 단가는 0 이상으로 입력하세요.")
            elif field in {"start_offset", "due_offset"}:
                value = int(raw.upper().replace("D", ""))
                current = self.db.one("SELECT start_offset,due_offset FROM master_items WHERE id=?", (item_id,))
                start = value if field == "start_offset" else current["start_offset"]
                due = value if field == "due_offset" else current["due_offset"]
                if start > due:
                    raise ValueError("작업 시작일은 마감일보다 늦을 수 없습니다.")
            self.db.execute(f"UPDATE master_items SET {field}=? WHERE id=?", (value, item_id))
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "입력 확인", str(exc) if str(exc) else "올바른 값을 입력하세요.")
            self.refresh()

    def edit_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item_id = self.table.item(row, 3).data(Qt.ItemDataRole.UserRole)
        item = self.db.one("SELECT * FROM master_items WHERE id=?", (item_id,))
        people, vendors = self._contacts()
        dialog = MasterItemDialog(item, people=people, vendors=vendors, parent=self)
        if dialog.exec():
            values = dialog.values()
            self.db.execute(
                """UPDATE master_items SET major=?,minor=?,name=?,detail=?,quantity=?,unit=?,
                   base_unit_price=?,default_vat_type=?,default_vendor_id=?,default_assignee_id=?,anchor=?,start_offset=?,due_offset=?,priority=?
                   WHERE id=?""",
                (*values.values(), item_id),
            )
            self.refresh()

    def _contacts(self):
        people = self.db.query("SELECT id,name FROM contacts WHERE kind='PERSON' ORDER BY name")
        vendors = self.db.query("SELECT id,name FROM contacts WHERE kind='VENDOR' ORDER BY name")
        return people, vendors

    def add_item(self):
        people, vendors = self._contacts()
        dialog = MasterItemDialog(people=people, vendors=vendors, parent=self)
        if not dialog.exec():
            return
        values = dialog.values()
        next_values = self.db.one("SELECT COALESCE(MAX(id),0)+1 next_id,COALESCE(MAX(sort_order),0)+1 next_order FROM master_items")
        self.db.execute(
            """INSERT INTO master_items(
               id,major,minor,name,detail,quantity,unit,base_unit_price,default_vat_type,
               default_vendor_id,default_assignee_id,anchor,start_offset,due_offset,priority,sort_order,active
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (next_values["next_id"], *values.values(), next_values["next_order"]),
        )
        self.refresh()

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "항목 선택", "삭제할 기본 항목을 선택하세요.")
            return
        item_id = self.table.item(row, 3).data(Qt.ItemDataRole.UserRole)
        name = self.table.item(row, 3).text()
        answer = QMessageBox.warning(
            self, "기본 항목 삭제 확인",
            f"'{name}'을(를) 기본 항목에서 삭제할까요?\n이미 생성된 행사의 업무는 그대로 유지됩니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.db.execute("DELETE FROM master_items WHERE id=?", (item_id,))
            self.refresh()
