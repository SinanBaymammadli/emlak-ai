// ── Shared constants ──────────────────────────────────────────────────────────
const FILES = {
  apartment: ['sale','rental'], house: ['sale','rental'],
  land: ['sale'], commercial: ['sale','rental'],
  office: ['sale','rental'], garage: ['sale','rental'],
};
const CATS = Object.keys(FILES);
const PAGE_SIZE = 50;
const PALETTE = ['#6366f1','#4ade80','#f59e0b','#ef4444','#06b6d4','#8b5cf6','#ec4899'];
const CAT_COLORS = {apartment:'#6366f1',house:'#4ade80',land:'#f59e0b',commercial:'#ef4444',office:'#06b6d4',garage:'#8b5cf6'};
const CHORO_COLORS = ['#dcfce7','#86efac','#fef08a','#fdba74','#f87171'];

const ALL_LOCATIONS = ['20 Yanvar m.','20-ci sahə q.','28 May m.','9-cu mikrorayon q.','Azadlıq Prospekti m.','Ağ şəhər q.','Badamdar q.','Bakıxanov q.','Bayıl q.','Bilgəh q.','Biləcəri q.','Binə q.','Binəqədi q.','Binəqədi r.','Buzovna q.','Dübəndi q.','Elmlər Akademiyası m.','Görədil q.','Gənclik m.','Hökməli q.','Hövsan q.','Həzi Aslanov m.','Həzi Aslanov q.','Koroğlu m.','Lökbatan q.','M.Ə.Rəsulzadə q.','Masazır q.','Mehdiabad q.','Memar Əcəmi m.','Məmmədli q.','Mərdəkan q.','Nardaran q.','Neftçilər m.','Nizami m.','Nizami r.','Novxanı q.','Nəriman Nərimanov m.','Nərimanov r.','Nəsimi r.','Qala q.','Qara Qarayev m.','Qaraçuxur q.','Qobu q.','Sahil q.','Saray q.','Sea Breeze q.','Türkan q.','Yasamal q.','Yasamal r.','Yeni Ramana q.','Yeni Yasamal q.','Zabrat q.','Zığ q.','İnşaatçılar m.','İçəri Şəhər m.','Şah İsmayıl Xətai m.','Şağan q.','Şüvəlan q.','Əhmədli m.','Ələt q.','Əmircan q.'];

// ── Shared state ──────────────────────────────────────────────────────────────
let selCat   = 'all';
let selType  = 'all';
let selLocs  = new Set();
let sort     = 'newest';
let showDel  = false;
let page     = 1;
let priceMin = null, priceMax = null;
let areaMin  = null, areaMax  = null;
let sotMin   = null, sotMax   = null;
let ppm2Min  = null, ppm2Max  = null;
let roomsF   = '';
let repairF  = '';
let agencyF  = '';
let kupcaF   = '';
let activeTab = 'listings';
let viewMode  = 'markers';

const cache = {};
let allListings = [];
let filtered = [];
let loading = false;
const charts = {};

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(n) {
  if (n == null) return '—';
  return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}
function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}
function formatPrice(price, dealType) {
  if (!price && price !== 0) return '—';
  return dealType === 'rental' ? `${fmt(price)} ₼/ay` : `${fmt(price)} ₼`;
}
function areaVal(l) {
  if (l.area_m2 == null) return null;
  if (typeof l.area_m2 === 'number') return l.area_m2;
  const m = String(l.area_m2).match(/[\d.]+/);
  return m ? parseFloat(m[0]) : null;
}
function ppm2(l) {
  const a = areaVal(l);
  if (!l.price || !a || a <= 0) return null;
  return l.price / a;
}
function ppsot(l) {
  if (!l.price || !l.land_area_sot || l.land_area_sot <= 0) return null;
  return l.price / l.land_area_sot;
}
function roomCount(l) {
  if (!l.rooms) return null;
  const m = String(l.rooms).match(/\d+/);
  return m ? parseInt(m[0]) : null;
}
function priceChange(l) {
  const h = l.price_history;
  if (!h || h.length < 2) return null;
  const prev = h[h.length - 2].price, curr = h[h.length - 1].price;
  return prev === curr ? null : curr - prev;
}
function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function catLabel(cat) {
  return {apartment:'Mənzil',house:'Həyət evi',land:'Torpaq',commercial:'Kommersiya',office:'Ofis',garage:'Qaraj'}[cat]||cat;
}
function locLabel(l) { return l.location_name || l.location || ''; }
function normName(s) {
  return (s||'').toLowerCase().replace(/rayonu?/g,'').replace(/\br\./g,'').replace(/nəriman\s+nərimanov/g,'nərimanov').replace(/[^a-zəığüöçşı]/g,' ').trim().replace(/\s+/g,' ');
}

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadFile(cat, type) {
  const key = `${cat}_${type}`;
  if (cache[key]) return cache[key];
  try {
    const res = await fetch(`data/${cat}_${type}.json`);
    if (!res.ok) throw new Error(res.status);
    cache[key] = await res.json();
  } catch { cache[key] = []; }
  return cache[key];
}

