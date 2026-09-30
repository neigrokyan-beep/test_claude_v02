# -*- coding: utf-8 -*-
"""bag_geo: угловатая нагрудная / поясная сумка с карманом-девайсом. Чистый Python (без hou), сантиметры.

Только квады, замкнутые детали, вершины валентности <= 4, без полюсов (крышки — сетки Кунса на кольце, не веера):
  solid_from_outline   тело из кольца контура: слои (отступ, z) от задней кромки к передней, купол, крышки Кунса
  ring_plate           пластина с отверстием: радиальные ряды между внешним и внутренним контуром, толщина
  squircle / poly ring контуры: суперэллипс (скруглённый прямоугольник) и скруглённый многоугольник
Система координат детали: X вправо, Y вверх, Z к зрителю (наружу), задняя стенка сумки на z = 0.
"""
import math
import bag_mesh as bm
from bag_mesh import Mesh, v_norm

PI = math.pi

# ------------------------------------------------------------------------------------------- контуры


def _resample(poly, N, closed=True):
    """N точек с равным шагом по длине вдоль замкнутой ломаной poly (список (x, y))."""
    pts = list(poly) + ([poly[0]] if closed else [])
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seg)
    out = []
    for k in range(N):
        s = total * k / N
        i = 0
        while i < len(seg) - 1 and s > seg[i]:
            s -= seg[i]
            i += 1
        t = s / seg[i] if seg[i] > 1e-12 else 0.0
        out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t))
    return out


def squircle(a, b, n, N, start_deg=45.0):
    """N точек суперэллипса |x/a|^n + |y/b|^n = 1 с равным шагом по длине, против часовой, старт на start_deg."""
    M = 3000
    dense = []
    for i in range(M):
        t = math.radians(start_deg) + 2.0 * PI * i / M
        c, s = math.cos(t), math.sin(t)
        dense.append((a * math.copysign(abs(c) ** (2.0 / n), c), b * math.copysign(abs(s) ** (2.0 / n), s)))
    return _resample(dense, N)


def round_poly(poly, r, N, arc=8):
    """скруглённый многоугольник (радиус r у каждой вершины), N точек по длине, против часовой."""
    n = len(poly)
    dense = []
    for i in range(n):
        p0, p1, p2 = poly[i - 1], poly[i], poly[(i + 1) % n]
        d0, d2 = v2_norm((p0[0] - p1[0], p0[1] - p1[1])), v2_norm((p2[0] - p1[0], p2[1] - p1[1]))
        ang = math.acos(max(-1.0, min(1.0, d0[0] * d2[0] + d0[1] * d2[1])))
        if ang < 1e-3 or abs(ang - PI) < 1e-3:
            dense.append(p1)
            continue
        t = min(r / math.tan(ang / 2.0), 0.45 * math.dist(p0, p1), 0.45 * math.dist(p1, p2))
        rr = t * math.tan(ang / 2.0)
        a = (p1[0] + d0[0] * t, p1[1] + d0[1] * t)
        b = (p1[0] + d2[0] * t, p1[1] + d2[1] * t)
        bis = v2_norm((d0[0] + d2[0], d0[1] + d2[1]))
        cen = (p1[0] + bis[0] * rr / math.sin(ang / 2.0), p1[1] + bis[1] * rr / math.sin(ang / 2.0))
        a0 = math.atan2(a[1] - cen[1], a[0] - cen[0])
        a1 = math.atan2(b[1] - cen[1], b[0] - cen[0])
        da = (a1 - a0 + PI) % (2 * PI) - PI
        for k in range(arc + 1):
            th = a0 + da * k / arc
            dense.append((cen[0] + rr * math.cos(th), cen[1] + rr * math.sin(th)))
    if signed_area(dense) < 0:
        dense.reverse()
    return _resample(dense, N)


def v2_norm(v):
    l = math.hypot(v[0], v[1])
    return (v[0] / l, v[1] / l) if l > 1e-12 else (0.0, 0.0)


def signed_area(p):
    return 0.5 * sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))


