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
    "name: smoke\nrouting: ospf\nnodes:\n"
    "  - {name: R1, model: 2911, interfaces: [{port: GigabitEthernet0/0, ip: 10.0.0.1/30},"
    " {port: GigabitEthernet0/1, ip: 192.168.1.1/24}]}\n"
    "  - {name: R2, model: 2911, interfaces: [{port: GigabitEthernet0/0, ip: 10.0.0.2/30},"
    " {port: GigabitEthernet0/1, ip: 192.168.2.1/24}]}\n"
    "  - {name: SW1, model: 2960-24TT}\n"
    "  - {name: PC1, model: PC-PT, ip: 192.168.1.10/24, gateway: 192.168.1.1}\n"
    "links:\n"
    "  - {a: R1, a_port: GigabitEthernet0/0, b: R2, b_port: GigabitEthernet0/0}\n"
    "  - {a: R1, a_port: GigabitEthernet0/1, b: SW1, b_port: GigabitEthernet0/1}\n"
    "  - {a: PC1, a_port: FastEthernet0, b: SW1, b_port: FastEthernet0/1}\n"
)
EXPECTED = {
    "pt_schema",
    "pt_list_models",
    "pt_plan",
    "pt_preview",
    "pt_build",
    "pt_new",
    "pt_devices",
    "pt_add_device",
    "pt_add_link",
    "pt_config",
    "pt_set_host",
    "pt_set_dhcp",
    "pt_set_wireless",
    "pt_set_config_register",
    "pt_set_os",
    "pt_install_module",
    "pt_remove_device",
    "pt_inspect",
    "pt_rename_device",
    "pt_move_device",
    "pt_set_power",
    "pt_clone_device",
    "pt_set_service",
    "pt_add_dhcp_pool",
    "pt_add_dns_record",
    "pt_add_aaa_user",
    "pt_add_aaa_client",
    "pt_add_acl",
    "pt_apply_acl",
    "pt_nat_static",
    "pt_nat_overload",
    "pt_nat_interface",
    "pt_activity",
    "pt_harvest",
}


def _text(result) -> str:
    return "".join(getattr(block, "text", "") for block in result.content)


def _flag(result, name: str) -> bool:
    return bool(getattr(result, name, getattr(result, name.replace("isError", "is_error"), False)))


async def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PTLAB_OUT_DIR"] = os.environ.get("PTLAB_OUT_DIR", "/mnt/d/PT-Labs")
    env["PTLAB_LIB"] = os.environ.get("PTLAB_LIB", str(Path(env["PTLAB_OUT_DIR"]) / "lib.json"))
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
                ("pt_new", {"name": "mcp_smoke_lab"}),
                ("pt_add_device", {"path": "mcp_smoke_lab", "model": "2911", "name": "R1"}),
                ("pt_add_device", {"path": "mcp_smoke_lab", "model": "Server-PT", "name": "SRV1"}),
                (
                    "pt_add_link",
                    {
                        "path": "mcp_smoke_lab",
                        "a": "R1",
                        "a_port": "GigabitEthernet0/0",
                        "b": "SRV1",
                        "b_port": "FastEthernet0",
                    },
                ),
                ("pt_set_service", {"path": "mcp_smoke_lab", "device": "SRV1", "service": "http"}),
                (
                    "pt_add_dhcp_pool",
                    {
                        "path": "mcp_smoke_lab",
                        "device": "SRV1",
                        "network": "192.168.1.0/24",
                        "gateway": "192.168.1.1",
                    },
                ),
                (
                    "pt_add_acl",
                    {
                        "path": "mcp_smoke_lab",
                        "device": "R1",
                        "acl": "100",
                        "rules": ["permit ip any any"],
                    },
                ),
                (
                    "pt_apply_acl",
                    {
                        "path": "mcp_smoke_lab",
                        "device": "R1",
                        "port": "GigabitEthernet0/0",
                        "acl": "100",
                    },
                ),
                (
                    "pt_clone_device",
                    {"path": "mcp_smoke_lab", "source": "R1", "name": "R2", "x": 300, "y": 150},
                ),
                ("pt_rename_device", {"path": "mcp_smoke_lab", "device": "R2", "new_name": "R-BORDE"}),
                ("pt_set_power", {"path": "mcp_smoke_lab", "device": "R-BORDE", "on": False}),
                ("pt_harvest", {"source": "mcp_smoke_lab"}),
                (
                    "pt_activity",
                    {
                        "initial": "mcp_smoke_lab",
                        "answer": "mcp_smoke_lab",
                        "name": "mcp_smoke_act",
                        "instructions": ["<p>Smoke</p>"],
                    },
                ),
                ("pt_inspect", {"path": "mcp_smoke_lab"}),
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
