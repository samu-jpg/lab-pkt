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
- **Primitivas de Packet Tracer como tools**: `pt_new`, `pt_devices`, `pt_add_device`,
  `pt_remove_device`, `pt_add_link` (copper/crossover/serial con DCE y clock rate), `pt_config`
  (IOS crudo), `pt_set_host`, `pt_set_dhcp`, `pt_set_wireless` (AP/router y clientes),
  `pt_install_module`, `pt_set_config_register`, `pt_set_os`, `pt_inspect` (leer un `.pkt`).
  Aceptan **todos** los modelos/modulos del vendor (100+ modelos, no una lista fija).
- Routing `static`/`rip`/`ospf`/`eigrp`/`bgp`; DHCP (pools por router + relay con Server-PT);
  VLANs con access/trunk/SVI y router-on-a-stick; switch L3 con `ip routing`.
- Preview SVG con iconos reales de Packet Tracer leidos de la instalacion local (no se shippean
  assets de Cisco en el repo).
- 42 tests verdes (un test por prima y por funcion del planner) + smoke test del MCP (18 tools).
- Publicado en GitHub (`samu-jpg/lab-pkt`): vendor como submodulo fijado a `ad9c38b`, LICENSE
  GPL-3.0-or-later, metadata completa en `pyproject.toml`.

## Fase 1 — Primitivas (hecho)

- Lab como archivo: crear vacio, abrir existente, guardar; equipos con nombre libre y sin
  colisiones de `save-ref-id` entre llamadas.
- Equipos: agregar/quitar (quita tambien cables y el leaf del rack fisico), modelos del vendor.
- Cables: copper (straight), crossover y serial (DCE + clock rate automatico).
- Config: lineas IOS crudas por equipo, red del host (estatica/DHCP), wireless, registro de
  configuracion, imagen de OS y modulos.
- Inspeccion: resumen de equipos (modelo, IP, config, pools, wireless) y enlaces.

## Fase 2 — Cobertura Packet Tracer (casi todo lo que se puede hacer)

- ACLs (standard/extended/named), NAT/PAT (static, dynamic, overload) como primitivas.
- En la spec: cable serial y switch L3 con VLANs (hoy bloqueados ahi; las primitivas ya pueden).
- Servicios Server-PT: HTTP, DNS, TFTP, NTP, Email, Syslog (el builder ya inyecta el XML del DHCP).
- Wireless: WLC 3504 y APs con seguridad (hoy: SSID basico via primitivas).
- IoT: MCU, sensores/actuadores, home gateway, registration server.
- Cloud/modem/ISP (Cloud-PT, DSL/cable) y firewall ASA basico.
- IPv6: direccionamiento, SLAAC/DHCPv6, OSPFv3/EIGRPv6/IPv6 estatico.
- Actividades (`.pka`) si el vendor lo permite.

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

1. Fase 2: ACL/NAT como primitivas + serial y L3 con VLANs en la spec, con tests.
2. CI (GitHub Actions) + README en ingles para el portafolio.
3. Arrancar el segundo MCP (video-mcp) con la misma estructura.
