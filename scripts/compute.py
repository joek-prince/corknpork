"""Turn data/league.json into the stats the site renders.

Usage: python3 scripts/compute.py data/league.json build/results.json
"""
import json
import sys
from collections import defaultdict

src = sys.argv[1] if len(sys.argv) > 1 else 'data/league.json'
dst = sys.argv[2] if len(sys.argv) > 2 else 'build/results.json'
D = json.load(open(src))

r1 = lambda x: round(x + 0.0, 1)
r2 = lambda x: round(x + 0.0, 2)


def short(name):
    """'Matt McCormick' -> 'Matt M.' so the public site doesn't carry full surnames."""
    parts = name.split()
    if len(parts) < 2:
        return name
    return f"{parts[0]} {parts[-1][0].upper()}."


OWN = [short(n) for n in D['owners']]
CUR = D['current']
DONE_WEEKS = D['doneWeeks']
PREVIEW = D.get('previewWeek')
YEARS = sorted(int(y) for y in D['seasons'])
SEAS = {y: D['seasons'][str(y)] for y in YEARS}
DONE_YEARS = [y for y in YEARS if SEAS[y].get('done')]

# ---------- normalise games ----------
team_owner, team_name = {}, {}
for y in YEARS:
    for t in SEAS[y]['t']:
        team_owner[(y, t[0])] = t[2]
        team_name[(y, t[0])] = t[1]

games = []  # regular season + winners bracket, decided only
for y in YEARS:
    for wk, h, hp, a, ap, win, tier in SEAS[y]['s']:
        if a is None or win not in ('H', 'A', 'T') or tier not in ('N', 'W'):
            continue
        games.append(dict(y=y, wk=wk, tier=tier, h=h, a=a, hp=hp, ap=ap,
                          ho=team_owner[(y, h)], ao=team_owner[(y, a)], win=win))


def sides(g):
    res_h = 'W' if g['win'] == 'H' else ('L' if g['win'] == 'A' else 'T')
    res_a = {'W': 'L', 'L': 'W', 'T': 'T'}[res_h]
    yield g['ho'], g['h'], g['hp'], g['ao'], g['a'], g['ap'], res_h
    yield g['ao'], g['a'], g['ap'], g['ho'], g['h'], g['hp'], res_a


def rec_str(t):
    return f"{t[5]}-{t[6]}" + (f"-{t[7]}" if t[7] else '')


# ---------- season summaries ----------
seasons_out = []
for y in YEARS:
    S = SEAS[y]
    T = S['t']
    n = len(T)
    row = {'year': y, 'teams': n, 'reg': S['reg'], 'po': S['po'], 'done': y in DONE_YEARS}
    if row['done']:
        by_rank = {t[3]: t for t in T}

        def tl(t):
            return {'team': t[1], 'owner': OWN[t[2]], 'oi': t[2], 'rec': rec_str(t), 'seed': t[4], 'pf': r1(t[8])}
        row.update(champ=tl(by_rank[1]), runner=tl(by_rank[2]), third=tl(by_rank[3]), last=tl(by_rank[n]),
                   topSeed=tl(min(T, key=lambda t: t[4])), topPF=tl(max(T, key=lambda t: t[8])))
        finals = [g for g in games if g['y'] == y and g['tier'] == 'W']
        if finals:
            last_wk = max(g['wk'] for g in finals)
            fg = [g for g in finals if g['wk'] == last_wk and {g['h'], g['a']} == {by_rank[1][0], by_rank[2][0]}]
            if fg:
                g = fg[0]
                c = g['h'] == by_rank[1][0]
                row['final'] = [r2(g['hp'] if c else g['ap']), r2(g['ap'] if c else g['hp'])]
    seasons_out.append(row)

# ---------- all-time owner table ----------
own = {i: defaultdict(float) for i in range(len(OWN))}
for i in own:
    own[i]['best'] = 99
