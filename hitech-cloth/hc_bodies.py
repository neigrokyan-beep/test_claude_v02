# -*- coding: utf-8 -*-
"""hc_bodies: mannequin (collider), knee/shin armour, belt pouch. Quads only, closed, Y-up, cm, front = -Z.
Uses wm_geo (sweep, Mesh, validate). Add the folder with wm_geo.py to sys.path first."""
import math
import wm_geo as g

Mesh = g.Mesh


def solidify(pts_out, quads, pts_in, name=""):
    """Closed thick shell from an open quad surface: outer + inner (reversed) + boundary walls."""
    n = len(pts_out)
    m = Mesh(list(pts_out) + list(pts_in), [], name)
    for q in quads:
        m.quads.append(q)
    for q in quads:
        m.quads.append((q[3] + n, q[2] + n, q[1] + n, q[0] + n))
    edges = {}
    for q in quads:
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]
            edges[(a, b)] = True
    for (a, b) in list(edges):
        if (b, a) not in edges:
            m.quads.append((b, a, a + n, b + n))       # wall: q_out->p_out, p_out->p_in, p_in->q_in
    return g.orient_outward(m)


def shell_strip(name, nr, nc, y0, y1, R, half_angle, thick, cx=0.0, cz=0.0, bulge=0.0, bulge_pow=1.0, taper=None):
    """Plate wrapped around a vertical axis at (cx, cz), centred on the front (-Z). Rows along y, cols across the angle.
    R(t): radius at row t (0 = y0 .. 1 = y1); half_angle(t) in degrees; bulge: dome height, vanishing at the border."""
    outer, inner = [], []
    for j in range(nr + 1):
        t = j / float(nr)
        y = y0 + (y1 - y0) * t
        r0 = R(t) if callable(R) else R
        ha = math.radians(half_angle(t) if callable(half_angle) else half_angle)
        for i in range(nc + 1):
            u = -1.0 + 2.0 * i / nc
            a = u * ha
            dome = bulge * (math.sin(math.pi * t) ** bulge_pow) * (math.cos(0.5 * math.pi * u) ** bulge_pow)
            r = r0 + dome
            outer.append((cx + r * math.sin(a), y, cz - r * math.cos(a)))
            inner.append((cx + (r - thick) * math.sin(a), y, cz - (r - thick) * math.cos(a)))
    quads = []
    W = nc + 1
    for j in range(nr):
        for i in range(nc):
            quads.append((j * W + i, j * W + i + 1, (j + 1) * W + i + 1, (j + 1) * W + i))
    return solidify(outer, quads, inner, name)


def limb(path, w, h, k, wfn, name, corner=0.9):
    return g.sweep(path, w, h, k=k, corner=corner, width_fn=wfn, name=name)


def lerp_fn(keys):
    """keys [(t, a, b)] -> function t -> (a, b) piecewise linear."""
    def f(t):
        for s in range(len(keys) - 1):
            t0, a0, b0 = keys[s]
            t1, a1, b1 = keys[s + 1]
            if t <= t1 or s == len(keys) - 2:
                u = 0.0 if t1 == t0 else max(0.0, min(1.0, (t - t0) / (t1 - t0)))
                return (a0 + (a1 - a0) * u, b0 + (b1 - b0) * u)
    return f


def mannequin():
    """Simple A-pose body collider, 175 cm, facing -Z. Returns {name: Mesh}."""
    out = {}
    # torso: hips y=88 .. neck base y=148 (width along X, depth along Z)
    torso_path = [(0, 88 + 60.0 * s / 10.0, 0) for s in range(11)]
    tw = lerp_fn([(0.0, 1.0, 1.0), (0.3, 0.84, 0.9), (0.62, 1.0, 1.0), (0.9, 1.02, 0.9), (1.0, 0.5, 0.55)])
    out['Mannequin_Torso'] = limb(torso_path, 36.0, 22.0, 6, tw, 'Mannequin_Torso', 0.8)
    out['Mannequin_Neck'] = limb([(0, 146 + 6.0 * s / 3.0, -0.5) for s in range(4)], 11.0, 11.0, 3, lambda t: (1.0, 1.0), 'Mannequin_Neck')
    hp = [(0, 154 + 21.0 * s / 6.0, -1.0) for s in range(7)]
    out['Mannequin_Head'] = limb(hp, 16.0, 20.0, 4, lerp_fn([(0.0, 0.45, 0.45), (0.15, 0.85, 0.85), (0.5, 1.0, 1.0), (0.85, 0.85, 0.85), (1.0, 0.35, 0.35)]), 'Mannequin_Head')
    for side, sx in (('L', 1.0), ('R', -1.0)):
        ang = math.radians(28.0)          # A-pose arm
        pts = []
        for s in range(9):
            L = 62.0 * s / 8.0
            pts.append((sx * (19.0 + L * math.sin(ang)), 143.0 - L * math.cos(ang), 0.0))
        out['Mannequin_Arm' + side] = limb(pts, 9.0, 9.0, 4, lerp_fn([(0.0, 1.0, 1.0), (0.5, 0.72, 0.72), (1.0, 0.5, 0.55)]), 'Mannequin_Arm' + side)
        leg = [(sx * (9.5 - 2.0 * s / 12.0), 90.0 - 88.0 * s / 12.0, 0.0) for s in range(13)]
        out['Mannequin_Leg' + side] = limb(leg, 19.0, 19.0, 5, lerp_fn([(0.0, 1.0, 1.0), (0.4, 0.68, 0.68), (0.55, 0.62, 0.62), (0.8, 0.5, 0.5), (1.0, 0.4, 0.45)]), 'Mannequin_Leg' + side)
        foot = [(sx * 7.5, 3.5, 4.0 - 2.4 * s / 4.0) for s in range(5)]
        out['Mannequin_Foot' + side] = limb(foot, 9.0, 7.0, 3, lerp_fn([(0.0, 0.9, 1.0), (1.0, 0.9, 1.0)]), 'Mannequin_Foot' + side, 0.7)
    return out


