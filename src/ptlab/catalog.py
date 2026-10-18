"""Catalogo de equipos y puertos soportados en el MVP."""
from __future__ import annotations

from dataclasses import dataclass

ROUTER = "router"
SWITCH = "switch"
L3SWITCH = "l3switch"
HOST = "host"
HUB = "hub"

DEFAULT_ROUTER = "2911"
DEFAULT_SWITCH = "2960-24TT"
DEFAULT_HOST = "PC-PT"
DEFAULT_SERVER = "Server-PT"


def _fast(n: int) -> tuple[str, ...]:
    return tuple(f"FastEthernet0/{i}" for i in range(1, n + 1))


@dataclass(frozen=True)
class Model:
    name: str
    role: str
    ports: tuple[str, ...]


MODELS: dict[str, Model] = {
    # routers (interfaces arrancan en 0)
    "2911": Model("2911", ROUTER, ("GigabitEthernet0/0", "GigabitEthernet0/1", "GigabitEthernet0/2")),
    "1941": Model("1941", ROUTER, ("GigabitEthernet0/0", "GigabitEthernet0/1")),
    "2901": Model("2901", ROUTER, ("GigabitEthernet0/0", "GigabitEthernet0/1")),
    "2811": Model("2811", ROUTER, ("FastEthernet0/0", "FastEthernet0/1")),
    # switches (arrancan en 1)
    "2960-24TT": Model("2960-24TT", SWITCH, _fast(24) + ("GigabitEthernet0/1", "GigabitEthernet0/2")),
    "2950-24": Model("2950-24", SWITCH, _fast(24)),
    "3560-24PS": Model("3560-24PS", L3SWITCH, _fast(24) + ("GigabitEthernet0/1", "GigabitEthernet0/2")),
    # hosts
    "PC-PT": Model("PC-PT", HOST, ("FastEthernet0",)),
    "Server-PT": Model("Server-PT", HOST, ("FastEthernet0",)),
    "Laptop-PT": Model("Laptop-PT", HOST, ("FastEthernet0",)),
    # hub (puertos genericos "Port N", como los demas equipos sin interfaces numeradas)
    "Hub-PT": Model("Hub-PT", HUB, tuple(f"Port {i}" for i in range(6))),
}


def palette() -> dict[str, list[Model]]:
    """Modelos agrupados por rol (paleta del editor web)."""
    groups: dict[str, list[Model]] = {}
    for model in MODELS.values():
        groups.setdefault(model.role, []).append(model)
    return groups


def model_of(name: str) -> Model:
    try:
        return MODELS[name]
    except KeyError:
        raise ValueError(f"modelo no soportado: {name!r} (soportados: {', '.join(MODELS)})") from None


def access_ports(model: str) -> list[str]:
    """Puertos de acceso de un switch (donde cuelgan los hosts)."""
    m = model_of(model)
    fast = [p for p in m.ports if p.startswith("FastEthernet")]
    return fast or list(m.ports)


def uplink_ports(model: str) -> list[str]:
    """Puertos de uplink de un switch (hacia routers u otros switches)."""
    m = model_of(model)
    gig = [p for p in m.ports if p.startswith("GigabitEthernet")]
    return gig or list(m.ports)[-2:]
