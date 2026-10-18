"""Servidor MCP de ptlab: expone el generador de topologias a cualquier agente LLM.

El agente (Command Code, Claude, Copilot...) es el "cerebro": planifica la topologia y
llama a estas tools. La salida por defecto va a PTLAB_OUT_DIR (por defecto /mnt/d/PT-Labs).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ptlab.builder import build
from ptlab.catalog import MODELS
from ptlab.planner import Plan, plan
from ptlab.preview import render_svg
from ptlab.spec import parse_spec, spec_json_schema

OUT_DIR = Path(os.environ.get("PTLAB_OUT_DIR", "/mnt/d/PT-Labs"))

mcp = MCPServer("ptlab")


def _summary(planned: Plan) -> str:
    lines = [f"Topologia: {planned.name}", "Equipos:"]
    for d in planned.devices:
        extra = d.host_ip[0] if d.host_ip else ("DHCP" if d.dhcp else "")
        lines.append(f"  - {d.name} ({d.model}) {extra}".rstrip())
        if d.service_pools:
            pools = ", ".join(f"{p.name} ({p.network})" for p in d.service_pools)
            lines.append(f"      pools DHCP: {pools}")
    lines.append("Enlaces:")
    for link in planned.links:
        lines.append(f"  - {link.a}:{link.a_port} <-> {link.b}:{link.b_port}")
    return "\n".join(lines)


@mcp.tool()
def pt_schema() -> str:
    """Devuelve el JSON schema de la spec de topologia (que campos acepta)."""
    return json.dumps(spec_json_schema(), indent=2, ensure_ascii=False)


@mcp.tool()
def pt_list_models() -> str:
    """Lista los modelos de equipos soportados, su rol y cantidad de puertos."""
    return "\n".join(f"- {m.name} ({m.role}) puertos={len(m.ports)}" for m in MODELS.values())


@mcp.tool()
def pt_plan(spec: str) -> str:
    """Valida y planifica una topologia desde una spec (JSON o YAML) y devuelve el resumen."""
    return _summary(plan(parse_spec(spec)))


@mcp.tool()
def pt_preview(spec: str, name: str = "preview") -> str:
    """Genera el preview SVG de la topologia y devuelve la ruta del archivo."""
    out = OUT_DIR / f"{name}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_svg(plan(parse_spec(spec))), encoding="utf-8")
    return f"preview: {out}"


@mcp.tool()
def pt_build(spec: str, name: str = "lab") -> str:
    """Genera el .pkt de la topologia y devuelve la ruta para abrir en Packet Tracer."""
    planned = plan(parse_spec(spec))
    out = build(planned, OUT_DIR / f"{name}.pkt")
    return f"generado: {out}\n{_summary(planned)}"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