for y in YEARS:
    S = SEAS[y]
    n = len(S['t'])
    for t in S['t']:
        o = own[t[2]]
        o['seasons'] += 1
        if y in DONE_YEARS:
            o['done'] += 1
            if t[4] <= S['po']:
                o['po_apps'] += 1
            if t[3] == 1:
                o['titles'] += 1
            if t[3] in (1, 2):
                o['finals'] += 1
            if t[3] == n:
                o['lasts'] += 1
            o['best'] = min(o['best'], t[3])
            o['finish_sum'] += t[3]
        o['moves'] += t[10]
        o['trades'] += t[11]
for g in games:
    for ow, tm, pts, oo, ot, op, res in sides(g):
        o = own[ow]
        k = 'reg' if g['tier'] == 'N' else 'po'
        o[k + '_g'] += 1
        o[k + '_' + res] += 1
        o[k + '_pf'] += pts
        o[k + '_pa'] += op
owners_out = []
for i, o in own.items():
    rg = o['reg_g']
    owners_out.append({
        'oi': i, 'name': OWN[i], 'seasons': int(o['seasons']), 'done': int(o['done']),
        'w': int(o['reg_W']), 'l': int(o['reg_L']), 't': int(o['reg_T']),
        'pct': round((o['reg_W'] + 0.5 * o['reg_T']) / rg, 3) if rg else 0,
        'ppg': r1(o['reg_pf'] / rg) if rg else 0,
        'po_apps': int(o['po_apps']), 'po_w': int(o['po_W']), 'po_l': int(o['po_L']),
        'titles': int(o['titles']), 'finals': int(o['finals']), 'lasts': int(o['lasts']),
        'best': int(o['best']) if o['best'] < 99 else None,
        'avg_finish': r1(o['finish_sum'] / o['done']) if o['done'] else None,
        'moves': int(o['moves']), 'trades': int(o['trades']),
    })
owners_out.sort(key=lambda r: (-r['titles'], -r['finals'], -r['pct']))

hist = defaultdict(list)
for y in YEARS:
    S = SEAS[y]
    for t in S['t']:
        hist[t[2]].append({'y': y, 'team': t[1], 'rank': t[3] if y in DONE_YEARS else None, 'seed': t[4],
                           'rec': rec_str(t), 'pf': r1(t[8]), 'po': t[4] <= S['po']})

# ---------- record book ----------
team_games = []
for g in games:
    for ow, tm, pts, oo, ot, op, res in sides(g):
        team_games.append(dict(y=g['y'], wk=g['wk'], tier=g['tier'], o=ow, tm=tm, pts=pts, oo=oo, ot=ot, op=op, res=res))


def tg(r, extra=None):
    d = {'y': r['y'], 'wk': r['wk'], 'po': r['tier'] == 'W', 'team': team_name[(r['y'], r['tm'])], 'owner': OWN[r['o']],
         'pts': r2(r['pts']), 'oppOwner': OWN[r['oo']], 'oppPts': r2(r['op'])}
    if extra:
        d.update(extra)
    return d


rec = {}
wins = [r for r in team_games if r['res'] == 'W']
losses = [r for r in team_games if r['res'] == 'L']
rec['high'] = [tg(r) for r in sorted(team_games, key=lambda r: -r['pts'])[:5]]
rec['low'] = [tg(r) for r in sorted(team_games, key=lambda r: r['pts'])[:5]]
rec['blowout'] = [tg(r, {'margin': r2(r['pts'] - r['op'])}) for r in sorted(wins, key=lambda r: -(r['pts'] - r['op']))[:5]]
rec['close'] = [tg(r, {'margin': r2(r['pts'] - r['op'])}) for r in sorted(wins, key=lambda r: r['pts'] - r['op'])[:5]]
rec['highLoss'] = [tg(r) for r in sorted(losses, key=lambda r: -r['pts'])[:3]]
rec['lowWin'] = [tg(r) for r in sorted(wins, key=lambda r: r['pts'])[:3]]