async function loadAll() {
  loading = true;
  renderActiveTab();
  const pairs = [];
  (selCat === 'all' ? CATS : [selCat]).forEach(c => {
    (FILES[c]||[]).forEach(t => { if (selType === 'all' || selType === t) pairs.push([c,t]); });
  });
  allListings = (await Promise.all(pairs.map(([c,t]) => loadFile(c,t)))).flat();
  loading = false;
  buildLocationDropdown();
  applyFilters();
}

// ── Filtering ─────────────────────────────────────────────────────────────────
function num(id) { const v = parseFloat(document.getElementById(id)?.value); return isNaN(v) ? null : v; }

function getFiltered() {
  priceMin = num('price-min'); priceMax = num('price-max');
  areaMin  = num('area-min');  areaMax  = num('area-max');
  sotMin   = num('sot-min');   sotMax   = num('sot-max');
  ppm2Min  = num('ppm2-min');  ppm2Max  = num('ppm2-max');
  roomsF   = document.getElementById('rooms-filter')?.value || '';
  repairF  = document.getElementById('repair-filter')?.value || '';
  agencyF  = document.getElementById('agency-filter')?.value || '';
  kupcaF   = document.getElementById('kupca-filter')?.value || '';
  showDel  = document.getElementById('show-deleted')?.checked || false;

  let list = showDel ? allListings : allListings.filter(l => !l.deleted_at);
  if (selLocs.size) list = list.filter(l => selLocs.has(l.location || l.location_name || ''));
  if (priceMin != null) list = list.filter(l => l.price != null && l.price >= priceMin);
  if (priceMax != null) list = list.filter(l => l.price != null && l.price <= priceMax);
  if (areaMin  != null) list = list.filter(l => { const a = areaVal(l); return a != null && a >= areaMin; });
  if (areaMax  != null) list = list.filter(l => { const a = areaVal(l); return a != null && a <= areaMax; });
  if (sotMin   != null) list = list.filter(l => l.land_area_sot != null && l.land_area_sot >= sotMin);
  if (sotMax   != null) list = list.filter(l => l.land_area_sot != null && l.land_area_sot <= sotMax);
  if (ppm2Min  != null) list = list.filter(l => { const v = ppm2(l); return v != null && v >= ppm2Min; });
  if (ppm2Max  != null) list = list.filter(l => { const v = ppm2(l); return v != null && v <= ppm2Max; });
  if (roomsF) {
    if (roomsF === '5') list = list.filter(l => { const r = roomCount(l); return r != null && r >= 5; });
    else { const n = parseInt(roomsF); list = list.filter(l => roomCount(l) === n); }
  }
  if (repairF === 'yes') list = list.filter(l => l.has_repair === true);
  if (repairF === 'no')  list = list.filter(l => l.has_repair === false);
  if (agencyF === 'agency') list = list.filter(l => l.is_agency === true);
  if (agencyF === 'owner')  list = list.filter(l => l.is_agency === false);
  if (kupcaF  === 'yes') list = list.filter(l => l.has_bill_of_sale === true);
  if (kupcaF  === 'no')  list = list.filter(l => l.has_bill_of_sale === false);
  return list;
}

function applyFilters() {
  filtered = getFiltered().sort((a, b) => {
    switch (sort) {
      case 'newest':     return new Date(b.updated_at_site||0) - new Date(a.updated_at_site||0);
      case 'price_asc':  return (a.price||0) - (b.price||0);
      case 'price_desc': return (b.price||0) - (a.price||0);
      case 'ppm2_asc':   return (ppm2(a)||0) - (ppm2(b)||0);
      case 'ppm2_desc':  return (ppm2(b)||0) - (ppm2(a)||0);
      case 'ppsot_asc':  return (ppsot(a)||0) - (ppsot(b)||0);
      case 'ppsot_desc': return (ppsot(b)||0) - (ppsot(a)||0);
      case 'area_asc':   return (areaVal(a)||0) - (areaVal(b)||0);
      case 'area_desc':  return (areaVal(b)||0) - (areaVal(a)||0);
      default: return 0;
    }
  });
  page = 1;
  renderActiveTab();
  pushState();
}

