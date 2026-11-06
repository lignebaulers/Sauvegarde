// Banc d'essai du relais v3.1 : faux services Google autour du vrai code .gs, avec une horloge pilotée
const fs = require('fs'), vm = require('vm'), crypto = require('crypto');
const DIR = __dirname, T = DIR + '/../t', SRC = fs.readFileSync(DIR + '/../tec/bus_tec_v31.gs', 'utf8');
const signed = buf => Array.from(buf, b => b > 127 ? b - 256 : b);
let FEED = { 'trip-update': T + '/tu.pb', 'vehicle-position': DIR + '/vp_a.pb' }, CALLS = [];
const ZIP = fs.readFileSync(T + '/gtfs.zip');
function resp(code, buf, headers) { return { getResponseCode: () => code, getContent: () => signed(buf), getContentText: () => buf.toString('utf8'), getHeaders: () => headers || {} }; }
const UrlFetchApp = { fetch(url, o) {
  CALLS.push(url);
  if (url.startsWith('https://api-management-opendata-production.azure-api.net/api/gtfs/feed/tec/rt/')) {
    if (o.headers['Ocp-Apim-Subscription-Key'] !== 'CLE-TEST') return resp(401, Buffer.from('{"statusCode":401}'));
    return resp(200, fs.readFileSync(FEED[url.split('/rt/')[1].split('?')[0]]));
  }
  if (url === 'http://opendata.tec-wl.be/Current%20GTFS/TEC-GTFS.zip') {
    const m = /^bytes=(-?\d+)(?:-(\d+))?$/.exec(o.headers.Range); let a = +m[1], b = m[2] === undefined ? null : +m[2];
    if (a < 0) { a = ZIP.length + a; b = ZIP.length - 1; } else if (b === null) b = ZIP.length - 1;
    b = Math.min(b, ZIP.length - 1);
    return resp(206, ZIP.subarray(a, b + 1), { 'Content-Range': `bytes ${a}-${b}/${ZIP.length}` });
  }
  throw new Error('URL inattendue ' + url);
} };
// horloge : Europe/Brussels = UTC+1 en novembre
let NOW = Date.UTC(2026, 10, 5, 21, 31, 5);
class FDate extends Date { constructor(...a) { if (a.length) super(...a); else super(NOW); } static now() { return NOW; } }
const p2 = n => String(n).padStart(2, '0');
const Utilities = {
  DigestAlgorithm: { MD5: 'md5' }, Charset: { UTF_8: 'utf8' },
  computeDigest: (alg, s) => signed(crypto.createHash(alg).update(s, 'utf8').digest()),
  base64EncodeWebSafe: bytes => Buffer.from(bytes.map(b => b & 255)).toString('base64').replace(/\+/g, '-').replace(/\//g, '_'),
  newBlob: (bytes, type, name) => ({ bytes, type, name }),
  unzip: blob => { const cp = require('child_process');
    const out = cp.execFileSync('python3', ['-c', 'import sys,zipfile,io;z=zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read()));n=z.namelist();sys.stdout.buffer.write(z.read(n[0]))'], { input: Buffer.from(blob.bytes.map(b => b & 255)) });
    return [{ getDataAsString: () => out.toString('utf8') }]; },
  zip: (blobs, name) => ({ name, zip: blobs.map(b => b.name), getName: () => name }),
  formatDate: (d, tz, fmt) => { const t = new Date(d.getTime() + 3600e3);
    const map = { yyyy: t.getUTCFullYear(), MM: p2(t.getUTCMonth() + 1), dd: p2(t.getUTCDate()), HH: p2(t.getUTCHours()), mm: p2(t.getUTCMinutes()), ss: p2(t.getUTCSeconds()), H: String(t.getUTCHours()) };
    return fmt.replace(/yyyy|MM|dd|HH|mm|ss|H/g, k => map[k]); },
};
const CACHE = new Map(); let NMGET = 0;
const CacheService = { getScriptCache: () => ({
  get: k => CACHE.has(k) ? CACHE.get(k) : null,
  put: (k, v) => { if (String(v).length > 100000) throw new Error('trop gros pour le cache ' + k); CACHE.set(k, String(v)); },
  getAll: ks => { const o = {}; ks.forEach(k => { if (/^nm:\d/.test(k)) NMGET++; if (CACHE.has(k)) o[k] = CACHE.get(k); }); return o; },
  putAll: o => { for (const k in o) { if (String(o[k]).length > 100000) throw new Error('trop gros ' + k); CACHE.set(k, String(o[k])); } },
  removeAll: ks => ks.forEach(k => CACHE.delete(k)), remove: k => CACHE.delete(k) }) };
const FILES = new Map([['cle_tec.txt', 'CLE-TEST\n']]);   // un seul espace de noms (dossier projet + « GPS bus »), suffisant ici
const PROPS = new Map(); let DRIVE_WRITES = 0;
const blobOf = name => ({ getDataAsString: () => FILES.get(name), setName: n => ({ name: n, src: name }) });
const file = name => ({ getName: () => name, setContent: c => { DRIVE_WRITES++; FILES.set(name, c); }, getBlob: () => blobOf(name), setTrashed() { FILES.delete(name); } });
const iter = names => { let i = 0; return { hasNext: () => i < names.length, next: () => file(names[i++]) }; };
const FOLDERS = new Set(); const TRIG = [];
const folder = () => ({
  getFilesByName: name => iter(FILES.has(name) ? [name] : []),
  searchFiles: q => { const m = /title contains '([^']+)'/.exec(q); return iter([...FILES.keys()].filter(n => n.includes(m[1])).sort()); },
  createFile: (name, c) => { DRIVE_WRITES++; if (typeof name === 'object') { FILES.set(name.name, name); return file(name.name); } FILES.set(name, c); return file(name); },
  getFoldersByName: n => { let done = !FOLDERS.has(n); return { hasNext: () => !done, next: () => { done = true; return folder(); } }; },
  createFolder: n => { FOLDERS.add(n); return folder(); } });
