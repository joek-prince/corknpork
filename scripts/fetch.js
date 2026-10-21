// Usage: ESPN_S2=... SWID=... node scripts/fetch.js data/league.json
// Pulls the league from ESPN and writes the compact data file the site is built from.
const fs = require('fs');
const { buildData } = require('./espn.js');

const out = process.argv[2] || 'data/league.json';
const S2 = (process.env.ESPN_S2 || '').trim();
const SWID = (process.env.SWID || '').trim();
const LEAGUE_ID = process.env.LEAGUE_ID || '91427782';

// print a problem and keep it in build/alerts.txt for the Slack alert
function alert(msg) {
  console.error(msg);
  try { fs.mkdirSync('build', { recursive: true }); fs.appendFileSync('build/alerts.txt', msg + '\n'); } catch (e) { /* best effort */ }
}

if (!S2 || !SWID) {
  if (process.env.ALLOW_STALE === '1') {
    console.log('ESPN_S2 / SWID secrets are not set, so the site is built from the last saved data.');
    process.exit(0);
  }
  alert('ESPN_S2 and SWID secrets are missing. Add them under Settings > Secrets and variables > Actions.');
  process.exit(1);
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
async function getJSON(url, headers = {}) {
  for (let attempt = 1; ; attempt++) {
    const r = await fetch(url, {
      headers: {
        ...headers,
        Cookie: `espn_s2=${S2}; SWID=${SWID}`,
        Accept: 'application/json',
        'User-Agent': 'Mozilla/5.0 (corknpork.net weekly build)'
      }
    });
    if (r.ok) return r.json();
    if (r.status === 401 || r.status === 403) {
      throw new Error(`ESPN refused the request (${r.status}). The ESPN_S2 / SWID cookies have probably expired; copy fresh ones from espn.com.`);
    }
    if (r.status === 404 || attempt >= 4) {
      const e = new Error(`ESPN returned ${r.status} for ${url}`); e.status = r.status; throw e;
    }
    await sleep(1500 * attempt);
  }
}

(async () => {
  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' });
  const D = await buildData(getJSON, { leagueId: LEAGUE_ID, today });
  fs.mkdirSync(require('path').dirname(out), { recursive: true });
  fs.writeFileSync(out, JSON.stringify(D) + '\n');
  console.log(`Saved ${out}: season ${D.current}, ${D.doneWeeks} weeks complete, ${Object.keys(D.seasons).length} seasons.`);
})().catch(e => { alert(e.message || String(e)); process.exit(1); });
