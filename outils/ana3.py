import csv, json, collections, statistics as st, math
A = {s[0]: s for s in json.load(open('../tecdiag/tec_arrets.json'))['arrets']}
def km(a, b, c, d): return math.hypot((d - b) * math.cos(math.radians(a)) * 111.32, (c - a) * 111.32)
rows = []
for f in ('gps_2026-11-05_17.csv', 'gps_2026-11-05_18.csv', 'gps_2026-11-05_19.csv'):
    rows += [r for r in csv.DictReader(open(f), delimiter=';') if r['arret_n'] and r['arret'] in A]
by = collections.defaultdict(list)
for r in rows: by[(r['vehicule'], r['course'])].append((int(r['ts']), int(r['arret_n']), r['ligne'], float(r['lat']), float(r['lon']), r['arret']))
trips = []
for k, L in by.items():
    L = sorted(set(L))
    if len(L) < 4: continue
    passt = {}; stopc = {}
    prev = None
    for ts, n, line, la, lo, ar in L:
        stopc[n] = (A[ar][2], A[ar][3])
        if prev is not None and n > prev[1]:
            for q in range(prev[1], n): passt.setdefault(q, ts)
        prev = (ts, n)
    trips.append((L[0][2], L, passt, stopc))
# vitesses de référence par ligne : s/arrêt et s/km (vol d'oiseau), sans la course testée
def refs(line, skip):
    a, b = [], []
    for j, (l2, L2, p2, c2) in enumerate(trips):
        if l2 != line or j == skip: continue
        d = L2[-1][0] - L2[0][0]; n = L2[-1][1] - L2[0][1]
        dist = sum(km(x[3], x[4], y[3], y[4]) for x, y in zip(L2, L2[1:]))
        if n >= 3 and d > 0: a.append(d / n)
        if dist > 1 and d > 0: b.append(d / dist)
    return (st.median(a) if a else 96), (st.median(b) if b else None)
gb = []
for j, (l2, L2, p2, c2) in enumerate(trips):
    d = L2[-1][0] - L2[0][0]; dist = sum(km(x[3], x[4], y[3], y[4]) for x, y in zip(L2, L2[1:]))
    if dist > 1 and d > 0: gb.append(d / dist)
GSK = st.median(gb); print('global s/km (trace GPS) %.0f soit %.1f km/h' % (GSK, 3600 / GSK))
E = collections.defaultdict(lambda: collections.defaultdict(list))
for i, (line, L, passt, stopc) in enumerate(trips):
    spa, spk = refs(line, i); spk = spk or GSK
    for ts, n, _, la, lo, ar in L:
        for q, tq in passt.items():
            k = q - n
            if k < 0 or tq <= ts or k > 30 or q not in stopc: continue
            real = tq - ts; dk = km(la, lo, *stopc[q])
            b = 'proche (0-3)' if k <= 3 else 'moyen (4-10)' if k <= 10 else 'loin (11-30)'
            p1 = (k + 0.5) * spa; p2 = dk * 1.3 * spk; p3 = (p1 + p2) / 2
            for nm, p in (('arrêts', p1), ('distance', p2), ('mélange', p3)): E[b][nm].append((p - real) / 60)
for b in ('proche (0-3)', 'moyen (4-10)', 'loin (11-30)'):
    for nm in ('arrêts', 'distance', 'mélange'):
        e = E[b][nm]; ae = sorted(abs(x) for x in e)
        print('%-13s %-9s n=%5d  écart médian %4.1f min  80%% < %4.1f min  biais %+.1f' % (b, nm, len(e), st.median(ae), ae[int(len(ae) * .8)], st.median(e)))
