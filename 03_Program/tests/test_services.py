from __future__ import annotations

from datetime import date

from event_checklist.services import EventService


def test_create_event_only_selected_and_snapshot_is_stable(db):
    service = EventService(db)
    masters = db.query("SELECT * FROM master_items ORDER BY sort_order LIMIT 3")
    event_id = service.create_event("테스트 행사", date(2026, 10, 2), date(2026, 10, 3), [masters[0]["id"], masters[2]["id"]])
    tasks = service.list_tasks(event_id)
    assert len(tasks) == 2
    first_name = tasks[0]["name"]
    db.execute("UPDATE master_items SET name='변경된 기본 항목' WHERE id=?", (masters[0]["id"],))
    assert service.list_tasks(event_id)[0]["name"] == first_name


def test_rebase_auto_preserves_manual_task(db):
    service = EventService(db)
    masters = db.query("SELECT * FROM master_items ORDER BY sort_order LIMIT 2")
    event_id = service.create_event("일정 행사", date(2026, 6, 1), None, [row["id"] for row in masters])
    tasks = service.list_tasks(event_id)
    manual_id = tasks[0]["id"]
    auto_id = tasks[1]["id"]
    service.update_task(manual_id, planned_start="2026-05-01", due_date="2026-05-15")
    old_auto = db.one("SELECT planned_start,due_date FROM event_tasks WHERE id=?", (auto_id,))
    service.update_event(event_id, "일정 행사", date(2026, 6, 11), None)
    manual = db.one("SELECT planned_start,due_date,schedule_mode FROM event_tasks WHERE id=?", (manual_id,))
    auto = db.one("SELECT planned_start,due_date,schedule_mode FROM event_tasks WHERE id=?", (auto_id,))
    assert (manual["planned_start"], manual["due_date"], manual["schedule_mode"]) == ("2026-05-01", "2026-05-15", "manual")
    assert auto["schedule_mode"] == "auto"
    assert auto["planned_start"] != old_auto["planned_start"]


def test_progress_excludes_not_applicable(db):
    service = EventService(db)
    ids = [row["id"] for row in db.query("SELECT id FROM master_items ORDER BY id LIMIT 3")]
    event_id = service.create_event("진행률 행사", date.today(), None, ids)
    tasks = service.list_tasks(event_id)
    service.set_completed(tasks[0]["id"], True)
    service.update_task(tasks[1]["id"], status="해당없음")
    result = service.dashboard(event_id)
    assert result["managed"] == 2
    assert result["completed"] == 1
    assert result["progress"] == 0.5


def test_master_defaults_copy_to_new_event(db):
    service = EventService(db)
    master = db.one("SELECT id FROM master_items ORDER BY id LIMIT 1")
    person = db.one("SELECT id FROM contacts WHERE kind='PERSON' ORDER BY id LIMIT 1")
    vendor = db.one("SELECT id FROM contacts WHERE kind='VENDOR' ORDER BY id LIMIT 1")
    db.execute(
        "UPDATE master_items SET quantity=7,unit='대',default_assignee_id=?,default_vendor_id=? WHERE id=?",
        (person["id"], vendor["id"], master["id"]),
    )
    event_id = service.create_event("기본값 행사", date(2026, 9, 1), None, [master["id"]])
    task = db.one("SELECT quantity,unit,assignee_id,vendor_id FROM event_tasks WHERE event_id=?", (event_id,))
    assert (task["quantity"], task["unit"], task["assignee_id"], task["vendor_id"]) == (
        7, "대", person["id"], vendor["id"]
    )


