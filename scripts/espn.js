// Pulls a private ESPN fantasy football league's full history into one compact JSON object.
// Transport is injected (getJSON) so the same code runs in Node (cookies from env) or a signed-in browser.
async function buildData(getJSON, opts) {
  const LID = opts.leagueId;
  const base = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl';
  const r1 = x => Math.round(x * 10) / 10;
  const r2 = x => x == null ? null : Math.round(x * 100) / 100;
  const POS = { 1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'D/ST' };
  const get = (y, views, extra = '', headers) =>
    getJSON(`${base}/seasons/${y}/segments/0/leagues/${LID}?${views.map(v => 'view=' + v).join('&')}${extra}`, headers);

  // ---- which season is current ----
  let cur = opts.season, status;
  if (!cur) {
    const yr = new Date(opts.today + 'T12:00:00Z').getUTCFullYear();
    for (const y of [yr, yr - 1]) {
      try { const j = await get(y, ['mStatus']); if (j && j.status) { cur = y; status = j.status; break; } } catch (e) { if (e.status !== 404) throw e; }
    }
    if (!cur) throw new Error('Could not find a current season for league ' + LID);
  }
  if (!status) status = (await get(cur, ['mStatus'])).status;
  const seasons = [...(status.previousSeasons || []).filter(y => y >= (opts.firstSeason || 0)), cur];

  // ---- every season: teams, schedule, draft ----
  const H = {};
  for (const y of seasons) {
    const j = await get(y, ['mTeam', 'mSettings', 'mMatchupScore', 'mDraftDetail', 'mStatus']);
    const members = (j.members || []).map(m => ({ id: m.id, fn: m.firstName, ln: m.lastName }));
    const teams = (j.teams || []).map(t => ({
      id: t.id, name: (t.name || ((t.location || '') + ' ' + (t.nickname || ''))).trim(), primary: t.primaryOwner,
      rank: t.rankCalculatedFinal, seed: t.playoffSeed,
      w: t.record && t.record.overall.wins, l: t.record && t.record.overall.losses, tie: t.record && t.record.overall.ties,
      pf: t.record && t.record.overall.pointsFor, pa: t.record && t.record.overall.pointsAgainst,
      moves: t.transactionCounter && { acq: t.transactionCounter.acquisitions, trades: t.transactionCounter.trades }
    }));
    const sch = (j.schedule || []).map(m => [m.matchupPeriodId, m.home && m.home.teamId, m.home && m.home.totalPoints,
      m.away ? m.away.teamId : null, m.away ? m.away.totalPoints : null, m.winner, m.playoffTierType]);
    const picks = ((j.draftDetail && j.draftDetail.picks) || []).map(p => [p.roundId, p.overallPickNumber, p.teamId, p.playerId]);
    const ss = j.settings.scheduleSettings;
    H[y] = { members, teams, sch, picks, regWeeks: ss.matchupPeriodCount, playoffTeams: ss.playoffTeamCount, name: j.settings.name,
      done: teams.length > 0 && teams.every(t => t.rank > 0) };
  }

  // ---- drafted players: name, position, season points, preseason projection ----
  for (const y of seasons) {
    const ids = [...new Set(H[y].picks.map(p => p[3]))];
    H[y].pl = {};
    if (!ids.length) continue;
    const j = await get(y, ['kona_player_info'], '', { 'X-Fantasy-Filter': JSON.stringify({ players: { filterIds: { value: ids } } }) });
    for (const p of j.players || []) {
      const st = p.player.stats || [];
      const act = st.find(s => s.statSourceId === 0 && s.statSplitTypeId === 0 && s.scoringPeriodId === 0 && s.seasonId === y);
      const prj = st.find(s => s.statSourceId === 1 && s.statSplitTypeId === 0 && s.scoringPeriodId === 0 && s.seasonId === y);
      H[y].pl[p.id] = [p.player.fullName, p.player.defaultPositionId, act ? r1(act.appliedTotal) : null, prj ? r1(prj.appliedTotal) : null];
    }
  }

  // ---- current season: which weeks are finished, which is next ----
  const C = H[cur];
  let doneWeeks = 0;
  for (let w = 1; w <= C.regWeeks; w++) {
    const g = C.sch.filter(m => m[0] === w && m[6] === 'NONE');
    if (g.length && g.every(m => m[5] && m[5] !== 'UNDECIDED')) doneWeeks = w; else break;
  }
  const previewWeek = doneWeeks < C.regWeeks && C.sch.some(m => m[0] === doneWeeks + 1) ? doneWeeks + 1 : null;

  // ---- current season week by week: lineups, actual and projected points ----
  const wkRaw = {}, pinfo = {};
  const lastWeek = previewWeek || doneWeeks;
  for (let w = 1; w <= lastWeek; w++) {
    const j = await get(cur, ['mMatchupScore', 'mBoxscore'], `&scoringPeriodId=${w}`,
      { 'X-Fantasy-Filter': JSON.stringify({ schedule: { filterMatchupPeriodIds: { value: [w] } } }) });
    const teams = {};
    for (const m of j.schedule || []) {
      if (m.matchupPeriodId !== w) continue;
      for (const side of ['home', 'away']) {
        const s = m[side]; if (!s) continue;
        const ros = (s.rosterForCurrentScoringPeriod || s.rosterForMatchupPeriod || {}).entries || [];
        const e = ros.map(x => {
          const pe = x.playerPoolEntry || {}, pl = pe.player || {};
          const pj = (pl.stats || []).find(st => st.statSourceId === 1 && st.scoringPeriodId === w);
          const ac = (pl.stats || []).find(st => st.statSourceId === 0 && st.scoringPeriodId === w);
          if (!pinfo[x.playerId]) pinfo[x.playerId] = [pl.fullName, pl.defaultPositionId, pl.proTeamId || 0];
          return [x.playerId, x.lineupSlotId, ac ? r2(ac.appliedTotal) : (pe.appliedStatTotal != null ? r2(pe.appliedStatTotal) : 0), pj ? r2(pj.appliedTotal) : null, pl.injuryStatus || null];
        });
        teams[s.teamId] = { e, total: s.totalPoints };
      }
    }
    wkRaw[w] = teams;
  }

  // ---- draft summaries ----
  const draft = {};
  for (const y of seasons) {
    const S = H[y];
    if (!S.picks.length) continue;
    const rows = S.picks.map(p => { const pl = S.pl[p[3]] || ['?', 0, 0, 0]; return { rd: p[0], ov: p[1], tm: p[2], name: pl[0], pos: POS[pl[1]] || '?', act: pl[2] || 0, proj: pl[3] || 0 }; });
    const skill = rows.filter(r => !['K', 'D/ST'].includes(r.pos));
    [...skill].sort((a, b) => b.act - a.act).forEach((r, i) => r.prk = i + 1);
    [...skill].sort((a, b) => a.ov - b.ov).forEach((r, i) => r.drk = i + 1);
    skill.forEach(r => r.val = r.drk - r.prk);
    const steals = [...skill].filter(r => r.rd >= 4).sort((a, b) => b.val - a.val).slice(0, 3);
    const busts = [...skill].filter(r => r.rd <= 3).sort((a, b) => a.val - b.val).slice(0, 3);
    const haul = {}; for (const r of rows) haul[r.tm] = (haul[r.tm] || 0) + r.act;
    const f = r => [r.name, r.pos, r.rd, r.ov, r.tm, r1(r.act), r.prk, r.val];
    const firsts = rows.filter(r => r.rd === 1).sort((a, b) => a.ov - b.ov).map(r => [r.name, r.pos, r.ov, r.tm, r1(r.act), r.prk || null]);
    draft[y] = { steals: steals.map(f), busts: busts.map(f), haul: Object.entries(haul).map(([t, v]) => [+t, r1(v)]).sort((a, b) => b[1] - a[1]), firsts };
  }

  // ---- weekly summaries (best possible lineup: QB, 2 RB, 2 WR, TE, FLEX, D/ST, K) ----
  const opt = ents => {
    const pool = ents.filter(e => e[1] !== 21).map(e => ({ pos: (pinfo[e[0]] || [])[1], pts: e[2] || 0 }));
    const take = (p, n) => { const c = pool.filter(x => x.pos === p && !x.u).sort((a, b) => b.pts - a.pts).slice(0, n); c.forEach(x => x.u = 1); return c.reduce((a, x) => a + x.pts, 0); };
    let t = take(1, 1) + take(2, 2) + take(3, 2) + take(4, 1) + take(5, 1) + take(16, 1);
    const fl = pool.filter(x => [2, 3, 4].includes(x.pos) && !x.u).sort((a, b) => b.pts - a.pts)[0]; if (fl) t += fl.pts; return t;
  };
  const nm = e => e ? (pinfo[e[0]] || ['?'])[0] : null;
  const wk = {};
  for (const [w, teams] of Object.entries(wkRaw)) {
    wk[w] = {};
    for (const [tid, o] of Object.entries(teams)) {
      const st = o.e.filter(e => e[1] !== 20 && e[1] !== 21), bn = o.e.filter(e => e[1] === 20);
      const projSum = st.reduce((a, e) => a + (e[3] || 0), 0);
      const top = [...st].sort((a, b) => (b[2] || 0) - (a[2] || 0))[0];
      const topB = [...bn].sort((a, b) => (b[2] || 0) - (a[2] || 0))[0];
      const topP = [...st].sort((a, b) => (b[3] || 0) - (a[3] || 0))[0];
      const inj = st.filter(e => e[4] && !['ACTIVE', 'NORMAL'].includes(e[4])).map(e => [nm(e), e[4]]);
      wk[w][tid] = +w <= doneWeeks
        ? { a: r1(o.total), p: r1(projSum), o: r1(opt(o.e)), top: [nm(top), r1(top ? top[2] : 0)], bench: [nm(topB), r1(topB ? topB[2] : 0)] }
        : { p: r1(projSum), topP: [nm(topP), r1(topP ? topP[3] : 0)], inj,
            // in-progress week: live total and each starter as [name, NFL proTeamId, points so far, projected]
            a: r1(o.total || 0), live: st.map(e => [nm(e), (pinfo[e[0]] || [])[2] || 0, e[2] || 0, e[3]]) };
    }
  }

  // ---- assemble ----
  const tc = s => (s || '').trim().split(/\s+/).map(w => w ? w[0].toUpperCase() + w.slice(1) : w).join(' ');
  const mem = {}; for (const y of seasons) for (const m of H[y].members) mem[m.id] = tc((m.fn || '') + ' ' + (m.ln || ''));
  const ownIdx = {}, owners = [];
  const oi = id => { if (!(id in ownIdx)) { ownIdx[id] = owners.length; owners.push(mem[id] || 'Unknown'); } return ownIdx[id]; };
  const out = {};
  for (const y of seasons) {
    const S = H[y];
    out[y] = {
      reg: S.regWeeks, po: S.playoffTeams,
      t: S.teams.map(t => [t.id, t.name.replace(/\s+/g, ' '), oi(t.primary), t.rank || 0, t.seed || 0, t.w, t.l, t.tie, r2(t.pf), r2(t.pa), t.moves ? t.moves.acq : 0, t.moves ? t.moves.trades : 0]),
      s: S.sch.map(m => [m[0], m[1], r2(m[2]), m[3], r2(m[4]),
        { HOME: 'H', AWAY: 'A', TIE: 'T', UNDECIDED: 'U' }[m[5]] || m[5],
        { NONE: 'N', WINNERS_BRACKET: 'W', LOSERS_CONSOLATION_LADDER: 'L', WINNERS_CONSOLATION_LADDER: 'C' }[m[6]] || m[6]]),
      done: S.done
    };
  }
  return { league: H[cur].name, asOf: opts.today, curWeek: previewWeek || doneWeeks + 1, owners, seasons: out, draft, wk,
    current: cur, doneWeeks, previewWeek };
}
if (typeof module !== 'undefined') module.exports = { buildData };
