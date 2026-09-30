# -*- coding: utf-8 -*-
"""bf_layout: procedural layout of a scaffold-like block frame. Pure Python: parameters in, placements out.

generate(params) -> (items, info). Every item is a dict: v (variant key for bf_kit), P, q (x,y,z,w), s (scale),
cls, order (assembly order 0..1), fdir (approach direction), spin (bolt turns), lvl.
Two seeds: seed_layout (cells, sizes, heights) and seed_parts (panels, braces, stairs, ladders, order noise)."""
import math
import random
import bf_mesh as bm
import bf_kit as kit
from bf_mesh import rot_x, rot_y, rot_z, m_mul, m_vec, m_from_axes, quat_from_matrix, IDENT, PI

DEFAULTS = dict(seed_layout=7, seed_parts=3, nx=6, ny=4, nz=5, cell=1.2, cell_var=0.35, fill=0.62, height_bias=1.0,
                overhang=0.15, tube_r=0.024, lift=0.0, foot_h=0.10, wall_density=0.45, interior_density=0.12,
                floor_density=0.55, roof_density=0.35, ground_floor=0.2, w_perf=1.0, w_round=0.8, w_mesh=0.7,
                w_louver=0.5, w_solid=0.3, panel_t=0.012, perf_pitch=0.075, brace_prob=0.25, stair_prob=0.35,
                ladder_prob=0.25, clips=1, bolts=1)

CLS = dict(foot=0, tube=1, hub=2, brace=3, clamp=4, panel=5, stair=6, clip=7, bolt=8)
GAP = 0.004


def q5(x):
    return max(0.3, round(x / 0.05) * 0.05)


def mm(x):
    return int(round(x * 1000.0))


