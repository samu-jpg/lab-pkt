"""Especificacion de topologia: la entrada del asistente (JSON o YAML).

Dos modos en la misma spec:
- `sites`: topologia parametrica (N sedes, cada una router + LANs) — el modo "rapido".
- `nodes` + `links`: grafo explicito (cada equipo y cada cable definidos a mano).

Con `nodes` se usa el modo grafo; con `sites`, el modo rapido. No se pueden mezclar.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ptlab.catalog import DEFAULT_HOST, DEFAULT_ROUTER, DEFAULT_SWITCH

Routing = Literal["none", "static", "rip", "ospf", "eigrp", "bgp"]


class LanSpec(BaseModel):
    """Una LAN: switch + hosts colgados de un puerto del router.

    Con `dhcp_server: true` la LAN aloja el Server-PT y el resto de las LANs quedan
    como relay (`ip helper-address`).
    """

    name: str | None = None
    lan: str | None = None
    hosts: int = Field(default=2, ge=0, le=24)
    dhcp: bool | None = None
    dhcp_server: bool = False


class SiteSpec(BaseModel):
    """Una sede: un router con una o mas LANs."""

    name: str
    as_number: int | None = Field(default=None, ge=1, le=65535)
    router_model: str = DEFAULT_ROUTER
    switch_model: str = DEFAULT_SWITCH
    host_model: str = DEFAULT_HOST
    hosts: int = Field(default=2, ge=0, le=24)
    lan: str | None = None
    dhcp: bool | None = None
    dhcp_server: bool = False
    lans: list[LanSpec] = []

    @field_validator("router_model", "switch_model", "host_model", mode="before")
    @classmethod
    def _model_as_text(cls, value: object) -> object:
        """`router_model: 2911` en YAML llega como numero; los modelos son texto."""
        return str(value) if isinstance(value, (int, float)) else value

    def lan_list(self) -> list[LanSpec]:
        """LANs de la sede; sin `lans` se usa la LAN unica de lan/hosts/dhcp."""
        if self.lans:
            return self.lans
        return [LanSpec(lan=self.lan, hosts=self.hosts, dhcp=self.dhcp, dhcp_server=self.dhcp_server)]


class NodeInterface(BaseModel):
    """Una interfaz de un nodo del grafo.

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
    """Pool DHCP de un Server-PT del grafo."""

    name: str | None = None
    network: str
    gateway: str
    dns: str | None = None
    start_ip: str | None = None


class NodeSpec(BaseModel):
    """Un equipo del grafo (router, switch, host, hub...).

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
    """Spec completa de la topologia.

    Modo rapido (`sites`): direccionamiento y layout automaticos.
    Modo grafo (`nodes`+`links`): todo explicito; el planner solo autocompleta
    lo que falte (layout, config IOS desde los datos, rutas sobre el grafo).
    """

    name: str = "lab"
    routing: Routing = "none"
    ospf_process: int = 1
    ospf_area: int = 0
    eigrp_as: int = Field(default=100, ge=1, le=65535)
    bgp_as_base: int = Field(default=65000, ge=1, le=65535)
    dhcp: bool = False
    dns: str = "8.8.8.8"
    lan_base: str = "192.168.0.0/16"
    link_base: str = "10.0.0.0/16"
    topology: Literal[
        "line", "ring", "star", "mesh", "ladder", "tree", "grid", "dual_star"
    ] = "line"
    sites: list[SiteSpec] = []
    nodes: list[NodeSpec] = []
    links: list[LinkSpec] = []

    @model_validator(mode="after")
    def _one_mode(self) -> "Spec":
        if self.nodes and self.sites:
            raise ValueError("la spec no puede tener `sites` y `nodes` a la vez")
        if not self.nodes and not self.sites:
            raise ValueError("la spec necesita `nodes` (modo grafo) o `sites` (modo rapido)")
        return self

    def is_graph(self) -> bool:
        return bool(self.nodes)

    def lan_dhcp(self, lan: LanSpec) -> bool:
        return self.dhcp if lan.dhcp is None else lan.dhcp


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
