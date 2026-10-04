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

const ALL_LOCATIONS = ['20 Yanvar m.','20-ci sahə q.','28 May m.','9-cu mikrorayon q.','Azadlıq Prospekti m.','Ağ şəhər q.','Badamdar q.','Bakıxanov q.','Bayıl q.','Bilgəh q.','Biləcəri q.','Binə q.','Binəqədi q.','Binəqədi r.','Buzovna q.','Dübəndi q.','Elmlər Akademiyası m.','Görədil q.','Gənclik m.','Hökməli q.','Hövsan q.','Həzi Aslanov m.','Həzi Aslanov q.','Koroğlu m.','Lökbatan q.','M.Ə.Rəsulzadə q.','Masazır q.','Mehdiabad q.','Memar Əcəmi m.','Məmmədli q.','Mərdəkan q.','Nardaran q.','Neftçilər m.','Nizami m.','Nizami r.','Novxanı q.','Nəriman Nərimanov m.','Nərimanov r.','Nəsimi r.','Qala q.','Qara Qarayev m.','Qaraçuxur q.','Qobu q.','Sahil q.','Saray q.','Sea Breeze q.','Türkan q.','Yasamal q.','Yasamal r.','Yeni Ramana q.','Yeni Yasamal q.','Zabrat q.','Zığ q.','İnşaatçılar m.','İçəri Şəhər m.','Şah İsmayıl Xətai m.','Şağan q.','Şüvəlan q.','Əhmədli m.','Ələt q.','Əmircan q.'];

// ── Shared state ──────────────────────────────────────────────────────────────
let selCat   = 'all';
let selType  = 'all';
let selLocs  = new Set();
let sort     = 'newest';
let showDel       = false;
let priceChangedF = false;
let page     = 1;
let priceMin = null, priceMax = null;
let areaMin  = null, areaMax  = null;
let sotMin   = null, sotMax   = null;
let ppm2Min  = null, ppm2Max  = null;
let scoreMin = null, scoreMax = null;
let roomsF   = new Set();
let repairF  = '';
let agencyF  = '';
let kupcaF   = '';
let activeTab   = 'listings';
let activeModal = null;

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
  maybeRestoreModal();
}

// ── Filtering ─────────────────────────────────────────────────────────────────
function num(id) { const v = parseFloat(document.getElementById(id)?.value); return isNaN(v) ? null : v; }

function getFiltered() {
  priceMin = num('price-min'); priceMax = num('price-max');
  areaMin  = num('area-min');  areaMax  = num('area-max');
  sotMin   = num('sot-min');   sotMax   = num('sot-max');
  ppm2Min  = num('ppm2-min');  ppm2Max  = num('ppm2-max');
  roomsF   = new Set([...document.querySelectorAll('#room-chips .room-chip.active')].map(b => b.dataset.room));
  repairF  = document.getElementById('repair-filter')?.value || '';
  agencyF  = document.getElementById('agency-filter')?.value || '';
  kupcaF   = document.getElementById('kupca-filter')?.value || '';
  showDel       = document.getElementById('show-deleted')?.checked || false;
  priceChangedF = document.getElementById('price-changed')?.checked || false;

  let list = showDel ? allListings : allListings.filter(l => !l.deleted_at);
  if (priceChangedF) list = list.filter(l => (l.price_history || []).length > 1);
  if (selLocs.size) list = list.filter(l => selLocs.has(l.location || l.location_name || ''));
  if (priceMin != null) list = list.filter(l => l.price != null && l.price >= priceMin);
  if (priceMax != null) list = list.filter(l => l.price != null && l.price <= priceMax);
  if (areaMin  != null) list = list.filter(l => { const a = areaVal(l); return a != null && a >= areaMin; });
  if (areaMax  != null) list = list.filter(l => { const a = areaVal(l); return a != null && a <= areaMax; });
  if (sotMin   != null) list = list.filter(l => l.land_area_sot != null && l.land_area_sot >= sotMin);
  if (sotMax   != null) list = list.filter(l => l.land_area_sot != null && l.land_area_sot <= sotMax);
  if (ppm2Min  != null) list = list.filter(l => { const v = ppm2(l); return v != null && v >= ppm2Min; });
  if (ppm2Max  != null) list = list.filter(l => { const v = ppm2(l); return v != null && v <= ppm2Max; });
  if (roomsF.size) {
    list = list.filter(l => {
      const r = roomCount(l);
      if (r == null) return false;
      return (roomsF.has('5') && r >= 5) || [...roomsF].some(v => v !== '5' && parseInt(v) === r);
    });
  }
  if (repairF === 'yes') list = list.filter(l => l.has_repair === true);
  if (repairF === 'no')  list = list.filter(l => l.has_repair === false);
  if (agencyF === 'agency') list = list.filter(l => l.is_agency === true);
  if (agencyF === 'owner')  list = list.filter(l => l.is_agency === false);
  if (kupcaF  === 'yes') list = list.filter(l => l.has_bill_of_sale === true);
  if (kupcaF  === 'no')  list = list.filter(l => l.has_bill_of_sale === false);
  return list;
}

