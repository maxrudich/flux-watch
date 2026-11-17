import sys, json
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np
from PIL import Image
import extract as ex
SP='/private/tmp/claude-501/-Users-max-Documents-Claude-Projects-flux-watch/afa109c7-f74e-4f2d-8576-abb24b6de1d3/scratchpad/'
def overlays(minutes, out, scale=6, lay=None):
    g=np.asarray(Image.open(ex.GRID).convert('L'),dtype=np.float32)/255
    lat=ex.find_lattice(g)
    if lay is None:
        txt=open(ex.ROOT+'/data/layouts.js').read(); lay=json.loads(txt[txt.index('window.FLUX_LAYOUTS = ')+22:txt.rindex(';')])
    tiles=[]
    for mn in minutes:
        h,m=map(int,mn.split(':'))
        cell=ex.Cell(g,lat,h,m); digits=ex.digits_for(h,m)
        cov=np.zeros((cell.H,cell.W),np.float32)
        bx,pp=ex.from_out(lay[h*60+m])
        for dg,b,p in zip(digits,bx,pp): cov=np.maximum(cov,ex.render(cell,dg,b,over=p))
        rgb=np.zeros((cell.H,cell.W,3),np.float32)
        rgb[...,0]=cov; rgb[...,1]=np.minimum(cov,cell.d); rgb[...,2]=cell.d
        img=Image.fromarray((np.clip(rgb,0,1)*255).astype(np.uint8)).resize((cell.W*scale,cell.H*scale),Image.NEAREST)
        tiles.append(img)
    W=sum(t.width for t in tiles)+8*len(tiles); H=max(t.height for t in tiles)
    c=Image.new('RGB',(W,H)); x=0
    for t in tiles: c.paste(t,(x,0)); x+=t.width+8
    c.save(out); return c.size
if __name__=='__main__':
    print(overlays(sys.argv[2:], SP+sys.argv[1]))
