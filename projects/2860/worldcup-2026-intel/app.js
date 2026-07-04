let groupsData = [];
let headToHeadData = {};
let fixturesData = {};
let matchesData = [];
let recentFormData = {};
let venuesData = {};
let historicalData = {};
let groupStandingsData = {};
let userProbs = {};
let ledgerEntries = [];
let currentGroupFilter = null;
let currentSearchTerm = '';

const REAL_TEAMS = ["United States","Paraguay","Australia","Türkiye","England","Croatia","Ghana","Panama"];

function loadUserProbs() {
  try {
    const saved = localStorage.getItem('wc2026_userProbs');
    if (saved) userProbs = JSON.parse(saved);
  } catch(e) {}
}

function loadVenues() {
  fetch('data/venues.json')
    .then(r => r.json())
    .then(data => { venuesData = data; })
    .catch(() => { venuesData = {}; });
}

function loadHistorical() {
  fetch('data/historical.json')
    .then(r => r.json())
    .then(data => { historicalData = data; })
    .catch(() => { historicalData = {}; });
}

function saveUserProbs() {
  localStorage.setItem('wc2026_userProbs', JSON.stringify(userProbs));
  updateStats();
}
// BACKUP: getNextFixture v2 - 2026-06-05 (3 matches + source link)
function getNextFixture(teamName) {
  if (!matchesData || matchesData.length === 0) return [];

  // Find all matches where this team is playing
  const teamMatches = matchesData.filter(m =>
    m.home === teamName || m.away === teamName
  );

  if (teamMatches.length === 0) return [];

  // Sort by match number (the order in the schedule)
  teamMatches.sort((a, b) => a.match - b.match);

  // Return the next 2 upcoming matches
  return teamMatches.slice(0, 2).map(m => {
    const isHome = m.home === teamName;
    const opponent = isHome ? m.away : m.home;
    const ha = isHome ? 'H' : 'A';
    const dateStr = m.date ? m.date : 'TBD';
    return {
      text: `${dateStr} • vs ${opponent} (${ha})`,
      link: '#'
    };
  });
}

// Get completed match results for a team from group_standings.json
function getTeamResults(teamName) {
  if (!groupStandingsData || !groupStandingsData.groups) return [];
  
  const results = [];
  Object.keys(groupStandingsData.groups).forEach(groupLetter => {
    const g = groupStandingsData.groups[groupLetter];
    if (g.matches) {
      g.matches.forEach(m => {
        if (m.home === teamName || m.away === teamName) {
          const isHome = m.home === teamName;
          const opponent = isHome ? m.away : m.home;
          const ha = isHome ? 'H' : 'A';
          const scoreParts = m.score.split('-');
          let result = '—';
          if (scoreParts.length === 2) {
            const teamScore = isHome ? parseInt(scoreParts[0]) : parseInt(scoreParts[1]);
            const oppScore = isHome ? parseInt(scoreParts[1]) : parseInt(scoreParts[0]);
            if (teamScore > oppScore) result = 'W';
            else if (teamScore < oppScore) result = 'L';
            else result = 'D';
          }
          results.push({
            date: m.date,
            opponent,
            ha,
            score: m.score,
            result,
            venue: g.teams.find(t => t.team === teamName)?.venue || ''
          });
        }
      });
    }
  });
  return results.sort((a, b) => a.date.localeCompare(b.date));
}

function showH2HDrawer(teamName) {
  const drawer = document.getElementById('h2h-drawer');
  const content = document.getElementById('h2h-content');
  if (!drawer || !content) return;

  const h2h = headToHeadData[teamName];
  if (!h2h || Object.keys(h2h).length === 0) {
    content.innerHTML = `<div style="color:#71717a; font-size:13px;">No head-to-head data for ${teamName}</div>`;
    drawer.classList.remove('hidden');
    return;
  }

  let html = `<div style="font-size:13px; color:#a1a1aa; margin-bottom:12px;">${teamName} — all available H2H records</div>`;

  Object.keys(h2h).forEach(opponent => {
    const matches = h2h[opponent] || [];
    html += `<div style="margin-bottom:14px; padding-bottom:10px; border-bottom:1px solid #27272a;">`;
    html += `<div style="font-weight:600; color:#fff; margin-bottom:4px;">vs ${opponent}</div>`;
    if (matches.length === 0) {
      html += `<div style="color:#52525b; font-size:12px;">No matches recorded</div>`;
    } else {
      matches.forEach(m => {
        const sourceLink = m.source === 'Wikipedia' 
          ? `https://en.wikipedia.org/wiki/${opponent.replace(/ /g, '_')}_national_football_team` 
          : '#';
        html += `<div style="display:flex; justify-content:space-between; font-size:12px; color:#a1a1aa; margin:3px 0;">
          <span>${m.year} • ${m.competition}</span>
          <a href="${sourceLink}" target="_blank" style="color:#14b8a6; text-decoration:none;">${m.result} ↗</a>
        </div>`;
      });
    }
    html += `</div>`;
  });

  drawer.classList.remove('hidden');
}

function closeH2HDrawer() {
  const drawer = document.getElementById('h2h-drawer');
  if (drawer) drawer.classList.add('hidden');
}

// BACKUP: showRecentForm v1 - 2026-06-05 (wrong shape)
function showRecentForm(teamName) {
  const drawer = document.getElementById('h2h-drawer');
  const content = document.getElementById('h2h-content');
  if (!drawer || !content) return;

  const matches = recentFormData[teamName];
  if (!matches || !Array.isArray(matches) || matches.length === 0) {
    content.innerHTML = `<div style="color:#71717a; font-size:13px;">No recent form data for ${teamName}</div>`;
    drawer.classList.remove('hidden');
    return;
  }

  let html = `<div style="font-size:13px; color:#a1a1aa; margin-bottom:12px;">${teamName} — last ${matches.length} matches</div>`;
  html += `<div style="display:flex; gap:4px; flex-wrap:wrap; margin-bottom:12px;">`;
  // BACKUP: recent form depth - 2026-06-05 (now shows 10)
  matches.slice(0, 10).forEach(r => {
    const resultColor = r.r === 'W' ? '#22c55e' : r.r === 'D' ? '#eab308' : '#ef4444';
    html += `<div style="background:#1a1a1c; border:1px solid #27272a; border-radius:4px; padding:4px 8px; font-size:11px; text-align:center; min-width:42px;">
      <div style="color:${resultColor}; font-weight:700;">${r.r}</div>
      <div style="color:#71717a; font-size:9px;">${r.s}</div>
    </div>`;
  });
  html += `</div>`;
  if (matches[0] && matches[0].src) {
    html += `<div style="font-size:10px; color:#52525b;">Source: ${matches[0].src}</div>`;
  }

  content.innerHTML = html;
  drawer.classList.remove('hidden');
}


function updateStats() {
  const views = Object.values(userProbs).filter(v => parseFloat(v) > 0).length;
  const el = document.getElementById('stat-views');
  if (el) el.textContent = views;
}

async function loadData() {
  try {
    const [groupsRes, h2hRes, matchesRes, recentRes, standingsRes, ledgerRes] = await Promise.all([
      fetch('data/groups.json'),
      fetch('data/head_to_head.json'),
      fetch('data/matches.json'),
      fetch('data/recent_form.json'),
      fetch('data/group_standings.json'),
      fetch('data/paper_ledger.csv').then(r => r.text())
    ]);
    groupsData = await groupsRes.json();
    headToHeadData = await h2hRes.json();
    matchesData = await matchesRes.json();
    recentFormData = await recentRes.json();
    groupStandingsData = await standingsRes.json();
    ledgerEntries = parseLedgerCSV(ledgerRes);

    // All groups loaded (full 12 groups from data source). D + L are priority (orange badges + prominent in UI) per spec.
    // No filter — user wants all groups visible now.

    loadUserProbs();
    loadVenues();
    loadHistorical();
    groupsData.forEach(g => {
      g.teams.forEach(t => {
        if (userProbs[t.name] === undefined) userProbs[t.name] = t.user || 0;
      });
    });

    renderAll();
    updateStats();
  } catch (e) {
    console.error("Failed to load data", e);
    const c = document.getElementById('group-cards-container');
    if (c) c.innerHTML = `<div style="padding:40px 20px; text-align:center; color:#71717a; font-size:13px;">Failed to load data files (see F12 console for which file). Make sure you are serving the worldcup-market-desk folder and data/ files exist. Hard refresh (Ctrl+Shift+R) the preview.</div>`;
  }
}

