from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSplitter, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .dialogs import ContactDialog
from .widgets import FastEditableTable, configure_data_table, fit_table_to_view


class ContactsPage(QWidget):
    changed = Signal()

    def __init__(self, db, parent=None, embedded: bool = False):
        super().__init__(parent)
        self.db = db
        root = QVBoxLayout(self)
        root.setContentsMargins(12 if embedded else 32, 12 if embedded else 28, 12 if embedded else 32, 12 if embedded else 32)
        root.setSpacing(14)
        if not embedded:
            title = QLabel("업체 · 담당자")
            title.setObjectName("PageTitle")
            root.addWidget(title)
        guide = QLabel("업체를 선택하면 해당 업체 소속 담당자를 관리할 수 있습니다. 소속이 없는 사람은 프리랜서에 등록하세요.")
        guide.setObjectName("InfoGuide")
        guide.setWordWrap(True)
        root.addWidget(guide)
        tabs = QTabWidget()
        tabs.addTab(self._companies_tab(), "업체별 담당자")
        tabs.addTab(self._freelancers_tab(), "프리랜서")
        root.addWidget(tabs, 1)
        self.refresh()

    def _table(self, headers, widths):
        table = FastEditableTable(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        configure_data_table(table, widths)
        return table

    def _companies_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        actions = QHBoxLayout()
        add_vendor = QPushButton("+ 업체 추가")
        add_vendor.setProperty("primary", True)
        delete_vendor = QPushButton("업체 삭제")
        delete_vendor.setProperty("danger", True)
        add_person = QPushButton("+ 소속 담당자 추가")
        actions.addWidget(add_vendor)
        actions.addWidget(delete_vendor)
        actions.addStretch()
        actions.addWidget(add_person)
        layout.addLayout(actions)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.vendor_table = self._table(["업체", "연락처", "분야"], [190, 150, 210])
        self.company_people = self._table(["담당자", "연락처", "역할"], [180, 150, 220])
        splitter.addWidget(self.vendor_table)
        splitter.addWidget(self.company_people)
        splitter.setSizes([520, 620])
        layout.addWidget(splitter, 1)
        self.vendor_table.itemSelectionChanged.connect(self._refresh_company_people)
        add_vendor.clicked.connect(lambda: self.add_contact("VENDOR"))
        delete_vendor.clicked.connect(lambda: self.delete_selected(self.vendor_table, "VENDOR"))
        add_person.clicked.connect(self.add_company_person)
        return page

    def _freelancers_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        actions = QHBoxLayout()
        actions.addStretch()
        fit = QPushButton("열 너비 맞춤")
        add = QPushButton("+ 프리랜서 추가")
        add.setProperty("primary", True)
        delete = QPushButton("선택 삭제")
        delete.setProperty("danger", True)
        actions.addWidget(delete)
        actions.addWidget(fit)
        actions.addWidget(add)
        layout.addLayout(actions)
        self.freelancer_table = self._table(["이름", "연락처", "역할 / 분야"], [220, 200, 420])
        layout.addWidget(self.freelancer_table, 1)
        add.clicked.connect(lambda: self.add_contact("PERSON", None))
        delete.clicked.connect(lambda: self.delete_selected(self.freelancer_table, "PERSON"))
        fit.clicked.connect(lambda: fit_table_to_view(self.freelancer_table))
        return page

    def refresh(self):
        vendors = self.db.query("SELECT * FROM contacts WHERE kind='VENDOR' ORDER BY name")
        self._fill(self.vendor_table, vendors)
        freelancers = self.db.query("SELECT * FROM contacts WHERE kind='PERSON' AND company_id IS NULL ORDER BY name")
        self._fill(self.freelancer_table, freelancers)
        if vendors and self.vendor_table.currentRow() < 0:
            self.vendor_table.selectRow(0)
        self._refresh_company_people()

    def _fill(self, table, rows):
        table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            for c, value in enumerate([item["name"], item["phone"], item["role_note"]]):
                cell = QTableWidgetItem(value or "")
                cell.setData(Qt.ItemDataRole.UserRole, item["id"])
                table.setItem(r, c, cell)
            table.setRowHeight(r, 42)

    def _selected_vendor_id(self):
        row = self.vendor_table.currentRow()
        return self.vendor_table.item(row, 0).data(Qt.ItemDataRole.UserRole) if row >= 0 else None

    def _refresh_company_people(self):
        vendor_id = self._selected_vendor_id()
        rows = self.db.query("SELECT * FROM contacts WHERE kind='PERSON' AND company_id=? ORDER BY name", (vendor_id,)) if vendor_id else []
        self._fill(self.company_people, rows)

    def add_contact(self, kind: str, company_id=None):
        dialog = ContactDialog(kind, self)
        if not dialog.exec():
            return
        name, phone, note = dialog.values()
        try:
            self.db.execute(
                "INSERT INTO contacts(kind,name,phone,role_note,company_id) VALUES (?,?,?,?,?)",
                (kind, name, phone, note, company_id),
            )
        except Exception as exc:
            QMessageBox.warning(self, "추가 실패", f"연락처를 추가하지 못했습니다.\n\n{exc}")
            return
        self.refresh()
        self.changed.emit()

    def add_company_person(self):
        vendor_id = self._selected_vendor_id()
        if not vendor_id:
            QMessageBox.information(self, "업체 선택", "담당자를 추가할 업체를 먼저 선택하세요.")
            return
        self.add_contact("PERSON", vendor_id)

    def delete_selected(self, table, kind):
        row = table.currentRow()
        if row < 0:
            return
        item_id = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        name = table.item(row, 0).text()
        if QMessageBox.question(self, "삭제 확인", f"'{name}'을(를) 삭제할까요?") == QMessageBox.StandardButton.Yes:
            self.db.execute("DELETE FROM contacts WHERE id=? AND kind=?", (item_id, kind))
            self.refresh()
            self.changed.emit()