season_rows = []
for y in DONE_YEARS:
    for t in SEAS[y]['t']:
        gp = t[5] + t[6] + t[7]
        season_rows.append({'y': y, 'team': t[1], 'owner': OWN[t[2]], 'w': t[5], 'l': t[6], 'ppg': r1(t[8] / gp),
                            'papg': r1(t[9] / gp), 'pct': (t[5] + 0.5 * t[7]) / gp, 'rank': t[3],
                            'moves': t[10], 'trades': t[11]})
rec['bestSeason'] = sorted(season_rows, key=lambda r: (-r['pct'], -r['ppg']))[:3]
rec['worstSeason'] = sorted(season_rows, key=lambda r: (r['pct'], r['ppg']))[:3]
rec['mostPF'] = sorted(season_rows, key=lambda r: -r['ppg'])[:3]
rec['fewestPF'] = sorted(season_rows, key=lambda r: r['ppg'])[:3]
rec['mostPA'] = sorted(season_rows, key=lambda r: -r['papg'])[:3]
rec['mostMoves'] = sorted(season_rows, key=lambda r: -r['moves'])[:3]
rec['mostTrades'] = sorted(season_rows, key=lambda r: -r['trades'])[:3]

by_owner = defaultdict(list)
for r in sorted(team_games, key=lambda r: (r['y'], r['wk'])):
    if r['tier'] == 'N':
        by_owner[r['o']].append(r)


def streaks(kind):
    out = []
    for o, rows in by_owner.items():
        best = cur = 0
        start = bs = be = None
        for r in rows:
            if r['res'] == kind:
                if cur == 0:
                    start = r
                cur += 1
                if cur > best:
                    best, bs, be = cur, start, r
            else:
                cur = 0
        if best:
            live = rows[-1]['res'] == kind and be is rows[-1]
            out.append({'owner': OWN[o], 'len': best, 'from': f"{bs['y']} Wk {bs['wk']}", 'to': f"{be['y']} Wk {be['wk']}", 'live': live})
    return sorted(out, key=lambda r: -r['len'])[:3]


rec['winStreak'] = streaks('W')
rec['loseStreak'] = streaks('L')

# all-play luck
weekly = defaultdict(dict)
for r in team_games:
    if r['tier'] == 'N':
        weekly[(r['y'], r['wk'])][r['tm']] = (r['pts'], r['res'])
allplay = defaultdict(lambda: [0.0, 0, 0.0, 0])
for (y, wk), tms in weekly.items():
    for tm, (p, res) in tms.items():
        others = [q for t2, (q, _) in tms.items() if t2 != tm]
        a = allplay[(y, tm)]
        a[0] += sum(1 for q in others if p > q) + 0.5 * sum(1 for q in others if p == q)
        a[1] += len(others)
        a[2] += 1 if res == 'W' else (0.5 if res == 'T' else 0)
        a[3] += 1
luck_rows = []
for (y, tm), (apw, apg, w, gp) in allplay.items():
    exp = apw / apg * gp
    luck_rows.append({'y': y, 'team': team_name[(y, tm)], 'owner': OWN[team_owner[(y, tm)]],
                      'ap': round(apw / apg, 3), 'w': w, 'exp': r1(exp), 'luck': r1(w - exp)})
done_luck = [r for r in luck_rows if r['y'] in DONE_YEARS]
rec['lucky'] = sorted(done_luck, key=lambda r: -r['luck'])[:3]
rec['unlucky'] = sorted(done_luck, key=lambda r: r['luck'])[:3]

# ---------- head to head ----------
N = len(OWN)
h2h = defaultdict(lambda: [0, 0, 0])
h2h_games = defaultdict(list)
for g in games:
    a, b = g['ho'], g['ao']
    if g['win'] == 'H':
        h2h[(a, b)][0] += 1; h2h[(b, a)][1] += 1
    elif g['win'] == 'A':
        h2h[(a, b)][1] += 1; h2h[(b, a)][0] += 1
    else:
        h2h[(a, b)][2] += 1; h2h[(b, a)][2] += 1
    h2h_games[(min(a, b), max(a, b))].append(g)