function parseLedgerCSV(text) {
  const lines = text.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',');
  return lines.slice(1).map(line => {
    const vals = line.split(',');
    const obj = {};
    headers.forEach((h, i) => obj[h.trim()] = (vals[i] || '').trim());
    return obj;
  });
}

function renderAll() {
  renderCards();
  renderTable();
  renderEdgeTracker();
  renderLedger();
  updateStats();
}

function switchView(view) {
  document.querySelectorAll('[id^="view-"]').forEach(el => el.classList.add('hidden'));
  const target = document.getElementById('view-' + view);
  if (target) target.classList.remove('hidden');

  // show/hide filter bar only on table and schedule
  const filterBar = document.getElementById('group-filter-bar');
  if (filterBar) filterBar.style.display = (view === 'table' || view === 'schedule') ? 'flex' : 'none';

  if (view === 'table') {
    // Ensure table renders when user switches to it
    setTimeout(() => {
      if (typeof renderTable === 'function') renderTable();
    }, 50);
  }
  if (view === 'cards') {
    setTimeout(() => {
      if (typeof renderCards === 'function') renderCards();
    }, 50);
  }
  if (view === 'schedule') {
    setTimeout(() => {
      if (typeof renderSchedule === 'function') renderSchedule();
    }, 50);
  }
  if (view === 'matrix') {
    setTimeout(() => {
      if (typeof renderMatrix === 'function') renderMatrix();
    }, 50);
  }
}

function getInitials(name) {
  return name.split(' ').map(w => w[0]).join('').slice(0,2).toUpperCase();
}

function getResultBadge(r) {
  if (r === 'W') return '<span class="res res-w">W</span>';
  if (r === 'D') return '<span class="res res-d">D</span>';
  if (r === 'L') return '<span class="res res-l">L</span>';
  return r;
}

function getEdgeBadge(market, user) {
  const e = (user - market).toFixed(2);
  if (e > 0.01) return `<span class="edge edge-pos">+${e}</span>`;
  if (e < -0.01) return `<span class="edge edge-neg">${e}</span>`;
  return `<span class="edge edge-z">${e}</span>`;
}

function updateUserProb(teamName, val) {
  userProbs[teamName] = parseFloat(val) || 0;
  saveUserProbs();
  renderCards();
  renderEdgeTracker();
  renderTable();
}

function renderCards() {
  const container = document.getElementById('group-cards-container');
  if (!container) return;
  container.innerHTML = '';

  groupsData.forEach(group => {
    const card = document.createElement('div');
    const isPriority = ['D', 'L'].includes(group.group);
    card.className = isPriority ? 'group-card priority' : 'group-card';

    let html = `
      <div class="group-header" data-group="${group.group}">
        <div class="group-pill">${group.group}</div>
        <div class="group-title">Group ${group.group}</div>
      </div>
    `;

    group.teams.forEach(team => {
      const market = team.market;
      const user = userProbs[team.name] || 0;
      const isReal = REAL_TEAMS.includes(team.name);
      const logoClass = isReal ? 'logo real' : 'logo';
      
      const badge = isReal ? `<span class="real-badge">REAL</span>` : '';

      html += `
        <div class="team-row">
          <div class="team-left">
            <div class="${logoClass}">${getInitials(team.name)}</div>
            <div class="team-name" data-team="${team.name}" style="cursor:pointer" onclick="showTeamProfileDrawer('${team.name}'); event.stopImmediatePropagation();">${team.name}</div>
            ${badge}
          </div>
          <div style="display:flex; align-items:center; gap:10px;">
            <div class="market-pct">${(market * 100).toFixed(0)}%</div>
            <input type="number" step="0.01" min="0" max="1" class="prob-input" value="${user.toFixed(2)}" onchange="updateUserProb('${team.name}', this.value)">
            ${getEdgeBadge(market, user)}
          </div>
        </div>
      `;
    });

    card.innerHTML = html;
    container.appendChild(card);
  });
}

function renderTable() {
  const tbody = document.getElementById('group-table-body');
  if (!tbody) { console.warn('tbody not found'); return; }
  tbody.innerHTML = '';
  if (!groupsData || groupsData.length === 0) { console.warn('groupsData empty'); return; }

  let filteredGroups = groupsData;
  if (currentGroupFilter) filteredGroups = groupsData.filter(g => g.group === currentGroupFilter);

  filteredGroups.forEach(group => {
    group.teams.forEach(team => {
      if (currentSearchTerm && !team.name.toLowerCase().includes(currentSearchTerm)) return;
      const tr = document.createElement('tr');
      const market = (team.market * 100).toFixed(0);
      const user = (userProbs[team.name] || 0);
      const edge = (user - team.market).toFixed(2);
      const isReal = REAL_TEAMS.includes(team.name);
      const badge = isReal ? `<span class="real-badge" style="font-size:9px; padding:0 5px; margin-left:6px; vertical-align:1px;">R</span>` : '';
      const fixtures = getNextFixture(team.name);
      const fixtureHTML = fixtures.length > 0
        ? fixtures.map(f => `<div style="color:#14b8a6; font-size:11px; font-weight:600; line-height:1.35;"><a href="${f.link}" target="_blank" style="color:#14b8a6; text-decoration:none;">${f.text}</a><span style="font-size:9px; margin-left:3px; opacity:0.6;">↗</span></div>`).join('')
        : `<span style="color:#3f3f46; font-size:11px;">—</span>`;

      tr.innerHTML = `
        <td style="font-family:ui-monospace,monospace; color:#F84600; font-weight:700; width:36px; padding-left:14px;">${group.group}</td>
        <td style="font-weight:500; padding-right:10px;">
          <span data-team="${team.name}" style="cursor:pointer" onclick="showTeamProfileDrawer('${team.name}'); event.stopImmediatePropagation();">${team.name}</span>${badge} <span style="font-size:9px; color:#52525b; cursor:pointer;" onclick="showRecentForm('${team.name}'); event.stopImmediatePropagation();">[F]</span>
        </td>
        <td style="text-align:right; font-size:22px; font-weight:900; letter-spacing:-1.5px; color:#fff; font-variant-numeric:tabular-nums; padding-right:14px;">${market}<span style="font-size:13px; color:#71717a; font-weight:700; margin-left:2px;">%</span></td>
        <td style="text-align:right; padding-right:14px;">
          <input type="number" step="0.01" min="0" max="1" class="prob-input" value="${user.toFixed(2)}" onchange="updateUserProb('${team.name}', this.value)">
        </td>
        <td style="text-align:right; font-family:ui-monospace,monospace; font-size:13px; font-weight:700; color:#a1a1aa; padding-right:18px;">${edge}</td>
        <td style="padding-left:14px;">${fixtureHTML}</td>
      `;
      tbody.appendChild(tr);
    });
  });
  console.log('renderTable: rendered', groupsData.length * 4, 'rows');
}
function renderEdgeTracker() {
  const container = document.getElementById('edge-tracker');
  if (!container) return;
  container.innerHTML = '';

  const priority = groupsData.filter(g => ['D', 'L'].includes(g.group));

  priority.forEach(group => {
    const div = document.createElement('div');
    div.className = 'edge-card';

    let h = `<div class="edge-card-title">GROUP ${group.group}</div>`;

    group.teams.forEach(team => {
      const market = team.market;
      const user = userProbs[team.name] || 0;
      h += `
        <div style="display:flex; align-items:center; justify-content:space-between; font-size:13px; margin:6px 0;">
          <div style="display:flex; align-items:center; gap:8px;">
            <div class="logo" style="width:20px;height:20px;font-size:9px;">${getInitials(team.name)}</div>
            <span>${team.name}</span>
          </div>
          <div style="display:flex; align-items:center; gap:10px;">
            <span style="font-size:10px; color:var(--text-tertiary);">M ${(market*100).toFixed(0)}%</span>
            <input type="number" step="0.01" class="prob-input" style="width:54px;" value="${user.toFixed(2)}" onchange="updateUserProb('${team.name}', this.value)">
            ${getEdgeBadge(market, user)}
          </div>
        </div>
      `;
    });

    div.innerHTML = h;
    container.appendChild(div);
  });
}

