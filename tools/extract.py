#!/usr/bin/env python3
"""Извлечение 1440 раскладок Flux из reference/tdc_3_all_1440_grid.jpg (ТЗ §4).

Запуск:  .venv/bin/python -I tools/extract.py [--only HH:MM ...] [--jobs N]
Выход:   data/layouts.js (window.FLUX_LAYOUTS), tools/extract_report.json

Пайплайн: проекции → решётка 24×60 → субпиксельные границы экрана → компоненты чернил →
привязка цифр к компонентам (IoU наших глифов) → локальное уточнение боксов (y целые, x шаг 0.25) →
привязка к сетке (поля, зазор 2u, стойка «1» = 4u) → overrides.json → вывод.
"""
import sys, os, json, math, time, itertools, argparse
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fluxglyph as fg

GRID = os.path.join(ROOT, 'reference', 'tdc_3_all_1440_grid.jpg')
GRID2 = os.path.join(ROOT, 'reference', 'user_grid_2000.webp')
T_STROKE = 4.0
GAP = 2.0
CONTENT_Y0, CONTENT_Y1 = 5.0, 55.0
CX0, CX1 = 5.2, 45.08
SCREEN_H = 60.0

# ---------------------------------------------------------------- решётка

def _runs(v, th):
    out, s = [], None
    for i, x in enumerate(v > th):
        if x and s is None:
            s = i
        if not x and s is not None:
            out.append((s, i - 1)); s = None
    if s is not None:
        out.append((s, len(v) - 1))
    return out


def find_lattice(g):
    """Не хардкодим координаты: ищем 60 столбцов и 24 строки по проекциям светлых пикселей."""
    white = g > 0.8
    cp, rp = white.sum(0), white.sum(1)
    cr = _runs(cp, 0.1 * cp.max())
    rr0 = _runs(rp, 0.1 * rp.max())
    mx = max(r[1] - r[0] for r in rr0)
    rr = [r for r in rr0 if r[1] - r[0] > 0.6 * mx]
    assert len(cr) == 60 and len(rr) == 24, (len(cr), len(rr))
    rows = []
    for r, (ya, yb) in enumerate(rr):
        for c, (xa, xb) in enumerate(cr):
            sub = g[ya - 3:yb + 4, xa - 3:xb + 4]
            h, w = sub.shape
            prof = sub[int(h * .3):int(h * .7)].mean(0)
            L = 8 - prof[:8].sum() + (xa - 3)
            R = (xb + 4 - 8) + prof[-8:].sum()
            midc = sub[:, int(w * .3):int(w * .7)].mean(1)
            T = 8 - midc[:8].sum() + (ya - 3)
            B = (yb + 4 - 8) + midc[-8:].sum()
            rows.append((r, c, L, R, T, B))
    a = np.array(rows)
    # L(c), T(r) — линейные
    kx, bx = np.polyfit(a[:, 1], a[:, 2], 1)
    ky, by = np.polyfit(a[:, 0], a[:, 4], 1)
    W = float(np.median(a[:, 3] - a[:, 2]))
    H = float(np.median(a[:, 5] - a[:, 4]))
    resid = max(np.abs(a[:, 2] - (kx * a[:, 1] + bx)).max(), np.abs(a[:, 4] - (ky * a[:, 0] + by)).max())
    return dict(L0=bx, Lp=kx, T0=by, Tp=ky, W=W, H=H, s=H / 60.0, resid=float(resid))


