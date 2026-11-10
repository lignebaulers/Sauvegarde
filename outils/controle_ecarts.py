"""Contrôle quotidien : les bus des lignes de Baulers roulent-ils sur nos tracés ?
Entrée : le zip GPS d'une journée (dossier Drive « GPS bus », gps_AAAA-MM-JJ.zip) + l'appli (index.html du dépôt).
Pour chaque course (bus en service, type B, lignes 6x, 7x, W, E4, E7) :
  1. variante de l'appli retrouvée par la géométrie (part des positions à ≤ 50 m) puis par l'heure de départ ;
  2. chaque position en service est mesurée au tracé de cette variante, à ses déviations actives ce jour-là
     (dates ET heures), et aux autres variantes de la même ligne ;
  3. hors tracé = à plus de 50 m de tout ça (fin de course et avant le 1er arrêt exclues).
Les positions hors tracé sont regroupées par endroit (≤ 250 m). Un endroit est :
  - « répété » : au moins 2 courses différentes y passent hors tracé → probable déviation non encodée ou tracé faux ;
  - « isolé »  : une seule course → détour ponctuel (embouteillage, accident…), à surveiller seulement.
Un endroit proche d'une déviation connue mais hors de ses dates est signalé « avis hors dates ».
Données véhicules seulement, anonymes : le rapport ne donne ni numéro de véhicule ni chauffeur.
Usage : python3 controle_ecarts.py gps_AAAA-MM-JJ.zip index.html dossier_sortie [historique.json]
Sorties : ecarts_AAAA-MM-JJ.json, ecarts_AAAA-MM-JJ.md, une carte PNG par endroit répété."""
import sys, os, io, re, csv, json, math, zipfile, collections, datetime as dt

LIGNES = re.compile(r'^(6\d|7\d|W|E4|E7)$')
SEUIL = 0.050      # km : hors tracé
GROUPE = 0.250     # km : même endroit
COS = math.cos(math.radians(50.62))
TZ = dt.timezone(dt.timedelta(hours=1))     # Belgique en hiver (novembre–mars)
def xy(p): return (p[1] * 111.32 * COS, p[0] * 111.32)
def km(a, b): A, B = xy(a), xy(b); return math.hypot(A[0] - B[0], A[1] - B[1])
TAG = re.compile(r'<script id="tec-data" type="application/json">(.*?)</script>', re.S)
def dec(s):
    pts = []; i = 0; la = lo = 0
    while i < len(s):
        vals = []
        for _ in range(2):
            sh = r = 0
            while True:
                b = ord(s[i]) - 63; i += 1; r |= (b & 0x1f) << sh; sh += 5
                if b < 0x20: break
            vals.append(~(r >> 1) if r & 1 else r >> 1)
        la += vals[0]; lo += vals[1]; pts.append((la / 1e6, lo / 1e6))
    return pts

class Poly:
    C = 0.1
    def __init__(s, pts):
        P = [xy(p) for p in pts]; s.segs = []; cum = 0
        for (x1, y1), (x2, y2) in zip(P, P[1:]):
            L = math.hypot(x2 - x1, y2 - y1)
            if L: s.segs.append((x1, y1, x2, y2, cum, L)); cum += L
        s.total = cum; s.G = collections.defaultdict(list)
        for i, (x1, y1, x2, y2, c, L) in enumerate(s.segs):
            for gx in range(math.floor(min(x1, x2) / s.C), math.floor(max(x1, x2) / s.C) + 1):
                for gy in range(math.floor(min(y1, y2) / s.C), math.floor(max(y1, y2) / s.C) + 1): s.G[(gx, gy)].append(i)
    def near(s, p):
        x, y = xy(p); gx, gy = math.floor(x / s.C), math.floor(y / s.C); best, pos = 9.0, None
        for dx in (-3, -2, -1, 0, 1, 2, 3):
            for dy in (-3, -2, -1, 0, 1, 2, 3):
                for i in s.G.get((gx + dx, gy + dy), ()):
                    x1, y1, x2, y2, c, L = s.segs[i]
                    t = max(0, min(1, ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / (L * L)))
                    d = math.hypot(x - (x1 + t * (x2 - x1)), y - (y1 + t * (y2 - y1)))
                    if d < best: best, pos = d, c + t * L
        return best, pos