const DriveApp = { getFolderById: () => folder() };
const ScriptApp = { newTrigger: h => ({ timeBased: () => ({ everyMinutes: m => ({ create: () => TRIG.push({ h, m, getHandlerFunction: () => h }) }) }) }),
  getProjectTriggers: () => TRIG.slice(), deleteTrigger: t => TRIG.splice(TRIG.indexOf(t), 1) };
const LOG = [];
const ctx = { ScriptApp, PropertiesService: { getScriptProperties: () => ({ getProperty: k => PROPS.has(k) ? PROPS.get(k) : null, setProperty: (k, v) => { if (String(v).length > 9216) throw new Error('propriété trop grosse ' + k); PROPS.set(k, v); }, deleteProperty: k => PROPS.delete(k) }) },
  UrlFetchApp, Utilities, CacheService, DriveApp, LockService: { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) },
  MimeType: { PLAIN_TEXT: 'text/plain' }, ContentService: { MimeType: { JSON: 'json' }, createTextOutput: s => ({ s, setMimeType() { return this; } }) },
  Logger: { log: s => LOG.push(String(s)) }, console, Date: FDate, Math, JSON, String, Object, Array, Uint8Array, DataView, Error, escape, decodeURIComponent, Number };
vm.createContext(ctx); vm.runInContext(SRC, ctx);
const run = s => vm.runInContext(s, ctx);
const F = []; const ck = (ok, l) => { console.log((ok ? 'OK   ' : 'ÉCHEC') + ' ' + l); if (!ok) F.push(l); };
const at = (d, h, m, s) => { NOW = Date.UTC(2026, 10, d, h - 1, m, s || 5); };          // heure de Bruxelles
const gps = n => (FILES.get(n) || '').trim().split('\n');
const T0 = 1793914260;

// 0) décodage : id et libellé du véhicule séparés
const vp = run('gtfsRt_(new Uint8Array(' + JSON.stringify(Array.from(fs.readFileSync(DIR + '/vp_a.pb'))) + '))');
const e = Object.fromEntries(vp.entities.map(x => [x.id, x.vp]));
ck(e.e0.veh === 'V7777-6337' && e.e0.vlab === 'V7777-6337' && e.e0.vid === '' && e.e1.veh === 'V7805-6357' && e.e1.vid === 'V7805-6357' && !e.e2.trip && e.e1.seq === 0,
  'flux décodé : libellé / id du véhicule, bus sans course, arrêt n° 0');

