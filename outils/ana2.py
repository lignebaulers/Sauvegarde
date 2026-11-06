import csv, json, collections, statistics as st
rows = []
for f in ('gps_2026-11-05_17.csv', 'gps_2026-11-05_18.csv', 'gps_2026-11-05_19.csv'):
    rows += [r for r in csv.DictReader(open(f), delimiter=';') if r['arret_n']]
by = collections.defaultdict(list)
for r in rows: by[(r['vehicule'], r['course'])].append((int(r['ts']), int(r['arret_n']), r['ligne']))
# temps de passage de chaque arrêt : premier instant où n dépasse q  (n = prochain arrêt)
trips = []
for k, L in by.items():
    L = sorted(set(L))
    if len(L) < 4: continue
    line = L[0][2]
    passt = {}  # q -> premier ts où n > q
    for ts, n, _ in L:
        for q in range(min(passt.keys(), default=0) if False else 0, 0): pass
    prev = None
    for ts, n, _ in L:
        if prev is not None and n > prev[1]:
            for q in range(prev[1], n):  # arrêts prev[1]..n-1 passés entre prev[0] et ts
                passt.setdefault(q, ts)
        prev = (ts, n)
    trips.append((line, L, passt))
# secondes par arrêt : par course (durée observée / arrêts franchis)
sp = collections.defaultdict(list)
for line, L, passt in trips:
    d = L[-1][0] - L[0][0]; n = L[-1][1] - L[0][1]
    if n >= 3 and d > 0: sp[line].append(d / n)
allv = [x for v in sp.values() for x in v]
print('courses suivies', len(trips), 'secondes par arrêt : médiane globale %.0f s, quartiles %.0f-%.0f' % (st.median(allv), *[sorted(allv)[int(len(allv)*q)] for q in (.25, .75)]))
med = {l: st.median(v) for l, v in sp.items() if len(v) >= 2}
print('lignes avec >= 2 courses', len(med))
print(sorted(((l, round(m), len(sp[l])) for l, m in med.items()), key=lambda x: x[1])[:6], '...', sorted(((l, round(m), len(sp[l])) for l, m in med.items()), key=lambda x: x[1])[-6:])
# précision de l'estimation « n arrêts × s/arrêt de la ligne » (valeur de la ligne calculée sans la course testée)
err = collections.defaultdict(list)
for i, (line, L, passt) in enumerate(trips):
    others = [x for j, (l2, L2, p2) in enumerate(trips) if l2 == line and j != i for x in [((L2[-1][0]-L2[0][0])/(L2[-1][1]-L2[0][1])) if L2[-1][1]-L2[0][1] >= 3 else None] if x]
    spl = st.median(others) if len(others) >= 1 else st.median(allv)
    for ts, n, _ in L:
        for q, tq in passt.items():
            k = q - n
            if k >= 0 and tq > ts and k <= 30:
                pred = (k + 0.5) * spl; real = tq - ts
                b = 'proche (0-3)' if k <= 3 else 'moyen (4-10)' if k <= 10 else 'loin (11-30)'
                err[b].append((pred - real) / 60)
for b in ('proche (0-3)', 'moyen (4-10)', 'loin (11-30)'):
    e = err[b]; ae = sorted(abs(x) for x in e)
    print('%s : %d cas, écart médian %.1f min, 80 %% des cas à moins de %.1f min, biais %.1f min' % (b, len(e), st.median(ae), ae[int(len(ae)*.8)], st.median(e)))
json.dump({l: round(m) for l, m in med.items()}, open('sec_par_arret.json', 'w'))
print('global', round(st.median(allv)))