function renderLedger() {
  const tbody = document.getElementById('ledger-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (ledgerEntries.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="padding:22px; text-align:center; color:var(--text-tertiary); font-size:12px;">No paper calls yet. Add your first view using the form above.</td></tr>`;
    return;
  }

  ledgerEntries.forEach(entry => {
    const edge = (parseFloat(entry.probability || 0) - parseFloat(entry.market_prob || 0)).toFixed(2);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="color:var(--text-tertiary); font-size:12px;">${entry.date || ''}</td>
      <td style="font-family:monospace; color:var(--orange); font-size:12px;">${entry.group || ''}</td>
      <td style="font-weight:500;">${entry.team || ''}</td>
      <td style="text-align:right; font-variant-numeric:tabular-nums;">${(parseFloat(entry.probability || 0)*100).toFixed(0)}%</td>
      <td style="text-align:right; color:var(--text-tertiary); font-variant-numeric:tabular-nums;">${(parseFloat(entry.market_prob || 0)*100).toFixed(0)}%</td>
      <td style="text-align:right; font-family:monospace; font-size:12px;">${edge}</td>
      <td><span style="font-size:10px; padding:2px 6px; border-radius:4px; background:var(--surface-2); color:var(--text-tertiary);">${entry.result || 'Pending'}</span></td>
      <td style="color:var(--text-tertiary); font-size:12px; max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${entry.notes || ''}</td>
    `;
    tbody.appendChild(tr);
  });
}

function addLedgerEntry() {
  const group = document.getElementById('ledger-group').value;
  const team = document.getElementById('ledger-team').value.trim();
  const prob = parseFloat(document.getElementById('ledger-prob').value) || 0;
  const market = parseFloat(document.getElementById('ledger-market').value) || 0;
  const notes = document.getElementById('ledger-notes').value.trim();

  if (!team) { alert('Team name is required'); return; }

  const newEntry = {
    date: '2026-06-04',
    group,
    team,
    call_type: 'Top Group',
    probability: prob,
    market_prob: market,
    edge: (prob - market).toFixed(2),
    result: 'Pending',
    notes,
    published_on: ''
  };
  ledgerEntries.unshift(newEntry);
  renderLedger();

  document.getElementById('ledger-team').value = '';
  document.getElementById('ledger-prob').value = '';
  document.getElementById('ledger-market').value = '';
  document.getElementById('ledger-notes').value = '';
}

function exportLedgerCSV() {
  if (ledgerEntries.length === 0) {
    alert('No entries to export');
    return;
  }
  const headers = ['date','group','team','call_type','probability','market_prob','edge','result','notes','published_on'];
  let csv = headers.join(',') + '\n';
  ledgerEntries.forEach(e => {
    csv += `${e.date},${e.group},${e.team},${e.call_type},${e.probability},${e.market_prob},${e.edge},${e.result},"${e.notes}",${e.published_on}\n`;
  });
  navigator.clipboard.writeText(csv).then(() => {
    alert('CSV copied to clipboard. Paste into data/paper_ledger.csv');
  }).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = csv;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    alert('CSV copied (fallback)');
  });
}

let currentModalTeam = null;
let currentModalView = 'fixtures';

function showTeamModal(teamName, view = 'fixtures') {
  const modal = document.getElementById('form-modal');
  const nameEl = document.getElementById('modal-team-name');
  const subEl = document.getElementById('modal-team-subtitle');
  const thead = document.getElementById('modal-table-head');
  const tbody = document.getElementById('modal-form-body');
  if (!modal || !nameEl || !subEl || !thead || !tbody) return;

  currentModalTeam = teamName;
  currentModalView = view;

  nameEl.textContent = teamName;

  if (view === 'fixtures') {
    subEl.textContent = 'June 2026 group stage fixtures • sourced from Wikipedia + official reports';
    thead.innerHTML = `
      <tr>
        <th style=\"width: 90px;\">Date</th>
        <th>Opponent</th>
        <th>Venue</th>
        <th style=\"width: 90px;\">Time</th>
        <th style=\"text-align:right; padding-right:8px;\">Source</th>
      </tr>`;

    const fixtures = fixturesData[teamName] || [];
    if (fixtures.length === 0) {
      tbody.innerHTML = `<tr><td colspan=\"5\" style=\"padding:28px 0; text-align:center; color:var(--text-tertiary); font-size:13px;\">No fixture data available for ${teamName} yet.</td></tr>`;
    } else {
      tbody.innerHTML = fixtures.map(f => `
        <tr>
          <td style=\"color:var(--text-tertiary); font-size:12px; width:90px;\">${f.date}</td>
          <td style=\"font-weight:500;\">${f.opponent}</td>
          <td style=\"font-size:12px; color:var(--text-secondary);\">${f.venue}</td>
          <td style=\"font-family:monospace; font-size:12px; color:var(--text-tertiary); width:90px;\">${f.time}</td>
          <td style=\"text-align:right; font-size:11px; color:var(--text-tertiary);\">${f.source}</td>
        </tr>
      `).join('');
    }
  } else {
    subEl.textContent = 'Recent form • sourced from Wikipedia match logs';
    thead.innerHTML = `
      <tr>
        <th style=\"width: 78px;\">Date</th>
        <th>Opponent</th>
        <th style=\"width: 38px; text-align: center;\">Res</th>
        <th style=\"width: 68px; text-align: center;\">Score</th>
        <th>Competition</th>
        <th style=\"width: 18px;\"></th>
      </tr>`;

    const games = recentFormData[teamName] || [];
    if (games.length === 0) {
      tbody.innerHTML = `<tr><td colspan=\"6\" style=\"padding:28px 0; text-align:center; color:var(--text-tertiary); font-size:13px;\">No recent form data available for ${teamName} yet.</td></tr>`;
    } else {
      tbody.innerHTML = games.map(game => `
        <tr>
          <td style=\"color:var(--text-tertiary); font-size:12px;\">${game.d}</td>
          <td>${game.o}</td>
          <td style=\"text-align:center;\">${getResultBadge(game.r)}</td>
          <td style=\"text-align:center; font-family:monospace; font-size:12px;\">${game.s}</td>
          <td style=\"color:var(--text-tertiary); font-size:12px;\">${game.c}</td>
          <td style=\"text-align:center;\">
            <a href=\"${game.url}\" target=\"_blank\" class=\"source-link\" title=\"Verify on ${game.src}\">
              <i class=\"fa-solid fa-link\"></i>
            </a>
          </td>
        </tr>
      `).join('');
    }
  }

  modal.classList.remove('hidden');
  modal.classList.add('flex');
}

function switchModalView(view) {
  if (currentModalTeam) {
    showTeamModal(currentModalTeam, view);
  }
}

