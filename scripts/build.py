#!/usr/bin/env python3
"""Renders the profile README's SVG cards. Standard library only.

  python3 scripts/build.py static                       # → assets/*.svg (committed to main)
  GITHUB_TOKEN=… python3 scripts/build.py live dist     # → dist/*.svg  (CI pushes to the output branch)
  python3 scripts/build.py live dist --gh               # same, but query through the local `gh` CLI

Content lives in scripts/profile.json; fonts/covers/sprite/icons come from scripts/prepare_media.py.
"""
import base64
import datetime as dt
import html
import json
import math
import os
import random
import subprocess
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = json.loads((ROOT / "scripts/profile.json").read_text())

PINK, CYAN, YELLOW, ORANGE, PURPLE, LIME, RED = "#ff2e88", "#2de2e6", "#ffd319", "#ff8a3d", "#a35bff", "#9cff57", "#ff4d5e"
TEXT, DIM, LINE, INK = "#f4f1ff", "#9a93c9", "#2a2156", "#120c2a"
RARITY = {"legendary": ORANGE, "epic": PURPLE, "rare": CYAN}
CJK = "'PingFang SC','Hiragino Sans GB','Microsoft YaHei','Noto Sans CJK SC','Noto Sans SC',sans-serif"
FONTS = {"PxA": "arcade", "PxM": "mono-500", "PxB": "mono-800"}

BASE_CSS = (
    ".a{font-family:PxA,monospace}.m{font-family:PxM,ui-monospace,monospace}"
    ".b{font-family:PxB,ui-monospace,monospace;font-weight:800}"
    f".c{{font-family:{CJK}}}"
    "@keyframes blink{50%{opacity:0}}.blink{animation:blink 1s steps(1) infinite}"
    "@keyframes fadein{from{opacity:0}}.in{animation:fadein .6s ease-out backwards}"
    "@keyframes pulse{50%{opacity:.35}}.pulse{animation:pulse 2.4s ease-in-out infinite}"
    "@keyframes tw{0%,100%{opacity:.15}50%{opacity:1}}.tw{animation:tw 3s ease-in-out infinite}"
    "@keyframes grow{from{transform:scaleX(0)}}"
    ".grow{transform-box:fill-box;transform-origin:0 50%;animation:grow 1.2s cubic-bezier(.2,.8,.2,1) .3s backwards}"
)
NEON = ('<filter id="neon" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.5" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
PANEL_DEFS = (
    '<linearGradient id="pbg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#170f37"/><stop offset="1" stop-color="#0c0820"/></linearGradient>'
    f'<linearGradient id="pst" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PINK}"/><stop offset=".5" stop-color="{PURPLE}"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>'
)


def esc(s):
    return html.escape(str(s), quote=True)


def font_face(fam):
    data = base64.b64encode((ROOT / f"assets/fonts/{FONTS[fam]}.woff2").read_bytes()).decode()
    return f"@font-face{{font-family:{fam};src:url(data:font/woff2;base64,{data}) format('woff2')}}"


def svg(w, h, body, title, css="", defs="", fonts=FONTS):
    faces = "".join(font_face(f) for f in fonts)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="{esc(title)}"><title>{esc(title)}</title><style>{faces}{BASE_CSS}{css}</style>'
            f"<defs>{NEON}{PANEL_DEFS}{defs}</defs>{body}</svg>\n")


def t(x, y, s, cls="m", size=16, fill=TEXT, anchor="start", extra=""):
    return (f'<text x="{x:g}" y="{y:g}" class="{cls}" font-size="{size:g}" fill="{fill}" '
            f'text-anchor="{anchor}" {extra}>{esc(s)}</text>')


def panel(w, h, rx=16):
    return f'<rect x="1.5" y="1.5" width="{w - 3}" height="{h - 3}" rx="{rx}" fill="url(#pbg)" stroke="url(#pst)" stroke-width="3"/>'


def text_width(s, size, cls):
    if cls == "a":
        return len(s) * size
    if cls in ("m", "b"):
        return len(s) * size * 0.6
    return sum(size if unicodedata.east_asian_width(ch) in "WF" else size * 0.56 for ch in s)


def wrap(s, width, size, max_lines):
    """Greedy wrap for mixed CJK/latin text; CJK breaks anywhere, latin at spaces."""
    tokens, word = [], ""
    for ch in s:
        if unicodedata.east_asian_width(ch) in "WF":
            if word:
                tokens.append(word)
                word = ""
            tokens.append(ch)
        else:
            word += ch
            if ch == " ":
                tokens.append(word)
                word = ""
    if word:
        tokens.append(word)
    lines, cur = [], ""
    for tok in tokens:
        if cur and text_width(cur + tok, size, "c") > width:
            lines.append(cur.rstrip())
            cur = tok.lstrip()
        else:
            cur += tok
    if cur:
        lines.append(cur.rstrip())
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while text_width(lines[-1] + "…", size, "c") > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines


def sprite_rects(x0, y0, s):
    d = json.loads((ROOT / "assets/sprite.json").read_text())
    out = []
    for y, row in enumerate(d["rows"]):
        x = 0
        while x < len(row):
            c, x2 = row[x], x
            while x2 < len(row) and row[x2] == c:
                x2 += 1
            if c != ".":
                out.append(f'<rect x="{x0 + x * s}" y="{y0 + y * s}" width="{(x2 - x) * s}" height="{s}" fill="{d["palette"][c]}"/>')
            x = x2
    return f'<g shape-rendering="crispEdges">{"".join(out)}</g>'


# ───────────────────────────────────────────── static cards ──