matrix = [[(h2h[(i, j)] if i != j else None) for j in range(N)] for i in range(N)]
riv = []
for i in range(N):
    for j in range(i + 1, N):
        w, l, t = h2h[(i, j)]
        if w + l + t == 0:
            continue
        riv.append({'a': OWN[i], 'b': OWN[j], 'w': w, 'l': l, 't': t, 'g': w + l + t,
                    'po': sum(1 for g in h2h_games[(i, j)] if g['tier'] == 'W')})
for r in riv:  # put the leader first
    if r['l'] > r['w']:
        r['a'], r['b'], r['w'], r['l'] = r['b'], r['a'], r['l'], r['w']
lopsided = sorted([r for r in riv if r['g'] >= 6], key=lambda r: (-(r['w'] - r['l']) / r['g'], -r['g']))
most_played = sorted(riv, key=lambda r: (-r['g'], -r['po']))
po_meet = sorted([r for r in riv if r['po'] > 0], key=lambda r: (-r['po'], -r['g']))
pairs = {f"{i}-{j}": [[g['y'], g['wk'], 1 if g['tier'] == 'W' else 0,
                       r2(g['hp'] if g['ho'] == i else g['ap']), r2(g['ap'] if g['ho'] == i else g['hp'])]
                      for g in sorted(gl, key=lambda g: (g['y'], g['wk']))]
         for (i, j), gl in h2h_games.items()}

# ---------- current season ----------
S = SEAS[CUR]
T = {t[0]: t for t in S['t']}
WK = D['wk']
cur_games = [g for g in games if g['y'] == CUR and g['tier'] == 'N']
team_week = defaultdict(dict)
for g in cur_games:
    for ow, tm, pts, oo, ot, op, res in sides(g):
        team_week[tm][g['wk']] = {'pts': pts, 'res': res}
teams_cur = {tm: {'team': t[1], 'owner': OWN[t[2]], 'seed': t[4], 'w': t[5], 'l': t[6]} for tm, t in T.items()}
cur_out = {'teams': teams_cur, 'standings': [], 'recap': [], 'awards': None, 'preview': [], 'weekMvps': []}

