"""Especificacion del lab: nodos y cables explicitos (JSON o YAML).

Cada equipo, cable, IP, VLAN y ruta los define quien usa el MCP (o el CLI): la spec no
trae plantillas ni topologias preajustadas. El planner solo autocompleta lo que falte
(layout, config IOS desde los datos del nodo, rutas calculadas sobre el propio grafo).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Routing = Literal["none", "static", "rip", "ospf", "eigrp", "bgp"]


class NodeInterface(BaseModel):
    """Una interfaz de un nodo.

    - `ip`: direccion en CIDR (ej. "192.168.1.1/24"); en switches "Vlan10" actua de SVI.
    - `dot1q`: subinterfaz trunk (router-on-a-stick); el puerto va como "GigabitEthernet0/1.10".
    - `helper`: IP del servidor DHCP para `ip helper-address` en esa interfaz.
    """

    port: str
    ip: str | None = None
    dot1q: int | None = Field(default=None, ge=1, le=4094)
    helper: str | None = None


class NodeVlan(BaseModel):
    id: int = Field(ge=1, le=4094)
    name: str | None = None


class AccessPort(BaseModel):
    """Puerto de switch en modo access sobre una VLAN."""

    port: str
    vlan: int = Field(ge=1, le=4094)


class PoolSpec(BaseModel):
    """Pool DHCP de un Server-PT."""

    name: str | None = None
    network: str
    gateway: str
    dns: str | None = None
    start_ip: str | None = None


class NodeSpec(BaseModel):
    """Un equipo del lab (router, switch, host, hub...).

    Campos por rol:
    - routers / switch L3: `interfaces` (ip, dot1q, helper), `routing`, `dhcp`, `as_number`, `config`.
    - switches L2: `vlans`, `access`, `trunks`, `interfaces` (SVI "Vlan10"), `config`.
    - hosts: `ip` + `gateway` (estatico) o `dhcp: true`.
    - Server-PT: `pools` (servicio DHCP del equipo).
    - `x`/`y`: posicion en el plano; si falta, el planner reparte por capas.
    """

    name: str
    model: str
    x: float | None = None
    y: float | None = None
    ip: str | None = None
    gateway: str | None = None
    dhcp: bool = False
    interfaces: list[NodeInterface] = []
    vlans: list[NodeVlan] = []
    access: list[AccessPort] = []
    trunks: list[str] = []
    pools: list[PoolSpec] = []
    routing: Routing | None = None
    as_number: int | None = Field(default=None, ge=1, le=65535)
    config: list[str] = []

    @field_validator("model", mode="before")
    @classmethod
    def _model_as_text(cls, value: object) -> object:
        return str(value) if isinstance(value, (int, float)) else value


class LinkSpec(BaseModel):
    """Un cable entre dos nodos, con el puerto exacto de cada extremo."""

    a: str
    a_port: str
    b: str
    b_port: str
    cable: Literal["straight", "crossover", "serial"] = "straight"
    dce: str | None = None


class Spec(BaseModel):
    """Spec del lab: `nodes` (equipos) + `links` (cables), todo explicito."""

    name: str = "lab"
    routing: Routing = "none"
    ospf_process: int = 1
    ospf_area: int = 0
    eigrp_as: int = Field(default=100, ge=1, le=65535)
    bgp_as_base: int = Field(default=65000, ge=1, le=65535)
    dns: str = "8.8.8.8"
    nodes: list[NodeSpec] = []
    links: list[LinkSpec] = []

    @model_validator(mode="after")
    def _needs_nodes(self) -> "Spec":
        if not self.nodes:
            raise ValueError("la spec necesita `nodes`: aca no hay plantillas de topologia")
        return self


def parse_spec(text: str) -> Spec:
    """Parsea una spec desde texto YAML o JSON."""
    stripped = text.strip()
    if stripped.startswith("{"):
        data = json.loads(stripped)
    else:
        import yaml

        data = yaml.safe_load(stripped)
    return Spec.model_validate(data)


def load_spec(path: str | Path) -> Spec:
    return parse_spec(Path(path).read_text(encoding="utf-8"))


def spec_json_schema() -> dict:
    return Spec.model_json_schema()
