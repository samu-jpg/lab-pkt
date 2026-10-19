# Contributing

Issues and pull requests are welcome. The project reuses a GPL-3.0 codec
(`packet-tracer-pkt-format`) as a git submodule, so the whole project is GPL-3.0-or-later.

## Setup

```bash
git clone --recurse-submodules git@github.com:samu-jpg/lab-pkt.git
cd lab-pkt
pip install -e ".[mcp,dev]"
python -m pytest tests -q
python scripts/mcp_smoke.py   # starts the MCP server over stdio and exercises its tools
```

Set `PTLAB_OUT_DIR` (default `/mnt/d/PT-Labs`) to choose where generated `.pkt`/`.svg`/`.pka`
files go, and `PTLAB_LIB` (default `~/.ptlab/device_templates.json`) for the local template
library.

## Guidelines

- One test per new public function (see `tests/test_lab.py` for the primitives).
- No preset topologies and no exercise examples: the spec is explicit and the MCP only exposes
  tools; whoever uses it decides devices, names and addressing.
- Messages in Spanish or English, imperative and to the point.
- `vendor/` is a third-party submodule: do not edit it here, changes belong upstream
  (`aacanadaa/packet-tracer-pkt-format`).
