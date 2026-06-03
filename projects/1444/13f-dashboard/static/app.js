// === 13F Atlas dashboard ===
const API = '';  // relative
let allFunds = [];
let currentFund = null;
let currentDetail = null;
let currentPeriod = null;
let currentDiff = [];
let currentDiffCat = 'NEW';
let treemapChart = null;
let timelineChart = null;
let baselineData = null;       // { periods, fund_aum, baselines: {SPY:{...},...} }
let activeBaselines = new Set(['SPY','QQQ']);
let timelineMode = 'aum';      // 'aum' | 'indexed'
let activeJobId = null;
let jobPollTimer = null;
let searchDebounce = null;
let currentHoldings = [];          // all loaded so far
let currentHoldingsTotal = 0;      // total positions in the filing
let currentHoldingsValue = 0;      // total $ value of full filing
let currentTableFilter = '';
const TABLE_PAGE_SIZE = 100;
const TABLE_HARD_CAP = 1000;

// ============ utils ============
const $ = (id) => document.getElementById(id);
const fmt = {
  usd(n) {
    n = +n || 0;
    const a = Math.abs(n);
    const sign = n < 0 ? '-' : '';
    if (a >= 1e9) return `${sign}$${(a/1e9).toFixed(2)}B`;
    if (a >= 1e6) return `${sign}$${(a/1e6).toFixed(2)}M`;
    if (a >= 1e3) return `${sign}$${(a/1e3).toFixed(1)}K`;
    return `${sign}$${a.toFixed(0)}`;
  },
  num(n) { return (+n || 0).toLocaleString('en-US'); },
  pct(n) {
    if (n === null || n === undefined || isNaN(n)) return '';
    return `${(n*100).toFixed(1)}%`;
  },
};

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

// ============ view nav ============
function showView(view) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  $(`view${view[0].toUpperCase()+view.slice(1)}`).classList.add('active');
  document.querySelectorAll('.navbtn[data-view]').forEach(b => {
    b.classList.toggle('active', b.dataset.view === view);
  });
  window.scrollTo({top:0, behavior:'instant'});
}

// ============ animations ============
function animateNum(el, from, to, dur=1.4, formatter=null) {
  const obj = { v: from };
  gsap.to(obj, {
    v: to, duration: dur, ease: 'expo.out',
    onUpdate: () => {
      el.textContent = formatter ? formatter(obj.v) : Math.round(obj.v).toLocaleString('en-US');
    }
  });
}

function staggerIn(els, opts={}) {
  return gsap.from(els, {
    y: 30, opacity: 0, duration: .8, ease: 'expo.out',
    stagger: opts.stagger || .06, ...opts,
  });
}

// ============ picker ============
async function loadPicker() {
  const data = await fetchJSON('api/funds');
  allFunds = data.funds || [];
  renderFundGrid(allFunds);
  // hero stats
  const totFilings = allFunds.reduce((s,f) => s + f.filings_count, 0);
  const totValue = allFunds.reduce((s,f) => s + (f.latest_value_usd||0), 0);
  animateNum($('statFunds'), 0, allFunds.length);
  animateNum($('statFilings'), 0, totFilings);
  animateNum($('statValue'), 0, totValue, 1.6, fmt.usd);
  // hero text animation
  gsap.from('.hero-eyebrow', { y: 14, opacity: 0, duration: .8, ease: 'expo.out' });
  gsap.from('.hero-title .word', { y: '105%', opacity: 0, duration: 1.1, stagger: .05, ease: 'expo.out', delay: .15 });
  gsap.from('.hero-sub', { y: 20, opacity: 0, duration: .9, ease: 'expo.out', delay: .55 });
  gsap.from('.hero-stats .stat', { y: 16, opacity: 0, stagger: .08, duration: .8, ease: 'expo.out', delay: .75 });
}

