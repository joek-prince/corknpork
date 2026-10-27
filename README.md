# corknpork.net

The Cork n' Pork fantasy football Hall of Fame: weekly recap and preview, the weekly bet, champions, records, rivalries, drafts and owner pages. It rebuilds itself from ESPN and the league bet doc every Tuesday morning and Thursday afternoon.

## How it updates

`.github/workflows/weekly.yml` runs on a schedule (and on every push, or from **Actions → Update corknpork.net → Run workflow**):

1. `scripts/fetch.js` pulls the private ESPN league (ID 91427782) using the `ESPN_S2` and `SWID` cookies stored as repository secrets, and writes `data/league.json`.
2. `scripts/bets.py` downloads the link-shared bet Google Doc as Markdown and writes `data/bets.json`.
3. `scripts/compute.py` turns both into `build/results.json` (records, rivalries, power rankings, bet stats).
4. `scripts/og.py` draws the link-preview card (`og.png`) and icons.
5. `scripts/build.py` renders `site/template.html` into `_site/index.html`, which is published to GitHub Pages.

Scheduled runs commit the refreshed `data/` files, so the repo keeps a week-by-week history.

## Setup checklist

- **Secrets** (Settings → Secrets and variables → Actions): `ESPN_S2` and `SWID`, copied from the espn.com cookies of a browser signed in to the league. They last about a year; when they expire the workflow fails with a message saying so.
- **Pages** (Settings → Pages): Source = GitHub Actions, custom domain = `corknpork.net`, then Enforce HTTPS once it's offered.
- **DNS** for corknpork.net: A records for `@` → 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153, and a CNAME for `www` → `joek-prince.github.io`.

## Slack alerts

If an update fails (expired ESPN cookies, the bet doc unreachable, Pages not publishing, the preview card not drawing), the `alert` job posts to Slack through an incoming webhook. Set it up once:

1. In Slack, create an app at api.slack.com/apps (From scratch), turn on **Incoming Webhooks**, click **Add New Webhook**, pick the channel, and copy the URL.
2. Add it as the repository secret `SLACK_WEBHOOK_URL` (Settings → Secrets and variables → Actions).
3. Run **Update corknpork.net** with "Also send a test message to Slack" ticked to check it.

Without the secret the alert job just logs what it would have sent.

## The commissioner's report

Each week's write-up lives in `data/reports/`, one file per week named like `2026-wk07.md`. The first lines can be `by: John M.` and `title: ...` (end the header with a blank line); everything after is the report, with blank lines between paragraphs. Hashtags are highlighted. The site shows the newest report for the current season at the top of This Week, with earlier weeks a tap away. Commit the file (or add it through GitHub's web editor) and the push rebuilds the site.

## The bet doc

Each week is a two-column table (name | pick), newest week first. A line that is just a year (like **2025**) starts an older season. Put ✅ or ❌ after a pick to grade it; the site counts those on the next update.

## Running it locally

```
ESPN_S2=... SWID=... node scripts/fetch.js data/league.json
python3 scripts/bets.py
python3 scripts/compute.py data/league.json build/results.json
python3 scripts/build.py build/results.json _site/index.html
```
