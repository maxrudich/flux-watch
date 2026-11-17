"""Параметрические монолинейные глифы Flux (порт src/glyph.js, должен совпадать с ним 1:1).

glyph(digit, x, y, w, h, t=4, P=None) -> список полигонов; полигон = (внешнее кольцо, [дыры]).
Все числа в единицах сетки u, y вниз.
"""
import math
import numpy as np

ARC_SEG = 16

def _load_params():
    import os, json
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'glyph_params.json')
    return json.load(open(p))


DEFAULT_P = _load_params()   # tools/glyph_params.json (подгонка: tools/fit_glyphs.py)

# границы значений параметров после вычисления билинейной модели
BOUNDS = {'2_leg': (0.05, 0.6), '2_y1': (0.1, 0.8), '2_y2': (0.3, 0.95), '3_leg': (0.05, 0.6), '3_ym': (0.3, 0.7),
          '3_bar': (0.0, 0.6), '4_yc': (0.1, 0.8), '5_ym': (0.2, 0.7), '5_ys': (0.3, 0.95), '5_leg': (0.05, 0.7),
          '6_yb': (0.2, 0.8), '6_leg': (0.05, 0.7), '7_bx': (0.1, 0.8), '7_tx': (0.6, 2.0), '8_ym': (0.3, 0.7),
          '1_d1': (1.0, 8.0), '1_d2': (3.0, 14.0), '1_d3': (1.0, 8.0), '7_vs': (0.0, 2.0)}
for _k in ('rho0', 'rho2', 'rho3', 'rho4', 'rho5', 'rho6', 'rho8', 'rho'):
    BOUNDS[_k] = (0.3, 3.0)


def resolve(P, w, h):
    """Параметр = число или [c0, c1, c2]: c0 + c1*w + c2*h (оси «ширина/высота» как у variable font)."""
    out = {}
    for k, v in P.items():
        if isinstance(v, (list, tuple)):
            v = v[0] + v[1] * w + v[2] * h
        if k in BOUNDS:
            v = min(max(v, BOUNDS[k][0]), BOUNDS[k][1])
        out[k] = v
    return out


def _unit(dx, dy):
    d = math.hypot(dx, dy)
    return dx / d, dy / d


def rounded_polyline(pts, radii, closed=False):
    """Ломаная со скруглёнными вершинами (дуги, касательные к сегментам), радиус по осевой.
    Возвращает плотную ломаную (список точек) с флагом острых вершин: [(x,y,sharp)]"""
    # убрать совпадающие подряд точки (вырожденные боксы)
    P2, R2 = [pts[0]], [radii[0]]
    for q, rq in zip(pts[1:], radii[1:]):
        if math.hypot(q[0] - P2[-1][0], q[1] - P2[-1][1]) > 1e-9:
            P2.append(q); R2.append(rq)
    if closed and len(P2) > 1 and math.hypot(P2[0][0] - P2[-1][0], P2[0][1] - P2[-1][1]) <= 1e-9:
        P2.pop(); R2.pop()
    pts, radii = P2, R2
    n = len(pts)
    out = []
    if n < 2:
        return [(pts[0][0], pts[0][1], False)] * 2
    if n == 2:
        closed = False
    if not closed:
        out.append((pts[0][0], pts[0][1], False))
    for i in range(n) if closed else range(1, n - 1):
        p = pts[i]
        p0 = pts[(i - 1) % n]
        p1 = pts[(i + 1) % n]
        r = radii[i]
        d0 = _unit(p[0] - p0[0], p[1] - p0[1])
        d1 = _unit(p1[0] - p[0], p1[1] - p[1])
        cross = d0[0] * d1[1] - d0[1] * d1[0]
        dot = d0[0] * d1[0] + d0[1] * d1[1]
        phi = math.atan2(abs(cross), dot)           # угол поворота
        if r <= 1e-9 or phi < 1e-6:
            out.append((p[0], p[1], r <= 1e-9 and phi > 1e-6))
            continue
        tl = r * math.tan(phi / 2)
        l0 = math.hypot(p[0] - p0[0], p[1] - p0[1])
        l1 = math.hypot(p1[0] - p[0], p1[1] - p[1])
        # зажим: касательная не длиннее половины соседних сегментов (для замкнутых и для открытых одинаково)
        lim = min(l0, l1) / 2 if (closed or True) else 1e9
        if not closed:
            lim = min(l0 / (2 if i > 1 else 1), l1 / (2 if i < n - 2 else 1))
        if tl > lim:
            tl = lim
            r = tl / math.tan(phi / 2)
        a = (p[0] - d0[0] * tl, p[1] - d0[1] * tl)
        b = (p[0] + d1[0] * tl, p[1] + d1[1] * tl)
        sgn = 1 if cross > 0 else -1
        nx, ny = -d0[1] * sgn, d0[0] * sgn           # нормаль к центру дуги
        cx, cy = a[0] + nx * r, a[1] + ny * r
        a0 = math.atan2(a[1] - cy, a[0] - cx)
        for k in range(ARC_SEG + 1):
            ang = a0 + sgn * phi * k / ARC_SEG
            out.append((cx + r * math.cos(ang), cy + r * math.sin(ang), False))
    if not closed:
        out.append((pts[-1][0], pts[-1][1], False))
    return out


