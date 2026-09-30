# -*- coding: ascii -*-
"""
tc2_geo -- geometry helpers for T_cubes (pure python, no c4d import: points are tuples, polygons are index tuples).
Used twice: exec'd inside the build script (orientation test) and pasted into the Python Generator code.
All parts are built around local origin: plate bottom centre at y=0, top at y=t.
"""
import math


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _add_poly(P, Q, ids, outward, flip):
    """Append polygon ids (3 or 4 point indices); make it face `outward`, then apply global flip."""
    p0, p1, p2 = P[ids[0]], P[ids[1]], P[ids[2]]
    n = _cross(_sub(p1, p0), _sub(p2, p0))
    ids = list(ids)
    if _dot(n, outward) < 0:
        ids.reverse()
    if flip:
        ids.reverse()
    Q.append(tuple(ids))


def cbox(P, Q, cx, cy, cz, sx, sy, sz, r, flip=False):
    """Chamfered box (24 points): 6 big faces, 12 edge quads, 8 corner triangles."""
    hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
    r = max(0.0, min(r, hx * 0.95, hy * 0.95, hz * 0.95))
    base = len(P)
    h = (hx, hy, hz)
    corners = [(i, j, k) for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]
    cidx = dict((c, n) for n, c in enumerate(corners))
    # vertex (corner, axis a): on the face perpendicular to axis a, other axes inset by r
    for c in corners:
        for a in range(3):
            v = [0.0, 0.0, 0.0]
            for ax in range(3):
                v[ax] = c[ax] * (h[ax] if ax == a else h[ax] - r)
            P.append((cx + v[0], cy + v[1], cz + v[2]))

    def V(c, a):
        return base + cidx[c] * 3 + a
    ctr = (cx, cy, cz)

    def out_of(ids):
        m = [sum(P[i][t] for i in ids) / float(len(ids)) for t in range(3)]
        return _sub(tuple(m), ctr)
    for a in range(3):
        for s in (-1, 1):
            cs = [c for c in corners if c[a] == s]
            b, c2 = [t for t in range(3) if t != a]
            order = []
            for (sb, sc) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                for c in cs:
                    if c[b] == sb and c[c2] == sc:
                        order.append(V(c, a))
            _add_poly(P, Q, order, out_of(order), flip)
    for a in range(3):
        for b in range(a + 1, 3):
            c3 = 3 - a - b
            for sa in (-1, 1):
                for sb in (-1, 1):
                    def corner(sc):
                        d = {a: sa, b: sb, c3: sc}
                        return (d[0], d[1], d[2])
                    ids = [V(corner(-1), a), V(corner(1), a), V(corner(1), b), V(corner(-1), b)]
                    _add_poly(P, Q, ids, out_of(ids), flip)
    for c in corners:
        ids = [V(c, 0), V(c, 1), V(c, 2)]
        _add_poly(P, Q, ids, out_of(ids), flip)


def cyl(P, Q, cx, y0, cz, r, h, n=32, flip=False):
    """Cylinder along Y, bottom at y0 (open bottom), top cap as triangle fan."""
    base = len(P)
    for k in range(n):
        a = 2.0 * math.pi * k / n
        P.append((cx + r * math.cos(a), y0, cz + r * math.sin(a)))
    for k in range(n):
        a = 2.0 * math.pi * k / n
        P.append((cx + r * math.cos(a), y0 + h, cz + r * math.sin(a)))
    top_c = len(P)
    P.append((cx, y0 + h, cz))
    for k in range(n):
        k2 = (k + 1) % n
        ids = [base + k, base + k2, base + n + k2, base + n + k]
        mid = ((P[ids[0]][0] + P[ids[2]][0]) * 0.5 - cx, 0.0, (P[ids[0]][2] + P[ids[2]][2]) * 0.5 - cz)
        _add_poly(P, Q, ids, mid, flip)
        _add_poly(P, Q, [top_c, base + n + k, base + n + k2], (0.0, 1.0, 0.0), flip)