function renderFundGrid(funds) {
  const grid = $('fundGrid');
  if (!funds.length) { grid.innerHTML = '<div class="empty">No 13F data downloaded yet.</div>'; return; }
  grid.innerHTML = funds.map(f => {
    const isEmpty = f.latest_holdings_count === 0 || f.latest_value_usd === 0;
    return `
    <div class="fund-card ${isEmpty ? 'empty-fund' : ''}" data-slug="${f.slug}">
      <div class="fc-arrow">↗</div>
      <div class="fc-cik">CIK · ${f.cik}</div>
      <div class="fc-name">${escapeHtml(f.name)}</div>
      <div class="fc-meta">
        <div>
          <div class="fc-aum-lbl">${isEmpty ? 'Status' : 'Latest AUM (13F)'}</div>
          <div class="fc-aum-val">${isEmpty ? 'No data' : fmt.usd(f.latest_value_usd)}</div>
        </div>
        <div class="fc-side">
          <div class="v">${f.filings_count}</div><div class="l">Filings</div>
          <div class="v" style="margin-top:6px">${f.latest_holdings_count}</div><div class="l">Positions</div>
        </div>
      </div>
    </div>
  `;}).join('');
  grid.querySelectorAll('.fund-card').forEach(card => {
    card.addEventListener('click', () => openFund(card.dataset.slug));
  });
  staggerIn(grid.querySelectorAll('.fund-card'), { stagger: .04, delay: .3 });
}

$('searchInput').addEventListener('input', (e) => {
  const q = e.target.value.toLowerCase();
  const filtered = allFunds.filter(f =>
    f.name.toLowerCase().includes(q) || f.cik.includes(q));
  renderFundGrid(filtered);
});

// ============ detail ============
async function openFund(slug) {
  const data = await fetchJSON(`api/funds/${slug}`);
  currentFund = slug;
  currentDetail = data;
  $('navDetail').disabled = false;
  showView('detail');

  $('detailCik').textContent = `CIK · ${data.manager.cik}`;
  $('detailName').textContent = data.manager.name;

  // intro animations
  gsap.from('.detail-name', { y: 30, opacity: 0, duration: 1, ease: 'expo.out' });
  gsap.from('#detailCik', { y: 12, opacity: 0, duration: .6, ease: 'expo.out' });
  gsap.from('.big-num, .big-lbl', { y: 18, opacity: 0, duration: .9, stagger: .1, ease: 'expo.out', delay: .15 });
  gsap.from('.panel', { y: 40, opacity: 0, duration: .9, stagger: .08, ease: 'expo.out', delay: .25 });

  // quarter pills
  const periods = data.filings.map(f => f.period);
  renderQuarterStrip(data.filings);
  baselineData = null;
  renderTimeline();  // shows AUM bars immediately
  loadBaselines();   // fetch baselines async, then re-render if mode==indexed

  // select latest quarter
  const latest = periods[periods.length - 1];
  await selectQuarter(latest);
}

async function loadBaselines() {
  try {
    baselineData = await fetchJSON(`api/funds/${currentFund}/baselines`);
    renderBaselineChips();
    renderTimeline();
  } catch(e) {
    console.warn('baselines unavailable', e);
  }
}

function renderQuarterStrip(filings) {
  const track = $('quartersTrack');
  // newest first
  const items = [...filings].reverse();
  track.innerHTML = items.map(f => `
    <button class="qpill" data-period="${f.period}">
      ${f.period}<span class="qval">${fmt.usd(f.total_value_usd)}</span>
    </button>
  `).join('');
  track.querySelectorAll('.qpill').forEach(b => {
    b.addEventListener('click', () => selectQuarter(b.dataset.period));
  });
  gsap.from(track.querySelectorAll('.qpill'), { y: 10, opacity: 0, stagger: .02, duration: .5, ease: 'expo.out', delay: .35 });
}

