# -*- coding: utf-8 -*-
"""wm_geo: geometry generators for a watch movement, pure Python (no numpy, no c4d/hou).

Every generator returns a Mesh: points [(x,y,z)] and quads [(a,b,c,d)]. Rules (for subdivision):
  * quads only, closed manifold, normals outward, vertex valence <= 4 (four grid corners have 3);
  * no poles: axis caps are (m x m) quad grids mapped square -> disk, not triangle fans;
  * every part is a separate mesh (each goes under its own subdivision surface in the DCC).
Units: millimetres. Axis of wheels/screws = +Z. Same code runs in C4D, Houdini and plain Python.
"""
import math

TAU = 2.0 * math.pi


class Mesh(object):
    def __init__(self, pts=None, quads=None, name=""):
        self.pts = pts if pts is not None else []
        self.quads = quads if quads is not None else []
        self.name = name

    def add_pt(self, p):
        self.pts.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.pts) - 1

    def add_quad(self, a, b, c, d):
        self.quads.append((a, b, c, d))

    def transformed(self, fn):
        return Mesh([fn(p) for p in self.pts], list(self.quads), self.name)

    def translate(self, dx, dy, dz):
        return self.transformed(lambda p: (p[0] + dx, p[1] + dy, p[2] + dz))

    def merged(self, other):
        n = len(self.pts)
        return Mesh(self.pts + other.pts, self.quads + [tuple(i + n for i in q) for q in other.quads], self.name)


# ----------------------------------------------------------------------------- helpers
def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _len(a): return math.sqrt(_dot(a, a))
def _norm(a):
    l = _len(a) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)


def signed_volume(m):
    v = 0.0
    for q in m.quads:
        a, b, c, d = (m.pts[i] for i in q)
        for tri in ((a, b, c), (a, c, d)):
            v += _dot(tri[0], _cross(tri[1], tri[2])) / 6.0
    return v


def orient_outward(m):
    """Flip all quads if the mesh is inside-out (negative volume)."""
    if signed_volume(m) < 0:
        m.quads = [(q[3], q[2], q[1], q[0]) for q in m.quads]
    return m


def validate(m):
    """Return dict: closed (every edge used by exactly 2 quads), max valence, counts, euler, volume."""
    edges = {}
    for q in m.quads:
        for i in range(4):
            a, b = q[i], q[(i + 1) % 4]
            k = (a, b) if a < b else (b, a)
            edges[k] = edges.get(k, 0) + 1
    closed = all(v == 2 for v in edges.values())
    val = {}
    for (a, b) in edges:
        val[a] = val.get(a, 0) + 1
        val[b] = val.get(b, 0) + 1
    degenerate = 0
    for q in m.quads:
        if len(set(q)) < 4:
            degenerate += 1
    used = len(val)
    return dict(closed=closed, max_valence=max(val.values()) if val else 0, pts=len(m.pts), used_pts=used,
                quads=len(m.quads), edges=len(edges), euler=used - len(edges) + len(m.quads),
                volume=signed_volume(m), degenerate=degenerate,
                non2=sum(1 for v in edges.values() if v != 2))


# ----------------------------------------------------------------------------- square -> disk cap
def _disk_grid(m):
    """Return (grid, boundary): grid[j][i] unit-disk xy for a (m x m) quad grid, boundary = list of (i,j)
    walking the border counter-clockwise, 4*m entries."""
    grid = []
    for j in range(m + 1):
        row = []
        v = -1.0 + 2.0 * j / m
        for i in range(m + 1):
            u = -1.0 + 2.0 * i / m
            row.append((u * math.sqrt(max(0.0, 1.0 - v * v / 2.0)), v * math.sqrt(max(0.0, 1.0 - u * u / 2.0))))
        grid.append(row)
    b = []
    for i in range(m):
        b.append((i, 0))
    for j in range(m):
        b.append((m, j))
    for i in range(m, 0, -1):
        b.append((i, m))
    for j in range(m, 0, -1):
        b.append((0, j))
    return grid, b


def ring_dirs(m):
    """Unit direction vectors of the 4*m ring points that match a disk cap of size m (CCW from (-1,-1) corner)."""
    grid, b = _disk_grid(m)
    out = []
    for (i, j) in b:
        x, y = grid[j][i]
        l = math.hypot(x, y)
        out.append((x / l, y / l))
    return out


def uniform_dirs(n):
    return [(math.cos(TAU * i / n), math.sin(TAU * i / n)) for i in range(n)]