// 1) noms en cache, anciens fichiers v3 pour amorcer la mémoire des bus B
run("cacheNames_(JSON.stringify({s:{},r:{'B0065-21803':'65','B0072-23739':'72','H1018-24178':'18'}}))");
FOLDERS.add('GPS bus');
FILES.set('gps_2026-11-05_21.csv', 'ts;vehicule;ligne;route;course;sens;depart;lat;lon;cap;vitesse;arret_n;etat;arret\n1;V7805-6300;72;B0072-23739;x;0;21:00:00;50.6;4.33;0;0;3;0;Bniv\n');
FILES.set('gps_2026-11-04_18.csv', 'ts;vehicule;ligne;route;course;sens;depart;lat;lon;cap;vitesse;arret_n;etat;arret\n1;V4444-1;40;B0040-1;y;0;18:00:00;50.6;4.33;0;0;3;0;Bx\n');
FILES.set('gps_2026-11-03_18.csv', 'ts;vehicule;ligne;route;course;sens;depart;lat;lon;cap;vitesse;arret_n;etat;arret\n1;V3333-1;40;B0040-1;y;0;18:00:00;50.6;4.33;0;0;3;0;Bx\n');

// 2) 1re prise à 22:31
at(5, 22, 31); FEED['vehicle-position'] = DIR + '/vp_a.pb'; CALLS = []; DRIVE_WRITES = 0;
run('collecte()');
const fl = JSON.parse(PROPS.get('GPS_FLOTTE'));
ck(fl.V7805 && fl.V4444 && !fl.V3333 && fl.V7777, 'mémoire des bus B : amorcée depuis les fichiers d\'aujourd\'hui et d\'hier (+ bus vus maintenant) : ' + Object.keys(fl).join(', '));
let st = JSON.parse(PROPS.get('GPS_STAT'));
ck(st.dernier.en_course_B === 2 && st.dernier.sans_course === 4 && st.dernier.autre_ligne === 2 && st.dernier.sans_course_bus_B === 1 && st.dernier.sans_course_zone === 1 && st.dernier.autre_ligne_bus_B === 1 && st.dernier.gardes === 5,
  'tri : 2 en course B, sans course gardés (1 bus B connu + 1 dans le BW), Liège et autre ligne inconnue ignorés, 1 bus B sous autre ligne gardé → 5 positions ' + JSON.stringify(st.dernier));
ck(![...FILES.keys()].some(k => k.startsWith('gps_2026-11-05_22')) && JSON.parse(CACHE.get('gps:idx')).length === 1, 'pas d\'écriture Drive à 22:31 : positions en mémoire (1 clé)');
ck(CALLS.length === 1, 'une seule demande au TEC par prise');

// 3) 22:32 : e0 et e3 roulent, e2 garé, e1 figé
at(5, 22, 32); FEED['vehicle-position'] = DIR + '/vp_b.pb'; const nm0 = NMGET; run('collecte()');
st = JSON.parse(PROPS.get('GPS_STAT'));
ck(st.dernier.gardes === 2, 'minute suivante : bus garé sans course et position figée non répétés (2 positions gardées)');
ck(NMGET === nm0, 'noms des lignes pris dans le petit cache (plus de relecture des 30 000 noms d\'arrêts à chaque minute)');

// 4) 22:39 : écriture groupée
at(5, 22, 39); run('collecte()');
let L = gps('gps_2026-11-05_22.csv');
ck(L[0] === 'ts;vehicule;ligne;route;course;sens;depart;lat;lon;cap;vitesse;arret_n;etat;arret;type;vid' && L.length === 8, `22:39 : fichier de l'heure écrit d'un coup (en-tête + ${L.length - 1} positions)`);
const rows = L.slice(1).map(l => l.split(';'));
const byType = t => rows.filter(r => r[14] === t);
ck(rows.every(r => r.length === 16) && byType('B').length === 3 && byType('S').length === 3 && byType('A').length === 1, 'colonnes : 16 partout, types B / S / A');
const r1 = rows.find(r => r[1] === 'V7805-6357'), rs = rows.find(r => r[1] === 'V7777-6400'), ra = rows.find(r => r[1] === 'V7805-9999');
ck(r1 && r1[2] === '72' && r1[11] === '0' && r1[15] === 'V7805-6357', 'bus B au 1er arrêt : n° 0 écrit (avant : vide), id du véhicule : ' + r1.join(';'));
ck(rs && rs[2] === '' && rs[3] === '' && rs[4] === '' && rs[14] === 'S', 'bus sans course : ligne / route / course vides, type S : ' + rs.join(';'));
ck(ra && ra[2] === '18' && ra[3] === 'H1018-24178' && ra[14] === 'A', 'bus B sous une autre ligne : route gardée, type A : ' + ra.join(';'));
ck(JSON.parse(CACHE.get('gps:idx')).length === 0 && ![...CACHE.keys()].some(k => k.startsWith('gps:b:')), 'mémoire vidée après écriture');

