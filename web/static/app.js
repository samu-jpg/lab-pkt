/* Modo rapido: formulario parametrico (N sedes) + preview + generacion del .pkt. */
/* ------------------------------------------------------------------ datos */
const TOPOS = {
  line:      { label: "Linea",      desc: "cadena",           nodes: [[0, .5], [.5, .5], [1, .5]],                      edges: [[0, 1], [1, 2]] },
  ring:      { label: "Anillo",     desc: "enlace de cierre",  nodes: [[.5, 0], [1, .5], [.5, 1], [0, .5]],              edges: [[0, 1], [1, 2], [2, 3], [3, 0]] },
  star:      { label: "Estrella",   desc: "hub central",      nodes: [[.5, .5], [.5, 0], [1, .5], [.5, 1], [0, .5]],    edges: [[0, 1], [0, 2], [0, 3], [0, 4]] },
  mesh:      { label: "Malla",      desc: "todos con todos",  nodes: [[0, 0], [1, 0], [0, 1], [1, 1]],                  edges: [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]] },
  ladder:    { label: "Escalera",   desc: "dos filas",        nodes: [[0, 0], [.5, 0], [1, 0], [0, 1], [.5, 1], [1, 1]], edges: [[0, 1], [1, 2], [3, 4], [4, 5], [0, 3], [1, 4], [2, 5]] },
  tree:      { label: "Arbol",      desc: "jerarquica",       nodes: [[.5, 0], [.25, .55], [.75, .55], [0, 1], [.5, 1]], edges: [[0, 1], [0, 2], [1, 3], [1, 4]] },
  grid:      { label: "Rejilla",    desc: "grilla regular",   nodes: [[0, 0], [1, 0], [0, 1], [1, 1]],                  edges: [[0, 1], [2, 3], [0, 2], [1, 3]] },
  dual_star: { label: "Doble hub",  desc: "redundante",       nodes: [[.25, .4], [.75, .4], [.25, 1], [.75, 1], [.5, 0]], edges: [[0, 1], [0, 2], [1, 3], [0, 4], [1, 4]] },
};

const PROTO = {
  ospf:   { hint: "OSPF: link-state, converge rapido. Se elige proceso y area; cada router anuncia sus redes.", fields: ["ospf_process", "ospf_area"] },
  eigrp:  { hint: "EIGRP: vector distancia avanzado de Cisco. Todos los routers comparten el mismo AS.", fields: ["eigrp_as"] },
  rip:    { hint: "RIP v2: vector distancia simple; anuncia por red mayor (classful). Ideal para labs chicos.", fields: [] },
  bgp:    { hint: "BGP: cada sede es un sistema autonomo (AS) y se conecta con el vecino por eBGP.", fields: ["bgp_as_base"] },
  static: { hint: "Rutas estaticas: se calculan las rutas de cada router hacia las LANs de las demas sedes.", fields: [] },
  none:   { hint: "Sin enrutamiento: util cuando el lab es una sola sede (todas sus LANs son directamente conectadas).", fields: [] },
};

const FIELDS = {
  ospf_process: { label: "Proceso OSPF",   min: 1, max: 65535, value: 1 },
  ospf_area:    { label: "Area OSPF",      min: 0, max: 255,   value: 0 },
  eigrp_as:     { label: "AS de EIGRP",    min: 1, max: 65535, value: 100 },
  bgp_as_base:  { label: "AS base de BGP", min: 1, max: 60000, value: 65000 },
};

