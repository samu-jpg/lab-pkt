"""Servidor MCP de ptlab: expone las librerias de Packet Tracer a cualquier agente LLM.

Dos familias de tools:
- spec -> .pkt/.svg: `pt_schema`, `pt_list_models`, `pt_plan`, `pt_preview`, `pt_build`.
- primitivas sobre un .pkt: `pt_new`, `pt_devices`, `pt_add_device`, `pt_remove_device`,
  `pt_clone_device`, `pt_rename_device`, `pt_move_device`, `pt_set_power`, `pt_add_link`,
  `pt_config`, `pt_set_host`, `pt_set_dhcp`, `pt_set_wireless`, `pt_set_config_register`,
  `pt_set_os`, `pt_install_module`, `pt_inspect`.
- servicios y seguridad: `pt_set_service`, `pt_add_dhcp_pool`, `pt_add_dns_record`,
  `pt_add_aaa_user`, `pt_add_aaa_client`, `pt_add_acl`, `pt_apply_acl`, `pt_nat_static`,
  `pt_nat_overload`, `pt_nat_interface`.

No hay plantillas de topologia: el agente decide equipos, nombres, cables y configs.
Las salidas por defecto van a PTLAB_OUT_DIR (por defecto /mnt/d/PT-Labs).
"""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ptlab import lab as labfile
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


def _lab_out(path: str) -> Path:
    """Resuelve el lab: nombre suelto -> PTLAB_OUT_DIR; ruta con carpetas -> tal cual."""
    p = Path(path).expanduser()
    if p.suffix != ".pkt":
        p = p.with_suffix(".pkt")
    if p.is_absolute() or p.parent != Path("."):
        return p
    return OUT_DIR / p


def _prefix(mask: str | None) -> str:
    if not mask:
        return "?"
    try:
        return str(ipaddress.ip_network(f"0.0.0.0/{mask}").prefixlen)
    except ValueError:
        return mask


def _inspect_text(data: dict) -> str:
    lines = [f"lab: {data['path']}"]
    lines.append(f"Equipos ({len(data['devices'])}):")
    for d in data["devices"]:
        head = f"- {d['name']} ({d['model']})"
        if d.get("x") is not None:
            head += f" x={d['x']} y={d['y']}"
        if d.get("power") is False:
            head += " [apagado]"
        lines.append(head)
        if d.get("ip"):
            lines.append(f"    ip {d['ip']}/{_prefix(d.get('mask'))} gw {d.get('gateway', '-')}")
        if d.get("dhcp"):
            lines.append("    dhcp: true")
        if d.get("ssid"):
            lines.append(f"    ssid: {', '.join(d['ssid'])}")
        for pool in d.get("dhcp_pools", []):
            lines.append(
                f"    pool {pool['name']}: {pool['network']} {pool['mask']} "
                f"gw {pool['gateway']} desde {pool['start_ip']}"
            )
        cfg = d.get("config") or []
        if cfg:
            lines.append(f"    config ({len(cfg)} lineas):")
            lines.extend(f"      {line}" for line in cfg)
    lines.append(f"Enlaces ({len(data['links'])}):")
    for link in data["links"]:
        extra = f" dce={link['dce']}" if link.get("dce") else ""
        lines.append(f"- {link['a']}:{link['a_port']} <-> {link['b']}:{link['b_port']} ({link['kind']}{extra})")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  Spec -> .pkt / .svg
# --------------------------------------------------------------------------- #


@mcp.tool()
def pt_schema() -> str:
    """Devuelve el JSON schema de la spec de topologia (que campos acepta)."""
    return json.dumps(spec_json_schema(), indent=2, ensure_ascii=False)


