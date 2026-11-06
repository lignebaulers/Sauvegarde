import json, collections, datetime as dt, math, sys
S = '/tmp/claude-0/-home-claude/090c89ab-6469-5ab1-bebb-ae2242a06172/scratchpad'
J = json.load(open(S + '/gpsdata/concord.json')); P = J['pts']; T = {t['crs'] + t['veh']: t for t in J['trips']}
A = {s[0]: s for s in json.load(open(S + '/tecdiag/tec_arrets.json'))['arrets']}
sys.path.insert(0, S + '/tools'); import devbuild3 as DB
h, m, D = DB.load(S + '/r73/index.html')
NST = {('L%s_%02d' % (ln, int(v['i']))): len(v['stops']) for ln, L in D['lines'].items() for v in L['variants']}
COS = math.cos(math.radians(50.65))
def km(p, q): return math.hypot((p[1] - q[1]) * 111.32 * COS, (p[0] - q[0]) * 111.32)
def sched(dep):
    hh, mm = map(int, dep.split(':')); return dt.datetime(2026, 11, 5).timestamp() + hh * 3600 + mm * 60
def nearest(p):
    return min((km(p, (s[2], s[3])), s[1]) for s in A.values() if abs(s[2] - p[0]) < 0.02 and abs(s[3] - p[1]) < 0.03)
hm = lambda t: dt.datetime.fromtimestamp(t).strftime('%H:%M')
SV = [p for p in P if p['t'] >= sched(T[p['crs'] + p['veh']]['dep']) - 30 and p['n'] >= 1]
off = [p for p in SV if p['d'] > 0.035 and p.get('ddev', 9) > 0.035]
print('en service (après l\'heure de départ) :', len(SV), '| sur le tracé <=35 m : %.1f %%' % (100 * sum(p['d'] <= 0.035 for p in SV) / len(SV)),
      '| sur déviation active :', sum(p['d'] > 0.035 and p.get('ddev', 9) <= 0.035 for p in SV), '| hors tracé :', len(off))
# grappes : même variante, positions à moins de 400 m les unes des autres (chaînage simple)
cl = []
for p in sorted(off, key=lambda p: (p['var'], p['p'])):
    for c in cl:
        if c['var'] == p['var'] and min(km(p['p'], q['p']) for q in c['P']) < 0.4: c['P'].append(p); break
    else: cl.append(dict(var=p['var'], P=[p]))
out = []
for c in cl:
    L = c['P']; trips = {q['crs'] for q in L}; ns = [q['n'] for q in L]
    lat = sum(q['p'][0] for q in L) / len(L); lon = sum(q['p'][1] for q in L) / len(L)
    nn = nearest((lat, lon)); last = NST[c['var']] - 1
    where = 'DÉBUT' if max(ns) <= 2 else ('FIN' if min(ns) >= last - 1 else 'milieu')
    tt = [T[q['crs'] + q['veh']]['n'] for q in L]
    out.append(dict(var=c['var'], n=len(L), trips=len(trips), ntrips_var=sum(1 for t in J['trips'] if t['var'] == c['var']), dmax=round(max(q['d'] for q in L) * 1000),
                    dmed=round(sorted(q['d'] for q in L)[len(L) // 2] * 1000), where=where, ns='%d-%d/%d' % (min(ns), max(ns), last), near='%s (%d m)' % (nn[1], nn[0] * 1000),
                    c=(round(lat, 5), round(lon, 5)), hh='%s-%s' % (hm(min(q['t'] for q in L)), hm(max(q['t'] for q in L)))))
out.sort(key=lambda x: (-x['trips'], -x['n']))
for o in out: print('%-8s %3d pos %2d/%2d courses  dmed %5d m  max %5d m  %-6s n=%-9s %s  %s  %s' % (o['var'], o['n'], o['trips'], o['ntrips_var'], o['dmed'], o['dmax'], o['where'], o['ns'], o['hh'], o['c'], o['near'][:55]))
json.dump(out, open(S + '/gpsdata/clusters.json', 'w'), ensure_ascii=False)
