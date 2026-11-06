import csv, json, math, collections, statistics as st, datetime as dt, sys
sys.path.insert(0, 'tools'); import devbuild3 as DB
h, m, D = DB.load('r73/index.html')
A = {s[0]: s for s in json.load(open('tecdiag/tec_arrets.json'))['arrets']}
rows = []
for f in ('17', '18', '19', '20'):
    rows += list(csv.DictReader(open('gpsdata/gps_2026-11-05_%s.csv' % f), delimiter=';'))
for r in rows: r['t'] = int(r['ts']); r['p'] = (float(r['lat']), float(r['lon'])); r['n'] = int(r['arret_n']) if r['arret_n'] else None
def km(p, q): return math.hypot((q[1] - p[1]) * math.cos(math.radians(p[0])) * 111.32, (q[0] - p[0]) * 111.32)
hm = lambda t: dt.datetime.fromtimestamp(t).strftime('%H:%M')
by = collections.defaultdict(list)
for r in rows: by[(r['vehicule'], r['course'])].append(r)
for L in by.values(): L.sort(key=lambda r: r['t'])
# --- départs du terminus, version prudente
dep = []
for k, L in by.items():
    if L[0]['n'] != 1 or not L[0]['arret'] or L[0]['arret'] not in A: continue
    s1 = (A[L[0]['arret']][2], A[L[0]['arret']][3])
    i = next((i for i, r in enumerate(L) if r['n'] and r['n'] >= 2), None)
    if i is None or i == 0: continue
    a, b = L[i - 1], L[i]
    if km(a['p'], s1) > 0.15 or km(b['p'], s1) > 1.2 or b['t'] - a['t'] > 150: continue      # le bus était au 1er arrêt, puis juste parti
    hh, mm, ss = map(int, L[0]['depart'].split(':')); sched = dt.datetime(2026, 11, 5).timestamp() + hh * 3600 + mm * 60 + ss
    leave = b['t'] - km(b['p'], s1) / 20 * 3600          # temps pour faire le bout depuis l'arrêt à ~20 km/h
    leave = max(leave, a['t'])
    dep.append(((leave - sched) / 60, L[0]['ligne'], L[0]['depart'][:5], A[L[0]['arret']][1]))
d = sorted(x[0] for x in dep)
q = lambda p: d[int(p * (len(d) - 1))]
print('DÉPARTS FIABLES :', len(d), '| médiane %+.1f min | quartiles %+.1f / %+.1f | en avance > 1 min : %d | retard > 3 min : %d | retard > 5 min : %d' % (
    st.median(d), q(.25), q(.75), sum(x < -1 for x in d), sum(x > 3 for x in d), sum(x > 5 for x in d)))