@mcp.tool()
def pt_list_models() -> str:
    """Modelos y modulos disponibles: catalogo de la spec y catalogo completo del vendor."""
    spec_lines = [f"- {m.name} ({m.role}) puertos={len(m.ports)}" for m in MODELS.values()]
    full = labfile.models()
    return "\n".join(
        [
            f"Catalogo de la spec (pt_plan/pt_build) — {len(spec_lines)}:",
            *spec_lines,
            "",
            f"Modelos del vendor (pt_add_device) — {len(full['models'])}:",
            *[f"- {m['model']} puertos={m['ports']}" for m in full["models"]],
            "",
            f"Modulos (pt_install_module) — {len(full['modules'])}:",
            *[f"- {m}" for m in full["modules"]],
        ]
    )


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


# --------------------------------------------------------------------------- #
#  Primitivas sobre un .pkt (sin plantillas: lo decide el agente)
# --------------------------------------------------------------------------- #


@mcp.tool()
def pt_new(name: str = "lab") -> str:
    """Crea un .pkt vacio (sin equipos) para armarlo con pt_add_device/pt_add_link."""
    out = labfile.new(_lab_out(name))
    return f"creado: {out}"


@mcp.tool()
def pt_devices(path: str) -> str:
    """Equipos del lab: nombre, modelo y posicion."""
    out = _lab_out(path)
    rows = labfile.devices(out)
    if not rows:
        return f"{out}: sin equipos (usa pt_add_device)"
    return "\n".join(f"- {r['name']} ({r['model']}) x={r['x']} y={r['y']}" for r in rows)


@mcp.tool()
def pt_add_device(
    path: str,
    model: str,
    name: str,
    x: int = 100,
    y: int = 100,
    power: bool = True,
    config: list[str] | None = None,
    host_ip: str = "",
    host_gateway: str = "",
    dhcp: bool = False,
    install: str = "",
    bay: int = 0,
    on_conflict: str = "raise",
) -> str:
    """Agrega un equipo (cualquier modelo de pt_list_models) con config y red opcionales.

    - `config`: lineas IOS del equipo (RUNNINGCONFIG), una por linea.
    - `host_ip` (CIDR) + `host_gateway`: red estatica del host; `dhcp: true` para DHCP.
    - `install`/`bay`: modulo (ej. HWIC-2T) a instalar; `on_conflict`: raise|suffix.
    """
    out = _lab_out(path)
    labfile.add_device(
        out,
        model=model,
        name=name,
        x=x,
        y=y,
        power=power,
        config=config,
        host_ip=host_ip,
        host_gateway=host_gateway,
        install=install or None,
        bay=bay,
        on_conflict=on_conflict,
    )
    if dhcp:
        labfile.set_dhcp(out, name, True)
    return f"agregado: {name} ({model})\nequipos: {', '.join(labfile.device_names(out))}"


@mcp.tool()
def pt_add_link(
    path: str,
    a: str,
    a_port: str,
    b: str,
    b_port: str,
    kind: str = "copper",
    dce: str = "",
    clock: int = 128000,
) -> str:
    """Cablea dos equipos (copper | crossover | serial; `dce` lleva el clock rate)."""
    labfile.add_link(_lab_out(path), a, a_port, b, b_port, kind=kind, dce=dce or None, clock=clock)
    return f"enlace: {a}:{a_port} <-> {b}:{b_port} ({kind})"


@mcp.tool()
def pt_config(path: str, device: str, lines: list[str]) -> str:
    """Agrega lineas IOS crudas al equipo (escape hatch total; se aplican al abrir)."""
    labfile.append_config(_lab_out(path), device, lines)
    return f"{device}: +{len(lines)} lineas IOS"


@mcp.tool()
def pt_set_host(path: str, device: str, ip: str, gateway: str = "") -> str:
    """IP estatica (CIDR) y gateway en el puerto del host."""
    labfile.set_host(_lab_out(path), device, ip, gateway)
    return f"{device}: {ip}" + (f" gw {gateway}" if gateway else "")


@mcp.tool()
def pt_set_dhcp(path: str, device: str, enable: bool = True) -> str:
    """Prende/apaga DHCP en el puerto del host."""
    labfile.set_dhcp(_lab_out(path), device, enable)
    return f"{device}: dhcp {'on' if enable else 'off'}"


