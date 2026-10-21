# corknpork.net

The Cork n' Pork fantasy football Hall of Fame: weekly recap and preview, the weekly bet, champions, records, rivalries, drafts and owner pages. It rebuilds itself from ESPN and the league bet doc every Tuesday morning and Thursday afternoon.

## How it updates

`.github/workflows/weekly.yml` runs on a schedule (and on every push, or from **Actions → Update corknpork.net → Run workflow**):

1. `scripts/fetch.js` pulls the private ESPN league (ID 91427782) using the `ESPN_S2` and `SWID` cookies stored as repository secrets, and writes `data/league.json`.
2. `scripts/bets.py` downloads the link-shared bet Google Doc as Markdown and writes `data/bets.json`.
3. `scripts/compute.py` turns both into `build/results.json` (records, rivalries, power rankings, bet stats).
4. `scripts/build.py` renders `site/template.html` into `_site/index.html`, which is published to GitHub Pages.

Scheduled runs commit the refreshed `data/` files, so the repo keeps a week-by-week history.

## Setup checklist

- **Secrets** (Settings → Secrets and variables → Actions): `ESPN_S2` and `SWID`, copied from the espn.com cookies of a browser signed in to the league. They last about a year; when they expire the workflow fails with a message saying so.
- **Pages** (Settings → Pages): Source = GitHub Actions, custom domain = `corknpork.net`, then Enforce HTTPS once it's offered.
- **DNS** for corknpork.net: A records for `@` → 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153, and a CNAME for `www` → `joek-prince.github.io`.

## The bet doc

Each week is a two-column table (name | pick), newest week first. A line that is just a year (like **2025**) starts an older season. Put ✅ or ❌ after a pick to grade it; the site counts those on the next update.

## Running it locally

```
ESPN_S2=... SWID=... node scripts/fetch.js data/league.json
python3 scripts/bets.py
python3 scripts/compute.py data/league.json build/results.json
python3 scripts/build.py build/results.json _site/index.html
```
