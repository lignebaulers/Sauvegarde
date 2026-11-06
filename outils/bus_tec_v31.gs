/**
 * Lignes Baulers – bus TEC en direct (projet séparé du relais des signalements, qui ne change pas).
 * Version 3.1 (05/11, 22 h 30) : enregistrement GPS plus léger (écriture groupée toutes les 10 min, moins de calcul),
 *   + bus sans course (fins de course, entrées en gare, haut-le-pied), + un fichier zip par jour.
 * La clé du portail open data est dans le fichier cle_tec.txt de ton Drive, jamais dans l’appli.
 * Mise à jour du code : coller, enregistrer. Rien d'autre : la minuterie déjà en place prend le nouveau code toute seule,
 * et le déploiement de l'appli n'a pas besoin d'être refait.
 * Contrôle (facultatif) : en haut, choisis testSansCourse puis Exécuter → rapport diag_sans_course.json dans le dossier Drive.
 * Enregistrement GPS : demarrerEnregistrement (une seule fois, déjà fait) ; arrêter : arreterEnregistrement.
 */
const FOLDER_ID = 'ID_DU_DOSSIER_DRIVE';   // à remplacer par l'identifiant du dossier Drive du projet
const TEC_RT = 'https://api-management-opendata-production.azure-api.net/api/gtfs/feed/tec/rt/';
const TEC_GTFS = 'http://opendata.tec-wl.be/Current%20GTFS/TEC-GTFS.zip'; // 77 Mo : on n’en lit que stops.txt et routes.txt

function doGet(e) {
  const p = (e && e.parameter) || {};
  try {
    if (p.tec) return out_(tecLive_(p));
  } catch (err) {
    return out_({ ok: false, err: String(err).slice(0, 300) });
  }
  if (p.gps) return out_({ ok: true, gps: JSON.parse(PropertiesService.getScriptProperties().getProperty('GPS_STAT') || '{}') });
  return out_({ ok: true, info: 'Lignes Baulers – bus TEC', v: 4 });
}
function out_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
function writeFile_(name, content) {
  const dossier = DriveApp.getFolderById(FOLDER_ID), it = dossier.getFilesByName(name);
  if (it.hasNext()) it.next().setContent(content); else dossier.createFile(name, content, MimeType.PLAIN_TEXT);
}

// la clé n'est pas dans ce code : elle est dans le fichier « cle_tec.txt » du dossier Drive, puis gardée dans les propriétés du script
function tecKey_() {
  const pr = PropertiesService.getScriptProperties();
  let k = pr.getProperty('TEC_KEY');
  if (k) return k;
  const it = DriveApp.getFolderById(FOLDER_ID).getFilesByName('cle_tec.txt');
  k = it.hasNext() ? it.next().getBlob().getDataAsString('UTF-8').trim() : '';
  if (k) pr.setProperty('TEC_KEY', k);
  return k;
}

// ?tec=1&s=ID1,ID2,…  (arrêts TEC d'un même pôle) → passages prévus à ces arrêts (+ ceux vus récemment et partis)
function tecLive_(p) {
  const ids = String(p.s || '').split(',').map(function (x) { return x.trim(); }).filter(String).slice(0, 80);
  if (!ids.length) return { ok: false, err: 'aucun arrêt demandé' };
  ids.sort();
  const key = 'tec:' + Utilities.base64EncodeWebSafe(Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, ids.join(','))).slice(0, 22);
  const cache = CacheService.getScriptCache();
  const hit = cache.get(key);
  if (hit) return JSON.parse(hit);
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const hit2 = cache.get(key);
    if (hit2) return JSON.parse(hit2);
    const now = Math.floor(Date.now() / 1000), S = {};
    ids.forEach(function (x) { S[x] = 1; });
    const tu = rtFetch_('trip-update');
    if (!tu.ok) return { ok: false, err: 'flux TEC : erreur ' + tu.code };
    const feed = gtfsRt_(tu.u8), N = names_(), items = [], V = {};
    // où en est chaque bus (position GPS du TEC) : numéro d'arrêt atteint, même quand l'heure manque
    const vp = rtFetch_('vehicle-position');
    if (vp.ok) gtfsRt_(vp.u8).entities.forEach(function (en) {
      const v = en.vp;
      if (v && v.trip && v.trip.trip_id) V[v.trip.trip_id] = { q: v.seq || 0, st: v.status === undefined ? null : v.status, ts: v.ts || 0, s: v.stop_id || '', la: v.lat, lo: v.lon };
    });
    feed.entities.forEach(function (en) {
      const t = en.tu;
      if (!t || !t.stu || !t.stu.length) return;
      const last = t.stu[t.stu.length - 1].stop_id, lq = t.stu[t.stu.length - 1].seq || 0, pos = V[t.trip.trip_id] || null;
      t.stu.forEach(function (u) {
        if (!S[u.stop_id]) return;
        const ev = u.dep || u.arr || {};
        items.push({ k: t.trip.trip_id + '|' + u.stop_id, r: t.trip.route_id || '', line: nm_(N.r, t.trip.route_id), to: nm_(N.s, last), dir: t.trip.dir, s: u.stop_id,
          t: ev.time || 0, d: ev.delay === undefined ? null : ev.delay, at: (u.arr && u.arr.time) || 0, q: u.seq || 0, x: u.sr || 0,
          sd: t.trip.start_date || '', st: t.trip.start_time || '', trip: t.trip.trip_id, tx: t.trip.sr || 0, veh: t.veh || '', lq: lq, vq: pos ? pos.q : null, vst: pos ? pos.st : null, vts: pos ? pos.ts : 0, vla: pos && pos.la ? +pos.la.toFixed(6) : null, vlo: pos && pos.lo ? +pos.lo.toFixed(6) : null });
      });
    });
    // mémoire courte : un passage qui disparaît du flux est parti
    const sk = key + ':vu';
    let vu = {};
    try { vu = JSON.parse(cache.get(sk) || '{}'); } catch (x) {}
    const cur = {};
    items.forEach(function (it) { cur[it.k] = 1; vu[it.k] = { line: it.line, to: it.to, s: it.s, t: it.t, d: it.d, vu: now }; });
    const gone = [];
    Object.keys(vu).forEach(function (k) {
      const o = vu[k];
      if (cur[k]) return;
      if (now - o.vu > 5400) { delete vu[k]; return; }
      gone.push({ k: k, line: o.line, to: o.to, s: o.s, t: o.t, d: o.d, vu: o.vu, gone: 1 });
    });
    let vs = JSON.stringify(vu);
    if (vs.length > 95000) { // on garde les plus récents
      const ks = Object.keys(vu).sort(function (a, b) { return vu[b].vu - vu[a].vu; }).slice(0, 250), v2 = {};
      ks.forEach(function (k) { v2[k] = vu[k]; }); vs = JSON.stringify(v2);
    }
    cache.put(sk, vs, 21600);
    const res = { ok: true, v: 3, ts: feed.ts, now: now, pos: vp.ok, items: items, gone: gone };
    const txt = JSON.stringify(res);
    if (txt.length < 99000) cache.put(key, txt, 25);
    return res;
  } finally {
    try { lock.releaseLock(); } catch (x) {}
  }
}

