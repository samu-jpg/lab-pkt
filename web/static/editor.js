/* Editor visual de topologias (modo grafo): canvas, paleta, propiedades, cableado
   y vista previa editable (reordenar equipos y reconectar cables) que luego genera el .pkt. */
(() => {
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const LS_KEY = "ptlab.graph.v1";
const CANVAS_W = 1600, CANVAS_H = 900;
const ROLE_LABEL = { router: "Routers", switch: "Switches L2", l3switch: "Switches L3", host: "Hosts", hub: "Hubs" };

/* ------------------------------------------------------------------ estado */
function fresh() {
  return { name: "lab", routing: "none", ospf_process: 1, ospf_area: 0, eigrp_as: 100, bgp_as_base: 65000, nodes: [], links: [] };
}
function loadState() {
  try { const raw = localStorage.getItem(LS_KEY); return raw ? JSON.parse(raw) : null; } catch { return null; }
}
let G = loadState() || fresh();
let MODELS = {}, GROUPS = {}, ICONS = {};
let selected = { kind: null, id: null };
let cableMode = false, pending = null, errorNames = [];
let saveTimer = null;

function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try { localStorage.setItem(LS_KEY, JSON.stringify(G)); } catch (_) { /* sin storage */ }
  }, 350);
  scheduleLive();
}
function roleOf(model) { const m = MODELS[model]; return (m && m.role) || "host"; }
function portsOf(model) { const m = MODELS[model]; return m ? m.ports : []; }
function findNode(name) { return G.nodes.find((n) => n.name === name); }
function usedPorts(name) {
  const used = new Set();
  G.links.forEach((l) => { if (l.a === name) used.add(l.a_port); if (l.b === name) used.add(l.b_port); });
  return used;
}
function setOrDel(obj, key, value) { if (value) obj[key] = value; else delete obj[key]; }
function rowIndex(el) {
  if (el.dataset.j !== undefined) return +el.dataset.j;
  const row = el.closest("[data-j]");
  return row ? +row.dataset.j : -1;
}

/* ------------------------------------------------------------------ spec limpia */
function cleanNode(n) {
  const out = { name: n.name, model: n.model };
  if (n.x != null) out.x = Math.round(n.x);
  if (n.y != null) out.y = Math.round(n.y);
  if (n.ip) out.ip = n.ip;
  if (n.gateway) out.gateway = n.gateway;
  if (n.dhcp) out.dhcp = true;
  if ((n.interfaces || []).length) {
    out.interfaces = n.interfaces.filter((f) => f.port).map((f) => {
      const o = { port: f.port };
      if (f.ip) o.ip = f.ip;
      if (f.dot1q) o.dot1q = +f.dot1q;
      if (f.helper) o.helper = f.helper;
      return o;
    });
  }
  if ((n.vlans || []).length) out.vlans = n.vlans.map((v) => { const o = { id: +v.id }; if (v.name) o.name = v.name; return o; });
  if ((n.access || []).length) out.access = n.access.map((a) => ({ port: a.port, vlan: +a.vlan }));
  if ((n.trunks || []).length) out.trunks = [...n.trunks];
  if ((n.pools || []).length) {
    out.pools = n.pools.filter((p) => p.network && p.gateway)
      .map((p) => { const o = { network: p.network, gateway: p.gateway }; if (p.name) o.name = p.name; return o; });
  }
  if (n.routing) out.routing = n.routing;
  if (n.as_number) out.as_number = +n.as_number;
  if ((n.config || []).length) out.config = [...n.config];
  return out;
}
function cleanSpec() {
  return {
    name: G.name || "lab",
    routing: G.routing || "none",
    ospf_process: +G.ospf_process || 1,
    ospf_area: Number.isFinite(+G.ospf_area) ? +G.ospf_area : 0,
    eigrp_as: +G.eigrp_as || 100,
    bgp_as_base: +G.bgp_as_base || 65000,
    nodes: G.nodes.map(cleanNode),
    links: G.links.map((l) => ({ a: l.a, a_port: l.a_port, b: l.b, b_port: l.b_port, cable: l.cable || "straight" })),
  };
}
const specText = () => JSON.stringify(cleanSpec(), null, 2);