// ── Tab switching ─────────────────────────────────────────────────────────────
function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.tab-content').forEach(s => s.style.display = 'none');
  document.getElementById(`tab-${tab}`).style.display = '';

  // Show/hide listings-only row
  document.getElementById('listings-filters-row').style.display = tab === 'listings' ? '' : 'none';

  if (tab === 'map') {
    initMap();
    setTimeout(() => { if (leafletMap) leafletMap.invalidateSize(); }, 100);
  }
  renderActiveTab();
  pushState();
}

function renderActiveTab() {
  if (activeTab === 'listings') renderListings();
  else if (activeTab === 'analytics') renderAnalytics();
  else if (activeTab === 'map') renderMap();
}

// ── Listings tab ──────────────────────────────────────────────────────────────
function renderListings() {
  const grid = document.getElementById('grid');
  const statsBar = document.getElementById('stats-bar');
  const glStats = document.getElementById('global-stats');

  if (loading) {
    grid.innerHTML = '<div class="state-msg"><div class="spinner"></div>Yüklənir…</div>';
    return;
  }
  const slice = filtered.slice((page-1)*PAGE_SIZE, page*PAGE_SIZE);
  if (!slice.length) {
    grid.innerHTML = '<div class="state-msg">Nəticə tapılmadı</div>';
  } else {
    grid.innerHTML = slice.map(cardHTML).join('');
  }

  const active = filtered.filter(l => !l.deleted_at).length;
  statsBar.textContent = showDel
    ? `${filtered.length} nəticə (${active} aktiv, ${filtered.length-active} silinmiş)`
    : `${filtered.length} aktiv elan`;
  glStats.textContent = `${allListings.length.toLocaleString()} elan yükləndi`;

  renderPagination();
}

function cardHTML(l) {
  const change = priceChange(l);
  let changeBadge = '';
  if (change !== null) {
    const abs = fmt(Math.abs(change));
    changeBadge = change < 0 ? `<span class="price-drop">↓ ${abs} ₼</span>` : `<span class="price-rise">↑ ${abs} ₼</span>`;
  }
  const photo = l.photo_url
    ? `<img src="${esc(l.photo_url)}" alt="" loading="lazy" onerror="this.parentElement.innerHTML='<div class=card-photo-placeholder>🏠</div>'">`
    : '<div class="card-photo-placeholder">🏠</div>';
  const m2 = ppm2(l), sot = ppsot(l);
  let unitPrice = '';
  if (m2) unitPrice = `<div class="card-unit-price">${fmt(m2)} ₼/m²</div>`;
  else if (sot) unitPrice = `<div class="card-unit-price">${fmt(sot)} ₼/sot</div>`;
  const area = areaVal(l);
  const specs = [l.rooms||'', area?`${area} m²`:'', l.land_area_sot?`${l.land_area_sot} sot`:'', l.floor?`${l.floor} mərt.`:''].filter(Boolean).join(' · ');
  const badges = [
    l.has_repair ? '<span class="badge badge-repair">✓ Təmirli</span>' : '',
    l.is_agency  ? '<span class="badge badge-agency">Agentlik</span>' : '<span class="badge badge-owner">Mülkiyyətçi</span>',
    l.deleted_at ? '<span class="badge badge-deleted">Silinib</span>' : '',
    selCat === 'all' ? `<span class="badge badge-cat">${catLabel(l.category)}</span>` : '',
  ].filter(Boolean).join('');
  return `<div class="card${l.deleted_at?' deleted':''}">
  <a class="card-photo-wrap" href="${esc(l.url)}" target="_blank" rel="noopener">${photo}</a>
  <div class="card-body">
    <div class="card-price-row"><span class="card-price">${formatPrice(l.price,l.deal_type)}</span>${changeBadge}</div>
    ${unitPrice}
    ${specs?`<div class="card-details">${esc(specs)}</div>`:''}
    ${l.location?`<div class="card-location">${esc(l.location)}</div>`:''}
    <div class="card-meta"><span class="card-date">${l.updated_at_site?fmtDate(l.updated_at_site):''}</span>${badges?`<div class="card-badges">${badges}</div>`:''}</div>
  </div>
  <div class="card-footer">
    <a href="${esc(l.url)}" target="_blank" rel="noopener">bina.az</a>
    ${l.lat&&l.lng?`<a href="https://www.google.com/maps?q=${l.lat},${l.lng}" target="_blank" rel="noopener">Xəritə</a>`:''}
  </div>
</div>`;
}