# ----------------------------------------------------------------------------- lathe
def lathe(profile, dirs, cap_start=0, cap_end=0, dome_start=0.0, dome_end=0.0, radial=None, name=""):
    """Revolve profile [(r, z, k), ...] (k optional) around Z.

    dirs: unit vectors of the ring points (uniform_dirs(n) or ring_dirs(m) when a cap is used).
    profile: a closed loop (annular part) when neither cap is used; an open polyline when cap_start/cap_end
      are m > 0: then the first (last) profile entry must be on the axis (r == 0) and it becomes a
      (m x m) quad cap disk of the radius/height of the next (previous) entry; len(dirs) must be 4*m.
    radial(i, k, ndirs) -> multiplier for point radius (used for gear teeth); k = profile point's third value.
    dome_*: cap centre lifted by this amount (positive = away from the part).
    """
    n = len(dirs)
    prof = list(profile)
    ks = [(p[2] if len(p) > 2 else 0.0) for p in prof]
    mesh = Mesh(name=name)
    if cap_start:
        assert n == 4 * cap_start
        prof = prof[1:]
        ks = ks[1:]
    if cap_end:
        assert n == 4 * cap_end
        prof = prof[:-1]
        ks = ks[:-1]
    closed_loop = not cap_start and not cap_end
    rings = []
    for j, p in enumerate(prof):
        r, z = p[0], p[1]
        ring = []
        for i in range(n):
            rr = r * (radial(i, ks[j], n) if radial else 1.0)
            ring.append(mesh.add_pt((dirs[i][0] * rr, dirs[i][1] * rr, z)))
        rings.append(ring)
    nr = len(rings)
    for j in range(nr - 1 + (1 if closed_loop else 0)):
        a = rings[j]
        b = rings[(j + 1) % nr]
        for i in range(n):
            i2 = (i + 1) % n
            mesh.add_quad(a[i], a[i2], b[i2], b[i])

    def make_cap(ring, r, z, m, dome, flip):
        grid, bnd = _disk_grid(m)
        idx = {}
        for k, (i, j) in enumerate(bnd):
            idx[(i, j)] = ring[k]
        for j in range(1, m):
            for i in range(1, m):
                x, y = grid[j][i]
                rho2 = x * x + y * y
                idx[(i, j)] = mesh.add_pt((x * r, y * r, z + dome * (1.0 - rho2)))
        for j in range(m):
            for i in range(m):
                q = (idx[(i, j)], idx[(i + 1, j)], idx[(i + 1, j + 1)], idx[(i, j + 1)])
                mesh.add_quad(*(q[::-1] if flip else q))

    if cap_start:
        make_cap(rings[0], prof[0][0], prof[0][1], cap_start, dome_start, False)
    if cap_end:
        make_cap(rings[-1], prof[-1][0], prof[-1][1], cap_end, dome_end, True)
    return orient_outward(mesh)


# ----------------------------------------------------------------------------- gear wheels
def _tooth_radial(teeth, kind="spur", per_tooth=4, depth=0.0):
    """radial(i, k, n): k in [0,1] moves a profile point from root radius to tip radius by the tooth shape."""
    if kind == "spur":
        pat = {4: (0.0, 1.0, 1.0, 0.0), 6: (0.0, 0.5, 1.0, 1.0, 0.5, 0.0), 8: (0.0, 0.25, 0.9, 1.0, 1.0, 0.9, 0.25, 0.0)}[per_tooth]
    elif kind == "ratchet":  # saw tooth
        pat = {4: (0.0, 0.0, 0.5, 1.0), 6: (0.0, 0.0, 0.0, 0.4, 0.8, 1.0), 8: (0.0, 0.0, 0.0, 0.0, 0.3, 0.6, 0.85, 1.0)}[per_tooth]
    else:
        pat = (0.0,) * per_tooth

    def f(i, k, n, pat=pat, depth=depth, per=per_tooth):
        if k <= 0.0:
            return 1.0
        t = pat[i % per]
        return 1.0 + (k * t) * depth  # depth is relative tooth height (h / r_root)
    return f


