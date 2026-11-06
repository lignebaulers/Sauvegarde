"""rebuild74 – 05/11 23 h : correspondances, bus « coupé » par le TEC (r73 -> r74, appli v27.1, sauvegarde v27 inchangée).
Constat GPS du 05/11 : le TEC clôt les courses toutes les 10 min selon l'horaire ; un bus en retard disparaît du flux avant
d'arriver (médiane 3 km avant le terminus). L'appli le marquait « ✓ Passé ». Désormais :
- disparu avant d'avoir atteint l'arrêt et heure attendue pas encore dépassée de 10 min → « ⚠ Suivi coupé par le TEC », arrivée prévue, dernière position ;
- au-delà de 10 min après l'heure attendue → « Normalement passé vers HH:MM » (grisé)."""
import sys, json
S = '/tmp/claude-0/-home-claude/090c89ab-6469-5ab1-bebb-ae2242a06172/scratchpad/'
sys.path.insert(0, S + 'tools'); import devbuild3 as DB
h, m, D = DB.load(S + 'r73/index.html'); pkg0 = json.dumps(D['pkg'], sort_keys=True)
D['qa']['items'].append(["Appli v27.1 (05/11, 23 h) – correspondances : bus coupé par le TEC",
    "Le TEC arrête de publier un bus quand l'horaire dit que sa course est finie, même s'il roule encore (bus en retard). "
    "Avant, l'appli le croyait passé. Maintenant elle affiche « ⚠ Suivi coupé par le TEC » avec l'heure d'arrivée prévue et sa dernière position, "
    "puis « Normalement passé » 10 min après cette heure."])
assert json.dumps(D['pkg'], sort_keys=True) == pkg0
blob = json.dumps(D, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
h = h[:m.start(2)] + blob + h[m.end(2):]
R = [
 ("""  if(!hasP&&(left||(hasT&&x.t<now-60)))return {c:'done',s:'✓ Passé'+(hasT?' '+corrHm(x.t):''),o:1,k:hasT?-x.t:0};""",
  """  if(left){   // plus dans le flux du TEC : passé, ou course clôturée par le TEC avant que le bus arrive (bus en retard)
    const due=hasT?x.t:hasP&&x.vu?x.vu+(n+.5)*spa:0,pas=hasP&&n>=0;
    if((pas||due>now+60)&&due&&now<due+600)return {c:'cut',s:'⚠ Suivi coupé par le TEC · '+(pas?(n>0?'dernier signal à '+n+' arrêt'+(n>1?'s':''):'dernier signal juste avant ici')+' · ':'')+'prévu vers '+corrHm(due),o:0,k:due,eta:due,est:!hasT};
    if(pas&&due)return {c:'done',s:'Normalement passé vers '+corrHm(due)+' (suivi coupé)',o:1,k:-due};
    if(!hasP)return {c:'done',s:'✓ Passé'+(hasT?' '+corrHm(x.t):''),o:1,k:hasT?-x.t:0}}
  if(!hasP&&hasT&&x.t<now-60)return {c:'done',s:'✓ Passé '+corrHm(x.t),o:1,k:-x.t};"""),
 ("""const tm=B.o===0&&B.eta&&(B.est||!hasT)?""", """const tm=B.c==='cut'?(B.est?'<span class=\"eta\">≈ '+busMin(Math.max(60,B.eta-now))+'</span>':corrHm(B.eta)):B.o===0&&B.eta&&(B.est||!hasT)?"""),
 ("""gps&&B.o===0?'📍\\u00a0'+""", """gps&&B.o===0?(B.c==='cut'?'dernière position ':'')+'📍\\u00a0'+"""),
]
for x, y in R:
    assert h.count(x) == 1, x[:90]
    h = h.replace(x, y)
css = '.cr.late .cs{color:#e07b12}'; assert h.count(css) == 1
h = h.replace(css, css + '''
/* r74 : bus dont le TEC a coupé le suivi */
.cr.cut{background:rgba(224,123,18,.10)}
.cr.cut .cs{color:#a65a00;font-weight:700}
.bmk.cut{background:#8a8a8a}''')
import os; os.makedirs(S + 'r74', exist_ok=True); open(S + 'r74/index.html', 'w', encoding='utf-8').write(h); print('r74 ok', len(h))