@mcp.tool()
def pt_set_wireless(
    path: str,
    device: str,
    ssid: str = "",
    password: str = "",
    channel: str = "",
    auth_type: str = "",
    encrypt_type: str = "",
    radio_band: str = "",
) -> str:
    """SSID/seguridad/canal en los puertos inalambricos (AP, laptop, router)."""
    labfile.set_wireless(
        _lab_out(path),
        device,
        ssid=ssid,
        password=password,
        channel=channel,
        auth_type=auth_type,
        encrypt_type=encrypt_type,
        radio_band=radio_band,
    )
    extra = f" (canal {channel})" if channel else ""
    return f"{device}: ssid {ssid!r}{extra}"


@mcp.tool()
def pt_set_config_register(path: str, device: str, value: int) -> str:
    """Registro de configuracion del equipo (`CONFIG_REGISTER`, ej. 0x2142 = 8500)."""
    labfile.set_config_register(_lab_out(path), device, value)
    return f"{device}: config-register {value}"


@mcp.tool()
def pt_set_os(path: str, device: str, image: str = "", file_name: str = "") -> str:
    """Imagen / archivo de boot del equipo (`OS_IMAGE`, `OS_FILE_NAME`)."""
    labfile.set_os(_lab_out(path), device, image=image, file_name=file_name)
    return f"{device}: os {image or file_name}"


@mcp.tool()
def pt_install_module(path: str, device: str, module: str, bay: int = 0) -> str:
    """Instala un modulo (ej. HWIC-2T) en el bay de tarjeta indicado."""
    labfile.install_module(_lab_out(path), device, module, bay)
    return f"{device}: modulo {module} en bay {bay}"


@mcp.tool()
def pt_remove_device(path: str, device: str) -> str:
    """Quita un equipo (con sus cables y su lugar en el rack fisico)."""
    out = _lab_out(path)
    labfile.remove_device(out, device)
    return f"quitado: {device}\nequipos: {', '.join(labfile.device_names(out)) or 'ninguno'}"


@mcp.tool()
def pt_inspect(path: str) -> str:
    """Lee un .pkt: equipos (modelo, IP, config, pools, wireless) y enlaces."""
    return _inspect_text(labfile.inspect(_lab_out(path)))


# --------------------------------------------------------------------------- #
#  Edicion de equipos, servicios, ACL/NAT
# --------------------------------------------------------------------------- #


@mcp.tool()
def pt_rename_device(path: str, device: str, new_name: str) -> str:
    """Renombra un equipo (los cables no se tocan: referencian un id interno)."""
    labfile.rename_device(_lab_out(path), device, new_name)
    return f"{device} -> {new_name}"


@mcp.tool()
def pt_move_device(path: str, device: str, x: int, y: int) -> str:
    """Mueve un equipo en el plano logico."""
    labfile.move_device(_lab_out(path), device, x, y)
    return f"{device}: x={x} y={y}"


@mcp.tool()
def pt_set_power(path: str, device: str, on: bool = True) -> str:
    """Prende/apaga un equipo (apagado, sus puertos quedan abajo)."""
    labfile.set_power(_lab_out(path), device, on)
    return f"{device}: {'on' if on else 'off'}"


@mcp.tool()
def pt_clone_device(path: str, source: str, name: str, x: int = -1, y: int = -1) -> str:
    """Duplica un equipo (config incluida) con nombre nuevo; sin x/y queda al lado del original."""
    out = _lab_out(path)
    labfile.clone_device(out, source, name, x=None if x < 0 else x, y=None if y < 0 else y)
    return f"clonado: {source} -> {name}\nequipos: {', '.join(labfile.device_names(out))}"


