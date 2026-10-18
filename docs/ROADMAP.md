# ptlab — roadmap

Principio rector: **el MCP es la caja de herramientas del proyecto**. Todo lo que se puede hacer
con un lab se expone como tool MCP y el agente (Command Code, Claude, Copilot...) opera todo:
planifica, arma la spec, genera, verifica y retoca. Sin UI propia. El mismo patron aplica a los
proximos MCPs (video, imagen, captura): un repo = un MCP con sus tools, y las operaciones largas
corren como jobs en segundo plano (start -> status -> resultado).

## Estado actual (base sobre la que se construye)

- Core Python: modo sedes (N sedes, topologias, routing) y modo grafo (nodos/cables explicitos,
  IPs por interfaz, VLAN con access/trunk/SVI, router-on-a-stick).
- Routing `static`/`rip`/`ospf`/`eigrp`/`bgp`; DHCP (pools por router + relay con Server-PT).
- Preview SVG con iconos reales de Packet Tracer leidos de la instalacion local (no se shippean
  assets de Cisco en el repo).
- MCP con 5 tools (`pt_schema`, `pt_list_models`, `pt_plan`, `pt_preview`, `pt_build`) y smoke
  test del servidor; CLI solo como apoyo de debug.
- Enfoque MCP-only aplicado: la web se retiro del proyecto (solo queda en el historial de git).
- Publicado en GitHub (`samu-jpg/lab-pkt`): vendor como submodulo fijado a `ad9c38b`, LICENSE
  GPL-3.0-or-later, metadata completa en `pyproject.toml`.
- Tests verdes (`python3 -m pytest tests -q`).

## Fase 1 — Tools nuevas (que el MCP sea la caja completa) — en curso

- `pt_inspect`: leer un `.pkt` existente y devolver resumen (equipos, IPs, configs, enlaces).
- `pt_edit`: cargar un `.pkt`, aplicar cambios (config, IPs) y reescribirlo.
- `pt_diff`: comparar dos specs o `.pkt` (que cambio entre versiones del lab).
- `pt_open_in_pt`: abrir el `.pkt` generado en Packet Tracer local.
- `pt_export`: PNG del preview (ademas de SVG) para informes/enunciados.
- `pt_presets` + `pt_list`/`pt_clean`: plantillas de labs tipicos y gestion de `PTLAB_OUT_DIR`.
- MCP resources (schema, catalogo, ejemplos) y prompts (lab VLAN, OSPF multiarea, ACL...).

## Fase 2 — Cobertura Packet Tracer (casi todo lo que se puede hacer)

- Enlaces: serial DCE/DTE con clock rate, fibra, consola.
- Switch L3 completo (3560: `ip routing`, SVIs, routing entre VLANs).
- ACLs (standard/extended/named), NAT/PAT (static, dynamic, overload).
- Port security, STP (rapid-pvst/portfast/BPDU guard), EtherChannel (LACP/PAgP), SSH, banners,
  passwords, AAA local.
- Servicios Server-PT: HTTP, DNS, TFTP, NTP, Email, Syslog (el builder ya inyecta el XML del DHCP).
- Wireless: WLC 3504, AP-PT, hosts inalambricos (SSID, WPA2, canales).
- IoT: MCU, sensores/actuadores, home gateway, registration server.
- Cloud/modem/ISP (Cloud-PT, DSL/cable) y firewall ASA basico.
- IPv6: direccionamiento, SLAAC/DHCPv6, OSPFv3/EIGRPv6/IPv6 estatico.
- Catalogo: sumar todos los device templates del vendor a la paleta.

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

1. `pt_inspect`/`pt_edit` (el decode del vendor ya existe) con tests y tools MCP nuevas.
2. Primer feature nuevo de Fase 2 (serial + L3 completo) con tests.
3. CI + README en ingles para el portafolio.