async function selectQuarter(period) {
  currentPeriod = period;
  document.querySelectorAll('.qpill').forEach(p => p.classList.toggle('active', p.dataset.period === period));
  const filing = currentDetail.filings.find(f => f.period === period);
  if (!filing) return;

  // big number animation
  const oldVal = parseFloat($('detailValue').dataset.v || '0');
  animateNum($('detailValue'), oldVal, filing.total_value_usd, 1.2, fmt.usd);
  $('detailValue').dataset.v = filing.total_value_usd;
  $('detailPeriod').textContent = period;
  $('detailHoldings').textContent = `${filing.holdings_count}`;

  $('treeSub').textContent = `${period} · ${fmt.usd(filing.total_value_usd)}`;
  $('tableQ').textContent = period;
  $('tableSub').textContent = `${filing.holdings_count} positions · filed ${filing.filed}`;

  // load holdings + diff in parallel
  const periods = currentDetail.filings.map(f => f.period);
  const idx = periods.indexOf(period);
  const prev = idx > 0 ? periods[idx-1] : null;

  // reset table state for new quarter
  currentHoldings = [];
  currentHoldingsTotal = 0;
  currentTableFilter = '';
  $('tblSearch').value = '';

  const [holdRes, diffRes] = await Promise.all([
    fetchJSON(`api/funds/${currentFund}/holdings/${period}?limit=${TABLE_PAGE_SIZE}`),
    prev ? fetchJSON(`api/funds/${currentFund}/diff/${prev}/${period}`) : Promise.resolve({diff:[],available:false}),
  ]);

  currentHoldings = holdRes.holdings;
  currentHoldingsTotal = holdRes.total_count;
  currentHoldingsValue = holdRes.total_value_usd || filing.total_value_usd;
  renderTreemap(holdRes.treemap, currentHoldingsValue);
  renderHoldingsTable();
  renderDiff(diffRes.diff, prev, period);
}

function renderTreemap(items, total) {
  if (!treemapChart) treemapChart = echarts.init($('treemap'), null, { renderer: 'canvas' });
  // `items` is already the compact top-40 + "Other" summary from server
  treemapChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      formatter: (p) => {
        const pct = total ? (p.value/total*100).toFixed(2) : '0';
        return `<div style="font-family:Inter,sans-serif;font-size:13px;line-height:1.5">
          <div style="font-weight:600;margin-bottom:4px">${p.data.full || p.name}</div>
          <div style="color:#9a96aa">${p.name}${p.data.putCall ? ' · '+p.data.putCall : ''}</div>
          <div style="margin-top:6px;font-family:JetBrains Mono,monospace">${fmt.usd(p.value)} <span style="color:#ffe66b">(${pct}%)</span></div>
        </div>`;
      },
      backgroundColor: 'rgba(15,15,23,0.95)',
      borderColor: '#3a3a52',
      textStyle: { color: '#f0eee6' },
    },
    series: [{
      type: 'treemap',
      data: items,
      roam: false, nodeClick: false, breadcrumb: { show: false },
      width: '100%', height: '100%', top: 0, left: 0,
      itemStyle: { borderColor: '#07070b', borderWidth: 3, gapWidth: 3 },
      label: {
        show: true,
        formatter: (p) => {
          const pct = total ? (p.value/total*100).toFixed(1) : '0';
          return `{name|${p.name}}\n{val|${fmt.usd(p.value)}  ${pct}%}`;
        },
        rich: {
          name: { fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 16, color: '#07070b', lineHeight: 22 },
          val: { fontFamily: 'JetBrains Mono', fontSize: 11, color: 'rgba(7,7,11,0.7)', lineHeight: 16 },
        },
      },
      levels: [{
        colorSaturation: [0.35, 0.85],
        colorMappingBy: 'value',
        itemStyle: { borderColor: '#07070b', borderWidth: 3, gapWidth: 3 },
      }],
      color: ['#ffe66b','#ffb84d','#ff8a5c','#ff4d8d','#c44dff','#5cd4ff','#7af0a8'],
      animationDuration: 900,
      animationEasing: 'expoOut',
    }],
  }, true);
}

