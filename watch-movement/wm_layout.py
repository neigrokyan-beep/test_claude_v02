# -*- coding: utf-8 -*-
"""wm_layout: blueprint of a perpetual-calendar style hand-wound movement (original design, generic parts).

build() -> list of part dicts:
  name, group, make (callable -> wm_geo.Mesh, Z-up mm), pos (x, y, z) assembled, rot (deg about Z),
  cyl (r, z0, z1) collision envelope relative to pos or None, parent (name of an assembly or None), mat (material key).
Gear pairs mesh: centre distance = pitch radius sum (module M). check() verifies that nothing else intersects.
Layers (z, mm): plate 0-0.9 | low wheels 1.0-2.1 | upper wheels 2.15-2.5 | bridges 2.9-3.4 | top train 3.5-4.1 |
                calendar plate 4.2-4.6 | date ring / moon disc 4.65-4.95 | dial 5.4-5.75 | crystal 6.4+
"""
import math
import wm_geo as g

M = 0.2  # gear module, mm (big teeth: fewer, clean quads)


def rp(n):
    return M * n / 2.0


def tip(n):
    return M * (n + 2) / 2.0


def polar(cx, cy, d, a):
    a = math.radians(a)
    return (cx + d * math.cos(a), cy + d * math.sin(a))


def mesh_at(c, n1, n2, ang):
    """Position of a wheel with n2 teeth meshing with a wheel n1 at c, in direction ang (deg)."""
    return polar(c[0], c[1], rp(n1) + rp(n2), ang)


