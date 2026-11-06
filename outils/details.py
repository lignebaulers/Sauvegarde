import json, collections, datetime as dt, math, sys
S = '/tmp/claude-0/-home-claude/090c89ab-6469-5ab1-bebb-ae2242a06172/scratchpad'
J = json.load(open(S + '/gpsdata/concord.json')); P = J['pts']; TR = J['trips']; T = {t['crs'] + t['veh']: t for t in TR}
A = {s[0]: s for s in json.load(open(S + '/tecdiag/tec_arrets.json'))['arrets']}
sys.path.insert(0, S + '/tools'); import devbuild3 as DB
h, m, D = DB.load(S + '/r73/index.html')
V = {('L%s_%02d' % (ln, int(v['i']))): v for ln, L in D['lines'].items() for v in L['variants']}
COS = math.cos(math.radians(50.65))
def km(p, q): return math.hypot((p[1] - q[1]) * 111.32 * COS, (p[0] - q[0]) * 111.32)
def sched(dep):
    hh, mm = map(int, dep.split(':')); return dt.datetime(2026, 11, 5).timestamp() + hh * 3600 + mm * 60
# 1) arrêts annoncés par TEC qui ne correspondent pas à notre arrêt n°
bad = collections.Counter(); badtrips = collections.defaultdict(set)
for t in TR:
    for n, sid in t['stbad']:
        st = V[t['var']]['stops']
        ours = st[n][0] if 0 <= n < len(st) else '(au-delà de nos %d arrêts)' % len(st)
        where = [k for k, s in enumerate(st) if km((A[sid][2], A[sid][3]), (s[1], s[2])) < 0.06]
        bad[(t['var'], n, A[sid][1], ours, tuple(where))] += 1; badtrips[t['var']].add(t['crs'])
print('ARRÊTS DIFFÉRENTS (variante, n, arrêt TEC, notre arrêt n°, où est l\'arrêt TEC chez nous) :')
for k, c in sorted(bad.items(), key=lambda kv: (kv[0][0], kv[0][1])): print('  ', k, 'x', c)
print('courses concernées par variante :', {k: len(v) for k, v in badtrips.items()})
# 2) contresens
SV = [p for p in P if p['t'] >= sched(T[p['crs'] + p['veh']]['dep']) - 30 and p['n'] >= 1]
cs = [p for p in SV if p.get('sens') == 'contre']
g = collections.defaultdict(list)
for p in cs: g[(p['var'], round(p['p'][0], 3), round(p['p'][1], 3))].append(p)
print('\nCONTRESENS (sur notre tracé mais roule dans l\'autre sens) :', len(cs), 'positions')
for k, L in sorted(g.items(), key=lambda kv: -len({x['crs'] for x in kv[1]}))[:25]:
    near = min((km(k[1:], (s[2], s[3])), s[1]) for s in A.values() if abs(s[2] - k[1]) < 0.01 and abs(s[3] - k[2]) < 0.015)
    print('   %-8s %2d pos %d courses  n=%s  cap %s  %s (%d m)' % (k[0], len(L), len({x['crs'] for x in L}), sorted({x['n'] for x in L}), sorted({int(x['cap']) for x in L})[:4], near[1][:45], near[0] * 1000))
# 3) déviations actives : le bus suit-il la déviation ?
print('\nDÉVIATIONS ACTIVES (positions plus proches de la déviation que du tracé normal, et inversement, dans la zone qui diffère) :')
dz = collections.defaultdict(lambda: [0, 0, set()])
for p in SV:
    if 'ddev' not in p: continue
    if p['ddev'] <= 0.035 and p['d'] > 0.06: dz[(p['var'], p['devf'])][0] += 1; dz[(p['var'], p['devf'])][2].add(p['crs'])
    elif p['d'] <= 0.035 and p['ddev'] > 0.06: dz[(p['var'], p['devf'])][1] += 1
for k, (a, b, c) in sorted(dz.items()): print('   %-8s %-40s suit la déviation : %3d pos (%d courses) | sur l\'itinéraire normal hors déviation : %3d pos' % (k[0], k[1][:40], a, len(c), b))
