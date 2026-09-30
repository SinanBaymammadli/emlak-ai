const FILES = {
  apartment: ['sale','rental'],
  house:     ['sale','rental'],
  land:      ['sale'],
  commercial:['sale','rental'],
  office:    ['sale','rental'],
  garage:    ['sale','rental'],
};
const CATS = Object.keys(FILES);
const PAGE_SIZE = 50;

// State
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

const cache = {};
let allListings = [];
let filtered    = [];
let loading     = false;

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmt(n) {
  if (n == null) return '—';
  return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
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
  const prev = h[h.length - 2].price;
  const curr = h[h.length - 1].price;
  return prev === curr ? null : curr - prev;
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function catLabel(cat) {
  return {apartment:'Mənzil',house:'Həyət evi',land:'Torpaq',commercial:'Kommersiya',office:'Ofis',garage:'Qaraj'}[cat]||cat;
}

// ── Data loading ──────────────────────────────────────────────────────────────

async function loadFile(cat, type) {
  const key = `${cat}_${type}`;
  if (cache[key]) return cache[key];
  try {
    const res = await fetch(`data/${cat}_${type}.json`);
    if (!res.ok) throw new Error(res.status);
    cache[key] = await res.json();
  } catch(e) {
    cache[key] = [];
  }
  return cache[key];
}

async function loadAll() {
  loading = true;
  renderGrid();

  const pairs = [];
  (selCat === 'all' ? CATS : [selCat]).forEach(c => {
    (FILES[c] || []).forEach(t => {
      if (selType === 'all' || selType === t) pairs.push([c, t]);
    });
  });

  allListings = (await Promise.all(pairs.map(([c,t]) => loadFile(c,t)))).flat();
  loading = false;
  buildLocationDropdown();
  applyFilters();
}

// ── Filtering ─────────────────────────────────────────────────────────────────

function num(id) {
  const v = parseFloat(document.getElementById(id).value);
  return isNaN(v) ? null : v;
}

function applyFilters() {
  priceMin = num('price-min'); priceMax = num('price-max');
  areaMin  = num('area-min');  areaMax  = num('area-max');
  sotMin   = num('sot-min');   sotMax   = num('sot-max');
  ppm2Min  = num('ppm2-min');  ppm2Max  = num('ppm2-max');
  roomsF   = document.getElementById('rooms-filter').value;
  repairF  = document.getElementById('repair-filter').value;
  agencyF  = document.getElementById('agency-filter').value;

  let list = allListings;

  if (!showDel) list = list.filter(l => !l.deleted_at);
  if (selLocs.size > 0) list = list.filter(l => selLocs.has(l.location || ''));
  if (priceMin != null) list = list.filter(l => l.price != null && l.price >= priceMin);
  if (priceMax != null) list = list.filter(l => l.price != null && l.price <= priceMax);
  if (areaMin  != null) list = list.filter(l => { const a = areaVal(l); return a != null && a >= areaMin; });
  if (areaMax  != null) list = list.filter(l => { const a = areaVal(l); return a != null && a <= areaMax; });
  if (sotMin   != null) list = list.filter(l => l.land_area_sot != null && l.land_area_sot >= sotMin);
  if (sotMax   != null) list = list.filter(l => l.land_area_sot != null && l.land_area_sot <= sotMax);
  if (ppm2Min  != null) list = list.filter(l => { const v = ppm2(l); return v != null && v >= ppm2Min; });
  if (ppm2Max  != null) list = list.filter(l => { const v = ppm2(l); return v != null && v <= ppm2Max; });

  if (roomsF) {
    if (roomsF === '5') {
      list = list.filter(l => { const r = roomCount(l); return r != null && r >= 5; });
    } else {
      const n = parseInt(roomsF);
      list = list.filter(l => roomCount(l) === n);
    }
  }

  if (repairF  === 'yes')    list = list.filter(l => l.has_repair === true);
  if (repairF  === 'no')     list = list.filter(l => l.has_repair === false);
  if (agencyF  === 'agency') list = list.filter(l => l.is_agency === true);
  if (agencyF  === 'owner')  list = list.filter(l => l.is_agency === false);

  list = [...list].sort((a, b) => {
    switch (sort) {
      case 'newest':     return new Date(b.last_seen_at) - new Date(a.last_seen_at);
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

  filtered = list;
  page = 1;
  updateStats();
  renderGrid();
  renderPagination();
}

// ── Render ────────────────────────────────────────────────────────────────────

function renderGrid() {
  const grid = document.getElementById('grid');
  if (loading) {
    grid.innerHTML = `<div class="state-msg"><div class="spinner"></div>Yüklənir…</div>`;
    return;
  }
  const slice = filtered.slice((page-1)*PAGE_SIZE, page*PAGE_SIZE);
  if (!slice.length) {
    grid.innerHTML = `<div class="state-msg">Nəticə tapılmadı</div>`;
    return;
  }
  grid.innerHTML = slice.map(cardHTML).join('');
}

function cardHTML(l) {
  const change = priceChange(l);
  let changeBadge = '';
  if (change !== null) {
    const abs = fmt(Math.abs(change));
    changeBadge = change < 0
      ? `<span class="price-drop">↓ ${abs} ₼</span>`
      : `<span class="price-rise">↑ ${abs} ₼</span>`;
  }

  const photo = l.photo_url
    ? `<img src="${esc(l.photo_url)}" alt="" loading="lazy" onerror="this.parentElement.innerHTML='<div class=card-photo-placeholder>🏠</div>'">`
    : `<div class="card-photo-placeholder">🏠</div>`;

  const m2  = ppm2(l);
  const sot = ppsot(l);
  let unitPrice = '';
  if (m2)       unitPrice = `<div class="card-unit-price">${fmt(m2)} ₼/m²</div>`;
  else if (sot) unitPrice = `<div class="card-unit-price">${fmt(sot)} ₼/sot</div>`;

  const area = areaVal(l);
  const details = [
    l.rooms || '',
    area ? `${area} m²` : '',
    l.land_area_sot ? `${l.land_area_sot} sot` : '',
  ].filter(Boolean).join(' · ');

  const badges = [
    l.has_repair ? `<span class="badge badge-repair">✓ Təmirli</span>` : '',
    l.is_agency  ? `<span class="badge badge-agency">Agentlik</span>` : `<span class="badge badge-owner">Mülkiyyətçi</span>`,
    l.deleted_at ? `<span class="badge badge-deleted">Silinib</span>` : '',
    selCat === 'all' ? `<span class="badge badge-cat">${catLabel(l.category)}</span>` : '',
  ].filter(Boolean).join('');

  return `
<div class="card${l.deleted_at ? ' deleted' : ''}">
  <a class="card-photo-wrap" href="${esc(l.url)}" target="_blank" rel="noopener">${photo}</a>
  <div class="card-body">
    <div class="card-price-row">
      <span class="card-price">${formatPrice(l.price, l.deal_type)}</span>
      ${changeBadge}
    </div>
    ${unitPrice}
    ${l.location ? `<div class="card-location">${esc(l.location)}</div>` : ''}
    ${details    ? `<div class="card-details">${esc(details)}</div>` : ''}
    ${badges     ? `<div class="card-badges">${badges}</div>` : ''}
  </div>
  <div class="card-footer">
    <a href="${esc(l.url)}" target="_blank" rel="noopener">🔗 bina.az</a>
    ${l.lat && l.lng ? `<a href="https://www.google.com/maps?q=${l.lat},${l.lng}" target="_blank" rel="noopener">📍 Xəritə</a>` : ''}
  </div>
</div>`;
}

function updateStats() {
  const active = filtered.filter(l => !l.deleted_at).length;
  const total  = filtered.length;
  document.getElementById('stats-bar').textContent = showDel
    ? `${total} nəticə (${active} aktiv, ${total-active} silinmiş)`
    : `${total} aktiv elan`;
  document.getElementById('global-stats').textContent = `${allListings.length.toLocaleString()} elan yükləndi`;
}

function renderPagination() {
  const total = Math.ceil(filtered.length / PAGE_SIZE);
  const pag = document.getElementById('pagination');
  if (total <= 1) { pag.style.display = 'none'; return; }
  pag.style.display = 'flex';
  pag.innerHTML = `
    <button id="btn-prev" ${page===1?'disabled':''}>← Əvvəlki</button>
    <span>${page} / ${total}</span>
    <button id="btn-next" ${page===total?'disabled':''}>Növbəti →</button>`;
  document.getElementById('btn-prev').onclick = () => { page--; renderGrid(); renderPagination(); scrollTo({top:0,behavior:'smooth'}); };
  document.getElementById('btn-next').onclick = () => { page++; renderGrid(); renderPagination(); scrollTo({top:0,behavior:'smooth'}); };
}

// ── Location multiselect ──────────────────────────────────────────────────────

const ALL_LOCATIONS = [
  '20 Yanvar m.','20-ci sahə q.','28 May m.','9-cu mikrorayon q.',
  'Azadlıq Prospekti m.','Ağ şəhər q.','Badamdar q.','Bakıxanov q.',
  'Bayıl q.','Bilgəh q.','Biləcəri q.','Binə q.','Binəqədi q.','Binəqədi r.',
  'Buzovna q.','Dübəndi q.','Elmlər Akademiyası m.','Görədil q.','Gənclik m.',
  'Hökməli q.','Hövsan q.','Həzi Aslanov m.','Həzi Aslanov q.','Koroğlu m.',
  'Lökbatan q.','M.Ə.Rəsulzadə q.','Masazır q.','Mehdiabad q.','Memar Əcəmi m.',
  'Məmmədli q.','Mərdəkan q.','Nardaran q.','Neftçilər m.','Nizami m.','Nizami r.',
  'Novxanı q.','Nəriman Nərimanov m.','Nərimanov r.','Nəsimi r.','Qala q.',
  'Qara Qarayev m.','Qaraçuxur q.','Qobu q.','Sahil q.','Saray q.',
  'Sea Breeze q.','Türkan q.','Yasamal q.','Yasamal r.','Yeni Ramana q.',
  'Yeni Yasamal q.','Zabrat q.','Zığ q.','İnşaatçılar m.','İçəri Şəhər m.',
  'Şah İsmayıl Xətai m.','Şağan q.','Şüvəlan q.','Əhmədli m.','Ələt q.','Əmircan q.',
];

function buildLocationDropdown(searchVal = '') {
  const list = document.getElementById('ms-list');
  const fromData = allListings.map(l => l.location || '').filter(Boolean);
  const locs = [...new Set([...ALL_LOCATIONS, ...fromData])].sort();
  const q = searchVal.toLowerCase();
  const visible = q ? locs.filter(l => l.toLowerCase().includes(q)) : locs;

  if (!visible.length) {
    list.innerHTML = `<div class="ms-empty">Nəticə yoxdur</div>`;
    return;
  }
  list.innerHTML = visible.map(loc => `
    <label class="ms-item">
      <input type="checkbox" value="${esc(loc)}" ${selLocs.has(loc) ? 'checked' : ''}>
      <span>${esc(loc)}</span>
    </label>`).join('');

  list.querySelectorAll('input[type=checkbox]').forEach(cb => {
    cb.addEventListener('change', () => {
      if (cb.checked) selLocs.add(cb.value); else selLocs.delete(cb.value);
      updateMsLabel();
      applyFilters();
    });
  });
}

function updateMsLabel() {
  const btn = document.getElementById('ms-btn');
  const label = document.getElementById('ms-label');
  if (selLocs.size === 0) {
    label.textContent = 'Bütün məkanlar';
    btn.classList.remove('has-selection');
  } else {
    label.textContent = `${selLocs.size} məkan seçildi`;
    btn.classList.add('has-selection');
  }
}

document.getElementById('ms-btn').addEventListener('click', e => {
  e.stopPropagation();
  const dd = document.getElementById('ms-dropdown');
  dd.classList.toggle('open');
  if (dd.classList.contains('open')) document.getElementById('ms-search').focus();
});

document.addEventListener('click', e => {
  if (!document.getElementById('ms-wrap').contains(e.target)) {
    document.getElementById('ms-dropdown').classList.remove('open');
  }
});

document.getElementById('ms-search').addEventListener('input', e => {
  buildLocationDropdown(e.target.value);
});

document.getElementById('ms-all').addEventListener('click', () => {
  const fromData = allListings.map(l => l.location || '').filter(Boolean);
  const locs = [...new Set([...ALL_LOCATIONS, ...fromData])];
  locs.forEach(l => selLocs.add(l));
  buildLocationDropdown(document.getElementById('ms-search').value);
  updateMsLabel();
  applyFilters();
});

document.getElementById('ms-none').addEventListener('click', () => {
  selLocs.clear();
  buildLocationDropdown(document.getElementById('ms-search').value);
  updateMsLabel();
  applyFilters();
});

// ── Event wiring ──────────────────────────────────────────────────────────────

document.getElementById('cat-chips').addEventListener('click', e => {
  const btn = e.target.closest('.chip'); if (!btn) return;
  document.querySelectorAll('#cat-chips .chip').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  selCat = btn.dataset.cat;
  selLocs.clear(); updateMsLabel();
  loadAll();
});

document.getElementById('type-chips').addEventListener('click', e => {
  const btn = e.target.closest('.chip'); if (!btn) return;
  document.querySelectorAll('#type-chips .chip').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  selType = btn.dataset.type;
  selLocs.clear(); updateMsLabel();
  loadAll();
});

document.getElementById('sort').addEventListener('change', e => { sort = e.target.value; applyFilters(); });
document.getElementById('show-deleted').addEventListener('change', e => { showDel = e.target.checked; applyFilters(); });

['price-min','price-max','area-min','area-max','sot-min','sot-max','ppm2-min','ppm2-max'].forEach(id => {
  document.getElementById(id).addEventListener('input', applyFilters);
});
document.getElementById('rooms-filter').addEventListener('change', applyFilters);
document.getElementById('repair-filter').addEventListener('change', applyFilters);
document.getElementById('agency-filter').addEventListener('change', applyFilters);

// ── Boot ──────────────────────────────────────────────────────────────────────
loadAll();