const PRESETS = [
  { t: "DHCP relay (guia)",  name: "guia_dhcp_relay", n: 1, h: 1, lans: 2, model: "2811", routing: "none", dhcp: "server", srv: 1, badge: "relay" },
  { t: "Linea 2 + OSPF",     name: "lab_dos_sedes",   n: 2, h: 3, lans: 1, model: "2911", routing: "ospf",   dhcp: "router", badge: "2" },
  { t: "Anillo 4 + OSPF",    name: "lab_anillo",      n: 4, h: 2, lans: 1, model: "2911", routing: "ospf",   dhcp: "router", badge: "4" },
  { t: "Estrella 3 + EIGRP", name: "lab_estrella",    n: 3, h: 3, lans: 1, model: "2911", routing: "eigrp",  dhcp: "router", badge: "3", eigrp_as: 10 },
  { t: "Doble hub 3 + RIP",  name: "lab_doble_hub",   n: 3, h: 2, lans: 1, model: "2911", routing: "rip",    dhcp: "off",    badge: "3" },
  { t: "Arbol 4 + OSPF",     name: "lab_arbol",       n: 4, h: 2, lans: 1, model: "2911", routing: "ospf",   dhcp: "router", badge: "4" },
  { t: "Rejilla 4 + EIGRP",  name: "lab_rejilla",     n: 4, h: 2, lans: 1, model: "2911", routing: "eigrp",  dhcp: "router", badge: "4" },
  { t: "BGP 3 AS",           name: "lab_bgp",         n: 3, h: 2, lans: 1, model: "2911", routing: "bgp",    dhcp: "router", badge: "BGP" },
  { t: "Escalera 4 estatico", name: "lab_escalera",   n: 4, h: 1, lans: 1, model: "2911", routing: "static", dhcp: "off",    badge: "4" },
];

/* ------------------------------------------------------------------ helpers */
const $ = (id) => document.getElementById(id);
const pane = $("pane"), stage = $("stage");
let mode = "easy", topology = "line", dhcpmode = "router", timer = null;

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function toast(text, kind) { const m = $("msg"); m.className = kind || ""; m.textContent = text; if (kind !== "ok") $("dl").style.display = "none"; }

/* ------------------------------------------------------------------ pestanas principales */
document.querySelectorAll(".mtab").forEach((btn) => btn.onclick = () => {
  document.querySelectorAll(".mtab").forEach((b) => b.classList.toggle("active", b === btn));
  const view = btn.dataset.view;
  $("view-editor").style.display = view === "editor" ? "" : "none";
  $("view-fast").style.display = view === "fast" ? "" : "none";
  if (view === "fast") changed();
  else if (window.editorShown) window.editorShown();
});

