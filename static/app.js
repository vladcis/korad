/* KORAD KA3005P web UI */
'use strict';
const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));

// ---------------------------------------------------------------- utils
async function api(path, method = 'GET', body) {
  const r = await fetch('/api' + path, {
    method, headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  let j = {};
  try { j = await r.json(); } catch (_) { }
  if (!r.ok || j.ok === false) throw new Error(j.error || r.statusText);
  return j;
}
let toastT;
function toast(msg, ok = false) {
  const t = $('#toast'); t.textContent = msg; t.className = 'toast' + (ok ? ' ok' : ''); t.hidden = false;
  clearTimeout(toastT); toastT = setTimeout(() => t.hidden = true, ok ? 1800 : 4000);
}
function guard(p) { return p.catch(e => toast(e.message)); }
const fmtT = t => new Date(t * 1000).toLocaleTimeString('en-GB');
const fmtDT = t => new Date(t * 1000).toLocaleString('en-GB');

// ---------------------------------------------------------------- 7-segment
const SEG = {
  '0': 'abcdef', '1': 'bc', '2': 'abdeg', '3': 'abcdg', '4': 'bcfg', '5': 'acdfg', '6': 'acdefg', '7': 'abc',
  '8': 'abcdefg', '9': 'abcdfg', '-': 'g', ' ': '', 'O': 'abcdef', 'F': 'aefg', 'E': 'adefg', 'r': 'eg',
  'C': 'adef', 'L': 'def', 'P': 'abefg', 'H': 'bcefg', 'n': 'ceg', 'o': 'cdeg', 't': 'defg', 'U': 'bcdef',
};
// segment geometry in a 44x74 box
const GEO = {
  a: 'M8,4 h26 l-5,6 h-16 z', g: 'M8,37 l5,-3 h16 l5,3 l-5,3 h-16 z', d: 'M8,70 l5,-6 h16 l5,6 z',
  b: 'M36,6 l6,-3 v30 l-6,4 l-4,-4 v-23 z', c: 'M36,41 l6,-4 v30 l-6,-3 l-4,-4 v-15 z',
  f: 'M8,6 l-6,-3 v30 l6,4 l4,-4 v-23 z', e: 'M8,41 l-6,-4 v30 l6,-3 l4,-4 v-15 z',
};
function sevenSeg(text, digits) {
  // split text into characters; a dot attaches to the previous character
  const cells = [];
  for (const ch of text) {
    if (ch === '.' && cells.length) cells[cells.length - 1].dp = true;
    else cells.push({ ch, dp: false });
  }
  while (cells.length < digits) cells.unshift({ ch: ' ', dp: false });
  const w = 50, h = 74;
  let svg = `<svg viewBox="0 0 ${w * cells.length} ${h}" xmlns="http://www.w3.org/2000/svg">`;
  cells.forEach((c, i) => {
    const on = SEG[c.ch] ?? SEG[c.ch.toUpperCase()] ?? '';
    svg += `<g transform="translate(${i * w},0)">`;
    for (const s of 'abcdefg') {
      const lit = on.includes(s);
      svg += `<path d="${GEO[s]}" fill="${lit ? '#ff3b1f' : '#1e0c09'}" ${lit ? 'filter="url(#glow)"' : ''}/>`;
    }
    svg += `<circle cx="46" cy="69" r="3.2" fill="${c.dp ? '#ff3b1f' : '#1e0c09'}"/></g>`;
  });
  svg += `<defs><filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="1.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs></svg>`;
  return svg;
}
const segCache = {};
function setSeg(id, text, digits) {
  if (segCache[id] === text) return;
  segCache[id] = text;
  document.getElementById(id).innerHTML = sevenSeg(text, digits);
}

// ---------------------------------------------------------------- UI state
const ui = { lock: false, mA: false, memSel: 0, editingV: false, editingI: false, lastState: null };
const chart = { data: [], win: 60, showP: false };

function setTog(id, on, label) {
  const b = $('#' + id); b.classList.toggle('on', !!on);
  const st = b.querySelector('.st'); if (st) st.textContent = label || (on ? 'ON' : 'OFF');
}
// A value just set from the panel wins over the polled one for a moment: the server reads
// VSET/ISET back only every few polls, so without this the old value flashes back in.
const PENDING_MS = 2000;
const pending = { v: null, i: null };
function setPending(k, val) { pending[k] = { val, until: Date.now() + PENDING_MS }; }
function shownSet(k, server) {
  const p = pending[k];
  if (!p) return server;
  if (Date.now() > p.until) { pending[k] = null; return server; }
  return p.val;
}

function setTitle(t) {
  if (document.body.classList.contains('trend-view')) t = 'Trend · ' + t;
  if (ui.title === t) return;
  ui.title = t; document.title = t;
  const api = window.pywebview && window.pywebview.api;
  if (api && api.set_title) api.set_title(t);       // native window title (desktop app)
}
window.addEventListener('pywebviewready', () => { const t = ui.title; ui.title = null; if (t) setTitle(t.replace(/^Trend · /, '')); });
function led(id, on, green) { const e = $('#' + id); e.classList.toggle('on', !!on); e.classList.toggle('green', !!green); }

function applyState(s) {
  ui.lastState = s;
  const conn = s.connected;
  $('#connDot').className = 'dot ' + (conn ? (s.error ? 'err' : 'on') : 'off');
  // device name, SN and port go to the window title; the header only shows a problem
  setTitle(conn ? `${s.idn} · ${s.port}` : 'KORAD – ' + (s.error || 'not connected'));
  $('#idn').textContent = conn ? '' : (s.error || 'not connected');
  $('#btnConnect').hidden = conn; $('#btnDisconnect').hidden = !conn;
  $('#dispErr').textContent = s.error || '';

  if (!conn) { setSeg('segV', '----', 4); setSeg('segI', '----', 4); setSeg('segP', '-OFF', 4); return; }
  // like the real display: set values while the output is off, measured values while on
  const vset = shownSet('v', s.vset), iset = shownSet('i', s.iset);
  const dv = s.output ? s.vout : vset, di = s.output ? s.iout : iset;
  setSeg('segV', dv.toFixed(2).padStart(5, '0'), 4);
  if (ui.mA && di < 1) setSeg('segI', (di * 1000).toFixed(0), 4); else setSeg('segI', di.toFixed(3), 4);
  $('#unitMA').classList.toggle('on', ui.mA && di < 1);
  setSeg('segP', s.output ? (s.power < 10 ? s.power.toFixed(2) : s.power < 100 ? s.power.toFixed(2) : s.power.toFixed(1)) : '-OFF', 4);
  led('ledCV', s.output && s.mode === 'CV'); led('ledCC', s.output && s.mode === 'CC');
  led('ledON', s.output, true); led('ledOCP', s.ocp); led('ledOVP', s.ovp); led('ledBEEP', s.beep);
  led('ledLOCK', ui.lock || ui.scriptRunning);
  $('#btnOUT').classList.toggle('on', s.output); $('#btnOUT').textContent = s.output ? 'OUTPUT ON  ·  turn OFF' : 'OUTPUT OFF  ·  turn ON';
  setTog('btnOCP', s.ocp); setTog('btnOVP', s.ovp); setTog('btnBEEP', s.beep);
  if (s.limits_supported !== false) {
    if (!ui.editingOCP && s.ocp_limit != null) $('#inOCP').value = s.ocp_limit.toFixed(3);
    if (!ui.editingOVP && s.ovp_limit != null) $('#inOVP').value = s.ovp_limit.toFixed(2);
  } else { $('#limitsNote').hidden = false; $('#inOCP').disabled = $('#inOVP').disabled = true; }
  if (!ui.editingV && !ui.dragV) { $('#inV').value = vset.toFixed(2); $('#slV').value = vset; }
  if (!ui.editingI && !ui.dragI) { $('#inI').value = iset.toFixed(3); $('#slI').value = iset; }
  const lastT = chart.data.length ? chart.data[chart.data.length - 1].t : 0;
  if (s.t > lastT) chart.data.push({ t: s.t, v: s.vout, i: s.iout, p: s.power });
  const cut = s.t - 3700;
  while (chart.data.length && chart.data[0].t < cut) chart.data.shift();
  drawTrend();
}

// ---------------------------------------------------------------- chart
function drawChart(cv, data, opt) {
  const dpr = window.devicePixelRatio || 1;
  // data-fill canvas takes its size from CSS, the others keep their height attribute
  const W = cv.clientWidth, H = cv.dataset.fill ? cv.clientHeight : cv.height / (cv._dpr || 1) || 220;
  if (!W || !H) return;
  if (cv.width !== W * dpr || cv.height !== H * dpr) { cv.width = W * dpr; cv.height = H * dpr; cv._dpr = dpr; }
  const g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, W, H);
  const L = 46, R = opt.showP ? 92 : 46, T = 10, B = 24, pw = W - L - R, ph = H - T - B;
  g.font = '11px system-ui'; g.fillStyle = '#777'; g.strokeStyle = '#26282d';
  if (data.length < 2) { g.fillText('waiting for data…', L + 10, T + 20); return; }
  const t0 = opt.t0 ?? data[0].t, t1 = opt.t1 ?? data[data.length - 1].t, span = Math.max(1e-3, t1 - t0);
  cv._x = { L, pw, t0, t1 };            // for mouse zoom / pan
  const mx = (k, pad) => { let m = 0; for (const d of data) if (d[k] > m) m = d[k]; return m <= 0 ? pad : m * 1.1; };
  const vmax = mx('v', 1), imax = mx('i', 0.1), pmax = mx('p', 1);
  const X = t => L + (t - t0) / span * pw;
  const Y = (val, max) => T + ph - val / max * ph;
  // grid
  for (let k = 0; k <= 4; k++) {
    const y = T + ph * k / 4; g.beginPath(); g.moveTo(L, y); g.lineTo(L + pw, y); g.stroke();
    g.fillStyle = '#ff6a3d'; g.textAlign = 'right'; g.fillText((vmax * (1 - k / 4)).toFixed(1), L - 4, y + 4);
    g.fillStyle = '#3ec8ff'; g.textAlign = 'left'; g.fillText((imax * (1 - k / 4)).toFixed(2), L + pw + 4, y + 4);
    if (opt.showP) { g.fillStyle = '#9cff57'; g.fillText((pmax * (1 - k / 4)).toFixed(1), L + pw + 46, y + 4); }
  }
  g.fillStyle = '#777'; g.textAlign = 'center';
  for (let k = 0; k <= 4; k++) {
    const t = t0 + span * k / 4; const x = X(t);
    g.beginPath(); g.moveTo(x, T); g.lineTo(x, T + ph); g.stroke();
    g.fillText(opt.rel ? `${(t - t0).toFixed(0)} s` : fmtT(t), x, H - 6);
  }
  const line = (k, max, color) => {
    g.beginPath(); g.strokeStyle = color; g.lineWidth = 1.6;
    data.forEach((d, i) => { const x = X(d.t), y = Y(d[k], max); i ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.stroke();
  };
  g.save(); g.beginPath(); g.rect(L, T - 2, pw, ph + 4); g.clip();
  if (opt.showP) line('p', pmax, '#9cff57');
  line('i', imax, '#3ec8ff'); line('v', vmax, '#ff6a3d');
  g.restore();
  if (opt.note) { g.fillStyle = '#e0b64a'; g.textAlign = 'left'; g.fillText(opt.note, L + 8, T + 14); }
}
// trend view: chart.span seconds wide, ending at chart.end (null = follow the live data)
chart.span = chart.win; chart.end = null;
function drawTrend() {
  const d = chart.data;
  if (!d.length) return drawChart($('#chart'), d, { showP: chart.showP });
  const last = d[d.length - 1].t;
  if (chart.end !== null && chart.end >= last) chart.end = null;
  const t1 = chart.end ?? last, t0 = t1 - chart.span;
  let a = 0, b = d.length;                // visible samples + one on each side, so lines reach the edges
  while (a < b && d[a].t < t0) a++;
  while (b > a && d[b - 1].t > t1) b--;
  const vis = d.slice(Math.max(0, a - 1), Math.min(d.length, b + 1));
  drawChart($('#chart'), vis, { showP: chart.showP, t0, t1,
    note: chart.end !== null ? '⏸ paused – scroll right or double-click for live' : '' });
}
function trendView(span, end) {
  const d = chart.data; if (!d.length) return;
  const first = d[0].t, last = d[d.length - 1].t;
  chart.span = Math.min(Math.max(span, 5), Math.max(chart.win, last - first, 5));
  chart.end = end === null || end >= last ? null : Math.max(end, first + chart.span);
  drawTrend();
}
// wheel = zoom around the cursor, horizontal wheel / Shift+wheel = pan, double-click = reset
$('#chart').addEventListener('wheel', e => {
  const cv = e.currentTarget, x = cv._x; if (!x || !chart.data.length) return;
  e.preventDefault();
  const k = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1;   // lines / pages -> px
  const dx = (e.shiftKey ? e.deltaY : e.deltaX) * k, dy = e.shiftKey ? 0 : e.deltaY * k;
  const span = x.t1 - x.t0;
  if (Math.abs(dx) > Math.abs(dy)) return trendView(span, x.t1 + dx / x.pw * span);
  // live view zooms around "now" (stays live), a paused view around the cursor
  const frac = chart.end === null ? 1 : Math.min(1, Math.max(0, (e.offsetX - x.L) / x.pw));
  const tc = x.t0 + frac * span, ns = span * Math.exp(dy * 0.0015);
  trendView(ns, tc + (1 - frac) * ns);
}, { passive: false });
$('#chart').ondblclick = () => { chart.span = chart.win; chart.end = null; drawTrend(); };
$('#chartWin').onchange = e => { chart.win = +e.target.value; chart.span = chart.win; chart.end = null; drawTrend(); };
$('#chShowP').onchange = e => { chart.showP = e.target.checked; drawTrend(); };
$('#chartClear').onclick = () => { chart.data = []; chart.span = chart.win; chart.end = null; drawTrend(); };
window.addEventListener('resize', () => ui.lastState && applyState(ui.lastState));
// desktop app: closing the window while a script runs (called from desktop.py)
function askQuit() {
  const name = $('#scriptLockName').textContent || 'A script';
  if (confirm(`${name} is still running.\n\nStop it (the output is switched off) and quit?`)) window.pywebview.api.quit();
}
// trend in its own window: native pywebview window in the desktop app, popup in the browser
$('#trendPop').onclick = () => {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.open_trend) window.pywebview.api.open_trend();
  else window.open('/?view=trend', 'korad-trend', 'popup,width=1100,height=520');
};
if (new URLSearchParams(location.search).get('view') === 'trend') {
  document.body.classList.add('trend-view');
  document.title = 'Trend · KORAD';
}

// ---------------------------------------------------------------- SSE
function connectStream() {
  const es = new EventSource('/api/stream');
  es.addEventListener('state', e => applyState(JSON.parse(e.data)));
  es.addEventListener('script', e => onScriptEvent(JSON.parse(e.data)));
  es.addEventListener('logger', e => onLoggerInfo(JSON.parse(e.data)));
  es.addEventListener('event', e => addEvent(JSON.parse(e.data)));
  es.addEventListener('cmd', e => addCmd(JSON.parse(e.data)));
  es.onerror = () => { $('#connDot').className = 'dot err'; $('#idn').textContent = 'server unreachable…'; setTitle('KORAD – server unreachable'); };
}

// ---------------------------------------------------------------- connection
async function loadPorts() {
  const j = await api('/ports');
  const sel = $('#portSel'); sel.innerHTML = '<option value="">(auto)</option>';
  for (const p of j.ports) {
    const o = document.createElement('option'); o.value = p.device;
    o.textContent = `${p.device} ${p.korad ? '★ KORAD' : ''} ${p.description !== 'n/a' ? p.description : ''}`;
    if (p.device === j.current) o.selected = true;
    sel.appendChild(o);
  }
  if (j.baud) $('#baudSel').value = String(j.baud);
}
$('#portSel').onfocus = () => guard(loadPorts());
$('#btnConnect').onclick = () => guard(api('/connect', 'POST', { port: $('#portSel').value, baud: +$('#baudSel').value }).then(j => toast('Connected: ' + j.idn, true)));
$('#btnDisconnect').onclick = () => guard(api('/disconnect', 'POST'));

// ---------------------------------------------------------------- controls
function locked() {
  if (ui.scriptRunning) { toast('A script is running – the panel is locked. Stop it with the Stop button.'); return true; }
  if (ui.lock) { toast('Controls are locked (LOCK)'); return true; }
  return false;
}
function applyLocks() {
  const lk = ui.lock || ui.scriptRunning;
  led('ledLOCK', lk);
  $('.controls').classList.toggle('locked', !!ui.scriptRunning);
  $('#scriptLock').hidden = !ui.scriptRunning;
  setTog('btnLOCK', ui.lock, ui.scriptRunning ? 'SCRIPT' : undefined);
}
$('#btnStopScript').onclick = () => guard(api('/scripts/stop', 'POST'));
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
async function setV(v) {
  if (locked()) return;
  v = Math.round(clamp(+v, 0, 30) * 100) / 100;
  if (!ui.dragV) { $('#inV').value = v.toFixed(2); $('#slV').value = v; setPending('v', v); }
  if (ui.lastState) applyState(ui.lastState);
  await guard(api('/set', 'POST', { v }));
}
async function setI(i) {
  if (locked()) return;
  i = Math.round(clamp(+i, 0, 5) * 1000) / 1000;
  if (!ui.dragI) { $('#inI').value = i.toFixed(3); $('#slI').value = i; setPending('i', i); }
  if (ui.lastState) applyState(ui.lastState);
  await guard(api('/set', 'POST', { i }));
}

$('#inV').onfocus = () => ui.editingV = true; $('#inI').onfocus = () => ui.editingI = true;
$('#inV').onblur = () => ui.editingV = false; $('#inI').onblur = () => ui.editingI = false;
$('#inV').onchange = e => setV(e.target.value); $('#inI').onchange = e => setI(e.target.value);
$('#inV').onkeydown = e => { if (e.key === 'Enter') e.target.blur(); };
$('#inI').onkeydown = e => { if (e.key === 'Enter') e.target.blur(); };
// slider: while it is held nothing overwrites it; the value goes to the PSU at most every 200 ms
// during the drag and once more, exactly, on release
function bindSlider(sl, inp, k, digits, send) {
  const drag = 'drag' + k.toUpperCase();
  let timer = null;
  const end = () => { ui[drag] = false; };
  sl.addEventListener('pointerdown', () => { ui[drag] = true; });
  sl.addEventListener('pointerup', end); sl.addEventListener('pointercancel', end);
  sl.oninput = () => {
    if (ui.scriptRunning || ui.lock) return;
    inp.value = (+sl.value).toFixed(digits); setPending(k, +sl.value);
    if (!timer) timer = setTimeout(() => { timer = null; send(+sl.value); }, 200);
  };
  sl.onchange = () => { clearTimeout(timer); timer = null; end(); send(+sl.value); };
}
bindSlider($('#slV'), $('#inV'), 'v', 2, setV);
bindSlider($('#slI'), $('#inI'), 'i', 3, setI);
$$('[data-dv]').forEach(b => b.onclick = () => setV(+$('#inV').value + +b.dataset.dv));
$$('[data-di]').forEach(b => b.onclick = () => setI(+$('#inI').value + +b.dataset.di));
$$('[data-pv]').forEach(b => b.onclick = () => setV(+b.dataset.pv));
$$('[data-pi]').forEach(b => b.onclick = () => setI(+b.dataset.pi));

$('#btnOUT').onclick = () => { if (locked()) return; guard(api('/output', 'POST', { on: !ui.lastState?.output })); };
$('#btnOCP').onclick = () => { if (locked()) return; guard(api('/ocp', 'POST', { on: !ui.lastState?.ocp })); };
$('#btnOVP').onclick = () => { if (locked()) return; guard(api('/ovp', 'POST', { on: !ui.lastState?.ovp })); };
$('#btnBEEP').onclick = () => { if (locked()) return; guard(api('/beep', 'POST', { on: !ui.lastState?.beep })); };
$('#btnLOCK').onclick = () => { if (ui.scriptRunning) return locked(); ui.lock = !ui.lock; applyLocks(); };
$('#btnMA').onclick = () => { ui.mA = !ui.mA; setTog('btnMA', ui.mA, ui.mA ? 'mA' : 'A'); segCache.segI = null; ui.lastState && applyState(ui.lastState); };
// OCP / OVP thresholds
$('#inOCP').onfocus = () => ui.editingOCP = true; $('#inOVP').onfocus = () => ui.editingOVP = true;
$('#inOCP').onblur = () => ui.editingOCP = false; $('#inOVP').onblur = () => ui.editingOVP = false;
$('#inOCP').onchange = e => { if (locked()) return; guard(api('/limits', 'POST', { ocp: +e.target.value }).then(j => toast(`OCP threshold ${j.ocp_limit.toFixed(3)} A`, true))); };
$('#inOVP').onchange = e => { if (locked()) return; guard(api('/limits', 'POST', { ovp: +e.target.value }).then(j => toast(`OVP threshold ${j.ovp_limit.toFixed(2)} V`, true))); };
$('#inOCP').onkeydown = e => { if (e.key === 'Enter') e.target.blur(); };
$('#inOVP').onkeydown = e => { if (e.key === 'Enter') e.target.blur(); };
$$('.key.mem').forEach(b => b.onclick = async () => {
  if (locked()) return;
  const m = +b.dataset.m, save = $('#memSave').checked;
  if (save && !confirm(`Save current settings to M${m}?`)) return;
  await guard(api(`/memory/${m}/${save ? 'save' : 'recall'}`, 'POST').then(() => {
    toast(save ? `Saved to M${m}` : `Recalled M${m}`, true);
    $('#memSave').checked = false; ui.memSel = m;
    $$('.mems .led-lbl').forEach(l => l.querySelector('.led').classList.toggle('on', +l.dataset.m === m));
  }));
});

// V/A presets
let presets = [];
async function loadPresets() {
  presets = (await api('/presets')).items; renderPresets();
}
function renderPresets() {
  const g = $('#presetGrid'); g.innerHTML = '';
  presets.forEach((p, n) => {
    const b = document.createElement('button'); b.className = 'key';
    b.textContent = `${p.v.toFixed(2)}V ${p.i.toFixed(3)}A`;
    b.onclick = async () => {
      if (locked()) return;
      if ($('#presetSave').checked) {
        const s = ui.lastState; if (!s) return;
        presets[n] = { v: s.vset, i: s.iset }; $('#presetSave').checked = false;
        await guard(api('/presets', 'PUT', { items: presets })); renderPresets(); toast(`Preset ${n + 1} saved`, true);
      } else {
        await guard(api(`/presets/${n}/apply`, 'POST').then(() => toast(`Set ${p.v} V / ${p.i} A`, true)));
      }
    };
    g.appendChild(b);
  });
}

// quick logging from the panel
$('#qlogBtn').onclick = () => {
  const info = ui.loggerInfo;
  if (info?.active) guard(api('/logs/stop', 'POST'));
  else guard(api('/logs/start', 'POST', { name: $('#qlogName').value, interval: +$('#logInt').value || 1 }));
};

// ---------------------------------------------------------------- tabs
function showTab(name) { const t = $$('.tab').find(x => x.dataset.tab === name); if (t) t.onclick(); }
$$('.tab').forEach(t => t.onclick = () => {
  $$('.tab').forEach(x => x.classList.remove('active')); t.classList.add('active');
  history.replaceState(null, '', '#' + t.dataset.tab);
  $$('.tabpane').forEach(p => p.classList.toggle('active', p.id === 'tab-' + t.dataset.tab));
  if (t.dataset.tab === 'scripts') loadScripts();
  if (t.dataset.tab === 'program') loadSequences();
  if (t.dataset.tab === 'logs') loadLogs();
  if (t.dataset.tab === 'console') loadConsole();
});

// ---------------------------------------------------------------- scripts
const code = $('#code'), gutter = $('#gutter');
let currentScript = null, dirty = false;
function updateGutter() {
  const n = code.value.split('\n').length;
  gutter.textContent = Array.from({ length: n }, (_, i) => i + 1).join('\n');
  gutter.scrollTop = code.scrollTop;
}
code.oninput = () => { dirty = true; updateGutter(); };
code.onscroll = () => gutter.scrollTop = code.scrollTop;
code.onkeydown = e => {
  if (e.key === 'Tab') {
    e.preventDefault(); const s = code.selectionStart, en = code.selectionEnd;
    code.setRangeText('    ', s, en, 'end'); dirty = true; updateGutter();
  } else if (e.key === 'Enter') {
    e.preventDefault();
    const s = code.selectionStart, line = code.value.slice(0, s).split('\n').pop();
    const ind = line.match(/^\s*/)[0] + (line.trimEnd().endsWith(':') ? '    ' : '');
    code.setRangeText('\n' + ind, s, code.selectionEnd, 'end'); dirty = true; updateGutter();
  } else if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); saveScript(); }
  else if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); runScript(); }
};
async function loadScripts() {
  const j = await api('/scripts');
  const ul = $('#scrList'); ul.innerHTML = '';
  for (const s of j.items) {
    const li = document.createElement('li');
    li.innerHTML = `<span>${s.name}</span><small>${(s.size / 1024).toFixed(1)} kB</small>`;
    li.classList.toggle('active', s.name === currentScript);
    li.onclick = () => openScript(s.name);
    ul.appendChild(li);
  }
  onScriptEvent(j.runner, true);
}
async function openScript(name) {
  if (dirty && !confirm('Discard unsaved changes?')) return;
  const j = await guard(api('/scripts/' + encodeURIComponent(name)));
  if (!j) return;
  currentScript = j.name; code.value = j.code; dirty = false; updateGutter();
  $('#scrName').value = j.name.replace(/\.py$/, '');
  $$('#scrList li').forEach(li => li.classList.toggle('active', li.firstChild.textContent === j.name));
}
async function saveScript() {
  const name = $('#scrName').value.trim(); if (!name) return toast('Enter a script name');
  const j = await guard(api('/scripts/' + encodeURIComponent(name), 'PUT', { code: code.value }));
  if (!j) return; currentScript = j.name; dirty = false; toast('Saved ' + j.name, true); loadScripts();
}
async function runScript() {
  const name = $('#scrName').value.trim() || 'editor';
  if (dirty || !currentScript) { /* run editor contents without saving */ }
  $('#scrOut').textContent = '';
  await guard(api('/scripts/run', 'POST', { name, code: code.value }));
}
$('#scrSave').onclick = saveScript;
$('#scrRun').onclick = runScript;
$('#scrStop').onclick = () => guard(api('/scripts/stop', 'POST'));
$('#scrClear').onclick = () => $('#scrOut').textContent = '';
$('#scrNew').onclick = () => {
  if (dirty && !confirm('Discard unsaved changes?')) return;
  currentScript = null; dirty = false; $('#scrName').value = 'new';
  code.value = '# New script – the psu object controls the power supply\npsu.set_v(5.0)\npsu.set_i(0.5)\npsu.on()\npsu.wait(2)\nprint("U =", psu.vout, "V  I =", psu.iout, "A")\npsu.off()\n';
  updateGutter(); $$('#scrList li').forEach(li => li.classList.remove('active'));
};
$('#scrDelete').onclick = async () => {
  if (!currentScript || !confirm(`Delete ${currentScript}?`)) return;
  await guard(api('/scripts/' + encodeURIComponent(currentScript), 'DELETE'));
  currentScript = null; code.value = ''; dirty = false; updateGutter(); loadScripts();
};
function appendOut(el, line, cls) {
  const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 8;
  const span = document.createElement('span'); if (cls) span.className = cls;
  span.textContent = line + '\n'; el.appendChild(span);
  while (el.childNodes.length > 1500) el.removeChild(el.firstChild);
  if (atBottom) el.scrollTop = el.scrollHeight;
}
function onScriptEvent(d, initial) {
  if (!d) return;
  const pill = $('#scrStatus'); pill.textContent = d.status + (d.name ? ' · ' + d.name : ''); pill.className = 'pill ' + d.status;
  const running = d.status === 'running';
  $('#scrRun').disabled = running; $('#scrStop').disabled = !running;
  led('ledSCR', running, true);
  ui.scriptRunning = running; $('#scriptLockName').textContent = d.name || ''; applyLocks();
  const isSeq = (d.name || '').startsWith('program:');
  const sp = $('#seqStatus'); sp.textContent = isSeq ? d.status : 'idle'; sp.className = 'pill ' + (isSeq ? d.status : '');
  $('#seqRun').disabled = running; $('#seqStop').disabled = !(running && isSeq);
  if (d.line) {
    appendOut($('#scrOut'), `[${fmtT(d.line.t)}] ${d.line.line}`, d.line.line.startsWith('ERROR') ? 'err' : '');
    if (isSeq) {
      appendOut($('#seqOut'), `[${fmtT(d.line.t)}] ${d.line.line}`, d.line.line.startsWith('ERROR') ? 'err' : '');
      const m = d.line.line.match(/step (\d+):/);
      if (m) $$('#seqTable tbody tr').forEach((tr, k) => tr.classList.toggle('cur', k + 1 === +m[1]));
    }
  }
  if (!running) $$('#seqTable tbody tr').forEach(tr => tr.classList.remove('cur'));
  if (initial && d.output) { $('#scrOut').textContent = ''; d.output.forEach(l => appendOut($('#scrOut'), `[${fmtT(l.t)}] ${l.line}`)); }
}

