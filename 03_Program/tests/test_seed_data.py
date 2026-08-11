from __future__ import annotations

import json
from importlib.resources import files


def test_seed_has_120_clean_items():
    payload = files("event_checklist").joinpath("resources/master_items.json").read_text(encoding="utf-8")
    items = json.loads(payload)
    assert len(items) == 120
    assert {item["major"] for item in items} == {"시스템", "시설", "행사", "홍보", "운영"}
    assert any(item["name"] == "카메라다이" for item in items)
    assert any(item["name"] == "콘솔다이" for item in items)
    assert '"81"' not in payload
    assert "#NAME?" not in payload
    assert all(item["start_offset"] <= item["due_offset"] for item in items)


def test_database_is_seeded(db):
    assert db.one("SELECT COUNT(*) count FROM master_items")["count"] == 120
    assert db.one("SELECT COUNT(*) count FROM contacts WHERE kind='PERSON'")["count"] == 9