function renderTimeline() {
  if (!timelineChart) timelineChart = echarts.init($('timeline'), null, { renderer: 'canvas' });
  if (!currentDetail) return;
  const filings = currentDetail.filings;
  const labels = filings.map(f => f.period);

  if (timelineMode === 'aum' || !baselineData) {
    const data = filings.map(f => f.total_value_usd);
    timelineChart.setOption({
      backgroundColor: 'transparent',
      grid: { left: 64, right: 20, top: 20, bottom: 42 },
      legend: { show: false },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15,15,23,0.95)', borderColor: '#3a3a52',
        textStyle: { color: '#f0eee6' },
        formatter: (p) => `<div style="font-family:Inter,sans-serif;font-size:13px"><b>${p[0].axisValue}</b><br><span style="color:#ffe66b;font-family:JetBrains Mono,monospace">${fmt.usd(p[0].value)}</span></div>`,
      },
      xAxis: {
        type: 'category', data: labels,
        axisLine: { lineStyle: { color: '#3a3a52' } },
        axisLabel: { color: '#9a96aa', fontFamily: 'JetBrains Mono', fontSize: 10, rotate: labels.length > 8 ? 35 : 0 },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false }, axisTick: { show: false },
        splitLine: { lineStyle: { color: '#23232f', type: 'dashed' } },
        axisLabel: { color: '#9a96aa', fontFamily: 'JetBrains Mono', fontSize: 10, formatter: (v) => fmt.usd(v) },
      },
      series: [{
        name: 'AUM',
        type: 'bar', data, barWidth: '55%',
        itemStyle: {
          borderRadius: [6,6,0,0],
          color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [{offset:0,color:'#ffe66b'},{offset:1,color:'#ff8a5c'}] },
        },
        emphasis: { itemStyle: { color: '#ff4d8d' } },
        animationDuration: 1100, animationEasing: 'expoOut',
        animationDelay: (i) => i * 50,
      }],
    }, true);
    return;
  }

  // === indexed mode — rebased to 100 at first period ===
  const periods = baselineData.periods;
  const fundAum = baselineData.fund_aum;
  const series = [];

  // fund itself
  const baseFund = fundAum.find(v => v > 0) || 1;
  const fundIdx = fundAum.map(v => v > 0 ? (v/baseFund*100) : null);
  series.push({
    name: currentDetail.manager.name,
    type: 'line',
    data: fundIdx,
    smooth: true, symbol: 'circle', symbolSize: 7,
    lineStyle: { width: 3.5, color: '#ffe66b' },
    itemStyle: { color: '#ffe66b', borderColor: '#07070b', borderWidth: 2 },
    areaStyle: {
      color: { type:'linear', x:0,y:0,x2:0,y2:1,
        colorStops:[{offset:0,color:'rgba(255,230,107,.35)'},{offset:1,color:'rgba(255,230,107,0)'}] }
    },
    z: 10, animationDuration: 1300, animationEasing: 'expoOut',
  });

  // baselines (only active)
  for (const ticker of Object.keys(baselineData.baselines)) {
    if (!activeBaselines.has(ticker)) continue;
    const b = baselineData.baselines[ticker];
    const closes = b.closes;
    const base = closes.find(v => v) || 1;
    const idx = closes.map(v => v ? (v/base*100) : null);
    series.push({
      name: b.label, type: 'line', data: idx,
      smooth: true, symbol: 'circle', symbolSize: 5,
      lineStyle: { width: 2, color: b.color, type: 'dashed' },
      itemStyle: { color: b.color },
      animationDuration: 1100, animationEasing: 'expoOut',
    });
  }

  timelineChart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 60, right: 20, top: 30, bottom: 42 },
    legend: { show: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15,15,23,0.95)', borderColor: '#3a3a52',
      textStyle: { color: '#f0eee6' },
      formatter: (params) => {
        let s = `<div style="font-family:Inter;font-size:13px"><b>${params[0].axisValue}</b><br>`;
        params.sort((a,b) => (b.value||0)-(a.value||0));
        for (const p of params) {
          if (p.value === null || p.value === undefined) continue;
          const diff = p.value - 100;
          const sign = diff >= 0 ? '+' : '';
          s += `<div style="margin-top:4px;display:flex;align-items:center;gap:8px">
            <span style="width:8px;height:8px;border-radius:50%;background:${p.color}"></span>
            <span style="flex:1">${p.seriesName}</span>
            <span style="font-family:JetBrains Mono,monospace">${p.value.toFixed(1)} <span style="color:#9a96aa">(${sign}${diff.toFixed(1)})</span></span>
          </div>`;
        }
        return s + '</div>';
      },
    },
    xAxis: {
      type: 'category', data: periods,
      axisLine: { lineStyle: { color: '#3a3a52' } },
      axisLabel: { color: '#9a96aa', fontFamily: 'JetBrains Mono', fontSize: 10, rotate: periods.length > 8 ? 35 : 0 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: { lineStyle: { color: '#23232f', type: 'dashed' } },
      axisLabel: { color: '#9a96aa', fontFamily: 'JetBrains Mono', fontSize: 10, formatter: (v) => v.toFixed(0) },
    },
    series,
  }, true);
}