@mcp.tool()
def pt_set_service(
    path: str,
    device: str,
    service: str,
    enable: bool = True,
    fields: dict[str, str] | None = None,
) -> str:
    """Prende/apaga y configura un servicio del equipo.

    service: http | https | dns | tftp | ntp | syslog | email | aaa | dhcp.
    `fields` pisa etiquetas crudas: {"username": "admin", "password": "x"}, {"domain": "lab.local"}.
    """
    labfile.set_service(_lab_out(path), device, service, enable=enable, fields=fields)
    return f"{device}: servicio {service} {'on' if enable else 'off'}"


@mcp.tool()
def pt_add_dhcp_pool(
    path: str,
    device: str,
    network: str,
    gateway: str,
    mask: str = "",
    dns: str = "",
    start_ip: str = "",
    name: str = "",
    max_users: int = 0,
) -> str:
    """Agrega un pool al servicio DHCP del equipo (la primera llamada llena el pool vacio)."""
    labfile.add_dhcp_pool(
        _lab_out(path), device, network, gateway, mask=mask, dns=dns, start_ip=start_ip, name=name,
        max_users=max_users,
    )
    return f"{device}: pool {network} gw {gateway}"


@mcp.tool()
def pt_add_dns_record(
    path: str,
    device: str,
    name: str,
    address: str,
    ttl: int = 86400,
    record_type: str = "A-REC",
) -> str:
    """Agrega un registro al servicio DNS del equipo."""
    labfile.add_dns_record(_lab_out(path), device, name, address, ttl=ttl, record_type=record_type)
    return f"{device}: {name} -> {address}"


@mcp.tool()
def pt_add_aaa_user(path: str, device: str, username: str, password: str, description: str = "") -> str:
    """Agrega un usuario al servidor AAA (ACS)."""
    labfile.add_aaa_user(_lab_out(path), device, username, password, description)
    return f"{device}: usuario {username}"


@mcp.tool()
def pt_add_aaa_client(
    path: str,
    device: str,
    host_ip: str,
    key: str,
    description: str = "",
    server_type: str = "RADIUS",
) -> str:
    """Registra un cliente AAA (ej. el router que autentica contra RADIUS)."""
    labfile.add_aaa_client(
        _lab_out(path), device, host_ip, key, description=description, server_type=server_type
    )
    return f"{device}: cliente {host_ip} ({server_type})"


@mcp.tool()
def pt_add_acl(path: str, device: str, acl: str, rules: list[str], kind: str = "extended") -> str:
    """Agrega una ACL al equipo: numerada (1-99/100-199/1300-1999/2000-2699) o con nombre."""
    labfile.add_acl(_lab_out(path), device, acl, rules, kind)
    return f"{device}: ACL {acl} ({kind}, {len(rules)} reglas)"


@mcp.tool()
def pt_apply_acl(path: str, device: str, port: str, acl: str, direction: str = "in") -> str:
    """Aplica una ACL a una interfaz del equipo (`ip access-group`)."""
    labfile.apply_acl(_lab_out(path), device, port, acl, direction)
    return f"{device}: {port} access-group {acl} {direction}"


@mcp.tool()
def pt_nat_static(path: str, device: str, inside_ip: str, outside_ip: str) -> str:
    """NAT estatico uno a uno en el equipo."""
    labfile.nat_static(_lab_out(path), device, inside_ip, outside_ip)
    return f"{device}: nat static {inside_ip} -> {outside_ip}"


@mcp.tool()
def pt_nat_overload(path: str, device: str, acl: str, port: str) -> str:
    """PAT (overload) del equipo: ACL + interfaz de salida."""
    labfile.nat_overload(_lab_out(path), device, acl, port)
    return f"{device}: nat overload list {acl} via {port}"


@mcp.tool()
def pt_nat_interface(path: str, device: str, port: str, side: str = "inside") -> str:
    """Marca una interfaz del equipo como `ip nat inside` / `ip nat outside`."""
    labfile.nat_interface(_lab_out(path), device, port, side)
    return f"{device}: {port} nat {side}"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
