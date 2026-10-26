"""Read the league's weekly-bet Google Doc and turn it into data/bets.json.

Usage:
  python3 scripts/bets.py            # download the doc (link-shared) and parse it
  python3 scripts/bets.py --offline  # parse the last saved copy in data/bets.md

The doc is a list of weeks, newest first. Each week is a two-column table of
name | pick. A line that is just a year (e.g. **2025**) starts an older season;
anything above the first year line belongs to the current season. A ✅ or ❌
anywhere in a pick grades it; ➖ marks a push.
"""
import json
import os
import re
import sys
import urllib.request

DOC_ID = '1hUcsOsBu0c2bVQbRWks86fwvyRXQGt_Ke1bnH_CHk0w'
MD_PATH = 'data/bets.md'
OUT_PATH = 'data/bets.json'
LEAGUE_PATH = 'data/league.json'
GRADES_PATH = 'data/bet-grades.json'  # written by scripts/grade.js; fills in picks the doc hasn't marked yet

TEAMS = {
    'Cardinals': ['cardinals', 'cards', 'arizona', 'ari'], 'Falcons': ['falcons', 'atlanta', 'atl'],
    'Ravens': ['ravens', 'baltimore'], 'Bills': ['bills', 'buffalo'], 'Panthers': ['panthers', 'carolina'],
    'Bears': ['bears', 'chicago'], 'Bengals': ['bengals', 'cincinnati', 'cincy'], 'Browns': ['browns', 'cleveland'],
    'Cowboys': ['cowboys', 'cowboy', 'dallas'], 'Broncos': ['broncos', 'denver'], 'Lions': ['lions', 'detroit', 'detorit'],
    'Packers': ['packers', 'green bay', 'gb'], 'Texans': ['texans', 'houston'], 'Colts': ['colts', 'indy', 'indianapolis'],
    'Jaguars': ['jaguars', 'jags', 'jacksonville'], 'Chiefs': ['chiefs', 'kc', 'kansas city'],
    'Raiders': ['raiders', 'raidas', 'vegas'], 'Chargers': ['chargers', 'bolts'], 'Rams': ['rams'],
    'Dolphins': ['dolphins', 'miami', 'fins'], 'Vikings': ['vikings', 'minnesota', 'vikes'],
    'Patriots': ['patriots', 'pats', 'ne', 'new england'], 'Saints': ['saints', 'new orleans'],
    'Giants': ['giants', 'gmen', 'nyg'], 'Jets': ['jets', 'nyj'], 'Eagles': ['eagles', 'eggles', 'philly', 'philadelphia'],
    'Steelers': ['steelers', 'pittsburgh'], '49ers': ['49ers', 'niners', 'san francisco'],
    'Seahawks': ['seahawks', 'seacocks', 'seattle'], 'Buccaneers': ['buccaneers', 'bucs', 'tb', 'tampa'],
    'Titans': ['titans', 'tennessee'], 'Commanders': ['commanders', 'commies'],
}
PLAYERS = [  # (pattern, name); checked in order, first match wins
    (r"chase brown", 'Chase Brown'), (r"ja.?marr chase", "Ja'Marr Chase"),
    (r"\bd(errick)?\.? ?henry\b|king henry|\bhenry\b", 'Derrick Henry'),
    (r"\bjsn\b|smith.?njigba", 'Jaxon Smith-Njigba'), (r"achane", "De'Von Achane"), (r"gibbs", 'Jahmyr Gibbs'),
    (r"bijan", 'Bijan Robinson'), (r"barkley|saquon", 'Saquon Barkley'), (r"\bcmc\b|mccaffrey", 'Christian McCaffrey'),
    (r"warren", 'Tyler Warren'), (r"hurts", 'Jalen Hurts'), (r"drake maye", 'Drake Maye'),
    (r"winston|jamies", 'Jameis Winston'), (r"mcconkey", 'Ladd McConkey'), (r"ceedee|\blamb\b", 'CeeDee Lamb'),
    (r"kelce", 'Travis Kelce'), (r"flacco", 'Joe Flacco'), (r"darnold", 'Sam Darnold'), (r"goff", 'Jared Goff'),
]


def strip_md(s):
    return re.sub(r'\\(.)', r'\1', s).strip()


def team_in(p, aliases):
    return any(re.search(r'(?<![a-z])' + re.escape(a) + r'(?![a-z])', p) for a in aliases)


