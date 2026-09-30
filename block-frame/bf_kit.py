# -*- coding: utf-8 -*-
"""bf_kit: kit of parts for the block-frame assembler. Every part is built from its variant key alone
(e.g. 'tube_r24_l1180_c3', 'hub_m21_r24', 'pperf_w1100_h1000_t12_p75'), so the layout only has to name parts.
Units: metres. Conventions (local frame):
  tube/sleeve/stube  : axis = +X, centred
  hub                : centred, sockets along +-X/+-Y/+-Z by bit mask (bit0 +x, 1 -x, 2 +y, 3 -y, 4 +z, 5 -z)
  panels             : width X, height Y, thickness/normal Z (+Z = outward), centred
  clip               : X along the tube, Y towards the panel centre, Z outward, origin on the tube axis
  clampsw            : lower tube along X (z=-r), upper tube rotated by a degrees about Z (z=+r)
  bolt               : origin under the head, +Z = head side (outward)
  foot               : origin on the ground, +Y up (top of the cup at y = h)
  stair              : X width, Z run (-l/2..l/2), Y rise 0..h ; ladder: X width, Y 0..h
"""
import math
import re
import bf_mesh as bm
from bf_mesh import Mesh, box, cyl, prism, hexbolt, annular_sector, hex_poly, rot_x, rot_y, rot_z, m_vec, v_norm, v_cross, PI

PAL = {'steel': (0.66, 0.68, 0.72), 'dark': (0.20, 0.21, 0.24), 'orange': (0.96, 0.40, 0.08), 'teal': (0.06, 0.62, 0.66),
       'cyan': (0.10, 0.78, 0.95), 'blue': (0.14, 0.28, 0.95), 'green': (0.28, 0.85, 0.25), 'red': (0.92, 0.14, 0.10),
       'yellow': (0.96, 0.80, 0.10), 'magenta': (0.86, 0.22, 0.66), 'purple': (0.55, 0.22, 0.82), 'cream': (0.86, 0.85, 0.74),
       'white': (0.93, 0.93, 0.93), 'grey': (0.58, 0.58, 0.60), 'lime': (0.55, 0.85, 0.15)}
CID = ['steel', 'dark', 'orange', 'teal', 'cyan', 'blue', 'green', 'red', 'yellow', 'magenta', 'purple', 'cream', 'white', 'grey', 'lime']


def cid(name):
    return CID.index(name)


def col(f, default):
    return PAL[CID[f['c']]] if 'c' in f else PAL[default]


def parse(key):
    parts = key.split('_')
    f = {}
    for p in parts[1:]:
        m = re.match(r'^([a-z]+)(\d+)$', p)
        if m:
            f[m.group(1)] = int(m.group(2))
    return parts[0], f


def frame_from_z(z):
    z = v_norm(z)
    a = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 1.0, 0.0)
    x = v_norm(v_cross(a, z))
    y = v_cross(z, x)
    return bm.m_from_axes(x, y, z)


DIRS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]


# ----------------------------------------------------------------------------- frame parts
def b_tube(f):
    return cyl(f['r'] / 1000.0, f['l'] / 1000.0, seg=10, col=col(f, 'steel'), axis='x')


def b_stube(f):
    w = f['w'] / 1000.0
    return box(f['l'] / 1000.0, w, w, col(f, 'teal'), bev=w * 0.12)