// ---------------------------------------------------------------- program (sequences)
let currentSeq = null;
function seqRows() {
  return $$('#seqTable tbody tr').map(tr => ({ v: +tr.querySelector('.sv').value, i: +tr.querySelector('.si').value, t: +tr.querySelector('.st').value }));
}
function seqRender(steps) {
  const tb = $('#seqTable tbody'); tb.innerHTML = '';
  steps.forEach((st, k) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${k + 1}</td><td><input class="sv" type="number" step="0.01" min="0" max="30" value="${st.v}"></td>` +
      `<td><input class="si" type="number" step="0.001" min="0" max="5" value="${st.i}"></td>` +
      `<td><input class="st" type="number" step="0.1" min="0" value="${st.t}"></td><td><button class="del" title="remove">✕</button></td>`;
    tr.querySelector('.del').onclick = () => { tr.remove(); seqRenumber(); };
    tb.appendChild(tr);
  });
  seqRenumber();
}
function seqRenumber() {
  const trs = $$('#seqTable tbody tr'); trs.forEach((tr, k) => tr.firstChild.textContent = k + 1);
  $('#seqEnd').max = trs.length; $('#seqStart').max = trs.length;
  if (+$('#seqEnd').value > trs.length || +$('#seqEnd').value < 1) $('#seqEnd').value = trs.length;
}
$('#seqAdd').onclick = () => { const r = seqRows(); const last = r[r.length - 1] || { v: 5, i: 1, t: 2 }; r.push({ ...last }); seqRender(r); $('#seqEnd').value = r.length; };
$('#seqNew').onclick = () => { currentSeq = null; $('#seqName').value = 'test'; seqRender([{ v: 5, i: 1, t: 2 }, { v: 10, i: 1, t: 2 }, { v: 15, i: 1, t: 2 }]); $('#seqStart').value = 1; $('#seqEnd').value = 3; $('#seqCycles').value = 1; };
async function loadSequences() {
  const j = await api('/sequences');
  const ul = $('#seqList'); ul.innerHTML = '';
  for (const n of j.items) {
    const li = document.createElement('li'); li.innerHTML = `<span>${n}</span>`;
    li.classList.toggle('active', n === currentSeq); li.onclick = () => openSequence(n); ul.appendChild(li);
  }
  if (!$('#seqTable tbody').children.length) {
    if (j.items.length) openSequence(j.items[0]); else $('#seqNew').onclick();
  }
}
async function openSequence(name) {
  const j = await guard(api('/sequences/' + encodeURIComponent(name))); if (!j) return;
  currentSeq = j.name; $('#seqName').value = j.name.replace(/\.json$/, '');
  seqRender(j.steps || []); $('#seqStart').value = j.start || 1; $('#seqEnd').value = j.end || (j.steps || []).length; $('#seqCycles').value = j.cycles ?? 1;
  $$('#seqList li').forEach(li => li.classList.toggle('active', li.firstChild.textContent === j.name));
}
function seqPayload() { return { name: $('#seqName').value.trim() || 'test', steps: seqRows(), start: +$('#seqStart').value, end: +$('#seqEnd').value, cycles: +$('#seqCycles').value }; }
$('#seqSave').onclick = async () => {
  const p = seqPayload(); const j = await guard(api('/sequences/' + encodeURIComponent(p.name), 'PUT', p));
  if (j) { currentSeq = j.name; toast('Sequence saved', true); loadSequences(); }
};
$('#seqDelete').onclick = async () => {
  if (!currentSeq || !confirm(`Delete ${currentSeq}?`)) return;
  await guard(api('/sequences/' + encodeURIComponent(currentSeq), 'DELETE')); currentSeq = null; $('#seqTable tbody').innerHTML = ''; loadSequences();
};
$('#seqRun').onclick = async () => {
  if (locked()) return;
  const p = seqPayload(); if (!p.steps.length) return toast('The sequence has no steps');
  if (!confirm(`Start program: steps ${p.start}–${p.end}, cycles ${p.cycles || '∞'}? The output will be switched ON.`)) return;
  $('#seqOut').textContent = '';
  await guard(api('/sequences/run', 'POST', p));
};
$('#seqStop').onclick = () => guard(api('/scripts/stop', 'POST'));
$('#seqClear').onclick = () => $('#seqOut').textContent = '';

// ---------------------------------------------------------------- logs
let currentLog = null;
function onLoggerInfo(info) {
  ui.loggerInfo = info;
  led('ledLOG', info.active);
  const txt = info.active ? `● ${info.name} · ${info.rows} rows · ${info.interval}s` : 'logging inactive';
  $('#logInfo').textContent = txt; $('#qlogInfo').textContent = info.active ? `${info.rows} rows` : '';
  $('#qlogBtn').textContent = info.active ? '■ Stop log' : '● Log';
  $('#qlogBtn').classList.toggle('stop', info.active);
  $('#logStart').disabled = info.active; $('#logStop').disabled = !info.active;
  if (info.rows % 10 === 0 && $('#tab-logs').classList.contains('active')) loadLogs(true);
}
async function loadLogs(quiet) {
  const j = await api('/logs');
  const ul = $('#logList'); ul.innerHTML = '';
  for (const l of j.items) {
    const li = document.createElement('li');
    li.innerHTML = `<span>${l.name}</span><small>${(l.size / 1024).toFixed(1)} kB</small>`;
    li.classList.toggle('rec', l.active); li.classList.toggle('active', l.name === currentLog);
    li.onclick = () => openLog(l.name);
    ul.appendChild(li);
  }
  if (!quiet) onLoggerInfo(j.logger);
  if (currentLog && j.items.some(l => l.name === currentLog && l.active)) openLog(currentLog);
}
async function openLog(name) {
  const j = await guard(api(`/logs/${encodeURIComponent(name)}/data?limit=2000`)); if (!j) return;
  currentLog = name;
  $$('#logList li').forEach(li => li.classList.toggle('active', li.firstChild.textContent === name));
  $('#logTitle').textContent = `${name} · ${j.total} rows`;
  $('#logDl').hidden = false; $('#logDl').href = '/api/logs/' + encodeURIComponent(name); $('#logDel').hidden = false;
  const rows = j.rows.map(r => ({ t: +r.time, v: +r.vout, i: +r.iout, p: +r.power }));
  drawChart($('#logChart'), rows, { showP: true });
  const cols = ['iso', 'elapsed', 'vset', 'iset', 'vout', 'iout', 'power', 'mode', 'output'];
  let h = '<tr>' + cols.map(c => `<th>${c}</th>`).join('') + '</tr>';
  const show = j.rows.slice(-300);
  for (const r of show) h += '<tr>' + cols.map(c => `<td>${c === 'iso' ? r[c].slice(11) : r[c]}</td>`).join('') + '</tr>';
  $('#logTable').innerHTML = h;
}
$('#logStart').onclick = () => guard(api('/logs/start', 'POST', { name: $('#logName').value, interval: +$('#logInt').value || 1 }).then(() => loadLogs()));
$('#logStop').onclick = () => guard(api('/logs/stop', 'POST').then(() => loadLogs()));
$('#logRefresh').onclick = () => loadLogs();
$('#logDel').onclick = async () => {
  if (!currentLog || !confirm(`Delete ${currentLog}?`)) return;
  await guard(api('/logs/' + encodeURIComponent(currentLog), 'DELETE'));
  currentLog = null; $('#logTitle').textContent = ''; $('#logTable').innerHTML = ''; $('#logDl').hidden = true; $('#logDel').hidden = true; loadLogs();
};

// ---------------------------------------------------------------- console
function addCmd(c) { appendOut($('#rawOut'), `[${fmtT(c.t)}] > ${c.cmd}${c.resp ? '   ← ' + JSON.stringify(c.resp) : ''}`); }
function addEvent(e) { appendOut($('#events'), `[${fmtDT(e.t)}] ${e.msg}`, e.kind === 'error' ? 'err' : ''); }
async function loadConsole() {
  const [c, e] = await Promise.all([api('/commands'), api('/events')]);
  $('#rawOut').textContent = ''; c.items.forEach(addCmd);
  $('#events').textContent = ''; e.items.forEach(addEvent);
}
async function sendRaw() {
  const cmd = $('#rawCmd').value.trim(); if (!cmd) return;
  const j = await guard(api('/raw', 'POST', { cmd }));
  if (j && cmd.endsWith('?')) appendOut($('#rawOut'), `   response: ${JSON.stringify(j.resp)}${cmd === 'STATUS?' && j.resp ? ' = 0b' + j.resp.charCodeAt(0).toString(2).padStart(8, '0') : ''}`);
  $('#rawCmd').select();
}
$('#rawSend').onclick = sendRaw;
$('#rawCmd').onkeydown = e => { if (e.key === 'Enter') sendRaw(); };

// ---------------------------------------------------------------- start
(async () => {
  setSeg('segV', '----', 4); setSeg('segI', '----', 4); setSeg('segP', '-OFF', 4);
  updateGutter();
  guard(loadPorts()); guard(loadPresets());
  if (location.hash.length > 1) showTab(location.hash.slice(1));
  // trend history from the server (survives page refresh)
  try {
    const h = await api('/history');
    chart.data = h.samples.map(x => ({ t: x[0], v: x[1], i: x[2], p: x[3] }));
  } catch (_) { }
  try { const j = await api('/state'); applyState(j.state); onScriptEvent(j.script, true); onLoggerInfo(j.logger); } catch (_) { }
  connectStream();
})();