function renderPagination() {
  const total = Math.ceil(filtered.length / PAGE_SIZE);
  const pag = document.getElementById('pagination');
  if (total <= 1) { pag.style.display = 'none'; return; }
  pag.style.display = 'flex';
  pag.innerHTML = `<button id="btn-prev" ${page===1?'disabled':''}>← Əvvəlki</button><span>${page} / ${total}</span><button id="btn-next" ${page===total?'disabled':''}>Növbəti →</button>`;
  document.getElementById('btn-prev').onclick = () => { page--; renderListings(); renderPagination(); scrollTo({top:0,behavior:'smooth'}); };
  document.getElementById('btn-next').onclick = () => { page++; renderListings(); renderPagination(); scrollTo({top:0,behavior:'smooth'}); };
}

// ── Analytics tab ─────────────────────────────────────────────────────────────
function renderAnalytics() {
  if (loading) {
    document.getElementById('analytics-content').innerHTML = '<div class="spinner" style="margin:60px auto"></div>';
    return;
  }
  const list = getFiltered();
  const container = document.getElementById('analytics-content');

  // Destroy old charts
  Object.keys(charts).forEach(k => { if (charts[k]) { charts[k].destroy(); delete charts[k]; } });

  container.innerHTML = `
    <div class="stat-tiles">
      <div class="stat-tile"><div class="label">Aktiv elanlar</div><div class="value" id="s-total">—</div></div>
      <div class="stat-tile"><div class="label">${selType==='rental'?'Orta kirayə (₼/ay)':'Orta qiymət'}</div><div class="value" id="s-avg-price">—</div></div>
      <div class="stat-tile"><div class="label">Orta ₼/m²</div><div class="value" id="s-avg-ppm2">—</div></div>
      <div class="stat-tile"><div class="label">Unikal məkanlar</div><div class="value" id="s-locs">—</div></div>
    </div>
    <div class="charts-grid">
      <div class="chart-card"><h3>Məkana görə elan sayı (top 15)</h3><div class="chart-wrap" style="height:300px"><canvas id="c-loc-count"></canvas></div></div>
      <div class="chart-card"><h3>Məkana görə orta ₼/m² (top 15)</h3><div class="chart-wrap" style="height:300px"><canvas id="c-loc-ppm2"></canvas></div></div>
      <div class="chart-card"><h3>Kateqoriyaya görə</h3><div class="chart-wrap" style="height:240px"><canvas id="c-cat"></canvas></div></div>
      <div class="chart-card"><h3>Satış vs Kirayə</h3><div class="chart-wrap" style="height:240px"><canvas id="c-deal"></canvas></div></div>
      <div class="chart-card"><h3>Yeni vs Köhnə tikili</h3><div class="chart-wrap" style="height:240px"><canvas id="c-build"></canvas></div></div>
      <div class="chart-card"><h3>Agentlik vs Mülkiyyətçi</h3><div class="chart-wrap" style="height:240px"><canvas id="c-agency"></canvas></div></div>
      <div class="chart-card full-width"><h3>Qiymət paylanması${selType==='rental'?' (kirayə)':' (satış)'}</h3><div class="chart-wrap" style="height:240px"><canvas id="c-price-dist"></canvas></div></div>
    </div>`;

  // Stats
  document.getElementById('s-total').textContent = list.length.toLocaleString();
  const prices = list.filter(l=>l.price).map(l=>l.price);
  document.getElementById('s-avg-price').textContent = prices.length ? `${fmt(prices.reduce((a,b)=>a+b,0)/prices.length)} ₼` : '—';
  const pm2vals = list.map(ppm2).filter(Boolean);
  document.getElementById('s-avg-ppm2').textContent = pm2vals.length ? `${fmt(pm2vals.reduce((a,b)=>a+b,0)/pm2vals.length)} ₼/m²` : '—';
  document.getElementById('s-locs').textContent = new Set(list.map(locLabel).filter(Boolean)).size;

  // Charts
  const makeBar = (id, labels, data, color=PALETTE[0], horiz=true) => {
    const ctx = document.getElementById(id); if (!ctx) return;
    if (!data.length) { ctx.parentElement.innerHTML = '<div class="no-data">Məlumat yoxdur</div>'; return; }
    charts[id] = new Chart(ctx, { type:'bar', data:{labels,datasets:[{data,backgroundColor:color,borderRadius:4}]}, options:{indexAxis:horiz?'y':'x',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{color:'#f0f2f5'},ticks:{font:{size:11}}},y:{grid:{display:false},ticks:{font:{size:11}}}}} });
  };
  const makeDoughnut = (id, labels, data) => {
    const ctx = document.getElementById(id); if (!ctx) return;
    if (!data.some(d=>d>0)) { ctx.parentElement.innerHTML = '<div class="no-data">Məlumat yoxdur</div>'; return; }
    charts[id] = new Chart(ctx, { type:'doughnut', data:{labels,datasets:[{data,backgroundColor:PALETTE,borderWidth:2,borderColor:'#fff'}]}, options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom',labels:{font:{size:11},boxWidth:12}}}} });
  };

  const locCount = {};
  list.forEach(l => { const k=locLabel(l); if(k) locCount[k]=(locCount[k]||0)+1; });
  const topLocs = Object.entries(locCount).sort((a,b)=>b[1]-a[1]).slice(0,15);
  makeBar('c-loc-count', topLocs.map(x=>x[0]), topLocs.map(x=>x[1]), PALETTE[0]);

  const locPpm2 = {};
  list.forEach(l => { const k=locLabel(l),v=ppm2(l); if(k&&v){if(!locPpm2[k])locPpm2[k]=[];locPpm2[k].push(v);} });
  const topPpm2 = Object.entries(locPpm2).filter(([,v])=>v.length>=3).map(([k,v])=>[k,v.reduce((a,b)=>a+b,0)/v.length]).sort((a,b)=>b[1]-a[1]).slice(0,15);
  makeBar('c-loc-ppm2', topPpm2.map(x=>x[0]), topPpm2.map(x=>Math.round(x[1])), PALETTE[2]);

  const cats = ['apartment','house','land','commercial','office','garage'];
  makeDoughnut('c-cat', cats.map(catLabel), cats.map(c=>list.filter(l=>l.category===c).length));
  makeDoughnut('c-deal', ['Satış','Kirayə'], [list.filter(l=>l.deal_type==='sale').length, list.filter(l=>l.deal_type==='rental').length]);

  const resid = list.filter(l=>l.category==='apartment'||l.category==='house');
  makeDoughnut('c-build', ['Yeni tikili','Köhnə tikili','Məlum deyil'], [resid.filter(l=>l.building_type==='Yeni tikili').length, resid.filter(l=>l.building_type==='Köhnə tikili').length, resid.filter(l=>!l.building_type).length]);
  makeDoughnut('c-agency', ['Agentlik','Mülkiyyətçi','Məlum deyil'], [list.filter(l=>l.is_agency===true).length, list.filter(l=>l.is_agency===false).length, list.filter(l=>l.is_agency==null).length]);

  const saleList = list.filter(l=>l.deal_type==='sale'&&l.price);
  const buckets = [[0,50000,'0–50k'],[50000,100000,'50–100k'],[100000,150000,'100–150k'],[150000,200000,'150–200k'],[200000,300000,'200–300k'],[300000,Infinity,'300k+']];
  makeBar('c-price-dist', buckets.map(b=>b[2]), buckets.map(([lo,hi])=>saleList.filter(l=>l.price>=lo&&l.price<hi).length), PALETTE[0], false);
}

// ── Map tab ───────────────────────────────────────────────────────────────────
let leafletMap = null;
let markerLayer = null;
let choroLayer = null;
let districtGeoJson = null;

function initMap() {
  if (leafletMap) return;
  leafletMap = L.map('map').setView([40.4093, 49.8671], 11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution:'© OpenStreetMap', maxZoom:19 }).addTo(leafletMap);
  markerLayer = L.layerGroup().addTo(leafletMap);

  // Load GeoJSON
  fetch('districts.geojson').then(r => r.ok ? r.json() : null).catch(()=>null).then(d => {
    districtGeoJson = d;
    if (activeTab === 'map') renderMap();
  });

  // View mode buttons
  document.getElementById('btn-markers').addEventListener('click', () => {
    viewMode = 'markers';
    document.getElementById('btn-markers').classList.add('active');
    document.getElementById('btn-choropleth').classList.remove('active');
    renderMap(); pushState();
  });
  document.getElementById('btn-choropleth').addEventListener('click', () => {
    viewMode = 'choropleth';
    document.getElementById('btn-choropleth').classList.add('active');
    document.getElementById('btn-markers').classList.remove('active');
    renderMap(); pushState();
  });
}