def armour():
    """Knee pads + shin plates for both legs, fitted on the mannequin legs (leg axis x = +-7.7, front = -Z)."""
    out = {}
    for side, sx in (('L', 1.0), ('R', -1.0)):
        cx = sx * 8.0
        out['Knee_' + side] = shell_strip('Knee_' + side, 8, 10, 38.0, 60.0, 10.5, 62, 1.0, cx, 0.0, bulge=3.2, bulge_pow=0.8)
        out['KneeRim_' + side] = shell_strip('KneeRim_' + side, 8, 10, 35.0, 63.0, 9.4, 68, 0.8, cx, 0.0, bulge=1.0)
        out['ShinUpper_' + side] = shell_strip('ShinUpper_' + side, 10, 8, 20.0, 37.0, lambda t: 8.6 - 1.2 * t, lambda t: 66 - 8 * t, 0.9, cx, 0.4, bulge=1.6, bulge_pow=0.6)
        out['ShinLower_' + side] = shell_strip('ShinLower_' + side, 8, 8, 9.0, 19.0, lambda t: 7.6 - 0.8 * t, lambda t: 60 - 10 * t, 0.9, cx, 0.5, bulge=1.2, bulge_pow=0.6)
        rib = [(cx, 36.0 - 26.0 * s / 8.0, -(10.4 - 3.0 * s / 8.0)) for s in range(9)]
        out['ShinRib_' + side] = g.sweep(rib, 1.6, 1.4, k=2, corner=0.6, name='ShinRib_' + side)
    return out


def pouch():
    """Belt pouch (vertical holster pocket, 11 x 19 x 4.6): body, raised lid, rim, back loops, side D-ring, zip pull."""
    out = {}
    H, W, D = 19.0, 11.0, 4.6
    body_path = [(0, H * s / 8.0, 0) for s in range(9)]
    out['Pouch_Body'] = g.sweep(body_path, W, D, k=6, corner=0.28, width_fn=lerp_fn([(0.0, 0.9, 0.85), (0.08, 1.0, 1.0), (0.92, 1.0, 1.0), (1.0, 0.9, 0.85)]), name='Pouch_Body')
    lid_path = [(0, 0.8 + (H - 1.6) * s / 6.0, -D * 0.5 + 0.1) for s in range(7)]
    out['Pouch_Lid'] = g.sweep(lid_path, W * 0.86, 1.4, k=6, corner=0.3, name='Pouch_Lid')
    rim = [(0, 0.3 + (H - 0.6) * s / 8.0, -D * 0.5 + 0.35) for s in range(9)]
    out['Pouch_Rim'] = g.sweep(rim, W * 1.0, 0.9, k=6, corner=0.4, name='Pouch_Rim')
    for tag, y in (('Top', H - 3.0), ('Bot', 3.0)):
        out['Pouch_Loop' + tag] = g.sweep([(0, y, D * 0.5 + 0.1 + 0.2 * s / 2.0) for s in range(3)], 3.0, 0.7, k=3, corner=0.3, name='Pouch_Loop' + tag)
    ring = g.arc_path(0.0, 0.0, 1.4, 0.0, 2 * math.pi * 0.9, 14)
    out['Pouch_DRing'] = g.sweep([(W * 0.5 + 0.5 + p[0] * 0.0, H * 0.72 + p[1], -0.2 + p[0]) for p in ring], 0.5, 0.5, k=2, corner=0.9, name='Pouch_DRing')
    out['Pouch_ZipPull'] = g.sweep([(2.2, H * 0.96 - 0.6 * s / 4.0, -D * 0.5 - 0.5) for s in range(5)], 0.9, 0.5, k=3, corner=0.6, name='Pouch_ZipPull')
    return out


if __name__ == '__main__':
    for grp in (mannequin(), armour(), pouch()):
        for n, m in grp.items():
            v = g.validate(m)
            print('%-18s pts %5d quads %5d  %s' % (n, len(m.pts), len(m.quads), {k: v[k] for k in v if k in ('closed', 'max_valence', 'volume', 'euler', 'degenerate', 'coincident')}))
