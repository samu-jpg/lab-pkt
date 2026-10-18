"""Actividades `.pka`: consigna, password, permisos, timer y redes inicial/respuesta.

Arma el `.pka` desde el esqueleto del vendor (`activity_skeleton.xml`) inyectando dos `.pkt`:
el de practica (red inicial) y el resuelto (red de respuesta, opcional). El arbol de
correccion (scoring) queda afuera: el vendor lo deriva de nodos de una actividad de
referencia, asi que se agrega cuando haya una a mano.
"""
from __future__ import annotations

from pathlib import Path

from ptlab import codec
from ptlab.vendorlib import ACTIVITY_SKELETON, lab_api


def _api():
    lab_api()
    import activity as vendor_activity

    return vendor_activity


def new_activity(
    initial: str | Path,
    out: str | Path,
    answer: str | Path | None = None,
    instructions: list[str] | None = None,
    title: str = "",
    password: str = "",
    locked: bool = False,
    noguest: bool = False,
    components: str = "",
    timer: int = 0,
) -> Path:
    """Genera el `.pka` a partir de la red inicial (`initial`) y la resuelta (`answer`).

    - `instructions`: paginas HTML de la consigna.
    - `password`: clave que Packet Tracer pide al abrir.
    - `components`: componentes corregibles disponibles (ej. "Ip, Routing, Acl").
    - `timer`: cuenta regresiva en segundos (0 = sin timer).
    """
    for src in (initial, answer):
        if src is not None and not Path(src).exists():
            raise ValueError(f"no existe {src}: genera el .pkt primero")
    api = _api()
    act = api.Activity(str(ACTIVITY_SKELETON))
    if instructions:
        act.set_instructions(list(instructions), title=title)
    if password:
        act.set_password(password)
    if locked or noguest or components:
        act.set_permissions(
            locked=locked or None,
            noguest=noguest or None,
            component_list=components or None,
        )
    if timer:
        act.set_timer(True, timer)
    act.set_networks(
        initial_xml=codec.decode(initial),
        answer_xml=codec.decode(answer) if answer else None,
    )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    act.save(str(out))
    return out
