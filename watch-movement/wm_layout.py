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
    return lambda: g.gear(n, tip(n), thick, bore, hub_r=max(bore * 1.8, tip(n) * 0.45), per_tooth=4, chamfer=0.02)


def f_arbor(r, length):
    return lambda: g.rod(r, length, m=2, chamfer=0.02)


def f_screw(scale=1.0, length=1.3):
    return lambda: g.screw(0.55 * scale, 0.32 * scale, 0.3 * scale, length * scale, 0.13 * scale, m=3)


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
        return mesh_at(c, n1, n2, ang), ang


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
    CRW = S.near((-8.0, 9.0), tip(30), 1.05, 1.8, rmax=9.0, limit=14.0, margin=0.15)
    add("crown_wheel", "wheel", f_wheel(30, 0.4, 0.3, hub_h=0.3), CRW[0], CRW[1], 1.1, cyl=(tip(30), 0, 0.7), mat="steel")
    arbor("crown", CRW[0], CRW[1], 0.9, 2.7, r=0.25)
    wp, wa = S.mesh_near(CRW, 30, 14, 90, tip(14), 1.05, 1.7)
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
    arbor("hourtrain", hw[0], hw[1], 3.4, 4.5, r=0.2)
    add("hour_pinion", "wheel", f_pinion(N_HPIN, 0.3, 0.2), hw[0], hw[1], 3.55, cyl=(tip(N_HPIN), 0, 0.3), mat="steel")
    hour, _ = S.mesh_near(hw, N_HPIN, N_HW, 250, tip(N_HW), 3.9, 4.25)
    add("hour_wheel", "wheel", f_wheel(N_HW, 0.3, 0.25, spokes=3), hour[0], hour[1], 3.9, cyl=(tip(N_HW), 0, 0.3), mat="steel")
    dd = S.near(polar(C[0], C[1], 9.0, 60), tip(20), 3.5, 3.9, rmax=4.0)
    add("date_driver", "wheel", f_wheel(20, 0.3, 0.2), dd[0], dd[1], 3.6, cyl=(tip(20), 0, 0.3), mat="steel")
    arbor("datedrv", dd[0], dd[1], 3.4, 4.5, r=0.2)
    star, _ = S.mesh_near(dd, 20, 31, 110, tip(31), 3.5, 3.9)
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
    add("crown", "case", lambda: g.gear(24, 1.6, 2.2, 0.35, kind="spur", per_tooth=4, chamfer=0.1), 17.0, 0.0, 3.0, mat="steel_polished")
    add("hour_hand", "hand", f_lever([(-1.2, 0.0), (0.0, 0.0), (5.0, 0.0), (7.2, 0.0)], 0.9, 0.16), 0, 0, 6.5, rot=290, mat="steel_polished")
    add("minute_hand", "hand", f_lever([(-1.6, 0.0), (0.0, 0.0), (7.0, 0.0), (11.4, 0.0)], 0.6, 0.14), 0, 0, 6.7, rot=60, mat="steel_polished")
    return parts


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
