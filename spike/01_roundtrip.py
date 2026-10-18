#!/usr/bin/env python3
"""Spike 1: verificar el codec contra .pkt reales de Packet Tracer 9.0.1."""
import glob
import os
import sys

VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vendor", "packet-tracer-pkt-format")
sys.path.insert(0, os.path.normpath(VENDOR))
import pt9  # noqa: E402

SAVES = "/mnt/d/Cisco Packet Tracer 9.0.1/saves"


def main():
    files = sorted(glob.glob(os.path.join(SAVES, "**", "*.pkt"), recursive=True), key=os.path.getsize)
    print(f"archivos .pkt encontrados: {len(files)}")
    if not files:
        raise SystemExit("no hay .pkt en el saves de PT")

    sample = files[:15]
    ok = 0
    for f in sample:
        rel = os.path.relpath(f, SAVES)
        try:
            raw = open(f, "rb").read()
            xml = pt9.decode_bytes(raw, "pkt")
            back = pt9.encode_bytes(xml, "pkt")
            same = back == raw
            ok += same
            print(f"{'OK  ' if same else 'DIFF'} {rel:55s} size={len(raw):>7} xml={len(xml):>8}")
        except Exception as e:  # noqa: BLE001
            print(f"ERR  {rel:55s} {type(e).__name__}: {e}")
    print(f"\nroundtrip exacto: {ok}/{len(sample)}")


if __name__ == "__main__":
    main()
