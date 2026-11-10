"""Named display groups persisted as JSON."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Group:
    name: str
    monitor_ids: list[str] = field(default_factory=list)


def _parse_groups(raw: Any) -> list[Group]:
    """Build groups from loaded JSON, skipping invalid or duplicate entries."""
    if not isinstance(raw, dict) or not isinstance(raw.get("groups"), list):
        return []

    groups: list[Group] = []
    seen: set[str] = set()
    for item in raw["groups"]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        ids = item.get("monitor_ids", [])
        if not isinstance(name, str) or not name.strip() or name in seen or not isinstance(ids, list):
            continue
        groups.append(Group(name=name, monitor_ids=[i for i in ids if isinstance(i, str)]))
        seen.add(name)
    return groups


class GroupStore:
    """In-memory list of groups with load and save to a JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.groups: list[Group] = []

    @staticmethod
    def default_path() -> Path:
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "display-switch" / "groups.json"

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.groups = []
            return
        except (OSError, ValueError):
            self._backup_corrupt()
            self.groups = []
            return
        self.groups = _parse_groups(raw)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "groups": [{"name": g.name, "monitor_ids": g.monitor_ids} for g in self.groups],
        }
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, name: str) -> Group | None:
        for group in self.groups:
            if group.name == name:
                return group
        return None

    def add(self, name: str) -> Group:
        name = name.strip()
        if not name:
            raise ValueError("Group name cannot be empty.")
        if self.get(name) is not None:
            raise ValueError(f"A group named '{name}' already exists.")
        group = Group(name=name)
        self.groups.append(group)
        return group

    def rename(self, old: str, new: str) -> None:
        new = new.strip()
        group = self._require(old)
        if not new:
            raise ValueError("Group name cannot be empty.")
        if new != old and self.get(new) is not None:
            raise ValueError(f"A group named '{new}' already exists.")
        group.name = new

    def delete(self, name: str) -> None:
        self.groups.remove(self._require(name))

    def set_members(self, name: str, monitor_ids: list[str]) -> None:
        self._require(name).monitor_ids = list(dict.fromkeys(monitor_ids))

    def _require(self, name: str) -> Group:
        group = self.get(name)
        if group is None:
            raise KeyError(name)
        return group

    def _backup_corrupt(self) -> None:
        try:
            self.path.replace(self.path.with_name(self.path.name + ".corrupt"))
        except OSError:
            pass
