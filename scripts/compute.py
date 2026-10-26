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
teams_cur = {tm: {'team': t[1], 'owner': OWN[t[2]], 'seed': t[4], 'w': t[5], 'l': t[6],
                  'ab': t[12] if len(t) > 12 else '', 'logo': t[13] if len(t) > 13 else ''} for tm, t in T.items()}
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

# ---------- Ass Clenchers: the close games, written up ----------
PRO = {1: 'ATL', 2: 'BUF', 3: 'CHI', 4: 'CIN', 5: 'CLE', 6: 'DAL', 7: 'DEN', 8: 'DET', 9: 'GB', 10: 'TEN', 11: 'IND', 12: 'KC',
       13: 'LV', 14: 'LAR', 15: 'MIA', 16: 'MIN', 17: 'NE', 18: 'NO', 19: 'NYG', 20: 'NYJ', 21: 'PHI', 22: 'ARI', 23: 'PIT',
       24: 'LAC', 25: 'SF', 26: 'SEA', 27: 'TB', 28: 'WSH', 29: 'CAR', 30: 'JAX', 33: 'BAL', 34: 'HOU'}
CLENCH = 10.0  # a game decided by fewer points than this is an ass-clencher
WHEN = 'the rest of the week'  # set below once the live board knows which games are left


def fn(tm):
    """owner's first name, for the write-ups"""
    return OWN[T[tm][2]].split()[0]


def tn(tm):
    return T[tm][1]


def pts(x):
    return f"{x:.1f}"


def names(players, with_proj=True):
    """'CeeDee Lamb (15.0)' / 'Saquon Barkley (13.9) and George Pickens (10.7)'"""
    parts = [f"{p['name']} ({pts(p['proj'])})" if with_proj else p['name'] for p in players]
    if len(parts) <= 1:
        return ''.join(parts)
    return ', '.join(parts[:-1]) + ' and ' + parts[-1]


def live_story(g):
    """A few sentences in the voice of a fantasy column, from the numbers only."""
    lead, trail = (g['h'], g['a']) if g['hp'] >= g['ap'] else (g['a'], g['h'])
    lp, tp = max(g['hp'], g['ap']), min(g['hp'], g['ap'])
    l_left, t_left = (g['hLeft'], g['aLeft']) if lead == g['h'] else (g['aLeft'], g['hLeft'])
    l_rem, t_rem = sum(p['proj'] for p in l_left), sum(p['proj'] for p in t_left)
    m = g['margin']
    proj_m = m + l_rem - t_rem  # projected final margin, leader's view
    L, Tt = fn(lead), fn(trail)
    LT, TT = tn(lead), tn(trail)
    if g['status'] == 'final':
        if m < 1:
            head = f"{LT} survives by {pts(m)}"
        elif m < CLENCH:
            head = f"{LT} holds off {TT} by {pts(m)}"
        else:
            head = f"{LT} over {TT}, {pts(lp)}–{pts(tp)}"
        top_l = max(g['hStarters'] if lead == g['h'] else g['aStarters'], key=lambda p: p['pts'], default=None)
        top_t = max(g['hStarters'] if trail == g['h'] else g['aStarters'], key=lambda p: p['pts'], default=None)
        s = f"Final. {L} closes it out {pts(lp)} to {pts(tp)}, and nobody on either side has a snap left to change it."
        if top_l:
            s += f" {top_l['name']} ({pts(top_l['pts'])}) did the heavy lifting for {LT}"
            s += f"; {top_t['name']} ({pts(top_t['pts'])}) was the best {Tt} had." if top_t else '.'
        if m < CLENCH:
            s += f" A {pts(m)}-point margin is the kind that lives in the group chat all week."
        return head, s
    if g['status'] == 'locked':
        head = f"{LT} up {pts(m)} — book it"
        if not t_left:
            s = f"{L} leads {pts(lp)} to {pts(tp)} and {Tt} is out of bullets. {L} still has {names(l_left)} to go, so this one only gets wider."
        else:
            s = (f"{L} leads {pts(lp)} to {pts(tp)}. {Tt} has {names(t_left)} left, but that's {pts(t_rem)} of projection against a "
                 f"{pts(m)}-point hole" + (f", and {L} still has {names(l_left)} to answer with" if l_left else '') +
                 f". It would take roughly double the projection to steal it. Barring something historic from {names(t_left, False)}, {L} moves on.")
        return head, s
    # clencher or live: both sides can still swing it
    if not l_left:
        head = f"{Tt} chasing {pts(m)} with {names(t_left, False)} left"
        s = (f"{L} is done at {pts(lp)} and can only watch. {Tt} sits at {pts(tp)} with {names(t_left)} still to play — "
             f"{pts(t_rem)} of projection against a {pts(m)}-point deficit. ")
        s += (f"On the numbers that's a {Tt} win by {pts(-proj_m)}." if proj_m < 0 else
              f"On the numbers {L} still holds by {pts(proj_m)}, so {Tt} needs {names(t_left, False)} to beat projection by {pts(proj_m)}.")
    elif not t_left:
        head = f"{LT} up {pts(m)}, {Tt} out of players"
        s = (f"{Tt} is finished at {pts(tp)}. {L} leads by {pts(m)} with {names(l_left)} still to play, so the only way this flips is "
             f"a negative night from {names(l_left, False)}. Not impossible with a D/ST in the mix, but close to it.")
    else:
        head = (f"Coin flip: {LT} {pts(lp)}, {TT} {pts(tp)}" if abs(proj_m) < 3 and m < 8 else
                f"{LT} up {pts(m)}, but it projects to a coin flip" if abs(proj_m) < 3 else
                f"{LT} up {pts(m)}, but {Tt} has the edge in what's left" if proj_m < 0 else
                f"{LT} up {pts(m)} with {WHEN} to come")
        s = (f"{L} leads {pts(lp)} to {pts(tp)}, and this is nowhere near over. {Tt} still has {names(t_left)} to play; "
             f"{L} counters with {names(l_left)}. ")
        if proj_m < 0:
            s += (f"Projection actually favors the comeback: {Tt} by {pts(-proj_m)} when the dust settles. "
                  f"{L} needs {names(l_left, False)} to beat {names(t_left, False)} by {pts(m)} to hang on — "
                  f"{pts(t_rem - l_rem - m)} better than the numbers say.")
        else:
            s += (f"On projection it ends {L} by {pts(proj_m)}. To flip it, {names(t_left, False)} {'have' if len(t_left) > 1 else 'has'} to outscore "
                  f"{names(l_left, False)} by {pts(m)} or more — {'well within range' if m < 7 else 'a real ask, but one big night does it'}.")
    return head, s


