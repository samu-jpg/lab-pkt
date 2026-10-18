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