function renderMap() {
  if (!leafletMap) return;
  const list = getFiltered();
  if (viewMode === 'markers') renderMarkers(list);
  else renderChoropleth(list);
}

function renderMarkers(list) {
  if (choroLayer) { leafletMap.removeLayer(choroLayer); choroLayer = null; }
  document.getElementById('choropleth-legend').classList.remove('visible');
  document.getElementById('marker-legend').style.display = '';
  markerLayer.clearLayers();
  const withCoords = list.filter(l => l.lat != null && l.lng != null);
  withCoords.forEach(l => {
    const color = CAT_COLORS[l.category] || '#6366f1';
    const marker = L.circleMarker([l.lat,l.lng], {radius:7,fillColor:color,fillOpacity:0.85,color:'#fff',weight:1.5});
    const m2 = ppm2(l), area = areaVal(l);
    const det = [l.rooms, area?`${area} m²`:'', l.land_area_sot?`${l.land_area_sot} sot`:''].filter(Boolean).join(' · ');
    const agencyBadge = l.is_agency===true ? '<span class="popup-badge popup-agency">Agentlik</span>' : l.is_agency===false ? '<span class="popup-badge popup-owner">Mülkiyyətçi</span>' : '';
    marker.bindPopup(`${l.photo_url?`<img class="popup-photo" src="${l.photo_url}" onerror="this.style.display='none'">`:''}
<div class="popup-price">${l.price?formatPrice(l.price,l.deal_type):'—'}</div>
${m2?`<div class="popup-ppm2">${fmt(m2)} ₼/m²</div>`:''}
${l.location?`<div class="popup-loc">${l.location}</div>`:''}
${det?`<div class="popup-det">${det}</div>`:''}${agencyBadge}
<a class="popup-link" href="${l.url}" target="_blank" rel="noopener">bina.az-da aç →</a>`, {maxWidth:220});
    markerLayer.addLayer(marker);
  });
  document.getElementById('map-stats').textContent = `${withCoords.length.toLocaleString()} elan xəritədə`;
}

