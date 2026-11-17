import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))) + '/'
# решётка (получена из проекций, tools/extract.py пересчитывает её сам; здесь значения для отладки)
PX_PER_U = 70.49155 / 60
CONTENT = (5.15, 5.0, 45.13, 55.0)       # x0,y0,x1,y1 в u
SCREEN_W_U = 50.284

def load_gray(path):
    return np.asarray(Image.open(path).convert('L'), dtype=np.float32) / 255.0

def expected_digits(h, m, h12=False):
    if m == 0:
        return [int(c) for c in str(h)]
    return [h // 10, h % 10, m // 10, m % 10]