// le flux temps réel préfixe les identifiants (gs:tec:…, gr:tec:…), pas les fichiers des arrêts et lignes
function nm_(m, id) {
  id = String(id || '');
  return m[id] || m[id.replace(/^g[a-z]:tec:/, '')] || '';
}

function rtFetch_(name) {
  const r = UrlFetchApp.fetch(TEC_RT + name + '?format=protobuf', { headers: { 'Ocp-Apim-Subscription-Key': tecKey_() }, muteHttpExceptions: true });
  const code = r.getResponseCode();
  if (code !== 200) return { ok: false, code: code, txt: String(r.getContentText()).slice(0, 300) };
  return { ok: true, code: code, u8: new Uint8Array(r.getContent()) };
}

/* ---------- lecteur GTFS-RT (protobuf), juste ce qu'il faut ---------- */
function gtfsRt_(u8) {
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  let i = 0;
  function vint() { let r = 0, s = 0, c; do { c = u8[i++]; if (s < 32) r |= (c & 127) << s; s += 7; } while (c & 128); return r >>> 0; }
  function str(a, b) { let o = ''; for (let k = a; k < b; k += 8192) o += String.fromCharCode.apply(null, u8.subarray(k, Math.min(b, k + 8192))); try { return decodeURIComponent(escape(o)); } catch (x) { return o; } }
  function skip(wt) { if (wt === 0) vint(); else if (wt === 1) i += 8; else if (wt === 2) { const l = vint(); i += l; } else if (wt === 5) i += 4; else throw new Error('protobuf : type ' + wt); }
  function msg(end, f) { while (i < end) { const tag = vint(), fn = tag >>> 3, wt = tag & 7; if (!f(fn, wt)) skip(wt); } }
  function sub(f) { const l = vint(), end = i + l, o = {}; msg(end, function (fn, wt) { return f(o, fn, wt); }); i = end; return o; }
  function sval() { const l = vint(), a = i; i += l; return str(a, i); }
  function f32() { const v = dv.getFloat32(i, true); i += 4; return Math.round(v * 1e6) / 1e6; }
  const trip = function (o, fn, wt) {
    if (wt === 2 && fn === 1) { o.trip_id = sval(); return 1; } if (wt === 2 && fn === 2) { o.start_time = sval(); return 1; }
    if (wt === 2 && fn === 3) { o.start_date = sval(); return 1; } if (wt === 0 && fn === 4) { o.sr = vint(); return 1; }
    if (wt === 2 && fn === 5) { o.route_id = sval(); return 1; } if (wt === 0 && fn === 6) { o.dir = vint(); return 1; } return 0; };
  const ev = function (o, fn, wt) { if (wt === 0 && fn === 1) { o.delay = vint() | 0; return 1; } if (wt === 0 && fn === 2) { o.time = vint(); return 1; } return 0; };
  const veh = function (o, fn, wt) { if (wt === 2 && fn === 1) { o.id = sval(); return 1; } if (wt === 2 && fn === 2) { o.label = sval(); return 1; } return 0; };
  const stu = function (o, fn, wt) {
    if (wt === 0 && fn === 1) { o.seq = vint(); return 1; } if (wt === 2 && fn === 2) { o.arr = sub(ev); return 1; }
    if (wt === 2 && fn === 3) { o.dep = sub(ev); return 1; } if (wt === 2 && fn === 4) { o.stop_id = sval(); return 1; }
    if (wt === 0 && fn === 5) { o.sr = vint(); return 1; } return 0; };
  const tripUpd = function (o, fn, wt) {
    if (wt === 2 && fn === 1) { o.trip = sub(trip); return 1; } if (wt === 2 && fn === 2) { (o.stu = o.stu || []).push(sub(stu)); return 1; }
    if (wt === 2 && fn === 3) { const v = sub(veh); o.veh = v.label || v.id || ''; return 1; } if (wt === 0 && fn === 4) { o.ts = vint(); return 1; }
    if (wt === 0 && fn === 5) { o.delay = vint() | 0; return 1; } return 0; };
  const pos = function (o, fn, wt) {
    if (wt === 5 && fn === 1) { o.lat = f32(); return 1; } if (wt === 5 && fn === 2) { o.lon = f32(); return 1; }
    if (wt === 5 && fn === 3) { o.bearing = f32(); return 1; } if (wt === 5 && fn === 5) { o.speed = f32(); return 1; } return 0; };
  const vehPos = function (o, fn, wt) {
    if (wt === 2 && fn === 1) { o.trip = sub(trip); return 1; } if (wt === 2 && fn === 2) { const q = sub(pos); o.lat = q.lat; o.lon = q.lon; o.bearing = q.bearing; o.speed = q.speed; return 1; }
    if (wt === 0 && fn === 3) { o.seq = vint(); return 1; } if (wt === 0 && fn === 4) { o.status = vint(); return 1; }
    if (wt === 0 && fn === 5) { o.ts = vint(); return 1; } if (wt === 2 && fn === 7) { o.stop_id = sval(); return 1; }
    if (wt === 2 && fn === 8) { const v = sub(veh); o.veh = v.label || v.id || ''; o.vid = v.id || ''; o.vlab = v.label || ''; return 1; } return 0; };
  const ent = function (o, fn, wt) {
    if (wt === 2 && fn === 1) { o.id = sval(); return 1; } if (wt === 2 && fn === 3) { o.tu = sub(tripUpd); return 1; }
    if (wt === 2 && fn === 4) { o.vp = sub(vehPos); return 1; } return 0; };
  const res = { ts: 0, entities: [] };
  msg(u8.length, function (fn, wt) {
    if (wt === 2 && fn === 1) { const h = sub(function (o, f2, w2) { if (w2 === 0 && f2 === 3) { o.ts = vint(); return 1; } return 0; }); res.ts = h.ts || 0; return 1; }
    if (wt === 2 && fn === 2) { res.entities.push(sub(ent)); return 1; }
    return 0;
  });
  return res;
}

