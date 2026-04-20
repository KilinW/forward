# forward

SSH port forward manager.

## Install

```sh
uv tool install .
```

## Usage

```sh
forward add <host> <port> [--tag TAG] [--local-port PORT]
forward list
forward remove <id|tag>
```

## Shell completion

```sh
forward completions install
```

Installs a bash completion script to `~/.local/share/bash-completion/completions/forward`. Picked up automatically by bash-completion 2.x — no `.bashrc` changes needed.
