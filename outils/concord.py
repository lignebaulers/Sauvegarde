"""Concordance GPS réel  ↔  tracés de l'appli (r73 / v27).
Pour chaque course GPS d'une ligne de l'appli :
  1) trouve la variante (heure de départ + liste d'arrêts TEC + géométrie)
  2) vérifie que le prochain arrêt annoncé par TEC (n, id) = notre arrêt n° n
  3) mesure la distance de chaque position (en service) à notre tracé, et le sens de marche
Sortie : résumé + concord.json (détails pour les cartes)."""
import csv, json, math, collections, statistics as st, datetime as dt, sys, glob
S = '/tmp/claude-0/-home-claude/090c89ab-6469-5ab1-bebb-ae2242a06172/scratchpad'
sys.path.insert(0, S + '/tools'); import devbuild3 as DB
h, m, D = DB.load(S + '/r73/index.html')
A = {s[0]: s for s in json.load(open(S + '/tecdiag/tec_arrets.json'))['arrets']}
TODAY = '2026-11-05'
rows, seen = [], set()
for f in sorted(glob.glob(S + '/gpsdata/gps_2026-11-05_*.csv')):
    for r in csv.DictReader(open(f), delimiter=';'):
        k = (r['ts'], r['vehicule'], r['course'])
        if k in seen: continue
        seen.add(k); rows.append(r)
for r in rows:
    r['t'] = int(r['ts']); r['p'] = (float(r['lat']), float(r['lon']))
    r['n'] = int(r['arret_n']) if r['arret_n'] else None
    r['cap'] = float(r['cap']) if r['cap'] not in ('', None) else None
    r['v'] = float(r['vitesse']) if r['vitesse'] not in ('', None) else 0.0
hm = lambda t: dt.datetime.fromtimestamp(t).strftime('%H:%M')
COS = math.cos(math.radians(50.65))
def xy(lat, lon): return (lon * 111.32 * COS, lat * 111.32)
def km(p, q):
    a, b = xy(*p), xy(*q); return math.hypot(a[0] - b[0], a[1] - b[1])
def adiff(a, b): d = abs(a - b) % 360; return min(d, 360 - d)

class Poly:
    C = 0.1
    def __init__(self, pts):
        self.pts = pts; P = [xy(*p) for p in pts]; self.segs = []; cum = 0
        for (x1, y1), (x2, y2) in zip(P, P[1:]):
            L = math.hypot(x2 - x1, y2 - y1)
            if L == 0: continue
            self.segs.append((x1, y1, x2, y2, cum, L, math.degrees(math.atan2(x2 - x1, y2 - y1)) % 360)); cum += L
        self.total = cum; self.G = collections.defaultdict(list)
        for i, (x1, y1, x2, y2, c, L, b) in enumerate(self.segs):
            for gx in range(math.floor(min(x1, x2) / self.C), math.floor(max(x1, x2) / self.C) + 1):
                for gy in range(math.floor(min(y1, y2) / self.C), math.floor(max(y1, y2) / self.C) + 1):
                    self.G[(gx, gy)].append(i)
    def near(self, p, R=0.6):
        """-> (distance min km, position le long km, [(d, cap du segment) pour d <= 40 m])"""
        x, y = xy(*p); k = math.ceil(R / self.C); gx, gy = math.floor(x / self.C), math.floor(y / self.C)
        cand = set()
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1): cand.update(self.G.get((gx + dx, gy + dy), ()))
        best, pos, close = 9.0, None, []
        for i in cand:
            x1, y1, x2, y2, c, L, b = self.segs[i]
            t = max(0, min(1, ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / (L * L)))
            d = math.hypot(x - (x1 + t * (x2 - x1)), y - (y1 + t * (y2 - y1)))
            if d < best: best, pos = d, c + t * L
            if d <= 0.04: close.append((d, b))
        return best, pos, close

VAR = {}          # (ligne, i) -> dict
for ln, L in D['lines'].items():
    for v in L['variants']:
        key = 'L%s_%02d' % (ln, int(v['i']))
        devs = [x for x in D['dev'].get(key, []) if any(w[0] <= TODAY and (w[1] is None or TODAY <= w[1]) for w in x.get('wins', []))]
        VAR[(ln, v['i'])] = dict(key=key, v=v, poly=Poly(DB.dec(v['poly'])), times=set(v['times']), stops=v['stops'],
                                 devs=[(x['file'], Poly(DB.dec(x['poly']))) for x in devs if x.get('poly')])

by = collections.defaultdict(list)
for r in rows:
    if r['ligne'] in D['lines']: by[(r['vehicule'], r['course'])].append(r)
for L in by.values(): L.sort(key=lambda r: r['t'])