print('   en avance :', [(round(x[0], 1),) + x[1:] for x in sorted(dep)[:5]])
print('   en retard :', [(round(x[0], 1),) + x[1:] for x in sorted(dep, key=lambda x: -x[0])[:5]])
dl = collections.defaultdict(list)
for x in dep: dl[x[1]].append(x[0])
print('   par ligne (>= 4 départs) :', sorted(((l, round(st.median(v), 1), len(v)) for l, v in dl.items() if len(v) >= 4), key=lambda z: -z[1])[:10])
# --- hors tracé : distance aux segments des parcours de la ligne (points tous les 25 m)
def dens(P, step=0.025):
    o = [P[0]]
    for a, b in zip(P, P[1:]):
        n = int(km(a, b) // step)
        for k in range(1, n + 1): t = k / (n + 1); o.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        o.append(b)
    return o
GR = {}
for ln, L in D['lines'].items():
    g = collections.defaultdict(list)
    for v in L['variants']:
        for p in dens(DB.dec(v['poly'])): g[(round(p[0] * 200), round(p[1] * 130))].append(p)
    GR[ln] = g
def dline(ln, p):
    g = GR[ln]; k = (round(p[0] * 200), round(p[1] * 130)); best = 9
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for q in g.get((k[0] + dx, k[1] + dy), []): best = min(best, km(p, q))
    return best
off = collections.defaultdict(list); tot = 0
for r in rows:
    if not r['n'] or r['n'] < 3 or r['ligne'] not in GR: continue
    tot += 1
    if dline(r['ligne'], r['p']) > 0.15: off[(r['ligne'], round(r['p'][0], 3), round(r['p'][1], 3))].append(r)
def nearest(p):
    return min((km(p, (s[2], s[3])), s[1]) for s in A.values() if abs(s[2] - p[0]) < 0.01 and abs(s[3] - p[1]) < 0.015)
zones = collections.defaultdict(list)
for (ln, a, b), L in off.items(): zones[(ln, round(a, 2), round(b, 2))] += L
oc = sorted(zones.items(), key=lambda kv: -len({x['course'] for x in kv[1]}))
print('HORS TRACÉ (> 150 m du parcours de la ligne, en service) : %d positions sur %d (%.1f %%)' % (sum(len(v) for v in off.values()), tot, 100 * sum(len(v) for v in off.values()) / tot))
for (ln, a, b), L in oc[:10]:
    nn = nearest(L[0]['p']); dd = max(dline(ln, x['p']) for x in L)
    print('   ligne %-4s %-42s %3d positions, %2d courses, jusqu\'à %4d m du tracé, %s→%s' % (ln, nn[1][:42], len(L), len({x['course'] for x in L}), dd * 1000, hm(min(x['t'] for x in L)), hm(max(x['t'] for x in L))))
# --- vitesses en roulant
sp = collections.defaultdict(list)
for L in by.values():
    for a, b in zip(L, L[1:]):
        dtt = b['t'] - a['t']
        if 30 <= dtt <= 180:
            v = km(a['p'], b['p']) / dtt * 3600
            if v > 3: sp[a['ligne']].append(v)
med = {l: st.median(v) for l, v in sp.items() if len(v) > 30}
print('VITESSE en roulant (médiane, vol d\'oiseau entre 2 positions) : %.0f km/h | plus lentes :' % st.median([x for v in sp.values() for x in v]),
      sorted(((l, round(v)) for l, v in med.items()), key=lambda x: x[1])[:6], '| plus rapides :', sorted(((l, round(v)) for l, v in med.items()), key=lambda x: -x[1])[:6])
# --- enchaînements : un même bus sur plusieurs lignes
ch = collections.defaultdict(list)
for r in sorted(rows, key=lambda r: r['t']):
    seq = ch[r['vehicule']]
    if not seq or seq[-1][0] != r['ligne'] or seq[-1][1] != r['course']: seq.append((r['ligne'], r['course'], r['depart'][:5]))
multi = {v: s for v, s in ch.items() if len({x[0] for x in s}) >= 2}
print('ENCHAÎNEMENTS : %d bus sur au moins 2 lignes différentes dans la soirée (sur %d)' % (len(multi), len(ch)))
dep_baulers = {'62', '63', '65', '66', '67', '69', '70', '71', '72', '73', '74', '75', '76', '77', 'W'}
ex = [(v, ' → '.join('%s (%s)' % (x[0], x[2]) for x in s)) for v, s in multi.items() if {x[0] for x in s} & dep_baulers]
for v, s in ex[:6]: print('   ', v.split('-')[0], ':', s)
# --- attentes en cours de route (pas au 1er arrêt)
mid = []
for L in by.values():
    i = 0
    while i < len(L):
        j = i
        while j + 1 < len(L) and km(L[i]['p'], L[j + 1]['p']) < 0.04: j += 1
        if L[j]['t'] - L[i]['t'] >= 300 and L[i]['n'] and L[i]['n'] > 2: mid.append((round((L[j]['t'] - L[i]['t']) / 60), L[i]['ligne'], L[i]['depart'][:5], nearest(L[i]['p'])[1], L[i]['n']))
        i = j + 1
print('ARRÊTS DE 5 MIN OU PLUS EN COURS DE ROUTE :', sorted(mid, reverse=True)[:8])