// 5) 22:42 : garé depuis 11 min → noté à nouveau
at(5, 22, 42); FEED['vehicle-position'] = DIR + '/vp_c.pb'; run('collecte()');
st = JSON.parse(PROPS.get('GPS_STAT')); ck(st.dernier.gardes === 4, 'bus garé : nouvelle position après 10 min (repère), 4 positions gardées');

// 6) changement d'heure : 23:00 → ce qui reste de 22 h va dans le fichier de 22 h
at(5, 23, 0); run('collecte()');
L = gps('gps_2026-11-05_22.csv'); ck(L.length === 12 && !FILES.has('gps_2026-11-05_23.csv'), `23:00 : reste de 22 h écrit dans le fichier de 22 h (${L.length - 1} positions), pas de fichier 23 h vide`);

// 7) positions de deux heures en mémoire → deux fichiers
run("(function(){ var c = CacheService.getScriptCache(); gpsTampon_(c, new Date(Date.UTC(2026,10,5,22,58,5)), ['1;Va-1;65;B0065-21803;t;0;;50.6;4.3;0;0;1;0;x;B;']); gpsTampon_(c, new Date(Date.UTC(2026,10,5,23,0,5)), ['2;Va-1;65;B0065-21803;t;0;;50.6;4.3;0;0;2;0;x;B;']); gpsFlush_(c, new Date(Date.UTC(2026,10,5,23,0,5)), false); })()");
ck(gps('gps_2026-11-05_23.csv').slice(-1)[0].startsWith('1;Va-1') && gps('gps_2026-11-06_00.csv')[1].startsWith('2;Va-1'), 'positions de 23:58 et 00:00 : chacune dans le fichier de son heure');

// 8) minute très chargée : découpée sous la limite du cache, remise dans l'ordre
const big = Array.from({ length: 3000 }, (_, i) => `${i};V${i}-1;65;B0065-21803;trip${i};0;10:00:00;50.600000;4.300000;90;108;12;0;Bnivgar5;B;V${i}-1`);
run("gpsTampon_(CacheService.getScriptCache(), new Date(Date.UTC(2026,10,5,23,10,5)), " + JSON.stringify(big) + ")");
const nk = JSON.parse(CACHE.get('gps:idx')).length;
run("gpsFlush_(CacheService.getScriptCache(), new Date(Date.UTC(2026,10,5,23,19,5)), false)");
L = gps('gps_2026-11-06_00.csv');
const g23 = gps('gps_2026-11-06_00.csv'); const f23 = gps('gps_2026-11-05_23.csv') ;
const inFile = f23.concat(g23).filter(l => /^\d+;V\d+-1;65/.test(l)).map(l => +l.split(';')[0]);
ck(nk >= 4 && inFile.length === 3000 && inFile.every((x, i) => x === i), `3 000 positions en une minute : ${nk} morceaux sous 100 Ko, tout réécrit dans l'ordre`);

// 9) clé perdue dans le cache : compté, le reste est écrit
run("gpsTampon_(CacheService.getScriptCache(), new Date(Date.UTC(2026,10,5,22,21,5)), ['9;Vb-1;65;B;t;0;;50.6;4.3;0;0;1;0;x;B;'])");
run("gpsTampon_(CacheService.getScriptCache(), new Date(Date.UTC(2026,10,5,22,22,5)), ['10;Vb-1;65;B;t;0;;50.6;4.3;0;0;1;0;x;B;'])");
CACHE.delete(JSON.parse(CACHE.get('gps:idx'))[0]);
const w9 = run("gpsFlush_(CacheService.getScriptCache(), new Date(Date.UTC(2026,10,5,22,29,5)), false)");
ck(w9.perdus === 1 && gps('gps_2026-11-05_23.csv').some(l => l.startsWith('10;Vb-1')), 'morceau effacé du cache : compté comme perdu, le reste écrit');

// 10) nuit : à 1 h, ce qui reste est écrit, aucune demande au TEC
run("gpsTampon_(CacheService.getScriptCache(), new Date(Date.UTC(2026,10,5,23,55,5)), ['11;Vc-1;65;B;t;0;;50.6;4.3;0;0;1;0;x;B;'])");
at(6, 1, 0); CALLS = []; run('collecte()');
ck(CALLS.length === 0 && gps('gps_2026-11-06_00.csv').some(l => l.startsWith('11;Vc-1')) && JSON.parse(CACHE.get('gps:idx')).length === 0, '1 h : pas de prise, dernières positions écrites');

