# ptlab

Asistente que disena topologias de red y **genera archivos `.pkt`** para **Cisco Packet Tracer**
sin abrir Packet Tracer: describe la topologia (o deja que un agente LLM la describa), mira el
preview y baja un `.pkt` que **ya trae los equipos cableados y configurados**.

El MCP es la caja de herramientas del proyecto: todo se expone como tools y lo opera el agente
que ya tengas (Command Code, Claude, Copilot...), sin costo extra de LLM. No hay UI propia: el
agente conversa, arma la spec y llama a las tools.

## Alcance actual
- N sedes, cada una con router + una o mas **LANs** (switch + hosts).
- Topologias entre sedes: `line`, `ring`, `star`, `mesh`, `ladder`, `tree`, `grid`, `dual_star`.
- Direccionamiento automatico (LANs `/24`, enlaces WAN `/30`, gateway `.1`).
- Routing: `none`, `static` (rutas calculadas), `rip` (v2), `ospf`, `eigrp` o `bgp` (eBGP, AS por sede).
- Hosts estaticos o por **DHCP**: pools en cada router, o **DHCP relay** con un `Server-PT`
  central y `ip helper-address` en las demas LANs.
- Preview **SVG** del plano (iconos reales de Packet Tracer).
- **Modo grafo (sin IA)**: nodos y cables explicitos — routers, switches L2/L3,
  hosts (PC/laptop/server) y hub; IPs por interfaz, routing global o por equipo, DHCP (pools o
  Server-PT con relay) y **VLANs con access / trunk / SVI y router-on-a-stick (dot1Q)**.

## Requisitos
- Python 3.10+ y `libgcrypt` (`sudo apt install libgcrypt20` en Debian/Ubuntu).
- Packet Tracer 9.x (solo para **abrir** el resultado).
- Se probo contra Packet Tracer **9.0.1** generando archivos que abren y rutean.

## Instalacion
```bash
git clone --recurse-submodules git@github.com:samu-jpg/lab-pkt.git
cd lab-pkt
pip install -e ".[mcp]"
```
El extra `mcp` instala el SDK del servidor MCP. El proyecto reutiliza el codec/generador
GPL-3.0 `packet-tracer-pkt-format`, integrado como **submodulo** en `vendor/`
(si clonaste sin submodulos: `git submodule update --init`). Por eso el proyecto es
**GPL-3.0-or-later**.

## Uso — servidor MCP (interfaz principal)
El agente conversa, arma la spec y llama a las tools. Comando del server (tras la instalacion):
`ptlab-mcp` (o `python3 -m ptlab.mcp_server`).

- `pt_schema` — JSON schema de la spec (que campos acepta).
- `pt_list_models` — modelos de equipos soportados, su rol y cantidad de puertos.
- `pt_plan` — valida/planifica y muestra el resumen con direccionamiento.
- `pt_preview` — genera el SVG.
- `pt_build` — genera el `.pkt`.

Ejemplo de registro en Command Code (`cmd mcp add`):
```bash
cmd mcp add ptlab -- ptlab-mcp
```
O en `.mcp.json`:
```json
{ "mcpServers": { "ptlab": { "command": "ptlab-mcp", "env": { "PTLAB_OUT_DIR": "/mnt/d/PT-Labs" } } } }
```
Mismo patron para Claude Code / Copilot / Cursor (transport stdio).

## Uso — CLI (apoyo para debug)
```bash
ptlab build examples/two_sites.yaml -o /mnt/d/PT-Labs/two_sites.pkt   # genera el .pkt
ptlab preview examples/two_sites.yaml -o /mnt/d/PT-Labs/two_sites.svg # preview
ptlab schema                                                          # campos de la spec
```
El `.pkt` queda en una carpeta accesible desde Windows (por defecto salida en `/mnt/d/PT-Labs`).

## Formato de la spec
```yaml
name: lab_dos_sedes
topology: line       # line | ring | star | mesh | ladder | tree | grid | dual_star
routing: ospf        # none | static | rip | ospf | eigrp | bgp
dhcp: true           # hosts por DHCP
dhcp_server: false   # (por LAN) true = esta LAN tiene el Server-PT y las demas van por relay
dns: 8.8.8.8         # DNS que entrega el servidor DHCP
ospf_process: 1      # parametros por protocolo
ospf_area: 0
eigrp_as: 100
bgp_as_base: 65000   # cada sede usa bgp_as_base + indice (o su as_number)
lan_base: 192.168.0.0/16   # de aca salen las LANs /24
link_base: 10.0.0.0/16     # de aca salen los enlaces WAN /30
sites:
  - name: Sede1
    router_model: 2911        # 2911 | 1941 | 2901 | 2811 | 3560-24PS (switch L3)
    switch_model: 2960-24TT   # opcional
    host_model: PC-PT         # opcional
    hosts: 2                  # hosts de la LAN unica
    lan: 192.168.1.0/24       # opcional (si no, se asigna solo)
    dhcp: false               # opcional (pisa el global)
  - {name: Sede2, lan: 192.168.2.0/24, hosts: 3, as_number: 65020}
```

