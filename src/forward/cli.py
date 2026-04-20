"""
forward — SSH port forward manager

Commands:
  forward list
  forward add <host> <port> [--tag TAG] [--local-port PORT]
  forward remove <id|tag>
  forward completions install
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from forward.core.ssh import kill_forward, parse_ssh_hosts, start_forward
from forward.core.state import StateManager, STATE_FILE

# ── Bash completion script ─────────────────────────────────────────────────────
# Installed to ~/.local/share/bash-completion/completions/forward
# Sourced automatically by bash-completion 2.x — no .bashrc changes needed.

_BASH_COMPLETION = """\
_forward() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local command="${COMP_WORDS[1]}"

    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=($(compgen -W "list add remove completions" -- "$cur"))
        return
    fi

    case "$command" in
        add)
            # Complete SSH hosts from ~/.ssh/config
            if [[ $COMP_CWORD -eq 2 ]]; then
                local hosts
                hosts=$(grep -iE "^[[:space:]]*Host[[:space:]]+" ~/.ssh/config 2>/dev/null \\
                        | awk '{print $2}' | grep -v '[*?]')
                COMPREPLY=($(compgen -W "$hosts" -- "$cur"))
            fi
            ;;
        remove)
            # Complete ID prefixes and tags from the state file
            if [[ $COMP_CWORD -eq 2 ]]; then
                local state_file="$HOME/.local/state/forward/forwards.json"
                local words=""
                if [[ -f "$state_file" ]]; then
                    local ids tags
                    ids=$(grep '"id"' "$state_file" | awk -F'"' '{print substr($4,1,8)}')
                    tags=$(grep '"tag"' "$state_file" | awk -F'"' '{print $4}' | grep -v '^$')
                    words="$ids $tags"
                fi
                COMPREPLY=($(compgen -W "$words" -- "$cur"))
            fi
            ;;
        completions)
            if [[ $COMP_CWORD -eq 2 ]]; then
                COMPREPLY=($(compgen -W "install" -- "$cur"))
            fi
            ;;
    esac
}

complete -F _forward forward
complete -F _forward pf
"""

_COMPLETION_INSTALL_PATH = (
    Path.home() / ".local" / "share" / "bash-completion" / "completions" / "forward"
)


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_list(state: StateManager) -> None:
    forwards = state.load()
    if not forwards:
        print("No forwards.")
        return

    col = "{:<10}  {:<20}  {:<16}  {:>6}  {:>6}  {:<8}  {}"
    header = col.format("ID", "Tag", "Host", "Remote", "Local", "Status", "PID")
    print(header)
    print("─" * len(header))
    for fwd in forwards:
        st = fwd.status
        print(col.format(
            fwd.id[:8],
            fwd.tag or "—",
            fwd.host,
            fwd.remote_port,
            fwd.local_port,
            st.upper(),
            str(fwd.pid) if st == "running" else "—",
        ))


def cmd_add(
    state: StateManager,
    host: str,
    port: int,
    tag: str,
    local_port: int | None,
) -> None:
    print(f"Forwarding {host}:{port} → localhost...")
    try:
        fwd = start_forward(host, port, tag=tag, local_port=local_port, state=state)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"  ✓ localhost:{fwd.local_port} → {host}:{port}  (pid {fwd.pid})")
    if fwd.tag:
        print(f"  tag: {fwd.tag}")
    print(f"  id:  {fwd.id[:8]}")


def cmd_remove(state: StateManager, id_or_tag: str) -> None:
    forwards = state.load()
    matches = [
        f for f in forwards
        if f.id.startswith(id_or_tag) or f.tag == id_or_tag
    ]

    if not matches:
        print(f"No forward matching '{id_or_tag}'.", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print(f"Ambiguous: '{id_or_tag}' matches {len(matches)} forwards.", file=sys.stderr)
        for f in matches:
            print(f"  {f.id[:8]}  {f.tag or '—'}  {f.host}:{f.remote_port}")
        sys.exit(1)

    fwd = matches[0]
    kill_forward(fwd)
    print(f"Killed pid {fwd.pid}.")
    state.remove(fwd.id)
    label = fwd.tag or f"{fwd.host}:{fwd.remote_port}"
    print(f"Removed '{label}'.")


def cmd_completions_install() -> None:
    _COMPLETION_INSTALL_PATH.parent.mkdir(parents=True, exist_ok=True)
    _COMPLETION_INSTALL_PATH.write_text(_BASH_COMPLETION)
    print(f"Installed: {_COMPLETION_INSTALL_PATH}")
    print("Restart your shell or run: source ~/.local/share/bash-completion/completions/forward")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="forward",
        description="SSH port forward manager",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all forwards and their status")

    add_p = sub.add_parser("add", help="Create a new SSH port forward")
    add_p.add_argument("host", help="SSH host (from ~/.ssh/config)")
    add_p.add_argument("port", type=int, help="Remote port to forward")
    add_p.add_argument("--tag", default="", metavar="TAG", help="Optional label")
    add_p.add_argument("--local-port", type=int, default=None, metavar="PORT",
                       help="Local port (default: same as remote)")

    rm_p = sub.add_parser("remove", help="Kill and remove a forward")
    rm_p.add_argument("id_or_tag", metavar="ID|TAG",
                      help="ID prefix or tag of the forward to remove")

    comp_p = sub.add_parser("completions", help="Shell completion helpers")
    comp_p.add_argument("action", choices=["install"], help="Install the completion script")

    args = parser.parse_args()
    state = StateManager()

    if args.command == "list":
        cmd_list(state)
    elif args.command == "add":
        cmd_add(state, args.host, args.port, args.tag, args.local_port)
    elif args.command == "remove":
        cmd_remove(state, args.id_or_tag)
    elif args.command == "completions":
        cmd_completions_install()