/* ---------- noms des arrêts et des lignes TEC (tirés du GTFS officiel) ---------- */
function names_() {
  const cache = CacheService.getScriptCache();
  const n = +(cache.get('nm:n') || 0);
  if (n) {
    const keys = []; for (let k = 0; k < n; k++) keys.push('nm:' + k);
    const got = cache.getAll(keys);
    if (Object.keys(got).length === n) { try { return JSON.parse(keys.map(function (k) { return got[k]; }).join('')); } catch (x) {} }
  }
  const f = DriveApp.getFolderById(FOLDER_ID).getFilesByName('tec_noms.json');
  const txt = f.hasNext() ? f.next().getBlob().getDataAsString('UTF-8') : JSON.stringify({ s: {}, r: {} });
  cacheNames_(txt);
  return JSON.parse(txt);
}
function cacheNames_(txt) {
  const cache = CacheService.getScriptCache(), parts = {}, step = 90000;
  let k = 0;
  for (let a = 0; a < txt.length; a += step) parts['nm:' + (k++)] = txt.slice(a, a + step);
  parts['nm:n'] = String(k);
  try { cache.putAll(parts, 21600); } catch (x) {}
}

// lit stops.txt et routes.txt dans le GTFS TEC (77 Mo) en ne téléchargeant que ces deux morceaux
function staticNames_() {
  const ents = zipEntries_(TEC_GTFS);
  const info = { fichiers: Object.keys(ents).map(function (k) { return k + ' ' + Math.round(ents[k].cs / 1024) + ' Ko'; }) };
  const stops = csv_(zipText_(TEC_GTFS, ents['stops.txt'])), routes = csv_(zipText_(TEC_GTFS, ents['routes.txt']));
  const hs = stops.shift(), hr = routes.shift(), c = function (h, n) { return h.indexOf(n); };
  const si = c(hs, 'stop_id'), sn = c(hs, 'stop_name'), sa = c(hs, 'stop_lat'), so = c(hs, 'stop_lon'), sp = c(hs, 'parent_station'), sc = c(hs, 'stop_code');
  const ri = c(hr, 'route_id'), rs = c(hr, 'route_short_name'), rl = c(hr, 'route_long_name');
  const S = {}, R = {}, list = [];
  stops.forEach(function (r) { if (!r[si]) return; S[r[si]] = r[sn]; list.push([r[si], r[sn], +(+r[sa]).toFixed(6), +(+r[so]).toFixed(6), sp >= 0 ? r[sp] || '' : '', sc >= 0 ? r[sc] || '' : '']); });
  routes.forEach(function (r) { if (r[ri]) R[r[ri]] = r[rs] || r[rl] || ''; });
  const noms = JSON.stringify({ s: S, r: R });
  writeFile_('tec_noms.json', noms);
  writeFile_('tec_arrets.json', JSON.stringify({ entete: ['stop_id', 'stop_name', 'lat', 'lon', 'parent', 'code'], arrets: list }));
  writeFile_('tec_lignes.json', JSON.stringify(routes.map(function (r) { return [r[ri], r[rs], r[rl]]; })));
  cacheNames_(noms);
  info.arrets = list.length; info.lignes = Object.keys(R).length;
  info.entete_arrets = hs; info.entete_lignes = hr;
  return info;
}
function le32_(v) { return [v & 255, (v >>> 8) & 255, (v >>> 16) & 255, (v >>> 24) & 255]; }
function u16_(u, i) { return u[i] | (u[i + 1] << 8); }
function u32_(u, i) { return (u[i] | (u[i + 1] << 8) | (u[i + 2] << 16) | (u[i + 3] << 24)) >>> 0; }
function fetchRange_(url, a, b) {
  const r = UrlFetchApp.fetch(url, { headers: { Range: b == null ? 'bytes=' + a : 'bytes=' + a + '-' + b }, muteHttpExceptions: true, followRedirects: true });
  const code = r.getResponseCode();
  if (code !== 206) throw new Error('le serveur TEC ne découpe pas le fichier (code ' + code + ')');
  const h = r.getHeaders();
  return { u8: new Uint8Array(r.getContent()), cr: String(h['Content-Range'] || h['content-range'] || '') };
}
function zipEntries_(url) {
  const u = fetchRange_(url, -65536, null).u8;
  let e = -1;
  for (let i = u.length - 22; i >= 0; i--) { if (u32_(u, i) === 0x06054b50) { e = i; break; } }
  if (e < 0) throw new Error('fin du zip introuvable');
  let cdSize = u32_(u, e + 12), cdOff = u32_(u, e + 16);
  if (cdOff === 0xffffffff || cdSize === 0xffffffff) {
    const l = e - 20;
    if (l < 0 || u32_(u, l) !== 0x07064b50) throw new Error('zip64 : repère introuvable');
    const z = fetchRange_(url, u32_(u, l + 8), u32_(u, l + 8) + 55).u8;
    cdSize = u32_(z, 40); cdOff = u32_(z, 48);
  }
  const cd = fetchRange_(url, cdOff, cdOff + cdSize - 1).u8, ents = {};
  let i = 0;
  while (i + 46 <= cd.length && u32_(cd, i) === 0x02014b50) {
    const method = u16_(cd, i + 10), crc = u32_(cd, i + 16), nl = u16_(cd, i + 28), xl = u16_(cd, i + 30), cl = u16_(cd, i + 32);
    let cs = u32_(cd, i + 20), us = u32_(cd, i + 24), off = u32_(cd, i + 42);
    const name = String.fromCharCode.apply(null, cd.subarray(i + 46, i + 46 + nl));
    if (cs === 0xffffffff || us === 0xffffffff || off === 0xffffffff) {
      let j = i + 46 + nl; const end = j + xl;
      while (j + 4 <= end) {
        const id = u16_(cd, j), sz = u16_(cd, j + 2);
        if (id === 1) { let k = j + 4; if (us === 0xffffffff) { us = u32_(cd, k); k += 8; } if (cs === 0xffffffff) { cs = u32_(cd, k); k += 8; } if (off === 0xffffffff) { off = u32_(cd, k); k += 8; } }
        j += 4 + sz;
      }
    }
    ents[name.split('/').pop()] = { method: method, crc: crc, cs: cs, us: us, off: off };
    i += 46 + nl + xl + cl;
  }
  return ents;
}
function zipText_(url, ent) {
  if (!ent) throw new Error('fichier absent du GTFS');
  const head = fetchRange_(url, ent.off, ent.off + 29).u8;
  if (u32_(head, 0) !== 0x04034b50) throw new Error('entête locale du zip');
  const start = ent.off + 30 + u16_(head, 26) + u16_(head, 28);
  const data = fetchRange_(url, start, start + ent.cs - 1).u8;
  return unzipOne_(data, ent);
}
// petit zip d'un seul fichier autour des octets déjà compressés, puis Utilities.unzip
function unzipOne_(data, ent) {
  const nb = [0x66, 0x2e, 0x74, 0x78, 0x74], m = [ent.method & 255, ent.method >> 8];
  const lh = [0x50, 0x4b, 0x03, 0x04, 20, 0, 0, 0].concat(m, [0, 0, 0, 0], le32_(ent.crc), le32_(ent.cs), le32_(ent.us), [nb.length, 0, 0, 0], nb);
  const cdh = [0x50, 0x4b, 0x01, 0x02, 20, 0, 20, 0, 0, 0].concat(m, [0, 0, 0, 0], le32_(ent.crc), le32_(ent.cs), le32_(ent.us), [nb.length, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], nb);
  const cdOff = lh.length + data.length;
  const eocd = [0x50, 0x4b, 0x05, 0x06, 0, 0, 0, 0, 1, 0, 1, 0].concat(le32_(cdh.length), le32_(cdOff), [0, 0]);
  const all = new Uint8Array(cdOff + cdh.length + eocd.length);
  all.set(lh, 0); all.set(data, lh.length); all.set(cdh, cdOff); all.set(eocd, cdOff + cdh.length);
  const bytes = new Array(all.length);
  for (let k = 0; k < all.length; k++) bytes[k] = all[k] > 127 ? all[k] - 256 : all[k];
  return Utilities.unzip(Utilities.newBlob(bytes, 'application/zip', 'x.zip'))[0].getDataAsString('UTF-8');
}
function csv_(txt) {
  const Q = String.fromCharCode(34), NL = String.fromCharCode(10), CR = String.fromCharCode(13), BOM = String.fromCharCode(65279);
  const rows = []; let row = [], f = '', q = false;
  if (txt.charAt(0) === BOM) txt = txt.slice(1);
  const fin = function (x) { return x.charAt(x.length - 1) === CR ? x.slice(0, -1) : x; };
  for (let i = 0; i < txt.length; i++) {
    const ch = txt.charAt(i);
    if (q) { if (ch === Q) { if (txt.charAt(i + 1) === Q) { f += Q; i++; } else q = false; } else f += ch; }
    else if (ch === Q) q = true;
    else if (ch === ',') { row.push(f); f = ''; }
    else if (ch === NL) { row.push(fin(f)); rows.push(row); row = []; f = ''; }
    else f += ch;
  }
  if (f.length || row.length) { row.push(fin(f)); rows.push(row); }
  return rows;
}

