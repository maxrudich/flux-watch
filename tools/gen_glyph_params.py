#!/usr/bin/env python3
"""Вшивает tools/glyph_params.json в src/glyph.js (между маркерами /*P:begin*/ … /*P:end*/)."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
P = json.load(open(os.path.join(HERE, 'glyph_params.json')))
def r(v):
    return [round(x, 5) for x in v] if isinstance(v, list) else round(v, 5)
js = '/*P:begin*/var DEFAULT_P = ' + json.dumps({k: r(v) for k, v in sorted(P.items())}, separators=(',', ':')) + ';/*P:end*/'
p = os.path.join(ROOT, 'src', 'glyph.js')
s = open(p).read()
s = re.sub(r'/\*P:begin\*/.*?/\*P:end\*/', lambda m: js, s, flags=re.S)
open(p, 'w').write(s)
print('src/glyph.js обновлён,', len(P), 'параметров')
