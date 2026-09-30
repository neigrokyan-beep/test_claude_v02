# -*- coding: utf-8 -*-
"""bf_mesh: tiny polygon-mesh toolkit for the block-frame kit of parts (pure Python, no numpy, no hou).

Faces may be any polygon; colours are per face (r, g, b). Build with any winding, then call Mesh.orient():
it makes every connected piece consistent and outward (right-hand rule). The Houdini adapter reverses the
vertex order when emitting (Houdini treats clockwise as front)."""
import math

PI = math.pi


# ----------------------------------------------------------------------------- vectors, matrices, quaternions
def v_add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def v_sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def v_mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def v_dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def v_cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def v_len(a): return math.sqrt(v_dot(a, a))


def v_norm(a):
    l = v_len(a)
    return (a[0] / l, a[1] / l, a[2] / l) if l > 1e-12 else (0.0, 0.0, 0.0)


IDENT = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def m_vec(R, v):
    return (R[0][0] * v[0] + R[0][1] * v[1] + R[0][2] * v[2],
            R[1][0] * v[0] + R[1][1] * v[1] + R[1][2] * v[2],
            R[2][0] * v[0] + R[2][1] * v[1] + R[2][2] * v[2])


def m_mul(A, B):
    return tuple(tuple(sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def m_from_axes(xa, ya, za):
    """Rotation matrix whose columns are the local axes expressed in the world frame."""
    return ((xa[0], ya[0], za[0]), (xa[1], ya[1], za[1]), (xa[2], ya[2], za[2]))


def quat_from_matrix(R):
    """(x, y, z, w) from a rotation matrix (rows)."""
    t = R[0][0] + R[1][1] + R[2][2]
    if t > 0.0:
        s = math.sqrt(t + 1.0) * 2.0
        return ((R[2][1] - R[1][2]) / s, (R[0][2] - R[2][0]) / s, (R[1][0] - R[0][1]) / s, 0.25 * s)
    if R[0][0] > R[1][1] and R[0][0] > R[2][2]:
        s = math.sqrt(1.0 + R[0][0] - R[1][1] - R[2][2]) * 2.0
        return (0.25 * s, (R[0][1] + R[1][0]) / s, (R[0][2] + R[2][0]) / s, (R[2][1] - R[1][2]) / s)
    if R[1][1] > R[2][2]:
        s = math.sqrt(1.0 + R[1][1] - R[0][0] - R[2][2]) * 2.0
        return ((R[0][1] + R[1][0]) / s, 0.25 * s, (R[1][2] + R[2][1]) / s, (R[0][2] - R[2][0]) / s)
    s = math.sqrt(1.0 + R[2][2] - R[0][0] - R[1][1]) * 2.0
    return ((R[0][2] + R[2][0]) / s, (R[1][2] + R[2][1]) / s, 0.25 * s, (R[1][0] - R[0][1]) / s)


def to_axis_rot(axis):
    """Rotation that sends local +Z to the given world axis ('x', 'y' or 'z')."""
    if axis == 'x':
        return rot_y(PI / 2)
    if axis == 'y':
        return rot_x(-PI / 2)
    return IDENT


# ----------------------------------------------------------------------------- mesh
class Mesh(object):
    def __init__(self):
        self.P = []
        self.F = []
        self.C = []

    def pt(self, p):
        self.P.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.P) - 1

    def face(self, ids, col):
        self.F.append(tuple(ids))
        self.C.append(col)

    def add(self, other, R=None, t=(0.0, 0.0, 0.0)):
        """Merge other (transformed by rotation R then translation t) into self."""
        n = len(self.P)
        for p in other.P:
            q = m_vec(R, p) if R is not None else p
            self.P.append((q[0] + t[0], q[1] + t[1], q[2] + t[2]))
        for f, c in zip(other.F, other.C):
            self.F.append(tuple(i + n for i in f))
            self.C.append(c)
        return self

    def orient(self):
        """Consistent, outward (right-hand) orientation for every connected piece."""
        F = [list(f) for f in self.F]
        n = len(F)
        ef = {}
        for fi, f in enumerate(F):
            for k in range(len(f)):
                a, b = f[k], f[(k + 1) % len(f)]
                ef.setdefault((a, b) if a < b else (b, a), []).append(fi)
        seen = [False] * n
        for s in range(n):
            if seen[s]:
                continue
            comp = [s]
            seen[s] = True
            stack = [s]
            while stack:
                fi = stack.pop()
                f = F[fi]
                for k in range(len(f)):
                    a, b = f[k], f[(k + 1) % len(f)]
                    for fj in ef[(a, b) if a < b else (b, a)]:
                        if fj == fi or seen[fj]:
                            continue
                        g = F[fj]
                        for m in range(len(g)):
                            if g[m] == a and g[(m + 1) % len(g)] == b:
                                F[fj] = g[::-1]
                                break
                        seen[fj] = True
                        stack.append(fj)
                        comp.append(fj)
            vol = 0.0
            for fi in comp:
                f = F[fi]
                p0 = self.P[f[0]]
                for k in range(1, len(f) - 1):
                    vol += v_dot(p0, v_cross(self.P[f[k]], self.P[f[k + 1]]))
            if vol < 0.0:
                for fi in comp:
                    F[fi] = F[fi][::-1]
        self.F = [tuple(f) for f in F]
        return self

    def bbox(self):
        xs = [p[0] for p in self.P]
        ys = [p[1] for p in self.P]
        zs = [p[2] for p in self.P]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


# ----------------------------------------------------------------------------- primitives (local axis = Z unless stated)
def cyl(r, L, seg=8, r2=None, col=(0.6, 0.6, 0.6), caps=True, z0=None, axis='z', rot=0.0):
    """Cylinder / cone along Z from -L/2 to +L/2 (or z0..z0+L when z0 is given)."""
    m = Mesh()
    r2 = r if r2 is None else r2
    a, b = (-L / 2.0, L / 2.0) if z0 is None else (z0, z0 + L)
    ra, rb = [], []
    for i in range(seg):
        ang = rot + 2.0 * PI * i / seg
        c, s = math.cos(ang), math.sin(ang)
        ra.append(m.pt((r * c, r * s, a)))
        rb.append(m.pt((r2 * c, r2 * s, b)))
    for i in range(seg):
        j = (i + 1) % seg
        m.face((ra[i], ra[j], rb[j], rb[i]), col)
    if caps:
        m.face(tuple(reversed(ra)), col)
        m.face(tuple(rb), col)
    m.orient()
    if axis != 'z':
        R = to_axis_rot(axis)
        m.P = [m_vec(R, p) for p in m.P]
    return m


def prism(poly, z0, z1, col):
    """Extrude a 2D polygon [(x, y), ...] between z0 and z1."""
    m = Mesh()
    lo = [m.pt((x, y, z0)) for x, y in poly]
    hi = [m.pt((x, y, z1)) for x, y in poly]
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        m.face((lo[i], lo[j], hi[j], hi[i]), col)
    m.face(tuple(reversed(lo)), col)
    m.face(tuple(hi), col)
    return m.orient()


def hex_poly(af):
    r = af / math.sqrt(3.0)
    return [(r * math.cos(PI / 3 * i), r * math.sin(PI / 3 * i)) for i in range(6)]


def box(sx, sy, sz, col, bev=0.0, center=(0.0, 0.0, 0.0)):
    """Box (optionally chamfered). Centered at `center`."""
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    m = Mesh()
    if bev <= 1e-9:
        pts = {}
        for ix in (-1, 1):
            for iy in (-1, 1):
                for iz in (-1, 1):
                    pts[(ix, iy, iz)] = m.pt((center[0] + ix * hx, center[1] + iy * hy, center[2] + iz * hz))
        for a in range(3):
            for s in (-1, 1):
                ids = []
                for (u, v) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    k = [0, 0, 0]
                    k[a] = s
                    k[(a + 1) % 3] = u
                    k[(a + 2) % 3] = v
                    ids.append(pts[tuple(k)])
                m.face(ids, col)
        return m.orient()
    b = min(bev, hx * 0.98, hy * 0.98, hz * 0.98)
    h = (hx, hy, hz)
    V = {}
    for ix in (-1, 1):
        for iy in (-1, 1):
            for iz in (-1, 1):
                c = (ix, iy, iz)
                for a in range(3):
                    p = [center[0] + ix * hx, center[1] + iy * hy, center[2] + iz * hz]
                    for o in range(3):
                        if o != a:
                            p[o] -= c[o] * b
                    V[(c, a)] = m.pt(p)
    for a in range(3):
        for s in (-1, 1):
            ids = []
            for (u, v) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                k = [0, 0, 0]
                k[a] = s
                k[(a + 1) % 3] = u
                k[(a + 2) % 3] = v
                ids.append(V[(tuple(k), a)])
            m.face(ids, col)
    for a in range(3):                       # edge quads: edge parallel to axis c between faces a and b
        b_ax = (a + 1) % 3
        c_ax = (a + 2) % 3
        for sa in (-1, 1):
            for sb in (-1, 1):
                ids = []
                for sc in (-1, 1):
                    k = [0, 0, 0]
                    k[a], k[b_ax], k[c_ax] = sa, sb, sc
                    ids.append(V[(tuple(k), a)])
                for sc in (1, -1):
                    k = [0, 0, 0]
                    k[a], k[b_ax], k[c_ax] = sa, sb, sc
                    ids.append(V[(tuple(k), b_ax)])
                m.face(ids, col)
    for ix in (-1, 1):
        for iy in (-1, 1):
            for iz in (-1, 1):
                c = (ix, iy, iz)
                m.face((V[(c, 0)], V[(c, 1)], V[(c, 2)]), col)
    return m.orient()


def annular_sector(ri, ro, a0, a1, n, x0, x1, col):
    """Annular sector (in the YZ plane, angle from +Y towards +Z) extruded along X from x0 to x1."""
    poly = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        poly.append((ro * math.cos(a), ro * math.sin(a)))
    for i in range(n, -1, -1):
        a = a0 + (a1 - a0) * i / n
        poly.append((ri * math.cos(a), ri * math.sin(a)))
    m = prism(poly, x0, x1, col)
    R = ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))    # local (u, v, w) -> world (w, u, v): w = X, u = Y, v = Z
    m.P = [m_vec(R, p) for p in m.P]
    return m


def hexbolt(d, L, col_head, col_shaft, hh=None):
    """Hex bolt with washer. Origin at the underside of the head, axis +Z is the head side (outward)."""
    af = d * 1.7
    hh = d * 0.7 if hh is None else hh
    m = Mesh()
    m.add(prism(hex_poly(af), 0.0, hh, col_head))
    m.add(cyl(d * 1.1, d * 0.25, seg=10, col=col_shaft, z0=-d * 0.25))
    m.add(cyl(d * 0.5, L, seg=8, col=col_shaft, z0=-L - d * 0.25))
    return m


def rot_quat_axis(axis, ang):
    ax = v_norm(axis)
    s = math.sin(ang / 2.0)
    return (ax[0] * s, ax[1] * s, ax[2] * s, math.cos(ang / 2.0))


def q_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def q_rot(q, v):
    x, y, z, w = q
    t = v_mul(v_cross((x, y, z), v), 2.0)
    return v_add(v_add(v, v_mul(t, w)), v_cross((x, y, z), t))