/* =====================  À lancer une fois depuis l'éditeur  ===================== */
// autorise l'accès au flux TEC, lit les noms des arrêts et des lignes, et laisse un rapport « diag_tec.json » dans le dossier Drive
function testTec() {
  PropertiesService.getScriptProperties().deleteProperty('TEC_KEY'); // relit cle_tec.txt (utile si tu changes de clé)
  const d = { cle: tecKey_() ? 'trouvée' : 'ABSENTE : fichier cle_tec.txt introuvable dans le dossier', quand: Utilities.formatDate(new Date(), 'Europe/Brussels', 'yyyy-MM-dd HH:mm:ss') };
  const now = Date.now() / 1000;
  ['trip-update', 'vehicle-position'].forEach(function (name) {
    const r = rtFetch_(name), o = d[name] = { code: r.code, taille: r.u8 ? r.u8.length : 0 };
    if (!r.ok) { o.erreur = r.txt; return; }
    const f = gtfsRt_(r.u8), routes = {}, stops = {};
    o.ts = f.ts; o.entites = f.entities.length;
    if (name === 'trip-update') {
      const T = f.entities.filter(function (e) { return e.tu; });
      let n = 0, hAr = 0, hDep = 0, rArr = 0, rDep = 0, passe = 0, seq0 = 0;
      T.forEach(function (e) {
        routes[e.tu.trip && e.tu.trip.route_id] = 1;
        (e.tu.stu || []).forEach(function (u, k) {
          n++; stops[u.stop_id] = 1;
          if (u.arr && u.arr.time) hAr++; if (u.dep && u.dep.time) hDep++;
          if (u.arr && u.arr.delay !== undefined) rArr++; if (u.dep && u.dep.delay !== undefined) rDep++;
          const t = (u.dep && u.dep.time) || (u.arr && u.arr.time) || 0; if (t && t < now - 120) passe++;
          if (k === 0 && u.seq === 1) seq0++;
        });
      });
      o.courses = T.length; o.arrets_maj = n; o.heure_arrivee = hAr; o.heure_depart = hDep; o.retard_arrivee = rArr; o.retard_depart = rDep;
      o.deja_passes = passe; o.commencent_au_1er_arret = seq0;
      o.ex = T.slice(0, 3).map(function (e) { return e.tu; });
    } else {
      const V = f.entities.filter(function (e) { return e.vp; });
      V.forEach(function (e) { routes[e.vp.trip && e.vp.trip.route_id] = 1; if (e.vp.stop_id) stops[e.vp.stop_id] = 1; });
      o.vehicules = V.length; o.ex = V.slice(0, 3).map(function (e) { return e.vp; });
    }
    o.nb_lignes = Object.keys(routes).length; o.ex_lignes = Object.keys(routes).slice(0, 20); o.ex_arrets = Object.keys(stops).slice(0, 25);
  });
  try { d.gtfs = staticNames_(); } catch (err) { d.gtfs = { erreur: String(err) }; }
  d.empreintes = empreintes_();
  writeFile_('diag_tec.json', JSON.stringify(d, null, 1));
  Logger.log(JSON.stringify(d).slice(0, 3000));
}

