#!/usr/bin/env python3
"""Голдены 10:09…10:15 из видео (ТЗ §4.8): кадры 2–16 с 4 к/с, боксы чернил → u (высота чернил = 50u, левый край = поле),
сравнение с data/layouts.js. Нужен ffmpeg.   .venv/bin/python -I tools/check_video.py"""
import os, sys, glob, subprocess, tempfile
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import extract as ex
lay = ex.load_layouts()
tmp = tempfile.mkdtemp()
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '2', '-t', '14', '-i', os.path.join(ROOT, 'reference', 'tdc_4_video.mp4'), '-vf', 'fps=4', os.path.join(tmp, 'g_%03d.png')], check=True)

def boxes(path):
    im = np.array(Image.open(path).convert('RGB')).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    mx, mn = im.max(2), im.min(2)
    ink = ((r < 60) & (g < 60) & (b < 60)) | ((mn > 185) & (mx < 238) & ((mx - mn) < 14))
    lab, n = ndi.label(ink)
    out = []
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        a = (lab[sl] == i).sum(); h = sl[0].stop - sl[0].start; w = sl[1].stop - sl[1].start
        if a > 1500 and h < 1000 and w < 1000:
            out.append((sl[1].start, sl[0].start, sl[1].stop, sl[0].stop))
    return out

best = {}
frames = {}
for p in sorted(glob.glob(os.path.join(tmp, 'g_*.png'))):
    cs = boxes(p)
    if len(cs) != 4:
        continue
    x0 = min(c[0] for c in cs); y0 = min(c[1] for c in cs); y1 = max(c[3] for c in cs)
    u = (y1 - y0) / 50.0
    if u < 14:      # только кадры крупного плана (мозаика и Always-On в начале/конце пропускаются)
        continue
    U = [[ex.CX0 + (c[0] - x0) / u, 5 + (c[1] - y0) / u, ex.CX0 + (c[2] - x0) / u, 5 + (c[3] - y0) / u] for c in cs]
    for m in range(9, 16):
        B, _ = ex.from_out(lay[10 * 60 + m])
        err = sum(min(sum(abs(a - b) for a, b in zip(q, bb)) for bb in B) for q in U) / len(U) / 4
        if err < 0.5:
            best.setdefault(m, []).append(err)
            frames.setdefault(m, []).append(2 + (int(os.path.basename(p)[2:5]) - 1) / 4)
for m in sorted(best):
    print('10:%02d  кадров %2d (t=%s с)  средняя ошибка края %.2fu (макс по кадрам %.2fu)' % (m, len(best[m]), ','.join('%.2f' % t for t in frames[m]), np.mean(best[m]), np.max(best[m])))