// ── Deal scoring ──────────────────────────────────────────────────────────────
const RENOVATION_COST_PER_M2 = 200;

function _pctRank(vals, lowerIsBetter) {
  const n = vals.length;
  const valid = vals.map((v, i) => v != null ? [i, v] : null).filter(Boolean);
  const out = new Array(n).fill(null);
  if (valid.length <= 1) { valid.forEach(([i]) => out[i] = 0.5); return out; }
  valid.sort((a, b) => a[1] - b[1]);
  valid.forEach(([i], rank) => { out[i] = rank / (valid.length - 1); });
  return lowerIsBetter ? out.map(v => v != null ? 1 - v : null) : out;
}

function computeScores(listings) {
  const groups = {};
  listings.forEach((l, i) => {
    const key = `${l.category}_${l.deal_type}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(i);
  });

  Object.values(groups).forEach(idxs => {
    const group = idxs.map(i => listings[i]);

    const ppm2vals = group.map(l => {
      const a = areaVal(l);
      if (!a || !l.price) return null;
      const reno = l.has_repair === false ? RENOVATION_COST_PER_M2 * a : 0;
      return (l.price + reno) / a;
    });
    const ppsotvars = group.map(l =>
      l.price && l.land_area_sot ? l.price / l.land_area_sot : null
    );
    const ppm2Pct  = _pctRank(ppm2vals,  true);
    const ppsotPct = _pctRank(ppsotvars, true);

    group.forEach((l, gi) => {
      let score = 0;
      const cat    = l.category;
      const isSale = l.deal_type === 'sale';
      const ownerPts = l.is_agency === false ? 1.0 : l.is_agency === true ? 0.0 : 0.5;
      const h = l.price_history || [];
      const dropped = h.length >= 2 && h[h.length - 1].price < h[0].price;

      if (cat === 'apartment') {
        if (ppm2Pct[gi]  != null) score += 50 * ppm2Pct[gi];
        if (l.building_type === 'Yeni tikili') score += 20;
        else if (l.building_type === 'Köhnə tikili') score += 5;
        score += 15 * ownerPts;
        if (dropped) score += 10;
        if (isSale && l.has_bill_of_sale === true) score += 5;

      } else if (cat === 'house') {
        if (ppm2Pct[gi]  != null) score += 35 * ppm2Pct[gi];
        if (ppsotPct[gi] != null) score += 30 * ppsotPct[gi];
        score += 15 * ownerPts;
        if (dropped) score += 15;
        if (isSale && l.has_bill_of_sale === true) score += 5;

      } else if (cat === 'land') {
        if (ppsotPct[gi] != null) score += 70 * ppsotPct[gi];
        else if (ppm2Pct[gi] != null) score += 70 * ppm2Pct[gi];
        score += 15 * ownerPts;
        if (dropped) score += 10;
        if (isSale && l.has_bill_of_sale === true) score += 5;

      } else if (cat === 'commercial' || cat === 'office') {
        if (ppm2Pct[gi]  != null) score += 55 * ppm2Pct[gi];
        score += 20 * ownerPts;
        if (dropped) score += 15;
        if (isSale && l.has_bill_of_sale === true) score += 10;

      } else if (cat === 'garage') {
        if (ppm2Pct[gi]  != null) score += 65 * ppm2Pct[gi];
        score += 25 * ownerPts;
        if (dropped) score += 10;
      }

      l._score = Math.round(Math.min(100, score));
    });
  });
}

function scoreClass(s) {
  if (s == null) return '';
  if (s >= 75) return 'score-high';
  if (s >= 50) return 'score-mid';
  return 'score-low';
}

function applyFilters() {
  scoreMin = num('score-min'); scoreMax = num('score-max');
  const list = getFiltered();
  computeScores(list);
  const scored = (scoreMin != null || scoreMax != null)
    ? list.filter(l => {
        const s = l._score ?? 0;
        if (scoreMin != null && s < scoreMin) return false;
        if (scoreMax != null && s > scoreMax) return false;
        return true;
      })
    : list;
  filtered = scored.sort((a, b) => {
    switch (sort) {
      case 'score_desc': return (b._score||0) - (a._score||0);
      case 'score_asc':  return (a._score||0) - (b._score||0);
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
    grid.innerHTML = slice.map((l, i) => cardHTML(l, i)).join('');
  }

  const active = filtered.filter(l => !l.deleted_at).length;
  statsBar.textContent = showDel
    ? `${filtered.length} nəticə (${active} aktiv, ${filtered.length-active} silinmiş)`
    : `${filtered.length} aktiv elan`;
  glStats.textContent = `${allListings.length.toLocaleString()} elan yükləndi`;

  renderPagination();
}

function cardHTML(l, idx) {
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
  const scoreBadge = l._score != null
    ? `<span class="badge badge-score ${scoreClass(l._score)}">${l._score}</span>` : '';
  const badges = [
    scoreBadge,
    l.has_repair ? '<span class="badge badge-repair">✓ Təmirli</span>' : '',
    l.is_agency  ? '<span class="badge badge-agency">Agentlik</span>' : '<span class="badge badge-owner">Mülkiyyətçi</span>',
    l.deleted_at ? '<span class="badge badge-deleted">Silinib</span>' : '',
    selCat === 'all' ? `<span class="badge badge-cat">${catLabel(l.category)}</span>` : '',
  ].filter(Boolean).join('');
  return `<div class="card${l.deleted_at?' deleted':''}" data-idx="${idx}">
  <div class="card-photo-wrap">${photo}</div>
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
let districtLayer = null;
let districtGeoJson = null;
let mapMode = 'markers'; // 'markers' | 'districts'
let activeRayons = new Set(); // empty = all visible

const DISTRICT_COLORS = [
  '#6366f1','#f59e0b','#10b981','#ef4444','#06b6d4',
  '#8b5cf6','#ec4899','#f97316','#84cc16','#14b8a6',
  '#f43f5e','#a855f7',
];

function initMap() {
  if (leafletMap) return;
  leafletMap = L.map('map').setView([40.4093, 49.8671], 11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution:'© OpenStreetMap', maxZoom:19 }).addTo(leafletMap);
  markerLayer = L.layerGroup().addTo(leafletMap);

  // Restore map mode button state
  document.getElementById('btn-markers').classList.toggle('active', mapMode === 'markers');
  document.getElementById('btn-districts').classList.toggle('active', mapMode === 'districts');
  document.getElementById('rayon-panel').style.display = mapMode === 'districts' ? '' : 'none';

  fetch('districts.geojson').then(r => r.ok ? r.json() : null).catch(() => null).then(d => {
    districtGeoJson = d;
    buildRayonPanel();
    if (mapMode === 'districts') renderDistricts();
  });

  document.getElementById('btn-markers').addEventListener('click', () => {
    mapMode = 'markers';
    document.getElementById('btn-markers').classList.add('active');
    document.getElementById('btn-districts').classList.remove('active');
    document.getElementById('rayon-panel').style.display = 'none';
    renderMap(); pushState();
  });
  document.getElementById('btn-districts').addEventListener('click', () => {
    mapMode = 'districts';
    document.getElementById('btn-districts').classList.add('active');
    document.getElementById('btn-markers').classList.remove('active');
    document.getElementById('rayon-panel').style.display = '';
    renderMap(); pushState();
  });
}

function renderMap() {
  if (!leafletMap) return;
  if (mapMode === 'districts') renderDistricts();
  else renderMarkers(filtered);
}

function buildRayonPanel() {
  const panel = document.getElementById('rayon-panel');
  if (!districtGeoJson) return;
  panel.innerHTML = districtGeoJson.features.map((f, idx) => {
    const name = f.properties.name;
    const color = DISTRICT_COLORS[idx % DISTRICT_COLORS.length];
    return `<div class="rayon-item" data-rayon="${esc(name)}">
      <div class="rayon-swatch" style="background:${color}"></div>
      <span>${esc(name)}</span>
    </div>`;
  }).join('');
  panel.querySelectorAll('.rayon-item').forEach(item => {
    if (activeRayons.has(item.dataset.rayon)) item.classList.add('active');
    item.addEventListener('click', () => {
      const name = item.dataset.rayon;
      if (activeRayons.has(name)) {
        activeRayons.delete(name);
        item.classList.remove('active');
      } else {
        activeRayons.add(name);
        item.classList.add('active');
      }
      renderDistricts();
      pushState();
    });
  });
}

function renderDistricts() {
  markerLayer.clearLayers();
  if (districtLayer) { leafletMap.removeLayer(districtLayer); districtLayer = null; }
  if (!districtGeoJson) { document.getElementById('map-stats').textContent = 'Rayonlar yüklənir…'; return; }

  const showAll = activeRayons.size === 0;

  districtLayer = L.geoJSON(districtGeoJson, {
    filter: f => showAll || activeRayons.has(f.properties.name),
    style: f => {
      const idx = districtGeoJson.features.indexOf(f);
      const selected = !showAll && activeRayons.has(f.properties.name);
      const color = DISTRICT_COLORS[idx % DISTRICT_COLORS.length];
      return {
        fillColor: color,
        fillOpacity: selected ? 0.35 : showAll ? 0.15 : 0,
        color: selected ? color : DISTRICT_COLORS[idx % DISTRICT_COLORS.length],
        weight: selected ? 3 : 2,
        opacity: 0.9,
      };
    },
    onEachFeature: (f, layer) => {
      const name = f.properties.name;
      layer.bindTooltip(name, { permanent: false, className: 'district-tooltip', sticky: true });
      layer.on({
        mouseover: e => e.target.setStyle({ fillOpacity: 0.7, weight: 3 }),
        mouseout:  () => districtLayer.resetStyle(layer),
      });
    },
  }).addTo(leafletMap);

  const shown = showAll ? districtGeoJson.features.length : activeRayons.size;
  document.getElementById('map-stats').textContent = `${shown} rayon göstərilir`;

  // Add numbered vertex markers for selected rayons
  if (!showAll) {
    districtGeoJson.features.forEach(f => {
      if (!activeRayons.has(f.properties.name)) return;
      f.geometry.coordinates.forEach(poly => {
        poly[0].forEach((pt, i) => {
          if (i === poly[0].length - 1) return; // skip closing point
          L.marker([pt[1], pt[0]], {
            icon: L.divIcon({
              className: '',
              html: `<div style="background:#1a1a2e;color:#fff;font-size:9px;padding:1px 3px;border-radius:3px;white-space:nowrap;line-height:1.2">${i}</div>`,
              iconAnchor: [0, 0],
            }),
            interactive: false,
          }).addTo(districtLayer);
        });
      });
    });
  }
}

function renderMarkers(list) {
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
document.getElementById('price-changed').addEventListener('change', e => { priceChangedF = e.target.checked; applyFilters(); });
['price-min','price-max','area-min','area-max','sot-min','sot-max','ppm2-min','ppm2-max','score-min','score-max'].forEach(id => document.getElementById(id)?.addEventListener('input', applyFilters));
document.getElementById('room-chips').addEventListener('click', e => {
  const btn = e.target.closest('.room-chip'); if (!btn) return;
  btn.classList.toggle('active');
  applyFilters();
});
['repair-filter','agency-filter','kupca-filter'].forEach(id => document.getElementById(id)?.addEventListener('change', applyFilters));

document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => switchTab(t.dataset.tab)));

// ── URL search param sync ─────────────────────────────────────────────────────
function pushState() {
  const p = new URLSearchParams();
  if (activeTab !== 'listings') p.set('tab', activeTab);
  if (selCat   !== 'all')  p.set('cat',    selCat);
  if (selType  !== 'all')  p.set('type',   selType);
  if (sort     !== 'newest') p.set('sort', sort);
  if (showDel)             p.set('del',    '1');
  if (priceChangedF)       p.set('pchg',   '1');
  if (priceMin != null)    p.set('pmin',   priceMin);
  if (priceMax != null)    p.set('pmax',   priceMax);
  if (areaMin  != null)    p.set('amin',   areaMin);
  if (areaMax  != null)    p.set('amax',   areaMax);
  if (sotMin   != null)    p.set('smin',   sotMin);
  if (sotMax   != null)    p.set('smax',   sotMax);
  if (ppm2Min  != null)    p.set('mmin',   ppm2Min);
  if (ppm2Max  != null)    p.set('mmax',   ppm2Max);
  if (scoreMin != null)    p.set('smin',   scoreMin);
  if (scoreMax != null)    p.set('smax',   scoreMax);
  if (roomsF.size)         p.set('rooms',  [...roomsF].join(','));
  if (repairF)             p.set('repair', repairF);
  if (agencyF)             p.set('agency', agencyF);
  if (kupcaF)              p.set('kupca',  kupcaF);
  if (selLocs.size)        p.set('locs',   [...selLocs].join('|'));
  if (activeModal)            p.set('modal', activeModal);
  if (mapMode !== 'markers')  p.set('mview', mapMode);
  if (activeRayons.size)      p.set('rayons', [...activeRayons].join('|'));
  const str = p.toString();
  history.replaceState(null, '', str ? `?${str}` : location.pathname);
}

function restoreFromUrl() {
  const p = new URLSearchParams(location.search);
  const tab = p.get('tab'); if (tab) { activeTab = tab; }
  if (p.has('cat'))    selCat  = p.get('cat');
  if (p.has('type'))   selType = p.get('type');
  if (p.has('sort'))   sort    = p.get('sort');
  if (p.has('del'))    showDel       = true;
  if (p.has('pchg'))   priceChangedF = true;
  if (p.has('modal'))  activeModal = p.get('modal');
  if (p.has('mview'))  mapMode     = p.get('mview');
  if (p.has('rayons')) p.get('rayons').split('|').filter(Boolean).forEach(r => activeRayons.add(r));
  if (p.has('locs'))   p.get('locs').split('|').filter(Boolean).forEach(l => selLocs.add(l));

  const restoreInput = (key, id) => { if (p.has(key)) document.getElementById(id) && (document.getElementById(id).value = p.get(key)); };
  restoreInput('pmin','price-min'); restoreInput('pmax','price-max');
  restoreInput('amin','area-min');  restoreInput('amax','area-max');
  restoreInput('smin','sot-min');   restoreInput('smax','sot-max');
  restoreInput('mmin','ppm2-min');  restoreInput('mmax','ppm2-max');
  restoreInput('smin','score-min'); restoreInput('smax','score-max');
  if (p.has('rooms')) {
    p.get('rooms').split(',').filter(Boolean).forEach(v => {
      roomsF.add(v);
      const btn = document.querySelector(`#room-chips .room-chip[data-room="${v}"]`);
      if (btn) btn.classList.add('active');
    });
  }
  restoreInput('repair','repair-filter');
  restoreInput('agency','agency-filter'); restoreInput('kupca','kupca-filter');
  if (showDel)        document.getElementById('show-deleted').checked  = true;
  if (priceChangedF)  document.getElementById('price-changed').checked = true;

  document.querySelectorAll('#cat-chips .chip').forEach(c => c.classList.toggle('active', c.dataset.cat === selCat));
  document.querySelectorAll('#type-chips .chip').forEach(c => c.classList.toggle('active', c.dataset.type === selType));
  document.getElementById('sort').value = sort;
  updateMsLabel();

  // Apply tab
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === activeTab));
  document.querySelectorAll('.tab-content').forEach(s => s.style.display = 'none');
  document.getElementById(`tab-${activeTab}`).style.display = '';
  document.getElementById('listings-filters-row').style.display = activeTab === 'listings' ? '' : 'none';

}