/* ------------------------------------------------------------------ API */
async function api(url, body) {
  let r;
  try {
    r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch (e) { throw new Error("Error de red: " + e); }
  if (!r.ok) {
    let detail = await r.text();
    try { detail = JSON.parse(detail).detail || detail; } catch (_) { /* texto plano */ }
    throw new Error(String(detail));
  }
  return r;
}

function toastEd(text, kind) {
  const m = $("ed-msg");
  m.className = kind || "";
  m.textContent = text;
  if (kind === "ok") setTimeout(() => { if (m.textContent === text) { m.className = ""; m.textContent = ""; } }, 4000);
}
function showProblems(msg) {
  const box = $("ed-problems");
  box.style.display = "";
  box.textContent = msg;
  errorNames = G.nodes.filter((n) => msg.includes(n.name)).map((n) => n.name);
  renderCanvas();
}
function clearProblems() {
  $("ed-problems").style.display = "none";
  errorNames = [];
  renderCanvas();
}

/* ------------------------------------------------------------------ validacion en vivo */
const live = { svg: null, error: null, timer: null, running: false, dirty: false };
function isPreviewOpen() { return $("ed-overlay").style.display !== "none"; }
function setStatus(kind) {
  const el = $("ed-status");
  if (!el) return;
  if (kind === "checking") { el.className = "status-chip"; el.textContent = "validando…"; }
  else if (kind === "ok") { el.className = "status-chip ok"; el.textContent = "OK"; }
  else if (kind === "err") { el.className = "status-chip err"; el.textContent = "problemas"; }
  else { el.className = "status-chip"; el.textContent = "sin equipos"; }
}
function scheduleLive() {
  clearTimeout(live.timer);
  live.timer = setTimeout(fetchLive, 650);
}
async function fetchLive() {
  if (!G.nodes.length) { live.svg = null; live.error = null; setStatus(null); return; }
  if (pvDrag || dragNode) { scheduleLive(); return; }
  if (live.running) { live.dirty = true; return; }
  live.running = true;
  setStatus("checking");
  try {
    const r = await api("/api/preview", { spec: specText(), name: G.name });
    live.svg = await r.text();
    live.error = null;
    setStatus("ok");
    clearProblems();
    if (isPreviewOpen()) paintPreview(true);
  } catch (err) {
    live.svg = null;
    live.error = String((err && err.message) || err);
    setStatus("err");
    showProblems(live.error);
    if (isPreviewOpen() && !$("ed-pv-stage").querySelector("svg")) {
      $("ed-pv-empty").style.display = "";
      $("ed-pv-empty").textContent = "No se pudo generar la vista previa; mira los problemas.";
    }
  } finally {
    live.running = false;
    if (live.dirty) { live.dirty = false; scheduleLive(); }
  }
}

/* ------------------------------------------------------------------ zoom/pan */
function makeZoom(paneId, stageId) {
  const paneEl = $(paneId), stageEl = $(stageId);
  const st = { scale: 1, tx: 0, ty: 0 };
  const apply = () => { stageEl.style.transform = `translate(${st.tx}px, ${st.ty}px) scale(${st.scale})`; };
  const clampS = (s) => Math.min(12, Math.max(0.08, s));
  st.fit = () => {
    const svg = stageEl.querySelector("svg");
    if (!svg || !paneEl.clientWidth) return;
    const vb = svg.viewBox.baseVal, sw = vb.width || 800, sh = vb.height || 600;
    svg.setAttribute("width", sw); svg.setAttribute("height", sh);
    st.scale = clampS(Math.min((paneEl.clientWidth - 36) / sw, (paneEl.clientHeight - 36) / sh));
    st.tx = (paneEl.clientWidth - sw * st.scale) / 2;
    st.ty = (paneEl.clientHeight - sh * st.scale) / 2;
    apply();
  };
  st.zoomBy = (f) => {
    const cx = paneEl.clientWidth / 2, cy = paneEl.clientHeight / 2, ns = clampS(st.scale * f), k = ns / st.scale;
    st.tx = cx - (cx - st.tx) * k; st.ty = cy - (cy - st.ty) * k; st.scale = ns;
    apply();
  };
  st.center = () => {
    if (!paneEl.clientWidth) return { x: 420, y: 300 };
    return { x: (paneEl.clientWidth / 2 - st.tx) / st.scale, y: (paneEl.clientHeight / 2 - st.ty) / st.scale };
  };
  paneEl.addEventListener("wheel", (e) => {
    if (!stageEl.querySelector("svg")) return;
    e.preventDefault();
    const r = paneEl.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    const ns = clampS(st.scale * (e.deltaY < 0 ? 1.12 : 1 / 1.12)), k = ns / st.scale;
    st.tx = mx - (mx - st.tx) * k; st.ty = my - (my - st.ty) * k; st.scale = ns;
    apply();
  }, { passive: false });
  let pan = null;
  paneEl.addEventListener("mousedown", (e) => {
    if (e.target.closest(".ed-node") || e.target.closest(".ed-link") || e.target.closest(".ov-node") || e.target.closest(".ov-link")) return;
    pan = { x: e.clientX - st.tx, y: e.clientY - st.ty };
    paneEl.classList.add("grabbing");
  });
  window.addEventListener("mousemove", (e) => {
    if (!pan) return;
    st.tx = e.clientX - pan.x; st.ty = e.clientY - pan.y;
    apply();
  });
  window.addEventListener("mouseup", () => { pan = null; paneEl.classList.remove("grabbing"); });
  return st;
}
function toSvg(e, paneEl) {
  const svg = paneEl.querySelector("svg");
  const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
  return { x: vb.x + (e.clientX - r.left) * (vb.width / r.width), y: vb.y + (e.clientY - r.top) * (vb.height / r.height) };
}
const edZoom = makeZoom("ed-pane", "ed-stage");

/* ------------------------------------------------------------------ canvas */
function renderCanvas() {
  const stageEl = $("ed-stage");
  $("ed-empty").style.display = G.nodes.length ? "none" : "";
  const byname = {};
  G.nodes.forEach((n) => { byname[n.name] = n; });
  const parts = [];
  parts.push(`<svg viewBox="0 0 ${CANVAS_W} ${CANVAS_H}" width="${CANVAS_W}" height="${CANVAS_H}" font-family="system-ui, sans-serif">`);
  parts.push(`<defs><pattern id="ed-grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e3e7ea" stroke-width="1"/></pattern></defs>`);
  parts.push(`<rect width="${CANVAS_W}" height="${CANVAS_H}" fill="#f7f9fb"/><rect width="${CANVAS_W}" height="${CANVAS_H}" fill="url(#ed-grid)"/>`);
  G.links.forEach((l, i) => {
    const a = byname[l.a], b = byname[l.b];
    if (!a || !b) return;
    const sel = selected.kind === "link" && selected.id === i;
    parts.push(`<g class="ed-link" data-i="${i}">
      <line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${sel ? "#e5534b" : "#4a5560"}" stroke-width="${sel ? 4 : 2}" stroke-linecap="round"/>
      <title>${esc(l.a)} ${esc(l.a_port)} ↔ ${esc(l.b)} ${esc(l.b_port)}</title></g>`);
  });
  G.nodes.forEach((n, i) => {
    const icon = ICONS[n.model];
    const sel = selected.kind === "node" && selected.id === i;
    const err = errorNames.includes(n.name);
    parts.push(`<g class="ed-node" data-i="${i}" transform="translate(${n.x},${n.y})">`);
    parts.push(`<circle class="halo" r="36" fill="${sel ? "rgba(77,140,245,.12)" : "transparent"}" stroke="${err ? "#e5534b" : (sel ? "#4d8cf5" : "transparent")}" stroke-width="2"/>`);
    if (icon) parts.push(`<image href="${icon}" x="-28" y="-28" width="56" height="56" pointer-events="none"/>`);
    else parts.push(`<rect x="-28" y="-28" width="56" height="56" rx="8" fill="#455a64" pointer-events="none"/>`);
    const sub = n.dhcp ? "DHCP" : (n.ip || "");
    parts.push(`<text y="46" text-anchor="middle" font-size="12" font-weight="600" fill="#111820" pointer-events="none">${esc(n.name)}</text>`);
    if (sub) parts.push(`<text y="59" text-anchor="middle" font-size="10" fill="#5b6b7a" pointer-events="none">${esc(sub)}</text>`);
    parts.push(`</g>`);
  });
  parts.push("</svg>");
  stageEl.innerHTML = parts.join("\n");
  attachCanvas();
  updateStats();
}

let dragNode = null, justDragged = false;
function attachCanvas() {
  const stageEl = $("ed-stage");
  stageEl.querySelectorAll(".ed-node").forEach((g) => {
    const i = +g.dataset.i;
    g.addEventListener("mousedown", (e) => {
      e.stopPropagation();
      e.preventDefault();
      const p = toSvg(e, $("ed-pane"));
      dragNode = { i, sx: p.x, sy: p.y, ox: G.nodes[i].x, oy: G.nodes[i].y, moved: false };
    });
    g.addEventListener("click", (e) => {
      e.stopPropagation();
      if (justDragged) { justDragged = false; return; }
      onNodeClick(i);
    });
  });
  stageEl.querySelectorAll(".ed-link").forEach((g) => {
    g.addEventListener("click", (e) => { e.stopPropagation(); selectLink(+g.dataset.i); });
  });
}
window.addEventListener("mousemove", (e) => {
  if (!dragNode) return;
  const p = toSvg(e, $("ed-pane"));
  const dx = p.x - dragNode.sx, dy = p.y - dragNode.sy;
  if (Math.abs(dx) + Math.abs(dy) > 4) dragNode.moved = true;
  if (dragNode.moved) {
    G.nodes[dragNode.i].x = Math.round(dragNode.ox + dx);
    G.nodes[dragNode.i].y = Math.round(dragNode.oy + dy);
    renderCanvas();
  }
});
window.addEventListener("mouseup", () => {
  if (dragNode) {
    if (dragNode.moved) { justDragged = true; save(); }
    dragNode = null;
  }
});

function updateStats() {
  const c = { router: 0, l3switch: 0, switch: 0, hub: 0, host: 0 };
  G.nodes.forEach((n) => { const r = roleOf(n.model); c[r] = (c[r] || 0) + 1; });
  const parts = [];
  if (c.router) parts.push(`<span class="stat"><b>${c.router}</b> routers</span>`);
  if (c.switch) parts.push(`<span class="stat"><b>${c.switch}</b> switches</span>`);
  if (c.l3switch) parts.push(`<span class="stat"><b>${c.l3switch}</b> switches L3</span>`);
  if (c.hub) parts.push(`<span class="stat"><b>${c.hub}</b> hubs</span>`);
  if (c.host) parts.push(`<span class="stat"><b>${c.host}</b> hosts</span>`);
  parts.push(`<span class="stat"><b>${G.links.length}</b> enlaces</span>`);
  $("ed-stats").innerHTML = parts.join("");
}

/* ------------------------------------------------------------------ paleta */
function buildPalette() {
  const order = ["router", "switch", "l3switch", "host", "hub"];
  const roles = Object.keys(GROUPS).sort((a, b) => {
    const ia = order.indexOf(a), ib = order.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  $("ed-palette").innerHTML = roles.map((role) => `
    <div class="pal-group">
      <div class="pal-title">${esc(ROLE_LABEL[role] || role)}</div>
      ${GROUPS[role].map((m) => `<button class="pal-item" data-model="${esc(m.name)}" title="puertos: ${esc(m.ports.join(", "))}">
        ${ICONS[m.name] ? `<img src="${ICONS[m.name]}" alt="">` : ""}<span>${esc(m.name)}</span></button>`).join("")}
    </div>`).join("");
  $("ed-palette").querySelectorAll(".pal-item").forEach((b) => b.onclick = () => addNode(b.dataset.model));
}

function nextName(model, role) {
  let prefix = { router: "R", l3switch: "L3", switch: "SW", hub: "H", host: "PC" }[role] || "D";
  if (model === "Server-PT") prefix = "SRV";
  else if (model === "Laptop-PT") prefix = "LAP";
  let i = 1;
  while (G.nodes.some((n) => n.name === prefix + i)) i++;
  return prefix + i;
}

function addNode(model) {
  const name = nextName(model, roleOf(model));
  const c = edZoom.center();
  const j = (G.nodes.length % 7) * 14;
  G.nodes.push({
    name, model, x: Math.round(c.x - 90 + j), y: Math.round(c.y - 60 + j),
    interfaces: [], vlans: [], access: [], trunks: [], pools: [],
  });
  selected = { kind: "node", id: G.nodes.length - 1 };
  save();
  renderCanvas();
  renderProps();
}

/* ------------------------------------------------------------------ seleccion */
function selectLink(i) {
  selected = { kind: "link", id: i };
  renderCanvas();
  renderProps();
}
function onNodeClick(i) {
  const n = G.nodes[i];
  if (cableMode) {
    if (!pending) {
      pickPort(n.name, "Puerto de salida", (port) => { pending = { name: n.name, port }; updateConnectHint(); });
    } else if (pending.name === n.name) {
      pending = null;
      updateConnectHint();
    } else {
      pickPort(n.name, "Puerto de entrada", (port) => {
        G.links.push({ a: pending.name, a_port: pending.port, b: n.name, b_port: port, cable: "straight" });
        toastEd(`Enlace ${pending.name} ${pending.port} ↔ ${n.name} ${port}`, "ok");
        pending = null;
        cableMode = false;
        updateConnectHint();
        save();
        renderCanvas();
        renderProps();
      });
    }
    return;
  }
  selected = { kind: "node", id: i };
  renderCanvas();
  renderProps();
}

/* ------------------------------------------------------------------ picker de puertos */
function pickPort(name, title, cb, extra = []) {
  const node = findNode(name);
  if (!node) return;
  const ports = portsOf(node.model);
  const used = usedPorts(name);
  const avail = ports.filter((p) => !used.has(p) || extra.includes(p));
  $("ed-picker-title").textContent = `${title}: ${name} (${avail.length} libres de ${ports.length})`;
  $("ed-picker-body").innerHTML = avail.length
    ? avail.map((p) => `<button class="chip" data-p="${esc(p)}">${esc(p)}${extra.includes(p) ? " *" : ""}</button>`).join("")
    : `<span class="hint">No quedan puertos libres en ${esc(name)}.</span>`;
  const pk = $("ed-picker");
  pk.style.display = "";
  pk.style.left = Math.max(12, (window.innerWidth - 320) / 2) + "px";
  pk.style.top = Math.max(12, (window.innerHeight - 300) / 2) + "px";
  $("ed-picker-body").querySelectorAll(".chip").forEach((b) => b.onclick = () => { closePicker(); cb(b.dataset.p); });
}
function closePicker() { $("ed-picker").style.display = "none"; }

/* ------------------------------------------------------------------ cableado */
function toggleConnect() {
  cableMode = !cableMode;
  pending = null;
  updateConnectHint();
}
function updateConnectHint() {
  const btn = $("ed-connect"), hint = $("ed-connect-hint");
  btn.className = cableMode ? "act go full" : "act alt full";
  btn.textContent = cableMode ? "Conectando… (click para cancelar)" : "Conectar equipos";
  hint.textContent = !cableMode
    ? 'Click en "Conectar" y despues en los dos equipos (elegis el puerto de cada uno).'
    : (pending ? `Salida: ${pending.name} ${pending.port}. Click en el segundo equipo.` : "Click en el primer equipo.");
}

/* ------------------------------------------------------------------ propiedades */
const ROUTING_OPTS = [["", "(usa el global)"], ["none", "none"], ["static", "static"], ["rip", "rip"], ["ospf", "ospf"], ["eigrp", "eigrp"], ["bgp", "bgp"]];
const modelOptions = (sel) => Object.entries(GROUPS).map(([role, list]) =>
  `<optgroup label="${esc(ROLE_LABEL[role] || role)}">${list.map((m) =>
    `<option value="${esc(m.name)}" ${m.name === sel ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</optgroup>`).join("");
const routingOptions = (sel) => ROUTING_OPTS.map(([v, t]) =>
  `<option value="${v}" ${(sel || "") === v ? "selected" : ""}>${esc(t)}</option>`).join("");
function portOptions(n, sel) {
  const ports = [...portsOf(n.model), ...(n.vlans || []).map((v) => "Vlan" + v.id)];
  if (sel && !ports.includes(sel)) ports.push(sel);
  return ports.map((p) => `<option value="${esc(p)}" ${p === sel ? "selected" : ""}>${esc(p)}</option>`).join("");
}

function renderProps() {
  const host = $("ed-props");
  if (!selected.kind) {
    $("ed-props-title").textContent = "Propiedades";
    host.innerHTML = `<div class="hint">Selecciona un equipo o un cable en el plano.</div>`;
    return;
  }
  if (selected.kind === "link") return renderLinkProps();
  const n = G.nodes[selected.id];
  if (!n) { selected = { kind: null, id: null }; return renderProps(); }
  const role = roleOf(n.model);
  $("ed-props-title").textContent = `Equipo: ${n.name}`;
  let html = `
    <div class="p-row"><label>Nombre</label><input type="text" data-act="node.name" value="${esc(n.name)}"></div>
    <div class="p-row"><label>Modelo</label><select data-act="node.model">${modelOptions(n.model)}</select></div>
    <div class="p-row2"><label>X</label><input type="number" data-act="node.x" value="${n.x ?? 0}"><label>Y</label><input type="number" data-act="node.y" value="${n.y ?? 0}"></div>`;
  if (role === "router" || role === "l3switch") {
    html += `<div class="sep"></div><h2 class="sec">Interfaces</h2>
      <div class="ifaces">${(n.interfaces || []).map((f, j) => `
        <div class="iface-row" data-j="${j}">
          <input class="mono" data-act="iface.port" value="${esc(f.port)}" placeholder="Ge0/1 o .10">
          <input class="mono" data-act="iface.ip" value="${esc(f.ip || "")}" placeholder="IP/24">
          <input class="mono" data-act="iface.dot1q" value="${f.dot1q ?? ""}" placeholder="dot1q">
          <input class="mono" data-act="iface.helper" value="${esc(f.helper || "")}" placeholder="helper">
          <button class="mini danger" data-act="iface.del" data-j="${j}">×</button>
        </div>`).join("")}</div>
      <button class="mini full" data-act="iface.add">+ interfaz</button>
      <div class="hint">Router-on-a-stick: <code>GigabitEthernet0/1.10</code> con dot1q 10.</div>
      <div class="sep"></div><h2 class="sec">Enrutamiento y DHCP</h2>
      <div class="p-row"><label>Protocolo del equipo (opcional)</label>
        <select data-act="node.routing">${routingOptions(n.routing)}</select></div>
      <label class="chk"><input type="checkbox" data-act="node.dhcp" ${n.dhcp ? "checked" : ""}> Servir DHCP (pool por interfaz /24)</label>
      <div class="p-row"><label>AS de BGP (opcional)</label><input type="number" data-act="node.as" value="${n.as_number ?? ""}"></div>
      <div class="p-row"><label>Config IOS extra (una linea por renglon)</label>
        <textarea style="height:90px" data-act="node.config" spellcheck="false">${esc((n.config || []).join("\n"))}</textarea></div>`;
  } else if (role === "switch") {
    html += `<div class="sep"></div><h2 class="sec">VLANs</h2>
      <div class="vlans">${(n.vlans || []).map((v, j) => {
        const svi = (n.interfaces || []).find((f) => f.port === "Vlan" + v.id);
        return `<div class="vlan-row" data-j="${j}">
          <input class="mono" data-act="vlan.id" value="${v.id}" placeholder="id">
          <input data-act="vlan.name" value="${esc(v.name || "")}" placeholder="nombre">
          <input class="mono" data-act="vlan.svi" value="${esc(svi ? svi.ip || "" : "")}" placeholder="IP gestion">
          <button class="mini danger" data-act="vlan.del" data-j="${j}">×</button>
        </div>`;
      }).join("")}</div>
      <button class="mini full" data-act="vlan.add">+ VLAN</button>
      <div class="hint">La IP de gestion crea la SVI (<code>interface VlanX</code>).</div>
      <div class="sep"></div><h2 class="sec">Puertos access</h2>
      <div class="access">${(n.access || []).map((a, j) => `
        <div class="trow" data-j="${j}">
          <select data-act="access.port">${portOptions(n, a.port)}</select>
          <input class="mono" data-act="access.vlan" value="${a.vlan}" placeholder="vlan">
          <button class="mini danger" data-act="access.del" data-j="${j}">×</button>
        </div>`).join("")}</div>
      <button class="mini full" data-act="access.add">+ access</button>
      <div class="sep"></div><h2 class="sec">Puertos trunk</h2>
      <div class="trunks">${(n.trunks || []).map((p, j) => `
        <div class="trow" data-j="${j}">
          <select data-act="trunk.port">${portOptions(n, p)}</select>
          <button class="mini danger" data-act="trunk.del" data-j="${j}">×</button>
        </div>`).join("")}</div>
      <button class="mini full" data-act="trunk.add">+ trunk</button>
      <div class="hint">El trunk va al router (subinterfaces dot1Q) o a otro switch.</div>`;
  } else if (role === "host") {
    html += `<div class="sep"></div>
      <label class="chk"><input type="checkbox" data-act="node.dhcp" ${n.dhcp ? "checked" : ""}> IP por DHCP</label>
      <div class="p-row"><label>IP (CIDR)</label><input class="mono" data-act="node.ip" value="${esc(n.ip || "")}" placeholder="192.168.1.10/24" ${n.dhcp ? "disabled" : ""}></div>
      <div class="p-row"><label>Gateway</label><input class="mono" data-act="node.gateway" value="${esc(n.gateway || "")}" placeholder="192.168.1.1" ${n.dhcp ? "disabled" : ""}></div>`;
    if (n.model === "Server-PT") {
      html += `<div class="sep"></div><h2 class="sec">Pools DHCP del servidor</h2>
        <div class="pools">${(n.pools || []).map((p, j) => `
          <div class="trow" data-j="${j}">
            <input class="mono" data-act="pool.network" value="${esc(p.network || "")}" placeholder="192.168.1.0/24">
            <input class="mono" data-act="pool.gateway" value="${esc(p.gateway || "")}" placeholder="192.168.1.1">
            <button class="mini danger" data-act="pool.del" data-j="${j}">×</button>
          </div>`).join("")}</div>
        <button class="mini full" data-act="pool.add">+ pool</button>
        <div class="hint">Los routers pueden apuntar sus interfaces al server con <code>helper</code>.</div>`;
    }
  } else {
    html += `<div class="hint">El hub no tiene configuracion: solo conecta equipos en la misma LAN.</div>`;
  }
  host.innerHTML = html;
}

function renderLinkProps() {
  const l = G.links[selected.id];
  if (!l) { selected = { kind: null, id: null }; return renderProps(); }
  $("ed-props-title").textContent = "Cable";
  $("ed-props").innerHTML = `
    <div class="link-ports">
      <b>${esc(l.a)}</b> ${esc(l.a_port)}<br><b>${esc(l.b)}</b> ${esc(l.b_port)}<br>tipo: ${esc(l.cable || "straight")}
    </div>
    <button class="mini full" data-act="link.recable">Reasignar puertos</button>
    <button class="mini full danger" data-act="link.del" style="margin-top:6px">Eliminar cable</button>
    <div class="hint">Tambien podes recablear desde la vista previa (click en el cable).</div>`;
}

function changeName(n, name) {
  if (!name || name === n.name) return;
  if (G.nodes.some((x) => x !== n && x.name === name)) {
    toastEd(`Ya existe un equipo llamado ${name}`, "err");
    renderProps();
    return;
  }
  const old = n.name;
  G.links.forEach((l) => { if (l.a === old) l.a = name; if (l.b === old) l.b = name; });
  n.name = name;
  selected.id = G.nodes.indexOf(n);
  save();
  renderCanvas();
}

function changeModel(n, model) {
  if (model === n.model) return;
  const ports = portsOf(model);
  const mine = G.links.filter((l) => l.a === n.name || l.b === n.name)
    .map((l) => (l.a === n.name ? l.a_port : l.b_port));
  const bad = mine.filter((p) => !ports.includes(p));
  if (bad.length && !confirm(`Los cables en ${bad.join(", ")} no existen en ${model}; se van a desconectar. Continuar?`)) {
    renderProps();
    return;
  }
  if (bad.length) {
    G.links = G.links.filter((l) => {
      if (l.a !== n.name && l.b !== n.name) return true;
      return !bad.includes(l.a === n.name ? l.a_port : l.b_port);
    });
  }
  n.model = model;
  const role = roleOf(model);
  if (role !== "router" && role !== "l3switch" && role !== "switch") {
    n.interfaces = [];
    n.vlans = [];
    n.access = [];
    n.trunks = [];
  }
  if (role === "switch") n.pools = [];
  save();
  renderCanvas();
  renderProps();
}

function onPropInput(e) {
  const el = e.target, act = el.dataset.act;
  if (!act || selected.kind !== "node") return;
  const n = G.nodes[selected.id];
  if (!n) return;
  const val = el.type === "checkbox" ? el.checked : el.value;
  const j = rowIndex(el);

  if (act === "node.name") { changeName(n, String(val).trim()); return; }
  if (act === "node.model") { changeModel(n, String(val)); return; }
  if (act === "node.x") { n.x = +val; }
  else if (act === "node.y") { n.y = +val; }
  else if (act === "node.routing") { if (val) n.routing = val; else delete n.routing; }
  else if (act === "node.dhcp") {
    n.dhcp = !!val;
    if (n.dhcp) { delete n.ip; delete n.gateway; }
    renderProps();
  }
  else if (act === "node.ip") { setOrDel(n, "ip", String(val).trim()); }
  else if (act === "node.gateway") { setOrDel(n, "gateway", String(val).trim()); }
  else if (act === "node.as") { if (String(val).trim()) n.as_number = +val; else delete n.as_number; }
  else if (act === "node.config") { n.config = String(val).split("\n").map((s) => s.trimEnd()).filter(Boolean); }
  else if (act.startsWith("iface.")) {
    const f = (n.interfaces || [])[j];
    if (!f) return;
    const field = act.split(".")[1];
    if (field === "dot1q") { if (String(val).trim()) f.dot1q = +val; else delete f.dot1q; }
    else setOrDel(f, field, String(val).trim());
  } else if (act.startsWith("vlan.")) {
    const v = (n.vlans || [])[j];
    if (!v) return;
    if (act === "vlan.id") {
      const old = v.id;
      v.id = +val || v.id;
      (n.interfaces || []).forEach((f) => { if (f.port === "Vlan" + old) f.port = "Vlan" + v.id; });
      (n.access || []).forEach((a) => { if (a.vlan === old) a.vlan = v.id; });
    } else if (act === "vlan.name") {
      setOrDel(v, "name", String(val).trim());
    } else if (act === "vlan.svi") {
      n.interfaces = n.interfaces || [];
      const port = "Vlan" + v.id;
      const idx = n.interfaces.findIndex((f) => f.port === port);
      if (String(val).trim()) {
        if (idx >= 0) n.interfaces[idx].ip = String(val).trim();
        else n.interfaces.push({ port, ip: String(val).trim() });
      } else if (idx >= 0) {
        n.interfaces.splice(idx, 1);
      }
    }
  } else if (act === "access.port") {
    if ((n.access || [])[j]) n.access[j].port = String(val);
  } else if (act === "access.vlan") {
    if ((n.access || [])[j]) n.access[j].vlan = +val;
  } else if (act === "trunk.port") {
    if ((n.trunks || [])[j] !== undefined) n.trunks[j] = String(val);
  } else if (act === "pool.network" || act === "pool.gateway") {
    const p = (n.pools || [])[j];
    if (!p) return;
    setOrDel(p, act.split(".")[1], String(val).trim());
  } else {
    return;
  }
  save();
  renderCanvas();
}

function onPropClick(e) {
  const el = e.target.closest("[data-act]");
  if (!el) return;
  const act = el.dataset.act;
  if (act.startsWith("link.")) {
    const l = G.links[selected.id];
    if (!l) return;
    if (act === "link.recable") {
      recableLink(selected.id);
    } else if (act === "link.del") {
      G.links.splice(selected.id, 1);
      selected = { kind: null, id: null };
      save(); renderCanvas(); renderProps();
    }
    return;
  }
  if (selected.kind !== "node") return;
  const n = G.nodes[selected.id];
  if (!n) return;
  const j = rowIndex(el);
  if (act === "iface.add") { n.interfaces = n.interfaces || []; n.interfaces.push({ port: nextFreePort(n) }); }
  else if (act === "iface.del") { (n.interfaces || []).splice(j, 1); }
  else if (act === "vlan.add") { n.vlans = n.vlans || []; n.vlans.push({ id: nextVlanId(n) }); }
  else if (act === "vlan.del") {
    const v = (n.vlans || [])[j];
    if (!v) return;
    n.vlans.splice(j, 1);
    n.interfaces = (n.interfaces || []).filter((f) => f.port !== "Vlan" + v.id);
    n.access = (n.access || []).filter((a) => a.vlan !== v.id);
  }
  else if (act === "access.add") {
    n.vlans = n.vlans || [];
    if (!n.vlans.length) n.vlans.push({ id: 1 });
    n.access = n.access || [];
    n.access.push({ port: firstFreePort(n), vlan: +n.vlans[0].id });
  }
  else if (act === "access.del") { (n.access || []).splice(j, 1); }
  else if (act === "trunk.add") { n.trunks = n.trunks || []; n.trunks.push(firstFreePort(n)); }
  else if (act === "trunk.del") { (n.trunks || []).splice(j, 1); }
  else if (act === "pool.add") { n.pools = n.pools || []; n.pools.push({ network: "", gateway: "" }); }
  else if (act === "pool.del") { (n.pools || []).splice(j, 1); }
  else return;
  save();
  renderCanvas();
  renderProps();
}

function nextFreePort(n) {
  const used = usedPorts(n.name);
  const inIfaces = new Set((n.interfaces || []).map((f) => f.port));
  const options = [...portsOf(n.model), ...(n.vlans || []).map((v) => "Vlan" + v.id)];
  for (const p of options) if (!used.has(p) && !inIfaces.has(p)) return p;
  return portsOf(n.model)[0] || "";
}
function firstFreePort(n) {
  const used = usedPorts(n.name);
  const busy = new Set([...(n.access || []).map((a) => a.port), ...(n.trunks || [])]);
  const fe = portsOf(n.model).filter((p) => p.startsWith("FastEthernet"));
  const pool = fe.length ? fe : portsOf(n.model);
  return pool.find((p) => !used.has(p) && !busy.has(p)) || pool[0] || "";
}
function nextVlanId(n) {
  const ids = new Set((n.vlans || []).map((v) => +v.id));
  let id = 10;
  while (ids.has(id)) id += 10;
  return id;
}

function recableLink(i) {
  const l = G.links[i];
  if (!l) return;
  pickPort(l.a, "Nuevo puerto de salida", (pa) => {
    pickPort(l.b, "Nuevo puerto de entrada", (pb) => {
      l.a_port = pa;
      l.b_port = pb;
      save();
      renderCanvas();
      renderProps();
    }, [l.b_port]);
  }, [l.a_port]);
}

/* ------------------------------------------------------------------ vista previa (modal) */
let pvZoom = null;
function initPreview() {
  if (pvZoom) return;
  pvZoom = makeZoom("ed-pv-pane", "ed-pv-stage");
  $("ed-pv-zin").onclick = () => pvZoom.zoomBy(1.25);
  $("ed-pv-zout").onclick = () => pvZoom.zoomBy(0.8);
  $("ed-pv-fit").onclick = () => pvZoom.fit();
}
async function openPreview() {
  if (!G.nodes.length) { toastEd("Agrega al menos un equipo.", "err"); return; }
  initPreview();
  $("ed-overlay").style.display = "";
  $("ed-pv-msg").style.display = "none";
  if (live.svg && !live.error) paintPreview(false);
  else await renderPreview();
  scheduleLive();
}
function closePreview() {
  $("ed-overlay").style.display = "none";
  save();
  renderCanvas();
}
function paintPreview(keepZoom) {
  if (!live.svg) return;
  const stageEl = $("ed-pv-stage");
  const hadSvg = !!stageEl.querySelector("svg");
  stageEl.innerHTML = live.svg;
  $("ed-pv-empty").style.display = "none";
  overlayEdits();
  if (!keepZoom || !hadSvg) pvZoom.fit();
  pvStats();
}
async function renderPreview() {
  const emptyEl = $("ed-pv-empty");
  emptyEl.style.display = "";
  emptyEl.textContent = "Generando vista previa…";
  try {
    const r = await api("/api/preview", { spec: specText(), name: G.name });
    live.svg = await r.text();
    live.error = null;
    setStatus("ok");
    clearProblems();
    paintPreview(false);
  } catch (err) {
    live.svg = null;
    live.error = String((err && err.message) || err);
    setStatus("err");
    emptyEl.textContent = "No se pudo generar la vista previa; mira los problemas.";
    showProblems(live.error);
  }
}
function pvStats() {
  const svg = $("ed-pv-stage").querySelector("svg");
  const stats = svg && svg.dataset.stats ? JSON.parse(svg.dataset.stats) : null;
  $("ed-pv-stats").innerHTML = !stats ? "" :
    `<span class="stat"><b>${stats.routers}</b> routers</span>
     <span class="stat"><b>${stats.switches}</b> switches</span>
     ${stats.hubs ? `<span class="stat"><b>${stats.hubs}</b> hubs</span>` : ""}
     <span class="stat"><b>${stats.hosts}</b> hosts</span>
     <span class="stat"><b>${stats.links}</b> enlaces</span>`;
}
function overlayEdits() {
  const svg = $("ed-pv-stage").querySelector("svg");
  if (!svg) return;
  const NS = "http://www.w3.org/2000/svg";
  const layer = document.createElementNS(NS, "g");
  G.links.forEach((l, i) => {
    const a = findNode(l.a), b = findNode(l.b);
    if (!a || !b) return;
    const ln = document.createElementNS(NS, "line");
    ln.setAttribute("x1", a.x); ln.setAttribute("y1", a.y);
    ln.setAttribute("x2", b.x); ln.setAttribute("y2", b.y);
    ln.setAttribute("stroke", "rgba(229,83,75,0)");
    ln.setAttribute("stroke-width", "16");
    ln.setAttribute("class", "ov-link");
    ln.style.cursor = "pointer";
    ln.addEventListener("click", (e) => { e.stopPropagation(); recableLink(i); });
    layer.appendChild(ln);
  });
  G.nodes.forEach((n) => {
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", n.x); c.setAttribute("cy", n.y); c.setAttribute("r", 34);
    c.setAttribute("fill", "rgba(77,140,245,0.001)");
    c.setAttribute("class", "ov-node");
    c.style.cursor = "grab";
    c.addEventListener("mousedown", (e) => {
      e.stopPropagation();
      e.preventDefault();
      const p = toSvg(e, $("ed-pv-pane"));
      pvDrag = { n, circle: c, sx: p.x, sy: p.y, ox: n.x, oy: n.y, moved: false, targets: pvTargets(n) };
      c.setAttribute("stroke", "#4d8cf5");
      c.setAttribute("stroke-width", "2");
      c.setAttribute("stroke-dasharray", "7 5");
      c.setAttribute("fill", "rgba(77,140,245,.08)");
    });
    layer.appendChild(c);
  });
  svg.appendChild(layer);
}
let pvDrag = null;
function pvTargets(n) {
  const svg = $("ed-pv-stage").querySelector("svg");
  const out = { icons: [], texts: [], lines: [] };
  if (!svg) return out;
  svg.querySelectorAll("text").forEach((t) => {
    const tx = parseFloat(t.getAttribute("x") || "NaN"), ty = parseFloat(t.getAttribute("y") || "NaN");
    if (Math.abs(tx - n.x) < 2 && Math.abs(ty - n.y) < 80) out.texts.push({ el: t, x: tx, y: ty });
  });
  svg.querySelectorAll("use, image").forEach((u) => {
    if (u.closest("defs")) return;
    let w = parseFloat(u.getAttribute("width") || "0"), h = parseFloat(u.getAttribute("height") || "0");
    if ((!w || !h) && u.tagName.toLowerCase() === "use") {
      const href = u.getAttribute("href") || "";
      const ref = href.startsWith("#") ? svg.querySelector('[id="' + href.slice(1) + '"]') : null;
      if (ref) {
        w = parseFloat(ref.getAttribute("width") || "0");
        h = parseFloat(ref.getAttribute("height") || "0");
      }
    }
    const x = parseFloat(u.getAttribute("x") || "NaN"), y = parseFloat(u.getAttribute("y") || "NaN");
    if (!w || !h || Number.isNaN(x) || Number.isNaN(y)) return;
    if (Math.abs(x + w / 2 - n.x) < 45 && Math.abs(y + h / 2 - n.y) < 45) out.icons.push({ el: u, x, y });
  });
  const near = (px, py) => Math.abs(px - n.x) < 3 && Math.abs(py - n.y) < 3;
  svg.querySelectorAll("line").forEach((ln) => {
    const x1 = parseFloat(ln.getAttribute("x1")), y1 = parseFloat(ln.getAttribute("y1"));
    const x2 = parseFloat(ln.getAttribute("x2")), y2 = parseFloat(ln.getAttribute("y2"));
    if (near(x1, y1)) out.lines.push({ el: ln, end: "a", x1, y1, x2, y2 });
    else if (near(x2, y2)) out.lines.push({ el: ln, end: "b", x1, y1, x2, y2 });
  });
  return out;
}
window.addEventListener("mousemove", (e) => {
  if (!pvDrag) return;
  const p = toSvg(e, $("ed-pv-pane"));
  const dx = p.x - pvDrag.sx, dy = p.y - pvDrag.sy;
  if (Math.abs(dx) + Math.abs(dy) > 4) pvDrag.moved = true;
  if (!pvDrag.moved) return;
  pvDrag.n.x = Math.round(pvDrag.ox + dx);
  pvDrag.n.y = Math.round(pvDrag.oy + dy);
  pvDrag.circle.setAttribute("cx", pvDrag.n.x);
  pvDrag.circle.setAttribute("cy", pvDrag.n.y);
  pvDrag.targets.icons.forEach((it) => { it.el.setAttribute("x", it.x + dx); it.el.setAttribute("y", it.y + dy); });
  pvDrag.targets.texts.forEach((it) => { it.el.setAttribute("x", it.x + dx); it.el.setAttribute("y", it.y + dy); });
  pvDrag.targets.lines.forEach((it) => {
    if (it.end === "a") { it.el.setAttribute("x1", it.x1 + dx); it.el.setAttribute("y1", it.y1 + dy); }
    else { it.el.setAttribute("x2", it.x2 + dx); it.el.setAttribute("y2", it.y2 + dy); }
  });
});
window.addEventListener("mouseup", () => {
  if (pvDrag) {
    if (pvDrag.moved) save();
    pvDrag = null;
  }
});

/* ------------------------------------------------------------------ generar / export / import */
function pvMessage(html, kind) {
  const el = $("ed-pv-msg");
  el.className = "pv-msg " + (kind || "");
  el.innerHTML = html;
  el.style.display = "";
}
async function generate() {
  if (!G.nodes.length) { toastEd("Agrega al menos un equipo.", "err"); return; }
  const btns = [$("ed-generate"), $("ed-pv-generate")];
  btns.forEach((b) => { b.disabled = true; });
  toastEd("Generando .pkt…", "");
  if (isPreviewOpen()) pvMessage("Generando .pkt…", "");
  try {
    const r = await api("/api/generate", { spec: specText(), name: G.name });
    const data = await r.json();
    toastEd("Listo: " + data.file, "ok");
    const dl = $("ed-dl");
    dl.href = data.download;
    dl.textContent = "Descargar " + (G.name || "lab") + ".pkt";
    dl.style.display = "block";
    if (isPreviewOpen()) {
      pvMessage(
        `Generado: <code>${esc(data.file)}</code> <a class="dl-inline" href="${esc(data.download)}" download>descargar .pkt</a>`,
        "ok",
      );
    }
    const tmp = document.createElement("a");
    tmp.href = data.download;
    tmp.download = "";
    document.body.appendChild(tmp);
    tmp.click();
    tmp.remove();
    clearProblems();
  } catch (err) {
    showProblems(err.message);
    toastEd("No se pudo generar el .pkt (mira los problemas).", "err");
    if (isPreviewOpen()) pvMessage("No se pudo generar: " + esc(err.message), "err");
  } finally {
    btns.forEach((b) => { b.disabled = false; });
  }
}

function exportSpec() {
  const blob = new Blob([JSON.stringify(cleanSpec(), null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = (G.name || "lab") + ".json";
  a.click();
  URL.revokeObjectURL(a.href);
}

async function loadSpecText(text) {
  let spec = null;
  if (text.trim().startsWith("{")) {
    try { spec = JSON.parse(text); } catch (_) { spec = null; }
  }
  if (!spec || (!spec.nodes && !spec.sites)) {
    try {
      const r = await api("/api/normalize", { spec: text, name: G.name });
      spec = (await r.json()).spec;
    } catch (err) {
      toastEd("No se pudo leer el archivo: " + err.message, "err");
      return;
    }
  }
  if (spec.nodes && spec.nodes.length) {
    G.name = spec.name || G.name;
    G.routing = spec.routing || "none";
    ["ospf_process", "ospf_area", "eigrp_as", "bgp_as_base"].forEach((k) => { if (spec[k] != null) G[k] = spec[k]; });
    const slots = { 160: 0, 350: 0, 560: 0 };
    G.nodes = spec.nodes.map((n) => {
      const role = roleOf(n.model);
      const y = { router: 160, l3switch: 160, switch: 350, hub: 350 }[role] ?? 560;
      const k = slots[y]++;
      return {
        ...n,
        x: n.x != null ? Math.round(n.x) : 240 + k * 180,
        y: n.y != null ? Math.round(n.y) : y,
        interfaces: n.interfaces || [], vlans: n.vlans || [],
        access: n.access || [], trunks: n.trunks || [], pools: n.pools || [],
      };
    });
    G.links = (spec.links || []).map((l) => ({ ...l }));
    selected = { kind: null, id: null };
    syncToolbar();
    save();
    renderCanvas();
    renderProps();
    edZoom.fit();
    clearProblems();
    toastEd("Spec cargada en el editor.", "ok");
  } else if (spec.sites && spec.sites.length) {
    alert("Esa spec usa el modo rapido (sites); se cargo en la pestana Rapido.");
    $("spec").value = JSON.stringify(spec, null, 2);
    document.querySelector('.mtab[data-view="fast"]').click();
    switchTab("adv");
  } else {
    toastEd("La spec no tiene nodos.", "err");
  }
}

function clearAll() {
  if (!confirm("Vaciar el plano? Se pierde la topologia actual.")) return;
  G = fresh();
  selected = { kind: null, id: null };
  syncToolbar();
  save();
  renderCanvas();
  renderProps();
  clearProblems();
  toastEd("Plano vaciado.", "ok");
}

/* ------------------------------------------------------------------ toolbar */
function renderExtras() {
  const fields = {
    ospf: [["ospf_process", "Proceso OSPF", 1, 65535], ["ospf_area", "Area OSPF", 0, 255]],
    eigrp: [["eigrp_as", "AS EIGRP", 1, 65535]],
    bgp: [["bgp_as_base", "AS base BGP", 1, 60000]],
  }[G.routing] || [];
  $("ed-extras").innerHTML = fields.map(([k, label, min, max]) =>
    `<div><label>${esc(label)}</label><input type="number" data-g="${k}" min="${min}" max="${max}" value="${G[k] ?? ""}"></div>`).join("");
  $("ed-extras").querySelectorAll("input").forEach((inp) =>
    inp.addEventListener("input", () => { G[inp.dataset.g] = +inp.value; save(); }));
}
function syncToolbar() {
  $("ed-name").value = G.name;
  $("ed-routing").value = G.routing || "none";
  renderExtras();
}
function bindToolbar() {
  const nameInp = $("ed-name");
  nameInp.value = G.name || "lab";
  nameInp.addEventListener("input", () => { G.name = nameInp.value.trim() || "lab"; save(); });
  const routingSel = $("ed-routing");
  routingSel.value = G.routing || "none";
  routingSel.addEventListener("change", () => { G.routing = routingSel.value; renderExtras(); save(); });
  renderExtras();
  $("ed-preview").addEventListener("click", openPreview);
  $("ed-generate").addEventListener("click", generate);
  $("ed-pv-refresh").addEventListener("click", renderPreview);
  $("ed-pv-generate").addEventListener("click", generate);
  $("ed-pv-apply").addEventListener("click", closePreview);
  $("ed-export").addEventListener("click", exportSpec);
  $("ed-clear").addEventListener("click", clearAll);
  $("ed-connect").addEventListener("click", toggleConnect);
  $("ed-zin").addEventListener("click", () => edZoom.zoomBy(1.25));
  $("ed-zout").addEventListener("click", () => edZoom.zoomBy(0.8));
  $("ed-fit").addEventListener("click", () => edZoom.fit());
  $("ed-import-btn").addEventListener("click", () => $("ed-import").click());
  $("ed-import").addEventListener("change", async () => {
    const file = $("ed-import").files[0];
    if (!file) return;
    const text = await file.text();
    $("ed-import").value = "";
    await loadSpecText(text);
  });
  const props = $("ed-props");
  props.addEventListener("input", onPropInput);
  props.addEventListener("change", onPropInput);
  props.addEventListener("click", onPropClick);
  $("ed-picker-cancel").addEventListener("click", () => {
    closePicker();
    pending = null;
    cableMode = false;
    updateConnectHint();
  });
}

/* ------------------------------------------------------------------ init */
function fitEditor() { edZoom.fit(); }
window.editorShown = fitEditor;

async function init() {
  try {
    const [mm, ii] = await Promise.all([
      fetch("/api/models").then((r) => r.json()),
      fetch("/api/icons").then((r) => r.json()),
    ]);
    GROUPS = mm.groups || {};
    ICONS = ii.icons || {};
    Object.entries(GROUPS).forEach(([role, list]) => list.forEach((m) => { MODELS[m.name] = { ...m, role }; }));
  } catch (e) {
    toastEd("No se pudo cargar el catalogo de modelos: " + e, "err");
  }
  buildPalette();
  bindToolbar();
  renderCanvas();
  renderProps();
  updateConnectHint();
  setStatus(G.nodes.length ? "checking" : null);
  if (G.nodes.length) scheduleLive();
  requestAnimationFrame(fitEditor);
}
init();
})();
