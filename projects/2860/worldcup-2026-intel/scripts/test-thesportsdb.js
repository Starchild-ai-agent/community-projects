#!/usr/bin/env node
// TheSportsDB test script — improved for quality assessment
// Usage:
//   node scripts/test-thesportsdb.js "Belgium"
//   node scripts/test-thesportsdb.js --batch "Poland,Morocco,Croatia,Ghana,Panama,Australia"
//   node scripts/test-thesportsdb.js --json "Japan"

const https = require('https');

const API_KEY = '3';
const BASE = `https://www.thesportsdb.com/api/v1/json/${API_KEY}`;
const cache = new Map();

function get(url) {
  if (cache.has(url)) return Promise.resolve(cache.get(url));

  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if (res.statusCode === 429) {
        reject(new Error('RATE_LIMIT'));
        return;
      }
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          cache.set(url, json);
          resolve(json);
        } catch (e) {
          reject(new Error('JSON_PARSE'));
        }
      });
    }).on('error', reject);
  });
}

function groupPlayers(players) {
  const groups = { GK: [], DEF: [], MID: [], FWD: [] };
  players.forEach(p => {
    const pos = (p.strPosition || '').toLowerCase();
    if (pos.includes('goal')) groups.GK.push(p);
    else if (pos.includes('back') || pos.includes('defen')) groups.DEF.push(p);
    else if (pos.includes('mid')) groups.MID.push(p);
    else if (pos.includes('forward') || pos.includes('winger') || pos.includes('striker')) groups.FWD.push(p);
    else groups.MID.push(p);
  });
  return groups;
}

function formatPlayer(p) {
  const club = p.strTeam || '—';
  let age = '—';
  if (p.dateBorn) {
    const birth = new Date(p.dateBorn);
    age = new Date().getFullYear() - birth.getFullYear();
  }
  return `${p.strPlayer} — ${p.strPosition} (${club}, ${age})`;
}

async function fetchTeam(teamName) {
  const searchUrl = `${BASE}/searchteams.php?t=${encodeURIComponent(teamName)}`;
  const searchRes = await get(searchUrl);

  if (!searchRes.teams || searchRes.teams.length === 0) {
    return { teamName, error: 'TEAM_NOT_FOUND' };
  }

  const team = searchRes.teams[0];
  const playersUrl = `${BASE}/lookup_all_players.php?id=${team.idTeam}`;
  const playersRes = await get(playersUrl);

  if (!playersRes.player || playersRes.player.length === 0) {
    return { teamName, error: 'NO_PLAYERS' };
  }

  // Prefer players whose nationality matches the team name
  const filtered = playersRes.player
    .filter(p => p.strPosition)
    .sort((a, b) => {
      const aMatch = (a.strNationality || '').toLowerCase().includes(teamName.toLowerCase()) ? 1 : 0;
      const bMatch = (b.strNationality || '').toLowerCase().includes(teamName.toLowerCase()) ? 1 : 0;
      return bMatch - aMatch;
    });

  const groups = groupPlayers(filtered);

  return {
    teamName,
    teamId: team.idTeam,
    stadium: team.strStadium || '—',
    totalPlayers: playersRes.player.length,
    groups: {
      GK: groups.GK.slice(0, 3).map(formatPlayer),
      DEF: groups.DEF.slice(0, 4).map(formatPlayer),
      MID: groups.MID.slice(0, 4).map(formatPlayer),
      FWD: groups.FWD.slice(0, 3).map(formatPlayer)
    }
  };
}

async function main() {
  const args = process.argv.slice(2);
  const jsonMode = args.includes('--json');
  const batchMode = args.includes('--batch');

  let teams = [];

  if (batchMode) {
    const batchArg = args.find(a => a.includes(','));
    if (batchArg) teams = batchArg.split(',').map(t => t.trim());
  } else {
    const teamArg = args.find(a => !a.startsWith('--'));
    if (teamArg) teams = [teamArg];
  }

  if (teams.length === 0) {
    console.log('Usage: node scripts/test-thesportsdb.js "Team Name"');
    console.log('       node scripts/test-thesportsdb.js --batch "Poland,Morocco,Croatia"');
    process.exit(1);
  }

  const results = [];
  let rateLimitHit = false;

  for (const team of teams) {
    if (rateLimitHit) {
      results.push({ teamName: team, error: 'SKIPPED_RATE_LIMIT' });
      continue;
    }

    try {
      const result = await fetchTeam(team);
      results.push(result);
    } catch (err) {
      if (err.message === 'RATE_LIMIT') {
        rateLimitHit = true;
        results.push({ teamName: team, error: 'RATE_LIMIT_HIT' });
      } else {
        results.push({ teamName: team, error: err.message });
      }
    }
  }

  if (jsonMode) {
    console.log(JSON.stringify(results, null, 2));
  } else {
    results.forEach(r => {
      if (r.error) {
        console.log(`\n=== ${r.teamName} ===`);
        console.log(`Error: ${r.error}`);
        return;
      }

      console.log(`\n=== ${r.teamName} (ID: ${r.teamId}) ===`);
      console.log(`Stadium: ${r.stadium}`);
      console.log(`Total players: ${r.totalPlayers}\n`);

      ['GK', 'DEF', 'MID', 'FWD'].forEach(g => {
        if (r.groups[g] && r.groups[g].length > 0) {
          console.log(`--- ${g} ---`);
          r.groups[g].forEach(p => console.log(`  ${p}`));
          console.log('');
        }
      });
    });

    console.log('\n--- Summary ---');
    console.log(`Teams tested: ${results.length}`);
    console.log(`Successful: ${results.filter(r => !r.error).length}`);
    console.log(`Source: TheSportsDB (free API) — 30 requests/min limit`);
    console.log(`Note: Data quality varies by team. Nationality filtering is approximate.\n`);
  }
}

main().catch(err => {
  console.error('Fatal error:', err.message);
  process.exit(1);
});