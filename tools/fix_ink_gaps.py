#!/usr/bin/env python3
"""Находит минуты, где чернила соседних глифов ближе GAP_MIN u, и подбирает боксы так, чтобы зазор стал >= GAP_GOAL
при максимальном IoU с эталоном. Результат дописывается в tools/overrides.json как {"boxes": [...], "params": [...]}
(формат boxes = [x0,y0,x1,y1] в u). Затем: .venv/bin/python -I tools/extract.py  → data/layouts.js.
Запуск: .venv/bin/python -I tools/fix_ink_gaps.py [--dry] [--only HH:MM ...]
Причина проблемы: gap_fix в extract.py чинит только зазоры 1.0–3.2u, а при перекрытии боксов (<1u) и при зазоре 0–1u
ничего не делал: например в 01:34 бокс «4» (M2) начинался на 1u выше конца «1» (H2) и чернила слипались."""
import os, sys, json, argparse
import numpy as np
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import extract as ex
import fluxglyph as fg

RES = 5.0                      # px/u для измерения зазора
GAP_MIN, GAP_GOAL = 1.5, 1.6   # порог проверки / цель поиска (растр 0.2u)
MAX_IOU_DROP = 0.05            # исправление принимаем, только если IoU с эталоном упал не больше
W, H = int(52 * RES), int(62 * RES)

def mask(dg, b, p):
    w, h = b[2] - b[0], b[3] - b[1]
    if w < 1 or h < 1: return np.zeros((H, W), bool)
    polys = fg.glyph(dg, b[0], b[1], w, h, ex.T_STROKE, ex._merge(None, p))
    return fg.rasterize(polys, W, H, 2, RES, 0, 0) > 0.5

def gaps(digits, boxes, params):
    ms = [mask(d, b, p) for d, b, p in zip(digits, boxes, params)]
    out = {}
    for i in range(len(ms)):
        if not ms[i].any(): continue
        dist = ndi.distance_transform_edt(~ms[i]) / RES
        for j in range(i + 1, len(ms)):
            if ms[j].any(): out[(i, j)] = float(dist[ms[j]].min())
    return out

def viol(digits, boxes, params, goal=GAP_GOAL):
    ms = [mask(d, b, p) for d, b, p in zip(digits, boxes, params)]
    v = 0.0
    for i in range(len(ms)):
        if not ms[i].any(): continue
        dist = ndi.distance_transform_edt(~ms[i]) / RES
        for j in range(i + 1, len(ms)):
            if not ms[j].any(): continue
            ov = float((ms[i] & ms[j]).sum()) / RES ** 2            # площадь пересечения (u²): убирает плато при слипании
            v += max(0.0, goal - float(dist[ms[j]].min())) + 0.05 * ov
    return v

def fix_minute(cell, digits, boxes, params):
    cache = {}
    def obj(bx):
        return ex.total_iou(cell, digits, bx, cache, None, params) - 0.5 * viol(digits, bx, params)
    cur = obj(boxes)
    for _ in range(14):
        improved = False
        for k in range(len(boxes)):
            for e in range(4):
                for step in (0.25, 0.5, 1.0, 2.0, 3.0):
                    for sgn in (1, -1):
                        t = [list(b) for b in boxes]
                        t[k][e] += sgn * step
                        b = t[k]
                        if b[2] - b[0] < 3 or b[3] - b[1] < 3: continue
                        if b[0] < ex.CX0 - 0.01 or b[2] > ex.CX1 + 0.01 or b[1] < ex.CONTENT_Y0 - 0.01 or b[3] > ex.CONTENT_Y1 + 0.01: continue
                        sc = obj(t)
                        if sc > cur + 1e-4:
                            cur, boxes, improved = sc, t, True
        if not improved: break
    return boxes

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dry', action='store_true'); ap.add_argument('--only', nargs='*')
    ap.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2) - 1)); a = ap.parse_args()
    ex.init_globals()
    lays = ex.load_layouts()
    ovp = os.path.join(HERE, 'overrides.json'); ov = json.load(open(ovp))
    todo = []
    for i in range(1440):
        key = '%02d:%02d' % divmod(i, 60)
        if a.only and key not in a.only: continue
        if key in ov and 'seed' not in ov[key]: continue          # ручные правки не трогаем
        boxes, params = ex.from_out(lays[i]); digits = ex.digits_for(i // 60, i % 60)
        if min(gaps(digits, boxes, params).values(), default=9) < GAP_MIN: todo.append(i)
    print('минут с зазором < %.1fu: %d' % (GAP_MIN, len(todo)), flush=True)
    import multiprocessing as mp
    with mp.Pool(a.jobs, initializer=ex.init_globals) as pool:
        res = pool.map(_work, [(i, lays[i]) for i in todo], chunksize=2)
    n_ok = 0; log = []; exc = {}
    for i, b0, b1, p, iou0, iou1, g0, g1 in res:
        key = '%02d:%02d' % divmod(i, 60); ok = g1 >= GAP_MIN and iou1 >= iou0 - MAX_IOU_DROP; n_ok += ok
        log.append('%s gap %.2f→%.2f IoU %.3f→%.3f %s' % (key, g0, g1, iou0, iou1, 'ok' if ok else 'ОСТАВЛЕНО (эталон касается/слипается)'))
        if ok:
            if not a.dry: ov[key] = {'boxes': [[round(v, 2) for v in b] for b in b1], 'params': p}
        else:
            exc[key] = {'gap': round(g0, 2), 'iou': round(iou0, 3), 'fixed_gap': round(g1, 2), 'fixed_iou': round(iou1, 3)}
    print('\n'.join(log)); print('исправлено %d из %d, оставлено как есть %d' % (n_ok, len(todo), len(exc)))
    if not a.dry:
        json.dump(ov, open(ovp, 'w'), ensure_ascii=False, separators=(',', ':'))
        json.dump(exc, open(os.path.join(HERE, 'ink_contact_exceptions.json'), 'w'), ensure_ascii=False, indent=0)

def _work(args):
    i, lay = args
    h, m = divmod(i, 60); cell = ex.Cell(ex._G, ex._LAT, h, m); digits = ex.digits_for(h, m)
    b0, params = ex.from_out(lay)
    iou0 = ex.total_iou(cell, digits, b0, {}, None, params); g0 = min(gaps(digits, b0, params).values(), default=9)
    b1 = fix_minute(cell, digits, b0, params)
    iou1 = ex.total_iou(cell, digits, b1, {}, None, params); g1 = min(gaps(digits, b1, params).values(), default=9)
    return i, b0, b1, params, iou0, iou1, g0, g1

if __name__ == '__main__': main()