class Cell:
    """Окно ячейки: пересчёт u ↔ пиксели с субпиксельной привязкой экрана."""
    PAD_U = 1.5

    def __init__(self, g, lat, h, m, content=(5.2, 5.0, 45.08, 55.0)):
        self.h, self.m = h, m
        self.s = lat['s']
        self.L = lat['L0'] + lat['Lp'] * m
        self.T = lat['T0'] + lat['Tp'] * h
        cx0, cy0, cx1, cy1 = content
        self.wx0 = int(math.floor(self.L + (cx0 - self.PAD_U) * self.s))
        self.wx1 = int(math.ceil(self.L + (cx1 + self.PAD_U) * self.s))
        self.wy0 = int(math.floor(self.T + (cy0 - self.PAD_U) * self.s))
        self.wy1 = int(math.ceil(self.T + (cy1 + self.PAD_U) * self.s))
        self.W = self.wx1 - self.wx0
        self.H = self.wy1 - self.wy0
        self.ox = self.L - self.wx0
        self.oy = self.T - self.wy0
        self.d = 1.0 - g[self.wy0:self.wy1, self.wx0:self.wx1]
        # вес: только содержимое ±0.5u (экран вне контента не трогаем: скруглённые углы, рамка)
        xs = (np.arange(self.W) + 0.5 - self.ox) / self.s
        ys = (np.arange(self.H) + 0.5 - self.oy) / self.s
        mx = (xs >= cx0 - 0.5) & (xs <= cx1 + 0.5)
        my = (ys >= cy0 - 0.5) & (ys <= cy1 + 0.5)
        self.wgt = (my[:, None] & mx[None, :]).astype(np.float32)

    def u2px(self, ux, uy):
        return self.L + ux * self.s, self.T + uy * self.s


def _merge(P, over):
    if not over:
        return P
    Q = dict(P or fg.DEFAULT_P)
    Q.update(over)
    return Q


def render(cell, digit, box, P=None, ss=3, over=None):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if w < 1.0 or h < 1.0:
        return np.zeros((cell.H, cell.W), np.float32)
    polys = fg.glyph(digit, x0, y0, w, h, T_STROKE, _merge(P, over))
    return fg.rasterize(polys, cell.W, cell.H, ss, cell.s, cell.ox, cell.oy)


def soft_iou(cov, d, wgt):
    a = np.minimum(cov, d) * wgt
    b = np.maximum(cov, d) * wgt
    return float(a.sum() / max(b.sum(), 1e-9))


