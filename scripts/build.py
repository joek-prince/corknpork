"""Render build/results.json into the finished site.

Usage: python3 scripts/build.py build/results.json _site/index.html
"""
import html
import json
import os
import sys

src = sys.argv[1] if len(sys.argv) > 1 else 'build/results.json'
dst = sys.argv[2] if len(sys.argv) > 2 else '_site/index.html'
R = json.load(open(src))
tpl = open(os.path.join(os.path.dirname(__file__), '..', 'site', 'template.html')).read()

first = R['seasons'][0]['year']
if R['cur']['seasonDone']:
    desc = f"The {R['current']} season is in the books. Champions, records and rivalries since {first}."
elif R['doneWeeks'] == 0:
    desc = f"The {R['current']} season is about to start. Champions, records and rivalries since {first}."
else:
    nxt = f", Week {R['previewWeek']} preview" if R.get('previewWeek') else ''
    desc = f"Week {R['doneWeeks']} recap{nxt}, the weekly bet and every record since {first}."

data = json.dumps(R, separators=(',', ':'), ensure_ascii=False).replace('</', '<\\/')
page = tpl.replace('__OG_DESC__', html.escape(desc, quote=True)).replace('__DATA__', data)
os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
open(dst, 'w').write(page)
print(f'Wrote {dst} ({len(page) // 1024} KB): {desc}')