// contrôle que le code arrivé dans Apps Script est bien celui testé (une empreinte par fonction)
function empreintes_() {
  const fs = [doGet, out_, writeFile_, tecKey_, tecLive_, nm_, collecte, demarrerEnregistrement, arreterEnregistrement, rtFetch_, gtfsRt_, names_, cacheNames_, staticNames_, le32_, u16_, u32_, fetchRange_, zipEntries_, zipText_, unzipOne_, csv_, testTec,
    gpsJour_, gpsKm_, gpsTri_, gpsLigne_, routeNames_, gpsIdx_, gpsTampon_, gpsFlush_, flotte_, flotteGarde_, flotteDepuisFichiers_, gpsZipVeille_, gpsDossier_, gpsStat_, testSansCourse];
  const o = {};
  fs.forEach(function (f) {
    const h = Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, f.toString(), Utilities.Charset.UTF_8);
    o[f.name] = h.map(function (b) { return ((b + 256) % 256).toString(16).padStart(2, '0'); }).join('').slice(0, 10);
  });
  return o;
}

/* ====================  Enregistrement GPS des bus du Brabant wallon (v3.1)  ====================
   Une prise par minute (minuterie Google) des positions publiées par le TEC. On garde :
   - les bus en course sur une ligne B (Brabant wallon), comme avant ;
   - ces mêmes bus quand ils n'ont plus de course ou roulent sous une autre ligne (fin de course, entrée en gare, haut-le-pied) ;
   - les bus sans course qui se trouvent dans le Brabant wallon.
   Un bus sans course qui ne bouge pas n'est noté qu'une fois toutes les 10 min.
   Les positions sont gardées en mémoire et écrites dans le Drive toutes les 10 min (dossier « GPS bus », un fichier par heure).
   Chaque matin vers 5 h, les fichiers de la veille sont regroupés dans un zip (gps_AAAA-MM-JJ.zip).
   Rien n'est enregistré entre 1 h et 5 h. Données des véhicules seulement : aucun nom de chauffeur n'existe dans le flux.
   Colonne type : B = en course sur une ligne B, A = autre ligne, S = sans course. Colonne vitesse : valeur du TEC × 3,6 (comme avant). */
const GPS_ENTETE = 'ts;vehicule;ligne;route;course;sens;depart;lat;lon;cap;vitesse;arret_n;etat;arret;type;vid\n';
const GPS_ZONE = [50.56, 50.84, 4.05, 5.10];   // Brabant wallon : sud, nord, ouest, est
const GPS_FLUSH_MIN = 10;                       // écriture dans le Drive toutes les 10 min

