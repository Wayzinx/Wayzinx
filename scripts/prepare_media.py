"""One-off media prep (run locally, results are committed).

    curl -L -o avatar.png "https://avatars.githubusercontent.com/u/46066700?s=240"
    uv run --with pillow --with fonttools --with brotli python scripts/prepare_media.py <fonts_dir> avatar.png

- assets/fonts/*.woff2   : ASCII subsets of Press Start 2P / JetBrains Mono (renamed, OFL)
- assets/covers/*.jpg    : square 300px game covers for the library cartridge shelf
- assets/sprite.json     : the GitHub avatar pixelated into a 40x40 palette sprite
- assets/icons.json      : simple-icons paths for the loadout inventory
"""
import json, re, subprocess, sys
from collections import Counter
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASCII = "".join(chr(c) for c in range(0x20, 0x7F))


def make_font(src, out, family, extra, wght=None):
    font = TTFont(src)
    if wght is not None:
        font = instancer.instantiateVariableFont(font, {"wght": wght})
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []
    opts.name_IDs = []
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(text=ASCII + extra)
    sub.subset(font)
    name = font["name"]
    for nid in (1, 4, 6, 16):
        name.setName(family if nid != 6 else family.replace(" ", ""), nid, 3, 1, 0x409)
    font.flavor = "woff2"
    font.save(out)
    print(out, Path(out).stat().st_size, "bytes")


def cover(src, out, zoom=1.0):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    side = int(min(w, h) / zoom)
    left, top = (w - side) // 2, (h - side) // 2
    im = im.crop((left, top, left + side, top + side)).resize((300, 300), Image.LANCZOS)
    im.save(out, quality=80, optimize=True, progressive=True)
    print(out, Path(out).stat().st_size, "bytes")


SPRITE_PAL = {"o": "#2b3354", "b": "#a8c0ee", "s": "#7f98cf", "w": "#ffffff", "p": "#f5a3b5",
              "y": "#f6c955", "r": "#e8964a", "t": "#b6e3e8", "m": "#f0b8d8"}


def sprite(src, out, n=40):
    """Map to a fixed palette, then majority-vote 8x8 blocks (outline wins at >=22%)."""
    rgb = {k: tuple(int(v[i : i + 2], 16) for i in (1, 3, 5)) for k, v in SPRITE_PAL.items()}
    im = Image.open(src).convert("RGB").resize((n * 8, n * 8), Image.LANCZOS)
    px = im.load()
    near = lambda c: min(rgb, key=lambda k: sum((a - b) ** 2 for a, b in zip(c, rgb[k])))
    lab = [[near(px[x, y]) for x in range(n * 8)] for y in range(n * 8)]
    rows = []
    for by in range(n):
        row = ""
        for bx in range(n):
            cnt = Counter(lab[by * 8 + j][bx * 8 + i] for j in range(8) for i in range(8))
            row += "o" if cnt["o"] >= 14 else cnt.most_common(1)[0][0]
        rows.append(row)
    # white reachable from the border is background → transparent ('.')
    clear, stack = set(), [(x, y) for x in range(n) for y in (0, n - 1)] + [(x, y) for y in range(n) for x in (0, n - 1)]
    while stack:
        x, y = stack.pop()
        if 0 <= x < n and 0 <= y < n and (x, y) not in clear and rows[y][x] == "w":
            clear.add((x, y))
            stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    rows = ["".join("." if (x, y) in clear else rows[y][x] for x in range(n)) for y in range(n)]
    Path(out).write_text(json.dumps({"palette": SPRITE_PAL, "rows": rows}, indent=1))
    print(out)


def icons(out, slugs):
    paths = {}
    for slug in slugs:
        svg = subprocess.run(["curl", "-sfL", f"https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{slug}.svg"],
                             check=True, capture_output=True, text=True).stdout
        paths[slug] = re.search(r'<path d="([^"]+)"', svg).group(1)
    Path(out).write_text(json.dumps(paths, indent=1))
    print(out, len(paths), "icons")


if __name__ == "__main__":
    fonts = Path(sys.argv[1])  # holds PressStart2P.ttf + JetBrainsMono.ttf (google/fonts, OFL)
    make_font(fonts / "PressStart2P.ttf", ROOT / "assets/fonts/arcade.woff2", "Arcade Sub", "▶★☆♥•·—…→←↑↓°♪©")
    for w in (500, 800):
        make_font(fonts / "JetBrainsMono.ttf", ROOT / f"assets/fonts/mono-{w}.woff2", f"Mono Sub {w}", "▶►▸█▓▒░■□●•·—…→←↑↓°©", wght=w)
    for name, src, zoom in [
        ("zelda", "zelda.jpeg", 1.0),
        ("deltaforce", "deltaforce.jpg", 1.0),
        ("pokemon", "pikacu.jpeg", 1.0),
        ("lol", "jinx.jpg", 1.0),
        ("mario", "mario.jpg", 1.7),
    ]:
        cover(ROOT / src, ROOT / f"assets/covers/{name}.jpg", zoom)
    sprite(sys.argv[2], ROOT / "assets/sprite.json")
    icons(ROOT / "assets/icons.json", ["python", "typescript", "javascript", "swift", "selenium", "jenkins",
                                       "git", "githubactions", "claude", "openai", "deepseek", "modelcontextprotocol"])