def main(zpath, html, out, histf=None):
    os.makedirs(out, exist_ok=True)
    jour = re.search(r'(\d{4}-\d\d-\d\d)', os.path.basename(zpath)).group(1)
    D = json.loads(TAG.search(open(html, encoding='utf-8').read()).group(1).replace('<\\/', '</'))
    VAR = collections.defaultdict(list); DEVJ = collections.defaultdict(list); DEVALL = collections.defaultdict(list)
    for ln, L in D['lines'].items():
        if not LIGNES.match(ln): continue
        for v in L['variants']:
            code = 'L%s_%02d' % (ln, int(v['i']))
            VAR[ln].append(dict(code=code, poly=Poly(dec(v['poly'])), times=set(v['times']), stops=v['stops'], to=v['to'], pts=dec(v['poly'])))
            for x in D['dev'].get(code, []):
                if not x.get('poly'): continue
                P = Poly(dec(x['poly'])); avis = ','.join(a['n'] for a in x.get('avis', []))
                DEVALL[ln].append((avis, P))
                if any(w[0] <= jour and (not w[1] or w[1] >= jour) for w in x.get('wins', [])): DEVJ[code].append((x.get('hrs'), avis, P))
    # positions du jour
    rows = []; seen = set()
    with zipfile.ZipFile(zpath) as Z:
        for n in sorted(Z.namelist()):
            if not n.endswith('.csv'): continue
            for r in csv.DictReader(io.TextIOWrapper(Z.open(n), 'utf-8'), delimiter=';'):
                if r.get('type') != 'B' or not LIGNES.match(r['ligne']) or not r['arret_n']: continue
                k = (r['ts'], r['vehicule'], r['course'])
                if k in seen: continue
                seen.add(k)
                try: rows.append(dict(t=int(r['ts']), p=(float(r['lat']), float(r['lon'])), n=int(r['arret_n']), ln=r['ligne'], crs=r['course'], veh=r['vehicule'], dep=r['depart'][:5]))
                except ValueError: pass
    by = collections.defaultdict(list)
    for r in rows: by[(r['veh'], r['crs'])].append(r)
    cnt = collections.Counter(); off = []; ncrs = 0; npos = 0; parligne = collections.Counter(); offligne = collections.Counter()
    for (veh, crs), L in by.items():
        L.sort(key=lambda r: r['t']); ln = L[0]['ln']; svc = [r for r in L if r['n'] >= 1]
        if len(svc) < 3 or not VAR.get(ln): continue
        smp = svc[::max(1, len(svc) // 30)]
        V = max(VAR[ln], key=lambda V: (sum(V['poly'].near(r['p'])[0] <= SEUIL for r in smp) / len(smp) + (0.15 if L[0]['dep'] in V['times'] else 0)))
        last = len(V['stops']) - 1; c_off = 0
        # jour de service de la course = date locale de sa 1re position (le zip peut contenir des heures d'un autre jour)
        t0 = dt.datetime.fromtimestamp(L[0]['t'], TZ); hh0, mm0 = map(int, L[0]['dep'].split(':'))
        t_dep = int(dt.datetime(t0.year, t0.month, t0.day, tzinfo=TZ).timestamp()) + hh0 * 3600 + mm0 * 60
        if t_dep - L[0]['t'] > 12 * 3600: t_dep -= 86400
        if L[0]['t'] - t_dep > 12 * 3600: t_dep += 86400
        if dt.datetime.fromtimestamp(t_dep, TZ).strftime('%Y-%m-%d') != jour: continue
        ncrs += 1; parligne[ln] += 1
        parti = fini = False
        for r in svc:
            d, pos = V['poly'].near(r['p'])
            if r['t'] < t_dep - 60: continue                                   # avant l'heure de départ : attente, haut-le-pied
            if not parti:
                if d > SEUIL: continue                                         # pas encore sur le parcours (approche du 1er arrêt)
                parti = True
            if d <= SEUIL and pos is not None and pos >= V['poly'].total - 0.3 and r['n'] >= last - 1: fini = True
            if fini: continue                                                  # fin de course, entrée en gare, retour
            npos += 1; cnt[(veh, crs)] += 1
            if d <= SEUIL: continue
            hh = dt.datetime.fromtimestamp(r['t'], TZ).strftime('%H:%M')
            if any(P.near(r['p'])[0] <= SEUIL for hrs, a, P in DEVJ[V['code']] if not hrs or hrs[0] <= L[0]['dep'] < hrs[1]): continue
            if any(W['poly'].near(r['p'])[0] <= SEUIL for W in VAR[ln] if W is not V): continue   # sur une autre variante de la ligne
            known = sorted({a for a, P in DEVALL[ln] if P.near(r['p'])[0] <= SEUIL})
            off.append(dict(p=r['p'], d=round(d * 1000), ln=ln, var=V['code'], crs=crs, h=hh, t=r['t'], avis=known))
            c_off += 1
        if c_off: offligne[ln] += 1
    # regroupement par endroit
    G = []; last_g = {}
    for o in sorted(off, key=lambda o: o['t']):
        g = last_g.get(o['crs'])
        if g is None or o['t'] - g[-1]['t'] > 200: g = []; G.append(g)    # même course, minutes qui se suivent : même détour
        g.append(o); last_g[o['crs']] = g
    merged = True
    while merged:
        merged = False
        for i in range(len(G)):
            for j in range(i + 1, len(G)):
                if any(km(a['p'], b['p']) <= GROUPE for a in G[i] for b in G[j]): G[i] += G.pop(j); merged = True; break
            if merged: break
    hist = json.load(open(histf)) if histf and os.path.exists(histf) else {}
    E = []
    for g in G:
        crs = {o['crs'] for o in g}; c = (sum(o['p'][0] for o in g) / len(g), sum(o['p'][1] for o in g) / len(g))
        V0 = next(V for V in VAR[g[0]['ln']] if V['code'] == g[0]['var'])
        st = min(V0['stops'], key=lambda s: km(c, (s[1], s[2])))
        vu = sorted({j for j, L in hist.items() if j < jour and any(km(c, tuple(x['c'])) <= GROUPE for x in L)})
        E.append(dict(c=[round(c[0], 5), round(c[1], 5)], courses=len(crs), positions=len(g), lignes=sorted({o['ln'] for o in g}),
                      variantes=sorted({o['var'] for o in g}), de=min(o['h'] for o in g), a=max(o['h'] for o in g), max_m=min(300, max(o['d'] for o in g)),
                      arret_proche=st[0], arret_m=round(km(c, (st[1], st[2])) * 1000), avis_hors_dates=sorted({a for o in g for a in o['avis']}),
                      niveau=('répété' if max(o['d'] for o in g) >= 100 else 'léger') if len(crs) >= 2 else 'isolé', deja_vu=vu, pts=[[o['p'][0], o['p'][1], o['var']] for o in g]))
    E.sort(key=lambda e: (-e['courses'], -e['positions']))
    res = dict(jour=jour, courses_sans_mesure=ncrs - sum(1 for k in cnt if cnt[k]), courses=ncrs, positions=npos, hors_trace=len(off), par_ligne=dict(parligne), courses_avec_ecart=dict(offligne), endroits=E)
    json.dump(res, open(os.path.join(out, 'ecarts_%s.json' % jour), 'w'), ensure_ascii=False, indent=1)
    hist[jour] = [dict(c=e['c'], niveau=e['niveau']) for e in E]
    if histf: json.dump(hist, open(histf, 'w'), ensure_ascii=False)
    # cartes des endroits répétés
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        for k, e in enumerate([e for e in E if e['niveau'] == 'répété'][:12], 1):
            c = e['c']; kx = math.cos(math.radians(c[0])); hl = max(0.004, max(max(abs(p[0] - c[0]), abs(p[1] - c[1]) * kx) for p in e['pts']) * 1.4 + 0.0015)
            fig, ax = plt.subplots(figsize=(7, 7), dpi=120); ax.set_facecolor('#fbfaf7')
            for ln in VAR:
                for V in VAR[ln]:
                    s = [p for p in V['pts'] if abs(p[0] - c[0]) < hl * 2 and abs(p[1] - c[1]) < hl * 2 / kx]
                    if len(s) > 1: ax.plot([p[1] * kx for p in s], [p[0] for p in s], color='#1565c0' if V['code'] in e['variantes'] else '#d8d3c8', lw=3 if V['code'] in e['variantes'] else 4, zorder=2 if V['code'] in e['variantes'] else 1)
            ax.plot([p[1] * kx for p in e['pts']], [p[0] for p in e['pts']], 'o', color='#d32f2f', mec='white', ms=7, zorder=5)
            ax.plot([], [], color='#1565c0', lw=3, label='notre tracé (' + ', '.join(e['variantes']) + ')'); ax.plot([], [], 'o', color='#d32f2f', label='positions GPS hors tracé')
            ax.legend(loc='lower left', fontsize=8); ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
            ax.set_xlim((c[1] - hl / kx) * kx, (c[1] + hl / kx) * kx); ax.set_ylim(c[0] - hl, c[0] + hl)
            ax.set_title('%s · %d courses hors tracé (%s–%s) · près de %s' % (jour, e['courses'], e['de'], e['a'], e['arret_proche']), fontsize=9, loc='left')
            fn = 'ecart_%s_%02d.png' % (jour, k); plt.savefig(os.path.join(out, fn), bbox_inches='tight'); plt.close(fig); e['carte'] = fn
    except ImportError: pass
    json.dump(res, open(os.path.join(out, 'ecarts_%s.json' % jour), 'w'), ensure_ascii=False, indent=1)
    # rapport texte
    R = ['# Contrôle des tracés – %s' % jour, '', '%d courses des lignes de Baulers vues au GPS, %d positions en service, %d hors tracé.' % (ncrs, npos, len(off)), '']
    rep = [e for e in E if e['niveau'] == 'répété']; iso = [e for e in E if e['niveau'] == 'isolé']
    R.append('## Endroits répétés (≥ 2 courses, à plus de 100 m) : %d' % len(rep))
    for e in rep:
        R.append('- **%s** – %d courses, %d positions, %s–%s, jusqu\'à %s m du tracé, près de %s (%d m)%s%s · https://maps.google.com/?q=%s,%s' % (
            '/'.join(e['lignes']), e['courses'], e['positions'], e['de'], e['a'], ('> 300' if e['max_m'] >= 300 else e['max_m']), e['arret_proche'], e['arret_m'],
            ' · avis hors dates : ' + ', '.join(e['avis_hors_dates']) if e['avis_hors_dates'] else '',
            ' · déjà vu le ' + ', '.join(j[8:] + '/' + j[5:7] for j in e['deja_vu']) if e['deja_vu'] else ' · NOUVEAU', e['c'][0], e['c'][1]))
    lg = [e for e in E if e['niveau'] == 'léger']
    R += ['', '## Petits écarts répétés (< 100 m, souvent GPS ou quai) : %d' % len(lg)]
    for e in lg: R.append('- %s – %d courses, jusqu\'à %d m, près de %s' % ('/'.join(e['lignes']), e['courses'], e['max_m'], e['arret_proche']))
    R += ['', '## Endroits isolés (1 course) : %d' % len(iso)]
    for e in iso[:25]:
        R.append('- %s – %s, %d positions, jusqu\'à %d m, près de %s' % ('/'.join(e['lignes']), e['de'], e['positions'], e['max_m'], e['arret_proche']))
    open(os.path.join(out, 'ecarts_%s.md' % jour), 'w').write('\n'.join(R) + '\n')
    print('\n'.join(R[:60]))

if __name__ == '__main__':
    main(*sys.argv[1:5])