def hero():
    W, H, HZ = 1000, 320, 214
    rnd = random.Random(2018)
    stars = "".join(
        f'<rect x="{rnd.randrange(8, W - 8)}" y="{rnd.randrange(64, HZ - 24)}" width="{s}" height="{s}" '
        f'fill="{rnd.choice((TEXT, TEXT, CYAN, PINK, YELLOW))}" class="tw" '
        f'style="animation-delay:-{rnd.random() * 4:.2f}s;animation-duration:{2 + rnd.random() * 3:.1f}s"/>'
        for s in (rnd.choice((2, 2, 2, 3, 4)) for _ in range(70)))

    slats = "".join(f'<rect x="0" y="{HZ - 4 - i * 14 - (7 - i)}" width="{W}" height="{max(1, 7 - i)}" fill="#000"/>' for i in range(7))
    sun = (f'<circle cx="500" cy="{HZ}" r="160" fill="{PINK}" opacity=".25" filter="url(#blur)" class="pulse"/>'
           f'<circle cx="500" cy="{HZ + 18}" r="128" fill="url(#sun)" mask="url(#slats)" clip-path="url(#sky)"/>')

    def ridge(xs, seed):
        r = random.Random(seed)
        pts = [(xs[0], HZ)] + [(x, HZ - r.randrange(12, 58)) for x in range(xs[0] + 30, xs[1], 30)] + [(xs[1], HZ)]
        return (f'<polygon points="{" ".join(f"{x},{y}" for x, y in pts)}" fill="#160a33" stroke="{PINK}" '
                f'stroke-opacity=".55" stroke-width="1.5" stroke-linejoin="bevel"/>')

    verticals = "".join(f'<line x1="{500 + k * 9}" y1="{HZ}" x2="{500 + k * 100}" y2="{H}"/>' for k in range(-15, 16))
    depth = lambda d: HZ + (H - HZ) * d ** 2.3
    n = 10
    horizontals = "".join(
        f'<line x1="0" x2="{W}" y1="{depth(i / n):.1f}" y2="{depth(i / n):.1f}">'
        f'<animate attributeName="y1" values="{depth(i / n):.1f};{depth((i + 1) / n):.1f}" dur=".9s" repeatCount="indefinite"/>'
        f'<animate attributeName="y2" values="{depth(i / n):.1f};{depth((i + 1) / n):.1f}" dur=".9s" repeatCount="indefinite"/></line>'
        for i in range(n))

    hud = (t(40, 32, "1UP", "a blink", 14, PINK) + t(40, 52, "002018", "a", 14, TEXT)
           + t(500, 32, "HI-SCORE", "a", 14, PINK, "middle") + t(500, 52, "999999", "a", 14, TEXT, "middle")
           + t(960, 32, "CREDIT", "a", 14, PINK, "end") + t(960, 52, "99", "a", 14, TEXT, "end"))

    name = P["name"]
    title = (
        '<g class="a" font-size="56" text-anchor="middle">'
        + "".join(f'<text x="{500 + i}" y="{126 + i}" fill="#3b0d5c">{name}</text>' for i in range(6, 0, -1))
        + f'<g class="g1"><text x="500" y="126" fill="{CYAN}" opacity=".85">{name}</text></g>'
        + f'<g class="g2"><text x="500" y="126" fill="{PINK}" opacity=".85">{name}</text></g>'
        + f'<text x="500" y="126" fill="url(#chrome)" filter="url(#tglow)">{name}</text></g>')

    # typing dialog box: one shared clip whose width steps through every tagline in turn
    lines, size = P["taglines"], 22
    cw = size * 0.6
    box_w = max(len(s) for s in lines) * cw + 64
    bx, tx = 500 - box_w / 2, 500 - box_w / 2 + 24
    seg, total = 3.6, 3.6 * len(lines)
    events = [(0.0, 0)]
    for j, s in enumerate(lines):
        start = j * seg
        events += [(start + (c / len(s)) * seg * 0.45, c) for c in range(1, len(s) + 1)]
        events.append((start + seg * 0.92, 0))
    kt = ";".join(f"{a / total:.4f}" for a, _ in events)
    widths = ";".join(f"{c * cw:.1f}" for _, c in events)
    xs = ";".join(f"{tx + c * cw:.1f}" for _, c in events)
    vis = []
    for j, s in enumerate(lines):
        a, b = j / len(lines), (j + 1) / len(lines)
        vals, kts = (["1", "0"], ["0", f"{b:.4f}"]) if j == 0 else (["0", "1", "0"], ["0", f"{a:.4f}", f"{b:.4f}"])
        if b >= 1:
            vals, kts = vals[:-1], kts[:-1]
        anim = f'<animate attributeName="opacity" values="{";".join(vals)}" keyTimes="{";".join(kts)}" calcMode="discrete" dur="{total}s" repeatCount="indefinite"/>'
        vis.append(f'<text x="{tx:.1f}" y="175" class="m" font-size="{size}" fill="{CYAN}" opacity="{1 if j == 0 else 0}">{esc(s)}{anim}</text>')
    typing = (
        f'<rect x="{bx:.1f}" y="146" width="{box_w:.1f}" height="40" rx="8" fill="#0b0618" fill-opacity=".82" stroke="{CYAN}" stroke-opacity=".5" stroke-width="1.5"/>'
        f'<clipPath id="type"><rect x="{tx:.1f}" y="146" width="{len(lines[0]) * cw:.1f}" height="40">'
        f'<animate attributeName="width" values="{widths}" keyTimes="{kt}" calcMode="discrete" dur="{total}s" repeatCount="indefinite"/></rect></clipPath>'
        f'<g clip-path="url(#type)">{"".join(vis)}</g>'
        f'<rect x="{tx + len(lines[0]) * cw:.1f}" y="157" width="11" height="22" fill="{CYAN}" class="blink">'
        f'<animate attributeName="x" values="{xs}" keyTimes="{kt}" calcMode="discrete" dur="{total}s" repeatCount="indefinite"/></rect>')

    defs = (
        f'<clipPath id="card"><rect width="{W}" height="{H}" rx="18"/></clipPath>'
        f'<clipPath id="sky"><rect width="{W}" height="{HZ}"/></clipPath>'
        f'<clipPath id="ground"><rect y="{HZ}" width="{W}" height="{H - HZ}"/></clipPath>'
        f'<mask id="slats"><rect width="{W}" height="{H}" fill="#fff"/>{slats}</mask>'
        f'<mask id="fade"><rect y="{HZ}" width="{W}" height="{H - HZ}" fill="url(#fadeg)"/></mask>'
        f'<linearGradient id="fadeg" gradientUnits="userSpaceOnUse" x1="0" y1="{HZ}" x2="0" y2="{HZ + 80}"><stop offset="0" stop-color="#000"/><stop offset="1" stop-color="#fff"/></linearGradient>'
        '<linearGradient id="skyg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#05031a"/><stop offset=".55" stop-color="#1c0a3f"/><stop offset="1" stop-color="#4a0f55"/></linearGradient>'
        '<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2a0848"/><stop offset="1" stop-color="#07031a"/></linearGradient>'
        '<linearGradient id="sun" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff6a8"/><stop offset=".35" stop-color="#ffc23a"/><stop offset=".75" stop-color="#ff4f8b"/><stop offset="1" stop-color="#c2187a"/></linearGradient>'
        '<linearGradient id="chrome" gradientUnits="userSpaceOnUse" x1="0" y1="78" x2="0" y2="126"><stop offset="0" stop-color="#ffffff"/><stop offset=".48" stop-color="#fff0b0"/><stop offset=".52" stop-color="#ff9fd2"/><stop offset="1" stop-color="#ff2e88"/></linearGradient>'
        '<linearGradient id="shootg" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="90" y2="-32"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        '<radialGradient id="vig" cx=".5" cy=".5" r=".75"><stop offset=".6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".6"/></radialGradient>'
        '<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1.3" fill="#000"/></pattern>'
        '<filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="24"/></filter>'
        f'<filter id="tglow" x="-20%" y="-40%" width="140%" height="180%"><feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="{PINK}" flood-opacity=".9"/></filter>'
    )
    css = (
        "@keyframes g1{0%,88%,100%{transform:translate(0,0)}89%{transform:translate(-7px,2px)}91%{transform:translate(5px,-2px)}93%{transform:translate(-3px,1px)}95%{transform:translate(0,0)}}"
        "@keyframes g2{0%,88%,100%{transform:translate(0,0)}89%{transform:translate(6px,-1px)}91%{transform:translate(-5px,2px)}93%{transform:translate(3px,0)}95%{transform:translate(0,0)}}"
        ".g1{animation:g1 4.5s infinite}.g2{animation:g2 4.5s infinite}"
        "@keyframes shoot{0%{transform:translate(940px,70px);opacity:0}2%{opacity:1}14%{transform:translate(600px,190px);opacity:0}100%{transform:translate(600px,190px);opacity:0}}"
        ".shoot{animation:shoot 7s linear 1.5s infinite;opacity:0}"
        "@keyframes roll{from{transform:translateY(-80px)}to{transform:translateY(340px)}}.roll{animation:roll 7s linear infinite}"
    )
    body = (
        f'<g clip-path="url(#card)">'
        f'<rect width="{W}" height="{H}" fill="url(#skyg)"/>{stars}'
        f'<g class="shoot"><line x1="0" y1="0" x2="90" y2="-32" stroke="url(#shootg)" stroke-width="2.5" stroke-linecap="round"/></g>'
        f'{sun}{ridge((0, 380), 3)}{ridge((620, 1000), 9)}'
        f'<rect y="{HZ}" width="{W}" height="{H - HZ}" fill="url(#floor)"/>'
        f'<g clip-path="url(#ground)" mask="url(#fade)" stroke="{PINK}" stroke-width="1.6" filter="url(#neon)">{verticals}{horizontals}</g>'
        f'<line x1="0" x2="{W}" y1="{HZ}" y2="{HZ}" stroke="#ff8fd0" stroke-width="2.5" filter="url(#neon)"/>'
        f"{hud}{title}{typing}"
        + t(502, 294, "PRESS START", "a blink", 16, "#000", "middle", 'opacity=".6"')
        + t(500, 292, "PRESS START", "a blink", 16, YELLOW, "middle")
        + f'<rect width="{W}" height="{H}" fill="url(#scan)" opacity=".35"/>'
        f'<rect class="roll" width="{W}" height="60" fill="#fff" opacity=".035"/>'
        f'<rect width="{W}" height="{H}" fill="url(#vig)"/></g>'
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="17" fill="none" stroke="#3a2a78" stroke-width="2"/>'
    )
    return svg(W, H, body, f"{name} — {' / '.join(s.lstrip('> ') for s in lines)}", css, defs)