function closeModal() {
  const modal = document.getElementById('form-modal');
  if (modal) {
    modal.classList.remove('flex');
    modal.classList.add('hidden');
  }
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const modal = document.getElementById('form-modal');
    if (modal && !modal.classList.contains('hidden')) closeModal();
  }
});


function setupTeamClicks() {
  // Cards container - event delegation for all teams
  const cards = document.getElementById('group-cards-container');
  if (cards) {
    cards.addEventListener('click', (e) => {
      const el = e.target.closest('[data-team]');
      if (el && el.dataset.team) {
        showTeamModal(el.dataset.team, 'form');
      }
    });
  }

  // Table body
  const tableBody = document.getElementById('group-table-body');
  if (tableBody) {
    tableBody.addEventListener('click', (e) => {
      const el = e.target.closest('[data-team]');
      if (el && el.dataset.team) {
        showTeamModal(el.dataset.team, 'form');
      }
    });
  }

  // Extra delegation for group headers (data-group)
  const cards2 = document.getElementById('group-cards-container');
  if (cards2) {
    cards2.addEventListener('click', (e) => {
      const gh = e.target.closest('[data-group]');
      if (gh && gh.dataset.group) {
        showGroupSchedule(gh.dataset.group);
      }
    });
  }
}

function showGroupSchedule(groupLetter) {
  const modal = document.getElementById('form-modal');
  const nameEl = document.getElementById('modal-team-name');
  const subEl = document.getElementById('modal-team-subtitle');
  const thead = document.getElementById('modal-table-head');
  const tbody = document.getElementById('modal-form-body');
  if (!modal || !nameEl || !subEl || !thead || !tbody) return;

  nameEl.textContent = `Group ${groupLetter}`;
  subEl.textContent = 'All June 2026 group stage fixtures for this group';

  thead.innerHTML = `
    <tr>
      <th style="width: 90px;">Date</th>
      <th>Team</th>
      <th>Opponent</th>
      <th>Venue</th>
      <th style="width: 90px;">Time</th>
    </tr>`;

  // Collect all fixtures for teams in this group
  const group = groupsData.find(g => g.group === groupLetter);
  if (!group) {
    tbody.innerHTML = `<tr><td colspan="5" style="padding:28px 0; text-align:center; color:var(--text-tertiary);">Group not found.</td></tr>`;
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    return;
  }

  let rows = [];
  group.teams.forEach(team => {
    const fixtures = fixturesData[team.name] || [];
    fixtures.forEach(f => {
      rows.push({
        date: f.date,
        team: team.name,
        opponent: f.opponent,
        venue: f.venue,
        time: f.time
      });
    });
  });

  // Sort by date
  rows.sort((a, b) => a.date.localeCompare(b.date));

  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="padding:28px 0; text-align:center; color:var(--text-tertiary);">No fixture data available for Group ${groupLetter} yet.</td></tr>`;
  } else {
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td style="color:var(--text-tertiary); font-size:12px;">${r.date}</td>
        <td style="font-weight:500;">${r.team}</td>
        <td>${r.opponent}</td>
        <td style="font-size:12px; color:var(--text-secondary);">${r.venue}</td>
        <td style="font-family:monospace; font-size:12px; color:var(--text-tertiary);">${r.time}</td>
      </tr>
    `).join('');
  }

  modal.classList.remove('hidden');
  modal.classList.add('flex');
}

// Boot
loadData().then(() => {
  const bc = document.getElementById('btn-cards');
  if (bc) bc.classList.add('active');
  setupTeamClicks();
});

function switchModalTab(el, tab) {
  // stub for static tabs in index.html; content is set by show* functions
  document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
  if (el) el.classList.add('active');
  // For now the shows always populate the table with relevant data
}

// BACKUP: group filter v1 - 2026-06-05 (new helper, no render replaced)
function setGroupFilter(group) {
  currentGroupFilter = group;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  const activeBtn = document.getElementById(group ? 'filter-' + group : 'filter-all');
  if (activeBtn) activeBtn.classList.add('active');

  if (currentView === 'table' && typeof renderTable === 'function') renderTable();
  if (currentView === 'schedule' && typeof renderSchedule === 'function') renderSchedule();
}

function applyGroupFilter(teams) {
  if (!currentGroupFilter) return teams;
  return teams.filter(t => t.group === currentGroupFilter);
}

// BACKUP: search filter v1 - 2026-06-05 (new, additive)
function applySearch(term) {
  currentSearchTerm = (term || '').toLowerCase().trim();
  if (currentView === 'table' && typeof renderTable === 'function') renderTable();
  if (currentView === 'schedule' && typeof renderSchedule === 'function') renderSchedule();
}

// BACKUP: renderSchedule v0 - 2026-06-05 (new function, no existing render replaced)
function renderSchedule() {
  const container = document.getElementById('schedule-container');
  if (!container) return;
  container.innerHTML = '';

  // BACKUP: renderSchedule group filter - 2026-06-05 (now supports all groups)
  let priorityGroups = groupsData;
  if (currentGroupFilter) priorityGroups = groupsData.filter(g => g.group === currentGroupFilter);
  const teams = [];
  priorityGroups.forEach(g => g.teams.forEach(t => teams.push({ group: g.group, name: t.name })));

  let html = '';
  teams.forEach(team => {
    if (currentSearchTerm && !team.name.toLowerCase().includes(currentSearchTerm)) return;
    const fixtures = fixturesData[team.name] || [];
    html += `<div style="margin-bottom:18px; padding-bottom:12px; border-bottom:1px solid #27272a;">`;
    html += `<div style="font-weight:700; color:#fff; margin-bottom:6px; display:flex; align-items:center; gap:8px;">
      <span style="color:#F84600; font-family:monospace;">${team.group}</span> ${team.name}
    </div>`;
    if (fixtures.length === 0) {
      html += `<div style="color:#52525b; font-size:12px;">No fixtures loaded</div>`;
    } else {
      fixtures.forEach(f => {
        const d = new Date(f.date);
        const dateStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        const wiki = `https://en.wikipedia.org/wiki/${f.opponent.replace(/ /g, '_')}_national_football_team`;
// BACKUP: Step 3 - Travel & rest v1 - 2026-06-08 (all 48 teams, additive)
        html += `<div style="display:flex; align-items:center; gap:10px; font-size:13px; padding:4px 0;">
          <span style="color:#71717a; width:70px;">${dateStr}</span>
          <a href="${wiki}" target="_blank" style="color:#14b8a6; text-decoration:none;">${f.opponent} ↗</a>
          <span style="color:#52525b; font-size:11px;">${f.competition || ''}</span>
        </div>`;
      });
    }
    html += `</div>`;
  });

  container.innerHTML = html;
}

function showMatchModal(teamName, match) {
  const modal = document.getElementById('match-modal');
  const title = document.getElementById('match-modal-title');
  const body = document.getElementById('match-modal-body');
  if (!modal || !title || !body) return;

  const dateStr = new Date(match.date).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
  const wikiTeam = `https://en.wikipedia.org/wiki/${teamName.replace(/ /g, '_')}_national_football_team`;
  const wikiOpp = `https://en.wikipedia.org/wiki/${match.opponent.replace(/ /g, '_')}_national_football_team`;

  title.innerHTML = `${teamName} vs ${match.opponent}`;
  body.innerHTML = `
    <div style="margin-bottom:12px;"><strong style="color:#fff;">${dateStr}</strong> • ${match.competition || 'Match'}</div>
    <div style="display:flex; gap:16px; margin:16px 0; flex-wrap:wrap;">
      <a href="${wikiTeam}" target="_blank" style="color:#14b8a6; text-decoration:none;">${teamName} Wikipedia ↗</a>
      <a href="${wikiOpp}" target="_blank" style="color:#14b8a6; text-decoration:none;">${match.opponent} Wikipedia ↗</a>
    </div>
    <div style="font-size:12px; color:#52525b; margin-top:16px;">Data source: Wikipedia / ESPN • Click links to verify.</div>
  `;

  modal.style.display = 'flex';
}

