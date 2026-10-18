"""Primitivas de Packet Tracer sobre un archivo .pkt (la caja de herramientas del MCP).

Cada funcion abre el .pkt, aplica el cambio con el `lab_api` del vendor y lo guarda otra vez.
No hay plantillas: modelos, nombres, cables, configs y modulos los decide quien llama.

`_lab(path)` deja los equipos existentes accesibles por su save-ref-id (`lab._els`), que es
lo que usan los metodos del vendor (`set_wireless`, `install_module`, `_append_config`, ...).
"""
from __future__ import annotations

import ipaddress
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ptlab.vendorlib import SEED, lab_api, templates


def _lab(path: str | Path):
    p = Path(path)
    if not p.exists():
        raise ValueError(f"no existe {p}: crea el lab primero (pt_new)")
    api = lab_api()
    models, modules = templates()
    try:
        lab = api.Lab(str(p), models, modules)
    except ValueError as exc:
        raise ValueError(f"{p}: no se pudo abrir ({exc})") from None
    for el in lab.devs.findall("DEVICE"):
        sid = el.findtext("ENGINE/SAVE_REF_ID")
        if sid:
            lab._els.setdefault(sid, el)
    return lab, p


def _save(lab, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lab.save(str(path))
    return path


def _names(lab) -> list[str]:
    return [el.findtext("ENGINE/NAME") or "" for el in lab.devs.findall("DEVICE")]


def _device(lab, name: str):
    for el in lab.devs.findall("DEVICE"):
        if (el.findtext("ENGINE/NAME") or "") == name:
            return el
    raise ValueError(f"no existe el equipo {name!r} (equipos: {', '.join(_names(lab)) or 'ninguno'})")


def _sid(lab, name: str) -> str:
    sid = _device(lab, name).findtext("ENGINE/SAVE_REF_ID")
    if not sid:
        raise ValueError(f"{name}: el equipo no tiene save-ref-id")
    return sid


def _modelos() -> dict:
    api_models, _modules = templates()
    return api_models


def _modulos() -> dict:
    _models, modules = templates()
    return modules


def _port_el(el):
    port = el.find(".//PORT")
    if port is None:
        raise ValueError(f"{(el.findtext('ENGINE/NAME') or '?')}: el equipo no tiene puertos")
    return port


def _put(parent, tag: str, value: str) -> None:
    node = parent.find(tag)
    if node is None:
        node = ET.SubElement(parent, tag)
    node.text = value


def _free_sid(lab) -> None:
    """Deja `lab._n` en un indice que no choque con los save-ref-id existentes.

    `Lab` numera desde 0 en cada apertura; sin esto, un equipo nuevo reutiliza el
    save-ref-id de otro equipo y los cables quedan mal atribuidos.
    """
    used = {el.findtext("ENGINE/SAVE_REF_ID") for el in lab.devs.findall("DEVICE")}
    i = 0
    while f"save-ref-id:{9_900_000_000_000_000_000 + i}" in used:
        i += 1
    lab._n = i


# --------------------------------------------------------------------------- #
#  Lab
# --------------------------------------------------------------------------- #


def new(path: str | Path) -> Path:
    """Crea un .pkt vacio (sin equipos del seed), listo para armar con `add_device`."""
    api = lab_api()
    models, modules = templates()
    lab = api.Lab(str(SEED), models, modules)
    lab.prune_seed_devices()
    return _save(lab, Path(path))


def device_names(path: str | Path) -> list[str]:
    """Nombres de los equipos del lab, en orden."""
    lab, _p = _lab(path)
    return _names(lab)


def devices(path: str | Path) -> list[dict]:
    """Equipos del lab: nombre, modelo y posicion."""
    lab, _p = _lab(path)
    out: list[dict] = []
    for el in lab.devs.findall("DEVICE"):
        eng = el.find("ENGINE")
        tipo = eng.find("TYPE") if eng is not None else None
        ws = el.find("WORKSPACE/LOGICAL")
        out.append(
            {
                "name": (eng.findtext("NAME") or "") if eng is not None else "",
                "model": (tipo.get("model") or "") if tipo is not None else "",
                "x": int(ws.findtext("X")) if ws is not None and ws.findtext("X") else None,
                "y": int(ws.findtext("Y")) if ws is not None and ws.findtext("Y") else None,
            }
        )
    return out


def models() -> dict:
    """Todos los modelos y modulos que acepta el vendor (no una lista fija)."""
    out = [
        {"model": name, "ports": len(re.findall(rb"<PORT>", blob))}
        for name, blob in _modelos().items()
    ]
    return {"models": sorted(out, key=lambda m: m["model"]), "modules": sorted(_modulos())}


# --------------------------------------------------------------------------- #
#  Equipos
# --------------------------------------------------------------------------- #


def add_device(
    path: str | Path,
    model: str,
    name: str,
    x: int = 100,
    y: int = 100,
    power: bool = True,
    config: list[str] | None = None,
    host_ip: str = "",
    host_gateway: str = "",
    install: str | None = None,
    bay: int = 0,
    on_conflict: str = "raise",
) -> Path:
    """Agrega un equipo con config IOS y/o red de host opcionales.

    `host_ip`: IP del host en CIDR (ej. 192.168.1.10/24) + `host_gateway` opcional.
    `install`: modelo de modulo a instalar (ej. HWIC-2T) en el bay indicado.
    """
    if model not in _modelos():
        raise ValueError(f"modelo desconocido {model!r}: usa pt_list_models")
    if install and install not in _modulos():
        raise ValueError(f"modulo desconocido {install!r}: usa pt_list_models")
    pc_ip = None
    if host_ip:
        iface = ipaddress.ip_interface(host_ip)
        pc_ip = (str(iface.ip), str(iface.network.netmask), host_gateway)
    lines = [line for line in (config or []) if line.strip()]
    if lines and lines[-1].strip().lower() != "end":
        lines.append("end")
    lab, p = _lab(path)
    _free_sid(lab)
    lab.add_device(
        model,
        name,
        x=x,
        y=y,
        power=power,
        ios_config=lines or None,
        pc_ip=pc_ip,
        install=install,
        bay=bay,
        on_name_conflict=on_conflict,
    )
    return _save(lab, p)


def remove_device(path: str | Path, device: str) -> Path:
    """Quita un equipo del lab (con sus cables y su lugar en el rack fisico)."""
    lab, p = _lab(path)
    _drop(lab, [_device(lab, device)])
    return _save(lab, p)


def _drop(lab, els) -> None:
    """Version general de `prune_seed_devices` para cualquier equipo (por XML)."""
    dead: set[str] = set()
    dropped = {id(el) for el in els}
    for el in els:
        sid = el.findtext("ENGINE/SAVE_REF_ID")
        if sid:
            dead.add(sid)
        ph = el.findtext("WORKSPACE/PHYSICAL")
        if ph and lab._wsroot is not None:
            leaf = "{%s}" % ph.split(",")[-1].strip().strip("{}")
            for n in list(lab._wsroot.iter("NODE")):
                if n.findtext("UUID_STR") == leaf:
                    for parent in lab._wsroot.iter("NODE"):
                        ch = parent.find("CHILDREN")
                        if ch is not None and n in list(ch):
                            ch.remove(n)
        if el in list(lab.devs):
            lab.devs.remove(el)
        for sid_key, mapped in list(lab._els.items()):
            if id(mapped) in dropped:
                del lab._els[sid_key]
    links = lab.net.find("LINKS")
    if links is not None and dead:
        for L in list(links.findall("LINK")):
            cab = L.find("CABLE")
            if cab is not None and (cab.findtext("FROM") in dead or cab.findtext("TO") in dead):
                links.remove(L)
    lab._initial_devs = [el for el in lab._initial_devs if id(el) not in dropped]


# --------------------------------------------------------------------------- #
#  Cables
# --------------------------------------------------------------------------- #


def add_link(
    path: str | Path,
    a: str,
    a_port: str,
    b: str,
    b_port: str,
    kind: str = "copper",
    dce: str | None = None,
    clock: int = 128000,
) -> Path:
    """Cablea dos equipos: `copper` (straight), `crossover` o `serial` (DCE con clock rate)."""
    if kind not in ("copper", "crossover", "serial"):
        raise ValueError(f"kind desconocido {kind!r}: copper | crossover | serial")
    lab, p = _lab(path)
    dce_sid = _sid(lab, dce) if dce else None
    lab.link(_sid(lab, a), a_port, _sid(lab, b), b_port, kind="copper" if kind == "crossover" else kind, dce=dce_sid, clock=clock)
    if kind == "crossover":
        links = lab.net.find("LINKS")
        cable = list(links.findall("LINK"))[-1].find("CABLE") if links is not None else None
        tag = cable.find("TYPE") if cable is not None else None
        if tag is not None:
            tag.text = "eCrossOver"
    return _save(lab, p)


# --------------------------------------------------------------------------- #
#  Configuracion
# --------------------------------------------------------------------------- #


def append_config(path: str | Path, device: str, lines: list[str]) -> Path:
    """Agrega lineas IOS crudas al `RUNNINGCONFIG` del equipo (antes del `end`)."""
    lab, p = _lab(path)
    if not lines:
        raise ValueError("`lines` esta vacio: no hay nada para agregar")
    lab._append_config(_sid(lab, device), list(lines))
    return _save(lab, p)


def set_host(path: str | Path, device: str, ip: str, gateway: str = "") -> Path:
    """IP estatica (CIDR) y gateway opcional en el puerto de un host."""
    lab, p = _lab(path)
    port = _port_el(_device(lab, device))
    iface = ipaddress.ip_interface(ip)
    _put(port, "IP", str(iface.ip))
    _put(port, "SUBNET", str(iface.network.netmask))
    _put(port, "PORT_DHCP_ENABLE", "false")
    if gateway:
        _put(port, "PORT_GATEWAY", gateway)
    return _save(lab, p)


def set_dhcp(path: str | Path, device: str, enable: bool = True) -> Path:
    """Prende/apaga DHCP en el puerto del host (apagado deja la IP estatica)."""
    lab, p = _lab(path)
    port = _port_el(_device(lab, device))
    _put(port, "PORT_DHCP_ENABLE", "true" if enable else "false")
    if enable:
        for tag in ("IP", "SUBNET", "PORT_GATEWAY"):
            _put(port, tag, "")
    return _save(lab, p)


def _wireless_client(el, ssid: str = "", password: str = "", channel: str = "",
                     auth_type: str = "", encrypt_type: str = "") -> int:
    """SSID/seguridad en la seccion `WIRELESS_CLIENT` (hosts clientes: laptop, PC).

    Los APs y routers llevan el SSID en sus puertos (lo cubre `Lab.set_wireless`); los
    clientes lo llevan en `WIRELESS_CLIENT/WIRELESS_COMMON` y en sus profiles.
    """
    changed = 0
    for wc in el.iter("WIRELESS_CLIENT"):
        changed += 1
        common = wc.find("WIRELESS_COMMON")
        if common is not None:
            if ssid:
                _put(common, "SSID", ssid)
            if auth_type:
                _put(common, "AUTHEN_TYPE", auth_type)
            if encrypt_type:
                _put(common, "ENCRYPT_TYPE", encrypt_type)
        for prof in wc.iter("WIRELESS_PROFILE"):
            if ssid:
                _put(prof, "SSID", ssid)
                _put(prof, "NAME", ssid)
            if password:
                _put(prof, "WPA_EAP_PASSWORD", password)
            if channel:
                _put(prof, "CHANNEL", channel)
    return changed


def set_wireless(
    path: str | Path,
    device: str,
    ssid: str = "",
    password: str = "",
    channel: str = "",
    auth_type: str = "",
    encrypt_type: str = "",
    radio_band: str = "",
) -> Path:
    """SSID/seguridad/canal del equipo inalambrico (AP, router, laptop, host)."""
    lab, p = _lab(path)
    el = _device(lab, device)
    changed = lab.set_wireless(
        _sid(lab, device),
        ssid=ssid or None,
        password=password or None,
        channel=channel or None,
        auth_type=auth_type or None,
        encrypt_type=encrypt_type or None,
        radio_band=radio_band or None,
    )
    changed += _wireless_client(
        el,
        ssid=ssid,
        password=password,
        channel=channel,
        auth_type=auth_type,
        encrypt_type=encrypt_type,
    )
    if not changed:
        raise ValueError(f"{device}: el modelo no tiene wireless (SSID)")
    return _save(lab, p)


def set_config_register(path: str | Path, device: str, value: int) -> Path:
    """Registro de configuracion del equipo (`CONFIG_REGISTER`, ej. 0x2142)."""
    lab, p = _lab(path)
    lab.set_config_register(_sid(lab, device), value)
    return _save(lab, p)


def set_os(path: str | Path, device: str, image: str = "", file_name: str = "") -> Path:
    """Imagen / archivo de boot del equipo (`OS_IMAGE`, `OS_FILE_NAME`)."""
    lab, p = _lab(path)
    if not image and not file_name:
        raise ValueError("pasa `image` o `file_name`")
    lab.set_os(_sid(lab, device), image=image or None, file_name=file_name or None)
    return _save(lab, p)


def install_module(path: str | Path, device: str, module: str, bay: int = 0) -> Path:
    """Instala un modulo (ej. HWIC-2T) en el bay de tarjeta indicado."""
    if module not in _modulos():
        raise ValueError(f"modulo desconocido {module!r}: usa pt_list_models")
    lab, p = _lab(path)
    lab.install_module(_sid(lab, device), module, bay)
    return _save(lab, p)


# --------------------------------------------------------------------------- #
#  Inspeccion
# --------------------------------------------------------------------------- #


def inspect(path: str | Path) -> dict:
    """Lee un .pkt: equipos (modelo, red, config, pools, wireless) y enlaces."""
    lab, p = _lab(path)
    names: dict[str, str] = {}
    out_devices: list[dict] = []
    for el in lab.devs.findall("DEVICE"):
        eng = el.find("ENGINE")
        nombre = (eng.findtext("NAME") or "") if eng is not None else ""
        names[el.findtext("ENGINE/SAVE_REF_ID") or ""] = nombre
        tipo = eng.find("TYPE") if eng is not None else None
        node: dict = {"name": nombre, "model": (tipo.get("model") or "") if tipo is not None else ""}
        if eng is not None and (eng.findtext("POWER") or "true") != "true":
            node["power"] = False
        ws = el.find("WORKSPACE/LOGICAL")
        if ws is not None and ws.findtext("X") is not None:
            node["x"] = int(ws.findtext("X"))
            node["y"] = int(ws.findtext("Y"))
        config = [line.text or "" for line in el.findall("ENGINE/RUNNINGCONFIG/LINE")]
        if config:
            node["config"] = config
        port = el.find(".//PORT")
        if port is not None:
            ip = port.findtext("IP")
            if ip:
                node["ip"] = ip
                node["mask"] = port.findtext("SUBNET") or ""
            if port.findtext("PORT_GATEWAY"):
                node["gateway"] = port.findtext("PORT_GATEWAY")
            if (port.findtext("PORT_DHCP_ENABLE") or "false").lower() == "true":
                node["dhcp"] = True
        for svc in el.iter("DHCP_SERVER"):
            pools = [
                {
                    "name": pool.findtext("NAME") or "",
                    "network": pool.findtext("NETWORK") or "",
                    "mask": pool.findtext("MASK") or "",
                    "gateway": pool.findtext("DEFAULT_ROUTER") or "",
                    "start_ip": pool.findtext("START_IP") or "",
                }
                for pool in svc.findall("POOLS/POOL")
            ]
            if pools:
                node["dhcp_pools"] = pools
        ssids = [
            port.findtext("SSID")
            for port in el.iter("PORT")
            if port.find("SSID") is not None and port.findtext("SSID")
        ]
        if ssids:
            node["ssid"] = ssids
        out_devices.append(node)

    links: list[dict] = []
    links_el = lab.net.find("LINKS")
    for L in links_el.findall("LINK") if links_el is not None else []:
        cab = L.find("CABLE")
        if cab is None:
            continue
        kind = "serial" if L.findtext("TYPE") == "eSerial" else (
            "crossover" if cab.findtext("TYPE") == "eCrossOver" else "copper"
        )
        ports = cab.findall("PORT")
        link = {
            "a": names.get(cab.findtext("FROM") or "", cab.findtext("FROM") or ""),
            "a_port": ports[0].text if len(ports) > 0 else "",
            "b": names.get(cab.findtext("TO") or "", cab.findtext("TO") or ""),
            "b_port": ports[1].text if len(ports) > 1 else "",
            "kind": kind,
        }
        if cab.findtext("DCEDEV"):
            link["dce"] = names.get(cab.findtext("DCEDEV") or "", cab.findtext("DCEDEV") or "")
        links.append(link)
    return {"path": str(p), "devices": out_devices, "links": links}