def header(stage, title):
    W, H = 1000, 64
    end = 44 + len(title) * 26 + 24
    body = (
        t(4, 43, "▶", "a blink", 22, PINK)
        + t(47, 47, title, "a", 26, CYAN, extra='opacity=".9"')
        + t(44, 44, title, "a", 26, PINK)
        + f'<line x1="{end}" y1="33" x2="{W - 150}" y2="33" stroke="{DIM}" stroke-width="4" stroke-dasharray="4 10" opacity=".7">'
        '<animate attributeName="stroke-dashoffset" values="0;-14" dur=".8s" repeatCount="indefinite"/></line>'
        + t(W - 4, 41, f"STAGE {stage:02d}", "a", 14, DIM, "end"))
    return svg(W, H, body, title, fonts=("PxA",))


def library():
    W, H = 1000, 340
    cw, ch, gap, y0 = 168, 232, 22, 58
    x0 = (W - (5 * cw + 4 * gap)) / 2
    defs, carts = [], []
    for i, g in enumerate(P["games"]):
        x = x0 + i * (cw + gap)
        img = base64.b64encode((ROOT / f"assets/covers/{g['cover']}.jpg").read_bytes()).decode()
        lum = sum(int(g["color"][k:k + 2], 16) * w for k, w in ((1, .299), (3, .587), (5, .114)))
        ink = INK if lum > 140 else TEXT
        defs.append(f'<clipPath id="lbl{i}"><rect x="{x + 12}" y="{y0 + 30}" width="144" height="144" rx="6"/></clipPath>')
        ridges = "".join(f'<rect x="{x + 22 + k * 18}" y="{y0 + 10}" width="8" height="12" rx="2" fill="#17122f"/>' for k in range(7))
        glow = ""
        if g.get("now"):
            glow = (f'<rect x="{x - 4}" y="{y0 - 4}" width="{cw + 8}" height="{ch + 8}" rx="15" fill="none" stroke="{PINK}" stroke-width="3" filter="url(#neon)" class="pulse"/>'
                    f'<rect x="{x + cw / 2 - 72}" y="{y0 - 40}" width="144" height="26" rx="13" fill="{PINK}"/>'
                    + t(x + cw / 2, y0 - 22, "▶ NOW PLAYING", "a blink", 9, TEXT, "middle"))
        carts.append(
            f'<g class="float" style="animation-delay:-{i * 0.8:.1f}s">{glow}'
            f'<rect x="{x}" y="{y0}" width="{cw}" height="{ch}" rx="12" fill="#2a2350" stroke="#4a3f86" stroke-width="2"/>{ridges}'
            f'<image href="data:image/jpeg;base64,{img}" x="{x + 12}" y="{y0 + 30}" width="144" height="144" preserveAspectRatio="xMidYMid slice" clip-path="url(#lbl{i})"/>'
            f'<g clip-path="url(#lbl{i})"><rect class="shine" x="{x - 120}" y="{y0 + 20}" width="70" height="170" fill="url(#shine)" style="animation-delay:{i * 0.6:.1f}s"/></g>'
            f'<rect x="{x + 12}" y="{y0 + 30}" width="144" height="144" rx="6" fill="none" stroke="{g["color"]}" stroke-width="2"/>'
            f'<rect x="{x + 12}" y="{y0 + 180}" width="144" height="40" rx="6" fill="{g["color"]}"/>'
            + t(x + cw / 2, y0 + 198, g["title"], "a", 10, ink, "middle")
            + t(x + cw / 2, y0 + 213, g["platform"], "b", 11, ink, "middle", 'opacity=".75"') + "</g>")
    css = ("@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}.float{animation:float 4s ease-in-out infinite}"
           "@keyframes shine{0%{transform:translateX(0) skewX(-20deg)}30%,100%{transform:translateX(300px) skewX(-20deg)}}"
           ".shine{animation:shine 5s ease-in-out infinite;transform-box:fill-box}")
    defs.append('<linearGradient id="shine" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
                '<stop offset=".5" stop-color="#fff" stop-opacity=".45"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    shelf_y = y0 + ch + 16
    body = (panel(W, H) + "".join(carts)
            + f'<line x1="28" x2="{W - 28}" y1="{shelf_y}" y2="{shelf_y}" stroke="{CYAN}" stroke-width="3" filter="url(#neon)"/>'
            + t(W / 2, shelf_y + 24, f"SAVE FILES FOUND: {len(P['games'])}", "a", 10, DIM, "middle"))
    names = ", ".join(g["title"].title() for g in P["games"])
    return svg(W, H, body, f"Game library: {names}", css, "".join(defs), fonts=("PxA", "PxB"))


def loadout():
    W, H = 1000, 300
    icons = json.loads((ROOT / "assets/icons.json").read_text())
    sw, sh, gap = 140, 104, 18
    x0, y0 = (W - (6 * sw + 5 * gap)) / 2, 26
    defs = "".join(
        f'<radialGradient id="r{k}" cx=".5" cy="1" r=".9"><stop offset="0" stop-color="{c}" stop-opacity=".35"/><stop offset="1" stop-color="#160f34" stop-opacity="0"/></radialGradient>'
        for k, c in RARITY.items())
    slots = []
    for i, it in enumerate(P["loadout"]):
        x, y = x0 + (i % 6) * (sw + gap), y0 + (i // 6) * (sh + gap)
        col = RARITY[it["rarity"]]
        extra = ""
        if it["rarity"] == "legendary":
            extra = (f'<rect x="{x}" y="{y}" width="{sw}" height="{sh}" rx="12" fill="none" stroke="{col}" stroke-width="3" filter="url(#neon)" class="pulse" style="animation-delay:-{i * 0.4:.1f}s"/>'
                     f'<path d="M0,-7 L1.6,-1.6 7,0 1.6,1.6 0,7 -1.6,1.6 -7,0 -1.6,-1.6Z" transform="translate({x + sw - 16},{y + 16})" fill="{YELLOW}" class="tw" style="animation-delay:-{i * 0.5:.1f}s"/>')
        slots.append(
            f'<g class="in" style="animation-delay:{0.15 + i * 0.07:.2f}s">'
            f'<rect x="{x}" y="{y}" width="{sw}" height="{sh}" rx="12" fill="#160f34"/>'
            f'<rect x="{x}" y="{y}" width="{sw}" height="{sh}" rx="12" fill="url(#r{it["rarity"]})" stroke="{col}" stroke-width="2"/>{extra}'
            f'<path d="{icons[it["icon"]]}" transform="translate({x + sw / 2 - 19},{y + 18}) scale(1.6)" fill="{it["color"]}"/>'
            + t(x + sw / 2, y + 88, it["name"], "a", 10, TEXT, "middle") + "</g>")
    legend, lx = [], 0
    items = [("LEGENDARY", RARITY["legendary"]), ("EPIC", RARITY["epic"]), ("RARE", RARITY["rare"])]
    total = sum(len(n) * 10 + 22 for n, _ in items) + 28 * (len(items) - 1)
    lx = W / 2 - total / 2
    for n, c in items:
        legend.append(f'<rect x="{lx + 2}" y="{H - 27}" width="9" height="9" fill="{c}" transform="rotate(45 {lx + 6.5} {H - 22.5})"/>' + t(lx + 20, H - 18, n, "a", 10, c))
        lx += len(n) * 10 + 22 + 28
    body = panel(W, H) + "".join(slots) + "".join(legend)
    return svg(W, H, body, "Loadout: " + ", ".join(it["name"].title() for it in P["loadout"]), defs=defs, fonts=("PxA",))


def footer():
    W, H, GY = 1000, 280, 214
    rnd = random.Random(1222)
    stars = "".join(f'<rect x="{rnd.randrange(10, 700)}" y="{rnd.randrange(10, 70)}" width="2" height="2" fill="#fff" class="tw" '
                    f'style="animation-delay:-{rnd.random() * 3:.1f}s"/>' for _ in range(24))
    TX, TY = 846, 118
    # canopy: many small blobs inside an ellipse, painted back-to-front and lit from the setting sun (left)
    shades = ["#4a1530", "#6e1f36", "#8f2a33", "#b8402e", "#d0582c", "#e8822f", "#f09a3a", "#ffc25c"]
    blobs = []
    for _ in range(70):
        a, rr = rnd.uniform(0, math.tau), rnd.uniform(0, 1) ** 0.6
        dx, dy = math.cos(a) * rr * 92, math.sin(a) * rr * 62
        light = (-dx / 92 * 0.45) + (-dy / 62 * 0.35) + rnd.uniform(-0.25, 0.35)
        blobs.append((light, dx, dy, rnd.uniform(9, 22)))
    blobs.sort()
    lo, hi = blobs[0][0], blobs[-1][0]
    canopy = "".join(
        f'<circle cx="{TX + dx:.0f}" cy="{TY + dy:.0f}" r="{r:.0f}" fill="{shades[min(7, int((l - lo) / (hi - lo + 1e-9) * 8))]}"/>'
        for l, dx, dy, r in blobs)
    tree = (f'<path d="M{TX - 9},{GY + 6} L{TX - 6},{TY + 30} L{TX - 34},{TY + 4} L{TX - 4},{TY + 18} L{TX + 2},{TY - 10} L{TX + 6},{TY + 16} '
            f'L{TX + 34},{TY} L{TX + 8},{TY + 32} L{TX + 10},{GY + 6}Z" fill="#160a1f"/>{canopy}')
    leaf_cols = ["#f09a3a", "#e8822f", "#d9642b", "#c24f2c", "#ffd36b", "#b8402e"]
    leaves, kfs = [], []
    for i in range(18):
        sx, sy = TX + rnd.randrange(-80, 80), TY + rnd.randrange(-70, 10)
        ex, ey = sx - rnd.randrange(260, 720), H + 10
        rot, sway = rnd.choice((-1, 1)) * rnd.randrange(360, 900), rnd.randrange(18, 40)
        steps = []
        for p in (0, 25, 50, 75, 100):
            f = p / 100
            x = sx + (ex - sx) * f + math.sin(f * math.pi * 3) * sway
            y = sy + (ey - sy) * (f ** 1.15)
            op = 0 if p == 0 else (1 if p <= 50 else (0.6 if p == 75 else 0))
            steps.append(f"{p}%{{transform:translate({x:.0f}px,{y:.0f}px) rotate({rot * f:.0f}deg);opacity:{op}}}")
        kfs.append(f"@keyframes lf{i}{{{''.join(steps)}}}.lf{i}{{animation:lf{i} {rnd.uniform(8, 14):.1f}s linear -{rnd.uniform(0, 14):.1f}s infinite}}")
        s = rnd.uniform(0.8, 1.4)
        leaves.append(f'<path class="lf{i}" transform="translate({sx},{sy})" d="M0,{-7 * s:.1f} C{5 * s:.1f},{-4 * s:.1f} {5 * s:.1f},{3 * s:.1f} 0,{8 * s:.1f} C{-5 * s:.1f},{3 * s:.1f} {-5 * s:.1f},{-4 * s:.1f} 0,{-7 * s:.1f}Z" fill="{rnd.choice(leaf_cols)}"/>')
    flies = "".join(
        f'<circle cx="{rnd.randrange(80, 760)}" cy="{rnd.randrange(GY + 4, H - 40)}" r="2" fill="{YELLOW}" filter="url(#neon)" class="fly" '
        f'style="animation-delay:-{rnd.random() * 6:.1f}s;animation-duration:{5 + rnd.random() * 4:.1f}s"/>' for _ in range(9))
    q1, q2 = P["quote"]
    QX = 420
    quote = (f'<text x="{QX - 330}" y="92" font-family="Georgia,serif" font-size="80" fill="{ORANGE}" opacity=".55">“</text>'
             f'<text x="{QX}" y="100" font-family="Georgia,\'Times New Roman\',serif" font-style="italic" font-size="26" fill="#fff1e0" text-anchor="middle" class="in" style="animation-delay:.3s">{esc(q1)}</text>'
             f'<text x="{QX}" y="140" font-family="Georgia,\'Times New Roman\',serif" font-style="italic" font-size="26" fill="#fff1e0" text-anchor="middle" class="in" style="animation-delay:1.4s">{esc(q2)}</text>')
    defs = (f'<clipPath id="card"><rect width="{W}" height="{H}" rx="18"/></clipPath>'
            '<linearGradient id="dusk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#120830"/><stop offset=".45" stop-color="#46185c"/>'
            '<stop offset=".72" stop-color="#a8345a"/><stop offset="1" stop-color="#ff8a3d"/></linearGradient>'
            '<radialGradient id="fsun"><stop offset="0" stop-color="#fff0a8"/><stop offset=".7" stop-color="#ffb347"/><stop offset="1" stop-color="#ff7a3d"/></radialGradient>'
            '<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1.3" fill="#000"/></pattern>')
    css = ("".join(kfs) + "@keyframes sink{to{transform:translateY(10px)}}.sink{animation:sink 9s ease-in-out infinite alternate}"
           "@keyframes fly{0%,100%{transform:translate(0,0);opacity:.2}50%{transform:translate(12px,-16px);opacity:1}}.fly{animation:fly 6s ease-in-out infinite}")
    body = (
        f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="url(#dusk)"/>{stars}'
        f'<g class="sink"><circle cx="230" cy="{GY + 6}" r="58" fill="url(#fsun)"/></g>'
        f'<path d="M0,{GY - 6} C180,{GY - 30} 320,{GY - 4} 520,{GY - 18} C700,{GY - 32} 860,{GY - 6} 1000,{GY - 20} L1000,{H} L0,{H}Z" fill="#3a1446" opacity=".85"/>'
        f'<path d="M0,{GY + 8} C200,{GY - 4} 420,{GY + 14} 640,{GY + 2} C800,{GY - 6} 900,{GY + 4} 1000,{GY} L1000,{H} L0,{H}Z" fill="#170b24"/>'
        f"{tree}{quote}{''.join(leaves)}{flies}"
        + t(QX, GY + 32, "THANKS FOR PLAYING", "a", 14, YELLOW, "middle")
        + t(QX, GY + 56, "CONTINUE? ▶", "a blink", 11, PINK, "middle")
        + f'<rect width="{W}" height="{H}" fill="url(#scan)" opacity=".18"/></g>'
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="17" fill="none" stroke="#3a2a78" stroke-width="2"/>')
    return svg(W, H, body, f"“{q1} {q2}” — Thanks for playing", css, defs, fonts=("PxA",))


# ───────────────────────────────────────────── live cards ──


def gql(query, variables, use_gh=False):
    if use_gh:
        args = ["gh", "api", "graphql", "-f", f"query={query}"] + [x for k, v in variables.items() for x in ("-F", f"{k}={v}")]
        res = json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)
    else:
        req = urllib.request.Request("https://api.github.com/graphql", json.dumps({"query": query, "variables": variables}).encode(),
                                     {"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "Content-Type": "application/json"})
        res = json.loads(urllib.request.urlopen(req, timeout=60).read())
    if res.get("errors"):
        raise SystemExit(f"GraphQL error: {res['errors']}")
    return res["data"]


def fetch(use_gh):
    login = P["login"]
    created = gql("query($login:String!){user(login:$login){createdAt}}", {"login": login}, use_gh)["user"]["createdAt"]
    now = dt.datetime.now(dt.timezone.utc)
    years = "".join(
        f'y{y}:contributionsCollection(from:"{max(created, f"{y}-01-01T00:00:00Z")}",to:"{min(now.strftime("%Y-%m-%dT%H:%M:%SZ"), f"{y}-12-31T23:59:59Z")}")'
        "{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}"
        for y in range(int(created[:4]), now.year + 1))
    q = ("query($login:String!){user(login:$login){createdAt "
         "recent:contributionsCollection{totalCommitContributions contributionCalendar{totalContributions}} "
         "repositories(first:100,ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC){nodes{name description url homepageUrl "
         "stargazerCount pushedAt primaryLanguage{name color} languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}} "
         + years + "}}")
    return gql(q, {"login": login}, use_gh)["user"]


def summarize(u, today):
    years = [v for k, v in u.items() if k.startswith("y") and k[1:].isdigit()]
    days = {}
    for y in years:
        for w in y["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = max(days.get(d["date"], 0), d["contributionCount"])
    longest = run = 0
    prev = None
    for date in sorted(days):
        cur = dt.date.fromisoformat(date)
        if days[date] > 0:
            run = run + 1 if prev and (cur - prev).days == 1 and days[prev.isoformat()] > 0 else 1
            longest = max(longest, run)
        prev = cur
    current, d = 0, today if days.get(today.isoformat(), 0) > 0 else today - dt.timedelta(days=1)
    while days.get(d.isoformat(), 0) > 0:
        current, d = current + 1, d - dt.timedelta(days=1)
    langs = {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            langs.setdefault(n, [0, e["node"]["color"] or DIM])[0] += e["size"]
    return {
        "total": sum(y["contributionCalendar"]["totalContributions"] for y in years),
        "recent": u["recent"]["contributionCalendar"]["totalContributions"],
        "commits": u["recent"]["totalCommitContributions"],
        "repos": len(u["repositories"]["nodes"]),
        "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "longest": longest, "current": current,
        "langs": sorted(((n, s, c) for n, (s, c) in langs.items()), key=lambda x: -x[1]),
    }


def player(created, today):
    W, H = 1000, 430
    lv_years = today.year - created.year - ((today.month, today.day) < (created.month, created.day))
    last = created.replace(year=created.year + lv_years)
    nxt = created.replace(year=created.year + lv_years + 1)
    pct, left = (today - last).days / (nxt - last).days, (nxt - today).days
    level = lv_years + 1

    fx, fy, fs = 28, 28, 256
    portrait = (
        f'<clipPath id="pf"><rect x="{fx}" y="{fy}" width="{fs}" height="{fs}" rx="10"/></clipPath>'
        f'<rect x="{fx}" y="{fy}" width="{fs}" height="{fs}" rx="10" fill="url(#port)"/>'
        f'<g clip-path="url(#pf)"><g class="bob">{sprite_rects(fx + 8, fy + fs - 240, 6)}</g></g>'
        f'<rect x="{fx}" y="{fy}" width="{fs}" height="{fs}" rx="10" fill="none" stroke="{CYAN}" stroke-width="3"/>'
        + t(fx, 324, P["name"], "a", 22, TEXT) + t(fx + fs, 324, f"LV.{level:02d}", "a", 16, YELLOW, "end")
        + t(fx, 350, P["class"], "b", 14, CYAN)
        + t(fx, 379, "EXP", "a", 11, DIM)
        + f'<rect x="{fx + 44}" y="{368}" width="{fs - 44}" height="12" rx="2" fill="{LINE}"/>'
        f'<rect x="{fx + 44}" y="{368}" width="{(fs - 44) * pct:.1f}" height="12" rx="2" fill="url(#exp)" class="grow"/>'
        + t(fx, 404, f"NEXT LV IN {left}D", "a", 10, DIM) + t(fx + fs, 404, f"{pct:.0%}", "a", 10, YELLOW, "end"))

    mx = 318
    attrs = [t(mx, 50, "ATTRIBUTES", "a", 13, CYAN)]
    row_cols = [PINK, CYAN, LIME, None, RED]
    rainbow = [RED, ORANGE, YELLOW, LIME, "#3dffb0", CYAN, "#4d9dff", PURPLE, "#e05bff", PINK]
    for i, a in enumerate(P["attributes"]):
        y = 86 + i * 40
        attrs.append(t(mx, y, a["name"], "b", 15, TEXT))
        for k in range(10):
            bx = 448 + k * 17
            attrs.append(f'<rect x="{bx}" y="{y - 14}" width="14" height="16" fill="#241b4d"/>')
            if k < a["value"]:
                col = rainbow[k] if a.get("note") == "MAX" else (row_cols[i % len(row_cols)] or PINK)
                attrs.append(f'<rect x="{bx}" y="{y - 14}" width="14" height="16" fill="{col}" class="seg" style="animation-delay:{0.3 + i * 0.18 + k * 0.05:.2f}s"/>')
        if a.get("note"):
            col = RED if a["value"] < 5 else YELLOW
            attrs.append(t(626, y, a["note"], "a blink", 10, col))
    attrs.append(t(mx, 284, "PLATFORMS", "a", 13, CYAN))
    cx = mx
    for p in P["platforms"]:
        w = len(p["name"]) * 10 + 24
        attrs.append(f'<rect x="{cx}" y="298" width="{w}" height="28" rx="4" fill="{p["color"]}"'
                     + (' stroke="#66c0f4" stroke-width="1.5"' if p["name"] == "STEAM" else "") + "/>")
        attrs.append(t(cx + w / 2, 317, p["name"], "a", 10, TEXT, "middle"))
        cx += w + 10

    ex = 690
    equip = [t(ex, 50, "EQUIPMENT", "a", 13, CYAN)]
    for i, e in enumerate(P["equipment"]):
        y = 68 + i * 44
        col = RARITY[e["rarity"]]
        equip.append(f'<rect x="{ex}" y="{y}" width="34" height="34" rx="6" fill="#1a1340" stroke="{col}" stroke-width="2"/>'
                     f'<rect x="{ex + 12}" y="{y + 12}" width="10" height="10" fill="{col}" transform="rotate(45 {ex + 17} {y + 17})"'
                     + (' class="pulse"' if e["rarity"] == "legendary" else "") + "/>")
        equip.append(t(ex + 46, y + 12, e["slot"], "a", 9, DIM) + t(ex + 46, y + 31, e["item"], "b", 15, TEXT))

    quest = (f'<rect x="{mx}" y="346" width="{W - 28 - mx}" height="60" rx="8" fill="#1b1236" stroke="{YELLOW}" stroke-width="1.5" stroke-dasharray="6 4"/>'
             + t(mx + 16, 370, "NOW PLAYING", "a", 10, YELLOW) + t(mx + 150, 371, P["now_playing"], "b", 15, TEXT)
             + t(mx + 16, 394, "SIDE QUEST", "a", 10, PINK) + t(mx + 150, 395, P["side_quest"], "m", 15, TEXT)
             + t(W - 62, 386, "!", "a bounce", 20, YELLOW))
    defs = ('<linearGradient id="port" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe3f1"/><stop offset="1" stop-color="#c9f1ff"/></linearGradient>'
            f'<linearGradient id="exp" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{YELLOW}"/><stop offset="1" stop-color="{ORANGE}"/></linearGradient>')
    css = ("@keyframes bob{0%,49%{transform:translateY(0)}50%,100%{transform:translateY(5px)}}.bob{animation:bob 1.2s infinite}"
           ".seg{animation:fadein .15s steps(1) backwards}"
           "@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}.bounce{animation:bounce .9s ease-in-out infinite}")
    body = panel(W, H) + portrait + "".join(attrs) + "".join(equip) + quest
    title = f"{P['name']} · LV.{level} {P['class']} · now playing {P['now_playing']}"
    return svg(W, H, body, title, css, defs)


def ago(iso, today):
    d = (today - dt.date.fromisoformat(iso[:10])).days
    if d <= 0:
        return "TODAY"
    for unit, n in (("Y", 365), ("MO", 30), ("W", 7), ("D", 1)):
        if d >= n:
            return f"{d // n}{unit} AGO"


def quest(repo, meta, idx, today):
    W, H = 480, 210
    main = meta["type"] == "main"
    col = YELLOW if main else CYAN
    tag = "MAIN QUEST" if main else "SIDE QUEST"
    tw = len(tag) * 10 + 20
    name = repo["name"]
    size = min(24, 440 / (len(name) * 0.6))
    desc = meta.get("blurb") or repo["description"] or "A mysterious quest with no description yet."
    lines = wrap(desc, 440, 16, 3)
    lang = repo["primaryLanguage"] or {"name": "—", "color": DIM}
    upd = f"· {ago(repo['pushedAt'], today)}"
    lx = 40 + len(lang["name"]) * 13 * 0.6 + 10
    body = (
        f'<clipPath id="qc"><rect width="{W}" height="{H}" rx="14"/></clipPath>'
        f'<rect x="1.5" y="1.5" width="{W - 3}" height="{H - 3}" rx="14" fill="url(#pbg)" stroke="{col}" stroke-width="2.5"/>'
        f'<g clip-path="url(#qc)"><rect class="shine" x="-160" y="-20" width="110" height="{H + 40}" fill="url(#shine)" style="animation-delay:{idx * 0.9:.1f}s"/></g>'
        f'<rect x="20" y="18" width="{tw}" height="24" rx="4" fill="{col}"/>' + t(30, 35, tag, "a", 10, INK)
        + (t(20 + tw + 12, 40, "!", "a bounce", 18, YELLOW) if main else "")
        + t(W - 20, 37, f"★ {repo['stargazerCount']}", "a", 13, YELLOW, "end")
        + t(20, 80, name, "b", round(size, 1), TEXT)
        + "".join(t(20, 112 + i * 25, ln, "c", 16, "#cfc8f2") for i, ln in enumerate(lines))
        + f'<circle cx="26" cy="{H - 26}" r="6" fill="{lang["color"]}"/>' + t(40, H - 21, lang["name"], "b", 13, TEXT)
        + t(lx, H - 21, upd, "a", 9, DIM)
        + (t(W - 20, H - 21, "▶ PLAY", "a blink", 10, PINK, "end") if repo.get("homepageUrl") else ""))
    defs = ('<linearGradient id="shine" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset=".5" stop-color="#fff" stop-opacity=".12"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    css = ("@keyframes shine{0%{transform:translateX(0) skewX(-20deg)}35%,100%{transform:translateX(760px) skewX(-20deg)}}"
           ".shine{animation:shine 6s ease-in-out infinite;transform-box:fill-box}"
           "@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}.bounce{animation:bounce .9s ease-in-out infinite}")
    return svg(W, H, body, f"{tag}: {name} — {desc}", css, defs, fonts=("PxA", "PxB"))


def stats(s, created):
    W, H = 1000, 400
    rows = [("TOTAL CONTRIBS", s["total"]), ("LAST 365 DAYS", s["recent"]), ("LONGEST STREAK", s["longest"]),
            ("CURRENT STREAK", s["current"]), ("STARS EARNED", s["stars"]), ("REPOS FORGED", s["repos"])]
    cols = [YELLOW, ORANGE, PINK, PURPLE, CYAN, LIME]
    ranks = ["1ST", "2ND", "3RD", "4TH", "5TH", "6TH"]
    out = [t(40, 58, "RANK", "a", 12, DIM), t(150, 58, "NAME", "a", 12, DIM), t(580, 58, "SCORE", "a", 12, DIM, "end"),
           f'<line x1="40" x2="580" y1="72" y2="72" stroke="{LINE}" stroke-width="2"/>']
    for i, ((name, val), c) in enumerate(zip(rows, cols)):
        y = 108 + i * 42
        g = t(40, y, ranks[i], "a", 16, c) + t(150, y, name, "a", 13, c) + t(580, y, f"{val:06d}", "a", 18, c, "end")
        if name == "CURRENT STREAK" and val and val == s["longest"]:
            g += t(150 + len(name) * 13 + 12, y, "NEW!", "a blink", 9, PINK)
        out.append(f'<g class="in" style="animation-delay:{0.2 + i * 0.22:.2f}s">{g}</g>')
    out += [t(40, 372, f"PLAYER SINCE {created:%Y.%m.%d}", "a", 10, DIM), t(580, 372, "INSERT COIN", "a blink", 10, PINK, "end")]

    lx, lw = 630, 330
    langs = s["langs"]
    top = langs[:6]
    if len(langs) > 6:
        top = langs[:5] + [("Other", sum(x[1] for x in langs[5:]), DIM)]
    total = sum(x[1] for x in langs) or 1
    out += [t(lx, 58, "LANGUAGES", "a", 12, DIM), f'<clipPath id="lb"><rect x="{lx}" y="76" width="{lw}" height="14" rx="4"/></clipPath>']
    bx, seg = lx, []
    for n, sz, c in top:
        w = lw * sz / total
        seg.append(f'<rect x="{bx:.1f}" y="76" width="{w + 0.5:.1f}" height="14" fill="{c}"/>')
        bx += w
    out.append(f'<g clip-path="url(#lb)" class="grow">{"".join(seg)}</g>')
    peak = top[0][1] if top else 1
    for i, (n, sz, c) in enumerate(top):
        y = 128 + i * 40
        out.append(f'<rect x="{lx}" y="{y - 12}" width="12" height="12" fill="{c}"/>' + t(lx + 22, y, n[:14], "b", 15, TEXT)
                   + f'<rect x="{lx + 176}" y="{y - 9}" width="100" height="8" rx="2" fill="{LINE}"/>'
                   f'<rect x="{lx + 176}" y="{y - 9}" width="{100 * sz / peak:.1f}" height="8" rx="2" fill="{c}" class="grow" style="animation-delay:{0.4 + i * 0.1:.1f}s"/>'
                   + t(lx + lw, y, f"{100 * sz / total:.1f}%", "b", 14, DIM, "end"))
    body = panel(W, H) + "".join(out)
    title = ", ".join(f"{n.lower()}: {v}" for n, v in rows)
    return svg(W, H, body, "High scores — " + title, fonts=("PxA", "PxB"))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "static"
    if mode == "static":
        out = ROOT / "assets"
        files = {"hero.svg": hero(), "library.svg": library(), "loadout.svg": loadout(), "footer.svg": footer()}
        for i, (slug, title) in enumerate([("player", "PLAYER 1"), ("quests", "QUEST LOG"), ("library", "GAME LIBRARY"),
                                           ("scores", "HIGH SCORES"), ("arcade", "ARCADE"), ("loadout", "LOADOUT")], 1):
            files[f"h-{slug}.svg"] = header(i, title)
    else:
        out = Path(sys.argv[2] if len(sys.argv) > 2 else "dist")
        u = fetch("--gh" in sys.argv)
        today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
        created = dt.date.fromisoformat(u["createdAt"][:10])
        repos = {r["name"]: r for r in u["repositories"]["nodes"]}
        files = {"player.svg": player(created, today), "stats.svg": stats(summarize(u, today), created)}
        for i, q in enumerate(P["quests"]):
            if q["repo"] in repos:
                files[f"quest-{q['repo'].lower()}.svg"] = quest(repos[q["repo"]], q, i, today)
            else:
                print(f"warning: quest repo {q['repo']} not found or not public", file=sys.stderr)
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out / name).write_text(content)
        print(f"{out / name}  {len(content) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
