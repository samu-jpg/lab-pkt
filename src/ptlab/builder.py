"""Construye el .pkt a partir de un Plan, usando el generador de vendor/.

Usa el codec de `pkt_core` (Python puro) en lugar de `pt9`/libgcrypt, para que corra
en Windows/macOS/Linux sin dependencias nativas.
"""
from __future__ import annotations

import copy
import ipaddress
import xml.etree.ElementTree as ET
from pathlib import Path

from ptlab.planner import Plan, ServicePool
from ptlab.vendorlib import VENDOR, lab_api as _lab_api, templates


def _set_host_dhcp(lab, dev_id: str) -> None:
    port = lab._els[dev_id].find(".//PORT")
    for tag, val in (("PORT_DHCP_ENABLE", "true"), ("IP", ""), ("SUBNET", ""), ("PORT_GATEWAY", "")):
        el = port.find(tag)
        if el is None:
            el = ET.SubElement(port, tag)
        el.text = val


def _tag_text(node, tag: str, value: str) -> None:
    el = node.find(tag)
    if el is None:
        el = ET.SubElement(node, tag)
    el.text = value


def _set_dhcp_service(lab, dev_id: str, pools: list[ServicePool]) -> None:
    """Carga los pools en el servicio DHCP del equipo (XML del Server-PT)."""
    service = next((el for el in lab._els[dev_id].iter("DHCP_SERVER")), None)
    if service is None:
        raise ValueError(f"{dev_id}: el modelo no tiene servicio DHCP configurable")
    _tag_text(service, "ENABLED", "1")
    pools_el = service.find("POOLS")
    template = pools_el.find("POOL")
    for i, pool in enumerate(pools):
        node = template if i == 0 else copy.deepcopy(template)
        if i:
            pools_el.append(node)
        for tag, value in (
            ("NAME", pool.name),
            ("NETWORK", pool.network),
            ("MASK", pool.mask),
            ("DEFAULT_ROUTER", pool.gateway),
            ("TFTP_ADDRESS", "0.0.0.0"),
            ("START_IP", pool.start_ip),
            ("END_IP", str(ipaddress.ip_address(pool.start_ip) + pool.max_users)),
            ("DNS_SERVER", pool.dns),
            ("MAX_USERS", str(pool.max_users)),
        ):
            _tag_text(node, tag, value)


def _set_crossover(lab) -> None:
    """Marca el ultimo cable como crossover (el formato solo lo distingue por el TYPE del CABLE)."""
    cable = lab.net.find("LINKS").findall("LINK")[-1].find("CABLE")
    tag = cable.find("TYPE") if cable is not None else None
    if tag is not None:
        tag.text = "eCrossOver"


def build(plan: Plan, out_path: str | Path) -> Path:
    lab_api = _lab_api()
    models, modules = templates()
    lab = lab_api.Lab(str(VENDOR / "tools" / "network_seed.xml"), models, modules)
    lab.prune_seed_devices()

    ids: dict[str, str] = {}
    for d in plan.devices:
        ids[d.name] = lab.add_device(
            d.model, d.name, d.x, d.y,
            ios_config=list(d.config) or None,
            pc_ip=list(d.host_ip) if d.host_ip else None,
        )
        if d.dhcp:
            _set_host_dhcp(lab, ids[d.name])
        if d.service_pools:
            _set_dhcp_service(lab, ids[d.name], d.service_pools)

    for link in plan.links:
        kind = "copper" if link.kind == "crossover" else link.kind
        lab.link(ids[link.a], link.a_port, ids[link.b], link.b_port, kind=kind)
        if link.kind == "crossover":
            _set_crossover(lab)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lab.save(str(out))
    return out