def gear(teeth, r_tip, thick=0.3, bore=0.25, hub_r=None, hub_h=0.0, web_r=None, web_drop=0.0, kind="spur",
         per_tooth=4, chamfer=0.03, tooth_h=None, name=""):
    """Toothed wheel around Z, z from 0 to thick (a hub may stick out by hub_h on top). One closed torus, all quads.
    r_tip: tip radius; tooth height defaults to 2.2*module. web_drop: depth of the recessed web on the top face."""
    n = teeth * per_tooth
    mod = 2.0 * r_tip / (teeth + 2.0)
    th = tooth_h if tooth_h else 2.2 * mod
    r_root = r_tip - th
    hub_r = hub_r if hub_r else max(bore * 2.2, bore + 0.08)
    web_r = web_r if web_r else max(hub_r + 0.06, r_root * 0.8)
    depth = th / r_root
    c = min(chamfer, thick * 0.3, th * 0.6)
    top = thick
    P = [(bore, 0.0, 0.0), (hub_r, 0.0, 0.0)]
    P += [(r_root - c, 0.0, 0.0), (r_root, 0.0, 0.8), (r_root, c, 1.0), (r_root, top - c, 1.0), (r_root, top, 0.8), (r_root - c, top, 0.0)]
    if web_drop > 0.0:
        P += [(web_r, top, 0.0), (web_r, top - web_drop, 0.0), (hub_r, top - web_drop, 0.0)]
        P += [(hub_r, top + hub_h, 0.0), (bore, top + hub_h, 0.0)] if hub_h > 0.0 else [(hub_r, top, 0.0), (bore, top, 0.0)]
    else:
        P += [(hub_r, top, 0.0)]
        P += [(hub_r, top + hub_h, 0.0), (bore, top + hub_h, 0.0)] if hub_h > 0.0 else [(bore, top, 0.0)]
    radial = _tooth_radial(teeth, kind, per_tooth, depth)
    return lathe(P, uniform_dirs(n), radial=radial, name=name)


# ----------------------------------------------------------------------------- discs, rings, plates
def annulus(r_out, r_in, thick, seg=64, bevel=0.04, steps=None, name=""):
    """Flat ring with bevelled rim. steps: optional [(r, dz)] raised rings on the top face."""
    b = min(bevel, thick * 0.35, (r_out - r_in) * 0.3)
    prof = [(r_in, 0.0), (r_out - b, 0.0), (r_out, b), (r_out, thick - b), (r_out - b, thick)]
    if steps:
        for (r, dz) in sorted(steps, reverse=True):
            prof.append((r, thick))
            prof.append((r, thick + dz))
            prof.append((r - 0.001, thick + dz))
    prof.append((r_in + b, thick))
    prof.append((r_in, thick - b))
    prof.append((r_in, b))
    return lathe(prof, uniform_dirs(seg), name=name)


def disc_solid(r, thick, m=4, dome=0.0, bevel=0.05, name=""):
    """Solid round disc / stud with quad caps (no poles); 4*m ring points."""
    b = min(bevel, thick * 0.4, r * 0.3)
    prof = [(0.0, 0.0), (r - b, 0.0), (r, b), (r, thick - b), (r - b, thick), (0.0, thick)]
    return lathe(prof, ring_dirs(m), cap_start=m, cap_end=m, dome_end=dome, name=name)


# ----------------------------------------------------------------------------- screws, jewels
def screw(head_r=0.55, head_h=0.35, shaft_r=0.3, shaft_len=1.0, thread_pitch=0.15, m=3, slot=True, domed=True, name=""):
    """Screw along Z: head on top (z from shaft_len to shaft_len+head_h), thread below down to z=0.
    Threads = ring ridges. Slot = lowered centre row of the head cap grid. m=3..4."""
    n = 4 * m
    prof = [(0.0, 0.0)]
    tip = shaft_r * 0.7
    prof.append((tip, 0.0))
    prof.append((shaft_r * 0.9, 0.06))
    steps = max(2, int(shaft_len / thread_pitch))
    for s in range(steps):
        z = 0.1 + (shaft_len - 0.1) * (s + 0.5) / steps
        prof.append((shaft_r * 1.0, z - thread_pitch * 0.15))
        prof.append((shaft_r * 0.78, z + thread_pitch * 0.15))
    prof.append((shaft_r * 0.9, shaft_len))
    prof.append((head_r * 0.85, shaft_len))
    prof.append((head_r, shaft_len + head_h * 0.12))
    prof.append((head_r, shaft_len + head_h * 0.62))
    prof.append((head_r * (0.86 if domed else 0.98), shaft_len + head_h * (0.95 if domed else 1.0)))
    prof.append((0.0, shaft_len + head_h))
    m_ = lathe(prof, ring_dirs(m), cap_start=m, cap_end=m, dome_end=head_h * 0.0, name=name)
    if slot:
        ztop = shaft_len + head_h
        # lower points of the top cap that lie near the X axis (|y| small)
        for i, p in enumerate(m_.pts):
            if abs(p[2] - ztop) < head_h * 0.06 and abs(p[1]) < head_r * 0.3:
                m_.pts[i] = (p[0], p[1], p[2] - head_h * 0.42)
    return m_


def jewel(r=0.55, h=0.35, m=3, name=""):
    """Ring jewel (rounded ring stone with a centre hole)."""
    n = 4 * m
    prof = [(r * 0.28, 0.0), (r * 0.9, 0.0), (r, h * 0.2), (r * 0.98, h * 0.6), (r * 0.82, h), (r * 0.45, h), (r * 0.28, h * 0.6)]
    return lathe(prof, uniform_dirs(n), name=name)


