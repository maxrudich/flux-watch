// Проверка пружинной смены минуты: для всех 1440 переходов на пике перелёта и в середине пути
// глифы не вырождаются (NaN, w/h <= 0) и соседи не слипаются глубже PEN u.
// Пружина берётся те же параметры, что в index.html. Запуск: node tools/check_morph.mjs
import { check, digitsFor, mt, masksFor, penetration } from './check_layouts.mjs';
const Z = 0.66, RESP = 0.60, wn = 2 * Math.PI / RESP, wd = wn * Math.sqrt(1 - Z * Z), A = Z * wn;
const spring = t => 1 - Math.exp(-A * t) * (Math.cos(wd * t) + A / wd * Math.sin(wd * t));
const tPeak = Math.PI / wd, pPeak = spring(tPeak);
console.log('перелёт на пике: ' + ((pPeak - 1) * 100).toFixed(1) + '% на ' + (tPeak * 1000 | 0) + ' мс; p>0.999 после ' + (() => { let t = 0; for (; t < 3; t += 0.001) { let ok = true; for (let u = t; u < t + 0.5; u += 0.01) if (Math.abs(spring(u) - 1) > 0.001) { ok = false; break; } if (ok) break; } return (t * 1000 | 0); })() + ' мс');
const L = window.FLUX_LAYOUTS, SL = ['H1', 'H2', 'M1', 'M2'];
function slots(i) { const d = digitsFor(i), lay = L[i], names = d.length === 4 ? SL : d.length === 2 ? ['H1', 'H2'] : ['H2'], o = {}; names.forEach((n, k) => o[n] = { d: d[k], b: lay[k].slice(0, 4), p: lay[k][4] || null }); return o; }
const lerp = (a, b, p) => a.map((v, i) => v + (b[i] - v) * p);
const bad = [], known = []; let worst = 0;
const fs = await import('node:fs'); let EXC = {};
try { EXC = JSON.parse(fs.readFileSync(new URL('./ink_contact_exceptions.json', import.meta.url))); } catch (e) {}
for (let k = 0; k < 1440; k++) {
  const A_ = slots((k + 1439) % 1440), B_ = slots(k), nm = SL;
  for (const [label, p] of [['пик', pPeak], ['0.5', 0.5]]) {
    const boxes = [], dig = [], P = [], names = [];
    SL.forEach(n => { const a = A_[n], b = B_[n]; if (a && b) { boxes.push(lerp(a.b, b.b, p)); dig.push(p >= 0.5 ? b.d : a.d); P.push(p >= 0.5 ? b.p : a.p); names.push(n); } });
    // слоты, которые появляются/исчезают, в проверку зазоров не входят (они сжимаются к центру бокса)
    const iss = check(boxes, dig, P, -1e9, names).filter(s => !/вне поля контента/.test(s));
    const ms = masksFor(boxes, dig, P);   // слипание глубже 1u (эрозия одного глифа на 1u всё ещё пересекает соседа)
    if (label === 'пик') for (let i = 0; i < ms.length; i++) for (let j = i + 1; j < ms.length; j++) if (penetration(ms[i], ms[j], 1.0)) iss.push(names[i] + '/' + names[j] + ' врезаются > 1u');
    if (iss.length) (EXC[mt(k)] && iss.every(t => /врезаются/.test(t)) ? known : bad).push(mt(k) + ' ' + label + ': ' + iss.join('; '));   // слипание в минутах, где эталон сам касается соседей, на перелёте чуть глубже
  }
}
console.log('переходов: 1440; проблем: ' + bad.length + '; перелёт углубляет известное касание эталона: ' + known.length + ' минут'); bad.forEach(s => console.log(' ', s));
process.exit(bad.length ? 1 : 0);