def recap_story(m, rank):
    w, l = (m['h'], m['a']) if m['win'] == 'H' else (m['a'], m['h'])
    wp, lp = (m['hp'], m['ap']) if m['win'] == 'H' else (m['ap'], m['hp'])
    wTop, lTop = (m['hTop'], m['aTop']) if m['win'] == 'H' else (m['aTop'], m['hTop'])
    wB, lB = (m['hBench'], m['aBench']) if m['win'] == 'H' else (m['aBench'], m['hBench'])
    mg = wp - lp
    W_, L_ = fn(w), fn(l)
    head = (f"Ass-clencher of the week: {tn(w)} by {pts(mg)}" if rank == 0 else
            f"{tn(w)} edges {tn(l)} by {pts(mg)}" if mg < CLENCH else f"{tn(w)} over {tn(l)} by {pts(mg)}")
    s = f"{W_} beat {L_} {pts(wp)} to {pts(lp)}. {wTop[0]} led the way with {pts(wTop[1])}; {lTop[0]} put up {pts(lTop[1])} in the loss."
    if lB > mg + 0.05:
        s += f" The part that stings: {L_} left {pts(lB)} on the bench — more than the margin. One lineup call the other way and this is a win."
    elif lB > 0.05:
        s += f" {L_} left {pts(lB)} on the bench, not quite enough to have mattered."
    else:
        s += f" {L_} started the best lineup available and still came up short — nothing to second-guess."
    if wB > mg + 0.05 and mg < CLENCH:
        s += f" {W_} wasn't exactly sharp either, with {pts(wB)} sitting on the bench, which makes the escape even luckier."
    return head, s


clench = {'live': None, 'recap': None, 'ledger': [], 'tight': 0, 'games': 0}
if DONE_WEEKS >= 1:
    # the closest game of every finished week
    for w in range(1, DONE_WEEKS + 1):
        wg = [g for g in cur_games if g['wk'] == w]
        if not wg:
            continue
        g = min(wg, key=lambda g: abs(g['hp'] - g['ap']))
        w_, l_ = (g['h'], g['a']) if g['hp'] >= g['ap'] else (g['a'], g['h'])
        clench['ledger'].append({'wk': w, 'w': w_, 'l': l_, 'wp': r2(max(g['hp'], g['ap'])), 'lp': r2(min(g['hp'], g['ap'])),
                                 'margin': r2(abs(g['hp'] - g['ap']))})
    clench['games'] = len(cur_games)
    clench['tight'] = sum(1 for g in cur_games if abs(g['hp'] - g['ap']) < CLENCH)
    # last finished week, closest three written up
    rc = sorted(cur_out['recap'], key=lambda m: abs(m['hp'] - m['ap']))
    rc = [m for m in rc[:3] if abs(m['hp'] - m['ap']) < CLENCH] or rc[:1]  # the real clenchers; always at least the closest game
    clench['recap'] = {'wk': DONE_WEEKS, 'games': []}
    for i, m in enumerate(rc):
        head, story = recap_story(m, i)
        w_, l_ = (m['h'], m['a']) if m['win'] == 'H' else (m['a'], m['h'])
        clench['recap']['games'].append({'w': w_, 'l': l_, 'wp': m['hp'] if m['win'] == 'H' else m['ap'], 'lp': m['ap'] if m['win'] == 'H' else m['hp'],
                                         'margin': r2(abs(m['hp'] - m['ap'])), 'head': head, 'story': story})

