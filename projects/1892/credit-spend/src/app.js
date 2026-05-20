// Credit Spend Dashboard — frontend
const PRIMARY = '#F84600';
const PALETTE = ['#F84600','#7dd3fc','#a78bfa','#22c55e','#fbbf24','#f472b6','#60a5fa','#34d399','#fb923c','#c084fc','#64748b','#facc15'];

const fmt = (n, d=2) => '$' + Number(n||0).toLocaleString('en-US', {minimumFractionDigits:d, maximumFractionDigits:d});
const fmtN = (n) => new Intl.NumberFormat('en-US').format(n||0);
const shortDate = (s) => s ? s.slice(5,10) : '';
const fullTs = (s) => s ? s.slice(0,19).replace('T',' ') : '';

Chart.defaults.color = '#888';
Chart.defaults.borderColor = '#1f1f1f';
Chart.defaults.font.family = 'Google Sans, system-ui, sans-serif';
Chart.defaults.plugins.legend.labels.color = '#ccc';
Chart.defaults.plugins.legend.labels.boxWidth = 10;
Chart.defaults.plugins.legend.labels.boxHeight = 10;
Chart.defaults.plugins.tooltip.backgroundColor = '#151515';
Chart.defaults.plugins.tooltip.borderColor = PRIMARY;
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.padding = 10;

let charts = [];
function resetCharts(){ charts.forEach(c => c.destroy()); charts = []; }

const els = {
  days: document.getElementById('days'),
  refresh: document.getElementById('refreshBtn'),
  statusText: document.getElementById('statusText'),
  statusPill: document.getElementById('statusPill'),
  errBox: document.getElementById('errBox'),
  stats: document.getElementById('stats'),
};

function setStatus(msg, kind='') {
  els.statusText.textContent = msg;
  els.statusPill.className = 'pill ' + kind;
}

function setError(msg) {
  els.errBox.innerHTML = msg ? `<div class="err">${msg}</div>` : '';
}

async function getJSON(url){
  const r = await fetch(url, {cache:'no-cache'});
  if(!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

function renderStats(balance, breakdown, daily){
  const window7 = (daily.daily || []).slice(-7).reduce((s,d) => s + (d.total_credits||0), 0);
  const reqs = (daily.daily || []).reduce((s,d) => s + (d.request_count||0), 0);
  els.stats.innerHTML = `
    <div class="stat accent">
      <div class="l">Current balance</div>
      <div class="v">${fmt(balance.credit_balance, 2)}</div>
      <div class="s">${balance.name ? 'Agent: '+balance.name : ''}</div>
    </div>
    <div class="stat">
      <div class="l">Spent (last ${breakdown.window_days}d)</div>
      <div class="v">${fmt(breakdown.total_credits_window, 2)}</div>
      <div class="s">${fmtN(breakdown.charges_in_window)} charges</div>
    </div>
    <div class="stat">
      <div class="l">Spent (last 7d)</div>
      <div class="v">${fmt(window7, 2)}</div>
      <div class="s">avg ${fmt(window7/7, 2)}/day</div>
    </div>
    <div class="stat">
      <div class="l">Lifetime used</div>
      <div class="v">${fmt(balance.total_used, 0)}</div>
      <div class="s">of ${fmt(balance.total_recharged, 0)} recharged</div>
    </div>
    <div class="stat">
      <div class="l">Requests (window)</div>
      <div class="v">${fmtN(reqs)}</div>
      <div class="s">avg ${fmt((breakdown.total_credits_window/(reqs||1)), 4)}/req</div>
    </div>
  `;
}

function renderDaily(daily){
  const days = daily.daily || [];
  const labels = days.map(d => shortDate(d.day));
  const data = days.map(d => Number(d.total_credits||0).toFixed(4));
  const ctx = document.getElementById('dailyChart').getContext('2d');
  charts.push(new Chart(ctx, {
    type:'bar',
    data:{ labels, datasets:[{
      label:'Credits', data,
      backgroundColor: PRIMARY+'cc', borderColor: PRIMARY, borderWidth:1, borderRadius:4,
    }]},
    options:{ responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{display:false}, tooltip:{ callbacks:{ label:(c)=>fmt(c.parsed.y, 4) }}},
      scales:{ y:{ ticks:{ callback:(v)=>'$'+v }}}
    }
  }));
}

function renderPie(canvasId, items, labelKey='name', valueKey='credits'){
  const labels = items.map(i => i[labelKey]);
  const data = items.map(i => Number(i[valueKey]||0).toFixed(4));
  const ctx = document.getElementById(canvasId).getContext('2d');
  charts.push(new Chart(ctx, {
    type:'doughnut',
    data:{ labels, datasets:[{ data,
      backgroundColor: labels.map((_,i)=>PALETTE[i % PALETTE.length]),
      borderColor:'#0c0c0c', borderWidth:2,
    }]},
    options:{ responsive:true, maintainAspectRatio:false,
      plugins:{
        legend:{ position:'right', labels:{ boxWidth:10, font:{size:11} }},
        tooltip:{ callbacks:{ label:(c)=>`${c.label}: ${fmt(c.parsed, 2)}` }}
      },
      cutout:'55%'
    }
  }));
}

function renderDailyByModel(daily){
  const days = daily.daily || [];
  const byApi = daily.by_api || [];
  // Group api_type into families & pivot per day
  const fam = (s) => {
    const t = (s||'').toLowerCase();
    if(t.includes('opus')) return 'Claude Opus';
    if(t.includes('sonnet')) return 'Claude Sonnet';
    if(t.includes('haiku')) return 'Claude Haiku';
    if(t.includes('codex')) return 'GPT Codex';
    if(t.includes('gpt')) return 'GPT';
    if(t.includes('gemini')) return 'Gemini';
    if(t.includes('deepseek')) return 'DeepSeek';
    if(t.includes('image')||t.includes('nano-banana')||t.includes('imagen')) return 'Image';
    if(t.includes('coingecko')||t.includes('twelvedata')||t.includes('coinglass')) return 'Market data';
    if(t.includes('search')||t.includes('brave')) return 'Web search';
    return 'Other';
  };
  const dayLabels = days.map(d => d.day);
  const pivot = {};
  for(const row of byApi){
    const f = fam(row.api_type);
    if(!pivot[f]) pivot[f] = {};
    pivot[f][row.day] = (pivot[f][row.day]||0) + Number(row.total_credits||0);
  }
  // Sort families by total
  const famTotals = Object.entries(pivot).map(([k,v]) => [k, Object.values(v).reduce((s,x)=>s+x,0)])
    .sort((a,b)=>b[1]-a[1]);
  const datasets = famTotals.map(([f], i) => ({
    label: f,
    data: dayLabels.map(d => Number((pivot[f][d]||0).toFixed(4))),
    backgroundColor: PALETTE[i % PALETTE.length],
    stack:'all', borderWidth:0,
  }));
  const ctx = document.getElementById('dailyModelChart').getContext('2d');
  charts.push(new Chart(ctx, {
    type:'bar',
    data:{ labels: dayLabels.map(shortDate), datasets },
    options:{ responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ position:'bottom' },
        tooltip:{ callbacks:{ label:(c)=>`${c.dataset.label}: ${fmt(c.parsed.y, 4)}` }}},
      scales:{ x:{stacked:true}, y:{stacked:true, ticks:{callback:(v)=>'$'+v}}}
    }
  }));
}

