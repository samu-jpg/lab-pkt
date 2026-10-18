"""Generadores de configuracion IOS (texto que va en <RUNNINGCONFIG>)."""
from __future__ import annotations

Interface = tuple[str, str, str]  # (puerto, ip, mascara)
Route = tuple[str, str, str]  # (red, mascara, next_hop)
Pool = tuple[str, str, str, str]  # (nombre, red, mascara, gateway)
Net = tuple[str, str]  # (red, wildcard o mascara)
Vlan = tuple[int, str | None]  # (id, nombre)
SubInterface = tuple[str, int, str, str]  # (puerto base, vlan, ip, mascara)


def _header(hostname: str) -> list[str]:
    return ["!", f"hostname {hostname}", "!"]


def vlan_block(vlans: list[Vlan] | None) -> list[str]:
    """Declaracion de VLANs: `vlan 10` / ` name VENTAS`."""
    if not vlans:
        return []
    lines: list[str] = []
    for vid, name in vlans:
        lines.append(f"vlan {vid}")
        if name:
            lines.append(f" name {name}")
    lines.append("!")
    return lines


def static_routes(routes: list[Route]) -> list[str]:
    if not routes:
        return []
    return [f"ip route {net} {mask} {nexthop}" for net, mask, nexthop in routes] + ["!"]


def rip_config(networks: list[str]) -> list[str]:
    """RIPv2: `network` es classful, asi que se pasan redes mayores."""
    return [
        "router rip",
        " version 2",
        " no auto-summary",
        *[f" network {net}" for net in networks],
        "!",
    ]


def ospf_config(process: int, area: int, networks: list[Net]) -> list[str]:
    return [
        f"router ospf {process}",
        *[f" network {net} {wildcard} area {area}" for net, wildcard in networks],
        "!",
    ]


def eigrp_config(asn: int, networks: list[Net]) -> list[str]:
    return [
        f"router eigrp {asn}",
        " no auto-summary",
        *[f" network {net} {wildcard}" for net, wildcard in networks],
        "!",
    ]


def bgp_config(asn: int, peers: list[tuple[str, int]], networks: list[Net]) -> list[str]:
    """eBGP: un `neighbor` por router vecino (con su AS) y las LAN propias anunciadas."""
    return [
        f"router bgp {asn}",
        " no synchronization",
        " no auto-summary",
        *[f" neighbor {ip} remote-as {remote_as}" for ip, remote_as in peers],
        *[f" network {net} mask {mask}" for net, mask in networks],
        "!",
    ]


def router_config(
    hostname: str,
    interfaces: list[Interface],
    routing: list[str] | None = None,
    dhcp_pools: list[Pool] | None = None,
    l3_switch: bool = False,
    helpers: dict[str, str] | None = None,
    subinterfaces: list[SubInterface] | None = None,
    extra: list[str] | None = None,
) -> list[str]:
    """Config del equipo que rutea la sede.

    Con `l3_switch=True` el equipo es un switch L3 (ej. 3560-24PS) usado como router:
    hace falta `ip routing` y `no switchport` en cada puerto ruteado.
    `helpers` mapea puerto -> IP del servidor DHCP para el relay (`ip helper-address`).
    `subinterfaces` son subinterfaces dot1Q (router-on-a-stick): (puerto base, vlan, ip, mascara).
    `extra` agrega lineas IOS crudas del nodo (escape hatch del modo grafo).
    """
    lines = _header(hostname)
    if l3_switch:
        lines += ["ip routing", "!"]
    for port, ip, mask in interfaces:
        lines.append(f"interface {port}")
        if l3_switch:
            lines.append(" no switchport")
        if ip:
            lines.append(f" ip address {ip} {mask}")
        lines.append(" no shutdown")
        if helpers and port in helpers:
            lines.append(f" ip helper-address {helpers[port]}")
        lines.append("!")
    for base, vlan, ip, mask in subinterfaces or []:
        lines += [
            f"interface {base}.{vlan}",
            f" encapsulation dot1Q {vlan}",
            f" ip address {ip} {mask}",
            " no shutdown",
            "!",
        ]
    lines += list(routing or [])
    for name, net, mask, gw in dhcp_pools or []:
        lines += [f"ip dhcp pool {name}", f" network {net} {mask}", f" default-router {gw}", "!"]
    lines += list(extra or [])
    lines.append("end")
    return lines


def switch_config(
    hostname: str,
    vlan1_ip: str | None = None,
    vlan1_mask: str | None = None,
    vlans: list[Vlan] | None = None,
    access: list[tuple[str, int]] | None = None,
    trunks: list[str] | None = None,
    svis: list[tuple[int, str, str]] | None = None,
) -> list[str]:
    """Config de un switch L2 (modo grafo: VLANs, access, trunk y SVIs).

    `svis` son interfaces de gestion (`interface Vlan10` + ip): (vlan, ip, mascara).
    """
    lines = _header(hostname)
    lines += vlan_block(vlans)
    for port, vid in access or []:
        lines += [f"interface {port}", " switchport mode access", f" switchport access vlan {vid}", "!"]
    for port in trunks or []:
        lines += [f"interface {port}", " switchport mode trunk", "!"]
    lines.append("interface Vlan1")
    if vlan1_ip:
        lines.append(f" ip address {vlan1_ip} {vlan1_mask}")
    lines += [" no shutdown", "!"]
    for vid, ip, mask in svis or []:
        lines += [f"interface Vlan{vid}", f" ip address {ip} {mask}", " no shutdown", "!"]
    lines.append("end")
    return lines