function renderChoropleth(list) {
  markerLayer.clearLayers();
  document.getElementById('marker-legend').style.display = 'none';
  document.getElementById('choropleth-legend').classList.add('visible');
  if (choroLayer) { leafletMap.removeLayer(choroLayer); choroLayer = null; }
  if (!districtGeoJson) { document.getElementById('map-stats').textContent = 'GeoJSON yüklənmədi'; return; }

  const buckets = {};
  list.filter(l=>!l.deleted_at).forEach(l => {
    const v = ppm2(l); if (!v) return;
    const k = normName(l.location_name||l.location); if (!k) return;
    if (!buckets[k]) buckets[k] = [];
    buckets[k].push(v);
  });
  const avgs = {};
  Object.entries(buckets).forEach(([k,vals]) => { if(vals.length>=2) avgs[k]=vals.reduce((a,b)=>a+b,0)/vals.length; });
  const sorted = Object.values(avgs).sort((a,b)=>a-b);
  const q = p => sorted[Math.min(Math.floor(p*sorted.length), sorted.length-1)];
  if (sorted.length >= 5) {
    ['choro-l1','choro-l2','choro-l3','choro-l4','choro-l5'].forEach((id,i) => {
      const el = document.getElementById(id);
      if (el) el.textContent = i<4 ? `≤ ${fmt(q((i+1)*0.2))} ₼/m²` : `> ${fmt(q(0.8))} ₼/m²`;
    });
  }
  const matchDist = name => {
    const fn = normName(name);
    if (avgs[fn] !== undefined) return avgs[fn];
    for (const [k,v] of Object.entries(avgs)) { if(fn.includes(k)||k.includes(fn)) return v; }
    return null;
  };
  const colorFor = v => {
    if (!v||!sorted.length) return '#e5e7eb';
    const pct = sorted.filter(x=>x<=v).length/sorted.length;
    return CHORO_COLORS[pct<=0.2?0:pct<=0.4?1:pct<=0.6?2:pct<=0.8?3:4];
  };
  choroLayer = L.geoJSON(districtGeoJson, {
    style: f => { const avg=matchDist(f.properties.name); return {fillColor:colorFor(avg),fillOpacity:0.65,color:'#94a3b8',weight:1.5}; },
    onEachFeature: (f, layer) => {
      const avg = matchDist(f.properties.name);
      const label = avg ? `<b>${f.properties.name}</b><br>Orta ₼/m²: ${fmt(avg)} ₼` : `<b>${f.properties.name}</b><br>Məlumat yoxdur`;
      layer.on({
        mouseover: e => { e.target.setStyle({fillOpacity:0.85,weight:2.5,color:'#1a1a2e'}); layer.bindTooltip(label,{className:'district-tooltip',sticky:true}).openTooltip(e.latlng); },
        mouseout: e => { choroLayer.resetStyle(e.target); layer.closeTooltip(); },
      });
    },
  });
  choroLayer.addTo(leafletMap);
  document.getElementById('map-stats').textContent = `${list.length.toLocaleString()} elan, ${districtGeoJson.features.length} rayon`;
}