def b_hub(f):
    r = f['r'] / 1000.0
    mask = f['m']
    h = 1.35 * r
    val = bin(mask).count('1')
    core = {1: 'yellow', 2: 'yellow', 3: 'blue', 4: 'green', 5: 'red', 6: 'magenta'}[min(6, max(1, val))]
    m = Mesh()
    m.add(box(2 * h, 2 * h, 2 * h, PAL[core], bev=0.32 * h))
    for bit, d in enumerate(DIRS):
        if not (mask >> bit) & 1:
            continue
        L = 2.4 * r
        axis = 'x' if d[0] else 'y' if d[1] else 'z'
        sgn = d[0] + d[1] + d[2]
        m.add(cyl(1.22 * r, L, seg=10, col=PAL['steel'], axis=axis), None, tuple(c * (h + L / 2.0) for c in d))
        m.add(cyl(1.36 * r, 0.32 * r, seg=10, col=PAL['dark'], axis=axis), None, tuple(c * (h + L - 0.16 * r) for c in d))
        perp = (0.0, 1.0, 0.0) if axis == 'x' else (0.0, 0.0, 1.0) if axis == 'y' else (1.0, 0.0, 0.0)
        R = frame_from_z(perp)
        pos = tuple(d[i] * (h + L * 0.5) + perp[i] * 1.2 * r for i in range(3))
        m.add(hexbolt(0.0065, 0.012, PAL['steel'], PAL['dark']), R, pos)
    return m


def b_sleeve(f):
    r = f['r'] / 1000.0
    m = Mesh()
    c = col(f, 'yellow')
    m.add(cyl(1.32 * r, 5.0 * r, seg=12, col=c, axis='x'))
    for sx in (-1, 1):
        m.add(cyl(1.42 * r, 0.5 * r, seg=12, col=PAL['dark'], axis='x'), None, (sx * 2.3 * r, 0.0, 0.0))
    for sx in (-1, 1):
        m.add(hexbolt(0.0065, 0.014, PAL['steel'], PAL['dark']), bm.rot_x(-PI / 2), (sx * 1.1 * r, 1.3 * r, 0.0))
    return m


def b_foot(f):
    r = f['r'] / 1000.0
    h = f['h'] / 1000.0
    m = Mesh()
    m.add(box(0.15, 0.007, 0.15, PAL['dark'], bev=0.003), None, (0.0, 0.0035, 0.0))
    rod_top = h - 0.055
    m.add(cyl(0.0085, rod_top - 0.007, seg=8, col=PAL['steel'], axis='y'), None, (0.0, 0.007 + (rod_top - 0.007) / 2.0, 0.0))
    m.add(prism(hex_poly(0.026), 0.0, 0.013, PAL['steel']), bm.rot_x(-PI / 2), (0.0, 0.02, 0.0))
    m.add(cyl(1.3 * r, 0.06, seg=12, col=PAL['orange'], axis='y'), None, (0.0, h - 0.03, 0.0))
    return m


def b_clampsw(f):
    r = f['r'] / 1000.0
    a = math.radians(f.get('a', 90))
    m = Mesh()
    orange, steel, dark = PAL['orange'], PAL['steel'], PAL['dark']
    m.add(cyl(1.34 * r, 3.6 * r, seg=12, col=orange, axis='x'), None, (0.0, 0.0, -r))
    up = Mesh()
    up.add(cyl(1.34 * r, 3.6 * r, seg=12, col=orange, axis='x'))
    for sy in (-1, 1):
        up.add(box(3.0 * r, 0.7 * r, 0.7 * r, orange, bev=0.15 * r), None, (0.0, sy * 1.5 * r, 0.0))
    up.add(box(2.2 * r, 2.6 * r, 0.6 * r, orange, bev=0.12 * r), None, (0.0, 0.0, -r * 1.05))
    m.add(up, bm.rot_z(a), (0.0, 0.0, r))
    Rz = bm.rot_z(a)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = m_vec(Rz, (sx * 1.0 * r, sy * 1.5 * r, 0.0))
            m.add(hexbolt(0.0075, 0.014, steel, dark), None, (p[0], p[1], r + 0.35 * r))
    return m


