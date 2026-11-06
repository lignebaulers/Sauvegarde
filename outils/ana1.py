import csv, json, math, collections, statistics as st
A = {s[0]: s for s in json.load(open('../tecdiag/tec_arrets.json'))['arrets']}
rows = []
for f in ('gps_2026-11-05_17.csv', 'gps_2026-11-05_18.csv', 'gps_2026-11-05_19.csv'):
    rows += list(csv.DictReader(open(f), delimiter=';'))
print('points', len(rows))
print('etat', collections.Counter(r['etat'] for r in rows))
print('arret vide', sum(1 for r in rows if not r['arret']), 'arret inconnu', sum(1 for r in rows if r['arret'] and r['arret'] not in A))
def km(a, b, c, d): return math.hypot((d - b) * math.cos(math.radians(a)) * 111.32, (c - a) * 111.32)
by = collections.defaultdict(list)
for r in rows:
    by[(r['vehicule'], r['course'])].append(r)
appro = eloigne = 0; chg_old = []; chg_new = []; at_dist = []
for k, L in by.items():
    L.sort(key=lambda r: int(r['ts']))
    for a, b in zip(L, L[1:]):
        if a['arret'] not in A or b['arret'] not in A or not a['arret_n'] or not b['arret_n']: continue
        sa = A[a['arret']]; sb = A[b['arret']]
        da = km(float(a['lat']), float(a['lon']), sa[2], sa[3]); db = km(float(b['lat']), float(b['lon']), sa[2], sa[3])
        if a['arret_n'] == b['arret_n'] and abs(da - db) > 0.03:
            if db < da: appro += 1
            else: eloigne += 1
        if b['arret_n'] != a['arret_n'] and int(b['arret_n']) == int(a['arret_n']) + 1:
            # au moment du changement : distance du bus (point b) à l'ancien arrêt et au nouvel arrêt
            chg_old.append(km(float(b['lat']), float(b['lon']), sa[2], sa[3])); chg_new.append(km(float(b['lat']), float(b['lon']), sb[2], sb[3]))
    for r in L:
        if r['arret'] in A: at_dist.append(km(float(r['lat']), float(r['lon']), A[r['arret']][2], A[r['arret']][3]))
print('même n° d\'arrêt entre 2 prises : le bus se rapproche de l\'arrêt indiqué', appro, 'fois, s\'en éloigne', eloigne, 'fois')
print('au passage n -> n+1 (bus juste après) : distance médiane à l\'ancien arrêt %.3f km, au nouveau %.3f km (n=%d)' % (st.median(chg_old), st.median(chg_new), len(chg_old)))
print('distance bus -> arrêt indiqué : médiane %.3f km, 90e centile %.3f km' % (st.median(at_dist), sorted(at_dist)[int(len(at_dist) * .9)]))
