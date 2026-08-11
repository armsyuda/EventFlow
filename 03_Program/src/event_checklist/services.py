from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from .database import Database
from .schedule import calculate_schedule


class EventService:
    def __init__(self, db: Database):
        self.db = db

    def list_events(self):
        return self.db.query("SELECT * FROM events ORDER BY start_date DESC, id DESC")

    def get_event(self, event_id: int):
        return self.db.one("SELECT * FROM events WHERE id=?", (event_id,))

    def create_event(
        self,
        name: str,
        start_date: date,
        end_date: date | None,
        selected_master_ids: Iterable[int],
        location: str = "",
        organizer: str = "",
        budget: float | None = None,
        budget_tax_mode: str = "UNSET",
        vendor_ids: Iterable[int] = (),
        freelancer_ids: Iterable[int] = (),
    ) -> int:
        name = name.strip()
        if not name:
            raise ValueError("행사명을 입력하세요.")
        if end_date and end_date < start_date:
            raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
        ids = list(dict.fromkeys(int(value) for value in selected_master_ids))
        if not ids:
            raise ValueError("하나 이상의 기본 항목을 선택하세요.")
        placeholders = ",".join("?" for _ in ids)
        masters = self.db.query(
            f"SELECT * FROM master_items WHERE id IN ({placeholders}) ORDER BY sort_order", ids
        )
        if len(masters) != len(ids):
            raise ValueError("선택한 기본 항목 중 사용할 수 없는 항목이 있습니다.")

        selected_vendors = {int(value) for value in vendor_ids}
        selected_freelancers = {int(value) for value in freelancer_ids}
        selected_vendors.update(int(item["default_vendor_id"]) for item in masters if item["default_vendor_id"])
        for item in masters:
            if not item["default_assignee_id"]:
                continue
            contact = self.db.one("SELECT company_id FROM contacts WHERE id=?", (item["default_assignee_id"],))
            if contact and contact["company_id"]:
                selected_vendors.add(int(contact["company_id"]))
            elif contact:
                selected_freelancers.add(int(item["default_assignee_id"]))

        with self.db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO events(name,start_date,end_date,location,organizer,budget,budget_tax_mode) VALUES (?,?,?,?,?,?,?)",
                (name, start_date.isoformat(), end_date.isoformat() if end_date else None, location.strip(), organizer.strip(), budget, budget_tax_mode),
            )
            event_id = int(cursor.lastrowid)
            conn.executemany(
                "INSERT OR IGNORE INTO event_vendors(event_id,vendor_id) VALUES (?,?)",
                [(event_id, value) for value in sorted(selected_vendors)],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO event_freelancers(event_id,person_id) VALUES (?,?)",
                [(event_id, value) for value in sorted(selected_freelancers)],
            )
            for item in masters:
                schedule = calculate_schedule(
                    start_date, end_date, item["anchor"], item["start_offset"], item["due_offset"]
                )
                conn.execute(
                    """
                    INSERT INTO event_tasks(
                        event_id,master_item_id,major,minor,name,detail,status,quantity,unit,assignee_id,vendor_id,
                        planned_start,due_date,schedule_mode,anchor,start_offset,due_offset,sort_order,unit_price,vat_type
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        event_id, item["id"], item["major"], item["minor"], item["name"], item["detail"],
                        "미착수", item["quantity"], item["unit"],
                        item["default_assignee_id"], item["default_vendor_id"],
                        schedule.planned_start.isoformat(), schedule.due_date.isoformat(), "auto",
                        item["anchor"], item["start_offset"], item["due_offset"], item["sort_order"],
                        item["base_unit_price"], item["default_vat_type"],
                    ),
                )
        return event_id

    def update_event(
        self,
        event_id: int,
        name: str,
        start_date: date,
        end_date: date | None,
        location: str = "",
        organizer: str = "",
        budget: float | None = None,
        budget_tax_mode: str = "UNSET",
        rebase_auto: bool = True,
    ) -> None:
        if not name.strip():
            raise ValueError("행사명을 입력하세요.")
        if end_date and end_date < start_date:
            raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE events SET name=?,start_date=?,end_date=?,location=?,organizer=?,budget=?,budget_tax_mode=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (name.strip(), start_date.isoformat(), end_date.isoformat() if end_date else None,
                 location.strip(), organizer.strip(), budget, budget_tax_mode, event_id),
            )
            if rebase_auto:
                tasks = conn.execute(
                    "SELECT id,anchor,start_offset,due_offset FROM event_tasks WHERE event_id=? AND schedule_mode='auto'",
                    (event_id,),
                ).fetchall()
                for task in tasks:
                    schedule = calculate_schedule(
                        start_date, end_date, task["anchor"], task["start_offset"], task["due_offset"]
                    )
                    conn.execute(
                        "UPDATE event_tasks SET planned_start=?,due_date=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (schedule.planned_start.isoformat(), schedule.due_date.isoformat(), task["id"]),
                    )

    def delete_event(self, event_id: int) -> None:
        self.db.execute("DELETE FROM events WHERE id=?", (event_id,))

    def list_tasks(self, event_id: int, search: str = "", status: str = "", major: str = "", include_removed: bool = False):
        sql = """
            SELECT t.*, p.name AS assignee_name, v.name AS vendor_name
            FROM event_tasks t
            LEFT JOIN contacts p ON p.id=t.assignee_id
            LEFT JOIN contacts v ON v.id=t.vendor_id
            WHERE t.event_id=?
        """
        params: list[object] = [event_id]
        if not include_removed:
            sql += " AND t.is_removed=0"
        if search:
            sql += " AND (t.name LIKE ? OR t.detail LIKE ? OR t.note LIKE ?)"
            value = f"%{search}%"
            params.extend([value, value, value])
        if status:
            sql += " AND t.status=?"
            params.append(status)
        if major:
            sql += " AND t.major=?"
            params.append(major)
        sql += " ORDER BY t.due_date, t.sort_order"
        return self.db.query(sql, params)

    def update_task(self, task_id: int, **fields) -> None:
        allowed = {
            "status", "quantity", "unit", "assignee_id", "vendor_id",
            "planned_start", "due_date", "cost", "note", "detail", "required",
            "unit_price", "vat_type", "is_removed", "removed_reason",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"수정할 수 없는 필드: {', '.join(sorted(unknown))}")
        if not fields:
            return
        row = self.db.one("SELECT planned_start,due_date,status FROM event_tasks WHERE id=?", (task_id,))
        if row is None:
            raise ValueError("업무를 찾을 수 없습니다.")
        planned = fields.get("planned_start", row["planned_start"])
        due = fields.get("due_date", row["due_date"])
        if planned > due:
            raise ValueError("작업 시작일은 마감일보다 늦을 수 없습니다.")
        if "planned_start" in fields or "due_date" in fields:
            fields["schedule_mode"] = "manual"
            allowed.add("schedule_mode")
        if "status" in fields:
            fields["completed_at"] = datetime.now().isoformat(timespec="seconds") if fields["status"] == "완료" else None
            allowed.add("completed_at")
        assignments = ",".join(f"{key}=?" for key in fields)
        values = list(fields.values()) + [task_id]
        self.db.execute(
            f"UPDATE event_tasks SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE id=?", values
        )

    def set_completed(self, task_id: int, completed: bool) -> None:
        self.update_task(task_id, status="완료" if completed else "미착수")

    def dashboard(self, event_id: int) -> dict:
        row = self.db.one(
            """
            SELECT
                COUNT(*) total,
                SUM(CASE WHEN required=1 AND status<>'해당없음' THEN 1 ELSE 0 END) managed,
                SUM(CASE WHEN status='완료' THEN 1 ELSE 0 END) completed,
                SUM(CASE WHEN status='진행중' THEN 1 ELSE 0 END) in_progress,
                SUM(CASE WHEN status='미착수' THEN 1 ELSE 0 END) not_started,
                SUM(CASE WHEN required=1 AND status NOT IN ('완료','해당없음') AND due_date < date('now','localtime') THEN 1 ELSE 0 END) overdue
            FROM event_tasks WHERE event_id=? AND is_removed=0
            """,
            (event_id,),
        )
        data = dict(row) if row else {}
        managed = data.get("managed") or 0
        completed = data.get("completed") or 0
        data["progress"] = completed / managed if managed else 0.0
        data["urgent"] = self.db.query(
            """
            SELECT id,name,status,due_date,
                   CAST(julianday(due_date)-julianday(date('now','localtime')) AS INTEGER) dday
            FROM event_tasks
            WHERE event_id=? AND is_removed=0 AND required=1 AND status NOT IN ('완료','해당없음')
              AND due_date <= date('now','localtime','+7 day')
            ORDER BY due_date, sort_order LIMIT 12
            """,
            (event_id,),
        )
        return data

    def calendar_tasks(self, selected_date: date, event_id: int | None = None):
        sql = """
            SELECT t.*, e.name AS event_name
            FROM event_tasks t JOIN events e ON e.id=t.event_id
            WHERE t.is_removed=0 AND ? BETWEEN t.planned_start AND t.due_date
        """
        params: list[object] = [selected_date.isoformat()]
        if event_id:
            sql += " AND t.event_id=?"
            params.append(event_id)
        sql += """ ORDER BY
            CASE WHEN t.status='완료' THEN 1 ELSE 0 END,
            CASE WHEN t.status<>'완료' AND t.due_date < date('now','localtime') THEN 0 ELSE 1 END,
            t.due_date, t.sort_order"""
        return self.db.query(sql, params)

    def calendar_range(self, first: date, last: date, event_id: int | None = None):
        sql = """
            SELECT id,event_id,name,major,sort_order,planned_start,due_date,status
            FROM event_tasks WHERE is_removed=0 AND status NOT IN ('완료','해당없음')
              AND due_date>=? AND planned_start<=?
        """
        params: list[object] = [first.isoformat(), last.isoformat()]
        if event_id:
            sql += " AND event_id=?"
            params.append(event_id)
        sql += " ORDER BY due_date, sort_order"
        return self.db.query(sql, params)

    def set_event_participants(self, event_id: int, vendor_ids=(), freelancer_ids=()) -> None:
        vendor_set = {int(value) for value in vendor_ids}
        freelancer_set = {int(value) for value in freelancer_ids}
        assigned = self.db.query(
            """SELECT DISTINCT t.vendor_id,t.assignee_id,c.company_id FROM event_tasks t
               LEFT JOIN contacts c ON c.id=t.assignee_id WHERE t.event_id=?""", (event_id,))
        for row in assigned:
            if row["vendor_id"]: vendor_set.add(int(row["vendor_id"]))
            if row["company_id"]: vendor_set.add(int(row["company_id"]))
            elif row["assignee_id"]: freelancer_set.add(int(row["assignee_id"]))
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM event_vendors WHERE event_id=?", (event_id,))
            conn.execute("DELETE FROM event_freelancers WHERE event_id=?", (event_id,))
            conn.executemany(
                "INSERT INTO event_vendors(event_id,vendor_id) VALUES (?,?)",
                [(event_id, value) for value in sorted(vendor_set)],
            )
            conn.executemany(
                "INSERT INTO event_freelancers(event_id,person_id) VALUES (?,?)",
                [(event_id, value) for value in sorted(freelancer_set)],
            )

    def event_participants(self, event_id: int) -> dict:
        return {
            "vendors": self.db.query(
                "SELECT c.* FROM contacts c JOIN event_vendors x ON x.vendor_id=c.id WHERE x.event_id=? ORDER BY c.name",
                (event_id,),
            ),
            "freelancers": self.db.query(
                "SELECT c.* FROM contacts c JOIN event_freelancers x ON x.person_id=c.id WHERE x.event_id=? ORDER BY c.name",
                (event_id,),
            ),
        }

    def available_assignees(self, event_id: int, vendor_id: int | None = None):
        params: list[object] = [event_id]
        sql = """
            SELECT DISTINCT c.* FROM contacts c
            WHERE c.kind='PERSON' AND (
                c.id IN (SELECT person_id FROM event_freelancers WHERE event_id=?)
        """
        if vendor_id:
            sql += " OR c.company_id=?"
            params.append(vendor_id)
        else:
            sql += " OR c.company_id IN (SELECT vendor_id FROM event_vendors WHERE event_id=?)"
            params.append(event_id)
        sql += ") ORDER BY c.name"
        return self.db.query(sql, params)

    def add_master_tasks(self, event_id: int, master_ids: Iterable[int]) -> tuple[int, int]:
        event = self.get_event(event_id)
        if not event:
            raise ValueError("행사를 찾을 수 없습니다.")
        restored = 0
        added = 0
        with self.db.transaction() as conn:
            for master_id in dict.fromkeys(int(value) for value in master_ids):
                existing = conn.execute(
                    "SELECT id,is_removed FROM event_tasks WHERE event_id=? AND master_item_id=?",
                    (event_id, master_id),
                ).fetchone()
                if existing:
                    if existing["is_removed"]:
                        conn.execute("UPDATE event_tasks SET is_removed=0,removed_reason='' WHERE id=?", (existing["id"],))
                        restored += 1
                    continue
                item = conn.execute("SELECT * FROM master_items WHERE id=?", (master_id,)).fetchone()
                if not item:
                    continue
                schedule = calculate_schedule(
                    date.fromisoformat(event["start_date"]),
                    date.fromisoformat(event["end_date"]) if event["end_date"] else None,
                    item["anchor"], item["start_offset"], item["due_offset"],
                )
                conn.execute(
                    """INSERT INTO event_tasks(
                       event_id,master_item_id,major,minor,name,detail,status,quantity,unit,
                       assignee_id,vendor_id,planned_start,due_date,schedule_mode,anchor,start_offset,due_offset,
                       sort_order,unit_price,vat_type) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (event_id,item["id"],item["major"],item["minor"],item["name"],item["detail"],"미착수",
                     item["quantity"],item["unit"],item["default_assignee_id"],item["default_vendor_id"],
                     schedule.planned_start.isoformat(),schedule.due_date.isoformat(),"auto",item["anchor"],
                     item["start_offset"],item["due_offset"],item["sort_order"],item["base_unit_price"],item["default_vat_type"]),
                )
                added += 1
        return added, restored

    def add_custom_task(self, event_id: int, *, major: str, minor: str, name: str, planned_start: date,
                        due_date: date, quantity: float = 1, unit: str = "", unit_price: int | None = None,
                        vat_type: str = "TAXABLE", detail: str = "") -> int:
        if not name.strip() or planned_start > due_date:
            raise ValueError("항목명과 올바른 작업 기간을 입력하세요.")
        next_order = self.db.one("SELECT COALESCE(MAX(sort_order),0)+1 n FROM event_tasks WHERE event_id=?", (event_id,))["n"]
        cursor = self.db.execute(
            """INSERT INTO event_tasks(event_id,major,minor,name,detail,status,quantity,unit,
               planned_start,due_date,schedule_mode,anchor,start_offset,due_offset,sort_order,unit_price,vat_type)
               VALUES (?,?,?,?,?,'미착수',?,?,?,?, 'manual','START',0,0,?,?,?)""",
            (event_id,major.strip(),minor.strip(),name.strip(),detail.strip(),quantity,unit.strip(),
             planned_start.isoformat(),due_date.isoformat(),next_order,unit_price,vat_type),
        )
        return int(cursor.lastrowid)

    def set_task_removed(self, task_ids: Iterable[int], removed: bool, reason: str = "") -> None:
        ids = list(dict.fromkeys(int(value) for value in task_ids))
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self.db.execute(
            f"UPDATE event_tasks SET is_removed=?,removed_reason=? WHERE id IN ({placeholders})",
            (1 if removed else 0, reason.strip() if removed else "", *ids),
        )

    @staticmethod
    def line_amounts(quantity, unit_price, vat_type: str) -> tuple[int, int, int]:
        if quantity is None or unit_price is None:
            return 0, 0, 0
        supply = int((Decimal(str(quantity)) * Decimal(int(unit_price))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        vat = int((Decimal(supply) * Decimal("0.10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if vat_type == "TAXABLE" else 0
        return supply, vat, supply + vat

    def settlement_summary(self, event_id: int) -> dict:
        event = self.get_event(event_id)
        rows = self.db.query(
            """SELECT t.*,v.name vendor_name FROM event_tasks t
               LEFT JOIN contacts v ON v.id=t.vendor_id
               WHERE t.event_id=? AND t.is_removed=0 AND t.status<>'해당없음'
               ORDER BY t.major,t.minor,t.sort_order""",
            (event_id,),
        )
        items = []
        categories: dict[str, dict[str, int]] = {}
        warnings = 0
        for row in rows:
            item = dict(row)
            supply, vat, total = self.line_amounts(row["quantity"], row["unit_price"], row["vat_type"])
            item.update(supply=supply, vat=vat, total=total)
            item["warning"] = "수량 미입력" if row["quantity"] is None else ("단가 미입력" if row["unit_price"] is None else "")
            warnings += bool(item["warning"])
            subtotal = categories.setdefault(row["major"], {"supply": 0, "vat": 0, "total": 0})
            for key, value in (("supply", supply), ("vat", vat), ("total", total)):
                subtotal[key] += value
            items.append(item)
        supply = sum(value["supply"] for value in categories.values())
        vat = sum(value["vat"] for value in categories.values())
        total = supply + vat
        budget = int(event["budget"] or 0) if event else 0
        mode = event["budget_tax_mode"] if event else "UNSET"
        comparison = total if mode == "INCLUDED" else supply
        return {"event": event, "items": items, "categories": categories, "supply": supply, "vat": vat,
                "total": total, "budget": budget, "budget_tax_mode": mode,
                "difference": budget - comparison if budget else None, "warnings": warnings}
