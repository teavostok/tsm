#!/usr/bin/env python3
"""
mpris-glow.py — Extract album art colors for SwayNC glow effects.

Watches MPRIS via playerctl, extracts dominant colors from album art,
and writes @keyframes CSS for a Spotify-style glow on the MPRIS widget.
"""

import sys
import os
import subprocess
import urllib.request
import urllib.parse
import json
import io
import colorsys
import time
from pathlib import Path
from collections import Counter

# Configuration
CONFIG_DIR  = Path.home() / ".config" / "swaync"
CSS_OUT     = CONFIG_DIR / "mpris-colors.css"
STYLE_CSS   = CONFIG_DIR / "style.css"

# Must match animation-duration values in style.css
ORBIT_SECS  = 7      # widget orbit cycle
ART_SECS    = 3      # album art pulse cycle
ART_DELAY   = -1.4   # phase offset (seconds) so art & widget don't peak together

# Color extraction settings
N_COLORS    = 4      # number of dominant colors to extract
MIN_BRIGHT  = 0.07   # luma floor — skip near-black pixels
MAX_BRIGHT  = 0.95   # luma ceiling — skip near-white pixels
MIN_SAT     = 0.08   # HSV saturation floor — skip near-grey pixels
SAT_BOOST   = 1.35   # saturation multiplier for vivid glow
VAL_BOOST   = 1.06   # value multiplier (slight brightness lift)
MIN_DIST    = 45     # min perceptual distance between accepted colors

POLL_SECS   = 2      # fallback polling interval (watch mode)

# Fallback: Apple Tahoe System colors — used when artwork unavailable
FALLBACK = [
    (50,  215,  75),   # System Green
    ( 0,  122, 255),   # System Blue
    (191,  90, 242),   # System Purple
]


# Subprocess helpers

def _run(*args):
    return subprocess.run(list(args), capture_output=True, text=True)


def get_art_url(player=None):
    cmd = ["playerctl"]
    if player:
        cmd += ["-p", player]
    cmd += ["metadata", "mpris:artUrl"]
    r = _run(*cmd)
    url = r.stdout.strip()
    return url if url else None


def get_track_meta(player=None):
    cmd = ["playerctl"]
    if player:
        cmd += ["-p", player]
    r = _run(*(cmd + ["metadata", "xesam:artist"]))
    artist = r.stdout.strip()
    r = _run(*(cmd + ["metadata", "xesam:title"]))
    title = r.stdout.strip()
    r = _run(*(cmd + ["metadata", "xesam:album"]))
    album = r.stdout.strip()
    return artist, title, album


