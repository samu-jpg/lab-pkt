"""Convierte una Spec en un Plan (equipos, puertos, direccionamiento, configs, layout)."""
from __future__ import annotations

import ipaddress
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field

from ptlab import ios
from ptlab.catalog import (
    DEFAULT_SERVER,
    HOST,
    HUB,
    L3SWITCH,
    MODELS,
    ROUTER,
    SWITCH,
    access_ports,
    uplink_ports,
)
from ptlab.spec import LinkSpec, NodeSpec, Spec

SERVER_NAME = "DHCP-Server"


@dataclass
class ServicePool:
    """Pool del servicio DHCP de un Server-PT (no es config IOS, va en el XML del equipo)."""

    name: str
    network: str
    mask: str
    gateway: str
    start_ip: str
    max_users: int = 240
    dns: str = "8.8.8.8"


@dataclass
class PlannedDevice:
    name: str
    model: str
    role: str
    x: int = 0
    y: int = 0
    config: list[str] = field(default_factory=list)
    host_ip: tuple[str, str, str] | None = None
    dhcp: bool = False
    service_pools: list[ServicePool] = field(default_factory=list)


@dataclass
class PlannedLink:
    a: str
    a_port: str
    b: str
    b_port: str
    kind: str = "copper"  # "copper" | "crossover"


@dataclass
class Plan:
    name: str
    devices: list[PlannedDevice]
    links: list[PlannedLink]

    def device(self, name: str) -> PlannedDevice:
        for d in self.devices:
            if d.name == name:
                return d
        raise KeyError(name)


class _Ports:
    def __init__(self) -> None:
        self._used: dict[str, set[str]] = {}

    def take(self, device: str, candidates: list[str]) -> str:
        used = self._used.setdefault(device, set())
        for port in candidates:
            if port not in used:
                used.add(port)
                return port
        raise ValueError(f"{device}: sin puertos libres (candidatos: {candidates[:4]}...)")


