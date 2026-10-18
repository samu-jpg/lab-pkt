# ptlab — roadmap

Principio rector: **el MCP es la caja de herramientas del proyecto**. Todo lo que se puede hacer
con un lab se expone como tool MCP y el agente (Command Code, Claude, Copilot...) opera todo:
planifica, arma la spec, genera, verifica y retoca. Sin UI propia y **sin plantillas ni topologias
preajustadas**: los equipos, nombres, cables y direcciones los decide quien usa el MCP. El mismo
patron aplica a los proximos MCPs (video, imagen, captura): un repo = un MCP con sus tools, y las
operaciones largas corren como jobs en segundo plano (start -> status -> resultado).

## Estado actual (base sobre la que se construye)

- Spec **explicita**: `nodes` (equipos) + `links` (cables puerto a puerto). Sin modo "N sedes" ni
  topologias predefinidas (se retiraron junto con los ejemplos de ejercicios).
- Routing `static`/`rip`/`ospf`/`eigrp`/`bgp`; DHCP (pools por router + relay con Server-PT);
  VLANs con access/trunk/SVI y router-on-a-stick; switch L3 con `ip routing`.
- Preview SVG con iconos reales de Packet Tracer leidos de la instalacion local (no se shippean
  assets de Cisco en el repo).
- MCP con 5 tools (`pt_schema`, `pt_list_models`, `pt_plan`, `pt_preview`, `pt_build`) y smoke
  test del servidor; CLI solo como apoyo de debug.
- Publicado en GitHub (`samu-jpg/lab-pkt`): vendor como submodulo fijado a `ad9c38b`, LICENSE
  GPL-3.0-or-later, metadata completa en `pyproject.toml`.
- Tests verdes (`python3 -m pytest tests -q`).

## Fase 1 — Primitivas de Packet Tracer como tools (el MCP como caja completa) — en curso

El MCP debe exponer las funciones de las librerias (vendor `lab_api`) para que el agente haga lo
que quiera, sin pasar por una spec:

- `pt_lab_new` / `pt_lab_open`: crear un `.pkt` vacio o abrir uno existente.
- `pt_add_device`, `pt_remove_device`, `pt_devices`: equipos (cualquier modelo del vendor).
- `pt_add_link`: cables copper/crossover/serial (con DCE y clock rate).
- `pt_config`: lineas IOS crudas a un equipo (escape hatch total).
- `pt_set_host`: IP/mask/gateway/DHCP de un host; `pt_set_wireless`: SSID/WPA2/canal.
- `pt_set_config_register`, `pt_set_os`, `pt_install_module`: registro, imagen y modulos.
- `pt_inspect`: leer un `.pkt` y devolver equipos, IPs, configs y enlaces.
- `pt_models`: modelos disponibles (dinamico desde `device_templates.json`, no una lista fija).
- `pt_diff`: comparar dos specs o `.pkt`.
- Prompts y resources MCP (schema, catalogo, ejemplos de armado paso a paso).

## Fase 2 — Cobertura Packet Tracer (casi todo lo que se puede hacer)

- Enlaces: serial DCE/DTE con clock rate, fibra, consola.
- Switch L3 con VLANs (hoy los L3 con VLAN estan bloqueados en la spec).
- ACLs (standard/extended/named), NAT/PAT (static, dynamic, overload).
- Port security, STP (rapid-pvst/portfast/BPDU guard), EtherChannel (LACP/PAgP), SSH, banners,
  passwords, AAA local.
- Servicios Server-PT: HTTP, DNS, TFTP, NTP, Email, Syslog (el builder ya inyecta el XML del DHCP).
- Wireless: WLC 3504, AP-PT, hosts inalambricos (SSID, WPA2, canales).
- IoT: MCU, sensores/actuadores, home gateway, registration server.
- Cloud/modem/ISP (Cloud-PT, DSL/cable) y firewall ASA basico.
- IPv6: direccionamiento, SLAAC/DHCPv6, OSPFv3/EIGRPv6/IPv6 estatico.

## Fase 3 — GitHub (portafolio)

- Hecho: repo creado, vendor como submodulo, LICENSE, `.gitignore`, metadata de `pyproject.toml`.
- CI (GitHub Actions): `pytest` + smoke del MCP en Python 3.10-3.13.
- README publico (es/en) con demo (GIF/SVG del preview), badges, topics, CONTRIBUTING, releases.
- Sin assets de Cisco en el repo; atribucion del vendor GPL y su origen.
- Opcional: publicar en PyPI y registrar el MCP en el MCP registry.

## Fase 4 — Otros MCPs (mismo patron: tools + jobs en segundo plano, sin UI propia)

- **video-mcp** (ffmpeg): probe/inspect, cortar, unir, convertir, comprimir, extraer frames/audio,
  GIF, subtitulos, thumbnails; lo largo corre como job con estado.
- **image-mcp** (Pillow/ImageMagick): inspect/EXIF, crop/resize/convert, watermark, batch, montage,
  ajustes de color, OCR opcional, thumbnails.
- **captura-mcp** (mss/ffmpeg x11grab): screenshot de pantalla/ventana/region, grabacion de
  pantalla, OCR — cubre "abre, captura, revisa, modifica" sin UI.
- Estandar comun: layout `src/`, tests, ruff, README con demo, CI, licencia permisiva
  (MIT/Apache-2.0 salvo que se reutilice codigo GPL), PyPI + MCP registry.

## Proximo paso inmediato

1. Fase 1: primitivas como tools (`pt_inspect` primero, el decode del vendor ya existe) + un test
   por cada tool y smoke actualizado.
2. Primer feature nuevo de Fase 2 (serial DCE/DTE + L3 con VLANs) con tests.
3. CI + README en ingles para el portafolio.
