"""3 cartes : W quai 10 (v27 confirmée), E5 évite l'E42, Gembloux gare."""
import json, math, sys, csv, glob, datetime as dt
S = '/tmp/claude-0/-home-claude/090c89ab-6469-5ab1-bebb-ae2242a06172/scratchpad/'
sys.path.insert(0, S + 'tools'); import devbuild3 as DB
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
h, m, D = DB.load(S + 'r73/index.html')
J = json.load(open(S + 'gpsdata/concord.json')); P = J['pts']; TR = {t['crs'] + t['veh']: t for t in J['trips']}
VV = {('L%s_%02d' % (ln, int(v['i']))): v for ln, L in D['lines'].items() for v in L['variants']}
ALL = [DB.dec(v['poly']) for v in VV.values()]
hm = lambda t: dt.datetime.fromtimestamp(t).strftime('%H:%M')
def sched(dep):
    hh, mm = map(int, dep.split(':')); return dt.datetime(2026, 11, 5).timestamp() + hh * 3600 + mm * 60

class Map:
    def __init__(s, c, half_lat, title, sub):
        s.k = math.cos(math.radians(c[0])); hl = half_lat / s.k
        s.S0, s.N0, s.W0, s.E0 = c[0] - half_lat, c[0] + half_lat, c[1] - hl, c[1] + hl; s.hl = half_lat
        s.fig, s.ax = plt.subplots(figsize=(8, 8), dpi=150); s.ax.set_facecolor('#fbfaf7')
        for Q in ALL:
            seg = [p for p in Q if s.inb(p, 0.01)]
            if len(seg) > 1: s.ax.plot([p[1] * s.k for p in seg], [p[0] for p in seg], color='#dcd7cc', lw=5, solid_capstyle='round', zorder=1)
        s.ax.set_title(title + '\n' + sub, fontsize=10.5, loc='left')
    def inb(s, p, mg=0): return s.S0 - mg <= p[0] <= s.N0 + mg and s.W0 - mg <= p[1] <= s.E0 + mg
    def X(s, p): return p[1] * s.k
    def trace(s, Q, col, lw=3, label=None, arrows=True, ls='-'):
        s.ax.plot([s.X(p) for p in Q], [p[0] for p in Q], color=col, lw=lw, zorder=3, label=label, ls=ls, solid_capstyle='round')
        if not arrows: return
        acc = 0
        for a, b in zip(Q, Q[1:]):
            acc += math.hypot((b[1] - a[1]) * s.k * 111.32, (b[0] - a[0]) * 111.32)
            if acc > s.hl * 70 and s.inb(a) and s.inb(b):
                acc = 0; s.ax.annotate('', xy=(s.X(b), b[0]), xytext=(s.X(a), a[0]), arrowprops=dict(arrowstyle='-|>', color=col, lw=1.6, mutation_scale=15), zorder=4)
    def gps(s, p, cap, col, ms=7, lab=None, marker='o'):
        s.ax.plot(s.X(p), p[0], marker, ms=ms, color=col, mec='white', mew=0.9, zorder=8)
        if cap is not None:
            r = s.hl * 0.05; a = math.radians(cap)
            s.ax.annotate('', xy=(s.X(p) + r * math.sin(a), p[0] + r * math.cos(a)), xytext=(s.X(p), p[0]), arrowprops=dict(arrowstyle='-|>', color=col, lw=1.2, mutation_scale=9), zorder=8)
        if lab: s.ax.annotate(lab, (s.X(p), p[0]), xytext=(6, -3), textcoords='offset points', fontsize=7.5, color=col, zorder=9)
    def stop(s, p, name, dx=6, dy=4):
        s.ax.plot(s.X(p), p[0], 's', ms=7, mfc='white', mec='#111', mew=1.5, zorder=7)
        s.ax.annotate(name, (s.X(p), p[0]), xytext=(dx, dy), textcoords='offset points', fontsize=8.5, color='#111', zorder=9, fontweight='bold')
    def label(s, p, txt, col='#444', rot=0, fs=8.5, box=False):
        s.ax.text(s.X(p), p[0], txt, color=col, fontsize=fs, rotation=rot, ha='center', va='center', style='italic', zorder=9,
                  bbox=dict(boxstyle='round,pad=0.25', fc='white', ec='none', alpha=.85) if box else None)
    def note(s, txt, left=False):
        s.ax.text(0.01 if left else 0.99, 0.99, txt, transform=s.ax.transAxes, ha='left' if left else 'right', va='top', fontsize=9, zorder=10, bbox=dict(boxstyle='round,pad=0.45', fc='white', ec='#333', alpha=.95))
    def save(s, fn, scale_m):
        x0 = s.E0 * s.k - (s.E0 - s.W0) * s.k * 0.3; y0 = s.S0 + (s.N0 - s.S0) * 0.035; dx = scale_m / 1000 / 111.32
        s.ax.plot([x0, x0 + dx], [y0, y0], color='#222', lw=3, zorder=9); s.ax.text(x0 + dx / 2, y0 + (s.N0 - s.S0) * 0.013, ('%d m' % scale_m) if scale_m < 1000 else '%d km' % (scale_m // 1000), ha='center', fontsize=9)
        s.ax.text(s.E0 * s.k - (s.E0 - s.W0) * s.k * 0.04, s.N0 - (s.N0 - s.S0) * 0.2, 'N\n↑', ha='center', fontsize=11, fontweight='bold')
        if not s.ax.get_legend(): s.ax.legend(loc='lower left', fontsize=8.2, framealpha=.94)
        s.ax.set_xlim(s.W0 * s.k, s.E0 * s.k); s.ax.set_ylim(s.S0, s.N0); s.ax.set_aspect('equal'); s.ax.set_xticks([]); s.ax.set_yticks([])
        plt.savefig(S + 'ecarts/' + fn, bbox_inches='tight'); plt.close(s.fig); print('ok', fn)

GREEN, RED, BLUE, PURP = '#2e7d32', '#d32f2f', '#1565c0', '#6a1b9a'

# ---------- 1. W : départ du quai 10 (v27)
raw = []
for f in sorted(glob.glob(S + 'gpsdata/gps_2026-11-05_*.csv')):
    raw += [r for r in csv.DictReader(open(f), delimiter=';') if r['ligne'] == 'W' and r['sens'] == '1']
Q10 = (50.683099, 4.37605)
M = Map((50.6837, 4.3770), 0.0024, 'W vers Bruxelles : départ du quai 10 de Braine-l\'Alleud', 'Positions GPS des bus TEC, jeudi 05/11 de 17h47 à 21h30 · une position par minute')
v = VV['LW_02']; M.trace(DB.dec(v['poly']), BLUE, label='notre tracé W v27 (tout droit, demi-tour au rond-point)')
trips = {}
for r in raw: trips.setdefault((r['vehicule'], r['course'], r['depart']), []).append(r)
n_dep = n_sud = 0
for (veh, crs, dep), L in sorted(trips.items(), key=lambda kv: kv[0][2]):
    L.sort(key=lambda r: int(r['ts'])); s0 = sched(dep[:5])
    W = [r for r in L if s0 - 120 <= int(r['ts']) <= s0 + 600]
    d10 = lambda r: math.hypot((float(r['lon']) - Q10[1]) * 70.6, (float(r['lat']) - Q10[0]) * 111.3)
    sud = [i for i, r in enumerate(W) if float(r['lat']) < 50.6829 and d10(r) < 0.15]
    at10 = [i for i, r in enumerate(W) if d10(r) < 0.015]
    if not sud and not at10: continue
    i0 = sud[0] if sud else at10[-1] + 1
    n_dep += 1; n_sud += bool(sud)
    for r in W[i0:]:
        p = (float(r['lat']), float(r['lon']))
        if not M.inb(p): continue
        M.gps(p, float(r['cap']) if float(r['vitesse'] or 0) > 0 else None, GREEN)
        if p[0] < 50.6829:
            k = len(M.ax.texts) % 2
            M.ax.annotate(hm(int(r['ts'])), (M.X(p), p[0]), xytext=(-34 if k else 7, -3), textcoords='offset points', fontsize=7.5, color=GREEN, zorder=9)
M.ax.plot([], [], 'o', color=GREEN, label='bus W en service (heure au sud du quai)')
M.stop(Q10, 'Gare – quai 10', dx=-84, dy=-4)
for s in v['stops']:
    if 'Ancienne Station' in s[0]: M.stop((s[1], s[2]), 'Ancienne Station', dx=-92, dy=2)
M.label((50.68212, 4.37705), 'rond-point\n(demi-tour)', fs=8.5, box=True)
M.label((50.6843, 4.3775), 'av. Albert Ier', rot=80, fs=8.5)
M.note('%d départs observés : tous remontent\nl\'av. Albert Ier après le quai 10,\n%d captés entre le quai 10 et le\nrond-point (le demi-tour).\nAucun par la boucle rue de la Croix.' % (n_dep, n_sud))
M.ax.legend(loc='upper left', fontsize=8.2, framealpha=.94)
M.save('1_W_quai10.png', 100)

# ---------- 2. E5 Namur → Nivelles : l'E42
M = Map((50.4975, 4.7555), 0.0265, 'E5 Namur → Nivelles : entre Rhisnes et Les Isnes', 'Positions GPS des bus TEC, jeudi 05/11 de 17h47 à 21h30 · une position par minute')
M.trace(DB.dec(VV['LE5_02']['poly']), BLUE, label='notre tracé E5 Namur → Nivelles (par l\'E42)')
for p in P:
    if p['var'] == 'LE5_02' and M.inb(p['p']) and p['t'] >= sched(TR[p['crs'] + p['veh']]['dep']) - 30 and p['n'] >= 2:
        off = p['d'] > 0.035; M.gps(p['p'], p['cap'] if p['v'] > 15 else None, RED if off else GREEN, ms=6.5)
for p in P:
    if p['var'] == 'LE5_01' and M.inb(p['p']) and p['n'] >= 2:
        M.gps(p['p'], None, '#00838f', ms=5.5, marker='s')
M.ax.plot([], [], 'o', color=GREEN, label='bus E5 → Nivelles, sur notre tracé'); M.ax.plot([], [], 'o', color=RED, label='bus E5 → Nivelles, hors tracé')
M.ax.plot([], [], 's', color='#00838f', label='bus E5 → Namur (autre sens) : bien sur l\'E42')
for s in VV['LE5_02']['stops']:
    if 'Ecolys' in s[0]: M.stop((s[1], s[2]), 'Rhisnes Ecolys', dx=-40, dy=-14)
    if 'Créalys' in s[0]: M.stop((s[1], s[2]), 'Les Isnes Créalys', dx=-30, dy=8)
M.label((50.4925, 4.758), 'E42', col=BLUE, fs=10, box=True)
M.label((50.5055, 4.7865), 'N4 chée de Bruxelles', rot=62, fs=8, box=True)
M.label((50.5185, 4.7695), 'Bovesse', fs=8.5, box=True)
M.label((50.5105, 4.7445), 'N912 route d\'Eghezée', rot=33, fs=8, box=True)
M.label((50.4805, 4.7605), 'N93 chée de Nivelles\n(Suarlée, Temploux)', rot=22, fs=8, box=True)
M.note(left=True, txt='5 bus sur 5 vers Nivelles évitent l\'E42 :\n4 par Bovesse (N4 puis N912),\n1 par Suarlée/Temploux (N93).\nVers Namur, les 3 bus prennent\nl\'E42 comme notre tracé.')
M.save('2_E5_E42.png', 1000)

# ---------- 3. Gembloux gare (25, 148, E6)
M = Map((50.5681, 4.6932), 0.0064, 'Gembloux gare : départs des 25, 148 et E6', 'Positions GPS des bus TEC, jeudi 05/11 de 17h47 à 21h30 · une position par minute')
for var, col, lw in (('L25_02', BLUE, 3), ('L148_08', BLUE, 3), ('LE6_02', BLUE, 3)):
    M.trace(DB.dec(VV[var]['poly']), col, lw=lw, label='nos tracés 25 / 148 / E6 (par l\'av. de la Faculté)' if var == 'L25_02' else None, arrows=(var == 'L25_02'))
for p in P:
    if p['var'] in ('L25_02', 'L25_03', 'L148_04', 'L148_08', 'LE6_02') and M.inb(p['p']) and p['t'] >= sched(TR[p['crs'] + p['veh']]['dep']) - 30:
        off = p['d'] > 0.035; M.gps(p['p'], p['cap'] if p['v'] > 15 else None, RED if off else GREEN, ms=6.5)
M.ax.plot([], [], 'o', color=GREEN, label='bus sur notre tracé'); M.ax.plot([], [], 'o', color=RED, label='bus hors tracé')
st = VV['L25_02']['stops']
M.stop((st[0][1], st[0][2]), 'Gare (quais)', dx=-68, dy=6)
M.stop((st[1][1], st[1][2]), 'Rue des Volontaires', dx=8, dy=-3)
M.stop((st[2][1], st[2][2]), 'Quatre coins', dx=8, dy=-3)
M.stop((50.57285, 4.698461), 'La Croisée', dx=-58, dy=7)
M.label((50.5655, 4.6965), 'av. de la Faculté\nd\'Agronomie', rot=-50, fs=8, col=BLUE, box=True)
M.label((50.5695, 4.6862), 'rue du Buisson\nSt-Guibert', fs=8, box=True)
M.label((50.5650, 4.6858), 'rue de\nl\'Agasse', fs=8, box=True)
M.label((50.5655, 4.6915), 'chée de Charleroi (N29)', rot=48, fs=8, box=True)
M.label((50.5716, 4.6988), 'chée de Tirlemont', rot=48, fs=8, box=True)
M.note(left=True, txt='Ce soir : 18 courses (148, 25, E6, 52, 27)\nvues sur le détour rue du Buisson St-Guibert,\nrue de l\'Agasse, chée de Charleroi.\n0 bus vu sur l\'av. de la Faculté d\'Agronomie\n(arrêts Rue des Volontaires, Quatre coins).')
M.save('3_Gembloux.png', 200)
