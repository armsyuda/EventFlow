from __future__ import annotations

import shutil
from datetime import date, datetime
from pathlib import Path

from .database import Database


def create_backup(db: Database, destination: Path) -> Path:
    db.checkpoint()
    destination = Path(destination)
    if destination.suffix.lower() != ".db":
        destination.mkdir(parents=True, exist_ok=True)
        destination = destination / f"event_checklist_{datetime.now():%Y%m%d_%H%M%S}.db"
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db.path, destination)
    return destination


def automatic_daily_backup(db: Database, directory: Path) -> Path | None:
    today = date.today().isoformat()
    if db.get_setting("last_auto_backup") == today:
        return None
    result = create_backup(db, directory)
    db.set_setting("last_auto_backup", today)
    return result


def restore_backup(db: Database, source: Path) -> None:
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(source)
    probe = Database(source)
    try:
        row = probe.one("SELECT version FROM schema_info LIMIT 1")
        if row is None:
            raise ValueError("올바른 백업 데이터베이스가 아닙니다.")
    finally:
        probe.close()
    db.close()
    try:
        shutil.copy2(source, db.path)
    finally:
        db.open()

