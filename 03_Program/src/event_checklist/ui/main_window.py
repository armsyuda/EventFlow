from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import webbrowser

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressDialog, QPushButton, QStackedWidget, QVBoxLayout, QWidget, QMainWindow

from ..config import backup_dir
from .. import __version__
from ..services import EventService
from ..update_service import UpdateInfo, download_update, fetch_latest_release, is_packaged_app, launch_installer, version_tuple
from .calendar_page import CalendarPage
from .dashboard_page import DashboardPage
from .dialogs import EventDialog
from .events_page import EventsPage
from .settings_page import SettingsPage
from .settlement_page import SettlementPage
from .title_bar import TitleBar, app_icon


class UpdateCheckThread(QThread):
    finished_with_result = Signal(object)
    failed = Signal()
    def run(self):
        try: self.finished_with_result.emit(fetch_latest_release())
        except Exception: self.failed.emit()


class UpdateDownloadThread(QThread):
    downloaded = Signal(object)
    failed = Signal(str)
    def __init__(self, info, parent=None): super().__init__(parent); self.info = info
    def run(self):
        try: self.downloaded.emit(download_update(self.info))
        except Exception as exc: self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, db, parent=None, enable_update_check: bool = True):
        super().__init__(parent)
        self.db = db
        self.service = EventService(db)
        self.selected_event_id: int | None = None
        self.setWindowTitle("이벤트 플로우")
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.resize(1440, 900)
        self.setMinimumSize(1120, 700)

        outer = QWidget(); outer.setObjectName("AppRoot")
        outer_layout = QVBoxLayout(outer); outer_layout.setContentsMargins(1, 1, 1, 1); outer_layout.setSpacing(0)
        self.title_bar = TitleBar(self); outer_layout.addWidget(self.title_bar)
        content = QWidget(); content_layout = QHBoxLayout(content); content_layout.setContentsMargins(0, 0, 0, 0); content_layout.setSpacing(0)
        content_layout.addWidget(self._build_sidebar())
        self.stack = QStackedWidget(); content_layout.addWidget(self.stack, 1)
        outer_layout.addWidget(content, 1); self.setCentralWidget(outer)

        self.dashboard = DashboardPage(self.service)
        self.events = EventsPage(self.service, db)
        self.calendar = CalendarPage(self.service, db)
        self.settlement = SettlementPage(self.service, db)
        self.settings = SettingsPage(db, backup_dir())
        for page in [self.dashboard, self.events, self.calendar, self.settlement, self.settings]:
            self.stack.addWidget(page)

        self.dashboard.create_requested.connect(self.create_event)
        self.dashboard.event_selected.connect(self.select_event)
        self.dashboard.edit_requested.connect(self.edit_event)
        self.dashboard.delete_requested.connect(self.delete_event)
        self.dashboard.clear_requested.connect(lambda: self.select_event(None))
        self.events.edit_requested.connect(self.edit_event)
        self.events.changed.connect(self.refresh_dynamic)
        self.calendar.changed.connect(self.refresh_dynamic)
        self.settings.contacts_changed.connect(self.refresh_dynamic)
        self.settings.restored.connect(lambda: self.select_event(None))
        self.title_bar.update_button.clicked.connect(self.install_available_update)
        self.available_update: UpdateInfo | None = None
        self.update_check_thread = None
        self.update_download_thread = None
        self.select_event(None)
        if is_packaged_app() and enable_update_check: QTimer.singleShot(700, self.check_updates)
        else: self.title_bar.set_update_status()

    def _build_sidebar(self):
        sidebar = QFrame(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(212)
        layout = QVBoxLayout(sidebar); layout.setContentsMargins(16, 20, 16, 20); layout.setSpacing(8)
        title = QLabel("이플"); title.setObjectName("AppTitle")
        subtitle = QLabel("이벤트 플로우"); subtitle.setObjectName("Muted"); subtitle.setContentsMargins(8, 0, 0, 18)
        layout.addWidget(title); layout.addWidget(subtitle)
        names = ["대시보드", "체크리스트", "달력", "정산내역", "설정"]
        self.nav_group = QButtonGroup(sidebar); self.nav_group.setExclusive(True); self.nav_buttons = []
        for index, name in enumerate(names):
            button = QPushButton(name); button.setCheckable(True); button.setProperty("nav", True)
            button.clicked.connect(lambda _checked=False, value=index: self._navigate(value))
            self.nav_group.addButton(button, index); self.nav_buttons.append(button); layout.addWidget(button)
        layout.addStretch(); version = QLabel(f"이벤트 플로우 {__version__}"); version.setObjectName("Muted")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(version)
        return sidebar

    def _navigate(self, index):
        if index in (1, 2, 3) and not self.selected_event_id:
            return
        if self.stack.currentIndex() == index:
            return
        self.stack.setCurrentIndex(index)
        if index == 0: self.dashboard.set_event(self.selected_event_id)
        elif index == 1: self.events.set_event(self.selected_event_id)
        elif index == 2: self.calendar.set_event(self.selected_event_id)
        elif index == 3: self.settlement.set_event(self.selected_event_id)
        elif index == 4: self.settings.refresh()

    def select_event(self, event_id: int | None):
        event = self.service.get_event(event_id) if event_id else None
        previous_event_id = self.selected_event_id
        self.selected_event_id = int(event_id) if event else None
        for index in (1, 2, 3): self.nav_buttons[index].setEnabled(bool(event))
        self.title_bar.set_event_name(event["name"] if event else None)
        self.dashboard.set_event(self.selected_event_id)
        # 선택 직후에는 대시보드만 그린다. 나머지 무거운 화면은 해당 메뉴를
        # 처음 눌렀을 때 로드해 행사 선택 응답을 즉시 유지한다.
        if previous_event_id != self.selected_event_id:
            self.events.event_id = self.selected_event_id
            self.events.invalidate()
            self.calendar.event_id = self.selected_event_id
            self.settlement.event_id = self.selected_event_id
        self.nav_buttons[0].setChecked(True); self.stack.setCurrentIndex(0)

    def _contacts_for_event_dialog(self):
        vendors = self.db.query("SELECT * FROM contacts WHERE kind='VENDOR' ORDER BY name")
        freelancers = self.db.query("SELECT * FROM contacts WHERE kind='PERSON' AND company_id IS NULL ORDER BY name")
        return vendors, freelancers

    def create_event(self):
        masters = self.db.query("SELECT * FROM master_items WHERE active=1 ORDER BY sort_order")
        vendors, freelancers = self._contacts_for_event_dialog()
        dialog = EventDialog(masters, vendors=vendors, freelancers=freelancers, parent=self)
        if not dialog.exec(): return
        try:
            event_id = self.service.create_event(**dialog.values(), selected_master_ids=dialog.selected_ids(),
                                                 vendor_ids=dialog.selected_vendor_ids(),
                                                 freelancer_ids=dialog.selected_freelancer_ids())
        except Exception as exc:
            QMessageBox.critical(self, "행사 생성 실패", str(exc)); return
        self.select_event(event_id); self.nav_buttons[1].click()

    def edit_event(self, event_id):
        event = self.service.get_event(event_id)
        if not event: return
        vendors, freelancers = self._contacts_for_event_dialog()
        participants = self.service.event_participants(event_id)
        dialog = EventDialog([], event=event, vendors=vendors, freelancers=freelancers,
                             selected_vendor_ids=[row["id"] for row in participants["vendors"]],
                             selected_freelancer_ids=[row["id"] for row in participants["freelancers"]], parent=self)
        if not dialog.exec(): return
        try:
            self.service.update_event(event_id, **dialog.values(), rebase_auto=True)
            self.service.set_event_participants(event_id, dialog.selected_vendor_ids(), dialog.selected_freelancer_ids())
        except Exception as exc:
            QMessageBox.critical(self, "행사 수정 실패", str(exc)); return
        self.events.invalidate()
        self.select_event(event_id)

    def delete_event(self, event_id):
        event = self.service.get_event(event_id)
        if not event: return
        answer = QMessageBox.warning(
            self, "행사 삭제 확인", f"'{event['name']}' 행사와 체크리스트를 삭제할까요?\n삭제 전에 필요한 경우 데이터 관리에서 백업하세요.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.service.delete_event(event_id); self.select_event(None)

    def refresh_dynamic(self, _event_id=0):
        if not self.selected_event_id: return
        # 보이지 않는 화면까지 즉시 다시 만드는 대신 다음 메뉴 진입 때 최신
        # 데이터를 읽는다. 현재 화면은 각 페이지가 변경 직후 자체 갱신한다.
        self.events.invalidate()

    def refresh_all(self, event_id=None): self.select_event(event_id)

    def check_updates(self):
        if self.update_check_thread and self.update_check_thread.isRunning(): return
        self.title_bar.set_update_checking()
        self.update_check_thread = UpdateCheckThread(self)
        self.update_check_thread.finished_with_result.connect(self._update_check_finished)
        self.update_check_thread.failed.connect(self.title_bar.set_update_error)
        self.update_check_thread.start()

    def _update_check_finished(self, info):
        update_available = bool(info and version_tuple(info.version) > version_tuple(__version__))
        self.available_update = info if update_available else None
        self.title_bar.set_update_status(info, update_available)

    def install_available_update(self):
        info = self.available_update
        if not info:
            self.check_updates()
            return
        if not info.asset_url:
            webbrowser.open(info.release_url); return
        answer = QMessageBox.question(
            self, "업데이트 설치", f"이벤트 플로우 {info.version} 버전을 내려받아 설치할까요?\n"
            "설치 중 앱이 종료된 뒤 새 버전으로 다시 실행됩니다. 행사 데이터는 그대로 유지됩니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes: return
        self.update_progress = QProgressDialog("업데이트를 내려받는 중입니다…", "취소", 0, 0, self)
        self.update_progress.setWindowTitle("이플 업데이트"); self.update_progress.setCancelButton(None)
        self.update_progress.setWindowModality(Qt.WindowModality.WindowModal); self.update_progress.show()
        self.update_download_thread = UpdateDownloadThread(info, self)
        self.update_download_thread.downloaded.connect(self._update_downloaded)
        self.update_download_thread.failed.connect(self._update_failed)
        self.update_download_thread.start()

    def _update_downloaded(self, archive):
        self.update_progress.close()
        try: launch_installer(archive, self.available_update, os.getpid())
        except Exception as exc:
            QMessageBox.critical(self, "업데이트 실패", str(exc)); return
        QApplication.quit()

    def _update_failed(self, message):
        self.update_progress.close(); QMessageBox.critical(self, "업데이트 실패", message)

    def nativeEvent(self, event_type, message):
        if event_type == b"windows_generic_MSG" and not self.isMaximized():
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0084:  # WM_NCHITTEST
                point = self.mapFromGlobal(self.cursor().pos()); border = 7
                left, right = point.x() < border, point.x() >= self.width() - border
                top, bottom = point.y() < border, point.y() >= self.height() - border
                hit = 0
                if top and left: hit = 13
                elif top and right: hit = 14
                elif bottom and left: hit = 16
                elif bottom and right: hit = 17
                elif left: hit = 10
                elif right: hit = 11
                elif top: hit = 12
                elif bottom: hit = 15
                if hit: return True, hit
        return super().nativeEvent(event_type, message)
