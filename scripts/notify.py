"""Post a Slack message when a site update fails or needs attention.

Run by the `alert` job in .github/workflows/weekly.yml. Reads everything from the
environment and does nothing if the SLACK_WEBHOOK_URL secret isn't set.
"""
import json
import os
import urllib.request

E = os.environ.get
url = E('SLACK_WEBHOOK_URL', '').strip()
run = f"<{E('RUN_URL', '')}|See the run on GitHub>"
alerts = [a.strip() for a in E('ALERTS', '').splitlines() if a.strip()]

STEPS = [  # (env var, what it means when it breaks)
    ('STEP_ESPN', "Couldn't pull the league from ESPN."),
    ('STEP_BETS', "Couldn't read the weekly bet doc."),
    ('STEP_COMPUTE', 'The stats step broke.'),
    ('STEP_PAGE', "Couldn't build the page."),
    ('STEP_SAVE', "Couldn't save this week's data snapshot to GitHub."),
]

if E('TEST_ALERT') == 'true':
    text = f":white_check_mark: Test from corknpork.net: Slack alerts are working. {run}"
elif E('BUILD_RESULT') == 'failure' or E('DEPLOY_RESULT') == 'failure':
    what = [msg for var, msg in STEPS if E(var) == 'failure']
    if E('BUILD_RESULT') == 'success' and E('DEPLOY_RESULT') == 'failure':
        what = ["The page built fine but GitHub Pages didn't publish it."]
    lines = [':rotating_light: *corknpork.net didn\'t update.*'] + (what or ['Something in the update broke.']) + alerts
    if E('STEP_ESPN') == 'failure' and any('expired' in a or 'missing' in a for a in alerts):
        lines.append('Fix: sign in at espn.com, copy fresh `espn_s2` and `SWID` cookies, and paste them into the repo secrets '
                     '(github.com/joek-prince/corknpork/settings/secrets/actions).')
    lines.append(f'The site keeps showing the last good version until the next run. {run}')
    text = '\n'.join(lines)
elif alerts:
    text = '\n'.join([':warning: *corknpork.net updated, with a heads-up:*'] + alerts + [run])
else:
    text = ''

if not text:
    print('Nothing to report.')
elif not url:
    print('SLACK_WEBHOOK_URL is not set, so this was not sent:\n' + text)
else:
    req = urllib.request.Request(url, data=json.dumps({'text': text}).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        print(f'Posted to Slack ({r.status}):\n{text}')