if DONE_WEEKS >= 1:
    def metrics(upto):
        out = {}
        for tm in T:
            pts = [team_week[tm][w]['pts'] for w in range(1, upto + 1)]
            apw = apg = 0
            for w in range(1, upto + 1):
                p = team_week[tm][w]['pts']
                others = [team_week[t2][w]['pts'] for t2 in T if t2 != tm]
                apw += sum(1 for q in others if p > q) + 0.5 * sum(1 for q in others if p == q)
                apg += len(others)
            wins = sum(1 for w in range(1, upto + 1) if team_week[tm][w]['res'] == 'W')
            ppg = sum(pts) / upto
            l3 = sum(pts[-3:]) / min(3, upto)
            appct = apw / apg
            out[tm] = dict(ppg=ppg, l3=l3, appct=appct, apw=apw, apl=apg - apw, wins=wins,
                           power=0.6 * ppg + 0.25 * l3 + 0.15 * appct * 100)
        return out

    now = metrics(DONE_WEEKS)
    prev = metrics(DONE_WEEKS - 1) if DONE_WEEKS >= 2 else now
    pr_now = sorted(T, key=lambda t: -now[t]['power'])
    pr_prev = sorted(T, key=lambda t: -prev[t]['power'])

    remaining = defaultdict(list)
    for wkk, h, hp, a, ap, win, tier in S['s']:
        if wkk > DONE_WEEKS and tier == 'N' and a is not None:
            remaining[h].append(a)
            remaining[a].append(h)

    def streak(tm):
        res = [team_week[tm][w]['res'] for w in range(1, DONE_WEEKS + 1)]
        n = 0
        for r in reversed(res):
            if r == res[-1]:
                n += 1
            else:
                break
        return f"{res[-1]}{n}"

    week_rank = {}
    for w in range(1, DONE_WEEKS + 1):
        for i, t in enumerate(sorted(T, key=lambda t: -team_week[t][w]['pts'])):
            week_rank[(t, w)] = i + 1

    standings = []
    for tm, t in T.items():
        wkd = [WK[str(w)][str(tm)] for w in range(1, DONE_WEEKS + 1)]
        actual, optimal = sum(x['a'] for x in wkd), sum(x['o'] for x in wkd)
        m = now[tm]
        rem = remaining[tm]
        standings.append({
            'tm': tm, 'team': t[1], 'owner': OWN[t[2]], 'seed': t[4], 'w': t[5], 'l': t[6], 'tie': t[7],
            'pf': r1(t[8]), 'pa': r1(t[9]), 'ppg': r1(m['ppg']), 'l3': r1(m['l3']),
            'apw': m['apw'], 'apl': m['apl'], 'luck': r1(m['wins'] - m['appct'] * DONE_WEEKS), 'streak': streak(tm),
            'bench': r1(optimal - actual), 'eff': round(actual / optimal * 100, 1) if optimal else 100.0,
            'power': r1(m['power']), 'pr': pr_now.index(tm) + 1, 'prPrev': pr_prev.index(tm) + 1,
            'sos': r1(sum(now[o]['ppg'] for o in rem) / len(rem)) if rem else None,
            'scores': [r1(team_week[tm][w]['pts']) for w in range(1, DONE_WEEKS + 1)],
            'res': [team_week[tm][w]['res'] for w in range(1, DONE_WEEKS + 1)],
            'wkRank': [week_rank[(tm, w)] for w in range(1, DONE_WEEKS + 1)],
        })
    standings.sort(key=lambda r: r['seed'])
    with_sos = [r for r in standings if r['sos'] is not None]
    for i, r in enumerate(sorted(with_sos, key=lambda r: -r['sos'])):
        r['sosRank'] = i + 1

    LW = DONE_WEEKS
    lw = {int(k): v for k, v in WK[str(LW)].items()}
    recap = []
    for g in [g for g in cur_games if g['wk'] == LW]:
        hw, aw = lw[g['h']], lw[g['a']]
        recap.append({'h': g['h'], 'a': g['a'], 'hp': r2(g['hp']), 'ap': r2(g['ap']), 'win': g['win'],
                      'hTop': hw['top'], 'aTop': aw['top'],
                      'hBench': r1(hw['o'] - hw['a']), 'aBench': r1(aw['o'] - aw['a'])})
    recap.sort(key=lambda m: -abs(m['hp'] - m['ap']))

    def mwin(m):
        return (m['h'], m['a'], m['hp'], m['ap']) if m['win'] == 'H' else (m['a'], m['h'], m['ap'], m['hp'])

    bl = max(recap, key=lambda m: abs(m['hp'] - m['ap']))
    cl = min(recap, key=lambda m: abs(m['hp'] - m['ap']))
    hi = max(lw, key=lambda t: lw[t]['a'])
    lo = min(lw, key=lambda t: lw[t]['a'])
    mvp = max(lw, key=lambda t: lw[t]['top'][1])
    bw = max(lw, key=lambda t: lw[t]['o'] - lw[t]['a'])
    pm = max(lw, key=lambda t: (lw[t]['a'] / lw[t]['o'] if lw[t]['o'] else 1, lw[t]['a']))
    over = max(lw, key=lambda t: lw[t]['a'] - lw[t]['p'])
    under = min(lw, key=lambda t: lw[t]['a'] - lw[t]['p'])
    result = {}
    for m in recap:
        result[m['h']] = 'W' if m['win'] == 'H' else 'L'
        result[m['a']] = 'W' if m['win'] == 'A' else 'L'
    awards = {
        'high': {'tm': hi, 'v': lw[hi]['a']}, 'low': {'tm': lo, 'v': lw[lo]['a']},
        'blowout': dict(zip(['w', 'l', 'wp', 'lp'], mwin(bl))), 'close': dict(zip(['w', 'l', 'wp', 'lp'], mwin(cl))),
        'mvp': {'tm': mvp, 'player': lw[mvp]['top'][0], 'v': lw[mvp]['top'][1]},
        'bench': {'tm': bw, 'v': r1(lw[bw]['o'] - lw[bw]['a']), 'player': lw[bw]['bench'][0], 'pv': lw[bw]['bench'][1]},
        'manager': {'tm': pm, 'eff': round(lw[pm]['a'] / lw[pm]['o'] * 100, 1) if lw[pm]['o'] else 100.0,
                    'perfect': abs(lw[pm]['o'] - lw[pm]['a']) < 0.05, 'res': result.get(pm)},
        'beatProj': {'tm': over, 'v': r1(lw[over]['a'] - lw[over]['p']), 'a': lw[over]['a'], 'p': lw[over]['p']},
        'missProj': {'tm': under, 'v': r1(lw[under]['a'] - lw[under]['p']), 'a': lw[under]['a'], 'p': lw[under]['p']},
    }

    preview = []
    if PREVIEW and str(PREVIEW) in WK:
        nw = WK[str(PREVIEW)]
        for wkk, h, hp, a, ap, win, tier in S['s']:
            if wkk != PREVIEW or a is None:
                continue
            hn, an = nw.get(str(h)), nw.get(str(a))
            if not hn or not an:
                continue
            preview.append({'h': h, 'a': a, 'hProj': hn['p'], 'aProj': an['p'], 'hTop': hn['topP'], 'aTop': an['topP'],
                            'h2h': h2h[(T[h][2], T[a][2])], 'hPpg': r1(now[h]['ppg']), 'aPpg': r1(now[a]['ppg'])})
        preview.sort(key=lambda m: abs(m['hProj'] - m['aProj']))

    week_mvps = []
    for w in range(1, DONE_WEEKS + 1):
        ww = {int(k): v for k, v in WK[str(w)].items()}
        t = max(ww, key=lambda t: ww[t]['top'][1])
        hiT = max(ww, key=lambda t: ww[t]['a'])
        week_mvps.append({'wk': w, 'tm': t, 'player': ww[t]['top'][0], 'v': ww[t]['top'][1], 'hiTm': hiT, 'hi': ww[hiT]['a']})

    cur_out.update(standings=standings, recap=recap, awards=awards, preview=preview, weekMvps=week_mvps)