function renderBaselineChips() {
  const c = $('tlBaselines');
  if (!baselineData) { c.classList.remove('show'); return; }
  const baselines = baselineData.baselines;
  c.classList.toggle('show', timelineMode === 'indexed');
  c.innerHTML = Object.entries(baselines).map(([t, b]) => `
    <button class="bl-chip ${activeBaselines.has(t) ? 'active' : ''}" data-ticker="${t}" style="color:${activeBaselines.has(t) ? b.color : ''}">
      <span class="dot" style="background:${b.color};color:${b.color}"></span>${b.label}
    </button>
  `).join('');
  c.querySelectorAll('.bl-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const t = btn.dataset.ticker;
      if (activeBaselines.has(t)) activeBaselines.delete(t);
      else activeBaselines.add(t);
      renderBaselineChips();
      renderTimeline();
    });
  });
}

document.querySelectorAll('.modebtn').forEach(b => {
  b.addEventListener('click', () => {
    timelineMode = b.dataset.mode;
    document.querySelectorAll('.modebtn').forEach(x => x.classList.toggle('active', x === b));
    renderBaselineChips();
    renderTimeline();
  });
});

function renderHoldingsTable() {
  const body = $('holdBody');
  const footer = $('tblFooter');
  const total = currentHoldingsValue;
  const all = currentHoldings;
  const q = currentTableFilter.trim().toLowerCase();
  const filtered = q
    ? all.filter(h => (h.ticker||'').toLowerCase().includes(q) || (h.nameOfIssuer||'').toLowerCase().includes(q))
    : all;

  // Update header sub
  const loaded = all.length;
  const tot = currentHoldingsTotal;
  $('tableSub').textContent = q
    ? `Showing ${filtered.length} of ${loaded} loaded (filter)`
    : `Top ${loaded} of ${fmt.num(tot)} positions`;

  if (!filtered.length) {
    body.innerHTML = '<tr><td colspan="8" class="empty">No matching positions.</td></tr>';
    footer.innerHTML = '';
    return;
  }

  // Render up to 500 rows in the table at a time — anything more chokes the DOM
  const RENDER_CAP = 500;
  const toRender = filtered.slice(0, RENDER_CAP);
  body.innerHTML = toRender.map((h, i) => {
    const w = total ? (h.value_usd / total * 100) : 0;
    const pos = h.putCall ? `<span class="pos-${h.putCall.toLowerCase()}">${h.putCall}</span>` : '<span style="color:var(--ink-low)">Long</span>';
    return `<tr>
      <td style="color:var(--ink-low)">${i+1}</td>
      <td class="ticker">${escapeHtml(h.ticker||'')}</td>
      <td class="issuer" title="${escapeHtml(h.nameOfIssuer)}">${escapeHtml(h.nameOfIssuer)}</td>
      <td style="color:var(--ink-dim)">${escapeHtml(h.titleOfClass||'')}</td>
      <td class="num">${fmt.num(h.sshPrnamt)}</td>
      <td class="num">${fmt.usd(h.value_usd)}</td>
      <td class="num"><span class="weight-bar" style="--w:${Math.min(w,100).toFixed(1)}%"></span>${w.toFixed(2)}%</td>
      <td>${pos}</td>
    </tr>`;
  }).join('');

  // Animate ONLY first ~30 rows — staggering 1000 rows is what killed the browser
  const rows = body.querySelectorAll('tr');
  const animTargets = Array.from(rows).slice(0, 30);
  if (animTargets.length) {
    gsap.from(animTargets, { opacity: 0, y: 6, stagger: .012, duration: .35, ease: 'power2.out' });
  }

  // Footer: load-more button or summary
  if (q) {
    footer.innerHTML = `<span class="tf-note">Filter active · ${filtered.length} matches in loaded rows</span>`;
  } else if (loaded < tot && loaded < TABLE_HARD_CAP) {
    const remaining = Math.min(TABLE_PAGE_SIZE, tot - loaded, TABLE_HARD_CAP - loaded);
    footer.innerHTML = `
      <button class="load-more" id="loadMoreBtn">Load ${remaining} more</button>
      <span class="tf-note">${loaded}/${fmt.num(tot)} loaded</span>`;
    $('loadMoreBtn').addEventListener('click', loadMoreHoldings);
  } else if (tot > TABLE_HARD_CAP && loaded >= TABLE_HARD_CAP) {
    footer.innerHTML = `<span class="tf-note">Showing top ${TABLE_HARD_CAP} of ${fmt.num(tot)} · use filter to find specific positions</span>`;
  } else if (filtered.length > RENDER_CAP) {
    footer.innerHTML = `<span class="tf-note">Rendered first ${RENDER_CAP} of ${filtered.length} matches</span>`;
  } else {
    footer.innerHTML = `<span class="tf-note">${loaded} positions</span>`;
  }
}

