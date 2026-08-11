from __future__ import annotations

import sqlite3
from datetime import date

from event_checklist.database import Database
from event_checklist.services import EventService


def test_v1_database_migrates_and_keeps_safety_copy(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE schema_info(version INTEGER NOT NULL);
        INSERT INTO schema_info VALUES (1);
        CREATE TABLE master_items (
            id INTEGER PRIMARY KEY, major TEXT NOT NULL, minor TEXT NOT NULL, name TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '', anchor TEXT NOT NULL, start_offset INTEGER NOT NULL,
            due_offset INTEGER NOT NULL, priority TEXT NOT NULL DEFAULT '중', quantity REAL,
            unit TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1
        );
        """
    )
    conn.commit()
    conn.close()
    db = Database(path)
    columns = {row["name"] for row in db.query("PRAGMA table_info(master_items)")}
    assert {"default_vendor_id", "default_assignee_id"} <= columns
    assert db.one("SELECT version FROM schema_info")["version"] == 4
    assert db.one("SELECT COUNT(*) count FROM master_items")["count"] == 120
    db.close()
    assert (tmp_path / "legacy.pre-v1.db").exists()


def test_v2_auto_schedules_rebase_but_manual_dates_are_preserved(tmp_path):
    path = tmp_path / "v2.db"
    db = Database(path)
    service = EventService(db)
    masters = db.query("SELECT id FROM master_items ORDER BY sort_order LIMIT 2")
    event_id = service.create_event(
        "준비 기간 행사", date(2026, 8, 10), date(2026, 10, 2), [row["id"] for row in masters]
    )
    tasks = db.query("SELECT id FROM event_tasks WHERE event_id=? ORDER BY id", (event_id,))
    auto_id, manual_id = tasks[0]["id"], tasks[1]["id"]
    db.execute(
        "UPDATE event_tasks SET planned_start='2026-04-12',due_date='2026-08-07' WHERE id=?",
        (auto_id,),
    )
    db.execute(
        "UPDATE event_tasks SET planned_start='2026-08-15',due_date='2026-08-20',schedule_mode='manual' WHERE id=?",
        (manual_id,),
    )
    db.execute("UPDATE schema_info SET version=2")
    db.close()

    migrated = Database(path)
    auto = migrated.one("SELECT planned_start,due_date FROM event_tasks WHERE id=?", (auto_id,))
    manual = migrated.one("SELECT planned_start,due_date,schedule_mode FROM event_tasks WHERE id=?", (manual_id,))
    assert auto["planned_start"] >= "2026-08-10"
    assert auto["due_date"] <= "2026-10-02"
    assert (manual["planned_start"], manual["due_date"], manual["schedule_mode"]) == (
        "2026-08-15", "2026-08-20", "manual"
    )
    migrated.close()
    assert (tmp_path / "v2.pre-v2.db").exists()


def test_v3_cost_migrates_to_unit_price_and_keeps_pre_v3_copy(tmp_path):
    path = tmp_path / "event_checklist.db"
    db = Database(path); service = EventService(db)
    master = db.one("SELECT id FROM master_items ORDER BY id LIMIT 1")
    event_id = service.create_event("기존 행사", date(2026, 9, 1), None, [master["id"]])
    db.execute("UPDATE event_tasks SET quantity=4,cost=12000,unit_price=NULL WHERE event_id=?", (event_id,))
    db.execute("UPDATE schema_info SET version=3"); db.close()
    migrated = Database(path)
    assert migrated.one("SELECT unit_price FROM event_tasks WHERE event_id=?", (event_id,))["unit_price"] == 3000
    assert migrated.one("SELECT version FROM schema_info")["version"] == 4
    migrated.close()
    assert (tmp_path / "event_checklist.pre-v3.db").exists()