def ribbon(poly, t, closed=False, cut0=None, cut1=None):
    """Полоса толщиной t вокруг ломаной (miter-стыки). cut0/cut1: None | 'h' | 'v' — срез конца."""
    a = t / 2
    P = [(p[0], p[1]) for p in poly]
    n = len(P)
    # убрать дубли
    Q = [P[0]]
    for p in P[1:]:
        if math.hypot(p[0] - Q[-1][0], p[1] - Q[-1][1]) > 1e-9:
            Q.append(p)
    if closed and math.hypot(Q[0][0] - Q[-1][0], Q[0][1] - Q[-1][1]) < 1e-9:
        Q.pop()
    P = Q
    n = len(P)
    if n < 2:
        return ([], [])
    segs = []
    m = n if closed else n - 1
    for i in range(m):
        d = _unit(P[(i + 1) % n][0] - P[i][0], P[(i + 1) % n][1] - P[i][1])
        segs.append(d)
    L, R = [], []

    def nrm(d):
        return (d[1], -d[0])          # «левая» (в системе y вниз это правая визуально, но нам важна лишь согласованность)

    def join(i, d0, d1):
        n0, n1 = nrm(d0), nrm(d1)
        mx, my = n0[0] + n1[0], n0[1] + n1[1]
        ml = math.hypot(mx, my)
        if ml < 1e-9:
            return n0, 1.0
        mx, my = mx / ml, my / ml
        c = mx * n0[0] + my * n0[1]
        return (mx, my), 1.0 / max(c, 0.2)
    for i in range(n):
        if closed:
            d0, d1 = segs[(i - 1) % n], segs[i]
        else:
            if i == 0:
                d0 = d1 = segs[0]
            elif i == n - 1:
                d0 = d1 = segs[-1]
            else:
                d0, d1 = segs[i - 1], segs[i]
        (mx, my), k = join(i, d0, d1)
        L.append((P[i][0] + mx * a * k, P[i][1] + my * a * k))
        R.append((P[i][0] - mx * a * k, P[i][1] - my * a * k))

    def recut(pL, pR, p, d, cut):
        # пересечь линии смещения (идут вдоль d) с горизонталью/вертикалью через p
        res = []
        for q in (pL, pR):
            if cut == 'h':
                if abs(d[1]) < 1e-9:
                    res.append(q)
                else:
                    s = (p[1] - q[1]) / d[1]
                    res.append((q[0] + d[0] * s, p[1]))
            else:
                if abs(d[0]) < 1e-9:
                    res.append(q)
                else:
                    s = (p[0] - q[0]) / d[0]
                    res.append((p[0], q[1] + d[1] * s))
        return res
    if not closed:
        if cut0:
            L[0], R[0] = recut(L[0], R[0], P[0], segs[0], cut0)
        if cut1:
            L[-1], R[-1] = recut(L[-1], R[-1], P[-1], segs[-1], cut1)
        return (L + R[::-1], [])
    return (L, [R])


