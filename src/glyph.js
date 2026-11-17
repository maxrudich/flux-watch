/* Flux: параметрические монолинейные глифы 0–9 (без шрифтов).
 * Порт tools/fluxglyph.py — геометрия должна совпадать 1:1 (tools/check_glyph_port.mjs сравнивает).
 * glyph(digit, x, y, w, h, t, P) -> [{o:[[x,y]..], h:[[[x,y]..]..]}]  (единицы любые, y вниз)
 * glyphPath(...) -> строка d для <path> (fill-rule nonzero: внешние кольца и дыры имеют противоположный обход).
 */
(function (root) {
  'use strict';
  var ARC_SEG = 16;
  /*P:begin*/var DEFAULT_P = {"1_d1":4.294,"1_d2":8.6481,"1_d3":4.0793,"2_leg":0.3034,"2_y1":0.445,"2_y2":0.6478,"3_bar":0.2022,"3_leg":0.3476,"3_ym":0.4997,"4_yc":[0.33385,0.0,0.0],"5_leg":0.2917,"5_ym":0.4179,"5_ys":0.7095,"6_leg":0.272,"6_yb":0.4803,"7_bx":0.375,"7_tx":1.1518,"7_vs":0.0,"8_ym":0.45,"rho0":0.8316,"rho2":0.8125,"rho3":0.8129,"rho4":[0.3875,0.0275,-0.0125],"rho5":0.5593,"rho6":0.7751,"rho8":0.8129};/*P:end*/

  var BOUNDS = {'2_leg':[0.05,0.6],'2_y1':[0.1,0.8],'2_y2':[0.3,0.95],'3_leg':[0.05,0.6],'3_ym':[0.3,0.7],'3_bar':[0,0.6],
    '4_yc':[0.1,0.8],'5_ym':[0.2,0.7],'5_ys':[0.3,0.95],'5_leg':[0.05,0.7],'6_yb':[0.2,0.8],'6_leg':[0.05,0.7],
    '7_bx':[0.1,0.8],'7_tx':[0.6,2.0],'8_ym':[0.3,0.7],'1_d1':[1,8],'1_d2':[3,14],'1_d3':[1,8],'7_vs':[0,2],
    rho0:[0.3,3],rho2:[0.3,3],rho3:[0.3,3],rho4:[0.3,3],rho5:[0.3,3],rho6:[0.3,3],rho8:[0.3,3],rho:[0.3,3]};
  /* параметр = число или [c0,c1,c2]: c0 + c1*w + c2*h (оси «ширина/высота»), затем зажим в BOUNDS */
  function resolve(P, w, h) {
    var out = {}, k, v;
    for (k in P) {
      v = P[k];
      if (Array.isArray(v)) v = v[0] + v[1] * w + v[2] * h;
      if (BOUNDS[k]) v = Math.min(Math.max(v, BOUNDS[k][0]), BOUNDS[k][1]);
      out[k] = v;
    }
    return out;
  }

  function unit(dx, dy) { var d = Math.hypot(dx, dy); return [dx / d, dy / d]; }

  function roundedPolyline(pts, radii, closed) {
    var P2 = [pts[0]], R2 = [radii[0]], z;
    for (z = 1; z < pts.length; z++) {
      var qq = P2[P2.length - 1];
      if (Math.hypot(pts[z][0] - qq[0], pts[z][1] - qq[1]) > 1e-9) { P2.push(pts[z]); R2.push(radii[z]); }
    }
    if (closed && P2.length > 1 && Math.hypot(P2[0][0] - P2[P2.length - 1][0], P2[0][1] - P2[P2.length - 1][1]) <= 1e-9) { P2.pop(); R2.pop(); }
    pts = P2; radii = R2;
    var n = pts.length, out = [], i;
    if (n < 2) return [[pts[0][0], pts[0][1]], [pts[0][0], pts[0][1]]];
    if (n === 2) closed = false;
    if (!closed) out.push([pts[0][0], pts[0][1]]);
    var lo = closed ? 0 : 1, hi = closed ? n : n - 1;
    for (i = lo; i < hi; i++) {
      var p = pts[i], p0 = pts[(i - 1 + n) % n], p1 = pts[(i + 1) % n], r = radii[i];
      var d0 = unit(p[0] - p0[0], p[1] - p0[1]), d1 = unit(p1[0] - p[0], p1[1] - p[1]);
      var cross = d0[0] * d1[1] - d0[1] * d1[0], dot = d0[0] * d1[0] + d0[1] * d1[1];
      var phi = Math.atan2(Math.abs(cross), dot);
      if (r <= 1e-9 || phi < 1e-6) { out.push([p[0], p[1]]); continue; }
      var tl = r * Math.tan(phi / 2);
      var l0 = Math.hypot(p[0] - p0[0], p[1] - p0[1]), l1 = Math.hypot(p1[0] - p[0], p1[1] - p[1]);
      var lim;
      if (closed) lim = Math.min(l0, l1) / 2;
      else lim = Math.min(l0 / (i > 1 ? 2 : 1), l1 / (i < n - 2 ? 2 : 1));
      if (tl > lim) { tl = lim; r = tl / Math.tan(phi / 2); }
      var a = [p[0] - d0[0] * tl, p[1] - d0[1] * tl];
      var sgn = cross > 0 ? 1 : -1;
      var nx = -d0[1] * sgn, ny = d0[0] * sgn;
      var cx = a[0] + nx * r, cy = a[1] + ny * r;
      var a0 = Math.atan2(a[1] - cy, a[0] - cx);
      for (var k = 0; k <= ARC_SEG; k++) {
        var ang = a0 + sgn * phi * k / ARC_SEG;
        out.push([cx + r * Math.cos(ang), cy + r * Math.sin(ang)]);
      }
    }
    if (!closed) out.push([pts[n - 1][0], pts[n - 1][1]]);
    return out;
  }

  function ribbon(poly, t, closed, cut0, cut1) {
    var a = t / 2, P = [poly[0]], i, n;
    for (i = 1; i < poly.length; i++) {
      var q = P[P.length - 1];
      if (Math.hypot(poly[i][0] - q[0], poly[i][1] - q[1]) > 1e-9) P.push(poly[i]);
    }
    if (closed && Math.hypot(P[0][0] - P[P.length - 1][0], P[0][1] - P[P.length - 1][1]) < 1e-9) P.pop();
    n = P.length;
    if (n < 2) return [[], []];
    var segs = [], m = closed ? n : n - 1;
    for (i = 0; i < m; i++) segs.push(unit(P[(i + 1) % n][0] - P[i][0], P[(i + 1) % n][1] - P[i][1]));
    var L = [], R = [];
    function nrm(d) { return [d[1], -d[0]]; }
    function join(d0, d1) {
      var n0 = nrm(d0), n1 = nrm(d1), mx = n0[0] + n1[0], my = n0[1] + n1[1], ml = Math.hypot(mx, my);
      if (ml < 1e-9) return [n0, 1];
      mx /= ml; my /= ml;
      var c = mx * n0[0] + my * n0[1];
      return [[mx, my], 1 / Math.max(c, 0.2)];
    }
    for (i = 0; i < n; i++) {
      var d0, d1;
      if (closed) { d0 = segs[(i - 1 + n) % n]; d1 = segs[i]; }
      else if (i === 0) { d0 = d1 = segs[0]; }
      else if (i === n - 1) { d0 = d1 = segs[segs.length - 1]; }
      else { d0 = segs[i - 1]; d1 = segs[i]; }
      var j = join(d0, d1), mm = j[0], k = j[1];
      L.push([P[i][0] + mm[0] * a * k, P[i][1] + mm[1] * a * k]);
      R.push([P[i][0] - mm[0] * a * k, P[i][1] - mm[1] * a * k]);
    }
    function recut(pL, pR, p, d, cut) {
      var res = [], qs = [pL, pR];
      for (var z = 0; z < 2; z++) {
        var q = qs[z];
        if (cut === 'h') {
          if (Math.abs(d[1]) < 1e-9) res.push(q);
          else { var s = (p[1] - q[1]) / d[1]; res.push([q[0] + d[0] * s, p[1]]); }
        } else {
          if (Math.abs(d[0]) < 1e-9) res.push(q);
          else { var s2 = (p[0] - q[0]) / d[0]; res.push([p[0], q[1] + d[1] * s2]); }
        }
      }
      return res;
    }
    if (!closed) {
      var r0;
      if (cut0) { r0 = recut(L[0], R[0], P[0], segs[0], cut0); L[0] = r0[0]; R[0] = r0[1]; }
      if (cut1) { r0 = recut(L[n - 1], R[n - 1], P[n - 1], segs[segs.length - 1], cut1); L[n - 1] = r0[0]; R[n - 1] = r0[1]; }
      return [L.concat(R.slice().reverse()), []];
    }
    return [L, [R]];
  }

  function area(r) {
    var s = 0;
    for (var i = 0; i < r.length; i++) { var q = r[(i + 1) % r.length]; s += r[i][0] * q[1] - q[0] * r[i][1]; }
    return s;
  }
  function orient(ring, ccw) {
    var s = area(ring);
    if ((s > 0) !== ccw) return ring.slice().reverse();
    return ring;
  }

  function stroke(pts, radii, t, closed, cut0, cut1) {
    var poly = roundedPolyline(pts, radii, !!closed);
    var rb = ribbon(poly, t, !!closed, cut0, cut1), o = rb[0], hs = rb[1];
    if (!o.length || (closed && !hs.length)) return [[], []];
    if (closed) {
      var a = o, b = hs[0];
      if (Math.abs(area(a)) < Math.abs(area(b))) { var tmp = a; a = b; b = tmp; }
      return [orient(a, true), [orient(b, false)]];
    }
    return [orient(o, true), []];
  }

  function rho(t, w, h, P, k) {
    var v = (P[k] !== undefined) ? P[k] : 0.75;
    return Math.min(v * t, (w - t) / 2, (h - t) / 2);
  }
  function pv(P, k, d) { return P[k] !== undefined ? P[k] : d; }

  var GLYPHS = {
    0: function (w, h, t, P) {
      var a = t / 2, r = rho(t, w, h, P, 'rho0');
      return [stroke([[a, a], [w - a, a], [w - a, h - a], [a, h - a]], [r, r, r, r], t, true)];
    },
    1: function (w, h, t, P) {
      var sx = w - t, out = [[orient([[sx, 0], [w, 0], [w, h], [sx, h]], true), []]];
      if (w >= pv(P, 'flag_min', 1.4) * t) {
        var d1 = pv(P, '1_d1', 4.29), d2 = pv(P, '1_d2', 8.65), d3 = pv(P, '1_d3', 4.08);
        var kk = Math.min(1, 0.6 * h / d2); d1 *= kk; d2 *= kk; d3 *= kk;
        out.push([orient([[sx, 0], [0, d1], [0, d2], [sx, d3]], true), []]);
      }
      return out;
    },
    2: function (w, h, t, P) {
      var a = t / 2, r = rho(t, w, h, P, 'rho2'), H = h - t;
      var y1 = a + pv(P, '2_y1', 0.445) * H, y2 = a + pv(P, '2_y2', 0.648) * H;
      var pts = [[a, a + pv(P, '2_leg', 0.30) * H], [a, a], [w - a, a], [w - a, y1], [a, y2], [a, h - a], [w, h - a]];
      return [stroke(pts, [0, r, r, 100, 100, 0, 0], t, false, null, 'v')];
    },
    3: function (w, h, t, P) {
      var a = t / 2, r = rho(t, w, h, P, 'rho3'), H = h - t;
      var ym = a + pv(P, '3_ym', 0.5) * H, leg = pv(P, '3_leg', 0.18) * H, bar = pv(P, '3_bar', 0.25) * (w - t);
      var top = [[a, a + leg], [a, a], [w - a, a], [w - a, ym], [a + bar, ym]];
      var bot = [[a, h - a - leg], [a, h - a], [w - a, h - a], [w - a, ym], [a + bar, ym]];
      var rt = [0, r, r, r, 0];
      return [stroke(top, rt, t, false, null, 'v'), stroke(bot, rt, t, false, null, 'v')];
    },
    4: function (w, h, t, P) {
      var a = t / 2, r = rho(t, w, h, P, 'rho4'), H = h - t;
      var yc = a + pv(P, '4_yc', 0.62) * H;
      return [stroke([[a, 0], [a, yc], [w - a, yc]], [0, r, 0], t), stroke([[w - a, 0], [w - a, h]], [0, 0], t)];
    },
    5: function (w, h, t, P) {
      var a = t / 2, r = rho(t, w, h, P, 'rho5'), H = h - t;
      var ym = a + pv(P, '5_ym', 0.42) * H, ys = pv(P, '5_ys', 0.62) * h, yl = h - pv(P, '5_leg', 0.34) * h;
      return [stroke([[w, a], [a, a], [a, ys]], [0, 0, 0], t),
              stroke([[t, ym], [w - a, ym], [w - a, h - a], [a, h - a], [a, yl]], [0, r, r, r, 0], t)];
    },
    6: function (w, h, t, P) {
      var a = t / 2, r = rho(t, w, h, P, 'rho6'), H = h - t;
      var yb = a + pv(P, '6_yb', 0.42) * H, leg = pv(P, '6_leg', 0.28) * H;
      return [stroke([[w - a, a + leg], [w - a, a], [a, a], [a, h - a], [w - a, h - a], [w - a, yb], [t, yb]],
                     [0, r, r, r, r, r, 0], t)];
    },
    7: function (w, h, t, P) {
      var vs = pv(P, '7_vs', 0) * t, bx = pv(P, '7_bx', 0.375), tx = pv(P, '7_tx', 1.15) * t, xb = bx * w;
      return [[orient([[0, 0], [w, 0], [w, t], [0, t]], true), []],
              [orient([[w - tx, t], [w, t], [w, t + vs], [xb + tx / 2, h], [xb - tx / 2, h]], true), []]];
    },
    8: function (w, h, t, P) {
      var a = t / 2, r = rho(t, w, h, P, 'rho8'), H = h - t, ym = a + pv(P, '8_ym', 0.45) * H;
      return [stroke([[a, a], [w - a, a], [w - a, ym], [a, ym]], [r, r, r, r], t, true),
              stroke([[a, ym], [w - a, ym], [w - a, h - a], [a, h - a]], [r, r, r, r], t, true)];
    },
    9: function (w, h, t, P) {
      var src = GLYPHS[6](w, h, t, P), out = [];
      src.forEach(function (pg) {
        out.push([pg[0].map(function (q) { return [w - q[0], h - q[1]]; }).reverse(),
                  pg[1].map(function (hh) { return hh.map(function (q) { return [w - q[0], h - q[1]]; }).reverse(); })]);
      });
      return out;
    }
  };

  function glyph(d, x, y, w, h, t, P) {
    P = resolve(P || DEFAULT_P, w, h); t = t === undefined ? 4 : t;
    var polys = GLYPHS[d](w, h, t, P), out = [];
    polys.forEach(function (pg) {
      out.push({ o: pg[0].map(function (q) { return [q[0] + x, q[1] + y]; }),
                 h: pg[1].map(function (hh) { return hh.map(function (q) { return [q[0] + x, q[1] + y]; }); }) });
    });
    return out;
  }

  function fmt(v) { return (Math.round(v * 1000) / 1000).toString(); }
  function ringPath(r, sx, sy, ox, oy) {
    var s = '';
    if (r.length < 3) return '';
    for (var i = 0; i < r.length; i++) s += (i ? 'L' : 'M') + fmt(r[i][0] * sx + ox) + ' ' + fmt(r[i][1] * sy + oy);
    return s + 'Z';
  }
  /* d для <path>; (sx,sy,ox,oy) — необязательное аффинное отображение единиц в пиксели (только перенос/масштаб точек) */
  function glyphPath(d, x, y, w, h, t, P, sx, sy, ox, oy) {
    sx = sx || 1; sy = sy || 1; ox = ox || 0; oy = oy || 0;
    var s = '';
    glyph(d, x, y, w, h, t, P).forEach(function (pg) {
      s += ringPath(pg.o, sx, sy, ox, oy);
      pg.h.forEach(function (hh) { s += ringPath(hh, sx, sy, ox, oy); });
    });
    return s;
  }

  root.FluxGlyph = { glyph: glyph, glyphPath: glyphPath, DEFAULT_P: DEFAULT_P };
})(typeof window !== 'undefined' ? window : globalThis);
