import sys, json
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np
from PIL import Image
import fluxglyph as fg
from _ref_masks import ink_mask

ROOT = __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))) + '/'
SP = '/private/tmp/claude-501/-Users-max-Documents-Claude-Projects-flux-watch/afa109c7-f74e-4f2d-8576-abb24b6de1d3/scratchpad/'
_cache = {}

from scipy import ndimage as ndi
_lab = {}
def getlab(path):
    if path not in _lab:
        p, _, mode = path.partition('#')
        im, m = ink_mask(ROOT + p, None)
        if mode == 'gray':
            r, g, b = im[..., 0], im[..., 1], im[..., 2]
            m = (abs(r - 128) < 30) & (abs(g - 128) < 30) & (abs(b - 128) < 30)
        elif mode == 'black':
            r, g, b = im[..., 0], im[..., 1], im[..., 2]
            m = (r < 60) & (g < 60) & (b < 60)
        lab, n = ndi.label(m)
        _lab[path] = (lab, ndi.find_objects(lab))
    return _lab[path]

def getmask(path, bbox, tol=5):
    lab, objs = getlab(path)
    x0, y0, x1, y1 = bbox
    keep = np.zeros(lab.shape, bool)
    for i, sl in enumerate(objs, 1):
        if sl is None: continue
        a, b, c, d = sl[1].start, sl[0].start, sl[1].stop, sl[0].stop
        if a >= x0 - tol and b >= y0 - tol and c <= x1 + tol and d <= y1 + tol and (c - a) * (d - b) > 150:
            keep |= (lab == i)
    return keep

# (name, digit, image, bbox px (x0,y0,x1,y1) полуоткрытый, u_px)
def inst_score(inst, P, save=None, pad=6):
    name, d, path, (x0, y0, x1, y1), u = inst
    m = getmask(path, (x0, y0, x1, y1))
    ref = m[y0 - pad:y1 + pad, x0 - pad:x1 + pad].astype(np.float32)
    H, W = ref.shape
    w, h = (x1 - x0) / u, (y1 - y0) / u
    polys = fg.glyph(d, 0, 0, w, h, 4.0, P)
    cov = fg.rasterize(polys, W, H, 4, u, pad, pad)
    inter = np.minimum(cov, ref).sum()
    uni = np.maximum(cov, ref).sum()
    if save:
        rgb = np.zeros((H, W, 3), np.uint8)
        rgb[..., 0] = (cov * 255)
        rgb[..., 1] = (ref * 255) * 0 + np.minimum(cov, ref) * 255
        rgb[..., 2] = (ref * 255)
        # красный: только наш, синий: только эталон, белый: оба
        rgb[..., 1] = np.minimum(cov, ref) * 255
        im = Image.fromarray(rgb).resize((W * 3, H * 3), Image.NEAREST)
        im.save(save)
    return inter / max(uni, 1)


INST = []
def add(name, d, path, bbox, u): INST.append((name, d, path, bbox, u))
C = 'reference/crops/'
# 03:09 / 03:10
u = 12.6
add('0309_0a', 0, C+'0309_0310_hires.png', (128,150,308,378), u)
add('0309_3',  3, C+'0309_0310_hires.png', (334,150,631,378), u)
add('0309_0b', 0, C+'0309_0310_hires.png', (128,403,437,783), u)
add('0309_9',  9, C+'0309_0310_hires.png', (463,403,632,783), u)
add('0310_0a', 0, C+'0309_0310_hires.png', (926,150,1094,504), u)
add('0310_3',  3, C+'0309_0310_hires.png', (1120,150,1430,378), u)
add('0310_1',  1, C+'0309_0310_hires.png', (926,530,1094,783), u)
add('0310_0b', 0, C+'0309_0310_hires.png', (1120,403,1430,783), u)
u2 = 17.44
add('0237_3', 3, C+'0237_19_hires.png', (168,525,579,839), u2)
add('0237_7', 7, C+'0237_19_hires.png', (489,420,862,839), u2)
H = 'reference/tdc_0_hero.jpg'
uh = 17.44
add('1204_1', 1, H, (2053,1766,2178,2358), uh)
add('1204_2', 2, H, (2214,1766,2747,2114), uh)
add('1204_4', 4, H, (2214,2149,2747,2637), uh)
add('1204_0', 0, H, (2053,2394,2640,2637), uh)

M='reference/crops/1225_to_1226_morph.png'
u3=8.04
Mb=M+'#black'; Mg=M+'#gray'
add('1225s_1',1,Mb,(102,103,208,247),u3)
add('1225s_2a',2,Mb,(225,103,422,336),u3)
add('1225s_2b',2,Mb,(102,264,208,505),u3)
add('1225s_5',5,Mb,(225,352,422,505),u3)
for k,(a,b,c,d) in enumerate([(678,354,871,503),(1086,330,1279,503),(1495,306,1688,503)]): add('1225f%d_5'%k,5,Mg,(a,b,c,d),u3)
add('1226f_6',6,Mg,(1916,282,2108,503),u3)
for k,bb in enumerate([(676,103,873,336),(1084,103,1281,312),(1493,103,1690,288),(1914,103,2111,264)]): add('1225f%d_2a'%k,2,Mg,bb,u3)
for k,bb in enumerate([(552,264,659,505),(961,283,1068,505),(1369,302,1476,505),(1790,322,1897,505)]): add('1225f%d_2b'%k,2,Mg,bb,u3)
for k,bb in enumerate([(554,105,657,245),(963,105,1066,265),(1372,105,1474,284),(1793,105,1895,303)]): add('1225f%d_1'%k,1,Mg,bb,u3)