def b_clip(f):
    r = f['r'] / 1000.0
    t = f['t'] / 1000.0
    m = Mesh()
    steel, dark = PAL['steel'], PAL['dark']
    m.add(annular_sector(r + 0.001, r + 0.005, 0.0, PI, 8, -0.022, 0.022, dark))
    top_z = r + 0.005
    m.add(box(0.044, 0.058, 0.004, steel, bev=0.001), None, (0.0, 0.029, top_z - 0.002))
    leg_h = top_z - t / 2.0
    m.add(box(0.044, 0.004, leg_h, steel, bev=0.001), None, (0.0, 0.058, t / 2.0 + leg_h / 2.0))
    m.add(box(0.044, 0.030, 0.004, steel, bev=0.001), None, (0.0, 0.075, t / 2.0 + 0.002))
    m.add(hexbolt(0.006, 0.014, steel, dark), None, (0.0, 0.078, t / 2.0 + 0.004))
    m.add(hexbolt(0.006, 0.014, steel, dark), None, (0.0, 0.028, top_z))
    return m


def b_bolt(f):
    d = f['m'] / 1000.0
    L = f['l'] / 1000.0
    c = col(f, 'steel')
    return hexbolt(d, L, c, PAL['dark'])


# ----------------------------------------------------------------------------- panels
OFFS8 = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


def plate_tiles(w, h, t, pitch, kind, col_):
    """Perforated plate: every tile has a hole; tile ring = 8 outer lattice points bridged to 8 hole points."""
    nx = max(1, int(round(w / pitch)))
    ny = max(1, int(round(h / pitch)))
    tw, th = w / nx, h / ny
    m = Mesh()
    lat = {}

    def L(ix, iy):
        k = (ix, iy)
        if k not in lat:
            x = -w / 2.0 + ix * tw / 2.0
            y = -h / 2.0 + iy * th / 2.0
            lat[k] = (m.pt((x, y, t / 2.0)), m.pt((x, y, -t / 2.0)))
        return lat[k]

    hs = 0.30 if kind == 'oct' else 0.0
    for j in range(ny):
        for i in range(nx):
            cx = -w / 2.0 + (i + 0.5) * tw
            cy = -h / 2.0 + (j + 0.5) * th
            outer = [L(2 * i + 1 + dx, 2 * j + 1 + dy) for dx, dy in OFFS8]
            inner_f, inner_b = [], []
            for k, (dx, dy) in enumerate(OFFS8):
                if kind == 'oct':
                    rh = hs * min(tw, th)
                    ang = k * PI / 4.0
                    px, py = cx + rh * math.cos(ang), cy + rh * math.sin(ang)
                else:
                    a, b = 0.30 * tw, 0.36 * th
                    px, py = cx + dx * a, cy + dy * b
                inner_f.append(m.pt((px, py, t / 2.0)))
                inner_b.append(m.pt((px, py, -t / 2.0)))
            for k in range(8):
                k2 = (k + 1) % 8
                m.face((outer[k][0], outer[k2][0], inner_f[k2], inner_f[k]), col_)
                m.face((outer[k][1], outer[k2][1], inner_b[k2], inner_b[k]), col_)
                m.face((inner_f[k], inner_f[k2], inner_b[k2], inner_b[k]), col_)
    border = ([(ix, 0) for ix in range(0, 2 * nx + 1)] + [(2 * nx, iy) for iy in range(1, 2 * ny + 1)] +
              [(ix, 2 * ny) for ix in range(2 * nx - 1, -1, -1)] + [(0, iy) for iy in range(2 * ny - 1, 0, -1)])
    for k in range(len(border)):
        a = L(*border[k])
        b = L(*border[(k + 1) % len(border)])
        m.face((a[0], b[0], b[1], a[1]), col_)
    return m.orient()