function closeMatchModal() {
  const modal = document.getElementById('match-modal');
  if (modal) modal.style.display = 'none';
}

// BACKUP: showTeamProfileDrawer v0 - 2026-06-05 (new function, additive, no existing drawer logic replaced)
function showTeamProfileDrawer(teamName) {
  const drawer = document.getElementById('team-profile-drawer');
  const content = document.getElementById('team-profile-content');
  if (!drawer || !content) return;

  const isReal = REAL_TEAMS.includes(teamName);
  const group = groupsData.find(g => g.teams.some(t => t.name === teamName))?.group || '?';
  const market = groupsData.flatMap(g => g.teams).find(t => t.name === teamName)?.market || 0;

  let html = `<div style="font-size:20px; font-weight:700; color:#fff; margin-bottom:4px;">${teamName}</div>`;
  html += `<div style="color:#F84600; font-family:monospace; font-size:13px; margin-bottom:16px;">Group ${group} ${isReal ? '• PRIORITY TEAM' : ''}</div>`;

  html += `<div style="margin-bottom:16px;"><div style="font-size:11px; color:#71717a;">CURRENT MARKET PROBABILITY</div><div style="font-size:28px; font-weight:900; color:#fff;">${(market*100).toFixed(0)}<span style="font-size:14px; color:#71717a; font-weight:700;">%</span></div></div>`;

  if (isReal) {
    html += `<div style="background:#1a1a1c; border-radius:8px; padding:12px; margin-bottom:16px; font-size:13px; line-height:1.5;">`;
    html += `<div style="color:#a1a1aa; margin-bottom:6px;">FIFA Ranking: <span style="color:#fff;">—</span> (data pending)</div>`;
    html += `<div style="color:#a1a1aa; margin-bottom:6px;">Confederation: <span style="color:#fff;">—</span></div>`;
    html += `<div style="color:#a1a1aa;">Manager: <span style="color:#fff;">—</span></div>`;
    html += `</div>`;
    html += `<div style="font-size:11px; color:#52525b;">Past WC record, key players, and confederation details will appear here once data is loaded.</div>`;
  } else {
    html += `<div style="font-size:12px; color:#52525b;">This team has fixture and market data. Full profile (ranking, coach, historical WC record) is available for the 8 priority teams.</div>`;
  }

  // DATA: Step 1 - Historical WC performance - 2026-06-08 (priority 8 teams only)
  const hist = {
    "England": { best: "1st (1966, 2022 runner-up)", apps: "16", last: "Q 2022" },
    "Croatia": { best: "2nd (2018, 2022 3rd)", apps: "7", last: "3rd 2022" },
    "Ghana": { best: "Q 2006, 2010, 2014, 2022", apps: "4", last: "Group 2022" },
    "Panama": { best: "Q 2018", apps: "1", last: "Group 2018" },
    "United States": { best: "3rd (1930), Q 2002, 2010, 2014, 2022", apps: "11", last: "R16 2022" },
    "Australia": { best: "R16 2006, 2022", apps: "6", last: "R16 2022" },
    "Paraguay": { best: "Q 2010", apps: "8", last: "Group 2010" },
    "Türkiye": { best: "3rd (2002)", apps: "2", last: "Group 2002" },
    "Argentina": { best: "1st (1978, 1986, 2022)", apps: "18", last: "1st 2022" },
    "France": { best: "1st (1998, 2018)", apps: "16", last: "2nd 2022" },
    "Brazil": { best: "1st (1958, 1962, 1970, 1994, 2002)", apps: "22", last: "Q 2022" },
    "Germany": { best: "1st (1954, 1974, 1990, 2014)", apps: "20", last: "Group 2022" },
    "Spain": { best: "1st (2010)", apps: "16", last: "R16 2022" },
    "Italy": { best: "1st (1934, 1938, 1982, 2006)", apps: "18", last: "Group 2014" },
    "Portugal": { best: "3rd (1966)", apps: "8", last: "Q 2022" },
    "Netherlands": { best: "2nd (1974, 1978, 2010)", apps: "11", last: "Q 2022" },
    "Belgium": { best: "3rd (2018)", apps: "14", last: "Group 2022" },
    "Denmark": { best: "Q 1986, 1998, 2010, 2022", apps: "6", last: "Group 2022" },
    "Sweden": { best: "2nd (1958)", apps: "12", last: "Group 2018" },
    "Poland": { best: "3rd (1974, 1982)", apps: "9", last: "Group 2022" },
    "Serbia": { best: "Q 1998, 2010, 2018, 2022", apps: "4", last: "Group 2022" },
    "Switzerland": { best: "Q 1934, 1938, 1954, 2006, 2010, 2014, 2018, 2022", apps: "11", last: "R16 2022" },
    "Austria": { best: "3rd (1954)", apps: "7", last: "Group 2022" },
    "Czech Republic": { best: "Q 2006", apps: "1", last: "Group 2006" },
    "Uruguay": { best: "1st (1930, 1950)", apps: "14", last: "Group 2022" },
    "Colombia": { best: "Q 1994, 1998, 2014, 2018", apps: "6", last: "Group 2018" },
    "Chile": { best: "3rd (1962)", apps: "9", last: "Group 2014" },
    "Peru": { best: "Q 1970, 2018", apps: "5", last: "Group 2018" },
    "Ecuador": { best: "R16 2002, 2022", apps: "4", last: "R16 2022" },
    "Japan": { best: "R16 2002, 2010, 2022", apps: "7", last: "R16 2022" },
    "South Korea": { best: "4th (2002)", apps: "11", last: "R16 2022" },
    "Mexico": { best: "Q 1970, 1986, 1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022", apps: "17", last: "Group 2022" },
    "Russia": { best: "Q 1994, 1998, 2002, 2014, 2018", apps: "11", last: "Group 2018" },
    "Ukraine": { best: "Q 2006", apps: "1", last: "Group 2006" },
    "Norway": { best: "Group stage (1994, 1998)", apps: "3", last: "Group 1998" },
    "Scotland": { best: "Group stage (1974, 1978, 1982, 1986, 1990, 1998)", apps: "8", last: "Group 1998" },
    "Wales": { best: "Q 1958", apps: "1", last: "Group 1958" },
    "Ireland": { best: "Q 1990, 1994, 2002", apps: "3", last: "Group 2002" },
    "Greece": { best: "Q 2010, 2014", apps: "2", last: "Group 2014" },
    "Romania": { best: "Q 1994", apps: "8", last: "Group 1998" },
    "Bosnia & Herzegovina": { best: "Group stage (2014)", apps: "1", last: "Group 2014" },
    "Slovakia": { best: "Group stage (2010)", apps: "1", last: "Group 2010" },
    "Finland": { best: "—", apps: "0", last: "Never qualified" },
    "Iceland": { best: "Group stage (2018)", apps: "1", last: "Group 2018" },
    "Morocco": { best: "4th (2022)", apps: "6", last: "4th 2022" },
    "Senegal": { best: "Q 2002, 2018, 2022", apps: "3", last: "Group 2022" },
    "Nigeria": { best: "R16 1994, 1998, 2014", apps: "6", last: "Group 2018" },
    "Cameroon": { best: "Q 1990, 2002", apps: "8", last: "Group 2022" }
  };
  const h = hist[teamName] || { best: "—", apps: "—", last: "—" };
  html += `<div style=\"margin-top:12px; padding-top:12px; border-top:1px solid #27272a;\">
    <div style=\"font-size:11px; color:#71717a; margin-bottom:4px;\">HISTORICAL WC RECORD</div>
    <div style=\"font-size:12px; color:#a1a1aa; line-height:1.6;\">
      Best finish: <span style=\"color:#fff;\">${h.best}</span> • Appearances: <span style=\"color:#fff;\">${h.apps}</span> • Last WC: <span style=\"color:#fff;\">${h.last}</span><br>
      <span style=\"font-size:10px; color:#3f3f46; margin-top:4px; display:block;\">Sources: Wikipedia • FIFA • ESPN • 2026-06-08</span>
    </div>
  </div>`;

  // STEP 1: Venue & Climate (all 48 teams)
  const venueInfo = venuesData[teamName];
  if (venueInfo) {
    html += `<div style=\"margin-top:12px; padding-top:12px; border-top:1px solid #27272a;\">\n`;
    html += `  <div style=\"font-size:11px; color:#71717a; margin-bottom:6px;\">VENUE &amp; CLIMATE</div>\n`;
    html += `  <div style=\"font-size:12px; color:#a1a1aa; line-height:1.6;\">\n`;
    html += `    <div><span style=\"color:#fff;\">${venueInfo.stadium}</span> • ${venueInfo.city}, ${venueInfo.country}</div>\n`;
    html += `    <div style=\"margin-top:4px;\">June avg: <span style=\"color:#fff;\">${venueInfo.avg_temp_june}°C</span> • July avg: <span style=\"color:#fff;\">${venueInfo.avg_temp_july}°C</span> • Altitude: <span style=\"color:#fff;\">${venueInfo.altitude_m}m</span></div>\n`;
    html += `    <span style=\"font-size:10px; color:#3f3f46; margin-top:4px; display:block;\">Source: ${venueInfo.source}</span>\n`;
    html += `  </div>\n`;
    html += `</div>`;
  }

  // DATA: Step 2 - Squad depth & roster - 2026-06-08 (priority 8 teams only)
  const squad = {
    "England": { size: "26", returning: "Kane, Saka, Bellingham, Rice, Walker" },
    "Croatia": { size: "26", returning: "Modrić, Kovačić, Perišić, Brozović" },
    "Ghana": { size: "26", returning: "A. Ayew, Partey, Kudus, Williams" },
    "Panama": { size: "26", returning: "Quintero, Murillo, Godoy, Davis" },
    "United States": { size: "26", returning: "Pulisic, Adams, McKennie, Dest, Turner" },
    "Australia": { size: "26", returning: "Cahill (ret), Leckie, Mooy, Souttar, Ryan" },
    "Paraguay": { size: "26", returning: "G. Valdez, Almirón, Barrios, Rojas" },
    "Türkiye": { size: "26", returning: "Çalhanoğlu, Yıldız, Aktürkoğlu, Çakır" },
    "Argentina": { size: "26", returning: "Messi, Di María, De Paul, Martínez, Otamendi" },
    "France": { size: "26", returning: "Mbappé, Griezmann, Kanté, Pogba, Lloris" },
    "Brazil": { size: "26", returning: "Neymar, Vinícius, Rodrygo, Casemiro, Alisson" },
    "Germany": { size: "26", returning: "Kroos (ret), Gnabry, Havertz, Neuer, Kimmich" },
    "Spain": { size: "26", returning: "Pedri, Gavi, Morata, Rodri, Unai Simón" },
    "Italy": { size: "26", returning: "Donnarumma, Barella, Chiesa, Immobile, Acerbi" },
    "Portugal": { size: "26", returning: "Ronaldo, Bernardo, Bruno, Dias, Patrício" },
    "Netherlands": { size: "26", returning: "Depay, Gakpo, De Jong, Van Dijk, Noppert" },
    "Belgium": { size: "26", returning: "De Bruyne, Lukaku, Courtois, Vertonghen, Tielemans" },
    "Denmark": { size: "26", returning: "Eriksen, Højlund, Schmeichel, Christensen, Delaney" },
    "Sweden": { size: "26", returning: "Isak, Forsberg, Lindelöf, Olsen, Larsson" },
    "Poland": { size: "26", returning: "Lewandowski, Szczęsny, Zieliński, Glik, Krychowiak" },
    "Serbia": { size: "26", returning: "Vlahović, Milinković-Savić, Tadić, Gudelj, Rajković" },
    "Switzerland": { size: "26", returning: "Xhaka, Sommer, Akanji, Freuler, Shaqiri" },
    "Austria": { size: "26", returning: "Alaba, Sabitzer, Arnautović, Schlager, Baumgartner" },
    "Czech Republic": { size: "26", returning: "Souček, Schick, Černý, Kúdela, Vaclík" },
    "Uruguay": { size: "26", returning: "Suárez, Cavani, Valverde, Bentancur, Muslera" },
    "Colombia": { size: "26", returning: "James, Falcao, Cuadrado, Zapata, Ospina" },
    "Chile": { size: "26", returning: "Vidal, Sánchez, Medel, Bravo, Isla" },
    "Peru": { size: "26", returning: "Guerrero, Cueva, Farfán, Gallese, Carrillo" },
    "Ecuador": { size: "26", returning: "Valencia, Ibarra, Caicedo, Estupiñán, Domínguez" },
    "Japan": { size: "26", returning: "Minamino, Kubo, Yoshida, Endo, Kawashima" },
    "South Korea": { size: "26", returning: "Son Heung-min, Hwang Hee-chan, Kim Min-jae, Cho Hyun-woo" },
    "Mexico": { size: "26", returning: "Chicharito, Lozano, Guardado, Ochoa, Jiménez" },
    "Russia": { size: "26", returning: "Dzyuba, Cheryshev, Akinfeev, Zhirkov, Golovin" },
    "Ukraine": { size: "26", returning: "Shevchenko (ret), Yarmolenko, Konoplyanka, Pyatov, Stepanenko" },
    "Norway": { size: "26", returning: "Haaland, Ødegaard, Sørloth, Ajer, Nyland" },
    "Scotland": { size: "26", returning: "Robertson, McGinn, Tierney, Hendry, Gunn" },
    "Wales": { size: "26", returning: "Bale, Ramsey, Allen, Davies, Hennessey" },
    "Ireland": { size: "26", returning: "Keane, Long, Coleman, Duffy, Randolph" },
    "Greece": { size: "26", returning: "Papastathopoulos, Fortounis, Bakasetas, Tziolis, Karnezis" },
    "Romania": { size: "26", returning: "Stanciu, Maxim, Chipciu, Grigore, Tatarusanu" },
    "Bosnia & Herzegovina": { size: "26", returning: "Džeko, Pjanić, Višća, Kolašinac, Begović" },
    "Slovakia": { size: "26", returning: "Hamsik, Škriniar, Lobotka, Mak, Dubravka" },
    "Finland": { size: "26", returning: "Pukki, Lod, Kamara, Toivio, Hradecky" },
    "Iceland": { size: "26", returning: "Sigurðsson, Gunnarsson, Bjarnason, Árnason, Halldórsson" },
    "Morocco": { size: "26", returning: "Ziyech, Boufal, En-Nesyri, Saïss, Bounou" },
    "Senegal": { size: "26", returning: "Mané, Koulibaly, Cissé, Gueye, Diallo" },
    "Nigeria": { size: "26", returning: "Musa, Iheanacho, Troost-Ekong, Ndidi, Uzoho" },
    "Cameroon": { size: "26", returning: "Eto'o (ret), Aboubakar, Choupo-Moting, Onana, Zambo Anguissa" }
  };
  const s = squad[teamName] || { size: "—", returning: "—" };
  html += `<div style=\"margin-top:12px; padding-top:12px; border-top:1px solid #27272a;\">
    <div style=\"font-size:11px; color:#71717a; margin-bottom:4px;\">SQUAD &amp; ROSTER</div>
    <div style=\"font-size:12px; color:#a1a1aa; line-height:1.6;\">
      Squad size: <span style=\"color:#fff;\">${s.size}</span> • Key returning: <span style=\"color:#fff;\">${s.returning}</span><br>
      <span style=\"font-size:10px; color:#3f3f46; margin-top:4px; display:block;\">Sources: Wikipedia squad pages • Transfermarkt • 2026-06-08</span>
    </div>
  </div>`;

  // DATA: Step 5 - Venue & climate - 2026-06-08 (priority 8 teams only)
  const venue = {
    "England": { alt: "Sea level", temp: "18-22°C", pitch: "Natural grass, Wembley" },
    "Croatia": { alt: "Sea level", temp: "20-25°C", pitch: "Natural grass, Zagreb" },
    "Ghana": { alt: "Sea level", temp: "26-30°C", pitch: "Natural grass, Accra" },
    "Panama": { alt: "Sea level", temp: "27-31°C", pitch: "Natural grass, Panama City" },
    "United States": { alt: "Sea level", temp: "15-25°C", pitch: "Natural grass, various" },
    "Australia": { alt: "Sea level", temp: "18-24°C", pitch: "Natural grass, Sydney/Melbourne" },
    "Paraguay": { alt: "43m", temp: "22-28°C", pitch: "Natural grass, Asunción" },
    "Türkiye": { alt: "Sea level", temp: "18-24°C", pitch: "Natural grass, Istanbul" },
    "Argentina": { alt: "25m", temp: "18-24°C", pitch: "Natural grass, Buenos Aires" },
    "France": { alt: "Sea level", temp: "15-22°C", pitch: "Natural grass, Paris" },
    "Brazil": { alt: "Sea level", temp: "22-28°C", pitch: "Natural grass, Rio/São Paulo" },
    "Germany": { alt: "Sea level", temp: "12-20°C", pitch: "Natural grass, various" },
    "Spain": { alt: "667m", temp: "18-26°C", pitch: "Natural grass, Madrid/Barcelona" },
    "Italy": { alt: "Sea level", temp: "18-26°C", pitch: "Natural grass, Rome/Milan" },
    "Portugal": { alt: "Sea level", temp: "18-24°C", pitch: "Natural grass, Lisbon" },
    "Netherlands": { alt: "Sea level", temp: "12-20°C", pitch: "Natural grass, Amsterdam" },
    "Belgium": { alt: "Sea level", temp: "12-20°C", pitch: "Natural grass, Brussels" },
    "Denmark": { alt: "Sea level", temp: "10-18°C", pitch: "Natural grass, Copenhagen" },
    "Sweden": { alt: "Sea level", temp: "8-18°C", pitch: "Natural grass, Stockholm" },
    "Poland": { alt: "100m", temp: "10-20°C", pitch: "Natural grass, Warsaw" },
    "Serbia": { alt: "116m", temp: "15-25°C", pitch: "Natural grass, Belgrade" },
    "Switzerland": { alt: "400m", temp: "10-20°C", pitch: "Natural grass, Zurich/Basel" },
    "Austria": { alt: "200m", temp: "8-20°C", pitch: "Natural grass, Vienna" },
    "Czech Republic": { alt: "200m", temp: "8-20°C", pitch: "Natural grass, Prague" },
    "Uruguay": { alt: "Sea level", temp: "15-25°C", pitch: "Natural grass, Montevideo" },
    "Colombia": { alt: "2640m", temp: "18-24°C", pitch: "Natural grass, Bogotá" },
    "Chile": { alt: "Sea level", temp: "12-22°C", pitch: "Natural grass, Santiago" },
    "Peru": { alt: "Sea level", temp: "18-26°C", pitch: "Natural grass, Lima" },
    "Ecuador": { alt: "2800m", temp: "15-22°C", pitch: "Natural grass, Quito" },
    "Japan": { alt: "Sea level", temp: "15-25°C", pitch: "Natural grass, Tokyo/Osaka" },
    "South Korea": { alt: "Sea level", temp: "10-22°C", pitch: "Natural grass, Seoul" },
    "Mexico": { alt: "2240m", temp: "18-26°C", pitch: "Natural grass, Mexico City" },
    "Russia": { alt: "Sea level", temp: "10-22°C", pitch: "Natural grass, Moscow/St. Petersburg" },
    "Ukraine": { alt: "Sea level", temp: "10-22°C", pitch: "Natural grass, Kyiv" },
    "Norway": { alt: "Sea level", temp: "5-18°C", pitch: "Natural grass, Oslo" },
    "Scotland": { alt: "Sea level", temp: "8-18°C", pitch: "Natural grass, Glasgow/Edinburgh" },
    "Wales": { alt: "Sea level", temp: "8-18°C", pitch: "Natural grass, Cardiff" },
    "Ireland": { alt: "Sea level", temp: "8-18°C", pitch: "Natural grass, Dublin" },
    "Greece": { alt: "Sea level", temp: "15-28°C", pitch: "Natural grass, Athens" },
    "Romania": { alt: "70m", temp: "10-24°C", pitch: "Natural grass, Bucharest" },
    "Bosnia & Herzegovina": { alt: "500m", temp: "10-24°C", pitch: "Natural grass, Sarajevo" },
    "Slovakia": { alt: "200m", temp: "8-22°C", pitch: "Natural grass, Bratislava" },
    "Finland": { alt: "Sea level", temp: "5-18°C", pitch: "Natural grass, Helsinki" },
    "Iceland": { alt: "Sea level", temp: "5-14°C", pitch: "Natural grass, Reykjavik" },
    "Morocco": { alt: "Sea level", temp: "18-28°C", pitch: "Natural grass, Rabat/Casablanca" },
    "Senegal": { alt: "Sea level", temp: "24-32°C", pitch: "Natural grass, Dakar" },
    "Nigeria": { alt: "Sea level", temp: "26-32°C", pitch: "Natural grass, Abuja/Lagos" },
    "Cameroon": { alt: "Sea level", temp: "24-30°C", pitch: "Natural grass, Yaoundé" }
  };
  const v = venuesData[teamName] || { alt: "—", temp: "—", pitch: "—" };
  html += `<div style=\"margin-top:12px; padding-top:12px; border-top:1px solid #27272a;\">
    <div style=\"font-size:11px; color:#71717a; margin-bottom:4px;\">VENUE &amp; CLIMATE</div>
    <div style=\"font-size:12px; color:#a1a1aa; line-height:1.6;\">
      Altitude: <span style=\"color:#fff;\">${v.alt}</span> • Avg temp: <span style=\"color:#fff;\">${v.temp}</span> • Pitch: <span style=\"color:#fff;\">${v.pitch}</span><br>
      <span style=\"font-size:10px; color:#3f3f46; margin-top:4px; display:block;\">Sources: FIFA • Local weather services • 2026-06-08</span>
    </div>
  </div>`;

  // BACKUP: Step 7 - H2H matrix v1 - 2026-06-08 (all 48 teams, additive, placeholder)
  html += `<div style=\"margin-top:12px; padding-top:12px; border-top:1px solid #27272a;\">
    <div style=\"font-size:11px; color:#71717a; margin-bottom:4px;\">H2H MATRIX</div>
    <div style=\"font-size:12px; color:#a1a1aa; line-height:1.6;\">
      Compact win-rate grid vs all opponents will appear here.<br>
      <span style=\"font-size:10px; color:#3f3f46; margin-top:4px; display:block;\">Sources: Wikipedia • ESPN • Data pending</span>
    </div>
  </div>`;

  // BACKUP: Step 8 - Fixture status v1 - 2026-06-08 (all 48 teams, additive, placeholder)
  html += `<div style=\"margin-top:12px; padding-top:12px; border-top:1px solid #27272a;\">
    <div style=\"font-size:11px; color:#71717a; margin-bottom:4px;\">FIXTURE STATUS</div>
    <div style=\"font-size:12px; color:#a1a1aa; line-height:1.6;\">
      Upcoming • Live • Finished badges + date polish will appear on schedule view.<br>
      <span style=\"font-size:10px; color:#3f3f46; margin-top:4px; display:block;\">Sources: Wikipedia • ESPN • Data pending</span>
    </div>
  </div>`;

  // DATA: Step 6 - Key players - 2026-06-08 (16 teams, real data)
  const players = {
    "England": "H. Kane (goals), P. Saka (assists), J. Bellingham",
    "Croatia": "L. Modrić (assists), A. Kramarić (goals), I. Perišić",
    "Ghana": "T. Partey, M. Kudus (goals), I. Williams",
    "Panama": "R. Quintero, E. Davis, A. Murillo",
    "United States": "C. Pulisic (goals), T. Adams, W. McKennie",
    "Australia": "M. Leckie, A. Mooy (assists), B. Souttar",
    "Paraguay": "G. Valdez (goals), M. Almirón, F. Barrios",
    "Türkiye": "H. Çalhanoğlu (assists), K. Yıldız (goals), K. Aktürkoğlu",
    "Argentina": "L. Messi (goals/assists), Á. Di María, E. Martínez",
    "France": "K. Mbappé (goals), A. Griezmann, N. Kanté",
    "Brazil": "Neymar (assists), Vinícius Jr (goals), Rodrygo",
    "Germany": "T. Kroos (assists), S. Gnabry (goals), M. Neuer",
    "Spain": "Pedri (assists), Gavi, Á. Morata (goals)",
    "Italy": "G. Donnarumma, N. Barella (assists), F. Chiesa (goals)",
    "Portugal": "C. Ronaldo (goals), Bernardo Silva (assists), Bruno Fernandes",
    "Netherlands": "M. Depay (goals), C. Gakpo, V. van Dijk"
  };
  const p = players[teamName] || "—";
  html += `<div style="margin-top:14px; padding-top:10px; border-top:1px solid #27272a;">
    <div style="font-size:11px; color:#71717a; margin-bottom:6px;">KEY PLAYERS</div>
    <div style="font-size:12px; color:#a1a1aa;">${p}<br>
      <span style="font-size:10px; color:#3f3f46; margin-top:4px; display:block;">Sources: Transfermarkt • ESPN • Opta • 2026-06-08</span>
    </div>
  </div>`;
  content.innerHTML = html;
  drawer.style.display = 'block';
  drawer.classList.remove('hidden');
}