/* ------------------------------------------------------------------ topologias */
function diagram(t, w, h) {
  const pad = 8;
  const p = t.nodes.map(([x, y]) => [pad + x * (w - 2 * pad), pad + y * (h - 2 * pad)]);
  const edges = t.edges.map(([a, b]) =>
    `<line x1="${p[a][0].toFixed(1)}" y1="${p[a][1].toFixed(1)}" x2="${p[b][0].toFixed(1)}" y2="${p[b][1].toFixed(1)}" stroke="#3d516b" stroke-width="1.3"/>`).join("");
  const dots = p.map(([x, y]) => `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.7" fill="#7fa9f0"/>`).join("");
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${edges}${dots}</svg>`;
}

function buildTopoPicker() {
  $("topos").innerHTML = Object.entries(TOPOS).map(([key, t]) =>
    `<button type="button" class="topo${key === topology ? " active" : ""}" data-k="${key}" title="${esc(t.desc)}">
       ${diagram(t, 64, 42)}<b>${esc(t.label)}</b><i>${esc(t.desc)}</i>
     </button>`).join("");
  $("topos").querySelectorAll(".topo").forEach((btn) => btn.onclick = () => {
    topology = btn.dataset.k;
    $("topos").querySelectorAll(".topo").forEach((b) => b.classList.toggle("active", b === btn));
    changed();
  });
}

function buildPresets() {
  $("presets").innerHTML = PRESETS.map((p, i) =>
    `<button class="chip" data-i="${i}">${esc(p.t)}<small>${esc(p.badge)}</small></button>`).join("");
  $("presets").querySelectorAll(".chip").forEach((btn) => btn.onclick = () => applyPreset(PRESETS[+btn.dataset.i], btn));
}

function applyPreset(p, btn) {
  $("nsites").value = p.n; $("nhosts").value = p.h; $("nlans").value = p.lans || 1;
  $("name").value = p.name; $("rmodel").value = p.model || "2911";
  topology = p.topology || "line"; $("routing").value = p.routing;
  if (p.eigrp_as) FIELDS.eigrp_as.value = p.eigrp_as;
  setDhcpmode(p.dhcp || "router");
  $("srvsite").value = String(p.srv || 1);
  renderSrvSites(p.srv || 1);
  $("topos").querySelectorAll(".topo").forEach((b) => b.classList.toggle("active", b.dataset.k === topology));
  renderExtras();
  $("presets").querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", c === btn));
  changed();
}

/* ------------------------------------------------------------------ formulario */
function setDhcpmode(v) {
  dhcpmode = v;
  $("dhcpmode").querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.v === v));
  $("srvwrap").style.display = v === "server" ? "" : "none";
}
$("dhcpmode").querySelectorAll("button").forEach((b) => b.onclick = () => { setDhcpmode(b.dataset.v); changed(); });

function renderSrvSites(keep) {
  const n = +$("nsites").value, sel = $("srvsite"), current = keep || +sel.value || 1;
  sel.innerHTML = Array.from({ length: n }, (_, i) => `<option value="${i + 1}">Sede${i + 1}</option>`).join("");
  sel.value = String(Math.min(Math.max(current, 1), n));
}
$("srvsite").addEventListener("change", changed);
$("rmodel").addEventListener("change", changed);

function renderExtras() {
  const proto = PROTO[$("routing").value];
  $("protohint").textContent = proto.hint;
  $("extras").innerHTML = proto.fields.map((k) => {
    const f = FIELDS[k];
    return `<div><label for="f-${k}">${esc(f.label)}</label>
      <input id="f-${k}" type="number" min="${f.min}" max="${f.max}" value="${f.value}" data-key="${k}"></div>`;
  }).join("");
  $("extras").querySelectorAll("input").forEach((inp) =>
    inp.addEventListener("input", () => { FIELDS[inp.dataset.key].value = inp.value; changed(); }));
}
const extra = (key) => { const el = $("f-" + key); return el ? Number(el.value) : FIELDS[key].value; };

function specFromForm() {
  const n = +$("nsites").value, h = +$("nhosts").value, nl = +$("nlans").value;
  const routing = $("routing").value, serverSite = +$("srvsite").value, model = $("rmodel").value;
  const dhcp = dhcpmode !== "off";
  const sites = [];
  let lanNo = 0;
  for (let i = 1; i <= n; i++) {
    const lans = [];
    for (let k = 1; k <= nl; k++) {
      lanNo += 1;
      const lan = { name: `LAN_${i}_${k}`, lan: `192.168.${lanNo}.0/24`, hosts: h, dhcp };
      if (dhcpmode === "server" && i === serverSite && k === nl) lan.dhcp_server = true;
      lans.push(lan);
    }
    sites.push({ name: "Sede" + i, router_model: model, lans });
  }
  const spec = { name: $("name").value || "lab", topology, routing, dhcp, sites };
  if (routing === "ospf") { spec.ospf_process = extra("ospf_process"); spec.ospf_area = extra("ospf_area"); }
  if (routing === "eigrp") spec.eigrp_as = extra("eigrp_as");
  if (routing === "bgp") spec.bgp_as_base = extra("bgp_as_base");
  return JSON.stringify(spec, null, 2);
}

function gridEdges(n) {
  const cols = Math.ceil(Math.sqrt(n));
  let e = 0;
  for (let i = 0; i < n; i++) {
    if (i % cols + 1 < cols && i + 1 < n) e++;
    if (i + cols < n) e++;
  }
  return e;
}

function summary() {
  const n = +$("nsites").value, h = +$("nhosts").value, nl = +$("nlans").value;
  const wan = {
    line: Math.max(n - 1, 0), ring: n > 2 ? n : Math.max(n - 1, 0), star: Math.max(n - 1, 0),
    mesh: (n * (n - 1)) / 2, ladder: Math.max(n - 1, 0) + Math.floor(n / 2),
    tree: Math.max(n - 1, 0), grid: gridEdges(n),
    dual_star: n <= 2 ? Math.max(n - 1, 0) : 3 + (n - 3) * 2,
  }[topology] || 0;
  const dhcpTxt = { off: "IPs fijas", router: "pools en cada router", server: `Server-PT en Sede${$("srvsite").value}` }[dhcpmode];
  $("sum").innerHTML =
    `<b>${n}</b> router(s) + <b>${n * nl}</b> switch(es) + <b>${n * nl * h}</b> host(s) · ` +
    `topologia <b>${esc(TOPOS[topology].label)}</b> con <b>${wan}</b> enlaces WAN · ` +
    `<b>${esc($("routing").selectedOptions[0].text)}</b> · DHCP: <b>${esc(dhcpTxt)}</b>`;
}

/* ------------------------------------------------------------------ tabs del form */
document.querySelectorAll(".tab").forEach((btn) => btn.onclick = () => {
  if (mode === "adv" && btn.dataset.mode === "easy") { applyYaml(); return; }
  mode = btn.dataset.mode;
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === btn));
  $("easy").style.display = mode === "easy" ? "" : "none";
  $("adv").style.display = mode === "adv" ? "" : "none";
  if (mode === "adv") $("spec").value = specFromForm();
});

async function applyYaml() {
  const r = await call("/api/normalize");
  if (!r) return;
  const spec = (await r.json()).spec;
  const sites = spec.sites || [];
  if (!sites.length) { toast("La spec necesita al menos una sede (o abrila en el editor).", "err"); return; }
  const lans = sites.map((s) => s.lans && s.lans.length ? s.lans : [s]);
  $("nsites").value = sites.length;
  $("nlans").value = Math.max(...lans.map((l) => l.length));
  $("nhosts").value = lans[0][0].hosts ?? 2;
  $("name").value = spec.name || "lab";
  $("rmodel").value = sites[0].router_model || "2911";
  topology = spec.topology || "line";
  $("routing").value = spec.routing || "none";
  const server = lans.findIndex((ls) => ls.some((l) => l.dhcp_server));
  setDhcpmode(server >= 0 ? "server" : (spec.dhcp ? "router" : "off"));
  renderSrvSites(server >= 0 ? server + 1 : 1);
  for (const k of Object.keys(FIELDS)) if (spec[k] != null) FIELDS[k].value = spec[k];
  $("topos").querySelectorAll(".topo").forEach((b) => b.classList.toggle("active", b.dataset.k === topology));
  renderExtras();
  switchTab("easy");
  const uneven = new Set(lans.flat().map((l) => l.hosts ?? 2)).size > 1;
  toast(uneven
    ? "Spec aplicada. Ojo: hay LANs con distinta cantidad de hosts, el formulario usa " + $("nhosts").value + "."
    : "Spec aplicada al formulario.", "ok");
  changed();
}

function switchTab(target) {
  mode = target;
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.mode === target));
  $("easy").style.display = target === "easy" ? "" : "none";
  $("adv").style.display = target === "adv" ? "" : "none";
}

/* ------------------------------------------------------------------ zoom / pan */
let scale = 1, tx = 0, ty = 0, dragging = false, startX = 0, startY = 0;
const apply = () => { stage.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`; };
const clamp = (s) => Math.min(12, Math.max(0.08, s));