// ── Detail modal ──────────────────────────────────────────────────────────────
let modalChart = null;

function openModal(l) {
  const overlay = document.getElementById('modal-overlay');
  const inner   = document.getElementById('modal-inner');

  if (modalChart) { modalChart.destroy(); modalChart = null; }

  const change = priceChange(l);
  let changeBadge = '';
  if (change !== null) {
    const abs = fmt(Math.abs(change));
    changeBadge = change < 0
      ? `<span class="modal-price-drop">↓ ${abs} ₼</span>`
      : `<span class="modal-price-rise">↑ ${abs} ₼</span>`;
  }

  const m2 = ppm2(l), area = areaVal(l);
  const ppm2Str = m2 ? `<span class="modal-ppm2">${fmt(m2)} ₼/m²</span>` : '';

  const photo = l.photo_url
    ? `<img class="modal-photo" src="${esc(l.photo_url)}" alt="" onerror="this.outerHTML='<div class=modal-photo-placeholder>🏠</div>'">`
    : '<div class="modal-photo-placeholder">🏠</div>';

  const specs = [];
  if (l.rooms)          specs.push(esc(l.rooms));
  if (area)             specs.push(`${area} m²`);
  if (l.land_area_sot)  specs.push(`${l.land_area_sot} sot`);
  if (l.floor)          specs.push(esc(l.floor));
  if (l.building_type)  specs.push(esc(l.building_type));
  if (l.deal_type)      specs.push(l.deal_type === 'rental' ? 'Kirayə' : 'Satış');

  const specsHTML = specs.map(s => `<span class="modal-spec">${s}</span>`).join('');

  const modalScore = l._score != null
    ? `<span class="badge badge-score ${scoreClass(l._score)} badge-score-lg">Reytinq: ${l._score}/100</span>` : '';
  const badges = [
    modalScore,
    l.has_repair         ? '<span class="badge badge-repair">✓ Təmirli</span>'      : '',
    l.is_agency === true ? '<span class="badge badge-agency">Agentlik</span>'        : '',
    l.is_agency === false? '<span class="badge badge-owner">Mülkiyyətçi</span>'     : '',
    l.has_bill_of_sale   ? '<span class="badge badge-repair">✓ Çıxarış var</span>'  : '',
    l.has_mortgage       ? '<span class="badge badge-cat">Ipoteka</span>'            : '',
    l.deleted_at         ? '<span class="badge badge-deleted">Silinib</span>'        : '',
    `<span class="badge badge-cat">${catLabel(l.category)}</span>`,
  ].filter(Boolean).join('');

  const title = l.title ? `<div class="modal-title">${esc(l.title)}</div>` : '';
  const desc  = l.description ? `<div class="modal-description">${esc(l.description)}</div>` : '';

  const loc = l.location_name || l.location || '';

  const metaParts = [];
  if (l.updated_at_site) metaParts.push(`Yenilənib: ${fmtDate(l.updated_at_site)}`);
  if (l.id)              metaParts.push(`ID: ${l.id}`);
  const metaHTML = metaParts.length ? `<div class="modal-meta">${metaParts.map(esc).join('<span>·</span>')}</div>` : '';

  const mapsLink = l.lat && l.lng
    ? `<a class="modal-link modal-link-secondary" href="https://www.google.com/maps?q=${l.lat},${l.lng}" target="_blank" rel="noopener">📍 Xəritədə aç</a>`
    : '';

  const history = l.price_history || [];
  const historyHtml = history.length
    ? `<div class="modal-history-title">Qiymət tarixi</div>
       ${history.length > 1 ? '<div class="modal-history-chart"><canvas id="modal-price-chart"></canvas></div>' : ''}
       <table class="modal-history-table">
         <thead><tr><th>Tarix</th><th>Qiymət</th><th>Dəyişiklik</th></tr></thead>
         <tbody>${history.map((h, i) => {
           const prev = i > 0 ? history[i-1].price : null;
           const diff = prev != null ? h.price - prev : null;
           let diffCell = '<td>—</td>';
           if (diff !== null && diff !== 0) {
             const cls = diff < 0 ? 'change-down' : 'change-up';
             const sign = diff < 0 ? '↓' : '↑';
             diffCell = `<td class="${cls}">${sign} ${fmt(Math.abs(diff))} ₼</td>`;
           }
           return `<tr><td>${fmtDate(h.date)}</td><td>${fmt(h.price)} ₼</td>${diffCell}</tr>`;
         }).join('')}</tbody>
       </table>`
    : '';

  inner.innerHTML = `
    ${photo}
    ${title}
    <div class="modal-price-row">
      <span class="modal-price">${formatPrice(l.price, l.deal_type)}</span>
      ${ppm2Str}
      ${changeBadge}
    </div>
    ${loc ? `<div class="modal-location">📍 ${esc(loc)}</div>` : ''}
    ${specsHTML ? `<div class="modal-specs">${specsHTML}</div>` : ''}
    ${badges   ? `<div class="modal-badges">${badges}</div>` : ''}
    ${desc}
    ${metaHTML}
    ${historyHtml}
    <div class="modal-links">
      <a class="modal-link modal-link-primary" href="${esc(l.url)}" target="_blank" rel="noopener">bina.az-da aç →</a>
      ${mapsLink}
    </div>`;

  activeModal = l.id;
  pushState();
  overlay.style.display = 'flex';
  document.body.style.overflow = 'hidden';

  if (history.length > 1) {
    const ctx = document.getElementById('modal-price-chart');
    if (ctx) {
      const labels = history.map(h => {
        const d = new Date(h.date);
        return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()}`;
      });
      const data = history.map(h => h.price);
      modalChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            data,
            borderColor: '#6366f1',
            backgroundColor: 'rgba(99,102,241,.08)',
            pointBackgroundColor: '#6366f1',
            pointRadius: 5,
            tension: 0.3,
            fill: true,
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 11 } } },
            y: { grid: { color: '#f0f2f5' }, ticks: { font: { size: 11 }, callback: v => `${fmt(v)} ₼` } }
          }
        }
      });
    }
  }
}

function closeModal() {
  document.getElementById('modal-overlay').style.display = 'none';
  document.body.style.overflow = '';
  if (modalChart) { modalChart.destroy(); modalChart = null; }
  activeModal = null;
  pushState();
}

async function maybeRestoreModal() {
  if (!activeModal) return;

  // Search already-loaded listings first (respects current cat/type selection)
  let listing = allListings.find(l => l.id === activeModal);

  // Search other cached files
  if (!listing) {
    for (const arr of Object.values(cache)) {
      listing = arr.find(l => l.id === activeModal);
      if (listing) break;
    }
  }

  // Load every file and search
  if (!listing) {
    const all = (await Promise.all(
      CATS.flatMap(c => FILES[c].map(t => loadFile(c, t)))
    )).flat();
    listing = all.find(l => l.id === activeModal);
  }

  if (listing) openModal(listing);
}

document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('modal-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('modal-overlay')) closeModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

document.getElementById('grid').addEventListener('click', e => {
  const link = e.target.closest('a');
  if (link) return;
  const card = e.target.closest('.card');
  if (!card) return;
  const idx = parseInt(card.dataset.idx, 10);
  if (isNaN(idx)) return;
  const slice = filtered.slice((page-1)*PAGE_SIZE, page*PAGE_SIZE);
  const listing = slice[idx];
  if (listing) openModal(listing);
});

// ── Boot ──────────────────────────────────────────────────────────────────────
restoreFromUrl();
if (activeTab === 'map') initMap();
loadAll();