def make_occ(p, rng):
    nx, ny, nz = p['nx'], p['ny'], p['nz']
    bumps = [(rng.uniform(0, nx - 1), rng.uniform(0, nz - 1), rng.uniform(0.9, 2.2), rng.uniform(0.6, 1.0))
             for _ in range(rng.randint(2, 4))]

    def field(i, k):
        return min(1.0, sum(a * math.exp(-((i - cx) ** 2 + (k - cz) ** 2) / (2 * s * s)) for cx, cz, s, a in bumps))

    thr = (1.0 - p['fill']) * 0.9
    heights = {}
    for i in range(nx):
        for k in range(nz):
            n = field(i, k) + rng.uniform(-0.08, 0.08)
            if n > thr:
                h = 1 + int((n - thr) / (1.0 - thr + 1e-6) * ny * p['height_bias'])
                heights[(i, k)] = max(1, min(ny, h))
    seen, best = set(), []
    for c in sorted(heights):
        if c in seen:
            continue
        comp, stack = [], [c]
        seen.add(c)
        while stack:
            a = stack.pop()
            comp.append(a)
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                b = (a[0] + d[0], a[1] + d[1])
                if b in heights and b not in seen:
                    seen.add(b)
                    stack.append(b)
        if len(comp) > len(best):
            best = comp
    if len(best) < 2:
        cx, cz = nx // 2, nz // 2
        best = [(cx, cz), (min(nx - 1, cx + 1), cz)]
        heights = {c: max(1, min(ny, 2)) for c in best}
    occ = set()
    for (i, k) in best:
        for j in range(heights[(i, k)]):
            occ.add((i, j, k))
    extra = []
    for j in range(1, ny):
        for i in range(nx):
            for k in range(nz):
                if (i, j, k) in occ or (i, j - 1, k) in occ:
                    continue
                if any((i + d[0], j, k + d[1]) in occ for d in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    if rng.random() < p['overhang']:
                        extra.append((i, j, k))
    occ.update(extra)
    return occ


def generate(params):
    p = dict(DEFAULTS)
    p.update(params or {})
    rl = random.Random(int(p['seed_layout']))
    rp = random.Random(int(p['seed_parts']))
    nx, ny, nz = int(p['nx']), int(p['ny']), int(p['nz'])
    r = float(p['tube_r'])
    hh = 1.35 * r
    base = p['lift'] + p['foot_h']

    def sizes(n):
        ch = sorted(set(q5(p['cell'] * (1.0 + d)) for d in (-p['cell_var'], 0.0, p['cell_var'])))
        return [rl.choice(ch) for _ in range(n)]

    sx, sy, sz = sizes(nx), sizes(ny), sizes(nz)
    xs = [0.0]
    for s in sx:
        xs.append(xs[-1] + s)
    zs = [0.0]
    for s in sz:
        zs.append(zs[-1] + s)
    ox, oz = xs[-1] / 2.0, zs[-1] / 2.0
    xs = [x - ox for x in xs]
    zs = [z - oz for z in zs]
    ys = [base]
    for s in sy:
        ys.append(ys[-1] + s)
    ymin, ymax = 0.0, ys[-1]

    def V(i, j, k):
        return (xs[i], ys[j], zs[k])

    def lvl(y):
        return max(0.0, min(0.999, (y - ymin) / (ymax - ymin + 1e-6)))

    occ = make_occ(p, rl)
    items = []

    def add(v, P, R, cls, order, fdir=(0.0, 1.0, 0.0), spin=0.0, lv=0.0):
        items.append({'v': v, 'P': (P[0], P[1], P[2]), 'q': quat_from_matrix(R), 's': (1.0, 1.0, 1.0), 'cls': CLS[cls],
                      'order': max(0.0, min(1.0, order)), 'fdir': fdir, 'spin': spin, 'lvl': lv})

    edges = set()
    for (i, j, k) in occ:
        for dj in (0, 1):
            for dk in (0, 1):
                edges.add(('x', i, j + dj, k + dk))
        for di in (0, 1):
            for dk in (0, 1):
                edges.add(('y', i + di, j, k + dk))
        for di in (0, 1):
            for dj in (0, 1):
                edges.add(('z', i + di, j + dj, k))
    vmask = {}
    for (a, i, j, k) in sorted(edges):
        v0 = (i, j, k)
        v1 = (i + (a == 'x'), j + (a == 'y'), k + (a == 'z'))
        bit = {'x': 0, 'y': 2, 'z': 4}[a]
        vmask[v0] = vmask.get(v0, 0) | (1 << bit)
        vmask[v1] = vmask.get(v1, 0) | (1 << (bit + 1))
    for (a, i, j, k) in sorted(edges):
        v0 = V(i, j, k)
        v1 = V(i + (a == 'x'), j + (a == 'y'), k + (a == 'z'))
        L = math.dist(v0, v1)
        Lt = L - 2.0 * hh
        mid = tuple((v0[t] + v1[t]) / 2.0 for t in range(3))
        lv = lvl(mid[1])
        o = 0.06 + 0.42 * lv + rp.random() * 0.06
        if a == 'y':
            key = 'tube_r%d_l%d_c%d' % (mm(r), mm(Lt), kit.cid('orange'))
            R = rot_z(PI / 2)
            fd = (0.0, 1.0, 0.0)
        elif a == 'x':
            key = 'stube_w%d_l%d_c%d' % (mm(r * 1.7), mm(Lt), kit.cid('teal'))
            R = IDENT
            fd = (1.0, 0.0, 0.0) if rp.random() < 0.5 else (-1.0, 0.0, 0.0)
        else:
            key = 'tube_r%d_l%d_c%d' % (mm(r), mm(Lt), kit.cid('cyan'))
            R = rot_y(-PI / 2)
            fd = (0.0, 0.0, 1.0) if rp.random() < 0.5 else (0.0, 0.0, -1.0)
        add(key, mid, R, 'tube', o, fd, 0.0, lv)
    for (i, j, k), mask in sorted(vmask.items()):
        P = V(i, j, k)
        lv = lvl(P[1])
        o = 0.10 + 0.42 * lv + rp.random() * 0.05
        pair = {0b000011: 'x', 0b001100: 'y', 0b110000: 'z'}.get(mask)
        if pair:
            R = {'x': IDENT, 'y': rot_z(PI / 2), 'z': rot_y(-PI / 2)}[pair]
            add('sleeve_r%d_c%d' % (mm(r), kit.cid('yellow')), P, R, 'hub', o, (0.0, 1.0, 0.0), 0.0, lv)
        else:
            add('hub_m%d_r%d' % (mask, mm(r)), P, IDENT, 'hub', o, (0.0, 1.0, 0.0), 0.0, lv)
        if j == 0 and (mask >> 2) & 1:
            fo = rp.random() * 0.12
            add('foot_r%d_h%d' % (mm(r), mm(p['foot_h'])), (P[0], 0.0, P[2]), IDENT, 'foot', fo, (0.0, 1.0, 0.0), 0.0, 0.0)
            if p['lift'] > 0.01:
                leg = 'tube_r%d_l%d_c%d' % (mm(r), mm(p['lift']), kit.cid('grey'))
                add(leg, (P[0], p['foot_h'] + p['lift'] / 2.0, P[2]), rot_z(PI / 2), 'tube', fo + 0.02, (0.0, 1.0, 0.0), 0.0, 0.0)

    faces = set()
    for (i, j, k) in occ:
        faces.update([('x', i, j, k), ('x', i + 1, j, k), ('y', i, j, k), ('y', i, j + 1, k), ('z', i, j, k), ('z', i, j, k + 1)])

    def cells_of(f):
        a, i, j, k = f
        if a == 'x':
            return (i - 1, j, k), (i, j, k)
        if a == 'y':
            return (i, j - 1, k), (i, j, k)
        return (i, j, k - 1), (i, j, k)

    def span(f):
        a, i, j, k = f
        if a == 'x':
            return sz[k], sy[j]
        if a == 'y':
            return sx[i], sz[k]
        return sx[i], sy[j]

    def center(f):
        a, i, j, k = f
        if a == 'x':
            return (xs[i], (ys[j] + ys[j + 1]) / 2.0, (zs[k] + zs[k + 1]) / 2.0)
        if a == 'y':
            return ((xs[i] + xs[i + 1]) / 2.0, ys[j], (zs[k] + zs[k + 1]) / 2.0)
        return ((xs[i] + xs[i + 1]) / 2.0, (ys[j] + ys[j + 1]) / 2.0, zs[k])

    def face_R(a, s):
        """Panel frame: local X width, Y height, Z outward (s = +-1 along the face axis)."""
        if a == 'x':
            return m_from_axes((0.0, 0.0, -float(s)), (0.0, 1.0, 0.0), (float(s), 0.0, 0.0))
        if a == 'z':
            return m_from_axes((float(s), 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, float(s)))
        return m_from_axes((1.0, 0.0, 0.0), (0.0, 0.0, -float(s)), (0.0, float(s), 0.0))

    def normal_of(R):
        return (R[0][2], R[1][2], R[2][2])

    nopanel = set()
    for c in sorted(occ):
        i, j, k = c
        if (i, j + 1, k) in occ and rp.random() < p['stair_prob']:
            fy = ('y', i, j + 1, k)
            if fy in nopanel:
                continue
            nopanel.add(fy)
            along = 'x' if rp.random() < 0.5 else 'z'
            sg = 1.0 if rp.random() < 0.5 else -1.0
            run = sx[i] if along == 'x' else sz[k]
            wid = (sz[k] if along == 'x' else sx[i]) - 0.16
            rise = sy[j] - 0.03
            cxy = ((xs[i] + xs[i + 1]) / 2.0, ys[j] + 0.012, (zs[k] + zs[k + 1]) / 2.0)
            if along == 'x':
                R = m_from_axes((0.0, 0.0, -sg), (0.0, 1.0, 0.0), (sg, 0.0, 0.0))
            else:
                R = m_from_axes((sg, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, sg))
            lv = lvl(cxy[1])
            add('stair_w%d_l%d_h%d' % (mm(wid), mm(run - 0.16), mm(rise)), cxy, R, 'stair', 0.52 + 0.35 * lv + rp.random() * 0.05,
                (0.0, 1.0, 0.0), 0.0, lv)

    types = [('pperf', p['w_perf']), ('pround', p['w_round']), ('pmesh', p['w_mesh']), ('plouver', p['w_louver']), ('psolid', p['w_solid'])]

    def pick(allowed):
        pool = [(t, w) for t, w in types if t in allowed and w > 0]
        if not pool:
            return allowed[0]
        tot = sum(w for _, w in pool)
        x = rp.random() * tot
        for t, w in pool:
            x -= w
            if x <= 0:
                return t
        return pool[-1][0]

    panel_faces = []
    for f in sorted(faces):
        if f in nopanel:
            continue
        a, i, j, k = f
        c0, c1 = cells_of(f)
        n0, n1 = c0 in occ, c1 in occ
        if a == 'y':
            if n0 and n1:
                prob, s = p['floor_density'], (1 if rp.random() < 0.5 else -1)
                allowed = ['pmesh', 'pperf', 'psolid']
            elif n1:
                prob, s = (p['ground_floor'] if j == 0 else p['floor_density'] * 0.5), -1
                allowed = ['pmesh', 'pperf']
            else:
                prob, s = p['roof_density'], 1
                allowed = ['psolid', 'plouver', 'pmesh']
        else:
            if n0 and n1:
                prob, s = p['interior_density'], (1 if rp.random() < 0.5 else -1)
            else:
                prob, s = p['wall_density'], (1 if n0 else -1)
            allowed = ['pperf', 'pround', 'pmesh', 'plouver', 'psolid']
        if rp.random() < prob:
            panel_faces.append((f, s, pick(allowed)))
    paneled = set(f for f, _, _ in panel_faces)

    tq = mm(p['panel_t'])
    for f, s, typ in panel_faces:
        a = f[0]
        c = center(f)
        wsp, hsp = span(f)
        w = wsp - 2.0 * (r + GAP)
        h = hsp - 2.0 * (r + GAP)
        R = face_R(a, s)
        lv = lvl(c[1])
        o = 0.42 + 0.40 * lv + rp.random() * 0.06
        fd = normal_of(R)
        if typ == 'pperf':
            key = 'pperf_w%d_h%d_t%d_p%d' % (mm(w), mm(h), tq, mm(p['perf_pitch']))
        elif typ == 'pmesh':
            key = 'pmesh_w%d_h%d_t%d_p%d' % (mm(w), mm(h), tq, mm(p['perf_pitch'] * 0.8))
        elif typ == 'pround':
            rr = min(w, h) * rp.choice((0.26, 0.32, 0.38))
            ax_, ay_ = w / 2.0 - rr - 0.05, h / 2.0 - rr - 0.05
            ox_ = rp.uniform(-ax_, ax_) if ax_ > 0 else 0.0
            oy_ = rp.uniform(-ay_, ay_) if ay_ > 0 else 0.0
            key = 'pround_w%d_h%d_t%d_u%d_v%d_rr%d' % (mm(w), mm(h), tq, 1000 + mm(ox_), 1000 + mm(oy_), mm(rr))
        elif typ == 'plouver':
            key = 'plouver_w%d_h%d_t%d' % (mm(w), mm(h), tq)
        else:
            key = 'psolid_w%d_h%d_t%d' % (mm(w), mm(h), tq)
        add(key, c, R, 'panel', o, fd, 0.0, lv)
        if p['clips']:
            wl, hl = w / 2.0 + r + GAP, h / 2.0 + r + GAP
            edges_local = [((0.0, -hl, 0.0), IDENT), ((0.0, hl, 0.0), rot_z(PI)), ((-wl, 0.0, 0.0), rot_z(-PI / 2)), ((wl, 0.0, 0.0), rot_z(PI / 2))]
            for lp, Rl in edges_local:
                pw = m_vec(R, lp)
                add('clip_r%d_t%d' % (mm(r), tq), (c[0] + pw[0], c[1] + pw[1], c[2] + pw[2]), m_mul(R, Rl), 'clip',
                    o + 0.05 + rp.random() * 0.03, fd, 0.0, lv)
        if p['bolts']:
            zt = 0.8 * p['panel_t']
            for sxx in (-1, 1):
                for syy in (-1, 1):
                    lp = (sxx * (w / 2.0 - 0.045), syy * (h / 2.0 - 0.045), zt)
                    pw = m_vec(R, lp)
                    add('bolt_m8_l20_c%d' % kit.cid('steel'), (c[0] + pw[0], c[1] + pw[1], c[2] + pw[2]), R, 'bolt',
                        o + 0.09 + rp.random() * 0.05, fd, (1.5 + rp.random() * 2.0) * (1 if rp.random() < 0.5 else -1), lv)

    for f in sorted(faces):
        a, i, j, k = f
        if a == 'y' or f in paneled:
            continue
        c0, c1 = cells_of(f)
        n0, n1 = c0 in occ, c1 in occ
        if n0 == n1:
            continue
        s = 1 if n0 else -1
        R = face_R(a, s)
        c = center(f)
        wsp, hsp = span(f)
        lv = lvl(c[1])
        if rp.random() < p['brace_prob'] and abs(wsp - hsp) / max(wsp, hsp) < 0.30:
            e = 0.18
            for zz, up in (((2 * r + 0.003), +1), (-(2 * r + 0.003), -1)):
                if up > 0:
                    P0, P1 = (-wsp / 2.0, -hsp / 2.0 + e), (wsp / 2.0, hsp / 2.0 - e)
                else:
                    P0, P1 = (-wsp / 2.0, hsp / 2.0 - e), (wsp / 2.0, -hsp / 2.0 + e)
                dx, dy = P1[0] - P0[0], P1[1] - P0[1]
                Ld = math.hypot(dx, dy)
                L = Ld + 0.08
                dxn, dyn = dx / Ld, dy / Ld
                mid = ((P0[0] + P1[0]) / 2.0, (P0[1] + P1[1]) / 2.0, zz)
                Rb = m_mul(R, m_from_axes((dxn, dyn, 0.0), (-dyn, dxn, 0.0), (0.0, 0.0, 1.0)))
                pw = m_vec(R, mid)
                o = 0.50 + 0.15 * lv + rp.random() * 0.05
                add('tube_r%d_l%d_c%d' % (mm(r), mm(L), kit.cid('grey')), (c[0] + pw[0], c[1] + pw[1], c[2] + pw[2]), Rb, 'brace', o,
                    normal_of(R), 0.0, lv)
                for endp in (P0, P1):
                    ang = math.atan2(-dxn, dyn) if up > 0 else math.atan2(dxn, dyn)
                    deg = int(round(math.degrees(ang) / 5.0) * 5) % 180
                    zc = (r + 0.0015) if up > 0 else -(r + 0.0015)
                    Zc = (0.0, 0.0, 1.0 if up > 0 else -1.0)
                    Xc = (0.0, 1.0, 0.0)
                    Yc = bm.v_cross(Zc, Xc)
                    Rc = m_mul(R, m_from_axes(Xc, Yc, Zc))
                    pw2 = m_vec(R, (endp[0], endp[1], zc))
                    add('clampsw_r%d_a%d' % (mm(r), deg), (c[0] + pw2[0], c[1] + pw2[1], c[2] + pw2[2]), Rc, 'clamp',
                        o + 0.03, normal_of(R), 0.0, lv)
        elif ((i, j + 1, k) not in occ and rp.random() < p['ladder_prob'] * 0.5) or (j == 0 and rp.random() < p['ladder_prob'] * 0.3):
            pw = m_vec(R, (0.0, -hsp / 2.0, r + 0.10))
            add('ladder_w450_h%d' % mm(hsp - 0.05), (c[0] + pw[0], c[1] + pw[1], c[2] + pw[2]), R, 'stair',
                0.52 + 0.35 * lv + rp.random() * 0.05, normal_of(R), 0.0, lv)

    info = {'cells': len(occ), 'edges': len(edges), 'vertices': len(vmask), 'panels': len(panel_faces), 'items': len(items),
            'variants': len(set(it['v'] for it in items)), 'size': (round(xs[-1] - xs[0], 2), round(ys[-1], 2), round(zs[-1] - zs[0], 2))}
    return items, info


if __name__ == '__main__':
    import collections
    import time
    t0 = time.time()
    items, info = generate({})
    print(info, 'time %.2fs' % (time.time() - t0))
    print(dict(collections.Counter(it['v'].split('_')[0] for it in items)))
    for seed in (1, 2, 3, 11, 42):
        it2, inf2 = generate({'seed_layout': seed, 'seed_parts': seed})
        print(seed, inf2['cells'], inf2['items'], inf2['variants'], inf2['size'])
