import sys; sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from _fitlab import *
from scipy.optimize import minimize
import json
def fit(digit, keys, x0, bounds, P0=None):
    P0 = dict(P0 or fg.DEFAULT_P)
    insts = [i for i in INST if i[1] == digit]
    def f(x):
        P = dict(P0)
        for k, v in zip(keys, x): P[k] = v
        return -np.mean([inst_score(i, P) for i in insts])
    r = minimize(f, x0, method='Powell', bounds=bounds, options={'xtol':1e-3,'ftol':1e-5})
    P = dict(P0)
    for k, v in zip(keys, r.x): P[k] = float(v)
    return P, -r.fun, len(insts)
if __name__ == '__main__':
    out = {}
    for d, keys, x0, b in [
        (3, ['3_leg','3_bar','3_ym','rho'], [0.18,0.25,0.5,0.75], [(0.05,0.4),(0.0,0.5),(0.4,0.6),(0.5,1.0)]),
        (7, ['7_bx','7_tx','7_vs','7_txk'], [0.3,1.0,0.3,1.12], [(0.1,0.6),(0.7,1.4),(0,1.5),(0.8,1.4)]),
        (6, [], [], []),
    ]:
        if keys:
            P, s, n = fit(d, keys, x0, b)
            print(d, round(s,4), n, {k: round(P[k],3) for k in keys})
