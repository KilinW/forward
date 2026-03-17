"""Data model for SSH port forwards."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

Status = Literal["running", "dead", "unknown"]


def pid_alive(pid: int) -> Status:
    """Check whether a process is alive via os.kill(pid, 0)."""
    try:
        os.kill(pid, 0)
        return "running"
    except ProcessLookupError:
        return "dead"
    except PermissionError:
        return "running"  # exists but not ours to signal
    except Exception:
        return "unknown"


@dataclass
class Forward:
    id: str
    host: str
    remote_port: int
    local_port: int
    pid: int
    created_at: str
    tag: str = ""

    @property
    def status(self) -> Status:
        return pid_alive(self.pid)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tag": self.tag,
            "host": self.host,
            "remote_port": self.remote_port,
            "local_port": self.local_port,
            "pid": self.pid,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Forward:
        return cls(
            id=d["id"],
            tag=d.get("tag", ""),
            host=d["host"],
            remote_port=d["remote_port"],
            local_port=d["local_port"],
            pid=d["pid"],
            created_at=d["created_at"],
        )
