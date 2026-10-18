"""Libreria local de plantillas: cosecha equipos desde tus propios .pkt.

`harvest` busca los `<DEVICE>` de los .pkt que le pases y los mergea en `PTLAB_LIB`
(por defecto `~/.ptlab/device_templates.json`, mismo formato que el catalogo del vendor).
Desde ahi `lab.add_device` acepta esos modelos igual que los de fabrica.
"""
from __future__ import annotations

import base64
import gzip
import json
import re
from pathlib import Path

from ptlab import codec
from ptlab.vendorlib import lib_path, local_templates


def harvest(source: str | Path, wanted: set[str] | None = None, save: bool = True) -> dict:
    """Cosecha los modelos de un .pkt (o carpeta de .pkt) y los guarda en la libreria local.

    Devuelve {"models": nombres cosechados, "new": los que no estaban, "path": la libreria}.
    """
    src = Path(source).expanduser()
    if not src.exists():
        raise ValueError(f"no existe {src}")
    files = sorted(src.rglob("*.pkt")) if src.is_dir() else [src]
    found: dict[str, bytes] = {}
    for f in files:
        try:
            xml = codec.decode(f)
        except Exception:
            continue
        for m in re.finditer(rb"<DEVICE>.*?</DEVICE>", xml, re.S):
            blk = m.group(0)
            mm = re.search(rb'<TYPE[^>]*model="([^"]*)"', blk)
            if not mm:
                continue
            model = mm.group(1).decode()
            if wanted and model not in wanted:
                continue
            found.setdefault(model, blk)
    if not found:
        raise ValueError(f"{src}: no se encontraron equipos para cosechar")
    current_models, _modules = local_templates()
    new = sorted(m for m in found if m not in current_models)
    if save:
        _save(found)
    return {"models": sorted(found), "new": new, "path": str(lib_path())}


def _save(models: dict[str, bytes]) -> Path:
    path = lib_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.setdefault("gz", True)
    data.setdefault("models", {})
    data.setdefault("modules", {})
    for model, blob in models.items():
        data["models"][model] = base64.b64encode(gzip.compress(blob, 9)).decode("ascii")
    path.write_text(json.dumps(data), encoding="utf-8")
    return path