NFL = D.get('nfl')
if PREVIEW and NFL and NFL.get('wk') == PREVIEW and str(PREVIEW) in WK:
    state = {}  # proTeamId -> (state, kickoff, shortName)
    for home, away, st, date, short_name, hs, as_, detail in NFL['games']:
        state[home] = state[away] = (st, date, short_name, detail)
    started = [g for g in NFL['games'] if g[2] != 'pre']
    if started:  # the week is under way: build the live board
        # what to call the games still to come: "Monday night", "Sunday night", "the late games"...
        WHEN = 'the rest of the week'
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            kicks = [datetime.fromisoformat(d.replace('Z', '+00:00')).astimezone(ZoneInfo('America/New_York'))
                     for home, away, st, d, *_ in NFL['games'] if st == 'pre']
            days = {k.strftime('%A') for k in kicks}
            if len(days) == 1:
                day = days.pop()
                night = all(k.hour >= 19 for k in kicks)
                WHEN = f"{day} night" if night else (f"{day}'s games" if len(kicks) > 1 else f"{day}'s game")
            elif kicks:
                WHEN = 'the late games'
        except Exception:
            pass
        nw = {int(k): v for k, v in WK[str(PREVIEW)].items()}
        lgames = []
        for wkk, h, hp_, a, ap_, win, tier in S['s']:
            if wkk != PREVIEW or a is None or h not in nw or a not in nw or 'live' not in nw[h]:
                continue
            def side(tm):
                starters = [{'name': p[0], 'team': PRO.get(p[1], '?'), 'pts': p[2] or 0, 'proj': p[3] or 0} for p in nw[tm]['live']]
                left = []
                for p, raw in zip(starters, nw[tm]['live']):
                    st = state.get(raw[1], ('post',))[0]
                    if st == 'pre':
                        left.append({**p, 'state': 'pre'})
                    elif st == 'in':
                        left.append({**p, 'proj': max(p['proj'] - p['pts'], 0), 'state': 'in'})
                return starters, left
            hS, hL = side(h)
            aS, aL = side(a)
            hp_live, ap_live = nw[h]['a'], nw[a]['a']
            m = abs(hp_live - ap_live)
            lead_left, trail_left = (hL, aL) if hp_live >= ap_live else (aL, hL)
            l_rem, t_rem = sum(p['proj'] for p in lead_left), sum(p['proj'] for p in trail_left)
            if not hL and not aL:
                status = 'final'
            elif m > 1.6 * t_rem + 0.5 * l_rem:
                status = 'locked'
            elif m < t_rem or abs(m + l_rem - t_rem) < CLENCH:
                status = 'clencher'
            else:
                status = 'live'
            g = {'h': h, 'a': a, 'hp': r2(hp_live), 'ap': r2(ap_live), 'margin': r2(m), 'status': status,
                 'hLeft': hL, 'aLeft': aL, 'hStarters': hS, 'aStarters': aS,
                 'hFinal': r1(hp_live + sum(p['proj'] for p in hL)), 'aFinal': r1(ap_live + sum(p['proj'] for p in aL))}
            g['head'], g['story'] = live_story(g)
            for k in ('hStarters', 'aStarters'):
                del g[k]
            lgames.append(g)
        order = {'clencher': 0, 'live': 1, 'locked': 2, 'final': 3}
        lgames.sort(key=lambda g: (order[g['status']], g['margin']))
        todo = sorted({(d, s, det) for st, d, s, det in state.values() if st != 'post'})
        clench['live'] = {'wk': PREVIEW, 'asOf': NFL['asOf'], 'games': lgames,
                          'allDone': all(st == 'post' for st, *_ in state.values()),
                          'next': [{'game': s, 'when': det, 'state': 'in' if any(v[2] == s and v[0] == 'in' for v in state.values()) else 'pre'} for d, s, det in todo]}
cur_out['clench'] = clench

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
            pushes = sum(1 for p in made if p['r'] == 'push')
            status = 'bust' if misses else ('hit' if made and hits and hits + pushes == len(made) else 'open')
            wl.append({'wk': int(w), 'picks': picks, 'made': len(made), 'hits': hits, 'misses': misses, 'pushes': pushes, 'status': status,
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
    graded = sum(wk['hits'] + wk['misses'] + wk['pushes'] for wl in all_lists for wk in wl)
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
