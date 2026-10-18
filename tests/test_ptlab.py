import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor" / "packet-tracer-pkt-format"))
sys.path.insert(0, str(ROOT / "vendor" / "packet-tracer-pkt-format" / "src"))

from ptlab.builder import build  # noqa: E402
from ptlab.planner import plan  # noqa: E402
from ptlab.spec import parse_spec  # noqa: E402

TWO = """
name: t
routing: ospf
dhcp: true
sites:
  - {name: S1, lan: 192.168.1.0/24, hosts: 2}
  - {name: S2, lan: 192.168.2.0/24, hosts: 1}
"""


def test_router_config_ospf_dhcp():
    p = plan(parse_spec(TWO))
    cfg = p.device("R1").config
    assert any("ip address 192.168.1.1 255.255.255.0" in line for line in cfg)
    assert "router ospf 1" in cfg
    assert any(line.startswith("ip dhcp pool") for line in cfg)
    assert p.device("PC1").dhcp is True


def test_hosts_static_addressing():
    spec = "name: s\nsites:\n  - {name: S1, lan: 192.168.5.0/24, hosts: 2}\n"
    p = plan(parse_spec(spec))
    assert p.device("PC1").host_ip == ("192.168.5.2", "255.255.255.0", "192.168.5.1")
    assert p.device("PC2").host_ip[0] == "192.168.5.3"


def test_static_routes_line():
    spec = (
        "name: s\nrouting: static\nsites:\n"
        "  - {name: A, lan: 192.168.10.0/24, hosts: 1}\n"
        "  - {name: B, lan: 192.168.20.0/24, hosts: 1}\n"
        "  - {name: C, lan: 192.168.30.0/24, hosts: 1}\n"
    )
    p = plan(parse_spec(spec))
    r1, r2 = p.device("R1").config, p.device("R2").config
    assert any(line.startswith("ip route 192.168.20.0") for line in r1)
    assert any(line.startswith("ip route 192.168.30.0") for line in r1)
    assert any(line.startswith("ip route 192.168.10.0") for line in r2)


def test_build_is_valid_container(tmp_path):
    import pt9

    out = build(plan(parse_spec(TWO)), tmp_path / "t.pkt")
    xml = pt9.decode_bytes(out.read_bytes(), "pkt")
    assert b"PACKETTRACER5" in xml[:200]
    assert b'<NAME translate="true">R1</NAME>' in xml


def _sites(n):
    return "".join(f"  - {{name: S{i}, lan: 192.168.{i}.0/24, hosts: 1}}\n" for i in range(1, n + 1))


def test_ring_adds_closing_link():
    p = plan(parse_spec("name: r\ntopology: ring\nsites:\n" + _sites(4)))
    wan = [l for l in p.links if l.a.startswith("R") and l.b.startswith("R")]
    assert len(wan) == 4


def test_star_port_limit_raises():
    import pytest

    spec = "name: s\ntopology: star\nsites:\n" + _sites(4)
    with pytest.raises(ValueError):
        plan(parse_spec(spec))


def test_preview_icons_and_aggregation():
    from ptlab.preview import render_svg

    svg = render_svg(plan(parse_spec(TWO)))
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")

    many = "name: h\nsites:\n  - {name: S1, lan: 192.168.7.0/24, hosts: 8}\n"
    assert "x8 equipos" in render_svg(plan(parse_spec(many)))


THREE = "name: t\nrouting: PROTO\nsites:\n" + _sites(3)


def test_rip_uses_classful_networks():
    cfg = plan(parse_spec(THREE.replace("PROTO", "rip"))).device("R1").config
    assert "router rip" in cfg and " version 2" in cfg and " no auto-summary" in cfg
    assert " network 10.0.0.0" in cfg and " network 192.168.1.0" in cfg


def test_eigrp_config():
    cfg = plan(parse_spec(THREE.replace("PROTO", "eigrp"))).device("R1").config
    assert "router eigrp 100" in cfg
    assert " network 192.168.1.0 0.0.0.255" in cfg
    assert " network 10.0.0.0 0.0.0.3" in cfg


def test_bgp_neighbors_and_as_numbers():
    spec = (
        "name: b\nrouting: bgp\ntopology: line\nsites:\n"
        "  - {name: A, lan: 192.168.1.0/24, hosts: 1, as_number: 65100}\n"
        "  - {name: B, lan: 192.168.2.0/24, hosts: 1, as_number: 65200}\n"
    )
    cfg = plan(parse_spec(spec)).device("R1").config
    assert "router bgp 65100" in cfg
    assert " neighbor 10.0.0.2 remote-as 65200" in cfg
    assert " network 192.168.1.0 mask 255.255.255.0" in cfg