### Sede con varias LANs (ej. guia de DHCP relay)
```yaml
name: guia_dhcp_relay
routing: none
dhcp: true
sites:
  - name: RouterC
    router_model: 2811
    lans:
      - {name: LAN_Izquierda, lan: 192.168.1.0/24, hosts: 1, dhcp: true}
      - {name: LAN_Derecha, lan: 192.168.2.0/24, hosts: 1, dhcp: true, dhcp_server: true}
```
Genera un `Server-PT` en `LAN_Derecha` (192.168.2.100) con un pool por subred y
`ip helper-address 192.168.2.100` en el resto de las LANs. Ejemplo listo en
`examples/guia_dhcp_relay.yaml`.

### Modo grafo (nodos y cables explicitos)
```yaml
name: graph_vlan
routing: ospf
nodes:
  - name: R1
    model: 2911
    interfaces:
      - {port: GigabitEthernet0/0, ip: 10.0.0.1/30}                    # enlace WAN
      - {port: GigabitEthernet0/1.10, ip: 192.168.10.1/24, dot1q: 10}  # router-on-a-stick
    dhcp: true                 # pools por interfaz /24 del router
  - name: SW1
    model: 2960-24TT
    vlans: [{id: 10, name: VENTAS}]
    access: [{port: FastEthernet0/1, vlan: 10}]
    trunks: [GigabitEthernet0/1]
  - {name: PC1, model: PC-PT, dhcp: true}
  - name: SRV1
    model: Server-PT
    ip: 192.168.30.11/24
    gateway: 192.168.30.1
    pools: [{network: 192.168.30.0/24, gateway: 192.168.30.1}]
links:
  - {a: R1, a_port: GigabitEthernet0/0, b: R2, b_port: GigabitEthernet0/0}
  - {a: PC1, a_port: FastEthernet0, b: SW1, b_port: FastEthernet0/1, cable: straight}
```
Cada nodo acepta: `model` (catalogo: 2911/1941/2901/2811, 2960-24TT/2950-24, 3560-24PS,
PC-PT/Server-PT/Laptop-PT, Hub-PT), `x`/`y` (si falta, layout por capas), `interfaces`
(`ip` en CIDR, `dot1q` para subinterfaces, `helper` para relay), `vlans`/`access`/`trunks`
(switches), `ip`/`gateway`/`dhcp` (hosts), `pools` (Server-PT), `routing`/`as_number` por equipo
y `config` (lineas IOS extra). Los enlaces llevan puerto exacto de cada extremo y `cable`
(`straight` o `crossover`). Ejemplo completo en `examples/graph_vlan.yaml`.

Los modelos de router con pocos puertos (1941/2811/2901/2911: 2-3) limitan cuantas LANs y
enlaces WAN puede tener una sede; para topologias exigentes usar `3560-24PS` (26 puertos,
se configura solo con `ip routing` y `no switchport`).

## Como funciona (pipeline)
```
spec (YAML/JSON)
  -> planner   : equipos, puertos, direccionamiento (LANs /24, WAN /30), configs IOS
  -> builder   : plantillas de equipos reales (vendor) -> XML -> cifrado -> .pkt
  -> preview   : SVG del plano
```
El `.pkt` es un XML cifrado (zlib + XOR + Twofish-EAX). Se generan los `<RUNNINGCONFIG>` de cada
equipo y la config de red de los hosts; Packet Tracer los aplica al abrir.

## Estructura
```
src/ptlab/     catalog, spec, planner, ios, builder, preview, cli, mcp_server
vendor/        packet-tracer-pkt-format (submodulo, GPL-3.0) — codec y plantillas reusadas
examples/      specs de ejemplo
docs/          roadmap
spike/         pruebas de viabilidad del codec
```

## Limitaciones / proximos pasos
- Sin ACL/NAT todavia (VLAN/trunk/SVI si, en modo grafo).
- En modo grafo quedan pendientes el cable serial y el switch L3 con VLANs.
- El DHCP del `Server-PT` se configura con pools y gateway/DNS; sin reservas ni opciones extra.
- Sin deploy "live" directo a Packet Tracer (por ahora es por archivo).
- Roadmap completo (tools nuevas como inspeccion/edicion de `.pkt`, cobertura PT y otros MCPs)
  en `docs/ROADMAP.md`.

## Legal
Reutiliza un proyecto de ingenieria inversa del formato `.pkt`. Uso con **archivos propios**, para
interoperabilidad y practica. **No** usar para alterar claves de correccion o competencias.
