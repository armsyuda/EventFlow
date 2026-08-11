from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from ..backup import create_backup, restore_backup
from .. import __version__
from ..export import export_csv, export_excel
from .contacts_page import ContactsPage
from .master_page import MasterPage


class SettingsPage(QWidget):
    restored = Signal()
    contacts_changed = Signal()

    def __init__(self, db, backup_directory: Path, parent=None):
        super().__init__(parent)
        self.db = db
        self.backup_directory = backup_directory
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 32)
        root.setSpacing(14)
        title = QLabel("설정")
        title.setObjectName("PageTitle")
        description = QLabel("행사마다 공통으로 사용하는 기본 항목, 업체·담당자와 데이터를 관리합니다.")
        description.setObjectName("PageDescription")
        root.addWidget(title)
        root.addWidget(description)
        self.tabs = QTabWidget()
        self.master_page = MasterPage(db, embedded=True)
        self.contacts_page = ContactsPage(db, embedded=True)
        self.contacts_page.changed.connect(self.contacts_changed)
        self.tabs.addTab(self.master_page, "기본 항목")
        self.tabs.addTab(self.contacts_page, "업체 · 담당자")
        self.tabs.addTab(self._data_page(), "데이터 관리")
        self.tabs.addTab(self._about_page(), "앱 정보")
        root.addWidget(self.tabs, 1)

    def _data_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.addWidget(self._section("데이터 저장 위치", str(self.db.path), []))
        layout.addWidget(self._section("백업", "앱 시작 시 하루 한 번 자동 백업합니다.", [
            ("지금 백업", self.backup_now, True), ("백업에서 복원", self.restore_now, False),
        ]))
        layout.addWidget(self._section("내보내기", "체크리스트와 행사별 정산 요약을 파일로 저장합니다.", [
            ("Excel 내보내기", self.export_xlsx, True), ("CSV 내보내기", self.export_csv_file, False),
        ]))
        layout.addStretch()
        return page

    def _about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.addWidget(self._section(
            "이벤트 플로우 · 이플",
            f"행사 준비 체크리스트, 일정과 예산 배분을 한곳에서 관리하는 Windows 로컬 프로그램입니다.\n버전 {__version__}",
            [],
        ))
        layout.addStretch()
        return page

    def _section(self, title_text, description_text, actions):
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        title = QLabel(title_text)
        title.setObjectName("SectionTitle")
        description = QLabel(description_text)
        description.setObjectName("Muted")
        description.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(description)
        if actions:
            row = QHBoxLayout()
            row.addStretch()
            for text, callback, primary in actions:
                button = QPushButton(text)
                if primary:
                    button.setProperty("primary", True)
                button.clicked.connect(callback)
                row.addWidget(button)
            layout.addLayout(row)
        return card

    def refresh(self):
        self.master_page.refresh()
        self.contacts_page.refresh()

    def backup_now(self):
        path, _ = QFileDialog.getSaveFileName(self, "백업 저장", str(self.backup_directory / "event_flow_backup.db"), "Database (*.db)")
        if path:
            result = create_backup(self.db, Path(path))
            QMessageBox.information(self, "백업 완료", f"백업을 저장했습니다.\n{result}")

    def restore_now(self):
        path, _ = QFileDialog.getOpenFileName(self, "백업 선택", str(self.backup_directory), "Database (*.db)")
        if not path:
            return
        answer = QMessageBox.warning(
            self, "복원 확인", "현재 데이터가 선택한 백업으로 교체됩니다. 계속할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            safety = create_backup(self.db, self.backup_directory)
            restore_backup(self.db, Path(path))
            QMessageBox.information(self, "복원 완료", f"복원 전 데이터는 다음 위치에 백업했습니다.\n{safety}")
            self.restored.emit()

    def export_xlsx(self):
        path, _ = QFileDialog.getSaveFileName(self, "Excel 내보내기", "event_flow.xlsx", "Excel (*.xlsx)")
        if path:
            result = export_excel(self.db, Path(path))
            QMessageBox.information(self, "내보내기 완료", f"Excel 파일을 저장했습니다.\n{result}")

    def export_csv_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV 내보내기", "event_flow.csv", "CSV (*.csv)")
        if path:
            result = export_csv(self.db, Path(path))
            QMessageBox.information(self, "내보내기 완료", f"CSV 파일을 저장했습니다.\n{result}")