def frame_bars(w, h, t, bar, col_):
    m = Mesh()
    tt = t * 1.6
    m.add(box(w, bar, tt, col_, bev=0.002), None, (0.0, h / 2.0 - bar / 2.0, 0.0))
    m.add(box(w, bar, tt, col_, bev=0.002), None, (0.0, -h / 2.0 + bar / 2.0, 0.0))
    m.add(box(bar, h - 2 * bar, tt, col_, bev=0.002), None, (w / 2.0 - bar / 2.0, 0.0, 0.0))
    m.add(box(bar, h - 2 * bar, tt, col_, bev=0.002), None, (-w / 2.0 + bar / 2.0, 0.0, 0.0))
    return m


def b_pperf(f):
    w, h, t = f['w'] / 1000.0, f['h'] / 1000.0, f['t'] / 1000.0
    c = col(f, 'magenta')
    m = plate_tiles(w, h, t, f.get('p', 75) / 1000.0, 'oct', c)
    m.add(frame_bars(w, h, t, 0.02, PAL['dark']))
    return m


def b_pmesh(f):
    w, h, t = f['w'] / 1000.0, f['h'] / 1000.0, f['t'] / 1000.0
    c = col(f, 'lime')
    m = plate_tiles(w, h, t, f.get('p', 60) / 1000.0, 'rect', c)
    m.add(frame_bars(w, h, t, 0.02, PAL['dark']))
    return m


