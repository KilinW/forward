"""Persistent state management for SSH port forwards."""

from __future__ import annotations

import json
from pathlib import Path

from .models import Forward

STATE_DIR = Path.home() / ".local" / "state" / "forward"
STATE_FILE = STATE_DIR / "forwards.json"
STATE_VERSION = 1


class StateManager:
    """Reads and writes the forwards.json state file."""

    def load(self) -> list[Forward]:
        if not STATE_FILE.exists():
            return []
        try:
            data = json.loads(STATE_FILE.read_text())
            return [Forward.from_dict(f) for f in data.get("forwards", [])]
        except (json.JSONDecodeError, KeyError):
            return []

    def save(self, forwards: list[Forward]) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(
            json.dumps(
                {"version": STATE_VERSION, "forwards": [f.to_dict() for f in forwards]},
                indent=2,
            )
        )

    def add(self, fwd: Forward) -> None:
        forwards = self.load()
        forwards.append(fwd)
        self.save(forwards)

    def remove(self, fwd_id: str) -> None:
        self.save([f for f in self.load() if f.id != fwd_id])
