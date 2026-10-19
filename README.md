# ptlab

English | [**Espanol**](README.es.md)

[![CI](https://github.com/samu-jpg/lab-pkt/actions/workflows/ci.yml/badge.svg)](https://github.com/samu-jpg/lab-pkt/actions/workflows/ci.yml)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

MCP server that exposes the libraries to build **Cisco Packet Tracer** labs and generate the
`.pkt` file without opening Packet Tracer: the AI (or you) describes the lab with devices, cables,
IPs, VLANs and routing, and the engine produces a `.pkt` that **already ships the devices cabled
and configured**.

The MCP is the project's toolbox: everything is exposed as tools and driven by whatever agent you
already use (Command Code, Claude, Copilot...), with no extra LLM cost. There is no UI of its own
and **no preset templates or topologies**: every device, name, cable and address is decided by
whoever uses the MCP.

## Demo

`ptlab preview` on a two-router lab (OSPF, Server-PT with DHCP and three hosts):

![lab preview](docs/demo.svg)

## Current scope
- **Explicit topology**: `nodes` (devices) + `links` (port-to-port cables), no templates.
- **MCP primitives**: create/edit a `.pkt` device by device (add/remove/clone/rename, move,
  power on/off, copper/crossover/serial cables, raw IOS config, modules, wireless,
  config-register, OS) and inspect existing labs.
- **Services and security**: Server-PT services (HTTP/HTTPS, DNS, TFTP, NTP, email, syslog,
  AAA/RADIUS, DHCP pools) and ACL/NAT (static, overload) as tools.
- **`.pka` activities**: guided practice (HTML instructions, initial and answer networks,
  password, permissions, timer). No grading tree: the vendor derives it from a reference activity.
- **Local library**: harvest device models from your own `.pkt` files (`pt_harvest`); after that
  `pt_add_device` accepts them like any factory model.
- Catalog: routers (2911/1941/2901/2811), L2 switches (2960-24TT/2950-24), L3 switch (3560-24PS),
  hosts (PC-PT/Server-PT/Laptop-PT) and Hub-PT; the primitives accept **every** model in the
  vendor template library (100+).
- Per-interface IPs (CIDR), dot1Q subinterfaces (router-on-a-stick), static or DHCP host IPs.
- **VLANs** with access / trunk / SVI and router-on-a-stick; L3 switch with `ip routing`.
- Routing `none`/`static`/`rip`/`ospf`/`eigrp`/`bgp` (global or per device, computed on the graph).
- DHCP: pools on the router, or a `Server-PT` with pools + `ip helper-address` (relay).
- **SVG** preview of the canvas (real Packet Tracer icons, read from the local installation).

## Requirements
- Python 3.10+ (the `.pkt` codec is pure Python: no native dependencies).
- Packet Tracer 9.x (only to open the result).
- Tested against Packet Tracer **9.0.1** producing files that open and route.

## Install
```bash
git clone --recurse-submodules git@github.com:samu-jpg/lab-pkt.git
cd lab-pkt
pip install -e ".[mcp]"
```
The `mcp` extra installs the MCP server SDK. The project reuses the GPL-3.0 codec/generator
`packet-tracer-pkt-format`, integrated as a **git submodule** under `vendor/` (cloned without
submodules? run `git submodule update --init`). Hence the project is **GPL-3.0-or-later**.

## Usage — MCP server (main interface)
Server command (after install): `ptlab-mcp` (or `python3 -m ptlab.mcp_server`). The agent talks
and operates everything through tools.

**Spec -> .pkt / .svg** (describe the lab in one shot):
- `pt_schema` — JSON schema of the spec (accepted fields).
- `pt_list_models` — spec catalog + every vendor model and module.
- `pt_plan` — validate/plan and return the summary with addressing.
- `pt_preview` — render the SVG.
- `pt_build` — generate the `.pkt`.

**Primitives on a .pkt** (the agent does whatever it wants, including opening and editing):
- `pt_new` — create an empty `.pkt`; `pt_devices` — list devices.
- `pt_add_device` / `pt_remove_device` — add/remove devices (any model, with IOS config and host
  network); `pt_add_link` — copper/crossover/serial cables (DCE with clock rate).
- `pt_clone_device` / `pt_rename_device` / `pt_move_device` / `pt_set_power` — clone (config
  included), rename, place and power devices.
- `pt_config` — raw IOS lines; `pt_set_host` / `pt_set_dhcp` — host network.
- `pt_set_wireless` — SSID/security (AP, router or client); `pt_install_module` — modules (HWIC...).
- `pt_set_config_register` / `pt_set_os` — config register and boot image.
- `pt_inspect` — read a `.pkt`: devices, IPs, configs, pools and links.

**Services and security:**
- `pt_set_service` — enable/disable and configure services (http, https, dns, tftp, ntp, syslog,
  email, aaa, dhcp) with raw fields.
- `pt_add_dhcp_pool`, `pt_add_dns_record`, `pt_add_aaa_user`, `pt_add_aaa_client` — DHCP pool,
  DNS records and AAA (RADIUS) users/clients on the Server-PT.
- `pt_add_acl` / `pt_apply_acl` — standard/extended ACLs (numbered or named) and `ip access-group`.
- `pt_nat_static`, `pt_nat_overload`, `pt_nat_interface` — static NAT, PAT and `ip nat inside/outside`.

**Activities and local library:**
- `pt_activity` — build a `.pka` with initial/answer networks, instructions, password, permissions
  and timer.
- `pt_harvest` — harvest models from your `.pkt` files into the local library (`pt_add_device`
  accepts them afterwards).

Example registration in Command Code (`cmd mcp add`):
```bash
cmd mcp add ptlab -- ptlab-mcp
```
Or in `.mcp.json`:
```json
{ "mcpServers": { "ptlab": { "command": "ptlab-mcp", "env": { "PTLAB_OUT_DIR": "/mnt/d/PT-Labs" } } } }
```
Same pattern for Claude Code / Copilot / Cursor (stdio transport).

## Usage — CLI (debug helper)
```bash
ptlab build mi_lab.yaml -o /mnt/d/PT-Labs/mi_lab.pkt   # generate the .pkt
ptlab preview mi_lab.yaml -o /mnt/d/PT-Labs/mi_lab.svg # preview
ptlab schema                                           # spec fields
```

## Spec format
```yaml
name: mi_lab
routing: ospf        # none | static | rip | ospf | eigrp | bgp (global; any node can override)
ospf_process: 1      # per-protocol parameters
ospf_area: 0
eigrp_as: 100
bgp_as_base: 65000   # BGP base AS when the node has no as_number
dns: 8.8.8.8         # default DNS for Server-PT pools
nodes:
  - name: R1
    model: 2911
    x: 200             # optional; without x/y the planner lays out by layers
    y: 300
    interfaces:
      - {port: GigabitEthernet0/0, ip: 10.0.0.1/30}                    # WAN link
      - {port: GigabitEthernet0/1.10, ip: 192.168.10.1/24, dot1q: 10}  # router-on-a-stick
      - {port: GigabitEthernet0/2, ip: 192.168.1.1/24, helper: 192.168.2.100}  # DHCP relay
    routing: ospf      # optional: overrides global routing
    as_number: 65010   # for bgp
    dhcp: true         # /24 pools per router interface
    config: []         # extra raw IOS lines (escape hatch)
  - name: SW1
    model: 2960-24TT
    vlans: [{id: 10, name: VENTAS}, {id: 20, name: ADMIN}]
    access: [{port: FastEthernet0/1, vlan: 10}]
    trunks: [GigabitEthernet0/1]
    interfaces: [{port: Vlan10, ip: 192.168.10.2/24}]    # SVI (management)
  - {name: PC1, model: PC-PT, ip: 192.168.1.10/24, gateway: 192.168.1.1, dhcp: false}
  - name: SRV1
    model: Server-PT
    ip: 192.168.30.11/24
    gateway: 192.168.30.1
    pools: [{network: 192.168.30.0/24, gateway: 192.168.30.1}]
links:
  - {a: R1, a_port: GigabitEthernet0/0, b: R2, b_port: GigabitEthernet0/0}
  - {a: PC1, a_port: FastEthernet0, b: SW1, b_port: FastEthernet0/1, cable: straight}
  - {a: R1, a_port: GigabitEthernet0/1, b: SW1, b_port: GigabitEthernet0/1}
```
Validations (Spanish messages): unique names, catalog model, existing ports without duplicates,
CIDR IPs without duplicates, VLAN 1-4094 declared before use, `dot1q` only on subinterfaces,
hosts with `ip`+`gateway` or `dhcp: true`.

Note: routers with few ports (1941/2811/2901/2911: 2-3) limit how many links each device can
have; use `3560-24PS` for demanding topologies (26 ports, configured with `ip routing` and
`no switchport`).

## How it works
```
spec (YAML/JSON: nodes + links)
  -> planner   : validates, builds devices/ports, IOS configs and layout
  -> builder   : real device templates (vendor) -> XML -> encrypted -> .pkt
  -> preview   : SVG of the canvas

primitives:
  pt_new/open -> lab_api (add devices, cables, configs) -> .pkt
```
The `.pkt` is an encrypted XML (zlib + XOR + Twofish-EAX). `<RUNNINGCONFIG>` blocks for every
device and the host network config are generated; Packet Tracer applies them on open.

## Repository layout
```
src/ptlab/     spec, planner, builder, ios, preview, lab, activity, library, vendorlib,
               codec, catalog, cli, mcp_server
vendor/        packet-tracer-pkt-format (submodule, GPL-3.0) — reused codec and templates
docs/          roadmap and demo
spike/         codec feasibility spikes
```

## Limitations / next steps
- No ACL/NAT in the spec yet (available through the ACL/NAT tools).
- In the spec: serial cables and L3 switch with VLANs are pending (primitives already do serial).
- The `Server-PT` DHCP service is configured with pools and gateway/DNS; no reservations yet.
- No "live" deployment straight into Packet Tracer (file based for now).
- Full roadmap (PT coverage, CI and the other MCPs) in `docs/ROADMAP.md`.

## Legal
It reuses a reverse-engineering project of the `.pkt` format. Use with **your own files**, for
interoperability and practice. **Do not** use it to tamper with grading keys or assessments.