def test_price_vat_snapshot_and_round_half_up(db):
    service = EventService(db)
    master = db.one("SELECT id FROM master_items ORDER BY id LIMIT 1")
    db.execute("UPDATE master_items SET quantity=2.5,base_unit_price=333,default_vat_type='TAXABLE' WHERE id=?", (master["id"],))
    event_id = service.create_event("정산 행사", date(2026, 9, 1), None, [master["id"]], budget=1000, budget_tax_mode="INCLUDED")
    task = service.list_tasks(event_id)[0]
    assert (task["unit_price"], task["vat_type"]) == (333, "TAXABLE")
    assert service.line_amounts(task["quantity"], task["unit_price"], task["vat_type"]) == (833, 83, 916)
    summary = service.settlement_summary(event_id)
    assert (summary["supply"], summary["vat"], summary["total"], summary["difference"]) == (833, 83, 916, 84)


def test_import_remove_restore_and_custom_task(db):
    service = EventService(db)
    masters = db.query("SELECT id FROM master_items ORDER BY id LIMIT 2")
    event_id = service.create_event("항목 관리", date(2026, 9, 1), None, [masters[0]["id"]])
    added, restored = service.add_master_tasks(event_id, [masters[1]["id"]])
    assert (added, restored) == (1, 0)
    task = db.one("SELECT id FROM event_tasks WHERE event_id=? AND master_item_id=?", (event_id, masters[1]["id"]))
    service.update_task(task["id"], status="진행중", note="보존 기록")
    service.set_task_removed([task["id"]], True, "이번 행사에는 불필요")
    assert db.one("SELECT removed_reason FROM event_tasks WHERE id=?", (task["id"],))["removed_reason"] == "이번 행사에는 불필요"
    assert len(service.list_tasks(event_id)) == 1
    assert service.add_master_tasks(event_id, [masters[1]["id"]]) == (0, 1)
    restored_task = db.one("SELECT status,note,is_removed,removed_reason FROM event_tasks WHERE id=?", (task["id"],))
    assert tuple(restored_task) == ("진행중", "보존 기록", 0, "")
    custom_id = service.add_custom_task(event_id, major="운영", minor="현장", name="일회성",
                                        planned_start=date(2026, 9, 1), due_date=date(2026, 9, 2))
    custom = db.one("SELECT master_item_id,quantity,schedule_mode FROM event_tasks WHERE id=?", (custom_id,))
    assert tuple(custom) == (None, 1, "manual")


def test_event_participants_and_company_assignees(db):
    service = EventService(db)
    vendor = db.one("SELECT id FROM contacts WHERE kind='VENDOR' ORDER BY id LIMIT 1")
    db.execute("INSERT INTO contacts(kind,name,company_id) VALUES ('PERSON','업체 담당자',?)", (vendor["id"],))
    person_id = db.one("SELECT last_insert_rowid() id")["id"]
    freelancer = db.one("SELECT id FROM contacts WHERE kind='PERSON' AND company_id IS NULL ORDER BY id LIMIT 1")
    master = db.one("SELECT id FROM master_items ORDER BY id LIMIT 1")
    event_id = service.create_event("참여자 행사", date(2026, 9, 1), None, [master["id"]],
                                    vendor_ids=[vendor["id"]], freelancer_ids=[freelancer["id"]])
    available = {row["id"] for row in service.available_assignees(event_id, vendor["id"])}
    assert {person_id, freelancer["id"]} <= available


def test_calendar_hides_completed_bars_but_lists_completed_last(db):
    service = EventService(db)
    masters = db.query("SELECT id FROM master_items ORDER BY id LIMIT 3")
    selected = date.today()
    event_id = service.create_event("달력 상태", selected, selected, [row["id"] for row in masters])
    tasks = service.list_tasks(event_id)
    for task in tasks:
        service.update_task(task["id"], planned_start=selected.isoformat(), due_date=selected.isoformat())
    service.update_task(tasks[0]["id"], status="완료")
    service.update_task(tasks[1]["id"], status="진행중", priority="상")

    bars = service.calendar_range(selected, selected, event_id)
    listed = service.calendar_tasks(selected, event_id)

    assert tasks[0]["id"] not in {row["id"] for row in bars}
    assert listed[-1]["status"] == "완료"
    assert listed[0]["status"] == "진행중"