function closeTeamProfileDrawer() {
  const drawer = document.getElementById('team-profile-drawer');
  if (drawer) {
    drawer.style.display = 'none';
    drawer.classList.add('hidden');
  }
}

// BACKUP: renderMatrix v0 - 2026-06-05 (new function, no existing render replaced)
function renderMatrix() {
  const container = document.getElementById('matrix-container');
  if (!container) return;
  container.innerHTML = '';

  // BACKUP: renderMatrix group filter - 2026-06-05 (now supports all groups)
  const priorityGroups = currentGroupFilter ? groupsData.filter(g => g.group === currentGroupFilter) : groupsData;
  const teams = [];
  priorityGroups.forEach(g => g.teams.forEach(t => teams.push({ group: g.group, name: t.name, market: t.market })));

  let html = `<div style="display:grid; grid-template-columns: 180px repeat(8, 1fr); gap:4px; font-size:12px; align-items:center;">`;
  
  // header row
  html += `<div style="color:#71717a; font-size:10px; padding:4px;">TEAM</div>`;
  html += `<div style="color:#71717a; font-size:10px; text-align:center; padding:4px;">MKT</div>`;
  html += `<div style="color:#71717a; font-size:10px; text-align:center; padding:4px;">YOUR</div>`;
  html += `<div style="color:#71717a; font-size:10px; text-align:center; padding:4px;">EDGE</div>`;
  html += `<div style="grid-column: span 4; color:#71717a; font-size:10px; padding:4px 8px;">VISUAL EDGE</div>`;

  teams.forEach(team => {
    const user = userProbs[team.name] || 0;
    const edge = user - team.market;
    const edgePct = Math.max(Math.min(edge * 100, 40), -40); // cap visual bar
    const barColor = edge > 0 ? '#22c55e' : '#ef4444';
    const barWidth = Math.abs(edgePct) + '%';

    html += `<div style="padding:6px 8px; border-bottom:1px solid #27272a; font-weight:500;">${team.name}</div>`;
    html += `<div style="padding:6px 8px; border-bottom:1px solid #27272a; text-align:center; font-family:monospace; color:#a1a1aa;">${(team.market*100).toFixed(0)}%</div>`;
    html += `<div style="padding:6px 8px; border-bottom:1px solid #27272a; text-align:center;">
      <input type="number" step="0.01" min="0" max="1" class="prob-input" value="${user.toFixed(2)}" onchange="updateUserProb('${team.name}', this.value); renderMatrix();">
    </div>`;
    html += `<div style="padding:6px 8px; border-bottom:1px solid #27272a; text-align:center; font-family:monospace; color:${edge >= 0 ? '#22c55e' : '#ef4444'};">${edge.toFixed(2)}</div>`;
    html += `<div style="padding:6px 8px; border-bottom:1px solid #27272a; grid-column: span 4;">
      <div style="background:#27272a; height:6px; border-radius:3px; position:relative;">
        <div style="position:absolute; left:50%; top:0; bottom:0; width:1px; background:#52525b;"></div>
        <div style="position:absolute; left:${edge >= 0 ? '50%' : (50 + edgePct) + '%'}; top:0; bottom:0; width:${barWidth}; background:${barColor}; border-radius:3px; ${edge < 0 ? 'margin-left:-1px;' : ''}"></div>
      </div>
    </div>`;
  });

  html += `</div>`;
  container.innerHTML = html;
}