# ----------------------------------------------------------------------------- sweeps
def _rrect_boundary(k, w, h, corner):
    """Points of a k x k grid on a rounded rectangle w x h (corner 0 = rectangle, 1 = ellipse) and its border walk."""
    pts = {}
    for j in range(k + 1):
        for i in range(k + 1):
            u = -1.0 + 2.0 * i / k
            v = -1.0 + 2.0 * j / k
            du = u * math.sqrt(max(0.0, 1.0 - v * v / 2.0))
            dv = v * math.sqrt(max(0.0, 1.0 - u * u / 2.0))
            pts[(i, j)] = (((1 - corner) * u + corner * du) * w * 0.5, ((1 - corner) * v + corner * dv) * h * 0.5)
    b = []
    for i in range(k):
        b.append((i, 0))
    for j in range(k):
        b.append((k, j))
    for i in range(k, 0, -1):
        b.append((i, k))
    for j in range(k, 0, -1):
        b.append((0, j))
    return pts, b


def sweep(path, w, h, k=2, corner=0.5, twist=None, width_fn=None, name=""):
    """Sweep a rounded-rectangle section (w x h) along path [(x,y,z),...] (>=2 points). Frame: T along path,
    B = Z-ish up, N = T x B. Both ends closed with (k x k) quad grids. width_fn(t) -> (w_scale, h_scale)."""
    n = len(path)
    grid, bnd = _rrect_boundary(k, w, h, corner)
    up = (0.0, 0.0, 1.0)
    mesh = Mesh(name=name)
    frames = []
    for s in range(n):
        p0 = path[max(0, s - 1)]
        p1 = path[min(n - 1, s + 1)]
        T = _norm(_sub(p1, p0))
        Nn = _norm(_cross(T, up)) if abs(T[2]) < 0.99 else (1.0, 0.0, 0.0)
        Bn = _cross(Nn, T)
        frames.append((T, Nn, Bn))
    rings = []
    for s in range(n):
        T, Nn, Bn = frames[s]
        ws, hs = width_fn(s / float(n - 1)) if width_fn else (1.0, 1.0)
        ring = []
        for (i, j) in bnd:
            x, y = grid[(i, j)]
            x *= ws
            y *= hs
            P = path[s]
            ring.append(mesh.add_pt((P[0] + Nn[0] * x + Bn[0] * y, P[1] + Nn[1] * x + Bn[1] * y, P[2] + Nn[2] * x + Bn[2] * y)))
        rings.append(ring)
    nb = len(bnd)
    for s in range(n - 1):
        a, b = rings[s], rings[s + 1]
        for i in range(nb):
            i2 = (i + 1) % nb
            mesh.add_quad(a[i], a[i2], b[i2], b[i])

    def cap(s, flip):
        T, Nn, Bn = frames[s]
        ws, hs = width_fn(s / float(n - 1)) if width_fn else (1.0, 1.0)
        idx = {}
        for kk, (i, j) in enumerate(bnd):
            idx[(i, j)] = rings[s][kk]
        P = path[s]
        for j in range(1, k):
            for i in range(1, k):
                x, y = grid[(i, j)]
                x *= ws
                y *= hs
                idx[(i, j)] = mesh.add_pt((P[0] + Nn[0] * x + Bn[0] * y, P[1] + Nn[1] * x + Bn[1] * y, P[2] + Nn[2] * x + Bn[2] * y))
        for j in range(k):
            for i in range(k):
                q = (idx[(i, j)], idx[(i + 1, j)], idx[(i + 1, j + 1)], idx[(i, j + 1)])
                mesh.add_quad(*(q[::-1] if flip else q))
    cap(0, False)
    cap(n - 1, True)
    return orient_outward(mesh)


def arc_path(cx, cy, r, a0, a1, n, z=0.0):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / (n - 1)), cy + r * math.sin(a0 + (a1 - a0) * i / (n - 1)), z) for i in range(n)]


def spiral_path(r0, r1, turns, n, z=0.0):
    out = []
    for i in range(n):
        t = i / float(n - 1)
        a = TAU * turns * t
        r = r0 + (r1 - r0) * t
        out.append((r * math.cos(a), r * math.sin(a), z))
    return out


def rod(r, length, m=2, chamfer=0.03, name=""):
    """Solid round rod along Z from 0..length (pole-free caps)."""
    return disc_solid(r, length, m=m, bevel=chamfer, name=name)


def bridge_plate(path, width, thick, k=2, taper=(1.0, 1.0), name=""):
    """Rounded plate following a path (arc or polyline), used for bridges, cocks, levers."""
    return sweep(path, width, thick, k=k, corner=0.6, width_fn=lambda t: (taper[0] + (taper[1] - taper[0]) * t, 1.0), name=name)