def inset(pts, d):
    """сдвинуть замкнутый контур (против часовой) внутрь на d по средним нормалям."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        e0 = v2_norm((p1[0] - p0[0], p1[1] - p0[1]))
        e1 = v2_norm((p2[0] - p1[0], p2[1] - p1[1]))
        n0, n1 = (-e0[1], e0[0]), (-e1[1], e1[0])          # внутрь для CCW
        nn = v2_norm((n0[0] + n1[0], n0[1] + n1[1]))
        k = max(0.45, nn[0] * n0[0] + nn[1] * n0[1])
        out.append((p1[0] + nn[0] * d / k, p1[1] + nn[1] * d / k))
    return out


# ------------------------------------------------------------------------------------------- тела


def coons_grid(ring, m):
    """сетка (m+1)x(m+1) по кольцу из 4m точек (Кунс). Возвращает (grid[j][i] -> (x, y), ring_index(i, j) или None)."""
    A = [ring[k] for k in range(0, m + 1)]
    B = [ring[k] for k in range(m, 2 * m + 1)]
    C = [ring[k] for k in range(2 * m, 3 * m + 1)]
    D = [ring[k % (4 * m)] for k in range(3 * m, 4 * m + 1)]
    bottom, right = A, B
    top = C[::-1]
    left = D[::-1]
    c0, c1, c2, c3 = A[0], A[m], C[0], C[m]
    grid = []
    for j in range(m + 1):
        v = j / float(m)
        row = []
        for i in range(m + 1):
            u = i / float(m)
            x = (1 - v) * bottom[i][0] + v * top[i][0] + (1 - u) * left[j][0] + u * right[j][0] - (
                (1 - u) * (1 - v) * c0[0] + u * (1 - v) * c1[0] + u * v * c2[0] + (1 - u) * v * c3[0])
            y = (1 - v) * bottom[i][1] + v * top[i][1] + (1 - u) * left[j][1] + u * right[j][1] - (
                (1 - u) * (1 - v) * c0[1] + u * (1 - v) * c1[1] + u * v * c2[1] + (1 - u) * v * c3[1])
            row.append((x, y))
        grid.append(row)

    def ring_idx(i, j):
        if j == 0:
            return i
        if i == m:
            return m + j
        if j == m:
            return 2 * m + (m - i)
        if i == 0:
            return (3 * m + (m - j)) % (4 * m)
        return None
    return grid, ring_idx


def _cap(mesh, ring_ids, ring_pts, m, z_fn, col):
    """крышка Кунса на кольце (индексы точек ring_ids уже в mesh)."""
    grid, ridx = coons_grid(ring_pts, m)
    ids = {}
    for j in range(m + 1):
        for i in range(m + 1):
            r = ridx(i, j)
            if r is not None:
                ids[(i, j)] = ring_ids[r]
            else:
                x, y = grid[j][i]
                ids[(i, j)] = mesh.pt((x, y, z_fn(i / float(m), j / float(m), x, y)))
    for j in range(m):
        for i in range(m):
            mesh.face((ids[(i, j)], ids[(i + 1, j)], ids[(i + 1, j + 1)], ids[(i, j + 1)]), col)


def solid_from_outline(outline, layers, m, dome=0.0, col=(0.6, 0.6, 0.6), gap_cols=None, back_col=None, front_col=None, z0=0.0):
    """Замкнутое тело: кольца outline со смещением внутрь и z из layers [(inset, z), ...] от задней кромки к передней.
    Задняя крышка плоская на первом слое, передняя — с куполом dome (высота в центре). gap_cols[j] — цвет j-го пояса."""
    N = len(outline)
    assert N == 4 * m
    mesh = Mesh()
    rings, pts_xy = [], []
    for (d, z) in layers:
        ring2d = inset(outline, d) if d > 1e-9 else list(outline)
        pts_xy.append(ring2d)
        rings.append([mesh.pt((x, y, z0 + z)) for x, y in ring2d])
    for j in range(len(layers) - 1):
        c = gap_cols[j] if gap_cols else col
        for i in range(N):
            k = (i + 1) % N
            mesh.face((rings[j][i], rings[j][k], rings[j + 1][k], rings[j + 1][i]), c)
    zf = z0 + layers[-1][1]
    _cap(mesh, rings[0], pts_xy[0], m, lambda u, v, x, y: z0 + layers[0][1], back_col or col)
    _cap(mesh, rings[-1], pts_xy[-1], m,
         lambda u, v, x, y: zf + dome * (1.0 - min(1.0, ((2 * u - 1) ** 2 + (2 * v - 1) ** 2) / 2.0)), front_col or col)
    return mesh.orient()


def ring_plate(outer, inner, t, rows=3, col=(0.5, 0.5, 0.5), z0=0.0, inner_col=None):
    """Пластина с отверстием: оба контура по N точек (соответствуют по индексу), rows радиальных поясов, толщина t."""
    N = len(outer)
    assert len(inner) == N
    mesh = Mesh()
    front, back = [], []
    for r in range(rows + 1):
        f = r / float(rows)
        rf, rb = [], []
        for k in range(N):
            x = inner[k][0] + (outer[k][0] - inner[k][0]) * f
            y = inner[k][1] + (outer[k][1] - inner[k][1]) * f
            rf.append(mesh.pt((x, y, z0 + t)))
            rb.append(mesh.pt((x, y, z0)))
        front.append(rf)
        back.append(rb)
    for r in range(rows):
        for k in range(N):
            k2 = (k + 1) % N
            mesh.face((front[r][k], front[r][k2], front[r + 1][k2], front[r + 1][k]), col)
            mesh.face((back[r][k], back[r][k2], back[r + 1][k2], back[r + 1][k]), col)
    for k in range(N):
        k2 = (k + 1) % N
        mesh.face((front[0][k], front[0][k2], back[0][k2], back[0][k]), inner_col or col)
        mesh.face((front[rows][k], front[rows][k2], back[rows][k2], back[rows][k]), col)
    return mesh.orient()


def xform(mesh, R=None, t=(0.0, 0.0, 0.0)):
    out = Mesh()
    out.add(mesh, R, t)
    return out


# ------------------------------------------------------------------------------------------- сама сумка
S = 0.072        # см на пиксель референса (схема куртки)
RED = (0.66, 0.07, 0.09)
RED_D = (0.42, 0.045, 0.06)
BLACK = (0.045, 0.045, 0.05)
ORANGE = (0.96, 0.38, 0.08)
WINDOW = (0.14, 0.045, 0.04)
CREAM = (0.93, 0.92, 0.88)
DARK = (0.10, 0.10, 0.11)


def px(p, c=(376.0, 372.0)):
    """пиксели схемы (y вниз) -> см относительно центра корпуса (y вверх)."""
    return ((p[0] - c[0]) * S, -(p[1] - c[1]) * S)


def default_params():
    return dict(depth=8.0, scale=1.0, pod=1, strap=1, belt=1, loops=1, color=0)


COLOR_SETS = [
    dict(body=RED, body2=RED_D, strap=BLACK, pod=ORANGE),                      # печатный красный, как кроссовок
    dict(body=(0.10, 0.11, 0.13), body2=(0.06, 0.065, 0.075), strap=(0.02, 0.02, 0.025), pod=ORANGE),   # чёрный техно
    dict(body=(0.70, 0.71, 0.74), body2=(0.5, 0.51, 0.54), strap=(0.06, 0.06, 0.07), pod=ORANGE),        # светло-серый
]


def build(params=None):
    """Возвращает {имя: Mesh}. Все размеры в см; порядок и имена частей — как на схеме: корпус, клапан, ушко, лямка, карман, девайс."""
    P = default_params()
    P.update(params or {})
    D = float(P['depth'])
    cs = COLOR_SETS[int(P['color']) % len(COLOR_SETS)]
    parts = {}

    # --- корпус: скруглённый семиугольник по схеме
    body_px = [(140, 330), (300, 192), (585, 190), (612, 215), (612, 550), (285, 555), (140, 470)]
    body = [px(p) for p in body_px]
    outline = round_poly(body, 1.3, 64)
    layers = [(0.0, 0.0), (0.0, 0.62 * D), (0.0, 0.9 * D), (0.22, 0.965 * D), (0.6, D)]
    parts['Bag_Body'] = solid_from_outline(outline, layers, 16, dome=0.3, col=cs['body'],
                                           gap_cols=[cs['body2'], cs['body'], cs['body'], cs['body']], back_col=cs['body2'])

    # --- клапан-клин сверху (откинут назад на 22 градуса вокруг верхней кромки корпуса)
    flap_px = [(300, 186), (416, 194), (526, 58), (588, 88), (603, 190), (586, 192)]
    flap = round_poly([px(p) for p in flap_px], 0.9, 48)
    fl = solid_from_outline(flap, [(0.0, 0.0), (0.0, 1.2), (0.0, 1.7), (0.18, 1.9), (0.45, 2.0)], 12, dome=0.12, col=cs['body'],
                            gap_cols=[cs['body2'], cs['body'], cs['body'], cs['body']], back_col=cs['body2'])
    hinge_y = px((0, 190))[1]
    Rf = bm.rot_x(math.radians(-22.0))
    fl2 = Mesh()
    fl2.P = []
    tmp = xform(fl, None, (0.0, -hinge_y, -0.0))
    tmp = xform(tmp, Rf, (0.0, hinge_y, D * 0.88))
    parts['Bag_Flap'] = tmp

    # --- ушко со щелью (над лямкой, слева сверху)
    tc = px((250, 164))
    tab_out = squircle(3.7, 4.1, 3.0, 48)
    tab_in = squircle(1.0, 2.6, 6.0, 48)
    tab = ring_plate(tab_out, tab_in, 0.7, rows=3, col=cs['body2'], inner_col=DARK)
    parts['Bag_Tab'] = xform(tab, bm.rot_z(math.radians(-8.0)), (tc[0], tc[1], D * 0.95))

    # --- лямка (диагональ вдоль верхней левой кромки) и фиксатор
    if int(P['strap']):
        a, b = px((100, 312)), px((338, 176))
        path = [(a[0] + (b[0] - a[0]) * s / 6.0, a[1] + (b[1] - a[1]) * s / 6.0, D + 0.40) for s in range(7)]
        import bag_sweep
        parts['Bag_Strap'] = bag_sweep.sweep(path, 2.7, 0.55, k=3, corner=0.35, col=cs['strap'])
        kc = px((280, 220))
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        kp = ring_plate(squircle(2.4, 1.6, 6.0, 32), squircle(1.6, 0.85, 8.0, 32), 0.9, rows=2, col=cs['strap'], inner_col=DARK)
        parts['Bag_Keeper'] = xform(kp, bm.rot_z(ang), (kc[0], kc[1], D + 0.55))

    # --- карман под девайс + сам девайс (справа, вертикальная капсула)
    if int(P['pod']):
        pc = px((552, 405))
        pw, ph = 4.3, 10.2
        pocket = ring_plate(squircle(pw + 1.35, ph + 1.05, 5.0, 48), squircle(pw + 0.55, ph + 0.35, 5.0, 48), 1.7, rows=3,
                            col=cs['body2'], inner_col=DARK)
        parts['Bag_Pocket'] = xform(pocket, None, (pc[0], pc[1], D * 0.72))
        dev_outline = squircle(pw, ph, 5.0, 48)
        dz = 3.4
        dl = [(0.0, 0.0), (0.0, 0.6 * dz), (0.0, 0.9 * dz), (0.2, 0.97 * dz), (0.5, dz), (0.9, dz), (1.1, dz - 0.05), (1.1, dz - 0.3)]
        gcols = [cs['pod']] * 7
        dev = solid_from_outline(dev_outline, dl, 12, dome=0.0, col=cs['pod'], gap_cols=gcols, back_col=cs['pod'], front_col=WINDOW)
        parts['Bag_Device'] = xform(dev, None, (pc[0], pc[1], D * 0.72 - 0.4))
        # кнопки и ползунок на верхней грани девайса (как у Chatbox)
        top_y = ph - 0.05
        zc = D * 0.72 - 0.4 + dz * 0.5
        b1 = ring_plate(squircle(0.85, 0.85, 2.0, 24), squircle(0.35, 0.35, 2.0, 24), 0.32, rows=2, col=CREAM, inner_col=DARK)
        Ry = bm.rot_x(math.radians(-90.0))
        parts['Bag_BtnRound'] = xform(b1, Ry, (pc[0] - 2.05, pc[1] + top_y, zc))
        b2 = ring_plate(squircle(1.55, 0.6, 5.0, 24), squircle(1.0, 0.25, 5.0, 24), 0.3, rows=2, col=CREAM, inner_col=DARK)
        parts['Bag_BtnPill'] = xform(b2, Ry, (pc[0] + 0.45, pc[1] + top_y, zc))
        slot = ring_plate(squircle(1.15, 0.5, 6.0, 24), squircle(0.75, 0.22, 6.0, 24), 0.22, rows=2, col=DARK, inner_col=DARK)
        parts['Bag_Slot'] = xform(slot, Ry, (pc[0] + 2.75, pc[1] + top_y - 0.05, zc))
        knob = bm.box(0.7, 0.45, 0.55, CREAM, bev=0.08)
        parts['Bag_Slider'] = xform(knob, None, (pc[0] + 2.55, pc[1] + top_y + 0.2, zc))

    # --- тянущая пластина слева от кармана (светлый прямоугольник на схеме)
    pl = ring_plate(squircle(1.8, 3.4, 6.0, 32), squircle(0.001 + 1.2, 2.8, 6.0, 32), 0.5, rows=2, col=cs['body2'], inner_col=cs['body'])
    parts['Bag_PullPlate'] = xform(pl, None, (px((465, 345))[0], px((465, 345))[1], D * 0.86))

    # --- пояс и петли сзади
    if int(P['loops']):
        for i, sx in enumerate((-6.5, 6.5)):
            lp = ring_plate(squircle(3.3, 1.35, 6.0, 32), squircle(2.7, 0.75, 6.0, 32), 0.7, rows=2, col=cs['strap'], inner_col=DARK)
            parts['Bag_Loop%d' % (i + 1)] = xform(lp, bm.rot_x(math.radians(90.0)), (sx, -1.0, -0.2))
    if int(P['belt']):
        import bag_sweep
        path = [(-26.0 + 52.0 * s / 8.0, -1.0, -1.1) for s in range(9)]
        parts['Bag_Belt'] = bag_sweep.sweep(path, 4.2, 0.6, k=3, corner=0.3, col=cs['strap'])
    sc = float(P['scale'])
    if abs(sc - 1.0) > 1e-9:
        for k, m in parts.items():
            parts[k] = Mesh()
            parts[k].P = [(p[0] * sc, p[1] * sc, p[2] * sc) for p in m.P]
            parts[k].F, parts[k].C = m.F, m.C
    return parts


if __name__ == '__main__':
    parts = build()
    tot_p = tot_f = 0
    for n, m in parts.items():
        E = {}
        for f in m.F:
            for i in range(len(f)):
                e = (f[i], f[(i + 1) % len(f)])
                E[e] = E.get(e, 0) + 1
        bad = sum(1 for e, c in E.items() if c != 1 or (e[1], e[0]) not in E)
        nq = sum(1 for f in m.F if len(f) == 4)
        val = {}
        for f in m.F:
            for i in f:
                val[i] = val.get(i, 0) + 1
        mx = max(val.values()) if val else 0
        lo, hi = m.bbox()
        print('%-14s pts %5d faces %5d quads %5d bad-edges %d max-valence %d size %s' % (
            n, len(m.P), len(m.F), nq, bad, mx, tuple(round(b - a, 1) for a, b in zip(lo, hi))))
        tot_p += len(m.P)
        tot_f += len(m.F)
    print('total pts %d faces %d' % (tot_p, tot_f))
