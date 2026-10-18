#!/usr/bin/env python3
"""Spike 5: generar con el codec Python puro y validar con el codec de referencia (pt9)."""
import os
import sys
from pathlib import Path

os.environ["PKT_CORE_BACKEND"] = "pure"
os.environ["PKT_CORE_DISABLE_RUST"] = "1"

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "packet-tracer-pkt-format"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(VENDOR))
sys.path.insert(0, str(VENDOR / "src"))

import pt9 as reference_codec  # noqa: E402  (codec independiente, con libgcrypt)

from pkt_core import decode_bytes as pc_decode  # noqa: E402
from ptlab.builder import build  # noqa: E402
from ptlab.planner import plan  # noqa: E402
from ptlab.spec import parse_spec  # noqa: E402


def main() -> None:
    spec = parse_spec(
        "name: spike\nrouting: ospf\nnodes:\n"
        "  - {name: R1, model: 2911, interfaces: [{port: GigabitEthernet0/0, ip: 10.0.0.1/30}]}\n"
        "  - {name: R2, model: 2911, interfaces: [{port: GigabitEthernet0/0, ip: 10.0.0.2/30}]}\n"
        "links:\n  - {a: R1, a_port: GigabitEthernet0/0, b: R2, b_port: GigabitEthernet0/0}\n"
    )
    out = build(plan(spec), "/tmp/ptlab_pure.pkt")
    raw = out.read_bytes()

    xml_ref = reference_codec.decode_bytes(raw, "pkt")
    xml_pc = pc_decode(raw).xml
    print(f"archivo      : {out} ({len(raw)} bytes)")
    print(f"pt9 valida   : SI (root {reference_codec._root_tag(xml_ref)})")
    print(f"coincide XML : {xml_ref == xml_pc}")
    print(f"equipos      : {xml_ref.count(b'<DEVICE>')}  enlaces: {xml_ref.count(b'<LINK>')}")

    back = reference_codec.encode_bytes(xml_ref, "pkt")
    print(f"re-encode pt9: {len(back)} bytes | decodifica: {len(reference_codec.decode_bytes(back, 'pkt')) > 0}")


if __name__ == "__main__":
    main()
