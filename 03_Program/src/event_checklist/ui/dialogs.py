from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .widgets import DirectDateEdit, configure_money_spin


class EventDialog(QDialog):
    def __init__(self, masters, event=None, vendors=(), freelancers=(),
                 selected_vendor_ids=(), selected_freelancer_ids=(), parent=None):
        super().__init__(parent)
        self.masters = list(masters)
        # QObject.event() is a native Qt virtual method. Never shadow it with data.
        self.event_record = event
        self.setWindowTitle("행사 수정" if event else "새 행사")
        self.resize(840, 720 if event else 690)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(4)

        title = QLabel("행사 기본 정보")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        form = QFormLayout()
        form.setSpacing(4)
        self.name_edit = QLineEdit(event["name"] if event else "")
        self.name_edit.setPlaceholderText("예: 제33회 시민의 날")
        self.start_edit = DirectDateEdit()
        self.start_edit.setDate(QDate.fromString(event["start_date"], "yyyy-MM-dd") if event else QDate.currentDate())
        self.end_enabled = QCheckBox("최종 행사일 지정")
        self.end_edit = DirectDateEdit()
        self.end_edit.setDate(QDate.fromString(event["end_date"], "yyyy-MM-dd") if event and event["end_date"] else self.start_edit.date().addDays(60))
        self.end_enabled.setChecked(bool(event and event["end_date"]) or not event)
        self.end_edit.setEnabled(self.end_enabled.isChecked())
        self.end_enabled.toggled.connect(self.end_edit.setEnabled)
        end_row = QWidget()
        end_layout = QHBoxLayout(end_row)
        end_layout.setContentsMargins(0, 0, 0, 0)
        end_layout.addWidget(self.end_enabled)
        end_layout.addWidget(self.end_edit, 1)
        self.location_edit = QLineEdit(event["location"] if event else "")
        self.organizer_edit = QLineEdit(event["organizer"] if event else "")
        self.budget_edit = QDoubleSpinBox()
        self.budget_edit.setRange(0, 999_999_999_999)
        configure_money_spin(self.budget_edit)
        if event and event["budget"] is not None:
            self.budget_edit.setValue(event["budget"])
        self.budget_tax_mode = QComboBox()
        self.budget_tax_mode.addItem("선택하세요", "UNSET")
        self.budget_tax_mode.addItem("부가세 포함", "INCLUDED")
        self.budget_tax_mode.addItem("부가세 별도", "EXCLUDED")
        if event:
            index = self.budget_tax_mode.findData(event["budget_tax_mode"])
            self.budget_tax_mode.setCurrentIndex(max(0, index))
        form.addRow("행사명 *", self.name_edit)
        form.addRow("준비 시작일 *", self.start_edit)
        form.addRow("최종 행사일", end_row)
        form.addRow("장소", self.location_edit)
        form.addRow("주최 / 주관", self.organizer_edit)
        form.addRow("예산", self.budget_edit)
        form.addRow("예산 부가세", self.budget_tax_mode)
        root.addLayout(form)

        participants = QHBoxLayout()
        vendor_box = QVBoxLayout()
        vendor_box.addWidget(QLabel("참여 업체"))
        self.vendor_list = QListWidget()
        self.vendor_list.setMinimumHeight(170 if event else 70)
        self._populate_check_list(self.vendor_list, vendors, set(selected_vendor_ids))
        vendor_box.addWidget(self.vendor_list)
        freelancer_box = QVBoxLayout()
        freelancer_box.addWidget(QLabel("참여 프리랜서"))
        self.freelancer_list = QListWidget()
        self.freelancer_list.setMinimumHeight(170 if event else 70)
        self._populate_check_list(self.freelancer_list, freelancers, set(selected_freelancer_ids))
        freelancer_box.addWidget(self.freelancer_list)
        participants.addLayout(vendor_box, 1)
        participants.addLayout(freelancer_box, 1)
        root.addLayout(participants, 1)

        if not event:
            row = QHBoxLayout()
            guide = QLabel("준비 시작일부터 최종 행사일까지의 기간에 맞춰 선택한 업무가 일정순으로 자동 배치됩니다.")
            guide.setWordWrap(True)
            guide.setObjectName("InfoGuide")
            root.addWidget(guide)
            section = QLabel("필요한 기본 항목")
            section.setObjectName("SectionTitle")
            row.addWidget(section)
            row.addStretch()
            all_button = QPushButton("전체 선택")
            none_button = QPushButton("전체 해제")
            row.addWidget(all_button)
            row.addWidget(none_button)
            root.addLayout(row)
            self.tree = QTreeWidget()
            self.tree.setMinimumHeight(90)
            self.tree.setHeaderLabels(["분류 / 항목", "기본 일정", "우선순위"])
            self.tree.setColumnWidth(0, 440)
            self._populate_tree()
            all_button.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
            none_button.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
            root.addWidget(self.tree, 1)
        else:
            self.tree = None
            note = QLabel("날짜를 바꾸면 자동 일정만 준비 기간에 맞춰 다시 배치하고, 직접 수정한 일정은 유지됩니다.")
            note.setWordWrap(True)
            note.setObjectName("Muted")
            root.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("저장")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _populate_tree(self) -> None:
        parents: dict[tuple[str, str], QTreeWidgetItem] = {}
        major_items: dict[str, QTreeWidgetItem] = {}
        for item in self.masters:
            major = item["major"]
            minor = item["minor"]
            major_item = major_items.get(major)
            if major_item is None:
                major_item = QTreeWidgetItem(self.tree, [major])
                major_item.setFlags(major_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
                major_item.setCheckState(0, Qt.CheckState.Checked)
                major_items[major] = major_item
            parent = parents.get((major, minor))
            if parent is None:
                parent = QTreeWidgetItem(major_item, [minor])
                parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
                parent.setCheckState(0, Qt.CheckState.Checked)
                parents[(major, minor)] = parent
            anchor = "시작" if item["anchor"] == "START" else "종료"
            child = QTreeWidgetItem(parent, [item["name"], f"{anchor} {item['start_offset']:+d}~{item['due_offset']:+d}일", item["priority"]])
            child.setData(0, Qt.ItemDataRole.UserRole, item["id"])
            child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            child.setCheckState(0, Qt.CheckState.Checked)
        self.tree.expandToDepth(1)

    def _set_all(self, state: Qt.CheckState) -> None:
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, state)

    def selected_ids(self) -> list[int]:
        if self.tree is None:
            return []
        result: list[int] = []
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            item_id = item.data(0, Qt.ItemDataRole.UserRole)
            if item_id and item.checkState(0) == Qt.CheckState.Checked:
                result.append(int(item_id))
            iterator += 1
        return result

    def values(self) -> dict:
        start = self.start_edit.date().toPython()
        end = self.end_edit.date().toPython() if self.end_enabled.isChecked() else None
        budget = self.budget_edit.value() or None
        return {
            "name": self.name_edit.text().strip(),
            "start_date": start,
            "end_date": end,
            "location": self.location_edit.text().strip(),
            "organizer": self.organizer_edit.text().strip(),
            "budget": budget,
            "budget_tax_mode": self.budget_tax_mode.currentData(),
        }

    @staticmethod
    def _populate_check_list(widget: QListWidget, rows, selected: set[int]) -> None:
        for row in rows:
            item = QListWidgetItem(row["name"])
            item.setData(Qt.ItemDataRole.UserRole, int(row["id"]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if int(row["id"]) in selected else Qt.CheckState.Unchecked)
            widget.addItem(item)

    @staticmethod
    def _checked_ids(widget: QListWidget) -> list[int]:
        return [int(widget.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(widget.count())
                if widget.item(i).checkState() == Qt.CheckState.Checked]

    def selected_vendor_ids(self) -> list[int]:
        return self._checked_ids(self.vendor_list)

    def selected_freelancer_ids(self) -> list[int]:
        return self._checked_ids(self.freelancer_list)

    def _validate(self) -> None:
        values = self.values()
        if not values["name"]:
            QMessageBox.warning(self, "입력 확인", "행사명을 입력하세요.")
            self.name_edit.setFocus()
            return
        if values["end_date"] and values["end_date"] < values["start_date"]:
            QMessageBox.warning(self, "입력 확인", "최종 행사일은 준비 시작일보다 빠를 수 없습니다.")
            return
        if values["budget"] and values["budget_tax_mode"] == "UNSET":
            QMessageBox.warning(self, "입력 확인", "총예산이 있으면 부가세 포함 또는 별도를 선택하세요.")
            self.budget_tax_mode.setFocus()
            return
        if self.tree is not None and not self.selected_ids():
            QMessageBox.warning(self, "입력 확인", "하나 이상의 기본 항목을 선택하세요.")
            return
        self.accept()


from PySide6.QtWidgets import QTreeWidgetItemIterator  # noqa: E402


class MasterImportDialog(QDialog):
    def __init__(self, masters, parent=None):
        super().__init__(parent)
        self.setWindowTitle("기본항목 가져오기")
        self.resize(720, 620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        title = QLabel("가져올 기본항목을 선택하세요")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["분류 / 항목", "일정", "상태"])
        parents = {}
        for row in masters:
            key = (row["major"], row["minor"])
            parent_item = parents.get(key)
            if parent_item is None:
                parent_item = QTreeWidgetItem(self.tree, [f"{key[0]} / {key[1]}"])
                parent_item.setFlags(parent_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
                parent_item.setCheckState(0, Qt.CheckState.Unchecked)
                parents[key] = parent_item
            state = "제외 기록 복원" if row["is_removed"] else "새로 추가"
            child = QTreeWidgetItem(parent_item, [row["name"], f"{row['start_offset']:+d} ~ {row['due_offset']:+d}일", state])
            child.setData(0, Qt.ItemDataRole.UserRole, int(row["id"]))
            child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            child.setCheckState(0, Qt.CheckState.Unchecked)
        self.tree.expandToDepth(0)
        layout.addWidget(self.tree, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("가져오기")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_ids(self) -> list[int]:
        ids = []
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            value = item.data(0, Qt.ItemDataRole.UserRole)
            if value and item.checkState(0) == Qt.CheckState.Checked:
                ids.append(int(value))
            iterator += 1
        return ids

    def _accept(self):
        if not self.selected_ids():
            QMessageBox.warning(self, "선택 확인", "하나 이상의 항목을 선택하세요.")
            return
        self.accept()


class CustomTaskDialog(QDialog):
    def __init__(self, event, parent=None):
        super().__init__(parent)
        self.setWindowTitle("직접 항목 추가")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        form = QFormLayout()
        self.major = QComboBox()
        self.major.setEditable(True)
        self.major.addItems(["시스템", "시설", "행사", "홍보", "운영"])
        self.minor = QLineEdit()
        self.name = QLineEdit()
        self.detail = QTextEdit()
        self.detail.setMaximumHeight(90)
        self.start = DirectDateEdit()
        self.start.setDate(QDate.fromString(event["start_date"], "yyyy-MM-dd"))
        self.due = DirectDateEdit()
        self.due.setDate(QDate.fromString(event["end_date"] or event["start_date"], "yyyy-MM-dd"))
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0, 999_999_999)
        self.quantity.setDecimals(2)
        self.quantity.setValue(1)
        self.unit = QLineEdit()
        self.price = QDoubleSpinBox()
        self.price.setRange(0, 999_999_999_999)
        configure_money_spin(self.price)
        self.vat = QComboBox()
        self.vat.addItem("VAT 10%", "TAXABLE")
        self.vat.addItem("면세", "EXEMPT")
        for label, widget in [("대분류 *", self.major), ("중분류 *", self.minor), ("항목 *", self.name),
                              ("확인 포인트", self.detail), ("작업 시작일", self.start), ("마감일", self.due),
                              ("수량", self.quantity), ("단위", self.unit), ("행사 단가", self.price), ("VAT", self.vat)]:
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        if not self.major.currentText().strip() or not self.minor.text().strip() or not self.name.text().strip():
            QMessageBox.warning(self, "입력 확인", "대분류, 중분류, 항목을 모두 입력하세요.")
            return
        if self.due.date() < self.start.date():
            QMessageBox.warning(self, "날짜 확인", "마감일은 작업 시작일보다 빠를 수 없습니다.")
            return
        self.accept()

    def values(self) -> dict:
        return {"major": self.major.currentText().strip(), "minor": self.minor.text().strip(),
                "name": self.name.text().strip(), "detail": self.detail.toPlainText().strip(),
                "planned_start": self.start.date().toPython(), "due_date": self.due.date().toPython(),
                "quantity": self.quantity.value(), "unit": self.unit.text().strip(),
                "unit_price": int(self.price.value()) or None, "vat_type": self.vat.currentData()}


class ContactDialog(QDialog):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setWindowTitle("담당자 추가" if kind == "PERSON" else "업체 추가")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.note_edit = QLineEdit()
        form.addRow("이름 *" if kind == "PERSON" else "업체명 *", self.name_edit)
        form.addRow("연락처", self.phone_edit)
        form.addRow("역할 / 분야", self.note_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "입력 확인", "이름을 입력하세요.")
            return
        self.accept()

    def values(self):
        return self.name_edit.text().strip(), self.phone_edit.text().strip(), self.note_edit.text().strip()


class MasterItemDialog(QDialog):
    def __init__(self, item=None, people=(), vendors=(), parent=None):
        super().__init__(parent)
        self.item = item
        self.setWindowTitle("기본 항목 수정" if item else "기본 항목 추가")
        self.resize(620, 660)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        form = QFormLayout()
        self.major = QComboBox()
        self.major.setEditable(True)
        self.major.addItems(["시스템", "시설", "행사", "홍보", "운영"])
        self.minor = QComboBox()
        self.minor.setEditable(True)
        self.minor.addItems([
            "무대", "소스", "기반", "렌탈", "기타", "연출", "개막식", "공연", "경연",
            "참여,체험", "전시", "먹거리", "판매", "부대행사", "공통", "온라인", "인쇄",
            "옥외", "행정", "인력", "비품/물품", "환경정리", "기록",
        ])
        self.name = QLineEdit(item["name"] if item else "")
        self.detail = QTextEdit(item["detail"] if item else "")
        self.detail.setMaximumHeight(100)
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0, 999_999_999)
        self.quantity.setDecimals(2)
        self.quantity.setValue((item["quantity"] or 0) if item else 0)
        self.unit = QLineEdit(item["unit"] if item else "")
        self.base_unit_price = QDoubleSpinBox()
        self.base_unit_price.setRange(0, 999_999_999_999)
        configure_money_spin(self.base_unit_price)
        self.base_unit_price.setValue((item["base_unit_price"] or 0) if item else 0)
        self.vat_type = QComboBox()
        self.vat_type.addItem("VAT 10%", "TAXABLE")
        self.vat_type.addItem("면세", "EXEMPT")
        self.vendor = QComboBox()
        self.vendor.addItem("미지정", None)
        for contact in vendors:
            self.vendor.addItem(contact["name"], contact["id"])
        self.assignee = QComboBox()
        self.assignee.addItem("미지정", None)
        for contact in people:
            self.assignee.addItem(contact["name"], contact["id"])
        self.anchor = QComboBox()
        self.anchor.addItem("행사 시작일", "START")
        self.anchor.addItem("행사 종료일", "END")
        self.priority = QComboBox()
        self.priority.addItems(["상", "중", "하"])
        self.start_offset = QDoubleSpinBox()
        self.start_offset.setRange(-365, 365)
        self.start_offset.setDecimals(0)
        self.start_offset.setValue(item["start_offset"] if item else -30)
        self.due_offset = QDoubleSpinBox()
        self.due_offset.setRange(-365, 365)
        self.due_offset.setDecimals(0)
        self.due_offset.setValue(item["due_offset"] if item else -1)
        if item:
            self.major.setCurrentText(item["major"])
            self.minor.setCurrentText(item["minor"])
            self.anchor.setCurrentIndex(max(0, self.anchor.findData(item["anchor"])))
            self.priority.setCurrentText(item["priority"])
            self.vendor.setCurrentIndex(max(0, self.vendor.findData(item["default_vendor_id"])))
            self.assignee.setCurrentIndex(max(0, self.assignee.findData(item["default_assignee_id"])))
            self.vat_type.setCurrentIndex(max(0, self.vat_type.findData(item["default_vat_type"])))
        form.addRow("대분류 *", self.major)
        form.addRow("중분류 *", self.minor)
        form.addRow("항목 *", self.name)
        form.addRow("확인 포인트", self.detail)
        form.addRow("수량", self.quantity)
        form.addRow("단위", self.unit)
        form.addRow("기준 단가(공급가)", self.base_unit_price)
        form.addRow("VAT", self.vat_type)
        form.addRow("기본 업체", self.vendor)
        form.addRow("기본 담당", self.assignee)
        form.addRow("일정 기준", self.anchor)
        form.addRow("작업 시작 오프셋", self.start_offset)
        form.addRow("마감 오프셋", self.due_offset)
        form.addRow("우선순위", self.priority)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        if not self.major.currentText().strip() or not self.minor.currentText().strip() or not self.name.text().strip():
            QMessageBox.warning(self, "입력 확인", "대분류, 중분류, 항목명을 모두 입력하세요.")
            return
        if self.start_offset.value() > self.due_offset.value():
            QMessageBox.warning(self, "입력 확인", "작업 시작 오프셋은 마감 오프셋보다 클 수 없습니다.")
            return
        self.accept()

    def values(self):
        return {
            "major": self.major.currentText().strip(),
            "minor": self.minor.currentText().strip(),
            "name": self.name.text().strip(),
            "detail": self.detail.toPlainText().strip(),
            "quantity": self.quantity.value() or None,
            "unit": self.unit.text().strip(),
            "base_unit_price": int(self.base_unit_price.value()) or None,
            "default_vat_type": self.vat_type.currentData(),
            "default_vendor_id": self.vendor.currentData(),
            "default_assignee_id": self.assignee.currentData(),
            "anchor": self.anchor.currentData(),
            "start_offset": int(self.start_offset.value()),
            "due_offset": int(self.due_offset.value()),
            "priority": self.priority.currentText(),
        }


class TaskDetailsDialog(QDialog):
    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle("업무 상세 수정")
        self.resize(620, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        title = QLabel(task["name"])
        title.setObjectName("SectionTitle")
        category = QLabel(f"{task['major']} / {task['minor']}")
        category.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(category)
        form = QFormLayout()
        self.detail = QTextEdit(task["detail"])
        self.detail.setPlaceholderText("확인해야 할 세부 내용을 입력하세요.")
        self.detail.setMaximumHeight(120)
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0, 999_999_999)
        self.quantity.setDecimals(2)
        self.quantity.setValue(task["quantity"] or 0)
        self.unit = QLineEdit(task["unit"] or "")
        self.note = QTextEdit(task["note"])
        self.note.setPlaceholderText("이 행사에서만 사용하는 메모를 입력하세요.")
        self.note.setMaximumHeight(140)
        form.addRow("확인 포인트", self.detail)
        form.addRow("수량", self.quantity)
        form.addRow("단위", self.unit)
        form.addRow("메모", self.note)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return {
            "detail": self.detail.toPlainText().strip(),
            "quantity": self.quantity.value() or None,
            "unit": self.unit.text().strip(),
            "note": self.note.toPlainText().strip(),
        }