def search_art_url(artist, title, album=""):
    if not artist and not title:
        return None
    try:
        parts = [artist, title, album] if album else [artist, title]
        query = urllib.parse.quote(" ".join(p for p in parts if p))
        req = urllib.request.Request(
            f"https://itunes.apple.com/search?term={query}&limit=5&entity=song",
            headers={"User-Agent": "mpris-glow/1.0"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read())
        artist_lower = artist.lower().strip()
        title_lower = title.lower().strip()
        best = None
        for result in data.get("results", []):
            ra = result.get("artistName", "").lower().strip()
            rt = result.get("trackName", "").lower().strip()
            art = result.get("artworkUrl100", "")
            if not art:
                continue
            if ra == artist_lower and rt == title_lower:
                return art.replace("100x100", "600x600")
            if ra == artist_lower and title_lower in rt:
                best = art
        if best:
            return best.replace("100x100", "600x600")
        for result in data.get("results", []):
            art = result.get("artworkUrl100", "")
            if not art:
                continue
            ra = result.get("artistName", "").lower().strip()
            if ra == artist_lower:
                return art.replace("100x100", "600x600")
        for result in data.get("results", []):
            art = result.get("artworkUrl100", "")
            if art:
                return art.replace("100x100", "600x600")
    except Exception as exc:
        print(f"  iTunes search failed ({exc!r})")
    return None


def search_art_deezer(artist, title):
    if not artist and not title:
        return None
    try:
        query = urllib.parse.quote(f"{artist} {title}")
        req = urllib.request.Request(
            f"https://api.deezer.com/search?q={query}&limit=3",
            headers={"User-Agent": "mpris-glow/1.0"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read())
        for result in data.get("data", []):
            art = result.get("album", {}).get("cover_big", "")
            if art:
                return art
    except Exception as exc:
        print(f"  Deezer search failed ({exc!r})")
    return None


def get_players():
    r = _run("playerctl", "-l")
    if r.returncode != 0:
        return []
    return [p for p in r.stdout.strip().splitlines() if p]


def swaync_reload():
    _run("swaync-client", "--reload-css")


# Image fetching

def fetch_image(url: str):
    """
    Download or open the album art and return a PIL Image (RGB).
    Handles both file:// and https:// URLs.
    Returns None on any error.
    """
    try:
        from PIL import Image
    except ImportError:
        print(
            "⚠  Pillow not found — install it with:  pip install pillow\n"
            "   Using fallback Apple System palette instead."
        )
        return None

    try:
        if url.startswith("file://"):
            path = urllib.parse.unquote(url[7:])
            return Image.open(path).convert("RGB")

        req = urllib.request.Request(
            url, headers={"User-Agent": "mpris-glow/1.0 (SwayNC theme helper)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read()
        return Image.open(io.BytesIO(raw)).convert("RGB")

    except Exception as exc:
        print(f"⚠  Could not fetch artwork ({exc!r}) — using fallback.")
        return None


# Color extraction

def _luma(r, g, b):
    """BT.601 perceptual luma, 0–1."""
    return (r * 0.299 + g * 0.587 + b * 0.114) / 255.0


def _perceptual_dist(c1, c2):
    """Weighted Euclidean distance in RGB space (perceptual coefficients)."""
    dr = (c1[0] - c2[0]) * 0.299
    dg = (c1[1] - c2[1]) * 0.587
    db = (c1[2] - c2[2]) * 0.114
    return (dr ** 2 + dg ** 2 + db ** 2) ** 0.5


def extract_colors(img, n: int = N_COLORS):
    """
    Return up to n perceptually distinct, vibrant colors from img.

    Algorithm:
      1. Shrink to 80×80 to suppress noise and speed up quantization.
      2. Median-cut quantize to 32 palette entries.
      3. Walk palette by frequency; accept entries that are:
           • bright enough (MIN_BRIGHT < luma < MAX_BRIGHT)
           • saturated enough (HSV sat > MIN_SAT)
           • perceptually distant from already-accepted colors (> MIN_DIST)
      4. Pad with FALLBACK colors if fewer than n were accepted.
    """
    from PIL import Image

    thumb = img.resize((80, 80), Image.LANCZOS)
    quantized = thumb.quantize(colors=32, method=2)   # method 2 = FASTOCTREE
    pal = quantized.getpalette()                       # flat [R,G,B, …]
    try:
        counts = Counter(quantized.get_flattened_data())
    except AttributeError:
        counts = Counter(list(quantized.getdata()))

    accepted = []
    for idx, _ in counts.most_common():
        r, g, b = pal[idx * 3], pal[idx * 3 + 1], pal[idx * 3 + 2]
        luma = _luma(r, g, b)
        _, sat, _ = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

        if not (MIN_BRIGHT < luma < MAX_BRIGHT):
            continue
        if sat < MIN_SAT:
            continue
        if any(_perceptual_dist((r, g, b), c) < MIN_DIST for c in accepted):
            continue

        accepted.append((r, g, b))
        if len(accepted) >= n:
            break

    # Pad with fallback colors while maintaining distance constraint
    for fb in FALLBACK:
        if len(accepted) >= n:
            break
        if all(_perceptual_dist(fb, c) >= MIN_DIST for c in accepted):
            accepted.append(fb)

    # Last resort: just append whatever fallbacks are needed
    for fb in FALLBACK:
        if len(accepted) >= n:
            break
        accepted.append(fb)

    return accepted[:n]


def boost_color(r, g, b):
    """Boost saturation and slightly raise value for a vivid glow effect."""
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    s = min(1.0, s * SAT_BOOST)
    v = min(1.0, v * VAL_BOOST)
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return int(r2 * 255), int(g2 * 255), int(b2 * 255)


# CSS generation

def _struct_shadows():
    """Structural shadows present in every keyframe."""
    return (
        "0 0 0 0.5px rgba(0,0,0,0.42), "
        "0 4px 16px rgba(0,0,0,0.28), "
        "inset 0 1px 0 rgba(255,255,255,0.12)"
    )


def _orbit_frame(node_a_xy, node_b_xy, color_a, color_b, bloom_color):
    """Build the box-shadow value for one @keyframes stop."""
    ax, ay = node_a_xy
    bx, by = node_b_xy
    r1, g1, b1 = color_a
    r2, g2, b2 = color_b
    rb, gb, bb = bloom_color
    return (
        f"{_struct_shadows()}, "
        f"{ax}px {ay}px 38px 5px rgba({r1},{g1},{b1},0.54), "
        f"{bx}px {by}px 38px 5px rgba({r2},{g2},{b2},0.44), "
        f"0 0 80px 22px rgba({rb},{gb},{bb},0.13)"
    )


def build_orbit_keyframes(colors):
    """
    Two light nodes orbit the card in opposite directions.

    Node A travels:  TL → TR → BR → BL → TL
    Node B travels:  BR → BL → TL → TR → BR
    """
    boosted = [boost_color(*c) for c in colors]
    a, b, d = boosted[0], boosted[1], boosted[2]

    stops = {
        # percent : (node_a_pos,   node_b_pos,   color_a, color_b, bloom)
        "0%, 100%": ((-15, -12), ( 15,  13), a, b, a),
        "25%":      (( 15, -12), (-15,  13), b, d, b),
        "50%":      (( 15,  13), (-15, -12), d, a, d),
        "75%":      ((-15,  13), ( 15, -12), a, d, a),
    }

    lines = ["@keyframes mpris-orbit {"]
    for stop, (na, nb, ca, cb, bl) in stops.items():
        shadow = _orbit_frame(na, nb, ca, cb, bl)
        lines.append(f"  {stop} {{\n    box-shadow:\n      {shadow};\n  }}")
    lines.append("}")
    return "\n".join(lines)


def build_art_keyframes(colors):
    """
    Album art breathes between a subtle and a vivid glow.
    Primary color sets the hue; negative animation-delay creates phase offset.
    """
    r, g, b = boost_color(*colors[0]) if colors else FALLBACK[0]
    return f"""\
@keyframes mpris-art-glow {{
  0%, 100% {{
    box-shadow:
      0 4px 12px rgba(0,0,0,0.48),
      0 1px  3px rgba(0,0,0,0.24),
      0 0 12px  2px rgba({r},{g},{b},0.16);
  }}
  50% {{
    box-shadow:
      0 4px 12px rgba(0,0,0,0.48),
      0 1px  3px rgba(0,0,0,0.24),
      0 0 32px 10px rgba({r},{g},{b},0.34);
  }}
}}"""


def write_css(colors):
    """Write glow keyframes into style.css and mpris-colors.css."""
    hex_tags = " · ".join(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in colors)
    orbit = build_orbit_keyframes(colors)
    art = build_art_keyframes(colors)
    glow_css = f"{orbit}\n\n\n{art}\n"

    # Write backup file
    header = (
        "/* ─────────────────────────────────────────────────────────────\n"
        f"   mpris-colors.css — auto-generated by mpris-glow.py\n"
        f"   Extracted palette: {hex_tags}\n"
        "   Manual edits will be overwritten on the next track change.\n"
        "   ───────────────────────────────────────────────────────────── */\n\n"
    )
    CSS_OUT.parent.mkdir(parents=True, exist_ok=True)
    CSS_OUT.write_text(header + glow_css)

    # Write inline into style.css between glow markers
    style = STYLE_CSS.read_text()
    marker_start = "/* glow-start */"
    marker_end = "/* glow-end */"
    start_idx = style.find(marker_start)
    end_idx = style.find(marker_end)
    if start_idx != -1 and end_idx != -1:
        before = style[: start_idx + len(marker_start)]
        after = style[end_idx:]
        STYLE_CSS.write_text(before + "\n" + glow_css + after)


# Main logic

def update(image_path=None):
    """
    Read current player artwork → extract colors → write CSS → reload swaync.
    Safe to call repeatedly; no-ops gracefully if nothing is playing.
    If image_path is given, use that local file directly (from zen-mpris-host).
    """
    url = None
    if image_path:
        # Use the provided local image file directly
        img = fetch_image("file://" + image_path)
        if img is not None:
            colors = extract_colors(img, n=N_COLORS)
            write_css(colors)
            swaync_reload()
            hex_tags = " · ".join(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in colors)
            print(f"✓  Glow updated (from file)  →  {hex_tags}")
            return
        # Fall through to normal logic if file can't be read
        print(f"  Could not read image file {image_path}, trying playerctl...")

    url = get_art_url()

    if not url:
        # Try every active player before giving up
        for player in get_players():
            url = get_art_url(player)
            if url:
                break

    if not url:
        # No MPRIS art — search by artist + title + album
        artist, title, album = get_track_meta()
        if artist or title:
            print(f"  Searching iTunes for: {artist} — {title}")
            url = search_art_url(artist, title, album)
        if not url and (artist or title):
            print(f"  Searching Deezer for: {artist} — {title}")
            url = search_art_deezer(artist, title)

    if not url:
        print("  No artwork available — writing fallback palette.")
        write_css(FALLBACK)
        swaync_reload()
        return

    img = fetch_image(url)
    if img is None:
        write_css(FALLBACK)
        swaync_reload()
        return

    colors = extract_colors(img, n=N_COLORS)
    write_css(colors)
    swaync_reload()

    hex_tags = " · ".join(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in colors)
    print(f"✓  Glow updated  →  {hex_tags}")


def watch():
    """
    Daemon mode: poll every few seconds for track changes and call update().
    Uses polling for cross-player compatibility (Firefox/Zen don't emit --follow signals).
    """
    print("mpris-glow  •  watching for track changes  (Ctrl-C to stop)")

    # Do an initial update immediately
    update()

    last_track = object()
    while True:
        try:
            track = _run("playerctl", "metadata", "mpris:trackid").stdout.strip()
            if track != last_track:
                last_track = track
                update()
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        time.sleep(POLL_SECS)


# Entry point

if __name__ == "__main__":
    args = set(sys.argv[1:])

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    # --image <path>: use a local image file for color extraction (from zen-mpris-host)
    image_path = None
    if "--image" in args:
        idx = sys.argv.index("--image") + 1
        if idx < len(sys.argv):
            image_path = sys.argv[idx]

    if image_path:
        update(image_path)
    elif "--watch" in args:
        watch()
    else:
        update()