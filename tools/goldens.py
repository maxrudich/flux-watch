#!/usr/bin/env python3
"""Голдены ТЗ §4.8: боксы, снятые с крупных кадров (px → u по двум якорям: левый край чернил = поле, низ = строка 55).
Запуск:  .venv/bin/python -I tools/goldens.py   (сравнивает с data/layouts.js, допуск 1u)"""
import os, re, json, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CX0 = 5.2          # левое поле контента, u (совпадает с extract.py)

# (минута, источник, u px/u, x0px (левый край чернил = CX0), y1px (низ чернил = строка 55), боксы px [x0,y0,x1,y1] в порядке слотов; None = край срезан кадром)
G = [
 ('02:37', 'crops/0237_19_hires.png', 17.44, 168, 839, [[168,None,453,490],[489,None,862,386],[168,525,579,839],[489,420,862,839]]),
 ('03:09', 'crops/0309_0310_hires.png', 12.66, 128, 783, [[128,150,308,378],[334,150,631,378],[128,403,437,783],[463,403,632,783]]),
 ('03:10', 'crops/0309_0310_hires.png', 12.66, 926, 783, [[926,150,1094,504],[1120,150,1430,378],[926,530,1094,783],[1120,403,1430,783]]),
 ('03:09', 'tdc_2_kinetic_layout.jpg', 17.44, 955, 1577, [[955,706,1204,1020],[1240,706,1648,1020],[955,1055,1382,1577],[1417,1055,1649,1577]]),
 ('03:11', 'tdc_2_kinetic_layout.jpg', 17.44, 3152, 1577, [[3152,706,3382,1577],[3418,706,3845,1159],[3418,1194,3613,1577],[3649,1194,3844,1577]]),
 ('12:25', 'crops/1225_to_1226_morph.png', 8.04, 102, 505, [[102,103,208,247],[225,103,422,336],[102,264,208,505],[225,352,422,505]]),
 ('12:26', 'tdc_2_kinetic_layout.jpg', 8.04, 3718, 2565, [[3718,2163,3825,2404],[3842,2163,4039,2307],[3718,2421,3825,2565],[3841,2324,4039,2565]]),
 ('12:04', 'tdc_0_hero.jpg', 17.44, 2053, 2637, [[2053,1766,2178,2358],[2214,1766,2747,2114],[2053,2394,2640,2637],[2214,2149,2747,2637]]),
 ('22:01', 'tdc_0_hero.jpg', 17.44, 2053, 1364, [[2426,493,2747,841],[2053,493,2391,1015],[2053,1051,2640,1364],[2426,876,2747,1364]]),
 ('03:00', 'tdc_0_hero.jpg', 17.44, 3157, 1971, [[3157,1099,3851,1971]]),
]

def golden_boxes():
    out = []
    for minute, src, u, x0px, y1px, boxes in G:
        bb = []
        for b in boxes:
            X0 = CX0 + (b[0] - x0px) / u; X1 = CX0 + (b[2] - x0px) / u
            Y0 = None if b[1] is None else 55 - (y1px - b[1]) / u
            Y1 = 55 - (y1px - b[3]) / u
            bb.append([X0, Y0, X1, Y1])
        out.append((minute, src, bb))
    return out

def load_layouts(path=None):
    path = path or os.path.join(ROOT, 'data', 'layouts.js')
    txt = open(path).read()
    return json.loads(txt[txt.index('window.FLUX_LAYOUTS = ') + 22: txt.rindex(';')])

def check(layouts, tol=1.0, verbose=True):
    ok_all = True; rows = []
    for minute, src, gb in golden_boxes():
        h, m = map(int, minute.split(':'))
        lay = [[e[0], e[1], e[0] + e[2], e[1] + e[3]] for e in layouts[h * 60 + m]]
        worst = 0; where = None
        for k, (g, l) in enumerate(zip(gb, lay)):
            for e in range(4):
                if g[e] is None: continue
                d = abs(g[e] - l[e])
                if d > worst: worst, where = d, (k, 'x0 y0 x1 y1'.split()[e], round(g[e], 2), round(l[e], 2))
        ok = worst <= tol
        ok_all &= ok
        rows.append((minute, src, worst, where, ok))
        if verbose:
            print('%s %-32s max|Δ| = %.2fu %s %s' % (minute, src, worst, where if worst > 0.6 else '', 'OK' if ok else 'НЕ СОШЛОСЬ'))
    return ok_all, rows

if __name__ == '__main__':
    ok, _ = check(load_layouts())
    print('ВСЕ ГОЛДЕНЫ В ДОПУСКЕ 1u' if ok else 'ЕСТЬ РАСХОЖДЕНИЯ > 1u')
    sys.exit(0 if ok else 1)
