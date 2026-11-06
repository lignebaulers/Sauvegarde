"""Bouts « à vide » visibles : course déjà attribuée, bus pas encore à son 1er arrêt, qui roule hors de son tracé."""
import csv, glob, json, math, sys, collections, datetime as dt
S = '/tmp/claude-0/-home-claude/090c89ab-6469-5ab1-bebb-ae2242a06172/scratchpad/'
sys.path.insert(0, S + 'tools'); import devbuild3 as DB
h, m, D = DB.load(S + 'r73/index.html')
J = json.load(open(S + 'gpsdata/concord.json')); TR = {t['crs'] + t['veh']: t for t in J['trips']}
VV = {('L%s_%02d' % (ln, int(v['i']))): v for ln, L in D['lines'].items() for v in L['variants']}
COS = math.cos(math.radians(50.65)); km = lambda p, q: math.hypot((p[1]-q[1])*111.32*COS, (p[0]-q[0])*111.32)
hm = lambda t: dt.datetime.fromtimestamp(t).strftime('%H:%M')
DEPOT = (50.6125, 4.3360)
rows = []
for f in sorted(glob.glob(S + 'gpsdata/gps_2026-11-05_*.csv')): rows += list(csv.DictReader(open(f), delimiter=';'))
T0 = min(int(r['ts']) for r in rows)
by = collections.defaultdict(list)
for r in rows: by[(r['vehicule'], r['course'])].append(r)
out = []
for (veh, crs), L in by.items():
    t = TR.get(crs + veh)
    if not t: continue
    L.sort(key=lambda r: int(r['ts'])); st = VV[t['var']]['stops']; s0 = (st[0][1], st[0][2])
    hh, mm = map(int, t['dep'].split(':')); sd = dt.datetime(2026, 11, 5, hh, mm).timestamp()
    if int(L[0]['ts']) < T0 + 120 or int(L[0]['ts']) > sd + 600: continue      # course apparue pendant l'enregistrement, avant (ou peu après) son heure
    pre = []
    for r in L:
        p = (float(r['lat']), float(r['lon']))
        if km(p, s0) < 0.06: break
        pre.append((int(r['ts']), p, float(r['vitesse'] or 0)))
    mov = [x for x in pre if x[2] > 0]
    if len(mov) < 2: continue
    span = km(pre[0][1], s0)
    if span < 0.4: continue
    out.append(dict(ln=t['ln'], var=t['var'], dep=t['dep'], debut=hm(pre[0][0]), n=len(pre), depuis_km=round(span, 1), depot=km(pre[0][1], DEPOT) < 0.4,
                    pts=[x[1] for x in pre], vers=st[0][0]))
json.dump(out, open(S + 'gpsdata/approche.json', 'w'), ensure_ascii=False)
print(len(out), 'courses vues en train de rouler vers leur 1er arrêt (≥ 400 m)', '| dont parties du dépôt de Baulers :', sum(o['depot'] for o in out))
for o in sorted(out, key=lambda o: -o['depuis_km'])[:25]:
    print('  %-5s %-8s départ %s, vu dès %s à %4.1f km de « %s »%s, %d positions' % (o['ln'], o['var'], o['dep'], o['debut'], o['depuis_km'], o['vers'][:38], ' (DÉPÔT)' if o['depot'] else '', o['n']))
