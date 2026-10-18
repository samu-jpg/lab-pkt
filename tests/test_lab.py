"""Un test por funcion de las primitivas (`ptlab.lab`) sobre archivos .pkt."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor" / "packet-tracer-pkt-format"))
sys.path.insert(0, str(ROOT / "vendor" / "packet-tracer-pkt-format" / "src"))

from ptlab import codec, lab  # noqa: E402


def _xml(path) -> str:
    return codec.decode(path).decode("utf-8", "replace")


def _new(tmp_path):
    return lab.new(tmp_path / "lab.pkt")


def test_new_lab(tmp_path):
    p = _new(tmp_path)
    assert p.exists() and lab.device_names(p) == []


def test_add_device(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1")
    assert lab.device_names(p) == ["R1"]
    assert lab.devices(p)[0]["model"] == "2911"


def test_add_device_unknown_model_raises(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="desconocido"):
        lab.add_device(_new(tmp_path), "NO-EXISTE", "X")


def test_add_device_host_ip(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "PC-PT", "PC-A", host_ip="192.168.1.10/24", host_gateway="192.168.1.1")
    dev = lab.inspect(p)["devices"][0]
    assert (dev["ip"], dev["mask"], dev["gateway"]) == ("192.168.1.10", "255.255.255.0", "192.168.1.1")


def test_add_device_config_lines(tmp_path):
    p = _new(tmp_path)
    lines = ["hostname R1", "interface GigabitEthernet0/0", " ip address 10.0.0.1 255.255.255.252"]
    lab.add_device(p, "2911", "R1", config=lines)
    cfg = lab.inspect(p)["devices"][0]["config"]
    assert " ip address 10.0.0.1 255.255.255.252" in cfg


def test_add_link(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1")
    lab.add_device(p, "2960-24TT", "SW1")
    lab.add_link(p, "R1", "GigabitEthernet0/0", "SW1", "GigabitEthernet0/1")
    assert lab.inspect(p)["links"] == [
        {
            "a": "R1",
            "a_port": "GigabitEthernet0/0",
            "b": "SW1",
            "b_port": "GigabitEthernet0/1",
            "kind": "copper",
        }
    ]


def test_add_link_crossover(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "PC-PT", "PC-A")
    lab.add_device(p, "PC-PT", "PC-B")
    lab.add_link(p, "PC-A", "FastEthernet0", "PC-B", "FastEthernet0", kind="crossover")
    assert "eCrossOver" in _xml(p)


def test_add_link_serial(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1", install="HWIC-2T")
    lab.add_device(p, "2911", "R2", install="HWIC-2T")
    lab.add_link(p, "R1", "Serial0/1/0", "R2", "Serial0/1/0", kind="serial", dce="R1")
    link = lab.inspect(p)["links"][0]
    assert link["kind"] == "serial" and link["dce"] == "R1"
    assert "clock rate 128000" in _xml(p)


def test_append_config(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1", config=["hostname R1"])
    lab.append_config(p, "R1", ["ip route 0.0.0.0 0.0.0.0 10.0.0.2"])
    cfg = lab.inspect(p)["devices"][0]["config"]
    assert "ip route 0.0.0.0 0.0.0.0 10.0.0.2" in cfg and cfg[-1] == "end"


def test_set_host(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "PC-PT", "PC-A")
    lab.set_host(p, "PC-A", "192.168.5.20/24", gateway="192.168.5.1")
    dev = lab.inspect(p)["devices"][0]
    assert (dev["ip"], dev["gateway"]) == ("192.168.5.20", "192.168.5.1")


def test_set_dhcp(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "PC-PT", "PC-A")
    lab.set_dhcp(p, "PC-A", True)
    dev = lab.inspect(p)["devices"][0]
    assert dev.get("dhcp") is True and "ip" not in dev


def test_set_wireless(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "Laptop-PT", "L1")
    lab.set_wireless(p, "L1", ssid="MIWIFI", password="clave12345", channel="6")
    assert "MIWIFI" in _xml(p)


def test_set_config_register(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1")
    lab.set_config_register(p, "R1", 0x2142)
    assert "<CONFIG_REGISTER>8514</CONFIG_REGISTER>" in _xml(p)


def test_set_os(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1")
    lab.set_os(p, "R1", image="c2900-universalk9-mz.SPA.155-3.M4a.bin")
    assert "c2900-universalk9" in _xml(p)


def test_install_module(tmp_path):
    modules = lab.models()["modules"]
    module = "HWIC-2T" if "HWIC-2T" in modules else modules[0]
    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1")
    lab.install_module(p, "R1", module)
    assert f"<MODEL>{module}</MODEL>" in _xml(p)


def test_remove_device_drops_links(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1")
    lab.add_device(p, "2960-24TT", "SW1")
    lab.add_link(p, "R1", "GigabitEthernet0/0", "SW1", "GigabitEthernet0/1")
    lab.remove_device(p, "SW1")
    assert lab.device_names(p) == ["R1"]
    assert lab.inspect(p)["links"] == []
    lab.add_device(p, "PC-PT", "PC-A")
    assert lab.device_names(p) == ["R1", "PC-A"]


def test_models_listing():
    data = lab.models()
    names = [m["model"] for m in data["models"]]
    assert "2911" in names and "2960-24TT" in names and "PC-PT" in names
    assert len(names) > 20 and data["modules"]


def test_unknown_device_raises(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="no existe el equipo"):
        lab.append_config(_new(tmp_path), "NOPE", ["x"])


def test_models_counts_ports():
    by_name = {m["model"]: m["ports"] for m in lab.models()["models"]}
    assert by_name["2911"] == 3 and by_name["PC-PT"] == 1


def test_rename_device_keeps_links(tmp_path):
    import pytest

    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1")
    lab.add_device(p, "2960-24TT", "SW1")
    lab.add_link(p, "R1", "GigabitEthernet0/0", "SW1", "GigabitEthernet0/1")
    lab.rename_device(p, "SW1", "ACCESO")
    assert lab.device_names(p) == ["R1", "ACCESO"]
    assert lab.inspect(p)["links"][0]["b"] == "ACCESO"
    with pytest.raises(ValueError, match="ya existe"):
        lab.rename_device(p, "R1", "ACCESO")


def test_move_device(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "PC-PT", "PC-A")
    lab.move_device(p, "PC-A", 640, 480)
    dev = lab.devices(p)[0]
    assert (dev["x"], dev["y"]) == (640, 480)


def test_set_power(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1")
    lab.set_power(p, "R1", False)
    assert lab.inspect(p)["devices"][0]["power"] is False
    lab.set_power(p, "R1", True)
    assert "power" not in lab.inspect(p)["devices"][0]


def test_clone_device_copies_config(tmp_path):
    p = _new(tmp_path)
    config = ["hostname R1", "interface GigabitEthernet0/0", " ip address 10.0.0.1 255.255.255.252"]
    lab.add_device(p, "2911", "R1", config=config)
    lab.clone_device(p, "R1", "R2", x=300, y=150)
    assert lab.device_names(p) == ["R1", "R2"]
    clone = lab.inspect(p)["devices"][1]
    assert clone["model"] == "2911" and (clone["x"], clone["y"]) == (300, 150)
    assert " ip address 10.0.0.1 255.255.255.252" in clone["config"]
    lab.add_device(p, "2960-24TT", "SW1")
    assert lab.device_names(p) == ["R1", "R2", "SW1"]


def test_set_service(tmp_path):
    import re

    import pytest

    p = _new(tmp_path)
    lab.add_device(p, "Server-PT", "SRV1")
    lab.set_service(p, "SRV1", "http", True, fields={"username": "admin", "password": "clave"})
    xml = _xml(p)
    assert "<USERNAME>admin</USERNAME>" in xml and "<PASSWORD>clave</PASSWORD>" in xml
    lab.set_service(p, "SRV1", "http", False)
    block = re.search(r"<HTTP_SERVER>.*?</HTTP_SERVER>", _xml(p), re.S).group(0)
    assert "<ENABLED>0</ENABLED>" in block
    with pytest.raises(ValueError, match="servicio desconocido"):
        lab.set_service(p, "SRV1", "ftp", True)


def test_set_service_missing_on_model(tmp_path):
    import pytest

    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1")
    with pytest.raises(ValueError, match="no tiene el servicio"):
        lab.set_service(p, "R1", "http", True)


def test_add_dhcp_pool(tmp_path):
    import re

    p = _new(tmp_path)
    lab.add_device(p, "Server-PT", "SRV1")
    lab.add_dhcp_pool(p, "SRV1", "192.168.1.0/24", "192.168.1.1", dns="8.8.8.8")
    lab.add_dhcp_pool(p, "SRV1", "192.168.2.0/24", "192.168.2.1", name="PISO2")
    xml = _xml(p)
    assert "<NAME>serverPool</NAME>" in xml and "<START_IP>192.168.1.10</START_IP>" in xml
    assert "<NAME>PISO2</NAME>" in xml and "<NETWORK>192.168.2.0</NETWORK>" in xml
    block = re.search(r"<DHCP_SERVER>.*?</DHCP_SERVER>", xml, re.S).group(0)
    assert block.count("<POOL>") == 2
    assert "<NETWORK>0.0.0.0</NETWORK>" not in block


def test_add_dns_record(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "Server-PT", "SRV1")
    lab.add_dns_record(p, "SRV1", "web.lab", "192.168.1.50")
    xml = _xml(p)
    assert "<NAME>web.lab</NAME>" in xml and "<IPADDRESS>192.168.1.50</IPADDRESS>" in xml


def test_add_aaa_user_and_client(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "Server-PT", "SRV1")
    lab.add_aaa_user(p, "SRV1", "alumno", "secreto", description="acceso ssh")
    lab.add_aaa_client(p, "SRV1", "192.168.1.1", "claveradius", description="R1")
    xml = _xml(p)
    assert "<NAME>alumno</NAME>" in xml and "<PASSWORD>secreto</PASSWORD>" in xml
    assert "<HOST_IP>192.168.1.1</HOST_IP>" in xml and "<KEY>claveradius</KEY>" in xml


def test_add_acl_and_apply(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1")
    lab.add_acl(p, "R1", "100", ["permit ip 192.168.1.0 0.0.0.255 any"], "extended")
    lab.apply_acl(p, "R1", "GigabitEthernet0/0", "100", "in")
    cfg = lab.inspect(p)["devices"][0]["config"]
    assert "access-list 100 permit ip 192.168.1.0 0.0.0.255 any" in cfg
    assert " ip access-group 100 in" in cfg


def test_nat_primitives(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1")
    lab.nat_static(p, "R1", "192.168.1.10", "200.1.1.10")
    lab.nat_overload(p, "R1", "100", "GigabitEthernet0/0")
    lab.nat_interface(p, "R1", "GigabitEthernet0/0", "outside")
    lab.nat_interface(p, "R1", "GigabitEthernet0/1", "inside")
    cfg = lab.inspect(p)["devices"][0]["config"]
    assert "ip nat inside source static 192.168.1.10 200.1.1.10" in cfg
    assert "ip nat inside source list 100 interface GigabitEthernet0/0 overload" in cfg
    assert " ip nat outside" in cfg and " ip nat inside" in cfg


def test_new_activity(tmp_path):
    import re

    from ptlab import activity

    p = lab.new(tmp_path / "practica.pkt")
    lab.add_device(p, "2911", "R1")
    a = lab.new(tmp_path / "resuelto.pkt")
    lab.add_device(a, "2911", "R1", config=["hostname R1"])
    out = activity.new_activity(
        p,
        tmp_path / "act.pka",
        answer=a,
        instructions=["<h3>Tarea</h3><p>Configura R1</p>"],
        password="clave",
        locked=True,
        components="Ip, Routing",
        timer=600,
    )
    xml = codec.decode_bytes(out.read_bytes()).decode("utf-8", "replace")
    assert "<PACKETTRACER5_ACTIVITY>" in xml
    blocks = re.findall(r"<PACKETTRACER5>.*?</PACKETTRACER5>", xml, re.S)
    assert len(blocks) == 3
    assert "hostname R1" not in blocks[1] and "hostname R1" in blocks[2]
    assert "Configura R1" in xml and 'PASS="clave"' in xml
    assert "<COMPONENT_LIST>Ip, Routing</COMPONENT_LIST>" in xml


def test_harvest_and_use_local_model(tmp_path, monkeypatch):
    from ptlab import library

    monkeypatch.setenv("PTLAB_LIB", str(tmp_path / "lib.json"))
    p = _new(tmp_path)
    lab.add_device(p, "2911", "R1")
    xml = codec.decode(p).replace(b'model="2911"', b'model="2911X"', 1)
    codec.encode(p, xml)
    result = library.harvest(p)
    assert result["models"] == ["2911X"] and result["new"] == ["2911X"]
    lab.add_device(p, "2911X", "R2")
    assert lab.device_names(p) == ["R1", "R2"]


def test_iot_models_can_be_added(tmp_path):
    p = _new(tmp_path)
    lab.add_device(p, "MCU-PT", "MCU1")
    lab.add_device(p, "Thing", "TH1")
    lab.add_device(p, "SBC-PT", "SBC1")
    assert lab.device_names(p) == ["MCU1", "TH1", "SBC1"]
    lab.set_wireless(p, "TH1", ssid="IOTLAB")
    assert "IOTLAB" in _xml(p)


def test_mcp_server_imports_standalone():
    import os
    import subprocess
    import sys

    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run(
        [sys.executable, "-c", "import ptlab.mcp_server"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr
