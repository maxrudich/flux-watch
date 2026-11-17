# Вспомогательный модуль: маски чернил из эталонных кропов (для подгонки глифов)
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

def ink_mask(path, screen_bg_colors, tol=40):
    im = np.array(Image.open(path).convert('RGB')).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    black = (r < 60) & (g < 60) & (b < 60)
    light = (abs(r-214) < 22) & (abs(g-214) < 22) & (abs(b-216) < 22)
    return im, black | light

def comps(mask, minarea=300):
    lab, n = ndi.label(mask)
    out = []
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        a = (lab[sl] == i).sum()
        if a >= minarea:
            out.append((sl[1].start, sl[0].start, sl[1].stop, sl[0].stop, int(a)))
    return lab, out
