from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..theme import TOKENS
from .widgets import KpiCard, UnitComboBox, configure_money_spin, configure_quantity_spin, configure_resizable_table, fit_table_to_view


def money(value) -> str:
    return f"{int(value or 0):,}원"


class SettlementPage(QWidget):
    def __init__(self, service, db, parent=None):
        super().__init__(parent)
        self.service = service
        self.db = db
        self.event_id: int | None = None
        self.loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 32)
        root.setSpacing(14)
        top = QHBoxLayout()
        box = QVBoxLayout()
        title = QLabel("정산내역")
        title.setObjectName("PageTitle")
        self.description = QLabel("행사를 선택하면 예산과 항목 합계를 비교할 수 있습니다.")
        self.description.setObjectName("PageDescription")
        box.addWidget(title)
        box.addWidget(self.description)
        top.addLayout(box)
        top.addStretch()
        top.addWidget(QLabel("입력 예산"))
        self.budget = QDoubleSpinBox()
        self.budget.setRange(0, 999_999_999_999)
        configure_money_spin(self.budget)
        self.budget.setMinimumWidth(180)
        self.budget.editingFinished.connect(self._save_budget)
        self.tax_mode = QComboBox()
        self.tax_mode.addItem("VAT 포함/별도 선택", "UNSET")
        self.tax_mode.addItem("VAT 포함 예산", "INCLUDED")
        self.tax_mode.addItem("VAT 별도 예산", "EXCLUDED")
        self.tax_mode.currentIndexChanged.connect(self._save_budget)
        fit = QPushButton("열 너비 맞춤")
        fit.clicked.connect(lambda: fit_table_to_view(self.table))
        top.addWidget(self.budget)
        top.addWidget(self.tax_mode)
        top.addWidget(fit)
        root.addLayout(top)

        cards = QGridLayout()
        self.cards = {}
        for column, (key, label) in enumerate([
            ("budget", "입력 예산"), ("supply", "공급가 합계"), ("vat", "VAT"),
            ("total", "VAT 포함 합계"), ("difference", "예산 차이"),
        ]):
            card = KpiCard(label)
            self.cards[key] = card
            cards.addWidget(card, 0, column)
        root.addLayout(cards)
        self.warning = QLabel("")
        self.warning.setObjectName("InfoGuide")
        self.warning.setWordWrap(True)
        root.addWidget(self.warning)
        self.table = QTableWidget(0, 12)
        self.table.setHorizontalHeaderLabels([
            "대분류", "중분류", "항목", "수량", "단위", "행사 단가", "공급가",
            "VAT 구분", "VAT", "합계", "업체", "메모",
        ])
        self.table.verticalHeader().setVisible(False)
        configure_resizable_table(self.table, [90, 110, 180, 90, 80, 130, 130, 105, 110, 130, 150, 220])
        root.addWidget(self.table, 1)

    def set_event(self, event_id: int | None):
        self.event_id = event_id
        self.refresh()

    def refresh(self):
        self.loading = True
        self.table.setRowCount(0)
        if not self.event_id:
            self.loading = False
            return
        summary = self.service.settlement_summary(self.event_id)
        event = summary["event"]
        self.description.setText(f"{event['name']} · 공급가 기준 단가와 VAT를 합산합니다.")
        self.budget.setValue(event["budget"] or 0)
        self.tax_mode.setCurrentIndex(max(0, self.tax_mode.findData(event["budget_tax_mode"])))
        for key in ("budget", "supply", "vat", "total"):
            self.cards[key].set_value(money(summary[key]))
        difference = summary["difference"]
        if difference is None:
            difference_text = "예산 미입력"
        elif difference == 0:
            difference_text = "일치"
        elif difference > 0:
            difference_text = f"{money(difference)} 남음"
        else:
            difference_text = f"{money(abs(difference))} 초과"
        self.cards["difference"].set_value(difference_text)
        messages = []
        if event["budget"] and event["budget_tax_mode"] == "UNSET":
            messages.append("입력 예산이 VAT 포함인지 별도인지 선택하세요.")
        if summary["warnings"]:
            messages.append(f"수량 또는 단가가 비어 있는 항목이 {summary['warnings']}개 있습니다.")
        self.warning.setText("  ".join(messages) if messages else "모든 금액 입력이 정상입니다.")
        participants = self.service.event_participants(self.event_id)
        vendors = participants["vendors"]
        current_major = None
        for item in summary["items"]:
            if current_major is not None and item["major"] != current_major:
                self._add_subtotal_row(current_major, summary["categories"][current_major])
            current_major = item["major"]
            self._add_item_row(item, vendors)
        if current_major is not None:
            self._add_subtotal_row(current_major, summary["categories"][current_major])
        self._add_total_row(summary)
        self.loading = False

    def _add_item_row(self, item, vendors):
        row = self.table.rowCount()
        self.table.insertRow(row)
        task_id = int(item["id"])
        for column, value in [(0,item["major"]),(1,item["minor"]),(2,item["name"]),(6,money(item["supply"])),(8,money(item["vat"])),(9,money(item["total"]))]:
            cell = QTableWidgetItem(str(value))
            cell.setData(Qt.ItemDataRole.UserRole, task_id)
            self.table.setItem(row, column, cell)
        quantity = QDoubleSpinBox()
        quantity.setRange(0, 999_999_999)
        configure_quantity_spin(quantity)
        quantity.setValue(item["quantity"] or 0)
        quantity.editingFinished.connect(lambda tid=task_id,w=quantity:self._update(tid,quantity=int(w.value()) or None))
        self.table.setCellWidget(row, 3, quantity)
        unit = UnitComboBox(item["unit"] or "식")
        unit.value_committed.connect(lambda value, tid=task_id:self._update(tid,unit=value))
        self.table.setCellWidget(row, 4, unit)
        price = QDoubleSpinBox()
        price.setRange(0, 999_999_999_999)
        configure_money_spin(price)
        price.setValue(item["unit_price"] or 0)
        price.editingFinished.connect(lambda tid=task_id,w=price:self._update(tid,unit_price=int(w.value()) or None))
        self.table.setCellWidget(row, 5, price)
        vat = QComboBox()
        vat.addItem("10%", "TAXABLE")
        vat.addItem("면세", "EXEMPT")
        vat.setCurrentIndex(max(0, vat.findData(item["vat_type"])))
        vat.currentIndexChanged.connect(lambda _=0,tid=task_id,w=vat:self._update(tid,vat_type=w.currentData()))
        self.table.setCellWidget(row, 7, vat)
        vendor = QComboBox()
        vendor.addItem("미지정", None)
        for entry in vendors:
            vendor.addItem(entry["name"], entry["id"])
        vendor.setCurrentIndex(max(0, vendor.findData(item["vendor_id"])))
        vendor.currentIndexChanged.connect(lambda _=0,tid=task_id,w=vendor:self._update(tid,vendor_id=w.currentData()))
        self.table.setCellWidget(row, 10, vendor)
        note = QLineEdit(item["note"] or "")
        note.editingFinished.connect(lambda tid=task_id,w=note:self._update(tid,note=w.text().strip()))
        self.table.setCellWidget(row, 11, note)
        self.table.setRowHeight(row, 44)

    def _add_subtotal_row(self, major, subtotal):
        row = self.table.rowCount()
        self.table.insertRow(row)
        label = QTableWidgetItem(f"{major} 소계")
        self.table.setItem(row, 0, label)
        self.table.setSpan(row, 0, 1, 6)
        for column, value in [(6,subtotal["supply"]),(8,subtotal["vat"]),(9,subtotal["total"])]:
            cell = QTableWidgetItem(money(value))
            self.table.setItem(row, column, cell)
        for column in range(self.table.columnCount()):
            cell = self.table.item(row, column)
            if cell is None:
                cell = QTableWidgetItem(""); self.table.setItem(row, column, cell)
            cell.setBackground(QColor(TOKENS["brand_weak"]))
            cell.setForeground(QColor(TOKENS["brand_pressed"]))
            cell.setFont(QFont(cell.font().family(), cell.font().pointSize(), QFont.Weight.DemiBold))
        self.table.setRowHeight(row, 38)

    def _add_total_row(self, summary):
        row = self.table.rowCount(); self.table.insertRow(row)
        label = QTableWidgetItem("전체 합계"); self.table.setItem(row, 0, label); self.table.setSpan(row, 0, 1, 6)
        for column, value in [(6, summary["supply"]), (8, summary["vat"]), (9, summary["total"])]:
            cell = QTableWidgetItem(money(value)); self.table.setItem(row, column, cell)
        for column in range(self.table.columnCount()):
            cell = self.table.item(row, column)
            if cell is None:
                cell = QTableWidgetItem(""); self.table.setItem(row, column, cell)
            cell.setBackground(QColor(TOKENS["brand"]))
            cell.setForeground(QColor("#FFFFFF"))
            font = cell.font(); font.setBold(True); font.setPointSize(max(11, font.pointSize() + 1)); cell.setFont(font)
        self.table.setRowHeight(row, 46)

    def _update(self, task_id, **values):
        if self.loading:
            return
        self.service.update_task(task_id, **values)
        self.refresh()

    def _save_budget(self):
        if self.loading or not self.event_id:
            return
        self.db.execute(
            "UPDATE events SET budget=?,budget_tax_mode=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (self.budget.value() or None, self.tax_mode.currentData(), self.event_id),
        )
        self.refresh()
