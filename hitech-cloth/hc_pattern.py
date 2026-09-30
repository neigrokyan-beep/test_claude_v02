# -*- coding: utf-8 -*-
"""hc_pattern: flat sewing pattern (kimono-style jacket + wide trousers) as quad grids. Pure Python.

Units: cm. Every panel lies in the XY plane (z = 0), normal towards -Z (the viewer in C4D front view),
point index = j * (nx + 1) + i, row j = 0 is the top edge (waist / shoulder / sleeve head).
A panel is a 'ruled' grid: every row j has its own left/right x -> clean quads, edges are point rows/columns.
A seam is a list of (panelA, indexA, panelB, indexB): point pairs to stitch (equal counts by construction).
"""
import math

CELL = 2.0

# ---- body / garment dimensions (cm)
NECK_HALF = 9.5          # half neck width at the shoulder line
NECK_DEPTH_BACK = 2.4
H_BODY = 74.0            # shoulder line -> hem
SHOULDER_X = 30.0        # half body width at the armhole (drop shoulder)
SIDE_FLARE = 3.0
OVERLAP_A = 14.0         # wrap panel A: inner edge past centre front
OVERLAP_B = 4.0
SLEEVE_LEN = 58.0
CUFF_W = 62.0            # bell sleeve opening (circumference)
FLAP_LEN = 40.0
COLLAR_H = 9.0
LEG_LEN = 92.0
CROTCH_D = 28.0
WAIST_F, WAIST_B = 20.0, 22.0
CROTCH_F, CROTCH_B = 30.0, 35.0
HEM_W = 44.0
CUFF_LEN, CUFF_CIRC = 8.0, 48.0
BAND_H = 6.0


class Panel(object):
    def __init__(self, name, nx, ny, pts, quads, group):
        self.name, self.nx, self.ny, self.pts, self.quads, self.group = name, nx, ny, pts, quads, group
        self.origin = (0.0, 0.0)

    def id(self, i, j):
        return j * (self.nx + 1) + i

    def top(self, a=0, b=None):
        b = self.nx if b is None else b
        return [self.id(i, 0) for i in range(a, b + 1)] if b >= a else [self.id(i, 0) for i in range(a, b - 1, -1)]

    def bottom(self, a=0, b=None):
        b = self.nx if b is None else b
        return [self.id(i, self.ny) for i in range(a, b + 1)] if b >= a else [self.id(i, self.ny) for i in range(a, b - 1, -1)]

    def left(self, a=0, b=None):
        b = self.ny if b is None else b
        return [self.id(0, j) for j in range(a, b + 1)] if b >= a else [self.id(0, j) for j in range(a, b - 1, -1)]

    def right(self, a=0, b=None):
        b = self.ny if b is None else b
        return [self.id(self.nx, j) for j in range(a, b + 1)] if b >= a else [self.id(self.nx, j) for j in range(a, b - 1, -1)]

    def row(self, j):
        return [self.id(i, j) for i in range(self.nx + 1)]


def ruled(name, group, nx, rows, left, right, mirror=False):
    """rows: depths (down from the top edge, ascending, rows[0] = 0). left(d)/right(d): x at depth d."""
    ny = len(rows) - 1
    pts = []
    for d in rows:
        l, r = left(d), right(d)
        for i in range(nx + 1):
            x = l + (r - l) * i / float(nx)
            pts.append(((-x if mirror else x), -d, 0.0))
    quads = []
    W = nx + 1
    for j in range(ny):
        for i in range(nx):
            a, b, c, d = j * W + i, j * W + i + 1, (j + 1) * W + i + 1, (j + 1) * W + i
            quads.append((a, d, c, b) if mirror else (a, b, c, d))
    return Panel(name, nx, ny, pts, quads, group)


def uniform_rows(length, cell=CELL, first=None):
    n = max(1, int(round(length / cell)))
    return [length * k / float(n) for k in range(n + 1)]


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * (2.0 - t)


