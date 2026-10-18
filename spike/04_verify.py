#!/usr/bin/env python3
"""Spike 4: verificar el .pkt generado (equipos, cables, configs)."""
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.normpath(os.path.join(HERE, "..", "vendor", "packet-tracer-pkt-format"))
sys.path.insert(0, VENDOR)
import pt9  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "/mnt/d/PT-Labs/spike_lab.pkt"


def main():
    raw = open(OUT, "rb").read()
    xml = pt9.decode_bytes(raw, "pkt")
    print(f"archivo : {OUT} ({len(raw)} bytes, xml {len(xml)} bytes)")

    # auto-consistencia del contenedor
    back = pt9.encode_bytes(xml, "pkt")
    print(f"re-encode consistente: {pt9.decode_bytes(back, 'pkt') == xml}")

    root = ET.fromstring(xml)
    net = root.find("NETWORK")
    id2name = {}
    print("\n== EQUIPOS ==")
    for d in net.find("DEVICES").findall("DEVICE"):
        eng = d.find("ENGINE")
        model = d.findtext("ENGINE/TYPE")
        name = eng.findtext("NAME")
        sid = eng.findtext("SAVE_REF_ID")
        id2name[sid] = name
        power = eng.findtext("POWER")
        print(f"  {name:5s} model={model:12s} power={power} id={sid}")
        rc = eng.find("RUNNINGCONFIG")
        if rc is not None:
            lines = [l.text for l in rc.findall("LINE")]
            print(f"        RUNNINGCONFIG ({len(lines)} lineas): " + " | ".join(lines[:6]) + (" ..." if len(lines) > 6 else ""))
        for port in d.iter("PORT"):
            ip = port.findtext("IP")
            if ip:
                print(f"        NIC ip={ip} mask={port.findtext('SUBNET')} gw={port.findtext('PORT_GATEWAY')} dhcp={port.findtext('PORT_DHCP_ENABLE')}")

    print("\n== CABLES ==")
    for L in net.find("LINKS").findall("LINK"):
        cab = L.find("CABLE")
        a, b = cab.findtext("FROM"), cab.findtext("TO")
        ports = [p.text for p in cab.findall("PORT")]
        pa = ports[0] if len(ports) > 0 else "?"
        pb = ports[1] if len(ports) > 1 else "?"
        print(f"  {id2name.get(a, a)}:{pa}  <->  {id2name.get(b, b)}:{pb}  ({cab.findtext('TYPE')})")


if __name__ == "__main__":
    main()