async function loadMoreHoldings() {
  const btn = $('loadMoreBtn');
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = 'Loading…';
  const offset = currentHoldings.length;
  try {
    const r = await fetchJSON(`api/funds/${currentFund}/holdings/${currentPeriod}?limit=${TABLE_PAGE_SIZE}&offset=${offset}`);
    currentHoldings = currentHoldings.concat(r.holdings);
    renderHoldingsTable();
  } catch(e) {
    btn.textContent = 'Failed';
  }
}

$('tblSearch').addEventListener('input', (e) => {
  currentTableFilter = e.target.value;
  renderHoldingsTable();
});

// ============ diffs ============
function renderDiff(diffRows, prevP, currP) {
  currentDiff = diffRows;
  if (prevP) $('diffSub').textContent = `${prevP} → ${currP}`;
  else $('diffSub').textContent = 'No prior quarter';
  const counts = { NEW:0, ADDED:0, REDUCED:0, CLOSED:0 };
  diffRows.forEach(r => { if (counts[r.action] !== undefined) counts[r.action]++; });
  Object.entries(counts).forEach(([k,v]) => { $(`cnt-${k}`).textContent = v; });
  renderDiffCategory(currentDiffCat);
}

function renderDiffCategory(cat) {
  currentDiffCat = cat;
  document.querySelectorAll('.dtab').forEach(t => t.classList.toggle('active', t.dataset.cat === cat));
  const list = $('diffList');
  const rows = currentDiff.filter(r => r.action === cat).slice(0, 60);
  if (!rows.length) {
    list.innerHTML = '<div class="empty">No positions in this category for this quarter.</div>';
    return;
  }
  list.innerHTML = rows.map(r => {
    const delta = r.value_delta_usd;
    const deltaSign = delta > 0 ? '+' : '';
    const sharesDelta = r.shares_delta;
    const pct = r.shares_pct_change;
    const optTag = r.putCall ? `<span class="dc-tag" style="background:rgba(255,255,255,.06);color:var(--ink-dim)">${r.putCall}</span>` : '';
    return `<div class="dcard ${r.action}">
      <div>
        <div class="dc-name">
          <span class="dc-tag">${r.action}</span>
          ${optTag}
          <span>${escapeHtml(r.nameOfIssuer || r.cusip)}</span>
        </div>
        <div class="dc-sub">${fmt.num(sharesDelta)} sh${pct !== null && pct !== undefined ? ` · ${pct > 0 ? '+' : ''}${fmt.pct(pct)}` : ''}</div>
      </div>
      <div class="dc-val">
        <div class="v">${fmt.usd(Math.abs(delta))}</div>
        <div class="d">${deltaSign}${fmt.usd(delta)} value</div>
      </div>
    </div>`;
  }).join('');
  gsap.from(list.querySelectorAll('.dcard'), { x: -14, opacity: 0, stagger: .03, duration: .5, ease: 'expo.out' });
}

