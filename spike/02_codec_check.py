#!/usr/bin/env python3
"""Spike 2: cobertura del codec, auto-consistencia y causa del byte-diff."""
import glob
import os
import sys
import zlib

VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vendor", "packet-tracer-pkt-format")
sys.path.insert(0, os.path.normpath(VENDOR))
import pt9  # noqa: E402

SAVES = "/mnt/d/Cisco Packet Tracer 9.0.1/saves"


def try_legacy(raw):
    """Familia vieja (PT 4.1-5.3.2): layer B + qCompress, sin AEAD."""
    return pt9._quncompress(pt9._layer_b(raw))


def main():
    files = sorted(glob.glob(os.path.join(SAVES, "**", "*.pkt"), recursive=True), key=os.path.getsize)
    modern = legacy = dead = 0
    self_inconsistent = 0
    modern_examples = []
    for f in files:
        raw = open(f, "rb").read()
        xml = None
        is_modern = False
        try:
            xml = pt9.decode_bytes(raw, "pkt", verify_tag=True)
            modern += 1
            is_modern = True
            if len(modern_examples) < 3:
                modern_examples.append(f)
        except Exception:
            try:
                xml = try_legacy(raw)
                legacy += 1
            except Exception:
                dead += 1
                continue
        if is_modern:
            back = pt9.encode_bytes(xml, "pkt")
            try:
                if pt9.decode_bytes(back, "pkt") != xml:
                    self_inconsistent += 1
            except Exception:
                self_inconsistent += 1

    print(f"total .pkt         : {len(files)}")
    print(f"  modernos (AEAD)  : {modern}")
    print(f"  legado (sin AEAD): {legacy}")
    print(f"  ilegibles        : {dead}")
    print(f"re-encode auto-consistente (modern): {modern - self_inconsistent}/{modern}")

    # causa del byte-diff: probar niveles de compresion zlib en un moderno
    if modern_examples:
        f = modern_examples[0]
        raw = open(f, "rb").read()
        xml = pt9.decode_bytes(raw, "pkt")
        print(f"\nbyte-exactness en: {os.path.relpath(f, SAVES)} (raw={len(raw)})")
        for lvl in range(0, 10):
            q = pt9._qcompress(xml, lvl)
            payload = pt9._layer_b(q)
            sealed = pt9._eax_encrypt("twofish", bytes([0x89]) * 16, bytes([0x10]) * 16, payload)
            cand = pt9._layer_a_inv(sealed)
            print(f"  level {lvl}: len={len(cand)} {'EXACTO' if cand == raw else ''}")


if __name__ == "__main__":
    main()