def test_new_topologies_edge_counts():
    tree = plan(parse_spec("name: t\ntopology: tree\nsites:\n" + _sites(3)))
    assert len([l for l in tree.links if l.a.startswith("R") and l.b.startswith("R")]) == 2

    grid = plan(parse_spec("name: g\ntopology: grid\nsites:\n" + _sites(4)))
    assert len([l for l in grid.links if l.a.startswith("R") and l.b.startswith("R")]) == 4

    dual = plan(parse_spec("name: d\ntopology: dual_star\nsites:\n" + _sites(3)))
    assert len([l for l in dual.links if l.a.startswith("R") and l.b.startswith("R")]) == 3


def test_l3_switch_as_router():
    spec = (
        "name: l3\ntopology: grid\nsites:\n"
        + "".join(f"  - {{name: S{i}, lan: 192.168.{i}.0/24, hosts: 1, router_model: 3560-24PS}}\n" for i in range(1, 5))
    )
    cfg = plan(parse_spec(spec)).device("R1").config
    assert "ip routing" in cfg and " no switchport" in cfg


def test_numeric_model_names_are_text():
    spec = "name: n\nsites:\n  - {name: S1, lan: 192.168.1.0/24, hosts: 1, router_model: 2911}\n"
    assert plan(parse_spec(spec)).device("R1").model == "2911"


RELAY = (
    "name: guia\nrouting: none\ndhcp: true\nsites:\n"
    "  - name: RouterC\n    router_model: 2811\n    lans:\n"
    "      - {name: LAN_Izquierda, lan: 192.168.1.0/24, hosts: 1, dhcp: true}\n"
    "      - {name: LAN_Derecha, lan: 192.168.2.0/24, hosts: 1, dhcp: true, dhcp_server: true}\n"
)


def test_dhcp_relay_helper_only_on_remote_lan():
    cfg = plan(parse_spec(RELAY)).device("R1").config
    assert " ip helper-address 192.168.2.100" in cfg
    assert "helper" not in cfg[cfg.index("interface FastEthernet0/1"):]
    assert " ip address 192.168.1.1 255.255.255.0" in cfg
    assert " ip address 192.168.2.1 255.255.255.0" in cfg


def test_dhcp_server_pools_and_clients():
    p = plan(parse_spec(RELAY))
    srv = p.device("DHCP-Server")
    assert srv.host_ip == ("192.168.2.100", "255.255.255.0", "192.168.2.1")
    assert [pool.name for pool in srv.service_pools] == ["Pool_LAN_Izquierda", "serverPool"]
    left = next(pool for pool in srv.service_pools if pool.name == "Pool_LAN_Izquierda")
    assert (left.network, left.mask, left.gateway, left.start_ip) == (
        "192.168.1.0", "255.255.255.0", "192.168.1.1", "192.168.1.10",
    )
    assert p.device("PC1").dhcp and p.device("PC2").dhcp
    assert not any(line.startswith("ip dhcp pool") for line in p.device("R1").config)


def test_build_writes_dhcp_service(tmp_path):
    out = build(plan(parse_spec(RELAY)), tmp_path / "g.pkt")
    import pt9

    xml = pt9.decode_bytes(out.read_bytes(), "pkt").decode("utf-8", "replace")
    assert "<NAME>Pool_LAN_Izquierda</NAME>" in xml
    assert "<START_IP>192.168.1.10</START_IP>" in xml
    assert "<ENABLED>1</ENABLED>" in xml
    assert "ip helper-address 192.168.2.100" in xml


def test_multi_lan_port_limit():
    import pytest

    spec = (
        "name: m\ntopology: line\nsites:\n"
        "  - name: A\n    router_model: 2811\n    lans:\n"
        "      - {name: L1, lan: 192.168.1.0/24, hosts: 0}\n"
        "      - {name: L2, lan: 192.168.2.0/24, hosts: 0}\n"
        "  - name: B\n    lan: 192.168.3.0/24\n    hosts: 0\n"
    )
    with pytest.raises(ValueError):
        plan(parse_spec(spec))


# ---------------------------- modo grafo (nodos y cables) --------------------------- #