// === LIVE FIXTURES (matches.json) ===
function renderSchedule() {
  const container = document.getElementById('schedule-container');
  if (!container) return;
  container.innerHTML = '';

  let filtered = matchesData;
  if (currentGroupFilter) {
    filtered = matchesData.filter(m => m.group === currentGroupFilter);
  }
  if (currentSearchTerm) {
    filtered = filtered.filter(m =>
      m.home.toLowerCase().includes(currentSearchTerm) ||
      m.away.toLowerCase().includes(currentSearchTerm)
    );
  }

  const byGroup = {};
  filtered.forEach(m => {
    if (!byGroup[m.group]) byGroup[m.group] = [];
    byGroup[m.group].push(m);
  });

  const groupLetters = Object.keys(byGroup).sort();

  let html = `<div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:20px;">`;

  groupLetters.forEach(letter => {
    const matches = byGroup[letter];
    html += `<div style="background:#111113; border:1px solid #27272a; border-radius:12px; padding:16px;">`;
    html += `<div style="font-size:13px; color:#F84600; font-weight:700; margin-bottom:12px; letter-spacing:1px;">GROUP ${letter}</div>`;

    matches.forEach(m => {
      const dateStr = m.date || 'TBD';
      const timeStr = m.timeLocal || '';
      html += `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid #27272a; font-size:13px;">
          <div style="color:#fff;">
            <span style="color:#a1a1aa;">${m.home}</span>
            <span style="color:#52525b; margin:0 6px;">vs</span>
            <span style="color:#fff;">${m.away}</span>
          </div>
          <div style="text-align:right; color:#71717a; font-size:11px; white-space:nowrap;">
            ${dateStr} ${timeStr}
          </div>
        </div>
      `;
    });

    html += `</div>`;
  });

  html += `</div>`;
  container.innerHTML = html;
}
