from __future__ import annotations

import argparse
import os
import sys
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from .backup import automatic_daily_backup
from .config import backup_dir, database_path, ensure_directories
from .database import Database
from .theme import application_stylesheet
from .ui.main_window import MainWindow
from .ui.title_bar import app_icon


def _arguments(argv=None):
    parser = argparse.ArgumentParser(description="이벤트 플로우")
    parser.add_argument("--smoke-test", action="store_true", help="창을 초기화한 뒤 자동 종료")
    parser.add_argument("--data-dir", help="개발·검증용 사용자 데이터 폴더")
    parser.add_argument("--screenshot", help="검수용으로 창 이미지를 저장한 뒤 종료")
    parser.add_argument("--page", type=int, choices=range(0, 5), default=0, help="검수용 시작 화면 번호")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _arguments(argv)
    if args.data_dir:
        os.environ["EVENT_CHECKLIST_DATA_DIR"] = args.data_dir
    ensure_directories()
    qt_app = QApplication(sys.argv[:1])
    qt_app.setApplicationName("이벤트 플로우")
    qt_app.setOrganizationName("EventFlow")
    qt_app.setStyle("Fusion")
    qt_app.setWindowIcon(app_icon())
    qt_app.setStyleSheet(application_stylesheet())
    db = None
    try:
        db = Database(database_path())
        automatic_daily_backup(db, backup_dir())
        window = MainWindow(db, enable_update_check=not args.smoke_test and not args.screenshot)
        if args.page:
            window.nav_buttons[args.page].click()
        window.show()
        if args.screenshot:
            def capture_and_quit():
                window.grab().save(args.screenshot)
                qt_app.quit()
            QTimer.singleShot(900, capture_and_quit)
        elif args.smoke_test:
            QTimer.singleShot(700, qt_app.quit)
        return qt_app.exec()
    except Exception as exc:
        traceback.print_exc()
        QMessageBox.critical(None, "시작 실패", f"프로그램을 시작하지 못했습니다.\n\n{exc}")
        return 1
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    raise SystemExit(main())