GRAPH = """
name: g
routing: ospf
nodes:
  - {name: R1, model: 2911, interfaces: [{port: GigabitEthernet0/0, ip: 10.0.0.1/30}]}
  - {name: SW1, model: 2960-24TT}
  - {name: PC1, model: PC-PT, ip: 192.168.1.10/24, gateway: 192.168.1.1}
links:
  - {a: R1, a_port: GigabitEthernet0/0, b: SW1, b_port: GigabitEthernet0/1}
  - {a: PC1, a_port: FastEthernet0, b: SW1, b_port: FastEthernet0/1}
"""

VLAN_GRAPH = """
name: v
routing: ospf
nodes:
  - name: R1
    model: 2911
    interfaces:
      - {port: GigabitEthernet0/1.10, ip: 192.168.10.1/24, dot1q: 10}
  - name: SW1
    model: 2960-24TT
    vlans: [{id: 10, name: VENTAS}]
    access: [{port: FastEthernet0/1, vlan: 10}]
    trunks: [GigabitEthernet0/1]
  - {name: PC1, model: PC-PT, ip: 192.168.10.10/24}
links:
  - {a: R1, a_port: GigabitEthernet0/1, b: SW1, b_port: GigabitEthernet0/1}
  - {a: PC1, a_port: FastEthernet0, b: SW1, b_port: FastEthernet0/1}
"""


def test_spec_two_modes_are_exclusive():
    import pytest

    with pytest.raises(ValueError):
        parse_spec("name: x\nnodes: [{name: A, model: PC-PT}]\nsites: [{name: S1}]\n")
    with pytest.raises(ValueError):
        parse_spec("name: x\n")


def test_plan_graph_basic():
    p = plan(parse_spec(GRAPH))
    assert [d.name for d in p.devices] == ["R1", "SW1", "PC1"]
    assert p.device("PC1").host_ip == ("192.168.1.10", "255.255.255.0", "192.168.1.1")
    assert len(p.links) == 2
    assert any("ip address 10.0.0.1 255.255.255.252" in line for line in p.device("R1").config)


def test_plan_graph_auto_layout_by_role():
    p = plan(parse_spec(GRAPH))
    assert p.device("R1").y < p.device("SW1").y < p.device("PC1").y


def test_plan_graph_duplicate_port_raises():
    import pytest

    spec = GRAPH.replace("b_port: FastEthernet0/1", "b_port: GigabitEthernet0/1")
    with pytest.raises(ValueError, match="ya esta usado"):
        plan(parse_spec(spec))


def test_plan_graph_unknown_port_raises():
    import pytest

    spec = GRAPH.replace("a_port: GigabitEthernet0/0, b: SW1", "a_port: GigabitEthernet0/9, b: SW1")
    with pytest.raises(ValueError, match="no existe"):
        plan(parse_spec(spec))


def test_plan_graph_vlan_trunk_and_dot1q():
    p = plan(parse_spec(VLAN_GRAPH))
    sw = p.device("SW1").config
    assert "vlan 10" in sw and " name VENTAS" in sw
    assert " switchport mode access" in sw and " switchport access vlan 10" in sw
    assert " switchport mode trunk" in sw
    r1 = p.device("R1").config
    assert "interface GigabitEthernet0/1.10" in r1
    assert " encapsulation dot1Q 10" in r1
    assert " ip address 192.168.10.1 255.255.255.0" in r1
    assert " network 192.168.10.0 0.0.0.255 area 0" in r1  # OSPF anuncia la subinterfaz


def test_plan_graph_svi_gestion():
    spec = (
        "name: s\nnodes:\n"
        "  - name: SW1\n    model: 2960-24TT\n    vlans: [{id: 10}]\n"
        "    interfaces: [{port: Vlan10, ip: 192.168.10.2/24}]\n"
    )
    cfg = plan(parse_spec(spec)).device("SW1").config
    assert "interface Vlan10" in cfg and " ip address 192.168.10.2 255.255.255.0" in cfg


def test_plan_graph_access_vlan_undeclared_raises():
    import pytest

    spec = VLAN_GRAPH.replace("vlans: [{id: 10, name: VENTAS}]", "vlans: []")
    with pytest.raises(ValueError, match="declara primero"):
        plan(parse_spec(spec))


