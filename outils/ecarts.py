"""Cartes des écarts GPS ↔ tracé.  python3 ecarts.py <cas> ...  (sans argument : tous)"""
import json, math, re, sys, collections, datetime as dt
S = '/tmp/claude-0/-home-claude/090c89ab-6469-5ab1-bebb-ae2242a06172/scratchpad/'
sys.path.insert(0, S + 'tools'); import devbuild3 as DB
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
h, m, D = DB.load(S + 'r73/index.html')
A = {s[0]: s for s in json.load(open(S + 'tecdiag/tec_arrets.json'))['arrets']}
J = json.load(open(S + 'gpsdata/concord.json')); P = J['pts']; TR = {t['crs'] + t['veh']: t for t in J['trips']}
VV = {('L%s_%02d' % (ln, int(v['i']))): v for ln, L in D['lines'].items() for v in L['variants']}
TODAY = '2026-11-05'
ALL = [DB.dec(v['poly']) for v in VV.values()]
hm = lambda t: dt.datetime.fromtimestamp(t).strftime('%H:%M')
def sched(dep):
    hh, mm = map(int, dep.split(':')); return dt.datetime(2026, 11, 5).timestamp() + hh * 3600 + mm * 60
def short(n):
    w = n.split(' '); i = 0
    while i < len(w) - 1 and w[i] == w[i].upper() and any(c.isalpha() for c in w[i]): i += 1
    return ' '.join(w[i:])

def case(fn, title, vars_, c, half_lat, note=None, fromstart=False, extra_stops=()):
    k = math.cos(math.radians(c[0])); half_lon = half_lat / k
    S0, N0, W0, E0 = c[0] - half_lat, c[0] + half_lat, c[1] - half_lon, c[1] + half_lon
    inb = lambda p, mg=0: S0 - mg <= p[0] <= N0 + mg and W0 - mg <= p[1] <= E0 + mg
    fig, ax = plt.subplots(figsize=(8, 8), dpi=120); ax.set_facecolor('#fbfaf7')
    for Q in ALL:
        seg = [p for p in Q if inb(p, 0.01)]
        if len(seg) > 1: ax.plot([p[1] * k for p in seg], [p[0] for p in seg], color='#dcd7cc', lw=4.5, solid_capstyle='round', zorder=1)
    cols = ['#1565c0', '#6a1b9a', '#00838f']
    for j, var in enumerate(vars_):
        v = VV[var]; Q = DB.dec(v['poly'])
        ax.plot([p[1] * k for p in Q], [p[0] for p in Q], color=cols[j], lw=2.6, zorder=3, label='notre tracé %s (%s → %s)' % (var, short(v['from'])[:22], short(v['to'])[:22]))
        # flèches de sens tous les ~250 m dans le cadre
        acc = 0
        for a, b in zip(Q, Q[1:]):
            acc += math.hypot((b[1] - a[1]) * k * 111.32, (b[0] - a[0]) * 111.32)
            if acc > 0.25 * half_lat / 0.004 and inb(a) and inb(b):
                acc = 0; ax.annotate('', xy=(b[1] * k, b[0]), xytext=(a[1] * k, a[0]), arrowprops=dict(arrowstyle='-|>', color=cols[j], lw=1.5, mutation_scale=14), zorder=4)
        for f in D['dev'].get(var, []):
            if f.get('poly') and any(w[0] <= TODAY and (w[1] is None or TODAY <= w[1]) for w in f.get('wins', [])):
                Q2 = DB.dec(f['poly']); ax.plot([p[1] * k for p in Q2], [p[0] for p in Q2], color='#ef6c00', lw=2, ls='--', zorder=3, label='déviation active ' + f['file'][-14:])
        for s in v['stops']:
            if inb((s[1], s[2])):
                ax.plot(s[2] * k, s[1], 's', ms=6, mfc='white', mec='#111', mew=1.4, zorder=6)
                ax.annotate(short(s[0])[:26], (s[2] * k, s[1]), xytext=(5, 4), textcoords='offset points', fontsize=8, color='#222', zorder=7)
    pts = [p for p in P if p['var'] in vars_ and inb(p['p']) and (fromstart or p['t'] >= sched(TR[p['crs'] + p['veh']]['dep']) - 30)]
    trips = sorted({p['crs'] for p in pts})
    for crs in trips:
        L = sorted([p for p in pts if p['crs'] == crs], key=lambda p: p['t'])
        ax.plot([p['p'][1] * k for p in L], [p['p'][0] for p in L], color='#999', lw=0.8, ls=':', zorder=4)
    for p in pts:
        off = p['d'] > 0.035 and p.get('ddev', 9) > 0.035
        ax.plot(p['p'][1] * k, p['p'][0], 'o', ms=6.5, color='#d32f2f' if off else '#2e7d32', mec='white', mew=0.8, zorder=8)
        if p['cap'] is not None and p['v'] > 15:
            r = half_lat * 0.035; a = math.radians(p['cap'])
            ax.annotate('', xy=(p['p'][1] * k + r * math.sin(a), p['p'][0] + r * math.cos(a)), xytext=(p['p'][1] * k, p['p'][0]),
                        arrowprops=dict(arrowstyle='-|>', color='#d32f2f' if off else '#2e7d32', lw=1, mutation_scale=8), zorder=8)
    for sid in extra_stops:
        s = A[sid]; ax.plot(s[3] * k, s[2], 'D', ms=6, mfc='#ffeb3b', mec='#111', zorder=7)
        ax.annotate(short(s[1])[:28], (s[3] * k, s[2]), xytext=(5, -10), textcoords='offset points', fontsize=8, color='#7a5b00', zorder=7)
    ax.plot([], [], 'o', color='#2e7d32', label='position GPS sur notre tracé (≤ 35 m)'); ax.plot([], [], 'o', color='#d32f2f', label='position GPS hors tracé')
    ax.legend(loc='lower left', fontsize=8, framealpha=.92)
    x0 = (E0 - (E0 - W0) * 0.3) * k; y0 = S0 + (N0 - S0) * 0.04
    sc = 0.1 if half_lat < 0.004 else (0.5 if half_lat < 0.02 else 1)
    dx = sc / 111.32; ax.plot([x0, x0 + dx], [y0, y0], color='#222', lw=3); ax.text(x0 + dx / 2, y0 + (N0 - S0) * 0.012, ('%d m' % (sc * 1000)) if sc < 1 else '1 km', ha='center', fontsize=9)
    ax.set_xlim(W0 * k, E0 * k); ax.set_ylim(S0, N0); ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title + '\nGPS TEC du 05/11 (17h47–21h30), %d courses · une position par minute' % len(trips), fontsize=10, loc='left')
    if note: ax.text(0.99, 0.99, note, transform=ax.transAxes, ha='right', va='top', fontsize=8.5, bbox=dict(boxstyle='round,pad=0.4', fc='white', ec='#333', alpha=.93), zorder=9)
    plt.savefig(S + 'ecarts/' + fn, bbox_inches='tight'); plt.close(fig)
    print(fn, len(pts), 'positions', len(trips), 'courses', 'hors tracé', sum(p['d'] > 0.035 and p.get('ddev', 9) > 0.035 for p in pts))