def _orient(ring, ccw=True):
    s = 0.0
    for i in range(len(ring)):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % len(ring)]
        s += x0 * y1 - x1 * y0
    if (s > 0) != ccw:
        return ring[::-1]
    return ring


def stroke(pts, radii, t, closed=False, cut0=None, cut1=None):
    poly = rounded_polyline(pts, radii, closed)
    o, holes = ribbon(poly, t, closed, cut0, cut1)
    if not o or (closed and not holes):
        return ([], [])
    # внешнее кольцо — большее по площади
    def area(r):
        return abs(sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r))))
    if closed:
        a, b = o, holes[0]
        if area(a) < area(b):
            a, b = b, a
        return (_orient(a, True), [_orient(b, False)])
    return (_orient(o, True), [])


def glyph(d, x, y, w, h, t=4.0, P=None):
    P = resolve(P or DEFAULT_P, w, h)
    f = GLYPHS[d]
    polys = f(w, h, t, P)
    out = []
    for o, hs in polys:
        out.append(([(px + x, py + y) for px, py in o], [[(px + x, py + y) for px, py in hh] for hh in hs]))
    return out


# ---------------- цифры ----------------
def _rho(t, w, h, P, k='rho'):
    return min(P.get(k, P.get('rho', 0.75)) * t, (w - t) / 2, (h - t) / 2)


def g0(w, h, t, P):
    a = t / 2
    r = _rho(t, w, h, P, 'rho0')
    pts = [(a, a), (w - a, a), (w - a, h - a), (a, h - a)]
    return [stroke(pts, [r] * 4, t, closed=True)]


def g1(w, h, t, P):
    # стойка у правого края + флажок (многоугольник); d1,d2,d3 в u
    sx = w - t
    polys = [([(sx, 0), (w, 0), (w, h), (sx, h)], [])]
    if w >= P.get('flag_min', 1.4) * t:
        d1 = P.get('1_d1', 4.29)
        d2 = P.get('1_d2', 8.65)
        d3 = P.get('1_d3', 4.08)
        k = min(1.0, 0.6 * h / d2)
        d1, d2, d3 = d1 * k, d2 * k, d3 * k
        fl = [(sx, 0), (0, d1), (0, d2), (sx, d3)]
        polys.append((fl, []))
    return [(_orient(p, True), hh) for p, hh in polys]


def g2(w, h, t, P):
    a = t / 2
    r = _rho(t, w, h, P, 'rho2')
    H = h - t
    y1 = a + P.get('2_y1', 0.445) * H           # где правая сторона уходит в диагональ
    y2 = a + P.get('2_y2', 0.648) * H           # где диагональ приходит на левую сторону
    pts = [(a, a + P.get('2_leg', 0.30) * H), (a, a), (w - a, a), (w - a, y1), (a, y2), (a, h - a), (w, h - a)]
    # скругления диагонали «максимальные» (зажимаются длиной соседних сегментов), основание — острый угол
    rr = [0, r, r, 100.0, 100.0, 0, 0]
    return [stroke(pts, rr, t, cut1='v')]


def g3(w, h, t, P):
    a = t / 2
    r = _rho(t, w, h, P, 'rho3')
    H = h - t
    ym = a + P.get('3_ym', 0.5) * H
    leg = P.get('3_leg', 0.18) * H
    bar = P.get('3_bar', 0.25) * (w - t)
    top = [(a, a + leg), (a, a), (w - a, a), (w - a, ym), (a + bar, ym)]
    bot = [(a, h - a - leg), (a, h - a), (w - a, h - a), (w - a, ym), (a + bar, ym)]
    rt = [0, r, r, r, 0]
    return [stroke(top, rt, t, cut1='v'), stroke(bot, rt, t, cut1='v')]