def build():
    """Returns (panels, seams). Panels are placed on a flat sheet (see layout())."""
    P = {}
    seams = []

    # ------------------------------------------------------------------ jacket torso
    rows_b = [0.0, 1.2, NECK_DEPTH_BACK]
    n_rest = int(round((H_BODY - NECK_DEPTH_BACK) / CELL))
    rows_b += [NECK_DEPTH_BACK + (H_BODY - NECK_DEPTH_BACK) * k / float(n_rest) for k in range(1, n_rest + 1)]
    JA = 14                                   # armhole rows: 0..JA
    D_ARM = rows_b[JA]
    JF = 18                                   # flap attach row
    NXT = 18                                  # columns of every torso panel

    def right_body(d):
        return SHOULDER_X + SIDE_FLARE * max(0.0, (d - D_ARM) / (H_BODY - D_ARM))

    def left_back(d):
        if d >= NECK_DEPTH_BACK:
            return 0.0
        return NECK_HALF * math.cos(0.5 * math.pi * d / NECK_DEPTH_BACK)

    def left_front(x_end):
        def f(d):
            t = min(1.0, d / D_ARM)
            return NECK_HALF + (x_end - NECK_HALF) * t
        return f

    P['Jacket_BackR'] = ruled('Jacket_BackR', 'jacket', NXT, rows_b, left_back, right_body, mirror=False)
    P['Jacket_BackL'] = ruled('Jacket_BackL', 'jacket', NXT, rows_b, left_back, right_body, mirror=True)
    P['Jacket_FrontA'] = ruled('Jacket_FrontA', 'jacket', NXT, rows_b, left_front(-OVERLAP_A), right_body, mirror=False)
    P['Jacket_FrontB'] = ruled('Jacket_FrontB', 'jacket', NXT, rows_b, left_front(-OVERLAP_B), right_body, mirror=True)
    BR, BL, FA, FB = (P['Jacket_BackR'], P['Jacket_BackL'], P['Jacket_FrontA'], P['Jacket_FrontB'])
    ny = BR.ny

    def seam(name, pa, la, pb, lb):
        assert len(la) == len(lb), (name, len(la), len(lb))
        seams.append({'name': name, 'pairs': [(pa, a, pb, b) for a, b in zip(la, lb)]})

    def seam3(name, pairs):     # pairs: [(panelA, idxA, panelB, idxB)]
        seams.append({'name': name, 'pairs': pairs})

    seam('shoulder_R', 'Jacket_BackR', BR.top(), 'Jacket_FrontA', FA.top())
    seam('shoulder_L', 'Jacket_BackL', BL.top(), 'Jacket_FrontB', FB.top())
    seam('centre_back', 'Jacket_BackR', BR.left(2, ny), 'Jacket_BackL', BL.left(2, ny))
    seam('side_R', 'Jacket_BackR', BR.right(JA, ny), 'Jacket_FrontA', FA.right(JA, ny))
    seam('side_L', 'Jacket_BackL', BL.right(JA, ny), 'Jacket_FrontB', FB.right(JA, ny))

    # ------------------------------------------------------------------ sleeves
    n_head = 2 * JA
    head_w = 2.0 * D_ARM
    srows = uniform_rows(SLEEVE_LEN)

    def sl_left(d):
        t = d / SLEEVE_LEN
        return -0.5 * (head_w + (CUFF_W - head_w) * (t ** 1.4))

    def sl_right(d):
        return -sl_left(d)

    P['Jacket_SleeveR'] = ruled('Jacket_SleeveR', 'jacket', n_head, srows, sl_left, sl_right, mirror=False)
    P['Jacket_SleeveL'] = ruled('Jacket_SleeveL', 'jacket', n_head, srows, sl_left, sl_right, mirror=True)
    for tag, sl, back, front in (('R', P['Jacket_SleeveR'], BR, FA), ('L', P['Jacket_SleeveL'], BL, FB)):
        ring = sl.top()                      # 2*JA + 1 points; armpit at i = 0 and i = 2*JA, shoulder tip at i = JA
        pairs = []
        for k in range(JA + 1):              # i = 0..JA : back armhole from armpit up to the shoulder tip
            pairs.append((sl.name, ring[k], back.name, back.id(back.nx, JA - k)))
        for k in range(1, JA + 1):           # i = JA+1..2JA : front armhole down to the armpit
            pairs.append((sl.name, ring[JA + k], front.name, front.id(front.nx, k)))
        seam3('armhole_' + tag, pairs)
        seam('sleeve_tube_' + tag, sl.name, sl.left(), sl.name, sl.right())

    # ------------------------------------------------------------------ collar (stand, wraps with the front)
    # neckline order: front A diag (j = JA .. 0), back R neck (j = 1, 2), back L neck (j = 1, 0), front B diag (j = 1 .. JA)
    neck = [('Jacket_FrontA', FA.id(0, j)) for j in range(JA, -1, -1)]
    neck += [('Jacket_BackR', BR.id(0, j)) for j in (1, 2)]
    neck += [('Jacket_BackL', BL.id(0, j)) for j in (1, 0)]
    neck += [('Jacket_FrontB', FB.id(0, j)) for j in range(1, JA + 1)]
    ncx = len(neck) - 1
    crow = uniform_rows(COLLAR_H, 1.8)
    bot_w, top_w = 88.0, 62.0
    P['Jacket_Collar'] = ruled('Jacket_Collar', 'jacket', ncx, crow,
                               lambda d: -0.5 * (bot_w + (top_w - bot_w) * d / COLLAR_H),
                               lambda d: 0.5 * (bot_w + (top_w - bot_w) * d / COLLAR_H))
    col = P['Jacket_Collar']
    seam3('collar_neck', [(col.name, col.id(i, col.ny), pn, pi) for i, (pn, pi) in enumerate(neck)])

    # ------------------------------------------------------------------ apron flap (hangs from front A)
    frow = uniform_rows(FLAP_LEN)
    dfl = rows_b[JF]
    P['Jacket_Flap'] = ruled('Jacket_Flap', 'jacket', NXT, frow, lambda d: left_front(-OVERLAP_A)(dfl), lambda d: right_body(dfl))
    fl = P['Jacket_Flap']
    seam('flap_top', fl.name, fl.top(), 'Jacket_FrontA', FA.row(JF))

    # ------------------------------------------------------------------ trousers
    lrows = [0.0]
    n_leg = int(round(LEG_LEN / CELL))
    lrows = [LEG_LEN * k / float(n_leg) for k in range(n_leg + 1)]
    JC = min(range(len(lrows)), key=lambda j: abs(lrows[j] - CROTCH_D))
    D_CR = lrows[JC]
    NXL = 20

    def leg_width(w0, wc):
        def w(d):
            if d <= D_CR:
                return w0 + (wc - w0) * _smooth(d / D_CR)
            return wc + (HEM_W - wc) * (d - D_CR) / (LEG_LEN - D_CR)
        return w

    def outseam(d):
        return 3.0 * d / LEG_LEN

    def mk(name, mirror, w0, wc):
        w = leg_width(w0, wc)
        return ruled(name, 'trousers', NXL, lrows, lambda d: outseam(d) - w(d), outseam, mirror=mirror)

    P['Trousers_FrontL'] = mk('Trousers_FrontL', False, WAIST_F, CROTCH_F)
    P['Trousers_FrontR'] = mk('Trousers_FrontR', True, WAIST_F, CROTCH_F)
    P['Trousers_BackL'] = mk('Trousers_BackL', False, WAIST_B, CROTCH_B)
    P['Trousers_BackR'] = mk('Trousers_BackR', True, WAIST_B, CROTCH_B)
    fL, fR, bL, bR = (P['Trousers_FrontL'], P['Trousers_FrontR'], P['Trousers_BackL'], P['Trousers_BackR'])
    ly = fL.ny
    seam('centre_front', fL.name, fL.left(0, JC), fR.name, fR.left(0, JC))
    seam('centre_back_t', bL.name, bL.left(0, JC), bR.name, bR.left(0, JC))
    seam('inseam_L', fL.name, fL.left(JC, ly), bL.name, bL.left(JC, ly))
    seam('inseam_R', fR.name, fR.left(JC, ly), bR.name, bR.left(JC, ly))
    seam('outseam_L', fL.name, fL.right(), bL.name, bL.right())
    seam('outseam_R', fR.name, fR.right(), bR.name, bR.right())

    # cuffs: ring around the hem (front bottom inseam -> outseam, back bottom outseam -> inseam)
    for tag, f, b in (('L', fL, bL), ('R', fR, bR)):
        ring = [(f.name, i) for i in f.bottom()] + [(b.name, i) for i in b.bottom(NXL - 1, 0)]
        crow2 = uniform_rows(CUFF_LEN, 2.0)
        cf = ruled('Trousers_Cuff' + tag, 'trousers', len(ring), crow2, lambda d: -0.5 * CUFF_CIRC, lambda d: 0.5 * CUFF_CIRC, mirror=(tag == 'R'))
        P[cf.name] = cf
        seam3('cuff_hem_' + tag, [(cf.name, cf.id(k, 0), pn, pi) for k, (pn, pi) in enumerate(ring)])
        seam('cuff_tube_' + tag, cf.name, cf.left(), cf.name, cf.right())

    # waistband: ring FL top (CF -> outseam), BL top (outseam -> CB), BR top (CB -> outseam), FR top (outseam -> CF)
    ring = [(fL.name, i) for i in fL.top()]
    ring += [(bL.name, i) for i in bL.top(NXL - 1, 0)]
    ring += [(bR.name, i) for i in bR.top(1, NXL)]
    ring += [(fR.name, i) for i in fR.top(NXL - 1, 1)]
    ring_len = len(ring)
    band_rows = uniform_rows(BAND_H, 1.5)
    wb = ruled('Trousers_Waistband', 'trousers', ring_len, band_rows, lambda d: -42.0, lambda d: 42.0)
    P[wb.name] = wb
    seam3('waistband', [(wb.name, wb.id(k, wb.ny), pn, pi) for k, (pn, pi) in enumerate(ring)])
    seam('waistband_tube', wb.name, wb.left(), wb.name, wb.right())
    return P, seams


