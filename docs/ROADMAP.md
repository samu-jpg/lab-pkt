# ptlab — roadmap

Principio rector: **el MCP es la caja de herramientas del proyecto**. Todo lo que se puede hacer
con un lab se expone como tool MCP y el agente (Command Code, Claude, Copilot...) opera todo:
planifica, arma la spec, genera, verifica y retoca. Sin UI propia y **sin plantillas ni topologias
preajustadas**: los equipos, nombres, cables y direcciones los decide quien usa el MCP. El mismo
patron aplica a los proximos MCPs (video, imagen, captura): un repo = un MCP con sus tools, y las
operaciones largas corren como jobs en segundo plano (start -> status -> resultado).

## Estado actual (base sobre la que se construye)

- Spec **explicita**: `nodes` (equipos) + `links` (cables puerto a puerto). Sin modo "N sedes" ni
  topologias predefinidas.
- **Primitivas de Packet Tracer como tools**: lab nuevo/abrir, equipos (agregar, quitar, clonar
  con config incluida, renombrar, mover, prender/apagar), cables (copper/crossover/serial con DCE
  y clock rate), config IOS cruda, red del host, wireless (AP/router y clientes), modulos,
  config-register, OS e inspeccion de `.pkt`. Aceptan **todos** los modelos/modulos del vendor.
- **Servicios**: Server-PT con HTTP/HTTPS, DNS (registros), DHCP (pools), AAA/RADIUS (usuarios y
  clientes), y toggles/campos para TFTP, NTP, email y syslog.
- **ACL/NAT**: ACL standard/extended numerada o con nombre, `ip access-group`, NAT estatico, PAT
  (overload) e `ip nat inside/outside`.
- **Actividades `.pka`**: `pt_activity` arma el archivo con consigna (HTML), password, permisos,
  timer y las redes inicial/respuesta desde dos `.pkt`. El arbol de correccion (scoring) queda
  afuera: el vendor lo deriva de nodos de una actividad de referencia (pendiente hasta tener una).
- **Libreria local**: `pt_harvest` cosecha modelos desde tus propios `.pkt` a `PTLAB_LIB`
  (por defecto `~/.ptlab/device_templates.json`) y se mergean sobre el catalogo del vendor.
- IoT: los equipos (Thing, MCU-PT, SBC-PT...) se pueden agregar y configurar en red/wireless; la
  programacion del MCU y el registro en el servidor IoT se hacen dentro de PT (no estan en el
  formato del archivo).
- Routing `static`/`rip`/`ospf`/`eigrp`/`bgp`; DHCP (pools por router + relay); VLANs con
  access/trunk/SVI y router-on-a-stick; switch L3 con `ip routing` (todo esto en la spec).
- Preview SVG con iconos reales de Packet Tracer leidos de la instalacion local.
- 61 tests verdes (un test por primitiva y por funcion del planner) + smoke del MCP (34 tools).
- Publicado en GitHub (`samu-jpg/lab-pkt`): vendor como submodulo fijado a `ad9c38b`, LICENSE
  GPL-3.0-or-later, metadata completa en `pyproject.toml`.

## Fase 2 — Cobertura Packet Tracer (lo que queda)

- Scoring de `.pka`: `scoring.py` del vendor clona nodos de item de una actividad de referencia;
  cuando haya un `.pka` de referencia a mano se expone `pt_activity(scoring=...)`.
- WLC 3504 y seguridad inalambrica avanzada (hoy: SSID/canal/password en AP y clientes).
- Programacion de MCU / registro en servidor IoT (esta en el runtime de PT, no en el archivo).
- VoIP (telefonos IP) y Cloud/modem/ISP (Cloud-PT, DSL/cable); firewall ASA basico.
- En la spec: cable serial y switch L3 con VLANs (en las primitivas ya funcionan).
- IPv6: direccionamiento, SLAAC/DHCPv6, OSPFv3/EIGRPv6.

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
- **docs-mcp** (docx/xlsx) y **ns3-mcp** (correr simulaciones ns-3 en background, parsear trazas,
  generar netanim).
- Estandar comun: layout `src/`, tests, ruff, README con demo, CI, licencia permisiva
  (MIT/Apache-2.0 salvo que se reutilice codigo GPL), PyPI + MCP registry.

## Proximo paso inmediato

1. CI (GitHub Actions) + README en ingles para el portafolio.
2. Arrancar el segundo MCP (video-mcp) con la misma estructura.
3. Scoring de `.pka` cuando haya una actividad de referencia.