# current-season playoff bracket (appears once ESPN schedules it)
cur_out['bracket'] = [[wk, h, (r2(hp) if win != 'U' else None), a, (r2(ap) if (a is not None and win != 'U') else None), win]
                      for wk, h, hp, a, ap, win, tier in S['s'] if tier == 'W']
cur_out['seasonDone'] = CUR in DONE_YEARS

# ---------- weekly bet (from the league's Google Doc) ----------
import os
from collections import Counter
bets_out = None
BETS = os.path.join(os.path.dirname(src) or '.', 'bets.json')
if os.path.exists(BETS):
    B = json.load(open(BETS))
    by_first = {n.split()[0].lower(): n for n in OWN}
    b_seasons = {}
    for y, weeks in B['seasons'].items():
        wl = []
        for w in sorted(weeks, key=int):
            picks = []
            for p in weeks[w]:
                who = by_first.get(p['who'].split()[0].lower(), p['who'])
                picks.append({'o': who, 'pick': p['pick'], 't': p.get('type'), 's': p.get('subject'), 'r': p.get('res')})
            made = [p for p in picks if p['pick']]
            hits = sum(1 for p in made if p['r'] == 'hit')
            misses = sum(1 for p in made if p['r'] == 'miss')
            status = 'bust' if misses else ('hit' if made and hits == len(made) else 'open')
            wl.append({'wk': int(w), 'picks': picks, 'made': len(made), 'hits': hits, 'misses': misses, 'status': status,
                       'missedBy': [p['o'] for p in made if p['r'] == 'miss']})
        b_seasons[y] = wl

    def owner_stats(lists):
        per = {}
        for wl in lists:
            for wk in wl:
                for p in wk['picks']:
                    d = per.setdefault(p['o'], {'weeks': 0, 'made': 0, 'hits': 0, 'misses': 0, 'types': Counter(), 'subj': Counter()})
                    d['weeks'] += 1
                    if not p['pick']:
                        continue
                    d['made'] += 1
                    d['types'][p['t']] += 1
                    if p['s']:
                        d['subj'][p['s']] += 1
                    if p['r'] == 'hit':
                        d['hits'] += 1
                    elif p['r'] == 'miss':
                        d['misses'] += 1
        rows = []
        for o, d in per.items():
            ft = d['types'].most_common(1)
            sg = d['subj'].most_common(1)
            g = d['hits'] + d['misses']
            rows.append({'o': o, 'weeks': d['weeks'], 'made': d['made'], 'hits': d['hits'], 'misses': d['misses'],
                         'rate': round(d['hits'] / g, 3) if g else None,
                         'fav': [ft[0][0], ft[0][1]] if ft else None,
                         'sig': [sg[0][0], sg[0][1]] if sg and sg[0][1] >= 3 else None})
        rows.sort(key=lambda r: (-(r['rate'] if r['rate'] is not None else -1), -r['made']))
        return rows

    all_lists = list(b_seasons.values())
    subj = Counter(); subj_by = {}
    types = Counter()
    for wl in all_lists:
        for wk in wl:
            for p in wk['picks']:
                if p['pick']:
                    types[p['t']] += 1
                    if p['s']:
                        subj[p['s']] += 1
                        subj_by.setdefault(p['s'], Counter())[p['o']] += 1
    total = sum(types.values())
    graded = sum(wk['hits'] + wk['misses'] for wl in all_lists for wk in wl)
    years = sorted(b_seasons, key=int, reverse=True)
    latest_y = years[0]
    bets_out = {
        'docUrl': f"https://docs.google.com/document/d/{B['docId']}/edit",
        'years': years, 'seasons': b_seasons,
        'stats': {**{y: owner_stats([b_seasons[y]]) for y in years}, 'all': owner_stats(all_lists)},
        'top': [{'s': s_, 'n': n, 'by': subj_by[s_].most_common(1)[0], 'people': len(subj_by[s_])} for s_, n in subj.most_common(8)],
        'types': types.most_common(), 'total': total, 'graded': graded,
        'latest': {'y': latest_y, 'wk': b_seasons[latest_y][-1]['wk'] if b_seasons[latest_y] else None},
    }

out = {
    'league': D['league'], 'asOf': D['asOf'], 'current': CUR, 'doneWeeks': DONE_WEEKS, 'previewWeek': PREVIEW,
    'regWeeks': S['reg'], 'poTeams': S['po'],
    'owners': OWN, 'seasons': seasons_out, 'ownerTable': owners_out, 'hist': {str(k): v for k, v in hist.items()},
    'records': rec, 'h2h': matrix, 'pairs': pairs,
    'rivals': {'lopsided': lopsided[:5], 'mostPlayed': most_played[:5], 'playoff': po_meet[:5]},
    'draft': D['draft'],
    'draftTeams': {str(y): {str(t[0]): {'team': t[1], 'owner': OWN[t[2]]} for t in SEAS[y]['t']} for y in YEARS},
    'cur': cur_out,
    'bets': bets_out,
}
import os
os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
json.dump(out, open(dst, 'w'), separators=(',', ':'), ensure_ascii=False)
print(f"Computed {dst}: {len(games)} games, season {CUR} through week {DONE_WEEKS}")