LAYOUT = [   # rows of panel names; y offset of each row is computed
    ['Jacket_BackR', 'Jacket_BackL', 'Jacket_FrontA', 'Jacket_FrontB'],
    ['Jacket_SleeveR', 'Jacket_SleeveL', 'Jacket_Collar', 'Jacket_Flap'],
    ['Trousers_FrontL', 'Trousers_BackL', 'Trousers_BackR', 'Trousers_FrontR'],
    ['Trousers_CuffL', 'Trousers_CuffR', 'Trousers_Waistband'],
]


def layout(P, gap=10.0):
    """Shift every panel so that its bounding box sits in its layout slot. Returns dict name -> world points."""
    world = {}
    y = 0.0
    for row in LAYOUT:
        x = 0.0
        h = 0.0
        for n in row:
            p = P[n]
            xs = [q[0] for q in p.pts]
            ys = [q[1] for q in p.pts]
            dx, dy = x - min(xs), y - max(ys)
            world[n] = [(q[0] + dx, q[1] + dy, 0.0) for q in p.pts]
            p.origin = (dx, dy)
            x += max(xs) - min(xs) + gap
            h = max(h, max(ys) - min(ys))
        y -= h + gap
    return world


def stats(P):
    return sum(len(p.pts) for p in P.values()), sum(len(p.quads) for p in P.values())