def classify(pick):
    p = pick.lower()
    prop_words = r"yards|\byd\b|yds|receptions|\brec\b|receiving|passing|rush|interceptions|\d\s*\+\s*(passing )?(td|touchdowns)"
    if re.search(prop_words, p):
        kind = 'Player prop'
    elif re.search(r"\b(td|tds|touchdown|tuddy|attd)\b|anytime|1st td", p):
        kind = 'Anytime TD'
    elif re.search(r"\bml+\b|moneyline", p):
        kind = 'Moneyline'
    elif re.search(r"\b(over|under|ova|unda)\b|\b[ou]\s?\d", p):
        # an over/under that names a team is a game total; one that names no team is a player line
        kind = 'Game total' if any(team_in(p, a) for a in TEAMS.values()) else 'Player prop'
    elif re.search(r"[+-]\s?\d", p):
        kind = 'Spread'
    else:
        kind = 'Other'
    subject = None
    for pat, name in PLAYERS:
        if re.search(pat, p):
            subject = name
            break
    if not subject and kind in ('Moneyline', 'Spread'):
        for team, aliases in TEAMS.items():
            if team_in(p, aliases):
                subject = team
                break
    return kind, subject


def parse(md, current_season):
    seasons, season, week, weeks_order = {}, current_season, None, {}
    for raw in md.splitlines():
        line = raw.strip()
        if not line:
            continue
        bare = re.sub(r'[*#_:\s]', '', line)
        if re.fullmatch(r'(19|20)\d\d', bare):
            season = int(bare)
            week = None
            continue
        m = re.search(r'week\s*(\d+)', line, re.I)
        if m and not line.startswith('|'):
            week = {'n': int(m.group(1)), 'label': strip_md(re.sub(r'[*:]', '', line)), 'picks': []}
            weeks_order.setdefault(season, []).append(week)
            continue
        if line.startswith('|') and week is not None:
            cells = [strip_md(c) for c in line.strip('|').split('|')]
            if len(cells) < 2 or re.fullmatch(r':?-+:?', cells[0].replace(' ', '')):
                continue
            who = re.sub(r'\(.*?\)', '', cells[0]).strip()
            pick = cells[1].strip()
            if not who:
                continue
            res = 'hit' if '✅' in pick else ('miss' if '❌' in pick else ('push' if '➖' in pick else None))
            text = re.sub(r'\s+', ' ', re.sub(r'[✅❌➖]', '', pick)).strip()
            item = {'who': who, 'pick': text}
            if text:
                kind, subj = classify(text)
                item.update(type=kind, subject=subj, res=res)
            week['picks'].append(item)
            continue
        if not line.startswith('|'):
            week = None  # any other text ends the current table
    for s, ws in weeks_order.items():
        # weeks are listed newest first; repair a mislabeled duplicate (e.g. a second "Week 9" that sits under Week 11)
        seen = [w['n'] for w in ws]
        for i, w in enumerate(ws):
            if seen.count(w['n']) > 1 and i > 0 and ws[i - 1]['n'] - w['n'] > 1 and (ws[i - 1]['n'] - 1) not in seen:
                w['n'] = ws[i - 1]['n'] - 1
                seen = [x['n'] for x in ws]
        seasons[str(s)] = {str(w['n']): w['picks'] for w in sorted(ws, key=lambda w: w['n']) if w['picks']}
    return seasons


def main():
    offline = '--offline' in sys.argv
    if not offline:
        url = f'https://docs.google.com/document/d/{DOC_ID}/export?format=md'
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'corknpork.net'}), timeout=30) as r:
                md = r.read().decode('utf-8')
            if '|' not in md:
                raise ValueError('the doc came back without any pick tables')
            open(MD_PATH, 'w').write(md)
        except Exception as e:  # keep the last good copy rather than breaking the site
            msg = f"Couldn't download the bet doc ({e}), so the Weekly Bet tab is showing the last saved copy. Check the doc is still shared by link."
            print(msg)
            os.makedirs('build', exist_ok=True)
            open('build/alerts.txt', 'a').write(msg + '\n')
    md = open(MD_PATH).read()
    current = json.load(open(LEAGUE_PATH))['current']
    seasons = parse(md, current)
    # A ✅/❌ in the doc always wins; otherwise use the grader's call so results show up the night the games end.
    filled = 0
    if os.path.exists(GRADES_PATH):
        graded = {(str(g['y']), str(g['wk']), g['who'].lower()): g['res'] for g in json.load(open(GRADES_PATH))
                  if g.get('res') in ('hit', 'miss', 'push')}
        for y, weeks in seasons.items():
            for w, picks in weeks.items():
                for p in picks:
                    if p.get('pick') and p.get('res') is None and (y, w, p['who'].lower()) in graded:
                        p['res'] = graded[(y, w, p['who'].lower())]
                        filled += 1
    if filled:
        print(f'{filled} pick(s) graded from {GRADES_PATH} (not yet marked in the doc)')
    json.dump({'docId': DOC_ID, 'seasons': seasons}, open(OUT_PATH, 'w'), ensure_ascii=False, separators=(',', ':'))
    total = sum(len([p for p in ps if p['pick']]) for s in seasons.values() for ps in s.values())
    print(f'Saved {OUT_PATH}: {total} picks across ' + ', '.join(f'{y} ({len(w)} weeks)' for y, w in sorted(seasons.items())))


if __name__ == '__main__':
    main()
