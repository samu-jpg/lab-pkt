"""Web local de ptlab: editor visual de topologias (sin IA) + modo rapido.

- `/` sirve la UI con dos pestanas: **Editor** (grafo explicito) y **Rapido** (N sedes).
- `/api/preview|normalize|generate|download` sirven ambos modos (la spec despacha sola).
- `/api/models` y `/api/icons`: catalogo e iconos PT para la paleta del editor.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ptlab.builder import build  # noqa: E402
from ptlab.catalog import MODELS, palette  # noqa: E402
from ptlab.planner import plan  # noqa: E402
from ptlab.preview import icon_data_uris, render_svg  # noqa: E402
from ptlab.spec import parse_spec  # noqa: E402

OUT_DIR = Path(os.environ.get("PTLAB_OUT_DIR", "/mnt/d/PT-Labs"))
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="ptlab")


class _NoCacheStatic(StaticFiles):
    """Sirve los estaticos siempre frescos: es una app local y evita cache vieja del navegador."""

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp


app.mount("/static", _NoCacheStatic(directory=STATIC), name="static")


class SpecIn(BaseModel):
    spec: str
    name: str = "lab"


def _safe_name(name: str) -> str:
    return Path(name).name or "lab"


def _plan_or_400(spec: str):
    try:
        return plan(parse_spec(spec))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"{type(exc).__name__}: {exc}") from exc


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(
        (STATIC / "index.html").read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/api/models")
def api_models() -> dict:
    """Catalogo de equipos para la paleta del editor: modelos por rol y sus puertos."""
    groups: dict[str, list[dict]] = {}
    for role, models in palette().items():
        groups[role] = [{"name": m.name, "ports": list(m.ports)} for m in models]
    return {"groups": groups, "count": len(MODELS)}


@app.get("/api/icons")
def api_icons() -> dict:
    """Iconos PT por modelo (data-URI PNG) para el canvas del editor."""
    return {"icons": icon_data_uris()}


@app.post("/api/preview")
def api_preview(inp: SpecIn) -> Response:
    return Response(render_svg(_plan_or_400(inp.spec)), media_type="image/svg+xml")


@app.post("/api/normalize")
def api_normalize(inp: SpecIn) -> dict:
    """Spec validada y canonica (mismos defaults que usa el motor)."""
    try:
        spec = parse_spec(inp.spec)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"{type(exc).__name__}: {exc}") from exc
    return {"spec": json.loads(spec.model_dump_json())}


@app.post("/api/generate")
def api_generate(inp: SpecIn) -> dict:
    name = _safe_name(inp.name)
    planned = _plan_or_400(inp.spec)
    try:
        out = build(planned, OUT_DIR / f"{name}.pkt")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
    return {"file": str(out), "download": f"/api/download/{name}.pkt"}


@app.get("/api/download/{name}")
def api_download(name: str) -> FileResponse:
    path = OUT_DIR / _safe_name(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="archivo no encontrado")
    return FileResponse(path, filename=path.name)