function collecte() {
  const t0 = Date.now(), now = new Date(), hh = +Utilities.formatDate(now, 'Europe/Brussels', 'H'), cache = CacheService.getScriptCache();
  if (hh >= 1 && hh < 5) { gpsFlush_(cache, now, true); return; }
  if (hh === 5) { try { gpsZipVeille_(now); } catch (x) {} }
  const r = rtFetch_('vehicle-position'), t1 = Date.now();
  if (!r.ok) { gpsStat_(t0, null, 'flux ' + r.code); return; }
  const f = gtfsRt_(r.u8), R = routeNames_(), t2 = Date.now();
  let last = {}, pos = {};
  try { last = JSON.parse(cache.get('gps:last') || '{}'); } catch (x) {}
  try { pos = JSON.parse(cache.get('gps:pos') || '{}'); } catch (x) {}
  const jour = gpsJour_(now), fl = flotte_(now);
  const res = gpsTri_(f.entities, R, last, pos, fl, jour);
  const lim = Math.floor(now.getTime() / 1000) - 3600;
  Object.keys(pos).forEach(function (k) { if (pos[k][2] < lim) delete pos[k]; });
  cache.put('gps:last', JSON.stringify(res.seen), 3600);
  cache.put('gps:pos', JSON.stringify(pos), 3600);
  if (res.flotte) flotteGarde_(fl, jour);
  const t3 = Date.now();
  gpsTampon_(cache, now, res.rows);
  const w = gpsFlush_(cache, now, false);
  gpsStat_(t0, res.c, w.err || '', { flux: t1 - t0, lecture: t2 - t1, tri: t3 - t2, ecriture: Date.now() - t3, perdus: w.perdus || 0 });
}
function gpsJour_(now) { return Math.floor(now.getTime() / 86400000); }
function gpsKm_(a, b, c, d) { return Math.sqrt(Math.pow((d - b) * 70.6, 2) + Math.pow((c - a) * 111.3, 2)); }

// tri des positions du flux : ce qu'on garde, et les compteurs du contrôle
function gpsTri_(ents, R, last, pos, fl, jour) {
  const c = { ent: ents.length, B: 0, A: 0, S: 0, S_flotte: 0, S_zone: 0, A_flotte: 0, garde_B: 0, garde_A: 0, garde_S: 0 }, rows = [], seen = {};
  let fch = false;
  ents.forEach(function (en) {
    const v = en.vp;
    if (!v || !v.lat) return;
    const rid = v.trip ? String(v.trip.route_id || '') : '', type = rid.indexOf('gr:tec:B') === 0 ? 'B' : (rid ? 'A' : 'S');
    c[type]++;
    const id = v.veh || (v.trip && v.trip.trip_id) || '';
    if (!id) return;
    const pre = String(v.veh || '').split('-')[0], ts = v.ts || 0;
    if (type === 'B') {
      if (pre && fl[pre] !== jour) { fl[pre] = jour; fch = true; }
    } else {
      const connu = !!(pre && fl[pre]), zone = type === 'S' && v.lat >= GPS_ZONE[0] && v.lat <= GPS_ZONE[1] && v.lon >= GPS_ZONE[2] && v.lon <= GPS_ZONE[3];
      if (!connu && !zone) return;
      if (type === 'A') c.A_flotte++; else if (connu) c.S_flotte++; else c.S_zone++;
      const p = pos[id];
      if (p && gpsKm_(p[0], p[1], v.lat, v.lon) < 0.03 && ts - p[2] < 600) { seen[id] = ts; return; }   // garé : une fois toutes les 10 min
      pos[id] = [+v.lat.toFixed(5), +v.lon.toFixed(5), ts];
    }
    seen[id] = ts;
    if (last[id] === ts) return;   // même position que la minute d'avant
    c['garde_' + type]++;
    rows.push(gpsLigne_(v, R, rid, type));
  });
  return { rows: rows, seen: seen, c: c, flotte: fch };
}
function gpsLigne_(v, R, rid, type) {
  const t = v.trip || {};
  return [v.ts || 0, v.veh || t.trip_id || '', rid ? nm_(R, rid) : '', rid.replace('gr:tec:', ''), String(t.trip_id || '').replace('gt:tec:', ''),
    t.dir === undefined ? '' : t.dir, t.start_time || '', v.lat.toFixed(6), v.lon.toFixed(6),
    v.bearing === undefined ? '' : Math.round(v.bearing), v.speed === undefined ? '' : Math.round(v.speed * 36) / 10,
    v.seq === undefined ? '' : v.seq, v.status === undefined ? '' : v.status, String(v.stop_id || '').replace('gs:tec:', ''), type, v.vid || ''].join(';');
}
// noms des lignes seulement (petit, gardé 6 h) : la prise de chaque minute n'a pas besoin des 30 000 noms d'arrêts
function routeNames_() {
  const cache = CacheService.getScriptCache(), hit = cache.get('nm:r');
  if (hit) { try { return JSON.parse(hit); } catch (x) {} }
  const r = names_().r || {};
  try { cache.put('nm:r', JSON.stringify(r), 21600); } catch (x) {}
  return r;
}

