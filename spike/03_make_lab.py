#!/usr/bin/env python3
"""Spike 3: generar un lab minimo (R1 - SW1 - PC1/PC2) listo para abrir en PT."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.normpath(os.path.join(HERE, "..", "vendor", "packet-tracer-pkt-format"))
sys.path.insert(0, VENDOR)
sys.path.insert(0, os.path.join(VENDOR, "tools"))
import lab_api  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "/mnt/d/PT-Labs/spike_lab.pkt"


def main():
    models, modules = lab_api.load_templates(os.path.join(VENDOR, "tools", "device_templates.json"))
    seed = os.path.join(VENDOR, "tools", "network_seed.xml")
    lab = lab_api.Lab(seed, models, modules)
    lab.prune_seed_devices()

    r1 = lab.add_device("2911", "R1", 220, 250, ios_config=[
        "!", "hostname R1", "!",
        "interface GigabitEthernet0/0", " ip address 192.168.10.1 255.255.255.0", " no shutdown", "!",
        "ip dhcp pool LAN10", " network 192.168.10.0 255.255.255.0", " default-router 192.168.10.1", "!",
        "end",
    ])
    sw1 = lab.add_device("2960-24TT", "SW1", 220, 430, ios_config=[
        "!", "hostname SW1", "!", "interface Vlan1", " no shutdown", "!", "end",
    ])
    pc1 = lab.add_device("PC-PT", "PC1", 110, 600, pc_ip=("192.168.10.10", "255.255.255.0", "192.168.10.1"))
    pc2 = lab.add_device("PC-PT", "PC2", 330, 600, pc_ip=("192.168.10.11", "255.255.255.0", "192.168.10.1"))

    lab.link(r1, "GigabitEthernet0/0", sw1, "GigabitEthernet0/1")
    lab.link(sw1, "FastEthernet0/1", pc1, "FastEthernet0")
    lab.link(sw1, "FastEthernet0/2", pc2, "FastEthernet0")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    lab.save(OUT)
    print("guardado :", OUT, "->", os.path.getsize(OUT), "bytes")
    print("equipos  :", lab.device_names())


if __name__ == "__main__":
    main()