function renderRecent(recent){
  const tbody = document.querySelector('#recentTable tbody');
  if(!recent || !recent.length){
    tbody.innerHTML = '<tr><td colspan="5" class="empty">No charges in window.</td></tr>';
    return;
  }
  tbody.innerHTML = recent.map(r => {
    const apiShort = (r.api_type||'').replace('openrouter/','').replace('anthropic/','').replace('openai/','').replace('google/','');
    return `<tr>
      <td class="dim">${fullTs(r.ts)}</td>
      <td>${apiShort}</td>
      <td><span class="badge ${r.call_type||'system'}">${r.call_type||'?'}</span></td>
      <td class="dim">${r.agent_id||'?'}</td>
      <td class="num">${fmt(r.amount, 6)}</td>
    </tr>`;
  }).join('');
}

async function loadAll(){
  setStatus('loading…');
  setError('');
  resetCharts();
  try{
    const days = Number(els.days.value);
    const [balance, daily, breakdown] = await Promise.all([
      getJSON('./api/balance'),
      getJSON(`./api/daily?days=${days}`),
      getJSON(`./api/breakdown?days=${days}`),
    ]);
    renderStats(balance, breakdown, daily);
    renderDaily(daily);
    renderPie('callTypeChart', breakdown.by_call_type || []);
    renderPie('modelChart', breakdown.by_model_family || []);
    renderPie('agentChart', breakdown.by_agent || []);
    renderDailyByModel(daily);
    renderRecent(breakdown.recent);
    const truncNote = breakdown.truncated ? ` · breakdown capped at ${breakdown.scanned_charges} charges` : '';
    setStatus(`updated ${new Date().toLocaleTimeString()}${truncNote}`, 'good');
  }catch(e){
    setError(`Failed to load: ${e.message}. Is the Credit API reachable from this container?`);
    setStatus('error', 'bad');
  }
}

els.refresh.addEventListener('click', loadAll);
els.days.addEventListener('change', loadAll);
loadAll();
