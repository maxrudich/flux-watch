// Сверка JS-глифов с Python-глифами: выводит максимальное расхождение координат по набору боксов
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
await import(root + '/src/glyph.js');
const boxes = [[0,0,8,20],[3,2,16.4,30],[1,1,24,18],[0,0,6,12],[0,0,21.5,24],[0,0,13,30.2],[0,0,40,50],[5,5,9,9]];
const py = JSON.parse(execFileSync(root + '/.venv/bin/python', ['-I', '-c', `
import sys, json
sys.path.insert(0, '${root}/tools')
import fluxglyph as fg
boxes = ${JSON.stringify(boxes)}
out = {}
for d in range(10):
    out[d] = [[ [ [list(p) for p in o], [[list(p) for p in h] for h in hs] ] for o, hs in fg.glyph(d, *b)] for b in boxes]
print(json.dumps(out))
`]).toString());
let worst = 0, bad = [];
for (let d = 0; d < 10; d++) boxes.forEach((b, bi) => {
  const js = FluxGlyph.glyph(d, b[0], b[1], b[2], b[3], 4);
  const pp = py[d][bi];
  if (js.length !== pp.length) { bad.push(`d${d} box${bi}: polys ${js.length} vs ${pp.length}`); return; }
  js.forEach((pg, i) => {
    const [po, ph] = pp[i];
    if (pg.o.length !== po.length) { bad.push(`d${d} box${bi}: ring len ${pg.o.length} vs ${po.length}`); return; }
    pg.o.forEach((q, k) => { worst = Math.max(worst, Math.abs(q[0]-po[k][0]), Math.abs(q[1]-po[k][1])); });
    pg.h.forEach((hh, hi) => hh.forEach((q, k) => { worst = Math.max(worst, Math.abs(q[0]-ph[hi][k][0]), Math.abs(q[1]-ph[hi][k][1])); }));
  });
});
console.log('max |JS-Python| =', worst.toExponential(2), bad.length ? bad : 'структура совпала');
process.exit(worst < 1e-6 && !bad.length ? 0 : 1);
