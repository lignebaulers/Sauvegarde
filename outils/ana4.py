import csv, json, math, collections, statistics as st, datetime as dt, sys
sys.path.insert(0, 'tools'); import devbuild3 as DB
sys.path.insert(0, 'ver'); from load import dec
h, m, D = DB.load('r73/index.html')
A = {s[0]: s for s in json.load(open('tecdiag/tec_arrets.json'))['arrets']}
rows = []
for f in ('17', '18', '19', '20'):
    rows += list(csv.DictReader(open('gpsdata/gps_2026-11-05_%s.csv' % f), delimiter=';'))
for r in rows: r['t'] = int(r['ts']); r['p'] = (float(r['lat']), float(r['lon'])); r['n'] = int(r['arret_n']) if r['arret_n'] else None
def km(p, q): return math.hypot((q[1] - p[1]) * math.cos(math.radians(p[0])) * 111.32, (q[0] - p[0]) * 111.32)
hm = lambda t: dt.datetime.fromtimestamp(t).strftime('%H:%M')
T0, T1 = min(r['t'] for r in rows), max(r['t'] for r in rows)
print('PÉRIODE', hm(T0), '→', hm(T1), '|', len(rows), 'positions |', len({r['vehicule'] for r in rows}), 'véhicules |', len({r['course'] for r in rows}), 'courses |', len({r['ligne'] for r in rows}), 'lignes')
# 1) bus en service par tranche de 30 min
fl = collections.defaultdict(set)
for r in rows: fl[(r['t'] // 1800) * 1800].add(r['vehicule'])
print('BUS EN SERVICE (par 30 min) :', ' | '.join('%s %d' % (hm(k), len(v)) for k, v in sorted(fl.items())))
# 2) ponctualité au départ du terminus : 1er instant où le bus a quitté son 1er arrêt (prochain arrêt >= 2)
by = collections.defaultdict(list)
for r in rows: by[(r['vehicule'], r['course'])].append(r)
dep = []
for k, L in by.items():
    L.sort(key=lambda r: r['t'])
    if L[0]['n'] != 1: continue
    lv = next((r for r in L if r['n'] and r['n'] >= 2), None)
    if not lv: continue
    hh, mm, ss = map(int, L[0]['depart'].split(':')); sched = dt.datetime(2026, 11, 5).timestamp() + hh * 3600 + mm * 60 + ss
    prev = max((r['t'] for r in L if r['n'] == 1 and r['t'] < lv['t']), default=lv['t'])
    dep.append((L[0]['ligne'], L[0]['depart'][:5], (prev + lv['t']) / 2 - sched, A.get(L[0]['arret'], [0, '?'])[1] if L[0]['arret'] else '?'))
d = [x[2] / 60 for x in dep]
print('DÉPARTS DU TERMINUS observés :', len(d), '| médiane %+.1f min | partis en avance (> 1 min) : %d (%.0f %%) | en retard > 3 min : %d (%.0f %%)' % (
    st.median(d), sum(x < -1 for x in d), 100 * sum(x < -1 for x in d) / len(d), sum(x > 3 for x in d), 100 * sum(x > 3 for x in d) / len(d)))
print('   les plus en avance :', sorted(dep, key=lambda x: x[2])[:4])
print('   les plus en retard :', sorted(dep, key=lambda x: -x[2])[:4])
# 3) attentes de 5 min ou plus au même endroit (moins de 40 m de déplacement)
stay = []
for k, L in by.items():
    L.sort(key=lambda r: r['t']); i = 0
    while i < len(L):
        j = i
        while j + 1 < len(L) and km(L[i]['p'], L[j + 1]['p']) < 0.04: j += 1
        if L[j]['t'] - L[i]['t'] >= 300: stay.append((L[i]['p'], L[j]['t'] - L[i]['t'], L[i]['ligne'], L[i]['n']))
        i = j + 1
spots = collections.defaultdict(list)
for p, dur, ln, n in stay: spots[(round(p[0], 3), round(p[1], 3))].append((dur, ln, n))
def nearest(p):
    best = min((km(p, (s[2], s[3])), s[1]) for s in A.values() if abs(s[2] - p[0]) < 0.01 and abs(s[3] - p[1]) < 0.015) if True else None
    return best
top = sorted(spots.items(), key=lambda kv: -sum(x[0] for x in kv[1]))[:8]
print('ATTENTES >= 5 min :', len(stay), 'fois. Endroits principaux :')
for (a, b), L in top:
    nn = nearest((a, b)); print('   %-45s %2d attentes, %3d min au total, médiane %d min | lignes %s | au début de course : %d' % (nn[1][:45] + ' (%d m)' % (nn[0] * 1000), len(L), sum(x[0] for x in L) / 60, st.median(x[0] for x in L) / 60, ','.join(sorted({x[1] for x in L}))[:30], sum(1 for x in L if x[2] == 1)))
mid = [x for x in stay if x[3] and x[3] > 2]
print('   attentes de 5 min ou plus EN COURS DE ROUTE (pas au départ) :', len(mid))
# 4) bus qui se suivent de près (même ligne, même sens, moins de 500 m, même minute)
grp = collections.defaultdict(list)
for r in rows:
    if r['n'] and r['n'] > 2: grp[(r['t'] // 60, r['ligne'], r['sens'])].append(r)
pairs = set()
for k, L in grp.items():
    for i in range(len(L)):
        for j in range(i + 1, len(L)):
            if L[i]['vehicule'] != L[j]['vehicule'] and km(L[i]['p'], L[j]['p']) < 0.5:
                pairs.add((k[1], tuple(sorted((L[i]['course'], L[j]['course'])))))
pc = collections.Counter(x[0] for x in pairs)
print('BUS EN PELOTON (même ligne, même sens, < 500 m) :', len(pairs), 'paires |', pc.most_common(6))
# 5) hors du tracé de leur ligne (en service, plus de 200 m de tout parcours de la ligne)
PL = {}
for ln, L in D['lines'].items():
    pts = [p for v in L['variants'] for p in DB.dec(v['poly'])[::2]]
    PL[ln] = pts
off = collections.defaultdict(list)
for r in rows:
    if not r['n'] or r['n'] < 3 or r['ligne'] not in PL: continue
    P = PL[r['ligne']]
    if min(km(r['p'], q) for q in P if abs(q[0] - r['p'][0]) < 0.01 and abs(q[1] - r['p'][1]) < 0.015) if any(abs(q[0] - r['p'][0]) < 0.01 and abs(q[1] - r['p'][1]) < 0.015 for q in P) else 99 > 0.2:
        off[(r['ligne'], round(r['p'][0], 2), round(r['p'][1], 2))].append(r)
oc = sorted(off.items(), key=lambda kv: -len(kv[1]))
print('HORS TRACÉ (> 200 m de tous les parcours de la ligne, en service) :', sum(len(v) for v in off.values()), 'positions,', len(oc), 'zones')
for (ln, a, b), L in oc[:8]:
    nn = nearest(L[0]['p']); print('   ligne %-4s près de %-40s %3d positions, %d courses, %s→%s' % (ln, nn[1][:40], len(L), len({x['course'] for x in L}), hm(min(x['t'] for x in L)), hm(max(x['t'] for x in L))))
# 6) vitesses moyennes (entre deux positions à 30–180 s d'intervalle, en roulant)
sp = collections.defaultdict(list)
for k, L in by.items():
    L.sort(key=lambda r: r['t'])
    for a, b in zip(L, L[1:]):
        dtt = b['t'] - a['t']
        if 30 <= dtt <= 180: sp[a['ligne']].append(km(a['p'], b['p']) / dtt * 3600)
allsp = [x for v in sp.values() for x in v]
med = {l: st.median(v) for l, v in sp.items() if len(v) > 30}
print('VITESSE moyenne (vol d\'oiseau, arrêts compris) : %.0f km/h | plus lentes :' % st.mean(allsp), sorted(((l, round(v)) for l, v in med.items()), key=lambda x: x[1])[:5], '| plus rapides :', sorted(((l, round(v)) for l, v in med.items()), key=lambda x: -x[1])[:5])
# 7) fraîcheur GPS : écart entre deux positions successives d'un même bus
gaps = []
for k, L in by.items():
    L.sort(key=lambda r: r['t']); gaps += [b['t'] - a['t'] for a, b in zip(L, L[1:])]
print('GPS : intervalle médian entre 2 positions d\'un bus %d s ; trous de plus de 5 min : %d (%.1f %%)' % (st.median(gaps), sum(g > 300 for g in gaps), 100 * sum(g > 300 for g in gaps) / len(gaps)))
