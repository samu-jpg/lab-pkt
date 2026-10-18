"""Acceso a las librerias del vendor `packet-tracer-pkt-format` (lab_api + codec)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[2] / "vendor" / "packet-tracer-pkt-format"
SEED = VENDOR / "tools" / "network_seed.xml"
TEMPLATES = VENDOR / "tools" / "device_templates.json"
ACTIVITY_SKELETON = VENDOR / "tools" / "activity_skeleton.xml"


def lib_path() -> Path:
    """Libreria local de plantillas (modelos cosechados de tus propios .pkt)."""
    return Path(os.environ.get("PTLAB_LIB", "~/.ptlab/device_templates.json")).expanduser()


def lab_api():
    """Importa `lab_api` del vendor usando el codec portable (pkt_core) en vez de `pt9`."""
    for path in (str(VENDOR), str(VENDOR / "tools"), str(VENDOR / "src")):
        if path not in sys.path:
            sys.path.insert(0, path)
    from ptlab import codec

    sys.modules["pt9"] = codec
    import lab_api as api

    return api


def local_templates() -> tuple[dict, dict]:
    """Plantillas de la libreria local (vacio si todavia no existe)."""
    path = lib_path()
    if not path.exists():
        return {}, {}
    api = lab_api()
    return api.load_templates(str(path))


def templates() -> tuple[dict, dict]:
    """({modelo: <DEVICE> bytes}, {modulo: <SLOT> str}): vendor con la libreria local encima."""
    api = lab_api()
    models, modules = api.load_templates(str(TEMPLATES))
    local_models, local_modules = local_templates()
    models.update(local_models)
    modules.update(local_modules)
    return models, modules