/* ---- mémoire tampon : une clé par minute, écrite dans le Drive toutes les 10 min ---- */
function gpsIdx_(cache) { try { return JSON.parse(cache.get('gps:idx') || '[]'); } catch (x) { return []; } }
function gpsTampon_(cache, now, rows) {
  if (!rows.length) return;
  const base = 'gps:b:' + Utilities.formatDate(now, 'Europe/Brussels', 'yyyy-MM-dd_HH:mm'), idx = gpsIdx_(cache), parts = {};
  let cur = [], len = 0, n = 0;
  const pousse = function () { const k = base + '#' + (n++); parts[k] = cur.join('\n'); idx.push(k); cur = []; len = 0; };
  rows.forEach(function (l) { if (len + l.length > 90000 && cur.length) pousse(); cur.push(l); len += l.length + 1; });
  if (cur.length) pousse();
  cache.putAll(parts, 21600);
  cache.put('gps:idx', JSON.stringify(idx), 21600);
}
function gpsFlush_(cache, now, force) {
  const idx = gpsIdx_(cache);
  if (!idx.length) return {};
  const heure = Utilities.formatDate(now, 'Europe/Brussels', 'yyyy-MM-dd_HH'), mn = now.getMinutes();
  const vieux = idx[0].slice(6, 19) !== heure;
  if (!force && !vieux && mn % GPS_FLUSH_MIN !== GPS_FLUSH_MIN - 1 && idx.length < 15) return {};
  const got = cache.getAll(idx), parH = {}, out = { perdus: 0 };
  idx.forEach(function (k) {
    if (got[k] == null) { out.perdus++; return; }
    const h = k.slice(6, 19); (parH[h] = parH[h] || []).push(got[k]);
  });
  try {
    const d = gpsDossier_();
    Object.keys(parH).sort().forEach(function (h) {
      const nom = 'gps_' + h + '.csv', it = d.getFilesByName(nom), txt = parH[h].join('\n') + '\n';
      if (it.hasNext()) { const fi = it.next(); fi.setContent(fi.getBlob().getDataAsString('UTF-8') + txt); }
      else d.createFile(nom, GPS_ENTETE + txt, MimeType.PLAIN_TEXT);
    });
    cache.removeAll(idx);
    cache.put('gps:idx', '[]', 21600);
  } catch (err) { out.err = 'écriture ' + String(err).slice(0, 120); }
  return out;
}

/* ---- mémoire des bus vus sur une ligne B (3 jours), pour les suivre aussi sans course ---- */
function flotte_(now) {
  let m = null;
  try { m = JSON.parse(PropertiesService.getScriptProperties().getProperty('GPS_FLOTTE') || 'null'); } catch (x) {}
  if (!m) { m = {}; try { flotteDepuisFichiers_(m, now); } catch (x) {} flotteGarde_(m, gpsJour_(now)); }
  return m;
}
function flotteGarde_(m, jour) {
  Object.keys(m).forEach(function (k) { if (jour - m[k] > 3) delete m[k]; });
  let s = JSON.stringify(m);
  if (s.length > 8500) {
    const ks = Object.keys(m).sort(function (a, b) { return m[b] - m[a]; }).slice(0, 450), m2 = {};
    ks.forEach(function (k) { m2[k] = m[k]; }); s = JSON.stringify(m2);
  }
  PropertiesService.getScriptProperties().setProperty('GPS_FLOTTE', s);
}
// première fois : les bus déjà vus sur une ligne B dans les fichiers GPS d'aujourd'hui et d'hier
function flotteDepuisFichiers_(m, now) {
  const d = gpsDossier_(), jour = gpsJour_(now);
  [0, 1].forEach(function (k) {
    const j = Utilities.formatDate(new Date(now.getTime() - k * 86400000), 'Europe/Brussels', 'yyyy-MM-dd');
    const it = d.searchFiles("title contains 'gps_" + j + "_'");
    while (it.hasNext()) {
      const fi = it.next();
      if (!/\.csv$/.test(fi.getName())) continue;
      fi.getBlob().getDataAsString('UTF-8').split('\n').forEach(function (l) {
        const c = l.split(';');
        if (c.length > 4 && c[3] && c[3].charAt(0) === 'B') { const p = c[1].split('-')[0]; if (p) m[p] = Math.max(m[p] || 0, jour - k); }
      });
    }
  });
}

/* ---- un zip par jour : fichiers de la veille (5 h – minuit) + celui de minuit – 1 h ---- */
function gpsZipVeille_(now) {
  const pr = PropertiesService.getScriptProperties(), veille = Utilities.formatDate(new Date(now.getTime() - 86400000), 'Europe/Brussels', 'yyyy-MM-dd');
  if (pr.getProperty('GPS_ZIP') === veille) return;
  const d = gpsDossier_(), nom = 'gps_' + veille + '.zip';
  if (!d.getFilesByName(nom).hasNext()) {
    const blobs = [], j0 = Utilities.formatDate(now, 'Europe/Brussels', 'yyyy-MM-dd');
    const it = d.searchFiles("title contains 'gps_" + veille + "_'");
    while (it.hasNext()) { const fi = it.next(); if (/\.csv$/.test(fi.getName())) blobs.push(fi.getBlob().setName(fi.getName())); }
    const m = d.getFilesByName('gps_' + j0 + '_00.csv');
    if (m.hasNext()) { const fi = m.next(); blobs.push(fi.getBlob().setName(fi.getName())); }
    if (blobs.length) d.createFile(Utilities.zip(blobs, nom));
  }
  pr.setProperty('GPS_ZIP', veille);
}

