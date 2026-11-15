#!/usr/bin/env python3
"""make.fun ai-excited-01 entry.

Draws ONE image procedurally (pure Python stdlib, no network):
a giant koi fish leaping through a blazing golden ring at sunset,
over Mount Fuji, cherry blossoms swirling, sun bursting, "WOW!"
in chunky letters. Deterministic: two runs are byte-identical.

Writes /output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png).
PNG, 1024x1024, stdlib zlib+struct encoding.
"""

import binascii
import math
import os
import random
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- canvas
buf = bytearray(W * H * 3)


def px(x, y):
    return (y * W + x) * 3


def put(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = px(x, y)
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b


def blend(x, y, r, g, b, a):
    """Blend colour over existing pixel, a in 0..1."""
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        i = px(x, y)
        if a >= 1.0:
            buf[i] = r
            buf[i + 1] = g
            buf[i + 2] = b
        else:
            buf[i] = int(r * a + buf[i] * (1.0 - a))
            buf[i + 1] = int(g * a + buf[i + 1] * (1.0 - a))
            buf[i + 2] = int(b * a + buf[i + 2] * (1.0 - a))


def hline(y, x0, x1, r, g, b):
    if y < 0 or y >= H:
        return
    x0 = max(0, x0)
    x1 = min(W - 1, x1)
    if x1 < x0:
        return
    i = px(x0, y)
    n = x1 - x0 + 1
    buf[i:i + n * 3] = bytes((r, g, b)) * n


def hline_a(y, x0, x1, r, g, b, a):
    if y < 0 or y >= H or a <= 0.0:
        return
    x0 = max(0, x0)
    x1 = min(W - 1, x1)
    for x in range(x0, x1 + 1):
        blend(x, y, r, g, b, a)


def lerp(a, b, t):
    return int(a + (b - a) * t)


def mix(c0, c1, t):
    return (lerp(c0[0], c1[0], t), lerp(c0[1], c1[1], t), lerp(c0[2], c1[2], t))


# ---------------------------------------------------------------- shapes
def disc(cx, cy, rad, col, alpha=1.0):
    """Filled circle, optionally translucent."""
    rad = int(rad)
    if rad <= 0:
        return
    r, g, b = col
    for y in range(cy - rad, cy + rad + 1):
        dy = y - cy
        dx = int(math.sqrt(max(0, rad * rad - dy * dy)))
        if alpha >= 1.0:
            hline(y, cx - dx, cx + dx, r, g, b)
        else:
            hline_a(y, cx - dx, cx + dx, r, g, b, alpha)


def ellipse(cx, cy, rx, ry, col, alpha=1.0):
    rx = int(rx)
    ry = int(ry)
    if rx <= 0 or ry <= 0:
        return
    r, g, b = col
    for y in range(cy - ry, cy + ry + 1):
        dy = (y - cy) / ry
        dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
        if alpha >= 1.0:
            hline(y, cx - dx, cx + dx, r, g, b)
        else:
            hline_a(y, cx - dx, cx + dx, r, g, b, alpha)


def ring(cx, cy, rad, thick, col, alpha=1.0, a0=None, a1=None):
    """Circle outline; optional angle range (radians, atan2(dy, dx))."""
    r, g, b = col
    outer = rad + thick / 2.0
    inner = rad - thick / 2.0
    x0 = int(cx - outer) - 1
    x1 = int(cx + outer) + 1
    y0 = int(cy - outer) - 1
    y1 = int(cy + outer) + 1
    for y in range(max(0, y0), min(H, y1 + 1)):
        for x in range(max(0, x0), min(W, x1 + 1)):
            d = math.hypot(x - cx, y - cy)
            if inner <= d <= outer:
                if a0 is not None:
                    ang = math.atan2(y - cy, x - cx)
                    lo, hi = a0, a1
                    ok = lo <= ang <= hi if lo <= hi else (ang >= lo or ang <= hi)
                    if not ok:
                        continue
                blend(x, y, r, g, b, alpha)


def poly(points, col, alpha=1.0):
    """Scanline-filled polygon."""
    if len(points) < 3:
        return
    r, g, b = col
    ys = [p[1] for p in points]
    y0, y1 = int(min(ys)), int(max(ys))
    n = len(points)
    for y in range(max(0, y0), min(H, y1 + 1)):
        xs = []
        for i in range(n):
            x1, y1p = points[i]
            x2, y2p = points[(i + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                t = (y - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        if len(xs) >= 2:
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa, xb = int(xs[k]), int(xs[k + 1])
                if alpha >= 1.0:
                    hline(y, xa, xb, r, g, b)
                else:
                    hline_a(y, xa, xb, r, g, b, alpha)


def thick_line(x0, y0, x1, y1, w, col, alpha=1.0):
    steps = int(math.hypot(x1 - x0, y1 - y0)) + 1
    for i in range(steps + 1):
        t = i / max(1, steps)
        disc(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t),
             max(1, w // 2), col, alpha)


# ---------------------------------------------------------------- text
FONT = {
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", ".#.#.", ".#.#."),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
}


def draw_text(text, x, y, scale, col, outline=None):
    cx = x
    for ch in text:
        glyph = FONT.get(ch)
        if glyph is None:
            cx += 6 * scale
            continue
        if outline is not None:
            for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3),
                           (-3, -3), (3, -3), (-3, 3), (3, 3)):
                _glyph(glyph, cx + ox, y + oy, scale, outline)
        _glyph(glyph, cx, y, scale, col)
        cx += 6 * scale


def _glyph(glyph, x, y, scale, col):
    r, g, b = col
    for row, line in enumerate(glyph):
        for c, ch in enumerate(line):
            if ch == "#":
                for dy in range(scale):
                    hline(y + row * scale + dy,
                          x + c * scale, x + c * scale + scale - 1, r, g, b)


# ---------------------------------------------------------------- scene
def sky():
    top = (16, 12, 58)
    mid = (148, 38, 112)
    hor = (255, 148, 66)
    for y in range(0, 840):
        if y < 430:
            c = mix(top, mid, y / 430.0)
        else:
            c = mix(mid, hor, (y - 430) / 410.0)
        hline(y, 0, W - 1, *c)


def stars_and_birds(rng):
    # sparkles high in the sky
    for _ in range(46):
        x = rng.randint(20, 1000)
        y = rng.randint(15, 380)
        s = rng.choice((3, 4, 5, 7))
        a = rng.choice((0.5, 0.7, 0.9))
        col = rng.choice(((255, 255, 255), (255, 230, 150), (255, 200, 220)))
        hline_a(y, x - s, x + s, *col, a)
        for yy in range(y - s, y + s + 1):
            blend(x, yy, *col, a)
    # birds: little dark "v" strokes
    for _ in range(7):
        x = rng.randint(60, 950)
        y = rng.randint(90, 330)
        s = rng.randint(9, 16)
        thick_line(x - s, y - s // 2, x, y + s // 3, 3, (30, 16, 60))
        thick_line(x, y + s // 3, x + s, y - s // 2, 3, (30, 16, 60))


def sun():
    cx, cy = 792, 228
    # glow: wide soft rings
    disc(cx, cy, 210, (255, 150, 70), 0.16)
    disc(cx, cy, 160, (255, 170, 80), 0.22)
    disc(cx, cy, 125, (255, 200, 110), 0.45)
    # horizontal light streaks
    for dy, ln, a in ((-58, 330, 0.35), (-20, 420, 0.30),
                      (30, 380, 0.30), (72, 300, 0.35)):
        hline_a(cy + dy, cx - ln, cx + ln, 255, 220, 150, a)
        hline_a(cy + dy + 3, cx - ln + 40, cx + ln - 40, 255, 220, 150, a * 0.7)
    # core
    disc(cx, cy, 92, (255, 238, 185))
    disc(cx, cy, 78, (255, 244, 205))
    # rays
    for k in range(12):
        ang = k * math.pi / 6.0
        x0 = cx + int(100 * math.cos(ang))
        y0 = cy + int(100 * math.sin(ang))
        x1 = cx + int(150 * math.cos(ang))
        y1 = cy + int(150 * math.sin(ang))
        thick_line(x0, y0, x1, y1, 7, (255, 214, 130), 0.85)


def fuji():
    # dark silhouette, snow cap, hazy base
    poly([(20, 845), (270, 545), (520, 845)], (36, 30, 84))
    poly([(222, 600), (270, 545), (318, 600), (300, 622),
          (282, 604), (270, 618), (258, 604), (240, 622)],
         (246, 240, 255))
    poly([(20, 845), (520, 845), (520, 800), (20, 800)], (36, 30, 84))
    # low cloud band hugging the mountain
    for cx, cy, rx in ((120, 800, 150), (330, 815, 170), (470, 795, 120)):
        ellipse(cx, cy, rx, 26, (255, 170, 130), 0.30)


def water():
    # deep band with a sine top edge
    for y in range(815, H):
        t = (y - 815) / (H - 815)
        c = mix((44, 96, 190), (12, 30, 96), t)
        hline(y, 0, W - 1, *c)
    # wave edge: lighter crest line
    for x in range(W):
        y = 818 + int(9 * math.sin(x / 55.0) + 5 * math.sin(x / 23.0))
        for dy in range(0, 4):
            blend(x, y + dy, 150, 210, 255, 0.55 - dy * 0.12)
    # foam streaks + reflections under the koi
    rng = random.Random(7)
    for _ in range(60):
        x = rng.randint(10, 1010)
        y = rng.randint(830, 1010)
        ln = rng.randint(14, 60)
        a = rng.uniform(0.10, 0.35)
        hline_a(y, x, x + ln, 190, 225, 255, a)
    for x0, ln, a in ((330, 260, 0.20), (430, 200, 0.16), (560, 240, 0.20)):
        for yy in range(840, 1000, 7):
            hline_a(yy, x0 + (yy % 13), x0 + ln - (yy % 11), 255, 150, 70, a)


def ring_and_koi(rng):
    rcx, rcy, rad = 600, 470, 238
    # --- back of the golden ring (upper arc, behind the fish)
    ring(rcx, rcy, rad + 34, 26, (255, 190, 60), 0.22)
    ring(rcx, rcy, rad + 18, 18, (255, 205, 80), 0.45)
    ring(rcx, rcy, rad, 26, (255, 205, 70), 1.0, a0=math.pi, a1=2 * math.pi)
    ring(rcx, rcy, rad, 10, (255, 240, 160), 1.0, a0=math.pi, a1=2 * math.pi)

    # --- koi spine: quadratic bezier, tail low-left -> head high-right
    p0 = (285.0, 800.0)
    p1 = (430.0, 285.0)
    p2 = (855.0, 325.0)

    def bez(t):
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        dx = 2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0])
        dy = 2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1])
        return x, y, dx, dy

    pts = [bez(t / 60.0) for t in range(61)]

    def radius(t):
        return 34.0 + 46.0 * (math.sin(math.pi * (0.10 + 0.80 * t)) ** 0.9)

    # dark outline pass
    for i, (x, y, _dx, _dy) in enumerate(pts):
        t = i / 60.0
        disc(int(x), int(y), radius(t) + 5, (40, 18, 66))
    # orange body
    for i, (x, y, _dx, _dy) in enumerate(pts):
        t = i / 60.0
        disc(int(x), int(y), radius(t), (255, 112, 32))
    # white belly along the lower edge
    for i, (x, y, dx, dy) in enumerate(pts):
        t = i / 60.0
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L  # normal; +y is down, so this is lower side
        r = radius(t)
        disc(int(x + nx * r * 0.42), int(y + ny * r * 0.42),
             r * 0.52, (255, 246, 228))
    # red patches on the back
    for t, rr in ((0.30, 0.52), (0.52, 0.60), (0.72, 0.46), (0.86, 0.34)):
        x, y, dx, dy = bez(t)
        L = math.hypot(dx, dy) or 1.0
        nx, ny = dy / L, -dx / L  # upper side
        r = radius(t)
        disc(int(x + nx * r * 0.30), int(y + ny * r * 0.30),
             r * rr, (222, 32, 32))
        disc(int(x + nx * r * 0.30), int(y + ny * r * 0.30),
             r * rr * 0.55, (245, 60, 40))
    # dorsal fin (top, mid-body)
    x, y, dx, dy = bez(0.48)
    L = math.hypot(dx, dy) or 1.0
    nx, ny = dy / L, -dx / L
    poly([(int(x - dx / L * 70), int(y - dy / L * 70)),
          (int(x + nx * 95), int(y + ny * 95)),
          (int(x + dx / L * 60), int(y + dy / L * 60))],
         (255, 140, 60), 0.92)
    # pectoral fin near the head (lower side)
    x, y, dx, dy = bez(0.82)
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    poly([(int(x), int(y)),
          (int(x + nx * 78 + dx / L * 40), int(y + ny * 78 + dy / L * 40)),
          (int(x + dx / L * 95), int(y + dy / L * 95))],
         (255, 150, 70), 0.9)
    # flowing tail at the tail end
    tx, ty, tdx, tdy = bez(0.0)
    TL = math.hypot(tdx, tdy) or 1.0
    ux, uy = tdx / TL, tdy / TL
    vx, vy = -uy, ux
    poly([(int(tx), int(ty)),
          (int(tx - ux * 150 + vx * 70), int(ty - uy * 150 + vy * 70)),
          (int(tx - ux * 185 + vx * 8), int(ty - uy * 185 + vy * 8)),
          (int(tx - ux * 120 - vx * 30), int(ty - uy * 120 - vy * 30))],
         (255, 130, 50), 0.85)
    poly([(int(tx), int(ty)),
          (int(tx - ux * 130 - vx * 65), int(ty - uy * 130 - vy * 65)),
          (int(tx - ux * 175 - vx * 10), int(ty - uy * 175 - vy * 10)),
          (int(tx - ux * 105 + vx * 25), int(ty - uy * 105 + vy * 25))],
         (255, 170, 90), 0.8)
    # head: eye + smile
    hx, hy, hdx, hdy = bez(1.0)
    HL = math.hypot(hdx, hdy) or 1.0
    ex = int(hx - hdy / HL * 26 - hdx / HL * 6)
    ey = int(hy + hdx / HL * 26 - hdy / HL * 6)
    disc(ex, ey, 11, (20, 8, 30))
    disc(ex - 3, ey - 3, 4, (255, 255, 255))
    # whiskers
    mx = int(hx + hdx / HL * 34)
    my = int(hy + hdy / HL * 34)
    thick_line(mx, my, mx + 42, my + 26, 3, (255, 220, 180), 0.9)
    thick_line(mx, my + 6, mx + 46, my + 8, 3, (255, 220, 180), 0.9)

    # --- front of the golden ring (lower arc, in front of the fish)
    ring(rcx, rcy, rad, 26, (255, 205, 70), 1.0, a0=0.0, a1=math.pi)
    ring(rcx, rcy, rad, 10, (255, 240, 160), 1.0, a0=0.0, a1=math.pi)
    # sparkle burst where the fish crosses the ring
    for sx, sy, s in ((392, 620, 10), (818, 352, 12), (600, 232, 9)):
        hline(sy, sx - s, sx + s, 255, 240, 170)
        for yy in range(sy - s, sy + s + 1):
            put(sx, yy, 255, 240, 170)


def splash(rng):
    # big splash where the tail leaves the water
    for _ in range(34):
        x = 285 + rng.randint(-90, 90)
        y = 800 + rng.randint(-70, 25)
        r = rng.randint(3, 13)
        disc(x, y, r, (235, 245, 255), rng.uniform(0.5, 0.95))
    # droplets arcing up around the tail
    for _ in range(22):
        x = 250 + rng.randint(-70, 130)
        y = 700 + rng.randint(-60, 90)
        disc(x, y, rng.randint(2, 6), (220, 238, 255), 0.85)
    # ripple rings on the water
    for cx, cy, rx in ((300, 832, 120), (300, 838, 170), (830, 845, 90)):
        ellipse(cx, cy, rx, 13, (220, 240, 255), 0.55)
        ellipse(cx, cy, rx - 12, 9, (44, 96, 190), 1.0)
        ellipse(cx, cy, rx - 24, 6, (220, 240, 255), 0.4)


def petals(rng):
    for _ in range(80):
        x = rng.randint(15, 1005)
        y = rng.randint(15, 950)
        rx = rng.randint(8, 14)
        ry = rng.randint(4, 7)
        col = rng.choice(((255, 170, 205), (255, 125, 175), (255, 195, 220)))
        ellipse(x, y, rx, ry, col, rng.uniform(0.55, 0.95))
        disc(x - rx // 2, y, 2, (255, 255, 255), 0.6)
    # a few fast motion streaks
    for _ in range(8):
        x = rng.randint(40, 980)
        y = rng.randint(60, 800)
        ln = rng.randint(25, 55)
        thick_line(x, y, x + ln, y - ln // 3, 2, (255, 190, 215), 0.5)


def title_text():
    draw_text("WOW!", 64, 62, 16, (255, 255, 255), outline=(22, 10, 56))


# ---------------------------------------------------------------- png
def chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", binascii.crc32(typ + data) & 0xFFFFFFFF)
    return out


def encode_png():
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += buf[y * W * 3:(y + 1) * W * 3]
    idat = zlib.compress(bytes(raw), 6)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


def main():
    rng = random.Random(20261116)
    sky()
    stars_and_birds(rng)
    sun()
    fuji()
    water()
    ring_and_koi(rng)
    splash(rng)
    petals(rng)
    title_text()
    png = encode_png()
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as f:
        f.write(png)
    print("wrote %s (%d bytes)" % (path, len(png)))


if __name__ == "__main__":
    main()