def _router_edges(topology: str, n: int) -> list[tuple[int, int]]:
    if n <= 1:
        return []
    if topology == "line":
        return [(i, i + 1) for i in range(n - 1)]
    if topology == "ring":
        edges = [(i, i + 1) for i in range(n - 1)]
        if n > 2:
            edges.append((n - 1, 0))
        return edges
    if topology == "star":
        return [(0, j) for j in range(1, n)]
    if topology == "mesh":
        return [(i, j) for i in range(n) for j in range(i + 1, n)]
    if topology == "ladder":
        k = (n + 1) // 2
        a, b = list(range(k)), list(range(k, n))
        edges = [(a[i], a[i + 1]) for i in range(len(a) - 1)]
        edges += [(b[i], b[i + 1]) for i in range(len(b) - 1)]
        edges += [(a[i], b[i]) for i in range(min(len(a), len(b)))]
        return edges
    if topology == "tree":
        return [((i - 1) // 2, i) for i in range(1, n)]
    if topology == "grid":
        cols = math.ceil(math.sqrt(n))
        edges = []
        for i in range(n):
            _row, col = divmod(i, cols)
            if col + 1 < cols and i + 1 < n:
                edges.append((i, i + 1))
            if i + cols < n:
                edges.append((i, i + cols))
        return edges
    if topology == "dual_star":
        if n == 2:
            return [(0, 1)]
        return [(0, 1)] + [(0, j) for j in range(2, n)] + [(1, j) for j in range(2, n)]
    return [(i, i + 1) for i in range(n - 1)]


def _router_positions(topology: str, n: int) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    dirs = [(0.0, 1.0)] * n
    if n == 0:
        return [], []
    if topology in ("ring", "mesh", "star"):
        cx, cy = 760.0, 470.0
        radius = max(320.0, 340.0 * n / (2 * math.pi))
        if topology == "star":
            pos = [(cx, cy)]
            for i in range(1, n):
                ang = -math.pi / 2 + 2 * math.pi * (i - 1) / max(1, n - 1)
                pos.append((cx + radius * math.cos(ang), cy + radius * math.sin(ang)))
        else:
            pos = [
                (cx + radius * math.cos(-math.pi / 2 + 2 * math.pi * i / n),
                 cy + radius * math.sin(-math.pi / 2 + 2 * math.pi * i / n))
                for i in range(n)
            ]
        for i in range(n):
            dx, dy = pos[i][0] - cx, pos[i][1] - cy
            length = math.hypot(dx, dy) or 1.0
            dirs[i] = (dx / length, dy / length) if length > 1 else (0.0, 1.0)
        dirs[0] = (0.0, 1.0) if topology == "star" else dirs[0]
        return pos, dirs
    if topology == "ladder":
        k = (n + 1) // 2
        pos = []
        for i in range(n):
            row, col = (0, i) if i < k else (1, i - k)
            pos.append((320.0 * col + 220, 170.0 + 660.0 * row))
        return pos, dirs
    if topology == "tree":
        pos = []
        for i in range(n):
            level = (i + 1).bit_length() - 1
            idx = i + 1 - 2**level
            step = 1600.0 / 2**level
            pos.append(((idx + 0.5) * step - 40.0, 190.0 + level * 230.0))
        for i in range(n):
            if 2 * i + 1 < n:
                dirs[i] = (-1.0, 0.0) if pos[i][0] < 760.0 else (1.0, 0.0)
        return pos, dirs
    if topology == "grid":
        cols = math.ceil(math.sqrt(n))
        pos = []
        for i in range(n):
            row, col = divmod(i, cols)
            pos.append((460.0 * col + 320.0, 560.0 * row + 190.0))
        return pos, dirs
    if topology == "dual_star":
        pos = [(700.0, 470.0), (980.0, 470.0)]
        for k, i in enumerate(range(2, n)):
            side = -1.0 if k % 2 == 0 else 1.0
            pos.append((700.0 + side * 420.0, 250.0 + (k // 2) * 250.0))
            dirs[i] = (side, 0.0)
        dirs[0] = (0.0, -1.0)
        if n > 1:
            dirs[1] = (0.0, 1.0)
        return pos[:n], dirs
    return [(320.0 * i + 220, 170.0) for i in range(n)], dirs


def _first_hops(n: int, adj: dict[int, list[tuple[int, int]]]) -> dict[int, dict[int, int | None]]:
    result: dict[int, dict[int, int | None]] = {}
    for src in range(n):
        first: dict[int, int | None] = {src: None}
        queue = deque([src])
        while queue:
            u = queue.popleft()
            for v, _edge in adj[u]:
                if v not in first:
                    first[v] = v if u == src else first[u]
                    queue.append(v)
        result[src] = first
    return result


def _classful(ip: str) -> str:
    """Red mayor (classful) de una IP: RIP solo acepta `network` classful."""
    octets = ip.split(".")
    first = int(octets[0])
    if first < 128:
        return f"{octets[0]}.0.0.0"
    if first < 192:
        return f"{octets[0]}.{octets[1]}.0.0"
    return f"{octets[0]}.{octets[1]}.{octets[2]}.0"


def _connected_nets(interfaces: list[ios.Interface]) -> list[ios.Net]:
    """(red, wildcard) de cada interfaz, para OSPF/EIGRP."""
    nets: list[ios.Net] = []
    for _port, ip, mask in interfaces:
        net = ipaddress.ip_network(f"{ip}/{mask}", strict=False)
        nets.append((str(net.network_address), str(net.hostmask)))
    return nets


def _routing_lines(
    spec: Spec,
    idx: int,
    interfaces: list[ios.Interface],
    hops: dict[int, dict[int, int | None]],
    adj: dict[int, list[tuple[int, int]]],
    edge_list: list[dict],
    lan_nets: dict[str, list[ipaddress.IPv4Network]],
    routers: list[str],
    as_numbers: list[int],
) -> list[str]:
    if spec.routing == "none":
        return []
    if spec.routing == "static":
        routes: list[ios.Route] = []
        first = hops[idx]
        for j, other in enumerate(routers):
            neighbor = first.get(j)
            if j == idx or neighbor is None:
                continue
            eidx = next(e for v, e in adj[idx] if v == neighbor)
            edge = edge_list[eidx]
            nexthop = edge["b_ip"] if edge["a"] == idx else edge["a_ip"]
            for dest in lan_nets[other]:
                routes.append((str(dest.network_address), str(dest.netmask), nexthop))
        return ios.static_routes(routes)
    if spec.routing == "rip":
        return ios.rip_config(sorted({_classful(ip) for _port, ip, _mask in interfaces}))
    if spec.routing == "ospf":
        return ios.ospf_config(spec.ospf_process, spec.ospf_area, _connected_nets(interfaces))
    if spec.routing == "eigrp":
        return ios.eigrp_config(spec.eigrp_as, _connected_nets(interfaces))
    peers: list[tuple[str, int]] = []
    for j, eidx in adj[idx]:
        edge = edge_list[eidx]
        peer_ip = edge["b_ip"] if edge["a"] == idx else edge["a_ip"]
        peers.append((peer_ip, as_numbers[j]))
    networks = [(str(net.network_address), str(net.netmask)) for net in lan_nets[routers[idx]]]
    return ios.bgp_config(as_numbers[idx], peers, networks)


def _pool_name(lan_name: str) -> str:
    return "Pool_" + "".join(c if c.isalnum() else "_" for c in lan_name)


def _lan_dir(base: tuple[float, float], k: int, total: int) -> tuple[float, float]:
    """Reparte las LANs de una sede alrededor de la direccion base."""
    if total <= 1:
        return base
    ang = math.radians(40.0 - 80.0 * k / (total - 1))
    dx, dy = base
    return (dx * math.cos(ang) - dy * math.sin(ang), dx * math.sin(ang) + dy * math.cos(ang))


def _pool_name(lan_name: str) -> str:
    return "Pool_" + "".join(c if c.isalnum() else "_" for c in lan_name)


def _server_lan_index(spec: Spec) -> int | None:
    """Indice (en orden de creacion) de la LAN marcada con dhcp_server."""
    found = None
    idx = 0
    for site in spec.sites:
        for lan in site.lan_list():
            if lan.dhcp_server:
                if found is not None:
                    raise ValueError("solo una LAN puede tener dhcp_server: true")
                found = idx
            idx += 1
    return found


def plan(spec: Spec) -> Plan:
    """Plan de la topologia: modo grafo (nodes) o modo rapido (sites)."""
    if spec.nodes:
        return plan_graph(spec)

    ports = _Ports()
    devices: list[PlannedDevice] = []
    links: list[PlannedLink] = []

    lan_pool = ipaddress.ip_network(spec.lan_base).subnets(new_prefix=24)
    wan_pool = ipaddress.ip_network(spec.link_base).subnets(new_prefix=30)

    dev: dict[str, PlannedDevice] = {}
    routers: list[str] = []
    switches: list[str] = []
    lan_nets: dict[str, list[ipaddress.IPv4Network]] = {}
    lan_ifaces: dict[str, list[ios.Interface]] = {}
    wan_ifaces: dict[str, list[ios.Interface]] = {}
    dhcp_pools: dict[str, list[ios.Pool]] = {}
    hosts_by_site: list[list[list[str]]] = []
    lans: list[dict] = []  # sede, router, switch, red y nombre de cada LAN del lab

    host_n = 0
    for i, site in enumerate(spec.sites):
        rname = f"R{i + 1}"
        dev[rname] = PlannedDevice(rname, site.router_model, ROUTER)
        devices.append(dev[rname])
        routers.append(rname)
        lan_nets[rname] = []
        lan_ifaces[rname] = []
        wan_ifaces[rname] = []
        dhcp_pools[rname] = []
        site_hosts: list[list[str]] = []

        for k, lan in enumerate(site.lan_list()):
            swname = f"SW{len(switches) + 1}"
            switches.append(swname)
            dev[swname] = PlannedDevice(swname, site.switch_model, SWITCH)
            devices.append(dev[swname])

            net = ipaddress.ip_network(lan.lan, strict=False) if lan.lan else next(lan_pool)
            lan_nets[rname].append(net)
            gw = str(net.network_address + 1)

            rport = ports.take(rname, list(MODELS[site.router_model].ports))
            sport = ports.take(swname, uplink_ports(site.switch_model))
            links.append(PlannedLink(rname, rport, swname, sport))
            lan_ifaces[rname].append((rport, gw, str(net.netmask)))

            name = lan.name or f"LAN_{site.name}_{k + 1}"
            lans.append({"site": i, "k": k, "rname": rname, "sw": swname, "net": net, "name": name})

            dhcp = spec.lan_dhcp(lan)
            if dhcp:
                dhcp_pools[rname].append(
                    (f"LAN{len(lans)}", str(net.network_address), str(net.netmask), gw)
                )

            lan_hosts: list[str] = []
            for h in range(lan.hosts):
                host_n += 1
                hname = f"PC{host_n}"
                hd = PlannedDevice(hname, site.host_model, MODELS[site.host_model].role)
                dev[hname] = hd
                devices.append(hd)
                lan_hosts.append(hname)
                if dhcp:
                    hd.dhcp = True
                else:
                    hd.host_ip = (str(net.network_address + 2 + h), str(net.netmask), gw)
                hport = ports.take(hname, list(MODELS[site.host_model].ports))
                sp = ports.take(swname, access_ports(site.switch_model))
                links.append(PlannedLink(hname, hport, swname, sp))
            site_hosts.append(lan_hosts)
        hosts_by_site.append(site_hosts)

    server_lan = _server_lan_index(spec)
    server_ip: str | None = None
    if server_lan is not None:
        info = lans[server_lan]
        net = info["net"]
        server_ip = str(net.network_address + 100)
        server = PlannedDevice(SERVER_NAME, DEFAULT_SERVER, MODELS[DEFAULT_SERVER].role)
        server.host_ip = (server_ip, str(net.netmask), str(net.network_address + 1))
        server.service_pools = [
            ServicePool(
                name="serverPool" if idx == server_lan else _pool_name(item["name"]),
                network=str(item["net"].network_address),
                mask=str(item["net"].netmask),
                gateway=str(item["net"].network_address + 1),
                start_ip=str(item["net"].network_address + 10),
                dns=spec.dns,
            )
            for idx, item in enumerate(lans)
        ]
        dev[SERVER_NAME] = server
        devices.append(server)
        swname = info["sw"]
        sport = ports.take(swname, access_ports(dev[swname].model))
        links.append(PlannedLink(SERVER_NAME, MODELS[DEFAULT_SERVER].ports[0], swname, sport))
        hosts_by_site[info["site"]][info["k"]].append(SERVER_NAME)

    edges = _router_edges(spec.topology, len(routers))
    degree: dict[int, int] = defaultdict(int)
    for a, b in edges:
        degree[a] += 1
        degree[b] += 1
    for i, rname in enumerate(routers):
        need = degree[i] + len(lan_ifaces[rname])
        avail = len(MODELS[dev[rname].model].ports)
        if need > avail:
            raise ValueError(
                f"{rname} ({dev[rname].model}) necesita {need} puertos con la topologia "
                f"'{spec.topology}' y solo tiene {avail}. Usa menos sedes, otra topologia o "
                f"router_model: 3560-24PS (switch L3, 26 puertos) en las sedes."
            )

    adj: dict[int, list[tuple[int, int]]] = defaultdict(list)
    edge_list: list[dict] = []
    for eidx, (a, b) in enumerate(edges):
        net = next(wan_pool)
        a_ip, b_ip = str(net.network_address + 1), str(net.network_address + 2)
        ap = ports.take(routers[a], list(MODELS[dev[routers[a]].model].ports))
        bp = ports.take(routers[b], list(MODELS[dev[routers[b]].model].ports))
        links.append(PlannedLink(routers[a], ap, routers[b], bp))
        wan_ifaces[routers[a]].append((ap, a_ip, str(net.netmask)))
        wan_ifaces[routers[b]].append((bp, b_ip, str(net.netmask)))
        edge_list.append({"a": a, "b": b, "a_ip": a_ip, "b_ip": b_ip})
        adj[a].append((b, eidx))
        adj[b].append((a, eidx))

    hops = _first_hops(len(routers), adj)
    as_numbers = [site.as_number or spec.bgp_as_base + i for i, site in enumerate(spec.sites)]
    for i, rname in enumerate(routers):
        interfaces = [*lan_ifaces[rname], *wan_ifaces[rname]]
        routing = _routing_lines(spec, i, interfaces, hops, adj, edge_list, lan_nets, routers, as_numbers)
        model = MODELS[dev[rname].model]
        helpers: dict[str, str] = {}
        if server_ip:
            for k, (port, _ip, _mask) in enumerate(lan_ifaces[rname]):
                if lans[server_lan]["rname"] == rname and lans[server_lan]["k"] == k:
                    continue
                helpers[port] = server_ip
        dev[rname].config = ios.router_config(
            rname,
            interfaces,
            routing,
            None if server_ip else dhcp_pools.get(rname),
            l3_switch=model.role == L3SWITCH,
            helpers=helpers,
        )

    for swname in switches:
        dev[swname].config = ios.switch_config(swname)

    positions, dirs = _router_positions(spec.topology, len(routers))
    for i, rname in enumerate(routers):
        dev[rname].x, dev[rname].y = int(positions[i][0]), int(positions[i][1])
    lan_idx = 0
    for i, rname in enumerate(routers):
        rx, ry = dev[rname].x, dev[rname].y
        total = len(hosts_by_site[i])
        for k, lan_hosts in enumerate(hosts_by_site[i]):
            dx, dy = _lan_dir(dirs[i], k, total)
            swname = lans[lan_idx]["sw"]
            lan_idx += 1
            sx, sy = rx + dx * 170, ry + dy * 170
            dev[swname].x, dev[swname].y = int(sx), int(sy)
            for h, hname in enumerate(lan_hosts):
                off = 110 + h * 96
                dev[hname].x = int(sx + dx * off)
                dev[hname].y = int(sy + dy * off)

    return Plan(spec.name, devices, links)


# --------------------------------------------------------------------------- #
#  Modo grafo: nodos y enlaces explicitos                                     #
# --------------------------------------------------------------------------- #

_LAYER_Y = {ROUTER: 150.0, L3SWITCH: 150.0, SWITCH: 340.0, HUB: 340.0}


def _port_list(model) -> str:
    ports = list(model.ports)
    head = ", ".join(ports[:6])
    return head + ("..." if len(ports) > 6 else "")


def _cidr(value: str, who: str, what: str, seen: dict[str, str]) -> ipaddress.IPv4Interface:
    """Valida una IP en CIDR, rechaza duplicados y la registra."""
    try:
        iface = ipaddress.ip_interface(value)
    except ValueError:
        raise ValueError(f"{who}: {what} invalida: {value!r} (formato 192.168.1.1/24)") from None
    if iface.version != 4:
        raise ValueError(f"{who}: {what} debe ser IPv4: {value!r}")
    ip = str(iface.ip)
    if ip in seen:
        raise ValueError(f"{who}: la IP {ip} ya esta usada por {seen[ip]}")
    seen[ip] = who
    return iface


def _iface_ip(node: NodeSpec, port: str, parsed: dict) -> str | None:
    for iface in node.interfaces:
        if iface.port == port and iface.ip:
            return str(parsed[(node.name, port)].ip)
    return None


def _owner_router(host: str, adjacency: dict[str, list[str]], routers: set[str]) -> str | None:
    """Primer router que alcanza un host siguiendo los cables (para el routing)."""
    seen = {host}
    queue = deque([host])
    while queue:
        u = queue.popleft()
        for v in adjacency.get(u, []):
            if v in seen:
                continue
            seen.add(v)
            if v in routers:
                return v
            queue.append(v)
    return None


def _cable_kind(link: LinkSpec) -> str:
    if link.cable == "serial":
        raise ValueError(
            f"enlace {link.a} <-> {link.b}: el cable serial todavia no esta soportado "
            f"(requiere instalar un modulo HWIC-2T en el router)"
        )
    return "crossover" if link.cable == "crossover" else "copper"


def _check_links(spec: Spec, byname: dict[str, NodeSpec], info: dict[str, dict]) -> None:
    used: dict[tuple[str, str], str] = {}
    for link in spec.links:
        for name in (link.a, link.b):
            if name not in byname:
                raise ValueError(f"enlace {link.a} <-> {link.b}: nodo desconocido {name!r}")
        if link.a == link.b:
            raise ValueError(f"enlace {link.a}: no puede unir un nodo consigo mismo")
        for name, port in ((link.a, link.a_port), (link.b, link.b_port)):
            model = info[name]["model"]
            if port not in model.ports:
                raise ValueError(
                    f"{name}: el puerto {port!r} no existe en {model.name} (puertos: {_port_list(model)})"
                )
            key = (name, port)
            if key in used:
                raise ValueError(f"{name}: el puerto {port} ya esta usado por otro enlace ({used[key]})")
            used[key] = f"{link.a}:{link.a_port} <-> {link.b}:{link.b_port}"


def plan_graph(spec: Spec) -> Plan:
    """Plan del modo grafo: respeta nodos/enlaces y autocompleta lo que falte.

    - Layout por capas cuando el nodo no trae x/y.
    - Config IOS de routers/switches a partir de los datos del nodo (interfaces,
      VLANs/trunk/SVI, DHCP, config extra).
    - Rutas calculadas sobre el propio grafo: `static` por BFS de vecinos,
      OSPF/EIGRP/RIP anuncian las redes conectadas y BGP usa `as_number` por nodo.
    """
    byname: dict[str, NodeSpec] = {}
    for node in spec.nodes:
        if node.name in byname:
            raise ValueError(f"nombre de nodo duplicado: {node.name!r}")
        byname[node.name] = node

    info: dict[str, dict] = {}
    for node in spec.nodes:
        try:
            model = MODELS[node.model]
        except KeyError:
            raise ValueError(
                f"{node.name}: modelo no soportado {node.model!r} (soportados: {', '.join(MODELS)})"
            ) from None
        info[node.name] = {"model": model, "role": model.role}

    _check_links(spec, byname, info)

    seen_ips: dict[str, str] = {}
    parsed: dict[tuple[str, str], ipaddress.IPv4Interface] = {}

    for node in spec.nodes:
        role = info[node.name]["role"]
        model = info[node.name]["model"]

        if node.pools and node.model != DEFAULT_SERVER:
            raise ValueError(f"{node.name}: `pools` (DHCP) solo aplica a Server-PT")

        if role in (HOST, HUB):
            if node.interfaces or node.vlans or node.access or node.trunks:
                raise ValueError(
                    f"{node.name} ({model.name}): interfaces/VLANs solo aplican a routers y switches"
                )
            if node.gateway:
                try:
                    ipaddress.ip_address(node.gateway)
                except ValueError:
                    raise ValueError(f"{node.name}: gateway invalido {node.gateway!r}") from None
            if node.ip:
                if node.dhcp:
                    raise ValueError(f"{node.name}: tiene `ip` y `dhcp: true` a la vez; elegi uno")
                parsed[(node.name, "@host")] = _cidr(node.ip, node.name, "la IP", seen_ips)
            for k, pool in enumerate(node.pools):
                try:
                    ipaddress.ip_network(pool.network, strict=False)
                except ValueError:
                    raise ValueError(f"{node.name}: pool {k + 1}: red invalida {pool.network!r}") from None
                if pool.start_ip:
                    try:
                        ipaddress.ip_address(pool.start_ip)
                    except ValueError:
                        raise ValueError(
                            f"{node.name}: pool {k + 1}: start_ip invalido {pool.start_ip!r}"
                        ) from None
            continue

        if role == L3SWITCH and (node.vlans or node.access or node.trunks):
            raise ValueError(
                f"{node.name}: switch L3 con VLANs todavia no esta soportado; usa un switch L2 "
                f"(2960-24TT, 2950-24) para las VLANs"
            )

        declared: set[int] = set()
        for vlan in node.vlans:
            if vlan.id in declared:
                raise ValueError(f"{node.name}: VLAN {vlan.id} repetida")
            declared.add(vlan.id)

        busy_ports: set[str] = set()
        for ap in node.access:
            if ap.port not in model.ports:
                raise ValueError(
                    f"{node.name}: {ap.port!r} no existe en {model.name} (puertos: {_port_list(model)})"
                )
            if ap.vlan not in declared:
                raise ValueError(
                    f"{node.name}: el puerto {ap.port} usa la VLAN {ap.vlan}; "
                    f"declara primero esa VLAN en `vlans`"
                )
            if ap.port in busy_ports:
                raise ValueError(f"{node.name}: el puerto {ap.port} aparece dos veces")
            busy_ports.add(ap.port)
        for port in node.trunks:
            if port not in model.ports:
                raise ValueError(
                    f"{node.name}: {port!r} no existe en {model.name} (puertos: {_port_list(model)})"
                )
            if port in busy_ports:
                raise ValueError(f"{node.name}: el puerto {port} aparece dos veces")
            busy_ports.add(port)

        for iface in node.interfaces:
            port = iface.port
            if "." in port:
                if role != ROUTER:
                    raise ValueError(f"{node.name}: la subinterfaz {port} solo aplica a routers")
                base, suffix = port.rsplit(".", 1)
                if base not in model.ports:
                    raise ValueError(
                        f"{node.name}: {port!r}: la interfaz base {base!r} no existe en {model.name}"
                    )
                if iface.dot1q is None:
                    raise ValueError(f"{node.name}: {port} necesita `dot1q` (vlan de la subinterfaz)")
                if str(iface.dot1q) != suffix:
                    raise ValueError(
                        f"{node.name}: {port} deberia llevar dot1q {suffix} (el sufijo del puerto)"
                    )
                if not iface.ip:
                    raise ValueError(f"{node.name}: la subinterfaz {port} necesita `ip`")
            elif port.lower().startswith("vlan"):
                if role != SWITCH:
                    raise ValueError(f"{node.name}: {port} (SVI) solo aplica a switches L2")
                suffix = port[4:]
                if not suffix.isdigit() or int(suffix) not in declared:
                    raise ValueError(f"{node.name}: {port}: declara primero la VLAN {suffix} en `vlans`")
                if not iface.ip:
                    raise ValueError(f"{node.name}: {port} (SVI) necesita `ip`")
            elif port not in model.ports:
                raise ValueError(
                    f"{node.name}: el puerto {port!r} no existe en {model.name} (puertos: {_port_list(model)})"
                )
            if iface.dot1q is not None and "." not in port:
                raise ValueError(
                    f"{node.name}: `dot1q` en {port} es solo para subinterfaces (ej. {port}.{iface.dot1q})"
                )
            if role == SWITCH and iface.ip and not port.lower().startswith("vlan"):
                raise ValueError(
                    f"{node.name}: un switch L2 no lleva IP en puertos fisicos; usa una SVI (ej. Vlan1)"
                )
            if iface.ip:
                parsed[(node.name, port)] = _cidr(iface.ip, node.name, f"la IP de {port}", seen_ips)
            if iface.helper:
                if role != ROUTER:
                    raise ValueError(f"{node.name}: `helper` solo aplica a routers")
                try:
                    ipaddress.ip_address(iface.helper)
                except ValueError:
                    raise ValueError(f"{node.name}: helper invalido en {port}: {iface.helper!r}") from None

    # --- layout: posicion dada o reparto por capas ---
    slots: dict[float, int] = defaultdict(int)
    pos: dict[str, tuple[float, float]] = {}
    for node in spec.nodes:
        role = info[node.name]["role"]
        if node.x is not None and node.y is not None:
            pos[node.name] = (float(node.x), float(node.y))
            continue
        y = _LAYER_Y.get(role, 540.0)
        pos[node.name] = (240.0 + slots[y] * 190.0, y)
        slots[y] += 1

    routers = [n.name for n in spec.nodes if info[n.name]["role"] in (ROUTER, L3SWITCH)]
    ridx = {name: i for i, name in enumerate(routers)}

    adjacency: dict[str, list[str]] = defaultdict(list)
    for link in spec.links:
        adjacency[link.a].append(link.b)
        adjacency[link.b].append(link.a)

    # enlaces router-router usables para rutas (ambos extremos con IP)
    adj_r: dict[int, list[tuple[int, int]]] = defaultdict(list)
    edge_ips: list[tuple[str | None, str | None]] = [(None, None)] * len(spec.links)
    for li, link in enumerate(spec.links):
        if link.a in ridx and link.b in ridx:
            a_ip = _iface_ip(byname[link.a], link.a_port, parsed)
            b_ip = _iface_ip(byname[link.b], link.b_port, parsed)
            if a_ip and b_ip:
                edge_ips[li] = (a_ip, b_ip)
                adj_r[ridx[link.a]].append((ridx[link.b], li))
                adj_r[ridx[link.b]].append((ridx[link.a], li))

    # redes "propias" de cada router: subredes de sus interfaces + hosts que cuelgan
    own_nets: dict[str, list[ipaddress.IPv4Network]] = {r: [] for r in routers}
    for rname in routers:
        for iface in byname[rname].interfaces:
            if iface.ip:
                net = parsed[(rname, iface.port)].network
                if net not in own_nets[rname]:
                    own_nets[rname].append(net)
    router_set = set(routers)
    for node in spec.nodes:
        if info[node.name]["role"] != HOST or node.dhcp or not node.ip:
            continue
        owner = _owner_router(node.name, adjacency, router_set)
        if owner:
            net = parsed[(node.name, "@host")].network
            if net not in own_nets[owner]:
                own_nets[owner].append(net)

    hops = _first_hops(len(routers), adj_r)
    as_numbers = [byname[r].as_number or spec.bgp_as_base + i for i, r in enumerate(routers)]

    devices: list[PlannedDevice] = []
    for node in spec.nodes:
        role = info[node.name]["role"]
        x, y = pos[node.name]
        dev = PlannedDevice(node.name, node.model, role, x=int(round(x)), y=int(round(y)))

        if role in (HOST, HUB):
            if role == HOST:
                if node.dhcp:
                    dev.dhcp = True
                elif node.ip:
                    iface = parsed[(node.name, "@host")]
                    gateway = node.gateway or str(iface.network.network_address + 1)
                    dev.host_ip = (str(iface.ip), str(iface.network.netmask), gateway)
                for k, pool in enumerate(node.pools):
                    net = ipaddress.ip_network(pool.network, strict=False)
                    dev.service_pools.append(
                        ServicePool(
                            name=pool.name or f"pool{k + 1}",
                            network=str(net.network_address),
                            mask=str(net.netmask),
                            gateway=pool.gateway,
                            start_ip=pool.start_ip or str(net.network_address + 10),
                            dns=pool.dns or spec.dns,
                        )
                    )
        elif role == SWITCH:
            svis: list[tuple[int, str, str]] = []
            vlan1_ip = vlan1_mask = None
            for iface in node.interfaces:
                iface_parsed = parsed.get((node.name, iface.port))
                if iface_parsed is None:
                    continue
                if iface.port.lower() == "vlan1":
                    vlan1_ip, vlan1_mask = str(iface_parsed.ip), str(iface_parsed.network.netmask)
                else:
                    svis.append(
                        (int(iface.port[4:]), str(iface_parsed.ip), str(iface_parsed.network.netmask))
                    )
            config = ios.switch_config(
                node.name,
                vlan1_ip=vlan1_ip,
                vlan1_mask=vlan1_mask,
                vlans=[(v.id, v.name) for v in node.vlans],
                access=[(a.port, a.vlan) for a in node.access],
                trunks=list(node.trunks),
                svis=svis,
            )
            if node.config:
                config = config[:-1] + list(node.config) + ["end"]
            dev.config = config
        else:  # router / switch L3 (como router)
            interfaces: list[ios.Interface] = []
            subinterfaces: list[ios.SubInterface] = []
            helpers: dict[str, str] = {}
            sub_bases: dict[str, list] = {}
            for iface in node.interfaces:
                if iface.dot1q:
                    sub_bases.setdefault(iface.port.rsplit(".", 1)[0], []).append(iface)
                    continue
                ip = mask = ""
                if iface.ip:
                    iface_parsed = parsed[(node.name, iface.port)]
                    ip, mask = str(iface_parsed.ip), str(iface_parsed.network.netmask)
                interfaces.append((iface.port, ip, mask))
                if iface.helper:
                    helpers[iface.port] = iface.helper
            for base, sub_ifaces in sub_bases.items():
                if base not in [p for p, _ip, _mask in interfaces]:
                    interfaces.append((base, None, None))
                for iface in sub_ifaces:
                    iface_parsed = parsed[(node.name, iface.port)]
                    subinterfaces.append(
                        (base, iface.dot1q, str(iface_parsed.ip), str(iface_parsed.network.netmask))
                    )

            proto = node.routing or spec.routing
            connected = [i for i in interfaces if i[1]]
            all_ips: list[ios.Interface] = [
                *connected,
                *[(f"{base}.{vlan}", ip, mask) for base, vlan, ip, mask in subinterfaces],
            ]
            if proto == "none":
                routing_lines: list[str] = []
            elif proto == "static":
                i = ridx[node.name]
                routes: list[ios.Route] = []
                for j, other in enumerate(routers):
                    neighbor = hops[i].get(j)
                    if j == i or neighbor is None:
                        continue
                    li = next(l for v, l in adj_r[i] if v == neighbor)
                    a_ip, b_ip = edge_ips[li]
                    nexthop = b_ip if spec.links[li].a == node.name else a_ip
                    for net in own_nets[other]:
                        if net not in own_nets[node.name]:
                            routes.append((str(net.network_address), str(net.netmask), nexthop))
                routing_lines = ios.static_routes(routes)
            elif proto == "rip":
                routing_lines = ios.rip_config(
                    sorted({_classful(ip) for _p, ip, _m in all_ips})
                )
            elif proto == "ospf":
                routing_lines = ios.ospf_config(
                    spec.ospf_process, spec.ospf_area, _connected_nets(all_ips)
                )
            elif proto == "eigrp":
                routing_lines = ios.eigrp_config(spec.eigrp_as, _connected_nets(all_ips))
            else:  # bgp
                i = ridx[node.name]
                peers: list[tuple[str, int]] = []
                for j, li in adj_r[i]:
                    a_ip, b_ip = edge_ips[li]
                    peer_ip = b_ip if spec.links[li].a == node.name else a_ip
                    peers.append((peer_ip, as_numbers[j]))
                nets = [(str(n.network_address), str(n.netmask)) for n in own_nets[node.name]]
                routing_lines = ios.bgp_config(as_numbers[i], peers, nets)

            dhcp_pools: list[ios.Pool] = []
            if node.dhcp:
                for k, (_port, ip, mask) in enumerate(all_ips):
                    net = ipaddress.ip_interface(f"{ip}/{mask}")
                    if net.network.prefixlen <= 24:
                        dhcp_pools.append(
                            (f"LAN{k + 1}", str(net.network.network_address), str(net.network.netmask), ip)
                        )
            dev.config = ios.router_config(
                node.name,
                interfaces,
                routing_lines,
                dhcp_pools or None,
                l3_switch=role == L3SWITCH,
                helpers=helpers or None,
                subinterfaces=subinterfaces or None,
                extra=list(node.config) or None,
            )
        devices.append(dev)

    links_out = [
        PlannedLink(link.a, link.a_port, link.b, link.b_port, kind=_cable_kind(link))
        for link in spec.links
    ]
    return Plan(spec.name, devices, links_out)
