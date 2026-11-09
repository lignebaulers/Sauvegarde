/* Lignes Baulers – hors ligne : réseau d'abord (3,5 s max), sinon version gardée sur le téléphone. */
const V='lb-1c1c5f0087';
const CORE=['./','index.html','jszip.min.js','pdf.min.js','pdf.worker.min.js','manifest.webmanifest','baulers-180.png','baulers-192.png','baulers-512.png','TEC_Baulers_sauvegarde.osf'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(V).then(c=>c.addAll(CORE.map(u=>new Request(u,{cache:'reload'})))).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith('lb-')&&k!==V&&k!=='lb-fonts').map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
function netFirst(req){return new Promise(resolve=>{let done=false;const fin=r=>{if(!done&&r){done=true;resolve(r)}};
  const fromCache=()=>caches.open(V).then(c=>c.match(req,{ignoreSearch:true})).then(m=>m||(req.mode==='navigate'?caches.open(V).then(c=>c.match('index.html')):null));
  const t=setTimeout(()=>fromCache().then(fin),3500);
  fetch(req,{cache:'no-cache'}).then(res=>{if(res&&res.ok){const cp=res.clone();caches.open(V).then(c=>c.put(req,cp))}clearTimeout(t);fin(res)})
    .catch(()=>fromCache().then(m=>{clearTimeout(t);fin(m||Response.error())}))})}
self.addEventListener('fetch',e=>{const r=e.request;if(r.method!=='GET')return;const u=new URL(r.url);
  if(u.origin===location.origin){if(u.pathname.endsWith('/version.json'))return;e.respondWith(netFirst(r));return}
  if(u.hostname==='fonts.googleapis.com'||u.hostname==='fonts.gstatic.com'){e.respondWith(caches.open('lb-fonts').then(c=>c.match(r).then(m=>m||fetch(r).then(res=>{c.put(r,res.clone());return res}))));}
});
