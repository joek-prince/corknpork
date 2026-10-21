"""Draw the link-preview card (og.png) and home-screen icons for the site.

Usage: python3 scripts/og.py build/results.json _site

The card is what iMessage, Slack and friends show when someone pastes the link,
so it carries this week's status line. Fonts live in site/fonts (SIL OFL).
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

src = sys.argv[1] if len(sys.argv) > 1 else 'build/results.json'
out = sys.argv[2] if len(sys.argv) > 2 else '_site'
R = json.load(open(src))
FONTS = os.path.join(os.path.dirname(__file__), '..', 'site', 'fonts')

MAROON, MAROON_DK, BRASS, BRASS_LT, CREAM = '#8C2B3B', '#5E1824', '#DDB862', '#EBD6A4', '#F8F1E4'
S = 2  # draw at 2x, then scale down for smooth edges
W, H = 1200, 630


def font(name, px):
    return ImageFont.truetype(os.path.join(FONTS, name), int(px * S))


def tracked_width(d, text, f, track):
    return sum(d.textlength(ch, font=f) for ch in text) + track * S * (len(text) - 1)


def draw_tracked(d, cx, y, text, f, fill, track=0):
    """Draw text centred on cx with extra letter spacing (in 1x px)."""
    x = cx * S - tracked_width(d, text, f, track) / 2
    for ch in text:
        d.text((x, y * S), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + track * S


def fit(d, text, name, px, max_w, track=0):
    """Largest font size (down from px) that keeps the line inside max_w."""
    while px > 18 and tracked_width(d, text, font(name, px), track) > max_w * S:
        px -= 1
    return font(name, px)


def trophy(d, cx, top, h, fill):
    """The site's favicon cup, scaled so it is h px tall with its top at `top`."""
    k = h / 35 * S  # favicon art spans y 14..49 in a 64-unit box
    X = lambda u: cx * S + (u - 32) * k
    Y = lambda v: top * S + (v - 14) * k
    w = max(2, int(3 * k))
    d.arc([X(11), Y(15), X(31), Y(31)], 90, 270, fill=fill, width=w)  # handles first; the cup covers their inner ends
    d.arc([X(33), Y(15), X(53), Y(31)], 270, 90, fill=fill, width=w)
    d.rectangle([X(20), Y(14), X(44), Y(22)], fill=fill)
    d.pieslice([X(20), Y(10), X(44), Y(34)], 0, 180, fill=fill)
    d.rectangle([X(29), Y(33), X(35), Y(42)], fill=fill)
    d.rounded_rectangle([X(21), Y(42), X(43), Y(49)], radius=2 * k, fill=fill)


def status_lines():
    C, Y = R['cur'], R['current']
    done = [s for s in R['seasons'] if s.get('done')]
    if C['seasonDone']:
        ch = R['seasons'][-1]['champ']
        return f"{Y} CHAMPION", f"{ch['team']} ({ch['owner']})"
    if R['doneWeeks'] == 0:
        champs = len({s['champ']['owner'] for s in done})
        return f"{Y} KICKS OFF SOON", f"{len(done)} seasons, {champs} different champions"
    wk, nxt = R['doneWeeks'], R.get('previewWeek')
    head = f"WEEK {wk} RECAP" + (f"  ·  WEEK {nxt} PREVIEW" if nxt else '')
    if wk >= R['regWeeks']:
        return head, f"{Y} playoffs are on"
    top = C['standings'][0]
    rec = f"{top['w']}-{top['l']}" + (f"-{top['tie']}" if top.get('tie') else '')
    return head, f"1st place: {top['team']} ({rec})"


def card(path):
    img = Image.new('RGB', (W * S, H * S), MAROON)
    d = ImageDraw.Draw(img)
    for i in range(H * S):  # gentle top-to-bottom darkening
        t = i / (H * S)
        r = int(0x94 + (0x6C - 0x94) * t); g = int(0x2E + (0x20 - 0x2E) * t); b = int(0x3F + (0x2D - 0x3F) * t)
        d.line([(0, i), (W * S, i)], fill=(r, g, b))
    d.rectangle([22 * S, 22 * S, (W - 22) * S, (H - 22) * S], outline=BRASS, width=4 * S)  # varsity double stroke
    d.rectangle([33 * S, 33 * S, (W - 33) * S, (H - 33) * S], outline=BRASS, width=1 * S)

    trophy(d, W / 2, 76, 92, BRASS)
    title = "CORK N' PORK"
    draw_tracked(d, W / 2, 182, title, fit(d, title, 'Graduate-Regular.ttf', 104, 1000, 2), CREAM, 2)
    draw_tracked(d, W / 2, 314, 'HALL OF FAME', font('BarlowSemiCondensed-Bold.ttf', 50), BRASS, 14)

    y = 406  # brass rule with a diamond in the middle
    d.line([(W / 2 - 230) * S, y * S, (W / 2 - 18) * S, y * S], fill=BRASS, width=2 * S)
    d.line([(W / 2 + 18) * S, y * S, (W / 2 + 230) * S, y * S], fill=BRASS, width=2 * S)
    d.polygon([((W / 2) * S, (y - 8) * S), ((W / 2 + 8) * S, y * S), ((W / 2) * S, (y + 8) * S), ((W / 2 - 8) * S, y * S)], fill=BRASS)

    l1, l2 = status_lines()
    draw_tracked(d, W / 2, 432, l1, fit(d, l1, 'BarlowSemiCondensed-Bold.ttf', 48, 1040, 3), CREAM, 3)
    draw_tracked(d, W / 2, 500, l2, fit(d, l2, 'Barlow-Medium.ttf', 40, 1040), BRASS_LT)
    img.resize((W, H), Image.LANCZOS).save(path, optimize=True)
    return l1, l2


def icon(path, px):
    img = Image.new('RGB', (px * S, px * S), MAROON)
    trophy(ImageDraw.Draw(img), px / 2, px * 0.2, px * 0.6, BRASS)
    img.resize((px, px), Image.LANCZOS).save(path, optimize=True)


os.makedirs(out, exist_ok=True)
lines = card(os.path.join(out, 'og.png'))
icon(os.path.join(out, 'apple-touch-icon.png'), 180)
icon(os.path.join(out, 'icon-192.png'), 192)
print('Drew og.png:', ' / '.join(lines))