// ── Location multiselect ──────────────────────────────────────────────────────
function buildLocationDropdown(searchVal = '') {
  const listEl = document.getElementById('ms-list'); if (!listEl) return;
  const fromData = allListings.map(l => l.location||'').filter(Boolean);
  const locs = [...new Set([...ALL_LOCATIONS,...fromData])].sort();
  const q = searchVal.toLowerCase();
  const visible = q ? locs.filter(l=>l.toLowerCase().includes(q)) : locs;
  if (!visible.length) { listEl.innerHTML = '<div class="ms-empty">Nəticə yoxdur</div>'; return; }
  listEl.innerHTML = visible.map(loc => `<label class="ms-item"><input type="checkbox" value="${esc(loc)}" ${selLocs.has(loc)?'checked':''}><span>${esc(loc)}</span></label>`).join('');
  listEl.querySelectorAll('input[type=checkbox]').forEach(cb => {
    cb.addEventListener('change', () => { if(cb.checked) selLocs.add(cb.value); else selLocs.delete(cb.value); updateMsLabel(); applyFilters(); });
  });
}
function updateMsLabel() {
  const btn = document.getElementById('ms-btn'), label = document.getElementById('ms-label');
  if (selLocs.size===0) { label.textContent='Bütün məkanlar'; btn.classList.remove('has-selection'); }
  else { label.textContent=`${selLocs.size} məkan seçildi`; btn.classList.add('has-selection'); }
}

document.getElementById('ms-btn').addEventListener('click', e => {
  e.stopPropagation();
  const dd = document.getElementById('ms-dropdown');
  dd.classList.toggle('open');
  if (dd.classList.contains('open')) document.getElementById('ms-search').focus();
});
document.addEventListener('click', e => {
  if (!document.getElementById('ms-wrap').contains(e.target)) document.getElementById('ms-dropdown').classList.remove('open');
});
document.getElementById('ms-search').addEventListener('input', e => buildLocationDropdown(e.target.value));
document.getElementById('ms-all').addEventListener('click', () => {
  [...new Set([...ALL_LOCATIONS,...allListings.map(l=>l.location||'').filter(Boolean)])].forEach(l=>selLocs.add(l));
  buildLocationDropdown(); updateMsLabel(); applyFilters();
});
document.getElementById('ms-none').addEventListener('click', () => {
  selLocs.clear(); buildLocationDropdown(); updateMsLabel(); applyFilters();
});