// 11) 5 h : zip de la veille (5 h – minuit + minuit – 1 h), une seule fois
at(6, 5, 0); FEED['vehicle-position'] = DIR + '/vp_c.pb'; run('collecte()');
const z = FILES.get('gps_2026-11-05.zip');
ck(z && z.zip.includes('gps_2026-11-05_22.csv') && z.zip.includes('gps_2026-11-05_21.csv') && z.zip.includes('gps_2026-11-06_00.csv') && !z.zip.some(n => n.includes('11-04')) && PROPS.get('GPS_ZIP') === '2026-11-05',
  '5 h : zip de la veille créé : ' + (z ? z.zip.join(', ') : 'absent'));
const nz = [...FILES.keys()].filter(k => k.endsWith('.zip')).length; at(6, 5, 1); run('collecte()');
ck([...FILES.keys()].filter(k => k.endsWith('.zip')).length === nz, '5 h 01 : pas de 2e zip');

// 12) suivi du quota
st = JSON.parse(PROPS.get('GPS_STAT'));
ck(st.jour === '2026-11-06' && typeof st.moyenne_s === 'number' && st.quota_restant_min <= 90 && st.dernier.ms && 'flux' in st.dernier.ms, 'suivi : temps moyen par prise, quota restant, détail du temps : ' + JSON.stringify({ moyenne_s: st.moyenne_s, quota: st.quota_restant_min, ms: st.dernier.ms }));
at(6, 5, 15); run('collecte()'); const sj = JSON.parse(FILES.get('gps_suivi.json')); ck(sj.prises >= 3 && sj.dernier, 'gps_suivi.json réécrit tous les quarts d\'heure');

// 13) contrôle testSansCourse
NOW = (T0 + 30) * 1000; FEED['vehicle-position'] = DIR + '/vp_a.pb'; run('testSansCourse()');
const d = JSON.parse(FILES.get('diag_sans_course.json'));
ck(d.bus_dans_le_flux === 8 && d.en_course_B === 2 && d.autre_ligne === 2 && d.autre_ligne_bus_B === 1 && d.sans_course === 4 && d.sans_course_bus_B === 1 && d.sans_course_zone === 2 && d.ex_sans_course_bus_B[0].veh === 'V7777-6400' && /publie 4 bus sans course/.test(d.conclusion),
  'testSansCourse : ' + d.conclusion);
NOW = (T0 + 900) * 1000; run('testSansCourse()'); ck(JSON.parse(FILES.get('diag_sans_course.json')).positions_figees_B === 2, 'testSansCourse : positions de plus de 3 min repérées');

// 14) le reste du relais n'a pas bougé
CACHE.clear(); run("cacheNames_(JSON.stringify({s:{HUB_1:'Pôle 1',HUB_2:'Pôle 2','S_Z0':'ÉCAUSSINNES Gare'},r:{R36:'36',R20:'20'}}))");
const r = JSON.parse(run("doGet({parameter:{tec:'1',s:'HUB_2,HUB_1'}}).s"));
ck(r.ok && r.items.length === 600, `doGet ?tec : ${r.items.length} passages (flux de positions avec bus sans course : pas d'erreur)`);
ck(JSON.parse(run("doGet({parameter:{gps:'1'}}).s")).gps.prises >= 1, 'doGet ?gps=1 : suivi');
FILES.set('cle_tec.txt', 'CLE-TEST'); PROPS.delete('TEC_KEY'); run('testTec()'); const dt = JSON.parse(FILES.get('diag_tec.json'));
fs.writeFileSync(DIR + '/empreintes_v31.json', JSON.stringify(dt.empreintes, null, 1));
ck(dt.cle === 'trouvée' && Object.keys(dt.empreintes).length === 38 && dt.gtfs.arrets === 7, 'testTec : rapport complet, 38 empreintes');
TRIG.length = 0; at(6, 9, 0); run('demarrerEnregistrement()'); ck(TRIG.length === 1 && TRIG[0].h === 'collecte', 'demarrerEnregistrement : une minuterie');
run("gpsTampon_(CacheService.getScriptCache(), new Date(Date.UTC(2026,10,6,8,3,5)), ['12;Vd-1;65;B;t;0;;50.6;4.3;0;0;1;0;x;B;'])");
run('arreterEnregistrement()'); ck(TRIG.length === 0 && gps('gps_2026-11-06_09.csv').some(l => l.startsWith('12;Vd-1')), 'arreterEnregistrement : minuterie supprimée et mémoire écrite');
console.log('échecs', F.length);