document.querySelectorAll('.dtab').forEach(t => {
  t.addEventListener('click', () => renderDiffCategory(t.dataset.cat));
});

// ============ misc ============
function escapeHtml(s) {
  return (s||'').replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

$('backBtn').addEventListener('click', () => { showView('picker'); });
document.querySelectorAll('.navbtn[data-view]').forEach(b => {
  b.addEventListener('click', () => {
    if (b.disabled) return;
    showView(b.dataset.view);
  });
});

window.addEventListener('resize', () => {
  treemapChart && treemapChart.resize();
  timelineChart && timelineChart.resize();
});

// ============ Add-fund modal ============
const modalBackdrop = $('modalBackdrop');
const secSearch = $('secSearch');
const secResults = $('secResults');
const modalJob = $('modalJob');
$('addFundBtn').addEventListener('click', openAddModal);
$('modalClose').addEventListener('click', closeAddModal);
modalBackdrop.addEventListener('click', (e) => { if (e.target === modalBackdrop) closeAddModal(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && modalBackdrop.classList.contains('show')) closeAddModal(); });

function openAddModal() {
  modalBackdrop.classList.add('show');
  setTimeout(() => secSearch.focus(), 100);
  gsap.fromTo('.modal', { y: 30, opacity: 0, scale: .96 }, { y: 0, opacity: 1, scale: 1, duration: .5, ease: 'expo.out' });
}
function closeAddModal() {
  modalBackdrop.classList.remove('show');
  if (jobPollTimer) { clearTimeout(jobPollTimer); jobPollTimer = null; }
  activeJobId = null;
}

secSearch.addEventListener('input', (e) => {
  const q = e.target.value.trim();
  if (searchDebounce) clearTimeout(searchDebounce);
  if (q.length < 2) {
    secResults.innerHTML = '<div class="empty modal-empty">Type at least 2 characters…</div>';
    return;
  }
  secResults.innerHTML = '<div class="empty modal-empty"><span class="spinner"></span>Searching EDGAR…</div>';
  searchDebounce = setTimeout(() => doSearch(q), 350);
});

async function doSearch(q) {
  try {
    const r = await fetchJSON(`api/search?q=${encodeURIComponent(q)}`);
    renderSearchResults(r.candidates || []);
  } catch(e) {
    secResults.innerHTML = `<div class="empty modal-empty">Search failed: ${escapeHtml(e.message)}</div>`;
  }
}

function renderSearchResults(cands) {
  if (!cands.length) {
    secResults.innerHTML = '<div class="empty modal-empty">No 13F filers found. Try a different name.</div>';
    return;
  }
  secResults.innerHTML = cands.map(c => {
    const activeTag = c.active ? '<span class="cc-pill active">● Active</span>' : '<span class="cc-pill inactive">Inactive</span>';
    const last = c.last_filed ? `Last filed ${c.last_filed}` : '';
    return `
    <div class="cand-card ${c.already_downloaded ? 'downloaded' : ''} ${c.active ? '' : 'cand-inactive'}" data-cik="${c.cik}" data-name="${escapeHtml(c.name)}">
      <div>
        <div class="cc-name">${escapeHtml(c.name)} ${activeTag}</div>
        <div class="cc-meta">CIK ${c.cik} · ${c.hits} filings · ${last}</div>
      </div>
      <button class="cc-btn">${c.already_downloaded ? '✓ Downloaded' : 'Download'}</button>
    </div>
  `;}).join('');
  secResults.querySelectorAll('.cand-card:not(.downloaded) .cc-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const card = e.target.closest('.cand-card');
      startDownload(card.dataset.cik, card.dataset.name);
    });
  });
  // animate only the first ~10 cards, cap total stagger to .25s, clear inline
  // opacity afterwards so a fast re-render can't leave cards stuck at 0
  const cards = secResults.querySelectorAll('.cand-card');
  const animTargets = Array.from(cards).slice(0, 10);
  if (animTargets.length) {
    gsap.fromTo(animTargets,
      { y: 8, opacity: 0 },
      { y: 0, opacity: 1, stagger: .025, duration: .3, ease: 'power2.out', overwrite: true, clearProps: 'opacity,transform' });
  }
}