def g4(w, h, t, P):
    a = t / 2
    r = _rho(t, w, h, P, 'rho4')
    H = h - t
    yc = a + P.get('4_yc', 0.62) * H
    left = [(a, 0), (a, yc), (w - a, yc)]
    right = [(w - a, 0), (w - a, h)]
    return [stroke(left, [0, r, 0], t), stroke(right, [0, 0], t)]


def g5(w, h, t, P):
    a = t / 2
    r = _rho(t, w, h, P, 'rho5')
    H = h - t
    ym = a + P.get('5_ym', 0.42) * H          # ось перекладины чаши
    ys = P.get('5_ys', 0.62) * h              # низ левой стойки (срез)
    yl = h - P.get('5_leg', 0.34) * h         # верх нижней ножки (срез)
    top = [(w, a), (a, a), (a, ys)]
    bowl = [(t, ym), (w - a, ym), (w - a, h - a), (a, h - a), (a, yl)]
    return [stroke(top, [0, 0, 0], t), stroke(bowl, [0, r, r, r, 0], t)]


def g6(w, h, t, P):
    a = t / 2
    r = _rho(t, w, h, P, 'rho6')
    H = h - t
    yb = a + P.get('6_yb', 0.42) * H            # ось перекладины чаши
    leg = P.get('6_leg', 0.28) * H
    pts = [(w - a, a + leg), (w - a, a), (a, a), (a, h - a), (w - a, h - a), (w - a, yb), (t, yb)]
    rr = [0, r, r, r, r, r, 0]
    return [stroke(pts, rr, t)]


def g7(w, h, t, P):
    # верхняя планка + (короткая вертикаль) + прямая диагональ с горизонтальным срезом внизу
    vs = P.get('7_vs', 0.0) * t
    bx = P.get('7_bx', 0.375)              # центр низа диагонали (доля w)
    tx = P.get('7_tx', 1.15) * t           # горизонтальная толщина диагонали
    polys = [(_orient([(0, 0), (w, 0), (w, t), (0, t)], True), [])]
    xb = bx * w
    pts = [(w - tx, t), (w, t), (w, t + vs), (xb + tx / 2, h), (xb - tx / 2, h)]
    polys.append((_orient(pts, True), []))
    return polys


def g8(w, h, t, P):
    a = t / 2
    r = _rho(t, w, h, P, 'rho8')
    H = h - t
    ym = a + P.get('8_ym', 0.45) * H
    topr = [(a, a), (w - a, a), (w - a, ym), (a, ym)]
    bot = [(a, ym), (w - a, ym), (w - a, h - a), (a, h - a)]
    return [stroke(topr, [r] * 4, t, closed=True), stroke(bot, [r] * 4, t, closed=True)]


def g9(w, h, t, P):
    polys = g6(w, h, t, P)
    out = []
    for o, hs in polys:
        out.append(([(w - px, h - py) for px, py in o][::-1], [[(w - px, h - py) for px, py in hh][::-1] for hh in hs]))
    return out


GLYPHS = {0: g0, 1: g1, 2: g2, 3: g3, 4: g4, 5: g5, 6: g6, 7: g7, 8: g8, 9: g9}


def rasterize(polys, W, H, ss=4, scale=1.0, ox=0.0, oy=0.0):
    """Покрытие 0..1 (H×W) для списка полигонов (в u); scale = px/u; ox, oy — смещение в px.
    Каждый полигон растеризуется отдельно (внешнее кольцо минус дыры), слои объединяются через max."""
    from PIL import Image, ImageDraw
    acc = np.zeros((H * ss, W * ss), dtype=np.uint8)
    for o, hs in polys:
        big = Image.new('L', (W * ss, H * ss), 0)
        dr = ImageDraw.Draw(big)
        dr.polygon([((px * scale + ox) * ss, (py * scale + oy) * ss) for px, py in o], fill=255)
        for hh in hs:
            dr.polygon([((px * scale + ox) * ss, (py * scale + oy) * ss) for px, py in hh], fill=0)
        acc = np.maximum(acc, np.asarray(big))
    return np.asarray(Image.fromarray(acc).resize((W, H), Image.BOX), dtype=np.float32) / 255.0
