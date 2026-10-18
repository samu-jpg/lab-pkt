"""Codec .pkt/.pka sobre pkt_core (Python puro: corre sin libgcrypt ni binarios).

Expone la misma interfaz que `pt9` (la que usa el `lab_api` del vendor), para poder
usarlo como reemplazo portable. Se deja `pkt_core` en el path por su cuenta.
"""
from __future__ import annotations

import sys
from pathlib import Path

_VENDOR = Path(__file__).resolve().parents[2] / "vendor" / "packet-tracer-pkt-format"
for _path in (str(_VENDOR / "src"), str(_VENDOR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from pkt_core import PacketTracerError
from pkt_core import decode as _decode
from pkt_core import decode_bytes as _decode_bytes
from pkt_core import encode as _encode
from pkt_core import encode_bytes as _encode_bytes

__all__ = ["FORMATS", "PacketTracerError", "decode", "decode_bytes", "encode", "encode_bytes"]

FORMATS = {
    "pkt": ("twofish", 0x89, 0x10),
    "pka": ("twofish", 0x89, 0x10),
}


def decode(path: str | Path, fmt: str = "pkt", verify_tag: bool = True) -> bytes:
    return _decode(path, fmt, verify_tag=verify_tag).xml


def decode_bytes(raw: bytes, fmt: str = "pkt", verify_tag: bool = True) -> bytes:
    return _decode_bytes(raw, fmt, verify_tag=verify_tag).xml


def encode(path: str | Path, xml: bytes, fmt: str = "pkt") -> None:
    _encode(path, xml, fmt)


def encode_bytes(xml: bytes, fmt: str = "pkt") -> bytes:
    return _encode_bytes(xml, fmt)
