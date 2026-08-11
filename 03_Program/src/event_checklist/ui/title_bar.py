from __future__ import annotations

from importlib.resources import files

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from .. import __version__


def app_icon() -> QIcon:
    path = files("event_checklist").joinpath("resources/assets/event_flow.ico")
    return QIcon(str(path)) if path.is_file() else QIcon()


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setObjectName("TitleBar"); self.setFixedHeight(44)
        layout = QHBoxLayout(self); layout.setContentsMargins(12, 0, 0, 0); layout.setSpacing(8)
        icon = QLabel(); icon.setPixmap(app_icon().pixmap(24, 24)); icon.setFixedSize(26, 26)
        title = QLabel("이벤트 플로우"); title.setObjectName("TitleBarName")
        self.event_name = QLabel("행사를 선택하세요"); self.event_name.setObjectName("TitleBarEvent")
        layout.addWidget(icon); layout.addWidget(title); layout.addWidget(self.event_name); layout.addStretch()
        self.update_button = QPushButton("업데이트 확인 중")
        self.update_button.setObjectName("UpdateButton")
        self.update_button.setFixedHeight(30)
        self.update_button.setEnabled(False)
        self.update_meta = QLabel(f"현재 {__version__}")
        self.update_meta.setObjectName("UpdateMeta")
        self.update_meta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.update_meta)
        layout.addWidget(self.update_button)
        self.minimum = self._button("—", "창 최소화", self.window.showMinimized)
        self.maximum = self._button("□", "창 최대화", self.toggle_maximized)
        self.close_button = self._button("×", "프로그램 종료", self.window.close, close=True)
        layout.addWidget(self.minimum); layout.addWidget(self.maximum); layout.addWidget(self.close_button)

    def _button(self, text, tooltip, callback, close=False):
        button = QPushButton(text); button.setObjectName("TitleCloseButton" if close else "TitleControlButton")
        button.setToolTip(tooltip); button.setFixedSize(46, 44); button.clicked.connect(callback); return button

    def set_event_name(self, name): self.event_name.setText(name or "행사를 선택하세요")

    def set_update_status(self, info=None, update_available: bool = False):
        if info is None:
            self.update_meta.setText(f"현재 {__version__}")
            self.update_button.setText("다시 확인")
            self.update_button.setEnabled(True)
            return
        release_date = (info.published_at or "")[:10] or "날짜 미확인"
        if update_available:
            self.update_meta.setText(f"새 버전 {info.version} · {release_date}")
            self.update_button.setText("업데이트")
            self.update_button.setToolTip(f"공개 릴리스 {info.version} 설치")
        else:
            self.update_meta.setText(f"현재 {__version__} · 공개 {info.version} · {release_date}")
            self.update_button.setText("다시 확인")
            self.update_button.setToolTip("GitHub 공개 릴리스를 다시 확인합니다.")
        self.update_button.setEnabled(True)

    def set_update_checking(self):
        self.update_meta.setText(f"현재 {__version__} · 확인 중…")
        self.update_button.setText("확인 중")
        self.update_button.setEnabled(False)

    def set_update_error(self):
        self.update_meta.setText(f"현재 {__version__} · 확인 실패")
        self.update_button.setText("업데이트 확인 불가")
        self.update_button.setEnabled(True)
        self.update_button.setToolTip("인터넷 연결 또는 GitHub 저장소 공개 설정을 확인하세요.")

    def toggle_maximized(self):
        self.window.showNormal() if self.window.isMaximized() else self.window.showMaximized()
        self.maximum.setText("❐" if self.window.isMaximized() else "□")

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.toggle_maximized(); event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.window.isMaximized():
            handle = self.window.windowHandle()
            if handle: handle.startSystemMove()
            event.accept()
