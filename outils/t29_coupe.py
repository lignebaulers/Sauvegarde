"""v27.1 : bus dont le TEC coupe le suivi. Usage : python3 t29_coupe.py <dossier_site> <port>"""
import sys, time, subprocess
from playwright.sync_api import sync_playwright
ROOT, PORT = sys.argv[1], int(sys.argv[2])
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT), '--bind', '127.0.0.1', '--directory', ROOT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
F = []
def ck(ok, l): print('OK   ' if ok else 'ÉCHEC', l); (F.append(l) if not ok else None)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={'width': 390, 'height': 844}); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.route('**/*', lambda r: r.abort() if any(h in r.request.url for h in ('tile.openstreetmap', 'fonts.g', 'irail', 'script.google')) else r.continue_())
        pg.goto(f'http://localhost:{PORT}/'); pg.wait_for_timeout(1200)
        R = pg.evaluate("""()=>{const now=1793916000,S=t=>busState(Object.assign({d:120,tx:0,x:0,st:'22:00:00',sd:'20261105',q:20,vq:null},t),now,true,96);
          return {
           a:S({t:now+300,vq:17,vu:now-120}),          // disparu à 3 arrêts, attendu dans 5 min
           b:S({t:now-240,vq:17,vu:now-600}),          // attendu il y a 4 min : encore « coupé »
           c:S({t:now-900,vq:17,vu:now-1200}),         // attendu il y a 15 min : normalement passé
           d:S({t:now-300,vq:21,vu:now-300}),          // vu après l'arrêt : passé
           e:S({t:now-300,vq:null}),                   // sans GPS, heure dépassée : passé
           f:S({t:now+400,vq:null}),                   // sans GPS, heure à venir : coupé
           g:S({t:0,vq:18,vu:now-60}),                 // sans heure : estimation depuis la dernière vue
           h:busState({d:0,tx:0,x:0,t:now+300,q:20,vq:17,st:'22:00:00',sd:'20261105'},now,false,96)}}""")
        for k, v in R.items(): print('   ', k, v['c'], '|', v['s'])
        ck(R['a']['c'] == 'cut' and R['a']['o'] == 0 and 'dernier signal à 3 arrêts' in R['a']['s'] and 'prévu vers' in R['a']['s'], 'bus coupé à 3 arrêts : « Suivi coupé par le TEC », reste dans les bus à venir')
        ck(R['b']['c'] == 'cut', 'heure prévue dépassée de 4 min : toujours « coupé » (bus en retard)')
        ck(R['c']['c'] == 'done' and 'Normalement passé' in R['c']['s'], '15 min après : « Normalement passé (suivi coupé) »')
        ck(R['d']['c'] == 'done' and R['d']['s'].startswith('✓ Passé'), 'vu après l\'arrêt : « ✓ Passé » comme avant')
        ck(R['e']['c'] == 'done' and R['f']['c'] == 'cut', 'sans GPS : passé si l\'heure est dépassée, coupé si elle est à venir')
        ck(R['g']['c'] == 'cut' and R['g']['est'], 'sans heure TEC : arrivée estimée (≈) depuis la dernière position')
        ck(R['h']['c'] != 'cut', 'bus encore dans le flux : pas touché')
        ck(not errs, 'aucune erreur JS ' + str(errs[:2]))
        b.close()
finally:
    srv.terminate()
print('échecs', len(F))
