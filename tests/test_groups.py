import json

import pytest

from display_switch.groups import GroupStore


def test_missing_file_loads_empty(tmp_path):
    store = GroupStore(tmp_path / "groups.json")
    store.load()
    assert store.groups == []


def test_round_trip(tmp_path):
    path = tmp_path / "groups.json"
    store = GroupStore(path)
    store.add("Work")
    store.set_members("Work", ["A", "B", "A"])
    store.save()

    loaded = GroupStore(path)
    loaded.load()
    assert [g.name for g in loaded.groups] == ["Work"]
    assert loaded.get("Work").monitor_ids == ["A", "B"]


def test_corrupt_file_is_backed_up(tmp_path):
    path = tmp_path / "groups.json"
    path.write_text("{not json", encoding="utf-8")
    store = GroupStore(path)
    store.load()
    assert store.groups == []
    assert (tmp_path / "groups.json.corrupt").exists()


def test_invalid_entries_are_skipped(tmp_path):
    path = tmp_path / "groups.json"
    payload = {
        "groups": [
            {"name": "Good", "monitor_ids": ["X", 5]},
            {"name": "Good", "monitor_ids": []},
            {"name": "", "monitor_ids": []},
            "junk",
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    store = GroupStore(path)
    store.load()
    assert [g.name for g in store.groups] == ["Good"]
    assert store.groups[0].monitor_ids == ["X"]


def test_add_rejects_empty_and_duplicate(tmp_path):
    store = GroupStore(tmp_path / "groups.json")
    store.add("Office")
    with pytest.raises(ValueError):
        store.add("   ")
    with pytest.raises(ValueError):
        store.add("Office")


def test_rename_and_delete(tmp_path):
    store = GroupStore(tmp_path / "groups.json")
    store.add("A")
    store.add("B")
    with pytest.raises(ValueError):
        store.rename("A", "B")
    store.rename("A", "C")
    assert store.get("C") is not None
    store.delete("C")
    assert store.get("C") is None
