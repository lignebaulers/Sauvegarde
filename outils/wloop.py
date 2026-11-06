import json, sys, math, csv
sys.path.insert(0, '/tmp/claude-0/-home-claude/090c89ab-6469-5ab1-bebb-ae2242a06172/scratchpad/tools'); import devbuild3 as DB
S = '/tmp/claude-0/-home-claude/090c89ab-6469-5ab1-bebb-ae2242a06172/scratchpad/'
h, m, D = DB.load(S + 'r72/index.html')
def dec(s):
    pts = []; i = a = b = 0
    while i < len(s):
        for k in (0, 1):
            sh = r = 0
            while True:
                c = ord(s[i]) - 63; i += 1; r |= (c & 31) << sh; sh += 5
                if c < 32: break
            v = ~(r >> 1) if r & 1 else r >> 1
            if k == 0: a += v
            else: b += v
        pts.append((a / 1e6, b / 1e6))
    return pts
def km(p, q): return math.hypot((q[1] - p[1]) * math.cos(math.radians(p[0])) * 111.32, (q[0] - p[0]) * 111.32)
L = D['lines']['W']
v = next(v for v in L['variants'] if 'Quai 10' in v['stops'][0][0] and 'BRAINE' in v['stops'][0][0])
pts = dec(v['poly']); st = (v['stops'][0][1], v['stops'][0][2]); s2 = (v['stops'][1][1], v['stops'][1][2])
print('variante', v['file'], '|', len(pts), 'points |', v['km'], 'km')
print('1er arrêt', v['stops'][0][0], st, '| 2e', v['stops'][1][0], s2, round(km(st, s2) * 1000), 'm à vol d\'oiseau')
d = 0; i2 = None
for i in range(1, len(pts)):
    d += km(pts[i - 1], pts[i])
    if km(pts[i], s2) < 0.03 and i2 is None: i2 = (i, round(d * 1000))
print('le tracé atteint le 2e arrêt après', i2, 'm de tracé')
seg = pts[:i2[0] + 1]
print('écart max du tracé au 1er arrêt avant le 2e :', round(max(km(st, p) for p in seg) * 1000), 'm')
json.dump(seg, open(S + 'gpsdata/wloop_seg.json', 'w'))
for p in seg[::max(1, len(seg)//25)]: print('   ', round(p[0], 6), round(p[1], 6), round(km(st, p) * 1000), 'm du quai 10')