function fit() {
  const svg = stage.querySelector("svg");
  if (!svg) return;
  const vb = svg.viewBox.baseVal, sw = vb.width || 800, sh = vb.height || 600;
  svg.setAttribute("width", sw); svg.setAttribute("height", sh);
  scale = clamp(Math.min((pane.clientWidth - 36) / sw, (pane.clientHeight - 36) / sh));
  tx = (pane.clientWidth - sw * scale) / 2;
  ty = (pane.clientHeight - sh * scale) / 2;
  apply();
}
function zoomBy(factor) {
  const cx = pane.clientWidth / 2, cy = pane.clientHeight / 2, ns = clamp(scale * factor);
  const k = ns / scale; tx = cx - (cx - tx) * k; ty = cy - (cy - ty) * k; scale = ns; apply();
}
function reset() { scale = 1; tx = 18; ty = 18; apply(); }

pane.addEventListener("wheel", (e) => {
  if (!stage.querySelector("svg")) return;
  e.preventDefault();
  const r = pane.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  const ns = clamp(scale * (e.deltaY < 0 ? 1.12 : 1 / 1.12)), k = ns / scale;
  tx = mx - (mx - tx) * k; ty = my - (my - ty) * k; scale = ns; apply();
}, { passive: false });
pane.addEventListener("mousedown", (e) => { if (!stage.querySelector("svg")) return; dragging = true; startX = e.clientX - tx; startY = e.clientY - ty; pane.classList.add("grabbing"); });
window.addEventListener("mousemove", (e) => { if (dragging) { tx = e.clientX - startX; ty = e.clientY - startY; apply(); } });
window.addEventListener("mouseup", () => { dragging = false; pane.classList.remove("grabbing"); });

