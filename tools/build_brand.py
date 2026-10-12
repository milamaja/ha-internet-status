#!/usr/bin/env python3
"""Build the integration's brand icons (custom_components/internet_status/brand/).

A globe with a round "online" badge with a check mark in the bottom-right
corner, drawn with plain Python (no image libraries), in two colour sets:

    icon.png / icon@2x.png            light theme
    dark_icon.png / dark_icon@2x.png  dark theme

    python tools/build_brand.py
"""
import math
import pathlib
import struct
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "custom_components" / "internet_status" / "brand"

SIZE = 512  # @2x; the 1x icon is this halved
SAMPLES = 3  # per axis, for anti-aliasing

COLOURS = {
    "light": {"globe": (33, 150, 243), "line": (255, 255, 255), "badge": (67, 160, 71), "check": (255, 255, 255)},
    "dark": {"globe": (100, 181, 246), "line": (38, 50, 56), "badge": (102, 187, 106), "check": (38, 50, 56)},
}

GLOBE, GLOBE_R, LINE = (224, 224), 192, 14
BADGE, BADGE_R, BADGE_GAP = (390, 390), 104, 18


def _on_check(x, y):
    """A check mark inside the badge: two thick strokes."""
    bx, by = BADGE
    strokes = [((bx - 50, by + 2), (bx - 14, by + 38)), ((bx - 14, by + 38), (bx + 52, by - 34))]
    for (x0, y0), (x1, y1) in strokes:
        dx, dy = x1 - x0, y1 - y0
        t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / (dx * dx + dy * dy)))
        if math.hypot(x - (x0 + t * dx), y - (y0 + t * dy)) <= 15:
            return True
    return False


def _colour_at(x, y, c):
    bx, by = BADGE
    d_badge = math.hypot(x - bx, y - by)
    if d_badge <= BADGE_R:
        return (c["check"] if _on_check(x, y) else c["badge"]) + (255,)
    if d_badge <= BADGE_R + BADGE_GAP:
        return (0, 0, 0, 0)
    gx, gy = GLOBE
    dx, dy = x - gx, y - gy
    d = math.hypot(dx, dy)
    if d > GLOBE_R:
        return (0, 0, 0, 0)
    half = LINE / 2
    # Equator and two latitudes.
    for lat in (0, -80, 80):
        if abs(dy - lat) <= half and d < GLOBE_R - 24:
            return c["line"] + (255,)
    # Central meridian and two curved meridians (ellipses).
    if abs(dx) <= half and d < GLOBE_R - 24:
        return c["line"] + (255,)
    for a in (92,):
        if dy * dy < (GLOBE_R - 24) ** 2:
            ex = a * math.sqrt(max(0.0, 1 - (dy / (GLOBE_R - 10)) ** 2))
            if abs(abs(dx) - ex) <= half:
                return c["line"] + (255,)
    # Outline ring.
    if d >= GLOBE_R - LINE - 10 and d <= GLOBE_R - 10:
        return c["line"] + (255,)
    return c["globe"] + (255,)


def render(c):
    rows, step, n = [], 1 / SAMPLES, SAMPLES * SAMPLES
    for py in range(SIZE):
        row = []
        for px in range(SIZE):
            r = g = b = a = 0
            for sy in range(SAMPLES):
                for sx in range(SAMPLES):
                    cr, cg, cb, ca = _colour_at(px + (sx + 0.5) * step, py + (sy + 0.5) * step, c)
                    r += cr * ca
                    g += cg * ca
                    b += cb * ca
                    a += ca
            row.append((r / n, g / n, b / n, a / n))
        rows.append(row)
    return rows


def halve(rows):
    return [
        [tuple(sum(p[i] for p in (rows[y][x], rows[y][x + 1], rows[y + 1][x], rows[y + 1][x + 1])) / 4 for i in range(4))
         for x in range(0, len(rows[0]), 2)]
        for y in range(0, len(rows), 2)
    ]


def write_png(path, rows):
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for r, g, b, a in row:
            raw += bytes((round(r / a), round(g / a), round(b / a), round(a))) if a else b"\0\0\0\0"

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", len(rows[0]), len(rows), 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for theme, colours in COLOURS.items():
        prefix = "" if theme == "light" else "dark_"
        big = render(colours)
        write_png(OUT / f"{prefix}icon@2x.png", big)
        write_png(OUT / f"{prefix}icon.png", halve(big))
        print(f"{theme}: {prefix}icon.png, {prefix}icon@2x.png")


if __name__ == "__main__":
    main()
