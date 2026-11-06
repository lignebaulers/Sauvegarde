"""Lignes de Baulers : départs et arrivées en gare (quai réellement utilisé + chemin d'entrée / de sortie) comparés à nos tracés.
Usage : python3 gares.py [fichiers csv...]   (défaut : tous les gps_*.csv du dossier gpsdata)
Sortie : résumé texte + gares.json"""
import csv, json, math, re, sys, glob, collections, datetime as dt
S = '/tmp/claude-0/-home-claude/090c89ab-6469-5ab1-bebb-ae2242a06172/scratchpad/'
sys.path.insert(0, S + 'tools'); import devbuild3 as DB
h, m, D = DB.load(S + 'r73/index.html')
A = json.load(open(S + 'tecdiag/tec_arrets.json'))['arrets']
BAU = lambda l: l == 'W' or l in ('E4', 'E7') or re.fullmatch(r'6\d|7\d', l)
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
def quai(p):
    """arrêt TEC le plus proche (nom), et sa distance"""
    c = [(km(p, (s[2], s[3])), s[1]) for s in A if abs(s[2] - p[0]) < 0.003 and abs(s[3] - p[1]) < 0.005]
    return min(c) if c else (9, '?')
def gare(n): return re.sub(r'\s*-\s*Quai.*|\s*\(.*\)$', '', n)
def sched(day, dep):
    hh, mm = map(int, dep.split(':')[:2]); return dt.datetime.fromisoformat(day).timestamp() + hh * 3600 + mm * 60
VV = {}
for ln, L in D['lines'].items():
    if BAU(ln):
        for v in L['variants']:
            P = [xy(p) for p in DB.dec(v['poly'])]; VV[(ln, v['i'])] = dict(key='L%s_%02d' % (ln, int(v['i'])), v=v, P=P, times=set(v['times']))
files = sys.argv[1:] or sorted(glob.glob(S + 'gpsdata/gps_*.csv'))
rows = []
for f in files:
    day = re.search(r'gps_(\d{4}-\d\d-\d\d)', f).group(1)
    for r in csv.DictReader(open(f), delimiter=';'):
        if BAU(r['ligne']): r['day'] = day; rows.append(r)
by = collections.defaultdict(list)
for r in rows: by[(r['day'], r['vehicule'], r['course'])].append(r)
def variant(ln, L):
    """variante de la course : heure de départ + arrêts annoncés par TEC (n 0-based)"""
    best = None
    for (l2, i), V in VV.items():
        if l2 != ln: continue
        sc = (L[0]['depart'][:5] in V['times'], str(V['v']['dir']) == L[0]['sens'])
        geo = sum(min(1, dpoly((float(r['lat']), float(r['lon'])), V['P'][::3]) < 0.05) for r in L[::max(1, len(L) // 12)])
        k = (sc[0] + sc[1], geo)
        if best is None or k > best[0]: best = (k, V)
    return best[1]
OUT = []
for (day, veh, crs), L in by.items():
    L.sort(key=lambda r: int(r['ts'])); ln = L[0]['ligne']; V = variant(ln, L); st = V['v']['stops']
    for r in L: r['p'] = (float(r['lat']), float(r['lon'])); r['t'] = int(r['ts']); r['v0'] = float(r['vitesse'] or 0) == 0; r['n'] = int(r['arret_n']) if r['arret_n'] != '' else -1
    s0 = sched(day, L[0]['depart']); first = (st[0][1], st[0][2]); last = (st[-1][1], st[-1][2])
    # ---- départ : dernière position à l'arrêt (vitesse 0, < 150 m du 1er arrêt) entre -15 et +6 min, puis sortie
    dep = [r for r in L if s0 - 900 <= r['t'] <= s0 + 360 and r['v0'] and km(r['p'], first) < 0.15]
    if dep:
        d0 = dep[-1]; after = [r for r in L if d0['t'] < r['t'] <= d0['t'] + 300 and km(r['p'], first) < 0.6]
        q = quai(d0['p'])
        OUT.append(dict(kind='départ', day=day, ln=ln, var=V['key'], gare=gare(st[0][0]), notre=st[0][0], reel=q[1], dq=round(q[0] * 1000), dnotre=round(km(d0['p'], first) * 1000),
                        t=d0['t'], sched=s0, chemin=[round(dpoly(r['p'], V['P']) * 1000) for r in after], pts=[r['p'] for r in after], p=d0['p']))
    # ---- arrivée : positions vers le(s) dernier(s) arrêt(s), entrée puis 1re position à l'arrêt près du terminus
    nl = len(st) - 1
    near = [r for r in L if r['n'] >= nl - 1 and km(r['p'], last) < 0.6]
    stop = [r for r in near if r['v0'] and km(r['p'], last) < 0.15]
    if near:
        a0 = stop[0] if stop else None
        entry = [r for r in near if a0 is None or r['t'] < a0['t']]
        q = quai(a0['p']) if a0 else (9, '?')
        OUT.append(dict(kind='arrivée', day=day, ln=ln, var=V['key'], gare=gare(st[-1][0]), notre=st[-1][0], reel=q[1] if a0 else None, dq=round(q[0] * 1000) if a0 else None,
                        dnotre=round(km(a0['p'], last) * 1000) if a0 else None, t=(a0 or near[0])['t'], chemin=[round(dpoly(r['p'], V['P']) * 1000) for r in entry],
                        pts=[r['p'] for r in entry], p=a0['p'] if a0 else None))
json.dump(OUT, open(S + 'gpsdata/gares.json', 'w'), ensure_ascii=False)
# ---- résumé par gare / ligne
g = collections.defaultdict(list)
for o in OUT: g[(o['gare'], o['kind'], o['ln'], o['notre'])].append(o)
print('%d courses de nos lignes, %d départs et %d arrivées captés' % (len(by), sum(o['kind'] == 'départ' for o in OUT), sum(1 for o in OUT if o['kind'] == 'arrivée' and o['p'])))
for k, L in sorted(g.items()):
    reel = collections.Counter(o['reel'] for o in L if o['reel'])
    ch = [x for o in L for x in o['chemin']]
    bad = [x for x in ch if x > 35]
    print('%-34s %-7s %-4s notre arrêt: %-40s vu: %d | à l\'arrêt réel: %s | écart à notre arrêt: %s m | chemin %d pts, %d > 35 m %s' % (
        k[0][:34], k[1], k[2], k[3][-40:], len(L), dict(reel.most_common(3)), sorted(o['dnotre'] for o in L if o['dnotre'] is not None),
        len(ch), len(bad), sorted(bad)[-3:] if bad else ''))