if __name__ == '__main__':
    P, S = build()
    W = layout(P)
    print('panels %d points %d quads %d seams %d' % (len(P), stats(P)[0], stats(P)[1], len(S)))
    for s in S:
        # seam edge length check: A vs B
        d = []
        for (pa, ia, pb, ib) in s['pairs']:
            a, b = W[pa][ia], W[pb][ib]
            d.append(0)
        la = sum(math.dist(W[s['pairs'][k][0]][s['pairs'][k][1]], W[s['pairs'][k + 1][0]][s['pairs'][k + 1][1]]) for k in range(len(s['pairs']) - 1)) if len(s['pairs']) > 1 else 0
        lb = sum(math.dist(W[s['pairs'][k][2]][s['pairs'][k][3]], W[s['pairs'][k + 1][2]][s['pairs'][k + 1][3]]) for k in range(len(s['pairs']) - 1)) if len(s['pairs']) > 1 else 0
        print('%-16s n=%3d  len A %6.1f  B %6.1f  ratio %.2f' % (s['name'], len(s['pairs']), la, lb, (la / lb if lb else 0)))
    for n, p in P.items():
        xs = [q[0] for q in W[n]]
        ys = [q[1] for q in W[n]]
        print('%-20s %dx%d  %.0f x %.0f cm' % (n, p.nx, p.ny, max(xs) - min(xs), max(ys) - min(ys)))
