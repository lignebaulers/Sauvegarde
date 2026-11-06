"""Trajets à vide visibles dans le GPS du TEC (lignes de Baulers) : le bus est publié dès que sa course lui est attribuée,
souvent pendant qu'il roule encore vers son 1er arrêt (sortie de dépôt, point d'attente → quai, fin d'une autre ligne → départ).
Usage : python3 hlp.py <dossier csv> [...]   →  hlp.json + résumé"""
import csv, glob, json, math, re, sys, collections, datetime as dt
S = '/tmp/claude-0/-home-claude/090c89ab-6469-5ab1-bebb-ae2242a06172/scratchpad/'
sys.path.insert(0, S + 'tools'); import devbuild3 as DB
h, m, D = DB.load(S + 'r73/index.html')
A = json.load(open(S + 'tecdiag/tec_arrets.json'))['arrets']
BAU = lambda l: l == 'W' or l in ('E4', 'E7') or re.fullmatch(r'6\d|7\d', l)
DEPOT = (50.6125, 4.3360)
COS = math.cos(math.radians(50.65))
def xy(p): return (p[1] * 111.32 * COS, p[0] * 111.32)
def km(p, q): a, b = xy(p), xy(q); return math.hypot(a[0] - b[0], a[1] - b[1])
def dpoly(p, P):
    x, y = xy(p); best = 9
    for (x1, y1), (x2, y2) in zip(P, P[1:]):
        L2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
        t = 0 if L2 == 0 else max(0, min(1, ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / L2))
        best = min(best, math.hypot(x - (x1 + t * (x2 - x1)), y - (y1 + t * (y2 - y1))))
    return best
def lieu(p):
    c = [(km(p, (s[2], s[3])), s[1]) for s in A if abs(s[2] - p[0]) < 0.01 and abs(s[3] - p[1]) < 0.015]
    return min(c) if c else (9, '?')
VAR = collections.defaultdict(list)
for ln, L in D['lines'].items():
    for v in L['variants']: VAR[ln].append(v)
MOVES = [(mv['file'], [xy(p) for p in DB.dec(mv['poly'])]) for mv in D['moves'] if mv.get('poly')]
ALLP = [[xy(p) for p in DB.dec(v['poly'])] for vs in VAR.values() for v in vs]
rows = []
for d in sys.argv[1:]:
    for f in sorted(glob.glob(d + '/gps_*.csv')):
        day = re.search(r'gps_(\d{4}-\d\d-\d\d)', f).group(1)
        for r in csv.DictReader(open(f), delimiter=';'):
            if r['ligne'] in VAR and r['route'].startswith('B'): r['day'] = day; rows.append(r)
start = collections.defaultdict(lambda: 9e12)
for r in rows: start[r['day']] = min(start[r['day']], int(r['ts']))
by = collections.defaultdict(list)
for r in rows: by[(r['day'], r['vehicule'], r['course'])].append(r)
OUT = []
for (day, veh, crs), L in by.items():
    L.sort(key=lambda r: int(r['ts'])); ln = L[0]['ligne']
    if int(L[0]['ts']) < start[day] + 90: continue                       # course déjà en cours au début de l'enregistrement
    hh, mm = map(int, L[0]['depart'][:5].split(':')); sd = dt.datetime.fromisoformat(day).timestamp() + hh * 3600 + mm * 60
    if int(L[0]['ts']) > sd + 300: continue                              # apparue après son départ : pas d'approche visible
    pts = [(int(r['ts']), (float(r['lat']), float(r['lon'])), float(r['vitesse'] or 0)) for r in L]
    # variante : heure + sens, puis celle dont le 1er arrêt est le plus proche du bus 2 min après l'heure de départ
    cand = [v for v in VAR[ln] if L[0]['depart'][:5] in v['times'] and str(v['dir']) == L[0]['sens']] or [v for v in VAR[ln] if str(v['dir']) == L[0]['sens']] or VAR[ln]
    ref = min(pts, key=lambda x: abs(x[0] - sd - 120))[1]
    v = min(cand, key=lambda v: km(ref, (v['stops'][0][1], v['stops'][0][2])) if True else 0)
    s0 = (v['stops'][0][1], v['stops'][0][2])
    app = []
    for x in pts:
        if km(x[1], s0) < 0.06: break
        app.append(x)
    if not app or km(app[0][1], s0) < 0.3: continue
    mov = sum(km(a[1], b[1]) for a, b in zip(app, app[1:]))
    if mov < 0.3: continue
    o = app[0][1]
    near_moves = []
    for f, P in MOVES:
        ds = [dpoly(x[1], P) for x in app]
        if sum(d < 0.04 for d in ds) >= max(2, 0.6 * len(ds)): near_moves.append((f, round(sum(d < 0.04 for d in ds) / len(ds), 2)))
    on_line = sum(min(dpoly(x[1], P) for P in ALLP if True) < 0.035 for x in app[::max(1, len(app) // 8)]) / len(app[::max(1, len(app) // 8)])
    OUT.append(dict(day=day, ln=ln, bau=bool(BAU(ln)), dep=L[0]['depart'][:5], var='L%s_%02d' % (ln, int(v['i'])), vers=v['stops'][0][0],
                    depuis=lieu(o)[1], depuis_m=round(lieu(o)[0] * 1000), depot=km(o, DEPOT) < 0.5, vu=dt.datetime.fromtimestamp(app[0][0]).strftime('%H:%M'),
                    km_vol=round(km(o, s0), 2), km_vus=round(mov, 2), n=len(app), sur_lignes=round(on_line, 2), moves=near_moves,
                    pts=[[round(x[1][0], 6), round(x[1][1], 6), x[0], x[2]] for x in app]))
json.dump(OUT, open(S + 'gpsdata/hlp.json', 'w'), ensure_ascii=False)
print('%d approches à vide visibles (≥ 300 m roulés) dont %d sur nos lignes, %d parties du dépôt de Baulers' % (len(OUT), sum(o['bau'] for o in OUT), sum(o['depot'] for o in OUT)))
for o in sorted([o for o in OUT if o['bau'] or o['depot']], key=lambda o: (o['day'], o['vu'])):
    print('%s %s %-3s %s  vu %s à %.1f km (à vol d\'oiseau), %.1f km roulés vus, %2d pos | depuis : %s%s (%d m) → %s | sur tracés de lignes %d %% | trajets appli : %s' % (
        o['day'][5:], 'DÉPÔT' if o['depot'] else '     ', o['ln'], o['dep'], o['vu'], o['km_vol'], o['km_vus'], o['n'], o['depuis'][:34], '', o['depuis_m'], o['vers'][:34], o['sur_lignes'] * 100, o['moves'] or '-'))