// ── Event wiring ──────────────────────────────────────────────────────────────
document.getElementById('cat-chips').addEventListener('click', e => {
  const btn = e.target.closest('.chip'); if (!btn) return;
  document.querySelectorAll('#cat-chips .chip').forEach(c=>c.classList.remove('active'));
  btn.classList.add('active'); selCat = btn.dataset.cat;
  selLocs.clear(); updateMsLabel(); loadAll();
});
document.getElementById('type-chips').addEventListener('click', e => {
  const btn = e.target.closest('.chip'); if (!btn) return;
  document.querySelectorAll('#type-chips .chip').forEach(c=>c.classList.remove('active'));
  btn.classList.add('active'); selType = btn.dataset.type;
  selLocs.clear(); updateMsLabel(); loadAll();
});
document.getElementById('sort').addEventListener('change', e => { sort = e.target.value; applyFilters(); });
document.getElementById('show-deleted').addEventListener('change', e => { showDel = e.target.checked; applyFilters(); });
['price-min','price-max','area-min','area-max','sot-min','sot-max','ppm2-min','ppm2-max'].forEach(id => document.getElementById(id)?.addEventListener('input', applyFilters));
['rooms-filter','repair-filter','agency-filter','kupca-filter'].forEach(id => document.getElementById(id)?.addEventListener('change', applyFilters));

document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => switchTab(t.dataset.tab)));

// ── URL search param sync ─────────────────────────────────────────────────────
function pushState() {
  const p = new URLSearchParams();
  if (activeTab !== 'listings') p.set('tab', activeTab);
  if (selCat   !== 'all')  p.set('cat',    selCat);
  if (selType  !== 'all')  p.set('type',   selType);
  if (sort     !== 'newest') p.set('sort', sort);
  if (showDel)             p.set('del',    '1');
  if (priceMin != null)    p.set('pmin',   priceMin);
  if (priceMax != null)    p.set('pmax',   priceMax);
  if (areaMin  != null)    p.set('amin',   areaMin);
  if (areaMax  != null)    p.set('amax',   areaMax);
  if (sotMin   != null)    p.set('smin',   sotMin);
  if (sotMax   != null)    p.set('smax',   sotMax);
  if (ppm2Min  != null)    p.set('mmin',   ppm2Min);
  if (ppm2Max  != null)    p.set('mmax',   ppm2Max);
  if (roomsF)              p.set('rooms',  roomsF);
  if (repairF)             p.set('repair', repairF);
  if (agencyF)             p.set('agency', agencyF);
  if (kupcaF)              p.set('kupca',  kupcaF);
  if (selLocs.size)        p.set('locs',   [...selLocs].join('|'));
  if (viewMode !== 'markers') p.set('view', viewMode);
  const str = p.toString();
  history.replaceState(null, '', str ? `?${str}` : location.pathname);
}

function restoreFromUrl() {
  const p = new URLSearchParams(location.search);
  const tab = p.get('tab'); if (tab) { activeTab = tab; }
  if (p.has('cat'))    selCat  = p.get('cat');
  if (p.has('type'))   selType = p.get('type');
  if (p.has('sort'))   sort    = p.get('sort');
  if (p.has('del'))    showDel = true;
  if (p.has('view'))   viewMode = p.get('view');
  if (p.has('locs'))   p.get('locs').split('|').filter(Boolean).forEach(l => selLocs.add(l));

  const restoreInput = (key, id) => { if (p.has(key)) document.getElementById(id) && (document.getElementById(id).value = p.get(key)); };
  restoreInput('pmin','price-min'); restoreInput('pmax','price-max');
  restoreInput('amin','area-min');  restoreInput('amax','area-max');
  restoreInput('smin','sot-min');   restoreInput('smax','sot-max');
  restoreInput('mmin','ppm2-min');  restoreInput('mmax','ppm2-max');
  restoreInput('rooms','rooms-filter'); restoreInput('repair','repair-filter');
  restoreInput('agency','agency-filter'); restoreInput('kupca','kupca-filter');
  if (showDel) document.getElementById('show-deleted').checked = true;

  document.querySelectorAll('#cat-chips .chip').forEach(c => c.classList.toggle('active', c.dataset.cat === selCat));
  document.querySelectorAll('#type-chips .chip').forEach(c => c.classList.toggle('active', c.dataset.type === selType));
  document.getElementById('sort').value = sort;
  updateMsLabel();

  // Apply tab
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === activeTab));
  document.querySelectorAll('.tab-content').forEach(s => s.style.display = 'none');
  document.getElementById(`tab-${activeTab}`).style.display = '';
  document.getElementById('listings-filters-row').style.display = activeTab === 'listings' ? '' : 'none';

  // View mode buttons
  document.getElementById('btn-markers').classList.toggle('active', viewMode === 'markers');
  document.getElementById('btn-choropleth').classList.toggle('active', viewMode === 'choropleth');
}

// ── Boot ──────────────────────────────────────────────────────────────────────
restoreFromUrl();
if (activeTab === 'map') initMap();
loadAll();
