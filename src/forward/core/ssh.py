"""SSH operations: discover hosts, start/kill tunnels, find PIDs."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import Forward
from .state import StateManager

SSH_CONFIG = Path.home() / ".ssh" / "config"


def parse_ssh_hosts() -> list[str]:
    """Return non-wildcard Host entries from ~/.ssh/config."""
    if not SSH_CONFIG.exists():
        return []
    hosts: list[str] = []
    for line in SSH_CONFIG.read_text().splitlines():
        m = re.match(r"^\s*Host\s+(\S+)", line, re.IGNORECASE)
        if m:
            h = m.group(1)
            if "*" not in h and "?" not in h:
                hosts.append(h)
    return hosts


def is_port_free(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def find_free_local_port(starting: int, max_tries: int = 50) -> int | None:
    for i in range(max_tries):
        if is_port_free(starting + i):
            return starting + i
    return None


def find_ssh_pid(port: int) -> int | None:
    """Return the PID of the process listening on TCP port, or None."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
        )
        pids = result.stdout.strip().split()
        return int(pids[0]) if pids else None
    except (FileNotFoundError, ValueError):
        return None


def start_forward(
    host: str,
    remote_port: int,
    tag: str = "",
    local_port: int | None = None,
    *,
    state: StateManager,
) -> Forward:
    """
    Start an SSH tunnel and record it in the state file.

    Raises RuntimeError if no free port is found or SSH fails.
    """
    start = local_port if local_port else remote_port
    port = find_free_local_port(start)
    if port is None:
        raise RuntimeError(f"No free local port found starting from {start}")

    # Use a temp file for stderr instead of a pipe. With capture_output=True,
    # subprocess.run() uses communicate() which waits for pipe EOF. But ssh -f
    # forks a daemon child that inherits the pipe fd, so EOF never comes and
    # the call blocks forever. A regular file has no such problem — run() just
    # calls wait() on the parent PID, which exits promptly after forking.
    with tempfile.TemporaryFile() as stderr_f:
        result = subprocess.run(
            [
                "ssh",
                "-f",
                "-N",
                "-o",
                "ExitOnForwardFailure=yes",
                "-L",
                f"{port}:localhost:{remote_port}",
                host,
            ],
            stdout=subprocess.DEVNULL,
            stderr=stderr_f,
        )
        stderr_f.seek(0)
        stderr_text = stderr_f.read().decode(errors="replace").strip()

    if result.returncode != 0:
        raise RuntimeError(stderr_text or f"SSH failed (exit {result.returncode})")

    pid = find_ssh_pid(port)
    if pid is None:
        raise RuntimeError("Tunnel started but could not determine PID")

    fwd = Forward(
        id=str(uuid.uuid4()),
        tag=tag,
        host=host,
        remote_port=remote_port,
        local_port=port,
        pid=pid,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    state.add(fwd)
    return fwd


def kill_forward(fwd: Forward) -> None:
    """Send SIGTERM to the tunnel process, only if its PID matches the recorded PID."""
    if find_ssh_pid(fwd.local_port) != fwd.pid:
        return
    try:
        os.kill(fwd.pid, 15)
    except ProcessLookupError:
        pass