def stopmatch(V, L):
    pairs = {(r['n'], r['arret']) for r in L if r['n'] is not None and r['arret'] in A}
    ok, bad = 0, []
    for n, sid in sorted(pairs):
        q = (A[sid][2], A[sid][3])
        if 0 <= n < len(V['stops']) and km(q, (V['stops'][n][1], V['stops'][n][2])) < 0.06: ok += 1      # n TEC = index 0-based
        else: bad.append((n, sid))
    return ok, len(pairs), bad

def classify(V, r):
    d, pos, close = V['poly'].near(r['p'])
    out = dict(d=d, pos=pos, tot=V['poly'].total)
    for f, P in V['devs']:
        dd = P.near(r['p'])[0]
        if dd < out.get('ddev', 9): out['ddev'], out['devf'] = dd, f
    if close and r['cap'] is not None and r['v'] > 15:
        out['sens'] = 'ok' if any(adiff(b, r['cap']) <= 60 for _, b in close) else ('contre' if any(adiff(b, r['cap']) >= 120 for _, b in close) else 'travers')
    return out

trips, pts = [], []
for (veh, crs), L in by.items():
    ln = L[0]['ligne']; dep = L[0]['depart'][:5]
    svc = [r for r in L if r['n'] is not None and r['n'] >= 1]      # a quitté le 1er arrêt
    if not svc: continue
    cands = []
    for (l2, i), V in VAR.items():
        if l2 != ln: continue
        ok, tot, bad = stopmatch(V, L)
        sample = svc[::max(1, len(svc) // 25)]
        geo = sum(V['poly'].near(r['p'])[0] <= 0.05 for r in sample) / len(sample)
        cands.append((2 * (ok / tot if tot else 0) + geo + (0.3 if dep in V['times'] else 0), i, ok, tot, bad, geo, dep in V['times']))
    cands.sort(reverse=True); sc, i, ok, tot, bad, geo, tm = cands[0]
    V = VAR[(ln, i)]
    tr = dict(veh=veh, crs=crs, ln=ln, dep=dep, sens=L[0]['sens'], var=V['key'], dir=V['v']['dir'], timeok=tm, stok=ok, sttot=tot, stbad=bad, geo=geo,
              second=(cands[1][1], round(cands[1][0], 2)) if len(cands) > 1 else None, score=round(sc, 2), n=len(L))
    trips.append(tr)
    last = len(V['stops']) - 1
    for r in svc:
        c = classify(V, r)
        endzone = c['pos'] is not None and c['pos'] >= c['tot'] - 0.05 and r['n'] >= last
        pts.append(dict(var=V['key'], ln=ln, crs=crs, veh=veh, t=r['t'], p=r['p'], n=r['n'], cap=r['cap'], v=r['v'], arret=r['arret'], end=endzone, **c))

# ---------------- RÉSUMÉ
print('PÉRIODE %s → %s | %d positions de lignes de l\'appli | %d courses | %d lignes' % (
    hm(min(r['t'] for r in rows)), hm(max(r['t'] for r in rows)), sum(len(L) for L in by.values()), len(trips), len({t['ln'] for t in trips})))
print('Variante retrouvée par l\'heure de départ :', sum(t['timeok'] for t in trips), '/', len(trips))
full = [t for t in trips if t['sttot'] and t['stok'] == t['sttot']]
print('Arrêts : courses dont TOUS les prochains arrêts annoncés par TEC = nos arrêts (même n°) :', len(full), '/', sum(1 for t in trips if t['sttot']))
dirs = collections.Counter((t['sens'], t['dir']) for t in trips); print('sens GTFS ↔ dir appli :', dict(dirs))
ins = [p for p in pts if not p['end']]
ds = sorted(p['d'] for p in ins)
q = lambda f: ds[int(f * (len(ds) - 1))] * 1000
print('POSITIONS EN SERVICE : %d | distance à notre tracé : médiane %.0f m, 90 %% %.0f m, 95 %% %.0f m, 99 %% %.0f m' % (len(ds), q(.5), q(.9), q(.95), q(.99)))
for th in (0.02, 0.035, 0.05, 0.08, 0.15):
    print('   <= %3d m : %.1f %%' % (th * 1000, 100 * sum(x <= th for x in ds) / len(ds)))
sens = collections.Counter(p.get('sens') for p in ins if p['d'] <= 0.035)
print('SENS (bus en mouvement, sur le tracé) :', dict(sens))
off = [p for p in ins if p['d'] > 0.035]
dev_ok = [p for p in off if p.get('ddev', 9) <= 0.035]
print('Hors tracé > 35 m : %d positions, dont %d sur une déviation active' % (len(off), len(dev_ok)))
json.dump(dict(trips=trips, pts=pts), open(S + '/gpsdata/concord.json', 'w'), default=str)
