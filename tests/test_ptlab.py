import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor" / "packet-tracer-pkt-format"))
sys.path.insert(0, str(ROOT / "vendor" / "packet-tracer-pkt-format" / "src"))

from ptlab.builder import build  # noqa: E402
from ptlab.planner import plan  # noqa: E402
from ptlab.spec import parse_spec  # noqa: E402

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


def test_spec_requires_nodes():
    import pytest

    with pytest.raises(ValueError):
        parse_spec("name: x\n")
    assert parse_spec("name: x\nnodes: [{name: A, model: PC-PT}]\n").nodes[0].name == "A"


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


def test_build_is_valid_container(tmp_path):
    import pt9

    out = build(plan(parse_spec(GRAPH)), tmp_path / "t.pkt")
    xml = pt9.decode_bytes(out.read_bytes(), "pkt")
    assert b"PACKETTRACER5" in xml[:200]
    assert b'<NAME translate="true">R1</NAME>' in xml


def test_preview_icons_and_aggregation():
    from ptlab.preview import render_svg

    svg = render_svg(plan(parse_spec(GRAPH)))
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")

    hosts = "".join(f"  - {{name: PC{i}, model: PC-PT, ip: 192.168.7.{i}/24}}\n" for i in range(1, 9))
    links = "".join(
        f"  - {{a: PC{i}, a_port: FastEthernet0, b: SW1, b_port: FastEthernet0/{i}}}\n"
        for i in range(1, 9)
    )
    many = f"name: h\nnodes:\n  - {{name: SW1, model: 2960-24TT}}\n{hosts}links:\n{links}"
    assert "x8 equipos" in render_svg(plan(parse_spec(many)))


def test_plan_graph_numeric_model_names_are_text():
    spec = "name: n\nnodes:\n  - {name: R1, model: 2911}\n"
    assert plan(parse_spec(spec)).device("R1").model == "2911"


def test_plan_graph_rip_classful_networks():
    spec = (
        "name: r\nrouting: rip\nnodes:\n"
        "  - {name: R1, model: 2911, interfaces: [{port: GigabitEthernet0/0, ip: 10.0.0.1/30},"
        " {port: GigabitEthernet0/1, ip: 192.168.1.1/24}]}\n"
        "  - {name: R2, model: 2911, interfaces: [{port: GigabitEthernet0/0, ip: 10.0.0.2/30},"
        " {port: GigabitEthernet0/1, ip: 192.168.2.1/24}]}\n"
        "links:\n  - {a: R1, a_port: GigabitEthernet0/0, b: R2, b_port: GigabitEthernet0/0}\n"
    )
    cfg = plan(parse_spec(spec)).device("R1").config
    assert "router rip" in cfg and " version 2" in cfg and " no auto-summary" in cfg
    assert " network 10.0.0.0" in cfg and " network 192.168.1.0" in cfg


def test_plan_graph_eigrp_config():
    spec = (
        "name: e\nrouting: eigrp\nnodes:\n"
        "  - {name: R1, model: 2911, interfaces: [{port: GigabitEthernet0/1, ip: 192.168.1.1/24}]}\n"
    )
    cfg = plan(parse_spec(spec)).device("R1").config
    assert "router eigrp 100" in cfg
    assert " network 192.168.1.0 0.0.0.255" in cfg


def test_plan_graph_bgp_neighbors():
    spec = (
        "name: b\nrouting: bgp\nnodes:\n"
        "  - {name: R1, model: 2911, as_number: 65100,"
        " interfaces: [{port: GigabitEthernet0/0, ip: 10.0.0.1/30},"
        " {port: GigabitEthernet0/1, ip: 192.168.1.1/24}]}\n"
        "  - {name: R2, model: 2911, as_number: 65200,"
        " interfaces: [{port: GigabitEthernet0/0, ip: 10.0.0.2/30},"
        " {port: GigabitEthernet0/1, ip: 192.168.2.1/24}]}\n"
        "links:\n  - {a: R1, a_port: GigabitEthernet0/0, b: R2, b_port: GigabitEthernet0/0}\n"
    )
    cfg = plan(parse_spec(spec)).device("R1").config
    assert "router bgp 65100" in cfg
    assert " neighbor 10.0.0.2 remote-as 65200" in cfg
    assert " network 192.168.1.0 mask 255.255.255.0" in cfg


def test_plan_graph_l3_switch_as_router():
    spec = (
        "name: l3\nnodes:\n"
        "  - {name: L3SW, model: 3560-24PS,"
        " interfaces: [{port: GigabitEthernet0/1, ip: 192.168.1.1/24}]}\n"
    )
    cfg = plan(parse_spec(spec)).device("L3SW").config
    assert "ip routing" in cfg and " no switchport" in cfg
