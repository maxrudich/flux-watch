// Устойчивость глифов: ни одного NaN/Infinity на сетке размеров (вырожденные боксы тоже)
await import(new URL('../src/glyph.js', import.meta.url).pathname);
let bad = [], n = 0;
for (let d = 0; d <= 9; d++) for (let w = 0.5; w <= 60; w += 0.5) for (let h = 0.5; h <= 60; h += 0.5) {
  n++;
  const s = FluxGlyph.glyphPath(d, 3, 4, w, h, 4);
  if (/NaN|Infinity/.test(s)) bad.push(`d${d} ${w}x${h}`);
}
console.log('проверено', n, 'комбинаций; NaN в', bad.length, bad.slice(0, 12));
process.exit(bad.length ? 1 : 0);
