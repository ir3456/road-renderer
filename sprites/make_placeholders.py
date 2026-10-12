"""Writes chunky placeholder sprites + manifest into sprites/placeholder/. Run: python3 sprites/make_placeholders.py"""
import json, os, struct, zlib

OUT = os.path.join(os.path.dirname(__file__), 'placeholder')
os.makedirs(OUT, exist_ok=True)

def png(name, w, h, px):
    raw = b''.join(b'\x00' + b''.join(bytes(px(x, y) or (0, 0, 0, 0)) for x in range(w)) for y in range(h))
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
    open(os.path.join(OUT, name + '.png'), 'wb').write(data)

def pine(x, y):
    if 40 <= y < 48 and 10 <= x < 14: return (96, 64, 32, 255)
    for top, base, half in ((0, 16, 7), (10, 28, 10), (22, 40, 12)):
        if top <= y < base:
            hw = (y - top) / (base - top) * half
            if abs(x - 11.5) <= hw: return (24, 112, 48, 255) if x < 12 else (16, 88, 40, 255)
    return None

def tree(x, y):
    if 30 <= y < 40 and 13 <= x < 19: return (104, 72, 40, 255)
    dx, dy = x - 15.5, y - 16
    if dx * dx / 240 + dy * dy / 230 <= 1: return (48, 152, 56, 255) if dx + dy < 0 else (32, 120, 40, 255)
    return None

def bush(x, y):
    dx, dy = x - 9.5, y - 11
    if dx * dx / 90 + dy * dy / 110 <= 1 and y < 12: return (64, 160, 64, 255) if dy < -3 else (40, 128, 48, 255)
    return None

def rock(x, y):
    dx, dy = x - 11.5, y - 13
    if dx * dx / 130 + dy * dy / 150 <= 1 and y < 14: return (168, 160, 152, 255) if dx + dy < -4 else (120, 112, 104, 255)
    return None

def sign(x, y):
    if y >= 12 and 5 <= x < 7: return (200, 200, 200, 255)
    if y < 12:
        if x in (0, 11) or y in (0, 11): return (0, 0, 0, 255)
        return (248, 208, 32, 255)
    return None

def stopsign(x, y):
    if y >= 12 and 5 <= x < 7: return (160, 160, 160, 255)
    if y < 12:
        dx, dy = abs(x - 5.5), abs(y - 5.5)
        if dx + dy <= 8.5: return (255, 255, 255, 255) if dx >= 5 or dy >= 5 or dx + dy > 7.5 else (216, 32, 32, 255)
    return None

def signal(x, y):
    if y >= 14 and 4 <= x < 6: return (90, 90, 90, 255)
    if y < 14 and 1 <= x < 9:
        if 3 <= x < 7 and 2 <= y < 5: return (240, 40, 40, 255)
        if 3 <= x < 7 and 6 <= y < 9: return (240, 200, 40, 255)
        if 3 <= x < 7 and 10 <= y < 13: return (40, 200, 60, 255)
        return (30, 30, 30, 255)
    return None

def building(x, y):
    if x < 50:
        if x == 0 or y in (8, 63): return (40, 40, 48, 255)
        if y < 8: return None
        if (y - 8) % 10 in (3, 4, 5, 6) and x % 8 in (2, 3, 4, 5) and y < 56: return (240, 232, 160, 255)
        if 52 <= y < 63 and 20 <= x < 28: return (72, 48, 32, 255)
        return (176, 120, 88, 255)
    top = 8 - (x - 50) * 0.5
    if y < top: return None
    if x in (50, 63) or y == 63 or y < top + 1: return (40, 40, 48, 255)
    if (y - 8) % 10 in (3, 4, 5, 6) and (x - 50) % 8 in (3, 4, 5, 6) and y < 56: return (208, 196, 128, 255)
    return (128, 84, 60, 255)

def cliff(x, y):
    if y < 40:
        band = (y // 6) % 2
        if x % 11 == (y // 6 * 3) % 11 and y % 6 != 0: return (72, 60, 52, 255)
        return (136, 116, 100, 255) if band else (120, 102, 88, 255)
    return None

def cabin(x, y):
    if x < 24:
        if y < 10:
            if abs(x - 11.5) <= y * 1.5 + 1: return (120, 56, 40, 255) if y % 2 else (104, 48, 36, 255)
            return None
        if y < 28:
            if 19 <= y < 27 and 9 <= x < 14: return (64, 40, 24, 255)
            if 13 <= y < 18 and (3 <= x < 8 or 16 <= x < 21): return (240, 232, 160, 255)
            return (168, 120, 72, 255) if (y // 3) % 2 else (152, 108, 64, 255)
        return None
    top = 10 - (x - 24) * 0.5
    if y < top or y >= 28: return None
    if y < top + 2: return (104, 48, 36, 255)
    if x == 31 or y == 27: return (64, 40, 24, 255)
    if 13 <= y < 18 and 26 <= x < 30: return (208, 196, 128, 255)
    return (136, 96, 56, 255) if (y // 3) % 2 else (120, 84, 48, 255)

def rider_fn(tint):
    def f(x, y):
        if 18 <= y < 24 and (4 <= x < 7 or 9 <= x < 12): return (24, 24, 24, tint[3])
        if 9 <= y < 18 and 5 <= x < 11: return tint
        if 5 <= y < 9 and 6 <= x < 10: return (240, 200, 160, tint[3])
        if 2 <= y < 5 and 5 <= x < 11: return (232, 48, 48, tint[3])
        if 16 <= y < 18 and 3 <= x < 13: return (160, 160, 160, tint[3])
        return None
    return f

def rocktile(x, y):
    n = (x * 73856093 ^ y * 19349663) % 11
    if (x * 3 + y * 5) % 13 == 0 or (x * 7 + y * 11) % 17 == 0: return (72, 60, 52, 255)
    return (108, 88, 72, 255) if n < 3 else (132, 110, 92, 255)

def bank_fn(flip):
    def f(x, y):
        u = (31 - x if flip else x) / 31
        top = 24 - int(24 * u ** 0.7)
        if y < top: return None
        if y - top < 2: return (48, 120, 56, 255)
        return (96, 80, 68, 255) if (x * 5 + y * 3) % 7 == 0 else (124, 100, 84, 255)
    return f

sprites = {
    'rocktile': (32, 32, rocktile, 4),
    'bankL':    (32, 24, bank_fn(True), 4),
    'bankR':    (32, 24, bank_fn(False), 4),
    'cliff':    (32, 40, cliff,    4),
    'cabin':    (32, 28, cabin,    5, True),
    'rider':    (16, 24, rider_fn((40, 88, 200, 255)), 1.7),
    'ghost':    (16, 24, rider_fn((200, 220, 255, 150)), 1.7),
    'pine':     (24, 48, pine,     14),
    'tree':     (32, 40, tree,     10),
    'bush':     (20, 12, bush,     2),
    'rock':     (24, 14, rock,     3),
    'sign':     (12, 32, sign,     3.5),
    'stopsign': (12, 36, stopsign, 2.4),
    'signal':   (10, 48, signal,   4.5),
    'building': (64, 64, building, 14, True),
}
manifest = {}
for name, (w, h, fn, meters, *face) in sprites.items():
    png(name, w, h, fn)
    manifest[name] = {'file': name + '.png', 'anchorX': w / 2, 'anchorY': h, 'meters': meters, **({'faceRoad': True} if face else {})}
json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)
print('wrote', list(sprites))