def b_pround(f):
    w, h, t = f['w'] / 1000.0, f['h'] / 1000.0, f['t'] / 1000.0
    ox, oy = (f.get('u', 1000) - 1000) / 1000.0, (f.get('v', 1000) - 1000) / 1000.0
    R = f.get('rr', 300) / 1000.0
    c = col(f, 'purple')
    m = Mesh()
    angs = set(2.0 * PI * k / 32 for k in range(32))
    for sx in (-1, 1):
        for sy in (-1, 1):
            angs.add(math.atan2(sy * h / 2.0 - oy, sx * w / 2.0 - ox) % (2.0 * PI))
    angs = sorted(angs)
    rows = [0.0, 0.34, 0.68, 1.0]
    outer_pts = []
    for a in angs:
        ux, uy = math.cos(a), math.sin(a)
        ts = []
        if abs(ux) > 1e-9:
            ts.append(((w / 2.0 if ux > 0 else -w / 2.0) - ox) / ux)
        if abs(uy) > 1e-9:
            ts.append(((h / 2.0 if uy > 0 else -h / 2.0) - oy) / uy)
        d = min(ts)
        outer_pts.append((ox + d * ux, oy + d * uy, ox + R * ux, oy + R * uy))
    n = len(angs)
    ringf, ringb = [], []
    for fr in rows:
        rf, rb = [], []
        for (X, Y, ix_, iy_) in outer_pts:
            x = ix_ + (X - ix_) * fr
            y = iy_ + (Y - iy_) * fr
            rf.append(m.pt((x, y, t / 2.0)))
            rb.append(m.pt((x, y, -t / 2.0)))
        ringf.append(rf)
        ringb.append(rb)
    for r_ in range(len(rows) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            m.face((ringf[r_][k], ringf[r_][k2], ringf[r_ + 1][k2], ringf[r_ + 1][k]), c)
            m.face((ringb[r_][k], ringb[r_][k2], ringb[r_ + 1][k2], ringb[r_ + 1][k]), c)
    for k in range(n):
        k2 = (k + 1) % n
        m.face((ringf[0][k], ringf[0][k2], ringb[0][k2], ringb[0][k]), c)
        m.face((ringf[-1][k], ringf[-1][k2], ringb[-1][k2], ringb[-1][k]), c)
    m.orient()
    m.add(frame_bars(w, h, t, 0.02, PAL['dark']))
    return m


def b_plouver(f):
    w, h, t = f['w'] / 1000.0, f['h'] / 1000.0, f['t'] / 1000.0
    c = col(f, 'teal')
    m = Mesh()
    m.add(frame_bars(w, h, t, 0.025, PAL['dark']))
    n = max(3, int(round(h / 0.07)))
    pitch = (h - 0.05) / n
    for i in range(n):
        y = -h / 2.0 + 0.025 + (i + 0.5) * pitch
        slat = box(w - 0.05, pitch * 0.85, 0.006, c, bev=0.0015)
        m.add(slat, bm.rot_x(math.radians(-32)), (0.0, y, 0.0))
    return m


def b_psolid(f):
    w, h, t = f['w'] / 1000.0, f['h'] / 1000.0, f['t'] / 1000.0
    c = col(f, 'cream')
    m = Mesh()
    m.add(box(w, h, t, c, bev=0.003))
    m.add(box(w - 0.09, h - 0.09, t * 1.5, c, bev=0.004), None, (0.0, 0.0, 0.0))
    m.add(frame_bars(w, h, t, 0.02, PAL['dark']))
    return m


# ----------------------------------------------------------------------------- stairs, ladders
def b_stair(f):
    w, l, h = f['w'] / 1000.0, f['l'] / 1000.0, f['h'] / 1000.0
    m = Mesh()
    ang = math.atan2(h, l)
    Ls = math.hypot(h, l)
    for sx in (-1, 1):
        m.add(box(0.035, 0.14, Ls, PAL['white'], bev=0.004), bm.rot_x(-ang), (sx * (w / 2.0 - 0.02), h / 2.0, 0.0))
    n = max(2, int(round(h / 0.19)))
    for i in range(n):
        y = (i + 1) * h / n - 0.0125
        z = -l / 2.0 + (i + 0.5) * l / n
        m.add(box(w - 0.07, 0.025, l / n * 0.92, PAL['cream'], bev=0.003), None, (0.0, y, z))
    return m


def b_ladder(f):
    w, h = f['w'] / 1000.0, f['h'] / 1000.0
    m = Mesh()
    for sx in (-1, 1):
        m.add(cyl(0.016, h, seg=8, col=PAL['white'], axis='y'), None, (sx * w / 2.0, h / 2.0, 0.0))
    n = max(2, int(h / 0.28))
    for i in range(n):
        y = (i + 0.7) * h / n
        m.add(cyl(0.012, w, seg=8, col=PAL['steel'], axis='x'), None, (0.0, y, 0.0))
    return m


BUILDERS = {'tube': b_tube, 'stube': b_stube, 'hub': b_hub, 'sleeve': b_sleeve, 'foot': b_foot, 'clampsw': b_clampsw,
            'clip': b_clip, 'bolt': b_bolt, 'pperf': b_pperf, 'pmesh': b_pmesh, 'pround': b_pround, 'plouver': b_plouver,
            'psolid': b_psolid, 'stair': b_stair, 'ladder': b_ladder}


def build(key):
    kind, f = parse(key)
    m = BUILDERS[kind](f)
    m.orient()
    return m


if __name__ == '__main__':
    tests = ['tube_r24_l1100_c4', 'stube_w40_l1100', 'hub_m21_r24', 'hub_m63_r24', 'sleeve_r24', 'foot_r24_h100', 'clampsw_r24_a35',
             'clip_r24_t12', 'bolt_m8_l25', 'pperf_w1100_h1000_t12_p75', 'pmesh_w1100_h1000_t12_p60',
             'pround_w1100_h1000_t12_u1080_v1000_rr300', 'plouver_w1100_h1000_t12', 'psolid_w1100_h1000_t12',
             'stair_w1000_l1000_h1200', 'ladder_w450_h1200']
    for k in tests:
        m = build(k)
        E = {}
        for fc in m.F:
            for i in range(len(fc)):
                e = (fc[i], fc[(i + 1) % len(fc)])
                E[e] = E.get(e, 0) + 1
        bad = sum(1 for e, n in E.items() if n != 1 or (e[1], e[0]) not in E)
        print('%-44s pts %5d faces %5d bad-edges %d bbox %s' % (k, len(m.P), len(m.F), bad, tuple(round(b - a, 3) for a, b in zip(*m.bbox()))))
