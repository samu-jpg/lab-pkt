#!/usr/bin/env python3
"""Smoke test del servidor MCP: lo arranca por stdio y ejercita las tools."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcp import ClientSession, StdioServerParameters, stdio_client  # noqa: E402

SPEC = (
    "name: smoke\ntopology: ring\nsites:\n"
    "  - {name: S1, lan: 192.168.1.0/24, hosts: 1}\n"
    "  - {name: S2, lan: 192.168.2.0/24, hosts: 1}\n"
    "  - {name: S3, lan: 192.168.3.0/24, hosts: 1}\n"
)
EXPECTED = {"pt_schema", "pt_list_models", "pt_plan", "pt_preview", "pt_build"}


def _text(result) -> str:
    return "".join(getattr(block, "text", "") for block in result.content)


def _flag(result, name: str) -> bool:
    return bool(getattr(result, name, getattr(result, name.replace("isError", "is_error"), False)))


async def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PTLAB_OUT_DIR"] = os.environ.get("PTLAB_OUT_DIR", "/mnt/d/PT-Labs")
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "ptlab.mcp_server"], env=env, cwd=str(ROOT)
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            server = getattr(info, "serverInfo", None) or getattr(info, "server_info", None)
            print("server :", getattr(server, "name", "?"), "| protocol", getattr(info, "protocolVersion", "?"))

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            print("tools  :", sorted(names))
            missing = EXPECTED - names
            if missing:
                print("FALTAN:", missing)
                return 1

            calls = [
                ("pt_list_models", {}),
                ("pt_plan", {"spec": SPEC}),
                ("pt_build", {"spec": SPEC, "name": "mcp_smoke"}),
            ]
            for name, args in calls:
                result = await session.call_tool(name, args)
                head = _text(result).splitlines()[0] if _text(result) else ""
                print(f"[{name}] error={_flag(result, 'isError')} -> {head}")
                if _flag(result, "isError"):
                    return 1

    print("MCP OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
