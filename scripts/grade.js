// Grade the weekly-bet picks against real NFL results from ESPN's public API.
// Usage: node scripts/grade.js data/bet-specs.txt data/bet-grades.json
// See the header of data/bet-specs.txt for the bet format.
const fs = require('fs');

const SITE = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl';
const norm = s => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[’'.]/g, '').replace(/-/g, ' ').replace(/\b(jr|sr|ii|iii|iv|v)\b/g, '').replace(/\s+/g, ' ').trim();

async function getJSON(url) {
  for (let i = 1; ; i++) {
    const r = await fetch(url, { headers: { 'User-Agent': 'corknpork.net bet grader' } });
    if (r.ok) return r.json();
    if (i >= 4) throw new Error(`${r.status} for ${url}`);
    await new Promise(res => setTimeout(res, 1000 * i));
  }
}

const boards = {}, summaries = {};
async function board(y, wk) {
  const k = `${y}-${wk}`;
  if (!boards[k]) {
    const j = await getJSON(`${SITE}/scoreboard?dates=${y}&seasontype=2&week=${wk}&limit=40`);
    boards[k] = (j.events || []).map(e => {
      const c = e.competitions[0];
      const side = h => c.competitors.find(x => x.homeAway === h);
      const t = x => ({ name: x.team.name, abbr: x.team.abbreviation, score: Number(x.score), winner: !!x.winner });
      const odds = (c.odds || [])[0] || {};
      return { id: e.id, done: c.status.type.completed, home: t(side('home')), away: t(side('away')), total: odds.overUnder ?? null, date: e.date };
    });
  }
  return boards[k];
}
async function summary(id) {
  if (!summaries[id]) summaries[id] = getJSON(`${SITE}/summary?event=${id}`);
  return summaries[id];
}
const teamGame = (games, team) => games.find(g => norm(g.home.name) === norm(team) || norm(g.away.name) === norm(team));

// player box-score line for one game
function playerLine(sum, who) {
  const want = norm(who);
  let found = null;
  for (const tm of (sum.boxscore && sum.boxscore.players) || []) {
    for (const cat of tm.statistics || []) {
      for (const a of cat.athletes || []) {
        if (norm(a.athlete && a.athlete.displayName) !== want) continue;
        found = found || { team: tm.team.abbreviation, s: {} };
        (cat.keys || []).forEach((k, i) => { found.s[k] = a.stats[i]; });
      }
    }
  }
  return found;
}
const num = v => { const n = parseFloat(String(v ?? '').split('/')[0]); return isNaN(n) ? 0 : n; };
const tdPlays = sum => (sum.scoringPlays || []).filter(p => /touchdown/i.test((p.type && p.type.text) || '') || /\bTD\b/.test((p.type && p.type.abbreviation) || ''));
const scoredTD = (sum, who) => tdPlays(sum).some(p => norm(p.text).startsWith(norm(who) + ' '));

async function findPlayer(y, wk, who) {
  const games = (await board(y, wk)).filter(g => g.done);
  const sums = await Promise.all(games.map(g => summary(g.id)));
  for (let i = 0; i < games.length; i++) {
    const line = playerLine(sums[i], who);
    if (line) return { game: games[i], sum: sums[i], line };
  }
  return null;
}
const cmp = (v, op, line) => op === '>' ? v > line : op === '>=' ? v >= line : op === '<' ? v < line : v <= line;
const gameTxt = g => `${g.away.name} ${g.away.score}, ${g.home.name} ${g.home.score}`;

async function grade(y, wk, bet) {
  const [kind, ...rest] = bet.split(' ');
  const arg = rest.join(' ');
  if (kind === '?') return { res: 'n/a', note: arg };
  const games = await board(y, wk);

  if (kind === 'ml' || kind === 'sp') {
    const parts = arg.split(' ');
    const line = kind === 'sp' ? parseFloat(parts.pop()) : 0;
    const team = parts.join(' ');
    const g = teamGame(games, team);
    if (!g) return { res: 'n/a', note: `${team} had no game in week ${wk}` };
    if (!g.done) return { res: 'n/a', note: 'game not final yet' };
    const me = norm(g.home.name) === norm(team) ? g.home : g.away, op = me === g.home ? g.away : g.home;
    const margin = me.score - op.score;
    const adj = margin + line;
    const res = kind === 'ml' ? (margin > 0 ? 'hit' : margin < 0 ? 'miss' : 'push') : (adj > 0 ? 'hit' : adj < 0 ? 'miss' : 'push');
    return { res, note: gameTxt(g) };
  }
  if (kind === 'tot') {
    const [side, lineS, ...teams] = rest;
    const g = teamGame(games, teams[0]);
    if (!g) return { res: 'n/a', note: `${teams[0]} had no game in week ${wk}` };
    if (!g.done) return { res: 'n/a', note: 'game not final yet' };
    let line = lineS === '-' ? null : parseFloat(lineS), src = '';
    if (line == null) {
      const sum = await summary(g.id);
      const pc = (sum.pickcenter || []).find(p => p.overUnder != null);
      line = pc ? pc.overUnder : g.total;
      if (line == null) {  // older games drop pickcenter; the core API still has the pregame line
        try {
          const o = await getJSON(`https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/${g.id}/competitions/${g.id}/odds`);
          const pre = (o.items || []).find(i => i.overUnder != null && !/live/i.test((i.provider && i.provider.name) || ''));
          if (pre) line = pre.overUnder;
        } catch (e) { /* fall through */ }
      }
      src = ' (closing total)';
      if (line == null) return { res: 'n/a', note: `no line given and no closing total found; ${gameTxt(g)}` };
    }
    const pts = g.home.score + g.away.score;
    const res = pts === line ? 'push' : ((pts > line) === (side === 'o') ? 'hit' : 'miss');
    return { res, note: `${pts} points vs ${line}${src}; ${gameTxt(g)}` };
  }
  if (kind === 'dst') {
    const g = teamGame(games, arg);
    if (!g) return { res: 'n/a', note: `${arg} had no game in week ${wk}` };
    const sum = await summary(g.id);
    const abbr = norm(g.home.name) === norm(arg) ? g.home.abbr : g.away.abbr;
    const plays = tdPlays(sum).filter(p => p.team && p.team.abbreviation === abbr && /return|fumble|blocked|safety|interception/i.test(p.type.text || ''));
    return { res: plays.length ? 'hit' : 'miss', note: plays.length ? plays[0].text : `no defensive or return TD; ${gameTxt(g)}` };
  }
  if (kind === 'td' || kind === 'ftd') {
    const f = await findPlayer(y, wk, arg);
    if (!f) return { res: 'n/a', note: `${arg} didn't play in week ${wk}` };
    if (kind === 'ftd') {
      const first = tdPlays(f.sum)[0];
      const hit = first && norm(first.text).startsWith(norm(arg) + ' ');
      return { res: hit ? 'hit' : 'miss', note: first ? `first TD: ${first.text}` : 'no touchdowns in the game' };
    }
    const rush = num(f.line.s.rushingTouchdowns), rec = num(f.line.s.receivingTouchdowns);
    const hit = rush + rec > 0 || scoredTD(f.sum, arg);
    return { res: hit ? 'hit' : 'miss', note: hit ? `${rush + rec || 1} TD` + (rush ? ` (${rush} rushing)` : '') + (rec ? ` (${rec} receiving)` : '') : `no TD; ${gameTxt(f.game)}` };
  }
  if (kind === 'stat') {
    const [who, stat, op, lineS] = arg.split(';');
    const f = await findPlayer(y, wk, who);
    if (!f) return { res: 'n/a', note: `${who} didn't play in week ${wk}` };
    const key = { passYds: 'passingYards', rushYds: 'rushingYards', recYds: 'receivingYards', rec: 'receptions', passTD: 'passingTouchdowns', int: 'interceptions' }[stat];
    const v = num(f.line.s[key]);
    if (lineS === '-') return { res: 'n/a', note: `${v} ${stat}; no line written` };
    const line = parseFloat(lineS);
    return { res: cmp(v, op, line) ? 'hit' : 'miss', note: `${v} ${stat} (needed ${op} ${line})` };
  }
  return { res: 'n/a', note: `unknown bet type "${kind}"` };
}

(async () => {
  const [specPath = 'data/bet-specs.txt', outPath = 'data/bet-grades.json'] = process.argv.slice(2);
  const specs = fs.readFileSync(specPath, 'utf8').split('\n').filter(l => l.trim() && !l.startsWith('#')).map(l => l.split('|'));
  const out = [];
  for (const [y, wk, who, bet, call] of specs) {
    let r;
    try { r = await grade(+y, +wk, bet); }
    catch (e) { r = { res: 'n/a', note: 'error: ' + e.message }; }
    // a 5th field is a hand call for a pick the data can't settle on its own (e.g. no line written)
    if (call && r.res === 'n/a') r = { res: call.trim(), note: `${r.note}; called ${call.trim()} by hand` };
    out.push({ y: +y, wk: +wk, who, bet, ...r });
  }
  fs.writeFileSync(outPath, JSON.stringify(out, null, 1) + '\n');
  const c = out.reduce((m, r) => (m[r.res] = (m[r.res] || 0) + 1, m), {});
  console.log(`Graded ${out.length} picks:`, c);
  for (const r of out) console.log(`${r.y} wk${String(r.wk).padStart(2)} ${r.who.padEnd(8)} ${r.res.padEnd(4)} ${r.bet} -- ${r.note}`);
})().catch(e => { console.error(e); process.exit(1); });
