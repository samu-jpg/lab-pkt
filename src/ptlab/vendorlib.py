"""Acceso a las librerias del vendor `packet-tracer-pkt-format` (lab_api + codec)."""
from __future__ import annotations

import sys
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[2] / "vendor" / "packet-tracer-pkt-format"
SEED = VENDOR / "tools" / "network_seed.xml"
TEMPLATES = VENDOR / "tools" / "device_templates.json"


def lab_api():
    """Importa `lab_api` del vendor usando el codec portable (pkt_core) en vez de `pt9`."""
    for path in (str(VENDOR), str(VENDOR / "tools"), str(VENDOR / "src")):
        if path not in sys.path:
            sys.path.insert(0, path)
    from ptlab import codec

    sys.modules["pt9"] = codec
    import lab_api as api

    return api


def templates() -> tuple[dict, dict]:
    """({modelo: <DEVICE> bytes}, {modulo: <SLOT> str}) del catalogo del vendor."""
    api = lab_api()
    return api.load_templates(str(TEMPLATES))
