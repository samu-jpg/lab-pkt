"""Preview del Plan como el canvas de Packet Tracer (iconos reales de PT).

Usa los PNG del canvas logico de Packet Tracer (art/Workspace/Logical), incrustados en el
SVG como data-URI y deduplicados con <defs>/<use>. Si no encuentra el arte de PT, cae a
iconos esquematicos.

El nodo raiz lleva `data-stats` con el resumen del plan (equipos por tipo y enlaces), para
que la web lo muestre sin replanificar.
"""
from __future__ import annotations

import base64
import json
import os
import struct
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from ptlab.catalog import HOST, HUB, L3SWITCH, MODELS, ROUTER, SWITCH
from ptlab.planner import Plan

PT_ART = Path(os.environ.get("PTLAB_PT_ART", "/mnt/d/Cisco Packet Tracer 9.0.1/art/Workspace/Logical"))
_AGGREGATE_OVER = 4

_ICON_FILE = {
    "PC-PT": "iWorkstation@2x.png",
    "Server-PT": "iServer@2x.png",
    "Laptop-PT": "iLaptop@2x.png",
    "Hub-PT": "iHub@2x.png",
}
_FILE_FOR_ROLE = {
    ROUTER: "iRouter@2x.png",
    SWITCH: "iSwitch@2x.png",
    L3SWITCH: "iSwitch3560@2x.png",
    HOST: "iWorkstation@2x.png",
    HUB: "iHub@2x.png",
}


def _is_host(role: str) -> bool:
    return role not in (ROUTER, SWITCH, L3SWITCH, HUB)


@lru_cache(maxsize=None)
def _icon_asset(role: str, model: str) -> tuple[str, str, int, int] | None:
    """(id, data-uri, ancho, alto) del icono PT, o None si no esta disponible."""
    name = _ICON_FILE.get(model) or _FILE_FOR_ROLE.get(role)
    path = PT_ART / name if name else None
    if path is None or not path.exists():
        return None
    raw = path.read_bytes()
    uri = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    w, h = struct.unpack(">II", raw[16:24])
    return name.replace("@", "_").replace(".", "_"), uri, w, h


# --------------------------- iconos esquematicos (fallback) --------------------------- #
_FAKE_COLORS = {ROUTER: "#1e59a5", SWITCH: "#2e7d32", L3SWITCH: "#00695c", HOST: "#6a1b9a", HUB: "#546e7a"}


def _fallback_icon(role: str, model: str, x: float, y: float) -> str:
    color = _FAKE_COLORS.get(role, "#455a64")
    if role in (ROUTER, SWITCH, L3SWITCH):
        w, h = 78, 46
    else:
        w, h = 56, 44
    return (
        f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w}" height="{h}" rx="9" '
        f'fill="{color}" stroke="#0b0f14"/>'
    )


def plan_stats(plan: Plan) -> dict[str, int]:
    """Equipos por tipo (segun el rol del modelo, sirven nombres arbitrarios) y enlaces."""
    stats = {"routers": 0, "switches": 0, "hubs": 0, "hosts": 0, "links": len(plan.links)}
    for d in plan.devices:
        if d.role in (ROUTER, L3SWITCH):
            stats["routers"] += 1
        elif d.role == SWITCH:
            stats["switches"] += 1
        elif d.role == HUB:
            stats["hubs"] += 1
        else:
            stats["hosts"] += 1
    return stats


def icon_data_uris() -> dict[str, str]:
    """Iconos PT por modelo (data-URI PNG), para el canvas del editor web."""
    out: dict[str, str] = {}
    for model in MODELS.values():
        asset = _icon_asset(model.role, model.name)
        if asset:
            out[model.name] = asset[1]
    return out