def test_plan_graph_static_routes():
    spec = (
        "name: s\nrouting: static\nnodes:\n"
        "  - {name: R1, model: 2911, interfaces: [{port: GigabitEthernet0/0, ip: 10.0.0.1/30},"
        " {port: GigabitEthernet0/1, ip: 192.168.1.1/24}]}\n"
        "  - {name: R2, model: 2911, interfaces: [{port: GigabitEthernet0/0, ip: 10.0.0.2/30},"
        " {port: GigabitEthernet0/1, ip: 192.168.2.1/24}]}\n"
        "links:\n  - {a: R1, a_port: GigabitEthernet0/0, b: R2, b_port: GigabitEthernet0/0}\n"
    )
    p = plan(parse_spec(spec))
    assert "ip route 192.168.2.0 255.255.255.0 10.0.0.2" in p.device("R1").config
    assert "ip route 192.168.1.0 255.255.255.0 10.0.0.1" in p.device("R2").config


def test_plan_graph_router_dhcp_pools():
    spec = (
        "name: d\nnodes:\n"
        "  - {name: R1, model: 2911, dhcp: true, interfaces: [{port: GigabitEthernet0/1, ip: 192.168.1.1/24}]}\n"
        "  - {name: PC1, model: PC-PT, dhcp: true}\n"
        "links:\n  - {a: PC1, a_port: FastEthernet0, b: R1, b_port: GigabitEthernet0/1}\n"
    )
    p = plan(parse_spec(spec))
    cfg = p.device("R1").config
    assert any(line.startswith("ip dhcp pool") for line in cfg)
    assert " network 192.168.1.0 255.255.255.0" in cfg
    assert " default-router 192.168.1.1" in cfg
    assert p.device("PC1").dhcp is True


def test_plan_graph_server_pools():
    spec = (
        "name: srv\nnodes:\n"
        "  - name: SRV1\n    model: Server-PT\n    ip: 192.168.2.100/24\n    gateway: 192.168.2.1\n"
        "    pools: [{network: 192.168.1.0/24, gateway: 192.168.1.1}, {network: 192.168.2.0/24, gateway: 192.168.2.1}]\n"
    )
    srv = plan(parse_spec(spec)).device("SRV1")
    assert [pool.name for pool in srv.service_pools] == ["pool1", "pool2"]
    assert srv.service_pools[0].start_ip == "192.168.1.10"
    assert srv.host_ip == ("192.168.2.100", "255.255.255.0", "192.168.2.1")


def test_plan_graph_hub():
    spec = (
        "name: h\nnodes:\n"
        "  - {name: H1, model: Hub-PT}\n"
        "  - {name: PC1, model: PC-PT, ip: 192.168.5.10/24}\n"
        "  - {name: PC2, model: PC-PT, ip: 192.168.5.11/24}\n"
        "links:\n"
        "  - {a: PC1, a_port: FastEthernet0, b: H1, b_port: 'Port 0'}\n"
        "  - {a: PC2, a_port: FastEthernet0, b: H1, b_port: 'Port 1'}\n"
    )
    p = plan(parse_spec(spec))
    assert p.device("H1").config == []
    assert p.device("H1").role == "hub"


def test_plan_graph_helper_relay():
    spec = (
        "name: r\nnodes:\n"
        "  - {name: R1, model: 2911, interfaces: [{port: GigabitEthernet0/1, ip: 192.168.1.1/24,"
        " helper: 192.168.2.100}]}\n"
    )
    assert " ip helper-address 192.168.2.100" in plan(parse_spec(spec)).device("R1").config


def test_plan_graph_serial_not_supported():
    import pytest

    spec = GRAPH.replace("b_port: GigabitEthernet0/1", "b_port: GigabitEthernet0/1, cable: serial")
    with pytest.raises(ValueError, match="serial"):
        plan(parse_spec(spec))


def test_plan_graph_build_end_to_end(tmp_path):
    import pt9

    out = build(plan(parse_spec(VLAN_GRAPH)), tmp_path / "g.pkt")
    xml = pt9.decode_bytes(out.read_bytes(), "pkt").decode("utf-8", "replace")
    assert "switchport access vlan 10" in xml
    assert "encapsulation dot1Q 10" in xml
    assert "interface GigabitEthernet0/1.10" in xml


def test_plan_graph_crossover_cable(tmp_path):
    import pt9

    spec = GRAPH.replace("b_port: FastEthernet0/1", "b_port: FastEthernet0/1, cable: crossover")
    out = build(plan(parse_spec(spec)), tmp_path / "x.pkt")
    xml = pt9.decode_bytes(out.read_bytes(), "pkt").decode("utf-8", "replace")
    assert "eCrossOver" in xml