async function startDownload(cik, name) {
  const limit = parseInt($('secLimit').value || '0', 10);
  try {
    const r = await fetch('api/download', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ cik, limit }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'request failed');
    activeJobId = data.job_id;
    secResults.style.display = 'none';
    modalJob.classList.add('show');
    modalJob.innerHTML = `
      <div class="mj-head"><div class="mj-name">${escapeHtml(name)}</div>
        <div class="mj-status running">Starting</div></div>
      <div class="mj-phase">Initializing…</div>
      <div class="mj-bar mj-bar-indeterminate"><div class="mj-bar-fill"></div></div>
      <div class="mj-log"></div>`;
    pollJob();
  } catch(e) {
    alert('Failed to start: ' + e.message);
  }
}

async function pollJob() {
  if (!activeJobId) return;
  try {
    const j = await fetchJSON(`api/download/${activeJobId}`);
    const statusEl = modalJob.querySelector('.mj-status');
    const phaseEl = modalJob.querySelector('.mj-phase');
    const barEl = modalJob.querySelector('.mj-bar');
    const fillEl = modalJob.querySelector('.mj-bar-fill');
    const logEl = modalJob.querySelector('.mj-log');
    statusEl.textContent = j.status;
    statusEl.className = `mj-status ${j.status}`;
    phaseEl.textContent = j.phase || '';
    if (j.progress) {
      barEl.classList.remove('mj-bar-indeterminate');
      const pct = (j.progress.current / j.progress.total) * 100;
      fillEl.style.width = pct + '%';
      phaseEl.textContent = `${j.phase || 'Downloading'} · ${j.progress.current}/${j.progress.total} filings`;
    }
    if (j.log && j.log.length) {
      logEl.textContent = j.log.slice(-8).join('\n');
      logEl.scrollTop = logEl.scrollHeight;
    }
    if (j.status === 'ok') {
      barEl.classList.remove('mj-bar-indeterminate');
      fillEl.style.width = '100%';
      modalJob.innerHTML += `<a class="mj-open" id="openNewFund">Open ${escapeHtml(j.resolved_name || 'fund')} →</a>`;
      $('openNewFund').addEventListener('click', async () => {
        await loadPicker();
        closeAddModal();
        secResults.style.display = '';
        modalJob.classList.remove('show');
        if (j.slug) openFund(j.slug);
      });
      // also refresh picker silently in background
      loadPicker();
      activeJobId = null;
      return;
    }
    if (j.status === 'error') {
      barEl.classList.remove('mj-bar-indeterminate');
      activeJobId = null;
      return;
    }
    jobPollTimer = setTimeout(pollJob, 1200);
  } catch(e) {
    jobPollTimer = setTimeout(pollJob, 2000);
  }
}

// ============ go ============
loadPicker().catch(e => {
  console.error(e);
  $('fundGrid').innerHTML = `<div class="empty">Failed to load funds: ${e.message}</div>`;
});
