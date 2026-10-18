"""CLI de ptlab: `build` (spec -> .pkt), `preview` (spec -> .svg), `schema`."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ptlab.builder import build
from ptlab.planner import plan
from ptlab.preview import render_svg
from ptlab.spec import load_spec, spec_json_schema


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ptlab", description="Asistente de topologias Packet Tracer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="spec -> .pkt")
    b.add_argument("spec")
    b.add_argument("-o", "--out", required=True)

    p = sub.add_parser("preview", help="spec -> .svg")
    p.add_argument("spec")
    p.add_argument("-o", "--out", required=True)

    sub.add_parser("schema", help="imprime el JSON schema de la spec")

    args = parser.parse_args(argv)

    if args.cmd == "schema":
        print(json.dumps(spec_json_schema(), indent=2, ensure_ascii=False))
        return 0

    spec = load_spec(args.spec)
    planned = plan(spec)

    if args.cmd == "preview":
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_svg(planned), encoding="utf-8")
        print(f"preview : {out}")
        return 0

    out = build(planned, args.out)
    print(f"generado: {out}")
    for d in planned.devices:
        extra = d.host_ip[0] if d.host_ip else ("DHCP" if d.dhcp else "")
        print(f"  {d.name:6s} {d.model:12s} {extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