def render_svg(plan: Plan, aggregate_over: int = _AGGREGATE_OVER) -> str:
    byname = {d.name: d for d in plan.devices}

    switch_hosts: dict[str, list[str]] = defaultdict(list)
    attached: set[str] = set()
    for link in plan.links:
        for dev_name, host_name in ((link.a, link.b), (link.b, link.a)):
            if dev_name in byname and host_name in byname:
                if not _is_host(byname[dev_name].role) and _is_host(byname[host_name].role):
                    switch_hosts[dev_name].append(host_name)
                    attached.add(host_name)

    rep: dict[str, str] = {}
    grouped: dict[str, int] = {}
    for hosts in switch_hosts.values():
        if len(hosts) > aggregate_over:
            rep[hosts[0]] = hosts[0]
            grouped[hosts[0]] = len(hosts)
        else:
            for h in hosts:
                rep[h] = h

    drawn: set[str] = set()
    for d in plan.devices:
        if _is_host(d.role):
            if d.name in rep:
                drawn.add(rep[d.name])
            elif d.name not in attached:
                drawn.add(d.name)
        else:
            drawn.add(d.name)

    pos = {n: (byname[n].x, byname[n].y) for n in drawn}
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    pad = 130
    min_x, max_x = min(xs) - pad, max(xs) + pad
    min_y, max_y = min(ys) - pad, max(ys) + pad
    w, h = max_x - min_x, max_y - min_y

    # iconos usados -> definiciones (dedupe)
    assets: dict[str, tuple[str, int, int]] = {}
    for name in pos:
        d = byname[name]
        asset = _icon_asset(d.role, d.model)
        if asset:
            key, uri, iw, ih = asset
            assets.setdefault(key, (uri, iw, ih))

    stats = json.dumps(plan_stats(plan), separators=(",", ":"))
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" data-stats=\'{stats}\' '
        f'viewBox="{min_x:.0f} {min_y:.0f} {w:.0f} {h:.0f}" '
        f'width="{w:.0f}" height="{h:.0f}" font-family="system-ui, sans-serif">',
        "<defs>",
        '<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">',
        '<path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e3e7ea" stroke-width="1"/>',
        "</pattern>",
    ]
    for key, (uri, iw, ih) in assets.items():
        out.append(f'<image id="ic-{key}" href="{uri}" width="{iw}" height="{ih}"/>')
    out += [
        "</defs>",
        f'<rect x="{min_x:.0f}" y="{min_y:.0f}" width="{w:.0f}" height="{h:.0f}" fill="#f7f9fb"/>',
        f'<rect x="{min_x:.0f}" y="{min_y:.0f}" width="{w:.0f}" height="{h:.0f}" fill="url(#grid)"/>',
    ]

    for link in plan.links:
        ra, rb = rep.get(link.a, link.a), rep.get(link.b, link.b)
        if ra in pos and rb in pos:
            x1, y1 = pos[ra]
            x2, y2 = pos[rb]
            out.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#4a5560" stroke-width="2"/>')

    for name in sorted(pos, key=lambda n: (pos[n][1], pos[n][0])):
        d = byname[name]
        x, y = pos[name]
        asset = _icon_asset(d.role, d.model)
        if asset:
            key, _uri, iw, ih = asset
            out.append(f'<use href="#ic-{key}" x="{x - iw / 2:.0f}" y="{y - ih / 2:.0f}"/>')
            label_y = y + ih / 2 + 15
        else:
            out.append(_fallback_icon(d.role, d.model, x, y))
            label_y = y + 34
        if name in grouped:
            title, sub = f"x{grouped[name]} equipos", "hosts"
        else:
            title = d.name
            sub = d.host_ip[0] if d.host_ip else ("DHCP" if d.dhcp else "")
        out.append(f'<text x="{x:.0f}" y="{label_y:.0f}" text-anchor="middle" fill="#111820" font-size="12" font-weight="600">{title}</text>')
        if sub:
            out.append(f'<text x="{x:.0f}" y="{label_y + 13:.0f}" text-anchor="middle" fill="#5b6b7a" font-size="10">{sub}</text>')

    out.append("</svg>")
    return "\n".join(out)