# --------------------------------------------------------------------------- mesh factories
def f_wheel(n, thick=0.3, bore=0.25, spokes=0, kind="spur", hub_h=0.0, per=4):
    """Toothed wheel. spokes >= 3 (and n >= 30): open wheel with crossings; otherwise a solid small wheel."""
    t = tip(n)
    if spokes and n >= 30:
        return lambda: g.wheel_open(n, t, thick, spokes=spokes, bore=bore, per_tooth=per, kind=kind, hub_h=hub_h)
    if n >= 30:   # large wheel without spokes: toothed ring + solid web disc on quad grid
        def make():
            ring = g.gear_ring(n, t, thick, None, kind, per)
            r_in = t - 2.2 * (2.0 * t / (n + 2.0)) - max(0.45, 0.14 * t)
            return ring.merged(g.plate(r_in + 0.25, thick * 0.55, m=max(6, int(r_in * 1.2) // 2 * 2)).translate(0, 0, thick * 0.22))
        return make
    return lambda: g.gear(n, t, thick, bore, web_drop=0.0, kind=kind, per_tooth=per, hub_h=hub_h)


def f_barrel(n, height):
    t = tip(n)

    def make():
        ring = g.gear_ring(n, t, height, None, "spur", 4, chamfer=0.05)
        r_in = t - 2.2 * (2.0 * t / (n + 2.0)) - max(0.45, 0.14 * t)
        return ring.merged(g.plate(r_in + 0.3, 0.16, m=12))
    return make


def f_plate(r, th, steps=None, m=12):
    return lambda: g.plate(r, th, steps=steps, m=m)


def f_pinion(n, thick=0.4, bore=0.12):
    t = tip(n)
    r_root = t - 2.2 * (2.0 * t / (n + 2.0))
    hub_r = min(max(bore * 1.6, bore + 0.08), r_root - 0.09)
    return lambda: g.gear(n, t, thick, min(bore, hub_r - 0.06), hub_r=hub_r, per_tooth=4, chamfer=0.02)


def f_arbor(r, length):
    return lambda: g.rod(r, length, m=2, chamfer=0.02)


def f_screw(scale=1.0, length=1.3):
    return lambda: g.screw(0.55 * scale, 0.32 * scale, 0.3 * scale, length * scale, 0.13 * scale, m=(2 if scale < 0.75 else 3))


def f_pin(r=0.14, h=0.8):
    return lambda: g.rod(r, h, m=2, chamfer=0.02)


def f_jewel(scale=1.0):
    return lambda: g.jewel(0.55 * scale, 0.32 * scale, m=3)


def f_annulus(ro, ri, th, seg=96, steps=None, bevel=0.04):
    return lambda: g.annulus(ro, ri, th, seg, bevel=bevel, steps=steps)


def f_disc(r, th, m=4, dome=0.0):
    return lambda: g.disc_solid(r, th, m, dome=dome)


def f_bridge(pts, width, thick, taper=(1.0, 0.8)):
    """Bridge following the smooth curve through pts (list of (x,y)), extended a little past the ends."""
    def make():
        path = _smooth(pts, 5, 1.6)
        return g.bridge_plate([(p[0], p[1], 0.0) for p in path], width, thick, k=2, taper=taper)
    return make


def f_lever(pts, width, thick):
    def make():
        path = _smooth(pts, 4, 0.0)
        return g.bridge_plate([(p[0], p[1], 0.0) for p in path], width, thick, k=1, taper=(1.0, 0.7))
    return make


def _smooth(pts, sub, ext):
    """Catmull-Rom through pts, ends extended by ext (mm) along the end tangents."""
    P = list(pts)
    if ext > 0:
        def unit(a, b):
            d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
            return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
        u0 = unit(P[1], P[0])
        u1 = unit(P[-2], P[-1])
        P = [(P[0][0] + u0[0] * ext, P[0][1] + u0[1] * ext)] + P + [(P[-1][0] + u1[0] * ext, P[-1][1] + u1[1] * ext)]
    if len(P) == 2:
        return [(P[0][0] + (P[1][0] - P[0][0]) * i / 6.0, P[0][1] + (P[1][1] - P[0][1]) * i / 6.0) for i in range(7)]
    Q = [P[0]] + P + [P[-1]]
    out = []
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        for s in range(sub):
            t = s / float(sub)
            t2, t3 = t * t, t * t * t
            out.append((0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                        0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)))
    out.append(P[-1])
    return out


# --------------------------------------------------------------------------- blueprint
class Space(object):
    """Occupied cylinders (x, y, r, z0, z1). Used to place parts where they do not intersect anything."""

    def __init__(self):
        self.c = []

    def add(self, x, y, r, z0, z1, tag=""):
        self.c.append((x, y, r, z0, z1, tag))

    def free(self, x, y, r, z0, z1, margin=0.08, skip=()):
        for (cx, cy, cr, a0, a1, tag) in self.c:
            if tag in skip or a1 <= z0 + 0.02 or z1 <= a0 + 0.02:
                continue
            if math.hypot(x - cx, y - cy) < r + cr + margin:
                return False
        return True

    def near(self, pref, r, z0, z1, rmax=6.0, limit=15.0, margin=0.08, skip=()):
        """Free point closest to pref (spiral search)."""
        best = None
        steps = int(rmax / 0.25)
        for i in range(steps + 1):
            d = 0.25 * i
            na = 1 if i == 0 else int(2 * math.pi * d / 0.25)
            for k in range(max(na, 1)):
                a = 2 * math.pi * k / max(na, 1)
                x, y = pref[0] + d * math.cos(a), pref[1] + d * math.sin(a)
                if math.hypot(x, y) + r > limit:
                    continue
                if self.free(x, y, r, z0, z1, margin, skip):
                    return (x, y)
        return best

    def mesh_near(self, c, n1, n2, ang, r, z0, z1, margin=0.08):
        """Meshing position for wheel n2 against n1 at c; scans the angle until the wheel is free."""
        for off in [0] + [s * d for d in range(4, 181, 4) for s in (1, -1)]:
            p = mesh_at(c, n1, n2, ang + off)
            if self.free(p[0], p[1], r, z0, z1, margin) and math.hypot(*p) + r < 15.2:
                return p, ang + off
        return None, None


def build():
    parts = []
    S = Space()

    def add(name, group, make, x, y, z, rot=0.0, cyl=None, parent=None, mat="steel", occupy=True):
        parts.append(dict(name=name, group=group, make=make, pos=(x, y, z), rot=rot, cyl=cyl, parent=parent, mat=mat))
        if cyl and occupy:
            S.add(x, y, cyl[0], z + cyl[1], z + cyl[2], group)

    add("mainplate", "plate", f_plate(15.6, 0.9, [(14.9, 0.3), (6.6, 0.12)], 14), 0, 0, 0.0, mat="steel_brushed")
    arb = {}

    def arbor(name, x, y, z0, z1, r=0.22, mat="steel_dark"):
        arb[name] = (x, y)
        add("arbor_" + name, "arbor", f_arbor(r, z1 - z0), x, y, z0, cyl=(r, 0, z1 - z0), mat=mat, occupy=True)

    # ---------------- going train (fixed geometry, meshing distances)
    C = (0.0, 0.0)
    N_BAR, N_CPIN, N_CW, N_TPIN, N_TW, N_FPIN, N_FW, N_EPIN = 60, 8, 48, 8, 44, 8, 40, 6
    B = mesh_at(C, N_BAR, N_CPIN, 200)
    T = mesh_at(C, N_CW, N_TPIN, 40)
    F = mesh_at(T, N_TW, N_FPIN, 5)
    E = mesh_at(F, N_FW, N_EPIN, -50)
    add("barrel", "wheel", f_barrel(N_BAR, 0.9), B[0], B[1], 1.0, cyl=(tip(N_BAR), 0, 0.9), mat="steel")
    add("barrel_lid", "wheel", f_plate(5.3, 0.12, [(1.6, 0.1)], 10), B[0], B[1], 1.9, cyl=(5.3, 0, 0.22), mat="steel_brushed")
    add("mainspring", "spring", lambda: g.sweep(g.spiral_path(1.3, 4.9, 6.5, 150, 0.0), 0.12, 0.7, k=1),
        B[0], B[1], 1.05, cyl=None, mat="steel_dark")
    arbor("barrel", B[0], B[1], 0.9, 3.8, r=0.55)
    arbor("centre", C[0], C[1], 0.9, 4.6, r=0.3)
    add("centre_pinion", "wheel", f_pinion(N_CPIN, 0.5, 0.3), C[0], C[1], 1.2, cyl=(tip(N_CPIN), 0, 0.5), mat="gold")
    add("centre_wheel", "wheel", f_wheel(N_CW, 0.3, 0.3, spokes=4), C[0], C[1], 2.15, cyl=(tip(N_CW), 0, 0.3), mat="gold")
    arbor("third", T[0], T[1], 0.9, 2.9)
    add("third_pinion", "wheel", f_pinion(N_TPIN, 0.4, 0.22), T[0], T[1], 2.1, cyl=(tip(N_TPIN), 0, 0.4), mat="steel_dark")
    add("third_wheel", "wheel", f_wheel(N_TW, 0.3, 0.25, spokes=4), T[0], T[1], 1.75, cyl=(tip(N_TW), 0, 0.3), mat="steel")
    arbor("fourth", F[0], F[1], 0.9, 3.0)
    add("fourth_pinion", "wheel", f_pinion(N_FPIN, 0.4, 0.22), F[0], F[1], 1.7, cyl=(tip(N_FPIN), 0, 0.4), mat="steel_dark")
    add("fourth_wheel", "wheel", f_wheel(N_FW, 0.3, 0.25, spokes=4), F[0], F[1], 1.2, cyl=(tip(N_FW), 0, 0.3), mat="steel")
    arbor("escape", E[0], E[1], 0.9, 3.0, r=0.18)
    add("escape_pinion", "wheel", f_pinion(N_EPIN, 0.4, 0.15), E[0], E[1], 1.15, cyl=(tip(N_EPIN), 0, 0.4), mat="steel_dark")
    add("escape_wheel", "wheel", f_wheel(15, 0.3, 0.2, kind="ratchet", per=4), E[0], E[1], 1.62, cyl=(tip(15), 0, 0.3), mat="steel_dark")

    # ---------------- pallet fork and balance (placed in free space near the escape wheel)
    PAL = S.near(polar(E[0], E[1], 3.6, -120), 1.6, 1.55, 2.0, rmax=3.0)
    arbor("pallet", PAL[0], PAL[1], 0.9, 3.0, r=0.16)
    BAL = S.near(polar(PAL[0], PAL[1], 5.0, -90), 4.15, 1.95, 2.5, rmax=6.0, margin=0.15)
    ang_fork = math.degrees(math.atan2(BAL[1] - PAL[1], BAL[0] - PAL[0]))
    arbor("balance", BAL[0], BAL[1], 0.9, 3.6, r=0.2)
    add("balance_rim", "balance", f_annulus(4.1, 3.7, 0.45, None), BAL[0], BAL[1], 2.0, cyl=(4.1, 0, 0.45), mat="gold")
    add("balance_hub", "balance", f_annulus(0.75, 0.2, 0.7, 24), BAL[0], BAL[1], 1.95, mat="gold")
    for k in range(3):
        a = math.radians(90 + 120 * k)
        p0 = (math.cos(a) * 0.6, math.sin(a) * 0.6, 0.0)
        p1 = (math.cos(a) * 3.9, math.sin(a) * 3.9, 0.0)
        add("balance_arm%d" % k, "balance", (lambda p0=p0, p1=p1: g.sweep(
            [p0, ((2 * p0[0] + p1[0]) / 3, (2 * p0[1] + p1[1]) / 3, 0.0), ((p0[0] + 2 * p1[0]) / 3, (p0[1] + 2 * p1[1]) / 3, 0.0), p1], 0.42, 0.28, k=1)),
            BAL[0], BAL[1], 2.22, mat="gold")
    for k in range(12):
        x, y = polar(BAL[0], BAL[1], 3.9, 360.0 / 12 * k + 8)
        add("balance_screw%d" % k, "balance", f_screw(0.5, 0.9), x, y, 1.65, mat="gold")
    add("hairspring", "spring", lambda: g.sweep(g.spiral_path(0.55, 2.4, 9.0, 260, 0.0), 0.05, 0.13, k=1),
        BAL[0], BAL[1], 2.75, mat="steel_blue")
    add("hairspring_collet", "balance", f_annulus(0.62, 0.2, 0.22, 24), BAL[0], BAL[1], 2.62, mat="gold")
    add("pallet_fork", "lever", f_lever([(-0.2, 0.0), (1.5, 0.0), (3.3, -0.2)], 0.6, 0.3), PAL[0], PAL[1], 1.62, rot=ang_fork, mat="steel")
    add("pallet_tail", "lever", f_lever([(-0.2, 0.0), (-1.2, 0.4), (-2.0, 0.8)], 0.42, 0.3), PAL[0], PAL[1], 1.62, rot=ang_fork, mat="steel")
    for nm, sg in (("in", 1), ("out", -1)):
        ex = polar(PAL[0], PAL[1], 1.05, math.degrees(math.atan2(E[1] - PAL[1], E[0] - PAL[0])) + sg * 40)
        add("pallet_stone_" + nm, "jewelstone", f_disc(0.22, 0.32, 2), ex[0], ex[1], 1.62, mat="ruby")

    # ---------------- winding wheels on the right (3 o'clock side)
    CRW = S.near((0.5, -10.4), tip(30), 1.05, 1.8, rmax=5.0, limit=14.0, margin=0.15)
    add("crown_wheel", "wheel", f_wheel(30, 0.4, 0.3, hub_h=0.3), CRW[0], CRW[1], 1.1, cyl=(tip(30), 0, 0.7), mat="steel")
    arbor("crown", CRW[0], CRW[1], 0.9, 2.7, r=0.25)
    wp, wa = S.mesh_near(CRW, 30, 14, 160, tip(14), 1.05, 1.7)
    if wp is None:
        wp = S.near((CRW[0] - 3.0, CRW[1] + 1.0), tip(14), 1.05, 1.7, rmax=5.0)
    add("winding_pinion", "wheel", f_wheel(14, 0.4, 0.2), wp[0], wp[1], 1.1, cyl=(tip(14), 0, 0.4), mat="steel")
    arbor("winding", wp[0], wp[1], 0.9, 2.7, r=0.2)

    # ---------------- bridge feet: free spots for pillars and screws (z 0.9 .. 2.9)
    BZ = 2.9
    feet = []

    def foot(bridge, pref):
        p = S.near(pref, 0.55, 0.9, BZ, rmax=5.0, margin=0.1)
        S.add(p[0], p[1], 0.55, 0.9, BZ, "pillar")
        feet.append((bridge, p))
        return p

    fb = [foot("bridge_barrel", polar(B[0], B[1], 6.4, 245)), foot("bridge_barrel", polar(C[0], C[1], 7.5, 285)),
          foot("bridge_barrel", polar(C[0], C[1], 5.8, 105))]
    ft = [foot("bridge_train", polar(T[0], T[1], 5.5, 95)), foot("bridge_train", polar(F[0], F[1], 5.5, 35)), foot("bridge_train", polar(E[0], E[1], 3.5, -30))]
    fbal = [foot("bridge_balance", polar(BAL[0], BAL[1], 4.6, 20)), foot("bridge_balance", polar(BAL[0], BAL[1], 4.6, 160)), foot("bridge_balance", polar(BAL[0], BAL[1], 4.6, -100))]
    fp = [foot("bridge_pallet", polar(PAL[0], PAL[1], 2.6, 200)), foot("bridge_pallet", polar(PAL[0], PAL[1], 2.6, -20))]
    bridges = [
        ("bridge_barrel", [fb[0], B, C, fb[2]], 3.6), ("bridge_train", [ft[0], T, F, E, ft[2]], 3.2),
        ("bridge_balance", [fbal[0], BAL, fbal[1]], 3.4), ("bridge_pallet", [fp[0], PAL, fp[1]], 2.4),
    ]
    for name, pts, w in bridges:
        add(name, "bridge", f_bridge(pts, w, 0.5), 0, 0, BZ, cyl=None, mat="steel_brushed", occupy=False)
    for i, p in enumerate([B, C, T, F, E, BAL, PAL]):
        add("jewel_top%d" % i, "jewel", f_jewel(1.0), p[0], p[1], 2.55, mat="ruby", occupy=False)
        add("jewel_bot%d" % i, "jewel", f_jewel(1.0), p[0], p[1], 0.9, mat="ruby", occupy=False)
    for i, (br, p) in enumerate(feet):
        add("screw_b%d" % i, "screw", f_screw(1.0, 1.3), p[0], p[1], BZ + 0.5 - 1.3, rot=i * 37.0, mat="steel_blued", occupy=False)
        add("pillar%d" % i, "pillar", f_arbor(0.5, BZ - 0.9), p[0], p[1], 0.9, mat="steel", occupy=False)
    add("ratchet", "wheel", f_wheel(30, 0.3, 0.6, spokes=4, kind="ratchet", per=4), B[0], B[1], 3.55, cyl=(tip(30), 0, 0.3), mat="steel")
    add("ratchet_cap", "wheel", f_annulus(0.9, 0.3, 0.2, 32), B[0], B[1], 3.85, mat="steel")
    add("screw_ratchet", "screw", f_screw(1.0, 1.0), B[0], B[1], 3.85 + 0.2 - 1.0, mat="steel_blued")
    add("click", "lever", f_lever([(0.0, 0.0), (1.4, 0.2), (2.3, -0.2)], 0.55, 0.3), B[0] + 3.2, B[1] + 2.4, 3.55, rot=-30, mat="steel")
    add("click_spring", "lever", f_lever([(0.0, 0.0), (1.6, 0.9), (3.1, 0.7)], 0.16, 0.16), B[0] + 1.0, B[1] + 3.6, 3.55, rot=-10, mat="steel_blue")

    # ---------------- top train (z 3.5 ... 4.2): placed with free-space search
    N_MIN, N_HPIN, N_HW = 32, 16, 36
    add("cannon_pinion", "wheel", lambda: g.annulus(0.9, 0.32, 1.1, 32, bevel=0.03), C[0], C[1], 3.5, cyl=(0.9, 0, 1.1), mat="gold")
    add("minute_wheel", "wheel", f_wheel(N_MIN, 0.3, 0.25, spokes=4), C[0], C[1], 3.55, cyl=(tip(N_MIN), 0, 0.3), mat="gold")
    hw, _ = S.mesh_near(C, N_MIN, N_HPIN, 300, tip(N_HPIN), 3.5, 3.9)
    hw = hw or S.near(polar(C[0], C[1], rp(N_MIN) + rp(N_HPIN), 300), tip(N_HPIN), 3.5, 3.9, rmax=2.0)
    arbor("hourtrain", hw[0], hw[1], 3.4, 4.5, r=0.2)
    add("hour_pinion", "wheel", f_pinion(N_HPIN, 0.3, 0.2), hw[0], hw[1], 3.55, cyl=(tip(N_HPIN), 0, 0.3), mat="steel")
    hour, _ = S.mesh_near(hw, N_HPIN, N_HW, 250, tip(N_HW), 3.9, 4.25)
    hour = hour or S.near(polar(hw[0], hw[1], rp(N_HPIN) + rp(N_HW), 250), tip(N_HW), 3.9, 4.25, rmax=3.0)
    add("hour_wheel", "wheel", f_wheel(N_HW, 0.3, 0.25, spokes=3), hour[0], hour[1], 3.9, cyl=(tip(N_HW), 0, 0.3), mat="steel")
    dd = S.near(polar(C[0], C[1], 9.0, 60), tip(20), 3.5, 3.9, rmax=4.0)
    add("date_driver", "wheel", f_wheel(20, 0.3, 0.2), dd[0], dd[1], 3.6, cyl=(tip(20), 0, 0.3), mat="steel")
    arbor("datedrv", dd[0], dd[1], 3.4, 4.5, r=0.2)
    star, _ = S.mesh_near(dd, 20, 31, 110, tip(31), 3.5, 3.9)
    star = star or S.near(polar(dd[0], dd[1], rp(20) + rp(31), 110), tip(31), 3.5, 3.9, rmax=3.0)
    add("date_star", "wheel", f_wheel(31, 0.3, 0.3, spokes=0, kind="ratchet", per=4), star[0], star[1], 3.6, cyl=(tip(31), 0, 0.3), mat="steel")
    arbor("datestar", star[0], star[1], 3.4, 4.5, r=0.22)
    add("date_jumper", "lever", f_lever([(0.0, 0.0), (1.8, 0.5), (3.6, 0.2)], 0.5, 0.25), star[0] + 3.4, star[1] - 0.8, 3.6, rot=200, mat="steel")
    moon = S.near(polar(C[0], C[1], 8.2, 150), tip(30), 3.5, 3.9, rmax=4.0)
    add("moon_wheel", "wheel", f_wheel(30, 0.3, 0.3, spokes=4), moon[0], moon[1], 3.6, cyl=(tip(30), 0, 0.3), mat="gold")
    arbor("moon", moon[0], moon[1], 3.4, 5.2, r=0.25)
    mstar = S.near(polar(C[0], C[1], 6.0, 255), tip(12), 3.5, 3.9, rmax=4.0)
    add("month_star", "wheel", f_wheel(12, 0.3, 0.25, kind="ratchet", per=4, hub_h=0.1), mstar[0], mstar[1], 3.6, cyl=(tip(12), 0, 0.3), mat="steel")
    leap = S.near(polar(C[0], C[1], 8.5, 230), tip(36), 3.95, 4.3, rmax=4.0)
    add("leap_cam", "wheel", f_wheel(36, 0.3, 0.25, spokes=0), leap[0], leap[1], 3.95, cyl=(tip(36), 0, 0.3), mat="steel_brushed")
    add("calendar_plate", "calplate", f_plate(14.6, 0.4, [(13.4, 0.12)], 14), 0, 0, 4.4, mat="steel_brushed")
    for k in range(6):
        p = polar(C[0], C[1], 13.2, 30 + 60 * k)
        add("screw_cal%d" % k, "screw", f_screw(0.9, 0.9), p[0], p[1], 4.4 + 0.4 + 0.12 - 0.9 + 0.2, rot=k * 51, mat="steel_blued", occupy=False)
        add("cal_post%d" % k, "pillar", f_arbor(0.45, 4.4 - 0.9), p[0], p[1], 0.9, mat="steel", occupy=False)
    add("date_ring", "calring", f_annulus(14.0, 12.3, 0.3, None, steps=[(13.2, 0.06)], bevel=0.05), 0, 0, 5.0, mat="white")
    add("moon_disc", "moondisc", f_plate(4.4, 0.26, [(3.9, 0.04)], 6), moon[0], moon[1], 5.05, mat="blue")
    add("moon_a", "moon", f_disc(1.5, 0.12, 5, dome=0.22), moon[0] + 1.5, moon[1] + 0.7, 5.35, mat="moonlit")
    add("moon_b", "moon", f_disc(1.5, 0.12, 5, dome=0.22), moon[0] - 1.5, moon[1] - 0.7, 5.35, mat="moonlit")
    for k, (r, x, y, z) in enumerate([(6.0, 0, 0, 5.6), (4.0, 7.5, 5.0, 5.65), (3.2, -7.0, -6.5, 5.65)]):
        add("sapphire_disc%d" % k, "glass", f_plate(r, 0.16, None, 6), x, y, z, mat="glass")
    add("dial", "dial", f_plate(14.4, 0.35, [(13.6, 0.05), (11.0, 0.05)], 14), 0, 0, 6.0, mat="white")
    add("case_ring", "case", f_annulus(17.4, 14.6, 5.2, None, steps=[(16.6, 0.25)], bevel=0.12), 0, 0, 1.2, mat="steel_polished")
    add("bezel", "case", f_annulus(17.2, 14.0, 0.9, None, bevel=0.15), 0, 0, 6.8, mat="steel_polished")
    add("crystal", "glass", f_disc(15.2, 0.9, 12, dome=1.4), 0, 0, 7.2, mat="glass")
    add("crown", "case", lambda: g.gear(24, 1.6, 2.2, 0.35, kind="spur", per_tooth=4, chamfer=0.1), 17.0, CRW[0], 3.0, mat="steel_polished")
    add("hour_hand", "hand", f_lever([(-1.2, 0.0), (0.0, 0.0), (5.0, 0.0), (7.2, 0.0)], 0.9, 0.16), 0, 0, 6.5, rot=290, mat="steel_polished")
    add("minute_hand", "hand", f_lever([(-1.6, 0.0), (0.0, 0.0), (7.0, 0.0), (11.4, 0.0)], 0.6, 0.14), 0, 0, 6.7, rot=60, mat="steel_polished")
    _details(parts, S, add, dict(B=B, C=C, T=T, F=F, E=E, BAL=BAL, PAL=PAL, CRW=CRW, wp=wp, moon=moon, star=star, bridges=bridges, feet=feet))
    return _mesh_phases(_orient(parts))


MESH_PAIRS = [("barrel", "centre_pinion", 60, 8), ("centre_wheel", "third_pinion", 48, 8), ("third_wheel", "fourth_pinion", 44, 8),
              ("fourth_wheel", "escape_pinion", 40, 6), ("minute_wheel", "hour_pinion", 32, 16), ("hour_pinion", "hour_wheel", 16, 36),
              ("date_driver", "date_star", 20, 31), ("crown_wheel", "winding_pinion", 30, 14),
              ("date_star", "cal_wheel0", 31, 18), ("cal_wheel0", "cal_wheel1", 18, 24), ("cal_wheel1", "cal_wheel2", 24, 28)]


def _mesh_phases(parts):
    """Turn every driven wheel so that a tooth of the driver points into a gap of the driven wheel.
    Tooth centres sit at (j + 0.375) pitches, gap centres half a pitch later (see wm_geo._tooth_radial, 4 samples/tooth)."""
    byname = {p["name"]: p for p in parts}
    for a, b, na, nb in MESH_PAIRS:
        A, Bp = byname.get(a), byname.get(b)
        if not A or not Bp:
            continue
        th = math.atan2(Bp["pos"][1] - A["pos"][1], Bp["pos"][0] - A["pos"][0])
        pb = 2 * math.pi / nb
        beta = th + math.pi - 0.375 * pb - 0.5 * pb
        Bp["rot"] = math.degrees(beta % pb)
    return parts


FIXED_GROUPS = ("case", "dial", "marker", "hand", "glass")
FIXED_NAMES = ("crown_tube", "crown_stem_cap", "crown", "date_frame", "dial_ring", "minute_track")


def _orient(parts, deg=90.0):
    """Turn the movement about the axis; case, dial, glass and hands keep their place."""
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    for p in parts:
        if p["group"] in FIXED_GROUPS or p["name"] in FIXED_NAMES:
            continue
        x, y, z = p["pos"]
        p["pos"] = (x * ca - y * sa, x * sa + y * ca, z)
        p["rot"] = p["rot"] + deg
    return parts


def _tiny(add, S, name, group, make, pref, r, z0, z1, mat="steel", z=None, rmax=4.0, margin=0.06, rot=0.0, cyl=None, **kw):
    """Place a small part near pref where nothing else stands in [z0, z1]; returns the spot or None."""
    p = S.near(pref, r, z0, z1, rmax=rmax, margin=margin)
    if p is None:
        return None
    add(name, group, make, p[0], p[1], z if z is not None else z0, rot=rot, cyl=(r, 0, z1 - z0) if cyl is None else cyl, mat=mat)
    return p


def _details(parts, S, add, cx):
    """Second pass: fasteners, pins, levers, springs, setting and calendar work, case, dial and hands."""
    B, C, T, F, E, BAL, PAL, CRW, wp, moon, star = (cx[k] for k in ("B", "C", "T", "F", "E", "BAL", "PAL", "CRW", "wp", "moon", "star"))
    BZ = 2.9
    top = BZ + 0.5

    # -- jewel settings: gold chaton on the bridge over every top jewel, two screws each, cap jewel on the pivots
    for i, p in enumerate([B, C, T, F, E, BAL, PAL]):
        a = 40.0 * i + 15
        add("chaton%d" % i, "chaton", f_annulus(1.15, 0.5, 0.14, None, bevel=0.03), p[0], p[1], top, mat="gold")
        for k in range(2):
            x, y = polar(p[0], p[1], 0.98, a + 180 * k)
            add("chaton%d_screw%d" % (i, k), "screw_t", f_screw(0.42, 0.7), x, y, top + 0.14 - 0.7 * 0.42, rot=37 * (i + k), mat="steel_blued")
        if i in (0, 2, 3, 4, 5):
            add("cap_jewel%d" % i, "chaton", f_jewel(0.62), p[0], p[1], top + 0.14, mat="ruby")

    # -- plate rim screws (holding the movement in the case), heads on the flange band
    for k in range(14):
        x, y = polar(0, 0, 15.25, 360.0 / 14 * k + 6)
        add("rim_screw%d" % k, "screw_t", f_screw(0.6, 0.8), x, y, 0.9 + 0.0 - 0.8 * 0.6 + 0.19, rot=k * 23, mat="steel_blued")

    # -- pins and studs on the plate (lever pivots, guides)
    n = 0
    for k in range(60):
        pref = polar(0, 0, 6 + (k % 6) * 1.3, 25.0 * k + 7)
        if _tiny(add, S, "pin%d" % n, "pin", f_pin(0.13 + 0.03 * (k % 3), 0.55 + 0.1 * (k % 4)), pref, 0.16, 0.9, 1.6, mat="steel_dark", z=0.9, rmax=1.2):
            n += 1
        if n >= 26:
            break

    # -- balance: staff, roller table, impulse pin, stud with holder, regulator index and pins, poising screws
    add("balance_staff", "balance", f_arbor(0.13, 3.2), BAL[0], BAL[1], 0.95, mat="steel_dark")
    add("roller_table", "balance", f_annulus(1.15, 0.2, 0.16, 32), BAL[0], BAL[1], 1.62, mat="steel")
    a_imp = math.radians(70)
    add("impulse_jewel", "jewelstone", f_disc(0.14, 0.26, 2), BAL[0] + 0.95 * math.cos(a_imp), BAL[1] + 0.95 * math.sin(a_imp), 1.78, mat="ruby")
    sx, sy = polar(BAL[0], BAL[1], 2.3, 200)
    add("hairspring_stud", "balance", f_pin(0.16, 0.5), sx, sy, 2.7, mat="steel")
    add("stud_holder", "balance", f_lever([(0.0, 0.0), (0.7, 0.2), (1.4, 0.1)], 0.5, 0.2), sx, sy, 3.2, rot=200, mat="steel")
    add("stud_screw", "screw_t", f_screw(0.4, 0.6), sx, sy, 3.4 - 0.6 * 0.4, mat="steel_blued")
    ix, iy = polar(BAL[0], BAL[1], 0.0, 0)
    add("regulator_index", "lever", f_lever([(0.0, 0.0), (1.6, 0.6), (3.0, 1.9)], 0.5, 0.18), BAL[0], BAL[1], top + 0.02, rot=250, mat="steel_brushed")
    for k in range(2):
        px, py = polar(BAL[0], BAL[1], 2.7, 250 + 10 * k)
        add("index_pin%d" % k, "pin", f_pin(0.06, 0.45), px, py, top, mat="gold")
    for k in range(4):
        x, y = polar(BAL[0], BAL[1], 2.0, 45 + 90 * k)
        add("poising_screw%d" % k, "balance", f_screw(0.4, 0.6), x, y, 2.05 + 0.28 + 0.0 - 0.6 * 0.4 + 0.02, rot=13 * k, mat="gold")

    # -- barrel and ratchet hardware
    for k in range(3):
        x, y = polar(B[0], B[1], 4.2, 90 + 120 * k)
        add("barrel_lid_screw%d" % k, "screw_t", f_screw(0.45, 0.6), x, y, 1.9 + 0.22 - 0.6 * 0.45, rot=17 * k, mat="steel_blued")
    add("click_screw", "screw_t", f_screw(0.5, 0.7), B[0] + 3.2, B[1] + 2.4, 3.85 - 0.7 * 0.5 + 0.02, mat="steel_blued")
    add("click_spring_screw", "screw_t", f_screw(0.4, 0.6), B[0] + 1.0, B[1] + 3.6, 3.71 - 0.6 * 0.4, mat="steel_blued")

    # -- winding and setting: sliding pinion, clutch, setting wheels, lever, yoke, springs, stem (left-up region)
    sp = S.near((CRW[0] + 3.4, CRW[1] - 1.0), 1.0, 1.05, 1.7, rmax=6.0)
    if sp:
        add("sliding_pinion", "wheel", f_wheel(12, 0.4, 0.2, hub_h=0.2), sp[0], sp[1], 1.1, cyl=(tip(12), 0, 0.6), mat="steel")
        arb2 = (sp[0], sp[1])
        add("arbor_sliding", "arbor", f_arbor(0.2, 1.8), sp[0], sp[1], 0.9, cyl=(0.2, 0, 1.8), mat="steel_dark")
    for k, (n1, nn, ang) in enumerate([(14, 24, 200), (24, 16, 250), (16, 20, 300)]):
        base = wp if k == 0 else last
        q, _ = S.mesh_near(base, n1, nn, ang, tip(nn), 1.05, 1.7)
        if q is None:
            break
        add("setting_wheel%d" % k, "wheel", f_wheel(nn, 0.35, 0.2), q[0], q[1], 1.1, cyl=(tip(nn), 0, 0.35), mat="steel")
        add("arbor_setting%d" % k, "arbor", f_arbor(0.2, 1.7), q[0], q[1], 0.9, cyl=(0.2, 0, 1.7), mat="steel_dark")
        last = q
    lv = S.near((CRW[0] - 4.5, CRW[1] + 2.0), 1.2, 1.0, 1.5, rmax=6.0)
    if lv:
        add("setting_lever", "lever", f_lever([(0.0, 0.0), (1.8, 0.7), (3.6, 0.5)], 0.7, 0.25), lv[0], lv[1], 1.0, rot=20, cyl=(1.4, 0, 0.25), mat="steel")
        add("yoke", "lever", f_lever([(0.0, 0.0), (1.4, -0.5), (2.6, -0.2)], 0.5, 0.22), lv[0] + 0.3, lv[1] - 0.9, 1.3, rot=-15, mat="steel")
        add("yoke_spring", "lever", f_lever([(0.0, 0.0), (1.2, 0.6), (2.4, 0.3)], 0.12, 0.12), lv[0] - 0.4, lv[1] + 0.9, 1.3, rot=10, mat="steel_blue")
        add("setting_lever_screw", "screw_t", f_screw(0.5, 0.7), lv[0], lv[1], 1.25 + 0.0 - 0.7 * 0.5 + 0.02, mat="steel_blued")
    add("winding_stem", "lever", (lambda L=19.4 + CRW[1]: g.sweep([(0.0, 0.0, 0.0), (L / 2, 0.0, 0.0), (L, 0.0, 0.0)], 0.64, 0.64, k=2, corner=1.0)), CRW[0], CRW[1], 1.3, rot=-90, mat="steel_polished")

    # -- top-level levers on the calendar plate: three jumpers with springs, four correctors (z 4.92)
    S.add(moon[0], moon[1], 4.6, 5.0, 5.5, "moon")
    for k in range(3):
        p = S.near(polar(0, 0, 9.2, 200 + 55 * k), 1.4, 4.9, 5.0, rmax=3.5, limit=12.0)
        if p:
            add("jumper%d" % k, "lever", f_lever([(0.0, 0.0), (1.6, 0.5), (3.2, 0.2)], 0.5, 0.2), p[0], p[1], 4.92, rot=25 + 90 * k, cyl=(1.4, 0, 0.2), mat="steel")
            add("jumper_spring%d" % k, "lever", f_lever([(0.0, 0.0), (1.3, 0.5), (2.5, 0.35)], 0.1, 0.1), p[0] + 0.2, p[1] + 0.7, 4.92, rot=25 + 90 * k, mat="steel_blue")
            add("jumper_screw%d" % k, "screw_t", f_screw(0.5, 0.7), p[0], p[1], 5.12 - 0.7 * 0.5, mat="steel_blued")
    for k in range(4):
        p = S.near(polar(0, 0, 10.5, 15 + 85 * k), 1.2, 4.9, 5.0, rmax=3.0, limit=12.2)
        if p:
            add("corrector%d" % k, "lever", f_lever([(0.0, 0.0), (1.2, 0.3), (2.4, 0.0)], 0.42, 0.18), p[0], p[1], 4.92, rot=60 * k, cyl=(1.2, 0, 0.18), mat="steel_brushed")
            add("corrector_pin%d" % k, "pin", f_pin(0.1, 0.4), p[0], p[1], 5.1, mat="gold")
    for k in range(6):   # extra calendar plate screws
        x, y = polar(0, 0, 12.4, 45 + 60 * k)
        add("cal_screw_b%d" % k, "screw_c", f_screw(0.6, 0.8), x, y, 4.92 - 0.8 * 0.6 + 0.19, rot=k * 31, mat="steel_blued")

    # -- date marks (31 raised ticks in one part, printed look) and month scale
    def date_marks():
        m = None
        for d in range(31):
            a = 2 * math.pi * d / 31.0
            r = 13.6
            tick = g.sweep([(r * math.cos(a), r * math.sin(a), 0.0), ((r + 0.3) * math.cos(a), (r + 0.3) * math.sin(a), 0.0)], 0.16, 0.05, k=1, corner=0.4)
            m = tick if m is None else m.merged(tick)
        return m
    add("date_marks", "calring", date_marks, 0, 0, 5.3, mat="steel_blued")

    # -- dial parts: 12 hour markers, three sub-dial rings, date window frame, minute track
    for k in range(12):
        a = 2 * math.pi * k / 12
        r0, r1 = 12.3, 13.6 if k % 3 else 13.9
        add("marker%d" % k, "marker", (lambda a=a, r0=r0, r1=r1: g.sweep([(r0 * math.cos(a), r0 * math.sin(a), 0.0), (r1 * math.cos(a), r1 * math.sin(a), 0.0)], 0.42 if k % 3 == 0 else 0.26, 0.09, k=1, corner=0.4)),
            0, 0, 6.4, mat="steel_polished")
    for k, (r, x, y) in enumerate([(3.6, 0.0, 6.0), (3.2, -6.0, -3.5), (3.2, 6.0, -3.5)]):
        add("subdial_ring%d" % k, "marker", f_annulus(r, r - 0.35, 0.09, None, bevel=0.02), x, y, 6.36, mat="steel_polished")
    add("date_frame", "marker", f_annulus(2.1, 1.7, 0.12, 48, bevel=0.03), 9.4, 4.5, 6.36, mat="steel_polished")
    add("minute_track", "marker", f_annulus(14.2, 14.0, 0.08, None, bevel=0.02), 0, 0, 6.36, mat="steel_polished")

    # -- case: middle, case back, gaskets, lugs and spring bars, crown tube, screws
    add("case_back", "case", f_plate(15.9, 0.9, [(15.0, 0.2)], 14), 0, 0, 0.0 - 1.4, mat="steel_polished")
    add("case_back_ring", "case", f_annulus(17.6, 16.0, 0.45, None, bevel=0.06), 0, 0, 0.0 - 0.5, mat="steel_polished")
    add("gasket_back", "case", f_annulus(15.8, 15.2, 0.3, None, bevel=0.05), 0, 0, 0.0 - 0.15, mat="steel_dark")
    add("gasket_crystal", "case", f_annulus(15.4, 14.6, 0.3, None, bevel=0.05), 0, 0, 7.05, mat="steel_dark")
    add("dial_ring", "case", f_annulus(15.0, 14.2, 0.5, None, bevel=0.06), 0, 0, 5.85, mat="white")
    add("movement_ring", "case", f_annulus(15.9, 15.4, 1.0, None, bevel=0.05), 0, 0, 0.25, mat="steel_dark")
    for k in range(6):
        x, y = polar(0, 0, 16.7, 60 * k + 30)
        add("case_back_screw%d" % k, "screw_t", f_screw(0.9, 1.0), x, y, -1.4 + 0.9 - 0.9 * 1.0 + 0.05, rot=k * 41, mat="steel_polished")
    for k in range(4):
        ang = 90 * k + 45
        x, y = polar(0, 0, 17.8, ang)
        add("lug%d" % k, "case", (lambda: g.sweep([(0.0, 0.0, 0.0), (1.6, 0.0, 0.0), (3.2, 0.0, -0.6), (4.6, 0.0, -1.6)], 3.0, 2.0, k=2, corner=0.5)),
            x, y, 3.4, rot=ang, mat="steel_polished")
    for k in range(2):
        y = 19.4 if k == 0 else -19.4
        add("spring_bar%d" % k, "case", (lambda: g.sweep([(-4.2, 0.0, 0.0), (0.0, 0.0, 0.0), (4.2, 0.0, 0.0)], 0.8, 0.8, k=2, corner=1.0)),
            0.0, y, 3.4 - 0.6, mat="steel_polished")
    add("crown_tube", "case", lambda: g.annulus(1.1, 0.6, 1.6, 24, bevel=0.03), 16.2, CRW[0], 3.0, mat="steel_polished")
    add("crown_stem_cap", "case", f_disc(0.8, 0.3, 2, dome=0.15), 19.6, CRW[0], 3.0, mat="steel_polished")
    add("second_hand", "hand", f_lever([(-2.4, 0.0), (0.0, 0.0), (9.0, 0.0), (12.4, 0.0)], 0.22, 0.08), 0, 0, 6.9, rot=200, mat="steel_polished")
    add("second_counterweight", "hand", f_disc(0.55, 0.1, 2), -2.4 * math.cos(math.radians(200)), -2.4 * math.sin(math.radians(200)), 6.9, mat="steel_polished")
    add("hand_cap", "hand", f_disc(0.7, 0.35, 3, dome=0.1), 0, 0, 7.0, mat="steel_polished")
    add("subdial_hand0", "hand", f_lever([(0.0, 0.0), (2.6, 0.0)], 0.16, 0.06), 0.0, 6.0, 6.5, rot=120, mat="steel_blued")
    add("subdial_hand1", "hand", f_lever([(0.0, 0.0), (2.4, 0.0)], 0.16, 0.06), -6.0, -3.5, 6.5, rot=40, mat="steel_blued")
    _details2(add, S, cx)


def _details2(add, S, cx):
    """Third pass: collars, plate screws, holders, dial feet, bezel screws, hand tubes, calendar intermediates."""
    B, C, BAL = cx["B"], cx["C"], cx["BAL"]
    # gold collars around the base of every pillar and calendar post (countersinks)
    for i, (br, p) in enumerate(cx["feet"]):
        add("pillar_collar%d" % i, "collar", f_annulus(0.9, 0.48, 0.07, 24, bevel=0.02), p[0], p[1], 0.9, mat="gold")
    for k in range(6):
        x, y = polar(0, 0, 13.2, 30 + 60 * k)
        add("post_collar%d" % k, "collar", f_annulus(0.85, 0.44, 0.07, 24, bevel=0.02), x, y, 0.9, mat="gold")
    # extra plate screws in free spots (blued steel, small)
    n = 0
    for k in range(40):
        pref = polar(0, 0, 4 + (k % 7) * 1.5, 47.0 * k + 11)
        p = S.near(pref, 0.5, 0.9, 1.4, rmax=1.5, margin=0.05)
        if p:
            add("plate_screw%d" % n, "screw_t", f_screw(0.5, 0.7), p[0], p[1], 0.9 + 0.16 - 0.7 * 0.5, rot=29 * k, mat="steel_blued")
            S.add(p[0], p[1], 0.5, 0.9, 1.3, "screw")
            n += 1
        if n >= 16:
            break
    # movement holders: three clamps on the plate rim with screws
    for k in range(3):
        x, y = polar(0, 0, 15.0, 120 * k + 20)
        add("holder%d" % k, "lever", f_lever([(0.0, 0.0), (1.4, 0.0), (2.6, 0.0)], 0.9, 0.22), x, y, 1.25, rot=120 * k + 20 + 180, mat="steel")
        add("holder_screw%d" % k, "screw_t", f_screw(0.55, 0.8), x, y, 1.47 - 0.8 * 0.55 + 0.02, rot=13 * k, mat="steel_blued")
    # dial feet and their screws, bezel screws, hand tubes
    for k in range(3):
        x, y = polar(0, 0, 13.9, 90 + 120 * k)
        add("dial_foot%d" % k, "case", f_arbor(0.3, 1.0), x, y, 5.0, mat="steel")
        add("dial_foot_screw%d" % k, "screw_t", f_screw(0.4, 0.6), x, y, 4.6, rot=k * 40, mat="steel_blued")
    for k in range(8):
        x, y = polar(0, 0, 16.6, 22.5 + 45 * k)
        add("bezel_screw%d" % k, "screw_t", f_screw(0.5, 0.5), x, y, 7.7 - 0.5 * 0.5 + 0.02, rot=k * 17, mat="steel_polished")
    add("crown_gasket", "case", lambda: g.annulus(1.05, 0.62, 0.25, 24, bevel=0.02), 16.0, cx["CRW"][0], 3.0, mat="steel_dark")
    add("hour_pipe", "hand", lambda: g.annulus(0.55, 0.28, 0.9, 24, bevel=0.03), 0, 0, 6.35, mat="steel_polished")
    add("minute_pipe", "hand", lambda: g.annulus(0.42, 0.22, 1.0, 24, bevel=0.03), 0, 0, 6.55, mat="steel_polished")
    add("second_pipe", "hand", lambda: g.annulus(0.3, 0.14, 1.1, 16, bevel=0.02), 0, 0, 6.75, mat="steel_polished")
    # calendar intermediates: three small wheels meshed in a chain on the top level
    base = cx["star"]
    last = base
    prev_n = 31
    for k, (nn, ang) in enumerate([(18, 40), (24, 100), (28, 160)]):
        q, _ = S.mesh_near(last, prev_n, nn, ang, tip(nn), 3.5, 3.9)
        if q is None:
            break
        add("cal_wheel%d" % k, "wheel", f_wheel(nn, 0.3, 0.2), q[0], q[1], 3.6, cyl=(tip(nn), 0, 0.3), mat="steel")
        add("arbor_calw%d" % k, "arbor", f_arbor(0.2, 1.0), q[0], q[1], 3.4, cyl=(0.2, 0, 1.0), mat="steel_dark")
        add("cal_wheel_screw%d" % k, "screw_t", f_screw(0.4, 0.6), q[0], q[1], 4.4 - 0.6 * 0.4, mat="steel_blued")
        last, prev_n = q, nn


# --------------------------------------------------------------------------- checks
def check(parts, tol=0.03):
    """Report pairs whose cylinders overlap in XY and Z (excluding meshing pairs and coaxial parts)."""
    cyls = []
    for p in parts:
        if p["cyl"]:
            r, z0, z1 = p["cyl"]
            cyls.append((p["name"], p["pos"][0], p["pos"][1], r, p["pos"][2] + z0, p["pos"][2] + z1, p["group"]))
    bad = []
    for i in range(len(cyls)):
        for j in range(i + 1, len(cyls)):
            a, b = cyls[i], cyls[j]
            if a[5] <= b[4] + tol or b[5] <= a[4] + tol:
                continue
            d = math.hypot(a[1] - b[1], a[2] - b[2])
            if d < 0.05:
                continue   # coaxial stack
            if d < a[3] + b[3] - tol:
                gear_pair = a[6] == "wheel" and b[6] == "wheel" and abs(d - (a[3] + b[3])) < 0.8
                if gear_pair:
                    continue
                if a[6] == "arbor" or b[6] == "arbor":
                    # arbor may pass through a coaxial part only
                    bad.append((a[0], b[0], round(d, 2), round(a[3] + b[3], 2)))
                    continue
                bad.append((a[0], b[0], round(d, 2), round(a[3] + b[3], 2)))
    return bad


def part_count(parts):
    return len(parts)