/* ------------------------------------------------------------------ API */
const currentSpec = () => mode === "adv" ? $("spec").value : specFromForm();

async function call(url) {
  let r;
  try {
    r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ spec: currentSpec(), name: $("name").value }) });
  } catch (e) { toast("Error de red: " + e, "err"); return null; }
  if (!r.ok) {
    let detail = await r.text();
    try { detail = JSON.parse(detail).detail || detail; } catch (_) { /* respuesta en texto plano */ }
    toast(detail, "err");
    return null;
  }
  return r;
}

function showStats() {
  const svg = stage.querySelector("svg");
  const stats = svg && svg.dataset.stats ? JSON.parse(svg.dataset.stats) : null;
  $("stats").innerHTML = !stats ? "" :
    `<span class="stat"><b>${stats.routers}</b> routers</span>
     <span class="stat"><b>${stats.switches}</b> switches</span>
     <span class="stat"><b>${stats.hosts}</b> hosts</span>
     <span class="stat"><b>${stats.links}</b> enlaces</span>`;
}

async function doPreview(manual) {
  $("spin").classList.add("on");
  const r = await call("/api/preview");
  $("spin").classList.remove("on");
  if (!r) return;
  stage.innerHTML = await r.text();
  $("empty").style.display = "none";
  fit();
  showStats();
  if (manual) toast("Preview actualizado.", "ok");
}

async function doGenerate() {
  const btn = $("btnGen");
  btn.disabled = true; toast("Generando .pkt…", "");
  const r = await call("/api/generate");
  btn.disabled = false;
  if (!r) return;
  const data = await r.json();
  toast("Listo: " + data.file, "ok");
  $("dl").href = data.download;
  $("dl").textContent = "Descargar " + ($("name").value || "lab") + ".pkt";
  $("dl").style.display = "block";
}

/* ------------------------------------------------------------------ init */
function changed() {
  summary();
  clearTimeout(timer);
  timer = setTimeout(() => doPreview(false), 450);
}

buildTopoPicker();
buildPresets();
renderExtras();
renderSrvSites(1);
applyPreset(PRESETS[0], $("presets").querySelector(".chip"));
["nsites", "nhosts", "nlans", "name"].forEach((id) => $(id).addEventListener("input", () => {
  if (id === "nsites") renderSrvSites();
  changed();
}));
$("routing").addEventListener("change", () => { renderExtras(); changed(); });
$("spec").addEventListener("input", changed);
