from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterator, Sequence


SCHEMA_VERSION = 5


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection: sqlite3.Connection | None = None
        self.open()

    def open(self) -> None:
        if self.connection is not None:
            return
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.initialize()

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self.connection is None:
            raise RuntimeError("데이터베이스가 닫혀 있습니다.")
        return self.connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def initialize(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_info (
                version INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                location TEXT NOT NULL DEFAULT '',
                organizer TEXT NOT NULL DEFAULT '',
                budget REAL,
                budget_tax_mode TEXT NOT NULL DEFAULT 'UNSET'
                    CHECK(budget_tax_mode IN ('INCLUDED','EXCLUDED','UNSET')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK(end_date IS NULL OR end_date >= start_date)
            );

            CREATE TABLE IF NOT EXISTS master_items (
                id INTEGER PRIMARY KEY,
                major TEXT NOT NULL,
                minor TEXT NOT NULL,
                name TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                anchor TEXT NOT NULL CHECK(anchor IN ('START', 'END')),
                start_offset INTEGER NOT NULL,
                due_offset INTEGER NOT NULL,
                priority TEXT NOT NULL DEFAULT '중' CHECK(priority IN ('상', '중', '하')),
                quantity REAL,
                unit TEXT NOT NULL DEFAULT '',
                base_unit_price INTEGER,
                default_vat_type TEXT NOT NULL DEFAULT 'TAXABLE'
                    CHECK(default_vat_type IN ('TAXABLE','EXEMPT')),
                default_vendor_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
                default_assignee_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
                sort_order INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                CHECK(start_offset <= due_offset)
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK(kind IN ('PERSON', 'VENDOR')),
                name TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                role_note TEXT NOT NULL DEFAULT '',
                company_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS event_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                master_item_id INTEGER REFERENCES master_items(id) ON DELETE SET NULL,
                major TEXT NOT NULL,
                minor TEXT NOT NULL,
                name TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                required INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT '미착수'
                    CHECK(status IN ('미착수','진행중','확인요청','완료','보류','해당없음')),
                priority TEXT NOT NULL DEFAULT '중' CHECK(priority IN ('상','중','하')),
                quantity REAL,
                unit TEXT NOT NULL DEFAULT '',
                assignee_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
                vendor_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
                planned_start TEXT NOT NULL,
                due_date TEXT NOT NULL,
                schedule_mode TEXT NOT NULL DEFAULT 'auto' CHECK(schedule_mode IN ('auto','manual')),
                anchor TEXT NOT NULL CHECK(anchor IN ('START','END')),
                start_offset INTEGER NOT NULL,
                due_offset INTEGER NOT NULL,
                cost REAL,
                unit_price INTEGER,
                vat_type TEXT NOT NULL DEFAULT 'TAXABLE'
                    CHECK(vat_type IN ('TAXABLE','EXEMPT')),
                is_removed INTEGER NOT NULL DEFAULT 0,
                removed_reason TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                completed_at TEXT,
                sort_order INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK(planned_start <= due_date)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS event_vendors (
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                vendor_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                PRIMARY KEY(event_id, vendor_id)
            );

            CREATE TABLE IF NOT EXISTS event_freelancers (
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                person_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                PRIMARY KEY(event_id, person_id)
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_event ON event_tasks(event_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_due ON event_tasks(due_date);
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON event_tasks(status);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_kind_name ON contacts(kind, name);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_event_master_unique
                ON event_tasks(event_id, master_item_id) WHERE master_item_id IS NOT NULL;
            """
        )
        row = self.conn.execute("SELECT version FROM schema_info LIMIT 1").fetchone()
        if row is None:
            self.conn.execute("INSERT INTO schema_info(version) VALUES (?)", (SCHEMA_VERSION,))
        elif row["version"] < SCHEMA_VERSION:
            self._migrate(row["version"])
        elif row["version"] > SCHEMA_VERSION:
            raise RuntimeError(f"지원하지 않는 DB 버전: {row['version']}")
        self.conn.execute("DROP INDEX IF EXISTS idx_contacts_kind_name")
        self.conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_company_name "
            "ON contacts(kind,name,COALESCE(company_id,0))"
        )
        task_columns = {column["name"] for column in self.conn.execute("PRAGMA table_info(event_tasks)")}
        if "removed_reason" not in task_columns:
            self.conn.execute("ALTER TABLE event_tasks ADD COLUMN removed_reason TEXT NOT NULL DEFAULT ''")
        self._seed_master_items()
        self._seed_contacts()
        self.conn.commit()

    def _migrate(self, from_version: int) -> None:
        safety_path = self.path.with_name(f"{self.path.stem}.pre-v{from_version}.db")
        if not safety_path.exists():
            safety = sqlite3.connect(safety_path)
            try:
                self.conn.backup(safety)
            finally:
                safety.close()
        version = from_version
        if version == 1:
            self.conn.execute(
                "ALTER TABLE master_items ADD COLUMN default_vendor_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL"
            )
            self.conn.execute(
                "ALTER TABLE master_items ADD COLUMN default_assignee_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL"
            )
            version = 2
        if version == 2:
            # v2까지는 start_date를 행사 당일로 해석해 준비 시작일보다 앞선
            # 일정이 생성됐다. 새 의미(준비 시작일~최종 행사일)에 맞춰 자동
            # 일정만 다시 계산하고, 사용자가 고친 수동 일정은 보존한다.
            from .schedule import calculate_schedule

            events = self.conn.execute("SELECT id,start_date,end_date FROM events").fetchall()
            for event in events:
                event_start = date.fromisoformat(event["start_date"])
                event_end = (
                    date.fromisoformat(event["end_date"])
                    if event["end_date"] else None
                )
                tasks = self.conn.execute(
                    "SELECT id,anchor,start_offset,due_offset FROM event_tasks "
                    "WHERE event_id=? AND schedule_mode='auto'",
                    (event["id"],),
                ).fetchall()
                for task in tasks:
                    schedule = calculate_schedule(
                        event_start, event_end, task["anchor"], task["start_offset"], task["due_offset"]
                    )
                    self.conn.execute(
                        "UPDATE event_tasks SET planned_start=?,due_date=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (schedule.planned_start.isoformat(), schedule.due_date.isoformat(), task["id"]),
                    )
            version = 3
        if version == 3:
            def add_column(table: str, column: str, declaration: str) -> None:
                existing = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")}
                if column not in existing:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

            add_column("master_items", "base_unit_price", "INTEGER")
            add_column("master_items", "default_vat_type", "TEXT NOT NULL DEFAULT 'TAXABLE'")
            add_column("events", "budget_tax_mode", "TEXT NOT NULL DEFAULT 'UNSET'")
            add_column("contacts", "company_id", "INTEGER REFERENCES contacts(id) ON DELETE SET NULL")
            add_column("event_tasks", "unit_price", "INTEGER")
            add_column("event_tasks", "vat_type", "TEXT NOT NULL DEFAULT 'TAXABLE'")
            add_column("event_tasks", "is_removed", "INTEGER NOT NULL DEFAULT 0")
            self.conn.execute(
                """UPDATE event_tasks SET unit_price = CASE
                   WHEN cost IS NULL THEN NULL
                   WHEN quantity IS NOT NULL AND quantity > 0 THEN CAST(ROUND(cost / quantity) AS INTEGER)
                   ELSE CAST(ROUND(cost) AS INTEGER) END"""
            )
            self.conn.execute(
                """INSERT OR IGNORE INTO event_vendors(event_id,vendor_id)
                   SELECT DISTINCT event_id,vendor_id FROM event_tasks WHERE vendor_id IS NOT NULL"""
            )
            self.conn.execute(
                """INSERT OR IGNORE INTO event_freelancers(event_id,person_id)
                   SELECT DISTINCT t.event_id,t.assignee_id FROM event_tasks t
                   JOIN contacts c ON c.id=t.assignee_id
                   WHERE t.assignee_id IS NOT NULL AND c.kind='PERSON' AND c.company_id IS NULL"""
            )
            version = 4
        if version == 4:
            from .units import infer_default_unit

            rows = self.conn.execute("SELECT id,major,minor,name,unit FROM master_items").fetchall()
            for item in rows:
                if not (item["unit"] or "").strip():
                    self.conn.execute(
                        "UPDATE master_items SET unit=? WHERE id=?",
                        (infer_default_unit(item["major"], item["minor"], item["name"]), item["id"]),
                    )
            self.conn.execute(
                """UPDATE event_tasks
                   SET unit=(SELECT m.unit FROM master_items m WHERE m.id=event_tasks.master_item_id)
                   WHERE TRIM(COALESCE(unit,''))='' AND master_item_id IS NOT NULL"""
            )
            version = 5
        if version != SCHEMA_VERSION:
            raise RuntimeError(f"DB 마이그레이션 경로가 없습니다: {from_version} → {SCHEMA_VERSION}")
        self.conn.execute("UPDATE schema_info SET version=?", (SCHEMA_VERSION,))

    def _seed_master_items(self) -> None:
        count = self.conn.execute("SELECT COUNT(*) FROM master_items").fetchone()[0]
        if count:
            return
        resource = files("event_checklist").joinpath("resources/master_items.json")
        items = json.loads(resource.read_text(encoding="utf-8"))
        from .units import infer_default_unit
        for item in items:
            if not (item.get("unit") or "").strip():
                item["unit"] = infer_default_unit(item["major"], item["minor"], item["name"])
        self.conn.executemany(
            """
            INSERT INTO master_items(
                id, major, minor, name, detail, anchor, start_offset, due_offset,
                priority, quantity, unit, sort_order, active
            ) VALUES (
                :id, :major, :minor, :name, :detail, :anchor, :start_offset, :due_offset,
                :priority, :quantity, :unit, :sort_order, :active
            )
            """,
            items,
        )

    def _seed_contacts(self) -> None:
        count = self.conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        if count:
            return
        people = ["총괄", "기획", "무대/시스템", "시설", "홍보", "운영", "행정", "안전", "기록"]
        self.conn.executemany(
            "INSERT INTO contacts(kind, name) VALUES ('PERSON', ?)", [(name,) for name in people]
        )
        self.conn.execute("INSERT INTO contacts(kind, name) VALUES ('VENDOR', '(업체 미정)')")

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        cursor = self.conn.execute(sql, params)
        self.conn.commit()
        return cursor

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, params).fetchall())

    def one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def checkpoint(self) -> None:
        self.conn.commit()
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