function gpsDossier_() {
  const p = DriveApp.getFolderById(FOLDER_ID), it = p.getFoldersByName('GPS bus');
  return it.hasNext() ? it.next() : p.createFolder('GPS bus');
}
// suivi du temps de calcul (Google limite les minuteries à environ 90 min par jour)
function gpsStat_(t0, c, err, tm) {
  const pr = PropertiesService.getScriptProperties(), j = Utilities.formatDate(new Date(), 'Europe/Brussels', 'yyyy-MM-dd');
  let s = {};
  try { s = JSON.parse(pr.getProperty('GPS_STAT') || '{}'); } catch (x) {}
  if (s.jour !== j) s = { jour: j, prises: 0, points: 0, points_sans_course: 0, points_autre_ligne: 0, secondes: 0, max_s: 0, erreurs: 0, derniere_erreur: '' };
  const dt = (Date.now() - t0) / 1000;
  s.prises++; s.secondes = Math.round((s.secondes + dt) * 10) / 10; s.max_s = Math.max(s.max_s || 0, Math.round(dt * 10) / 10);
  if (c) {
    s.points += c.garde_B + c.garde_A + c.garde_S;
    s.points_sans_course = (s.points_sans_course || 0) + c.garde_S; s.points_autre_ligne = (s.points_autre_ligne || 0) + c.garde_A;
    s.dernier = { h: Utilities.formatDate(new Date(), 'Europe/Brussels', 'HH:mm'), bus_dans_le_flux: c.ent, en_course_B: c.B, autre_ligne: c.A, sans_course: c.S,
      sans_course_bus_B: c.S_flotte, sans_course_zone: c.S_zone, autre_ligne_bus_B: c.A_flotte, gardes: c.garde_B + c.garde_A + c.garde_S, ms: tm || {} };
  }
  if (err) { s.erreurs++; s.derniere_erreur = err; }
  s.moyenne_s = Math.round(s.secondes / s.prises * 10) / 10;
  s.quota_restant_min = Math.round((5400 - s.secondes) / 60);
  s.maj = Utilities.formatDate(new Date(), 'Europe/Brussels', 'HH:mm');
  pr.setProperty('GPS_STAT', JSON.stringify(s));
  if (new Date().getMinutes() % 15 === 0 || s.prises === 1) try { writeFile_('gps_suivi.json', JSON.stringify(s, null, 1)); } catch (x) {}
}
function demarrerEnregistrement() {
  arreterEnregistrement();
  ScriptApp.newTrigger('collecte').timeBased().everyMinutes(1).create();
  collecte();
  Logger.log('Enregistrement GPS démarré : ' + PropertiesService.getScriptProperties().getProperty('GPS_STAT'));
}
function arreterEnregistrement() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'collecte') ScriptApp.deleteTrigger(t); });
  try { gpsFlush_(CacheService.getScriptCache(), new Date(), true); } catch (x) {}
}

/* ---- contrôle à lancer une fois depuis l'éditeur : le TEC publie-t-il les bus sans course ? ---- */
function testSansCourse() {
  const now = new Date(), nowS = Math.floor(now.getTime() / 1000), r = rtFetch_('vehicle-position');
  if (!r.ok) { Logger.log('flux TEC : erreur ' + r.code); return; }
  const f = gtfsRt_(r.u8), fl = flotte_(now);
  const d = { quand: Utilities.formatDate(now, 'Europe/Brussels', 'yyyy-MM-dd HH:mm:ss'), bus_dans_le_flux: f.entities.length, bus_B_connus: Object.keys(fl).length,
    en_course_B: 0, positions_figees_B: 0, autre_ligne: 0, autre_ligne_bus_B: 0, sans_course: 0, sans_course_sans_position: 0, sans_course_bus_B: 0, sans_course_zone: 0,
    ex_B: [], ex_sans_course_bus_B: [], ex_sans_course_zone: [], ex_autre_ligne_bus_B: [], ex_sans_course_ailleurs: [] };
  const ex = function (v) {
    const t = v.trip || {};
    return { veh: v.veh || '', id: v.vid || '', libelle: v.vlab || '', route: t.route_id || '', course: t.trip_id || '', depart: t.start_time || '',
      lat: v.lat, lon: v.lon, age_s: v.ts ? nowS - v.ts : null, vitesse: v.speed, arret_n: v.seq, arret: v.stop_id || '' };
  };
  f.entities.forEach(function (en) {
    const v = en.vp;
    if (!v) return;
    const rid = v.trip ? String(v.trip.route_id || '') : '', pre = String(v.veh || '').split('-')[0];
    if (!v.lat) { if (!rid) d.sans_course_sans_position++; return; }
    if (rid.indexOf('gr:tec:B') === 0) {
      d.en_course_B++; if (v.ts && nowS - v.ts > 180) d.positions_figees_B++;
      if (d.ex_B.length < 5) d.ex_B.push(ex(v)); return;
    }
    const connu = !!(pre && fl[pre]), zone = v.lat >= GPS_ZONE[0] && v.lat <= GPS_ZONE[1] && v.lon >= GPS_ZONE[2] && v.lon <= GPS_ZONE[3];
    if (rid) { d.autre_ligne++; if (connu) { d.autre_ligne_bus_B++; if (d.ex_autre_ligne_bus_B.length < 10) d.ex_autre_ligne_bus_B.push(ex(v)); } return; }
    d.sans_course++;
    if (connu) { d.sans_course_bus_B++; if (d.ex_sans_course_bus_B.length < 15) d.ex_sans_course_bus_B.push(ex(v)); }
    else if (zone) { d.sans_course_zone++; if (d.ex_sans_course_zone.length < 10) d.ex_sans_course_zone.push(ex(v)); }
    else if (d.ex_sans_course_ailleurs.length < 5) d.ex_sans_course_ailleurs.push(ex(v));
  });
  d.conclusion = d.sans_course + d.autre_ligne_bus_B === 0
    ? 'Le TEC ne publie aucun bus sans course : les entrées en gare et les haut-le-pied ne sont pas dans ce flux.'
    : 'Le TEC publie ' + d.sans_course + ' bus sans course (dont ' + d.sans_course_bus_B + ' déjà vus sur une ligne B, ' + d.sans_course_zone + ' dans le Brabant wallon) et ' + d.autre_ligne_bus_B + ' bus B sous une autre ligne : la v3.1 les enregistre.';
  writeFile_('diag_sans_course.json', JSON.stringify(d, null, 1));
  Logger.log(d.conclusion);
}
