// Проверка всех 1440 раскладок по реальным чернилам глифов (боксы Apple перекрываются легально: флажок «1» пуст).
// Для каждой минуты: глифы целиком внутри поля контента и своего бокса, нет NaN, минимальный зазор между
// чернилами разных слотов >= GAP u. Растр 0.2u. Запуск: node tools/check_layouts.mjs [--gap=1.5] [--json] ; код выхода 1 при проблемах.
// Модуль экспортирует inkGap/rasterize для проверки морфа (tools/check_morph.mjs).
globalThis.window = globalThis;
await import(new URL('../data/layouts.js', import.meta.url).pathname);
await import(new URL('../src/glyph.js', import.meta.url).pathname);
export const CX0 = 5.2, CX1 = 45.08, CY0 = 5, CY1 = 55, RES = 5;   // RES клеток на u
const W = Math.ceil(52 * RES), H = Math.ceil(62 * RES);
const NAMES = ['H1', 'H2', 'M1', 'M2'];
export function rasterize(polys) {            // polys: [{o:[[x,y]..], h:[[[x,y]..]..]}] -> Uint8Array (nonzero fill)
  const m = new Uint8Array(W * H), rings = [];
  polys.forEach(p => { rings.push(p.o); p.h.forEach(r => rings.push(r)); });
  for (let row = 0; row < H; row++) {
    const y = (row + 0.5) / RES, xs = [];
    for (const r of rings) for (let i = 0; i < r.length; i++) {
      const a = r[i], b = r[(i + 1) % r.length];
      if ((a[1] <= y) !== (b[1] <= y)) xs.push([a[0] + (y - a[1]) / (b[1] - a[1]) * (b[0] - a[0]), b[1] > a[1] ? 1 : -1]);
    }
    xs.sort((p, q) => p[0] - q[0]);
    let wn = 0;
    for (let i = 0; i < xs.length - 1; i++) {
      wn += xs[i][1];
      if (wn !== 0) { const c0 = Math.max(0, Math.round(xs[i][0] * RES)), c1 = Math.min(W, Math.round(xs[i + 1][0] * RES)); for (let c = c0; c < c1; c++) m[row * W + c] = 1; }
    }
  }
  return m;
}
function boundary(m) {
  const out = [];
  for (let r = 1; r < H - 1; r++) for (let c = 1; c < W - 1; c++) { const i = r * W + c; if (m[i] && (!m[i - 1] || !m[i + 1] || !m[i - W] || !m[i + W])) out.push(i); }
  return out;
}
export function inkGap(ma, mb) {              // минимальное евклидово расстояние между чернилами в u (0 = пересекаются)
  const ba = boundary(ma), bb = boundary(mb);
  for (let i = 0; i < ma.length; i++) if (ma[i] && mb[i]) return 0;
  let best = 1e9;
  for (const i of ba) { const r1 = (i / W) | 0, c1 = i % W; for (const j of bb) { const d = (r1 - ((j / W) | 0)) ** 2 + (c1 - j % W) ** 2; if (d < best) best = d; } }
  return Math.sqrt(best) / RES;
}
export function erode(m, n) {              // эрозия крестом на n клеток (n/RES u)
  let a = m;
  for (let k = 0; k < n; k++) { const b = new Uint8Array(a.length); for (let r = 1; r < H - 1; r++) for (let c = 1; c < W - 1; c++) { const i = r * W + c; if (a[i] && a[i - 1] && a[i + 1] && a[i - W] && a[i + W]) b[i] = 1; } a = b; }
  return a;
}
export function penetration(ma, mb, maxU = 1.0) {   // true, если чернила взаимно врезаются глубже maxU
  const ea = erode(ma, Math.round(maxU * RES)); for (let i = 0; i < ea.length; i++) if (ea[i] && mb[i]) return true; return false;
}
export function masksFor(boxes, digits, P) { return boxes.map((b, i) => rasterize(FluxGlyph.glyph(digits[i], b[0], b[1], b[2], b[3], 4, Object.assign({}, FluxGlyph.DEFAULT_P, P[i] || {})))); }
export function bounds(polys) {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  polys.forEach(p => p.o.forEach(q => { x0 = Math.min(x0, q[0]); x1 = Math.max(x1, q[0]); y0 = Math.min(y0, q[1]); y1 = Math.max(y1, q[1]); }));
  return [x0, y0, x1, y1];
}
export function digitsFor(i) { const h = Math.floor(i / 60), m = i % 60; return m === 0 ? String(h).split('').map(Number) : (String(h).padStart(2, '0') + String(m).padStart(2, '0')).split('').map(Number); }
export const mt = i => String(Math.floor(i / 60)).padStart(2, '0') + ':' + String(i % 60).padStart(2, '0');
export function check(boxes, digits, P, GAP, names) {   // -> массив строк-проблем
  const issues = [], polys = [], masks = [], EPS = 0.05;
  boxes.forEach((b, i) => {
    const [x, y, w, h] = b, nm = (names || NAMES)[i];
    if (![x, y, w, h].every(Number.isFinite) || w <= 0 || h <= 0) { issues.push(nm + ' битый бокс'); polys.push([]); masks.push(null); return; }
    const g = FluxGlyph.glyph(digits[i], x, y, w, h, 4, Object.assign({}, FluxGlyph.DEFAULT_P, P[i] || {}));
    if (g.some(p => p.o.concat(...p.h).some(q => !Number.isFinite(q[0]) || !Number.isFinite(q[1])))) issues.push(nm + ' NaN');
    const [a0, b0, a1, b1] = bounds(g);
    if (a0 < x - EPS || a1 > x + w + EPS || b0 < y - EPS || b1 > y + h + EPS) issues.push(`${nm} глиф вне бокса`);
    if (a0 < CX0 - EPS || a1 > CX1 + EPS || b0 < CY0 - EPS || b1 > CY1 + EPS) issues.push(`${nm} вне поля контента`);
    polys.push(g); masks.push(rasterize(g));
  });
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    if (!masks[i] || !masks[j]) continue;
    const g = inkGap(masks[i], masks[j]);
    if (g < GAP) issues.push(`${(names || NAMES)[i]}/${(names || NAMES)[j]} зазор ${g.toFixed(2)}u`);
  }
  return issues;
}
if (import.meta.url === 'file://' + process.argv[1]) {
  const GAP = +((process.argv.find(a => a.startsWith('--gap=')) || '--gap=1.5').slice(6));
  const L = window.FLUX_LAYOUTS, bad = [], known = [];
  // минуты, где эталон Apple сам касается соседей («11»: флажок второй «1» врастает в стойку первой): tools/ink_contact_exceptions.json
  const fs = await import('node:fs'); let EXC = {};
  try { EXC = JSON.parse(fs.readFileSync(new URL('./ink_contact_exceptions.json', import.meta.url))); } catch (e) {}
  for (let i = 0; i < 1440; i++) {
    const d = digitsFor(i), lay = L[i];
    if (lay.length !== d.length) { bad.push(mt(i) + ': слотов ' + lay.length + ', цифр ' + d.length); continue; }
    const names = d.length === 4 ? NAMES : d.length === 2 ? ['H1', 'H2'] : ['H2'];
    const iss = check(lay.map(e => e.slice(0, 4)), d, lay.map(e => e[4] || null), GAP, names);
    const real = iss.filter(t => !(EXC[mt(i)] && / зазор /.test(t)));
    if (real.length) bad.push(mt(i) + ': ' + real.join('; '));
    else if (iss.length) known.push(mt(i) + ': ' + iss.join('; '));
  }
  console.log('минут проверено: 1440, зазор >= ' + GAP + 'u; проблемных:', bad.length, '; известных касаний как у эталона:', known.length);
  bad.forEach(s => console.log(' ', s));
  if (process.argv.includes('--known')) known.forEach(s => console.log('  (эталон)', s));
  process.exit(bad.length ? 1 : 0);
}