import os; os.makedirs(S + 'ecarts', exist_ok=True)
CASES = {
 'e5namur': lambda: case('E5_Namur.png', 'E5 Namur → Nivelles, entre Namur et Les Isnes', ['LE5_02'], (50.49, 4.79), 0.035),
 'gembloux': lambda: case('Gembloux_25.png', '25 au départ de Gembloux gare', ['L25_02', 'L25_03'], (50.5685, 4.692), 0.006),
 'gembloux148': lambda: case('Gembloux_148.png', '148 à Gembloux', ['L148_04', 'L148_08'], (50.5685, 4.692), 0.006),
 'gemblouxe6': lambda: case('Gembloux_E6.png', 'E6 à Gembloux', ['LE6_02'], (50.5685, 4.692), 0.006),
 'delta': lambda: case('E11_Delta.png', 'E11 à Auderghem Delta', ['LE11_02', 'LE11_01'], (50.816, 4.405), 0.004),
 'e5niv': lambda: case('E5_Nivelles.png', 'E5 dans Nivelles', ['LE5_01', 'LE5_02'], (50.605, 4.335), 0.012),
 'e11lln': lambda: case('E11_LLN.png', 'E11 au départ de Louvain-la-Neuve', ['LE11_01'], (50.665, 4.612), 0.008),
 'fleurus': lambda: case('568_Fleurus.png', '568 à Fleurus', ['L568_02'], (50.486, 4.546), 0.006),
 'landen': lambda: case('148_Landen.png', '148 à Landen', ['L148_06', 'L148_25'], (50.748, 5.072), 0.006),
 'maransart': lambda: case('29_Maransart.png', '29 vers Maransart / Céroux', ['L29_01'], (50.665, 4.47), 0.012),
 'grez': lambda: case('23_Grez.png', '23 à Grez-Doiceau', ['L23_05'], (50.738, 4.70), 0.006),
 'walhain': lambda: case('25_Walhain.png', '25 à Walhain', ['L25_03'], (50.62, 4.695), 0.006),
 'bchateau': lambda: case('65_BraineChateau.png', '65 à Braine-le-Château (déviation Haut-Ittre)', ['L65_01'], (50.68, 4.268), 0.008),
 'hannut': lambda: case('339_Hannut.png', '339 à Hannut', ['L339_05'], (50.675, 5.085), 0.01, fromstart=True),
 'cimetiere': lambda: case('57_Cimetiere.png', '57 / Braine-l\'Alleud Cimetière', ['L57_02', 'L57_01'], (50.6865, 4.3745), 0.002, fromstart=True),
 'nivelles70': lambda: case('70_Nivelles.png', '70 au départ de Nivelles', ['L70_03'], (50.61, 4.33), 0.01),
}
for c in (sys.argv[1:] or CASES): CASES[c]()
