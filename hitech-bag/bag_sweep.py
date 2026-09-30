# -*- coding: utf-8 -*-
"""bag_sweep: лента / лямка — скруглённое сечение вдоль пути, торцы сеткой k x k (без веера). Путь в плоскости XY:
ширина w в плоскости, толщина h по Z."""
import math
import bag_mesh as bm
from bag_mesh import Mesh, v_norm, v_cross, v_sub


def _rrect_boundary(k, w, h, corner):
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


def sweep(path, w, h, k=3, corner=0.35, col=(0.5, 0.5, 0.5)):
    n = len(path)
    grid, bnd = _rrect_boundary(k, w, h, corner)
    up = (0.0, 0.0, 1.0)
    mesh = Mesh()
    frames = []
    for s in range(n):
        p0, p1 = path[max(0, s - 1)], path[min(n - 1, s + 1)]
        T = v_norm(v_sub(p1, p0))
        Nn = v_norm(v_cross(T, up))
        Bn = v_cross(Nn, T)
        frames.append((Nn, Bn))
    rings = []
    for s in range(n):
        Nn, Bn = frames[s]
        P = path[s]
        rings.append([mesh.pt((P[0] + Nn[0] * grid[(i, j)][0] + Bn[0] * grid[(i, j)][1],
                               P[1] + Nn[1] * grid[(i, j)][0] + Bn[1] * grid[(i, j)][1],
                               P[2] + Nn[2] * grid[(i, j)][0] + Bn[2] * grid[(i, j)][1])) for (i, j) in bnd])
    nb = len(bnd)
    for s in range(n - 1):
        for i in range(nb):
            i2 = (i + 1) % nb
            mesh.face((rings[s][i], rings[s][i2], rings[s + 1][i2], rings[s + 1][i]), col)

    def cap(s):
        Nn, Bn = frames[s]
        P = path[s]
        idx = {}
        for kk, (i, j) in enumerate(bnd):
            idx[(i, j)] = rings[s][kk]
        for j in range(1, k):
            for i in range(1, k):
                x, y = grid[(i, j)]
                idx[(i, j)] = mesh.pt((P[0] + Nn[0] * x + Bn[0] * y, P[1] + Nn[1] * x + Bn[1] * y, P[2] + Nn[2] * x + Bn[2] * y))
        for j in range(k):
            for i in range(k):
                mesh.face((idx[(i, j)], idx[(i + 1, j)], idx[(i + 1, j + 1)], idx[(i, j + 1)]), col)
    cap(0)
    cap(n - 1)
    return mesh.orient()