def digits_for(h, m, h12=False):
    if m == 0:
        return [int(c) for c in str(h)]
    return [h // 10, h % 10, m // 10, m % 10]

# ---------------------------------------------------------------- компоненты

def components(cell, thr=0.5, minpx=4):
    lab, n = ndi.label((cell.d > thr) & (cell.wgt > 0))
    out = []
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        m = lab[sl] == i
        if m.sum() < minpx:
            continue
        ys, xs = np.nonzero(lab == i)
        wsum = cell.d[ys, xs]
        # субпиксельный bbox по взвешенным краям: край = граница пикселя ± покрытие крайнего ряда/столбца
        x0p, x1p, y0p, y1p = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        out.append(dict(bbox_px=(x0p, y0p, x1p, y1p), area=int(m.sum())))
    return out


def bbox_u(cell, bp):
    x0, y0, x1, y1 = bp
    return [(x0 - cell.ox) / cell.s, (y0 - cell.oy) / cell.s, (x1 - cell.ox) / cell.s, (y1 - cell.oy) / cell.s]


def q(v, step):
    return round(v / step) * step

# ---------------------------------------------------------------- привязка и уточнение

def assign(cell, digits, comps, P=None):
    """Лучшая перестановка цифр по компонентам (IoU глифа в bbox компоненты). При равенстве — порядок чтения."""
    n = len(digits)
    boxes = []
    for c in comps:
        b = bbox_u(cell, c['bbox_px'])
        b = [q(b[0], 0.25), round(b[1]), q(b[2], 0.25), round(b[3])]
        b = [min(max(b[0], CX0), CX1), min(max(b[1], CONTENT_Y0), CONTENT_Y1), min(max(b[2], CX0), CX1), min(max(b[3], CONTENT_Y0), CONTENT_Y1)]
        boxes.append(b)
    # матрица IoU цифра×компонента по локальной маске компоненты
    M = np.zeros((n, len(comps)))
    for i, dg in enumerate(digits):
        for j, b in enumerate(boxes):
            cov = render(cell, dg, b, P)
            # ограничить сравнение окрестностью bbox
            x0, y0, x1, y1 = [int(v) for v in (cell.L + b[0] * cell.s - cell.wx0 - 2, cell.T + b[1] * cell.s - cell.wy0 - 2,
                                               cell.L + b[2] * cell.s - cell.wx0 + 2, cell.T + b[3] * cell.s - cell.wy0 + 2)]
            x0, y0 = max(x0, 0), max(y0, 0)
            sl = (slice(y0, y1), slice(x0, x1))
            M[i, j] = soft_iou(cov[sl], cell.d[sl], cell.wgt[sl])
    # порядок чтения компонент: сверху вниз, слева направо (по центру bbox, с допуском по строкам)
    order_key = lambda b: (round((b[1] + b[3]) / 2 / 6.0), (b[0] + b[2]) / 2)
    best = None
    for perm in itertools.permutations(range(len(comps)), n):
        sc = sum(M[i, perm[i]] for i in range(n))
        # tie-break: чем ближе к порядку чтения, тем лучше (малая добавка)
        rd = sorted(range(len(comps)), key=lambda j: order_key(boxes[j]))
        tb = -1e-4 * sum(abs(rd.index(perm[i]) - i) for i in range(n))
        if best is None or sc + tb > best[0]:
            best = (sc + tb, perm)
    perm = best[1]
    return [list(boxes[perm[i]]) for i in range(n)], [float(M[i, perm[i]]) for i in range(n)]


def total_iou(cell, digits, boxes, cache, P=None, params=None):
    cov = np.zeros((cell.H, cell.W), np.float32)
    for k, (dg, b) in enumerate(zip(digits, boxes)):
        ov = params[k] if params else None
        key = (dg, tuple(b), tuple(sorted(ov.items())) if ov else ())
        if key not in cache:
            cache[key] = render(cell, dg, b, P, over=ov)
        cov = np.maximum(cov, cache[key])
    return soft_iou(cov, cell.d, cell.wgt)


def refine(cell, digits, boxes, P=None, sweeps=8, stepx=0.25, stepy=1.0, params=None):
    boxes = [list(b) for b in boxes]
    cache = {}
    cur = total_iou(cell, digits, boxes, cache, P, params)
    for _ in range(sweeps):
        improved = False
        for k in range(len(boxes)):
            for e in range(4):
                step = stepx if e in (0, 2) else stepy
                for mult in (1, 2, -1, -2):
                    trial = [list(b) for b in boxes]
                    trial[k][e] += mult * step
                    b = trial[k]
                    if b[2] - b[0] < 3 or b[3] - b[1] < 3:
                        continue
                    if b[0] < CX0 - 0.01 or b[2] > CX1 + 0.01 or b[1] < CONTENT_Y0 - 0.01 or b[3] > CONTENT_Y1 + 0.01:
                        continue
                    sc = total_iou(cell, digits, trial, cache, P, params)
                    if sc > cur + 1e-4:
                        cur, boxes, improved = sc, trial, True
                        break
        if not improved:
            break
    return boxes, cur

# ---------------------------------------------------------------- привязка к сетке

CX0, CX1 = 5.2, 45.08

def snap(boxes, digits, cell=None, P=None, cache=None):
    """Привязка к сетке: поля контента, зазоры 2u, стойка «1» без флажка = 4u."""
    B = [list(b) for b in boxes]
    # границы контента
    for b in B:
        if abs(b[1] - CONTENT_Y0) <= 0.6: b[1] = CONTENT_Y0
        if abs(b[3] - CONTENT_Y1) <= 0.6: b[3] = CONTENT_Y1
        if abs(b[0] - CX0) <= 0.9: b[0] = CX0
        if abs(b[2] - CX1) <= 0.9: b[2] = CX1
    # структурный прижим: если дальше к краю контента нет других боксов, бокс доходит до края (раскладка = разбиение контента)
    n = len(B)
    for k, b in enumerate(B):
        oth = [B[j] for j in range(n) if j != k]
        ov_x = lambda o: min(b[2], o[2]) - max(b[0], o[0]) > 1.0
        ov_y = lambda o: min(b[3], o[3]) - max(b[1], o[1]) > 1.0
        if CONTENT_Y1 - 2.1 <= b[3] < CONTENT_Y1 and not any(ov_x(o) and o[1] >= b[3] - 0.5 for o in oth):
            b[3] = CONTENT_Y1
        if CONTENT_Y0 < b[1] <= CONTENT_Y0 + 2.1 and not any(ov_x(o) and o[3] <= b[1] + 0.5 for o in oth):
            b[1] = CONTENT_Y0
        if CX0 < b[0] <= CX0 + 1.6 and not any(ov_y(o) and o[2] <= b[0] + 0.5 for o in oth):
            b[0] = CX0
        if CX1 - 1.6 <= b[2] < CX1 and not any(ov_y(o) and o[0] >= b[2] - 0.5 for o in oth):
            b[2] = CX1
    # стойка «1» (w < 1.4t): ровно t
    for k, (dg, b) in enumerate(zip(digits, B)):
        if dg == 1 and (b[2] - b[0]) < 1.4 * T_STROKE + 0.9:
            if abs((b[2] - b[0]) - T_STROKE) <= 0.9:
                cx = b[2]                      # стойка у правого края бокса
                b[0] = cx - T_STROKE
    return B

def align_edges(cell, digits, boxes, P=None, params=None, tol=0.55):
    """Выравнивание левых (и правых) краёв столбцов: края x в пределах tol считаем одним (раскладки Apple выровнены)."""
    B = [list(b) for b in boxes]
    cache = {}
    for e in (0, 2):
        items = sorted(((B[k][e], k) for k in range(len(B))))
        clusters, cur = [], [items[0]]
        for it in items[1:]:
            if it[0] - cur[-1][0] <= tol:
                cur.append(it)
            else:
                clusters.append(cur); cur = [it]
        clusters.append(cur)
        for cl in clusters:
            vals = [v for v, _ in cl]
            if len(cl) < 2 or max(vals) - min(vals) < 1e-6:
                continue
            fixed = [v for v in vals if abs(v - CX0) < 1e-6 or abs(v - CX1) < 1e-6]
            cands = [fixed[0]] if fixed else sorted(set(vals)) + [round(sum(vals) / len(vals), 2)]
            best = None
            for c in cands:
                t = [list(b) for b in B]
                for _, k in cl:
                    t[k][e] = c
                sc = total_iou(cell, digits, t, cache, P, params)
                if best is None or sc > best[0] + 1e-6:
                    best = (sc, t)
            B = best[1]
    return B


def gap_fix(cell, digits, boxes, P=None, params=None):
    """Зазор между соседними боксами должен быть ровно 2u. Если измеренный в [1.2, 3.0], выбираем лучший по IoU вариант
    (сдвиг левого/правого/симметрично) из трёх."""
    B = [list(b) for b in boxes]
    cache = {}
    n = len(B)
    for i in range(n):
        for j in range(n):
            if i == j: continue
            a, b = B[i], B[j]
            # горизонтальные соседи: пересекаются по y
            if min(a[3], b[3]) - max(a[1], b[1]) > 1.0:
                g = b[0] - a[2]
                if 1.0 <= g <= 3.2 and abs(g - GAP) > 1e-6:
                    opts = []
                    d = g - GAP
                    for da, db in ((d, 0), (0, -d), (d / 2, -d / 2)):
                        t = [list(x) for x in B]
                        t[i][2] += da
                        t[j][0] += db
                        t[i][2] = q(t[i][2], 0.05); t[j][0] = q(t[j][0], 0.05)
                        opts.append((total_iou(cell, digits, t, cache, P, params), t))
                    B = max(opts, key=lambda o: o[0])[1]
            # вертикальные соседи: пересекаются по x
            if min(a[2], b[2]) - max(a[0], b[0]) > 1.0:
                g = b[1] - a[3]
                if 1.0 <= g <= 3.2 and abs(g - GAP) > 1e-6:
                    d = g - GAP
                    opts = []
                    for da, db in ((round(d), 0), (0, -round(d))):
                        t = [list(x) for x in B]
                        t[i][3] += da
                        t[j][1] += db
                        opts.append((total_iou(cell, digits, t, cache, P, params), t))
                    B = max(opts, key=lambda o: o[0])[1]
    return B

# ---------------------------------------------------------------- основной проход

def process_cell(g, lat, h, m, P=None, overrides=None):
    cell = Cell(g, lat, h, m)
    digits = digits_for(h, m)
    key = '%02d:%02d' % (h, m)
    rep = dict(minute=key, digits=digits)
    comps = components(cell)
    rep['components'] = len(comps)
    ov = (overrides or {}).get(key)
    seed = ov.get('seed') if ov else None
    if ov and not seed:
        boxes = ov['boxes']
        rep['override'] = True
        cache = {}
        params = [dict(p) for p in ov.get('params', [{}] * len(boxes))]
        rep['iou'] = total_iou(cell, digits, boxes, cache, P, params)
        rep['flags'] = ['override']
        return (boxes, params), rep
    flags = []
    if seed:
        flags.append('seed из overrides.json')
        comps = None
    elif len(comps) != len(digits):
        flags.append('components %d != %d' % (len(comps), len(digits)))
        # запасной путь: неполная привязка — берём что есть, остальное достроит уточнение с нуля (плохо) → помечаем
        if len(comps) < len(digits):
            rep['flags'] = flags
            boxes = [[CX0, CONTENT_Y0, CX1, CONTENT_Y1]] * len(digits)
            return (boxes, [dict() for _ in boxes]), rep
        comps = sorted(comps, key=lambda c: -c['area'])[:len(digits)]
    if seed:
        boxes = [list(b) for b in seed]
    else:
        boxes, ious = assign(cell, digits, comps, P)
    boxes, sc = refine(cell, digits, boxes, P)
    # две итерации «форма ↔ бокс»: параметры глифов под текущие боксы, затем боксы под эти параметры
    params, _ = fit_params(cell, digits, boxes, P)
    boxes, sc = refine(cell, digits, boxes, P, params=params)
    params, _ = fit_params(cell, digits, boxes, P)
    boxes = snap(boxes, digits)
    for _ in range(2):
        boxes = align_edges(cell, digits, boxes, P, params)
        boxes = gap_fix(cell, digits, boxes, P, params)
    cache = {}
    rep['iou_boxes'] = total_iou(cell, digits, boxes, cache, P, params)
    params, final = fit_params(cell, digits, boxes, P)
    rep['params'] = params
    rep['iou'] = final
    rep['iou_prefit'] = sc
    rep['per_digit_iou'] = None
    if final < 0.8:
        flags.append('iou<0.8')
    rep['flags'] = flags
    return (boxes, params), rep


# ---------------------------------------------------------------- P2: внутренние параметры глифа под ячейку
# (ключ, знаменатель доли: 'H' = h−t, 'h', 'W' = w−t, 'w'); позиции перебираем с шагом 1u → края перекладин на целых строках
SEARCH = {
    0: [('rho0', 4.0, 0.5)],
    1: [('1_d1', 1.0, 0.5), ('1_d2', 1.0, 0.5), ('1_d3', 1.0, 0.5)],
    2: [('rho2', 4.0, 0.5), ('2_y1', 'H', 1.0), ('2_y2', 'H', 1.0), ('2_leg', 'H', 1.0)],
    3: [('rho3', 4.0, 0.5), ('3_ym', 'H', 1.0), ('3_leg', 'H', 1.0), ('3_bar', 'W', 1.0)],
    4: [('rho4', 4.0, 0.5), ('4_yc', 'H', 1.0)],
    5: [('rho5', 4.0, 0.5), ('5_ym', 'H', 1.0), ('5_ys', 'h', 1.0), ('5_leg', 'h', 1.0)],
    6: [('rho6', 4.0, 0.5), ('6_yb', 'H', 1.0), ('6_leg', 'H', 1.0)],
    7: [('7_bx', 'w', 1.0)],
    8: [('rho8', 4.0, 0.5), ('8_ym', 'H', 1.0)],
}
SEARCH[9] = SEARCH[6]


def fit_params(cell, digits, boxes, P=None, span=9, gain=0.004):
    """Для каждого глифа подбираем параметры формы, максимизируя IoU ячейки; оставляем только то, что даёт заметный выигрыш."""
    params = [dict() for _ in boxes]
    cache = {}
    base = total_iou(cell, digits, boxes, cache, P, params)
    cur = base
    for k, (dg, b) in enumerate(zip(digits, boxes)):
        spec = SEARCH.get(dg)
        if not spec:
            continue
        w, h = b[2] - b[0], b[3] - b[1]
        res = fg.resolve(P or fg.DEFAULT_P, w, h)
        for rnd in range(2):
            for key, den, stp in spec:
                d = den if isinstance(den, float) else {'H': h - T_STROKE, 'h': h, 'W': w - T_STROKE, 'w': w}[den]
                if d <= 2 and not isinstance(den, float):
                    continue
                f0 = params[k].get(key, res[key])
                lo, hi = fg.BOUNDS[key]
                best = (cur, params[k].get(key))
                sp = span if stp >= 1.0 else int(span * 1.4)
                for i in range(-sp, sp + 1):
                    f = round((f0 * d + i * stp) / d, 5) if i else f0
                    if not (lo <= f <= hi):
                        continue
                    trial = [dict(x) for x in params]
                    trial[k][key] = f
                    sc = total_iou(cell, digits, boxes, cache, P, trial)
                    if sc > best[0] + 1e-5:
                        best = (sc, f)
                if best[1] is not None and best[1] != params[k].get(key):
                    params[k][key] = best[1]
                    cur = best[0]
    if cur < base + gain:
        params = [dict() for _ in boxes]
        cur = base
    else:
        # убрать параметры, не давшие выигрыша по отдельности (регуляризация: сбросить и сравнить)
        for k in range(len(params)):
            for key in list(params[k]):
                trial = [dict(x) for x in params]
                del trial[k][key]
                sc = total_iou(cell, digits, boxes, cache, P, trial)
                if sc > cur - gain / 2:
                    params = trial
                    cur = max(cur, sc) if sc > cur else cur
        cur = total_iou(cell, digits, boxes, cache, P, params)
    return params, cur


def refine_snapped(cell, digits, boxes, P=None):
    """Мелкий добор: сдвиги на 0.05u не нужны; просто оценка. Оставлено как точка расширения."""
    cache = {}
    return boxes, total_iou(cell, digits, boxes, cache, P)


def validate_second(layouts, lat1):
    """Вторая независимая выборка (reference/user_grid_2000.webp, ≈0.49 px/u): IoU наших раскладок против неё.
    Разрешение слишком мало для переизвлечения боксов, поэтому проверяем согласие, а не пере-фитим.
    Решётка = решётка основной сетки × (ширина/4800); сдвиг (dx, dy) подбираем по IoU на пробных ячейках."""
    g2 = np.asarray(Image.open(GRID2).convert('L'), dtype=np.float32) / 255.0
    k = g2.shape[1] / 4800.0
    base = {kk: lat1[kk] * k for kk in ('L0', 'Lp', 'T0', 'Tp', 'W', 'H', 's')}

    def cell_iou(lat, h, m):
        cell = Cell(g2, lat, h, m)
        digits = digits_for(h, m)
        B, PP = from_out(layouts[h * 60 + m])
        cov = np.zeros((cell.H, cell.W), np.float32)
        for dg, b, pp in zip(digits, B, PP):
            cov = np.maximum(cov, render(cell, dg, b, over=pp))
        return soft_iou(cov, cell.d, cell.wgt)
    probe = [(h, m) for h in range(0, 24, 5) for m in range(1, 60, 7)]
    best = None
    for dx in np.arange(-2.0, 2.01, 0.5):
        for dy in np.arange(-2.0, 2.01, 0.5):
            lat = dict(base, L0=base['L0'] + dx, T0=base['T0'] + dy)
            sc = np.mean([cell_iou(lat, h, m) for h, m in probe])
            if best is None or sc > best[0]:
                best = (sc, dx, dy)
    lat2 = dict(base, L0=base['L0'] + best[1], T0=base['T0'] + best[2], dx=float(best[1]), dy=float(best[2]))
    ious = {'%02d:%02d' % (h, m): cell_iou(lat2, h, m) for h in range(24) for m in range(60)}
    return lat2, ious


def to_out(boxes, params):
    out = []
    for b, p in zip(boxes, params):
        e = [round(float(b[0]), 2), round(float(b[1]), 2), round(float(b[2] - b[0]), 2), round(float(b[3] - b[1]), 2)]
        if p:
            e.append({k: round(float(v), 4) for k, v in p.items()})
        out.append(e)
    return out


def from_out(entries):
    """[x,y,w,h(,p)] → ([x0,y0,x1,y1], params)"""
    boxes = [[e[0], e[1], e[0] + e[2], e[1] + e[3]] for e in entries]
    return boxes, [dict(e[4]) if len(e) > 4 else {} for e in entries]


def load_layouts(path=None):
    txt = open(path or os.path.join(ROOT, 'data', 'layouts.js')).read()
    return json.loads(txt[txt.index('window.FLUX_LAYOUTS = ') + 22: txt.rindex(';')])


def _worker(args):
    h, m = args
    global _G, _LAT, _OV, _P
    return (h, m) + process_cell(_G, _LAT, h, m, _P, _OV)


def init_globals():
    global _G, _LAT, _OV, _P
    _G = np.asarray(Image.open(GRID).convert('L'), dtype=np.float32) / 255.0
    _LAT = find_lattice(_G)
    ovp = os.path.join(HERE, 'overrides.json')
    _OV = json.load(open(ovp)) if os.path.exists(ovp) else {}
    _P = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    init_globals()
    print('решётка:', {k: round(v, 4) for k, v in _LAT.items()})
    todo = [(h, m) for h in range(24) for m in range(60)]
    if a.only:
        sel = set(a.only)
        todo = [(h, m) for h, m in todo if '%02d:%02d' % (h, m) in sel]
    t0 = time.time()
    results = {}
    if a.jobs > 1 and len(todo) > 8:
        import multiprocessing as mp
        with mp.Pool(a.jobs, initializer=init_globals) as pool:
            for i, r in enumerate(pool.imap_unordered(_worker, todo, chunksize=8)):
                results[(r[0], r[1])] = (r[2], r[3])
                if i % 100 == 0:
                    print(i, '/', len(todo), round(time.time() - t0), 'с', flush=True)
    else:
        for h, m in todo:
            r = _worker((h, m)); results[(h, m)] = (r[2], r[3])
    if not a.only:
        layouts = []
        report = {'lattice': _LAT, 'minutes': {}}
        for h in range(24):
            for m in range(60):
                (boxes, params), rep = results[(h, m)]
                layouts.append(to_out(boxes, params))
                report['minutes']['%02d:%02d' % (h, m)] = rep
        out = a.out or os.path.join(ROOT, 'data', 'layouts.js')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'w') as f:
            f.write('// Сгенерировано tools/extract.py из reference/tdc_3_all_1440_grid.jpg\n')
            f.write('// Индекс = h*60+m (24-часовой); элемент = боксы слотов H1 H2 M1 M2: [x, y, w, h(, {параметры формы})] в u, y вниз; экран 50.284×60u\n')
            f.write('window.FLUX_LAYOUTS = ' + json.dumps(layouts, separators=(',', ':')) + ';\n')
        json.dump(report, open(os.path.join(HERE, 'extract_report.json'), 'w'), ensure_ascii=False, indent=1, default=float)
        lat2, i2 = validate_second(layouts, _LAT)
        v = np.array(list(i2.values()))
        report['second_sample'] = {'file': 'reference/user_grid_2000.webp', 'px_per_u': lat2['s'], 'shift_px': [lat2['dx'], lat2['dy']], 'median_iou': float(np.median(v)),
                                   'min_iou': float(v.min()), 'below_0.6': int((v < 0.6).sum()), 'iou': i2}
        print('вторая выборка (2000px): медиана IoU %.3f, min %.3f, <0.6: %d' % (np.median(v), v.min(), (v < 0.6).sum()))
        json.dump(report, open(os.path.join(HERE, 'extract_report.json'), 'w'), ensure_ascii=False, indent=1, default=float)
        ious = np.array([report['minutes'][k]['iou'] for k in report['minutes'] if 'iou' in report['minutes'][k]])
        print('медиана IoU %.3f, min %.3f, <0.8: %d, <0.75: %d' % (np.median(ious), ious.min(), (ious < .8).sum(), (ious < .75).sum()))
    else:
        for (h, m), (boxes, rep) in sorted(results.items()):
            print(rep['minute'], rep['digits'], 'comp', rep['components'], 'iou', round(rep.get('iou', 0), 3), rep.get('flags'))
            for b, pp in zip(*boxes):
                print('   ', [round(v, 2) for v in b], pp)
    print('готово за', round(time.time() - t0), 'с')


if __name__ == '__main__':
    main()
