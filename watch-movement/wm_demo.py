# -*- coding: utf-8 -*-
"""wm_demo: a small sample set of parts (one of each generator) laid out on a grid.
Used by run_c4d.py and run_houdini.py to check that the library works in the program.
PARTS: list of (name, factory) ; factory() -> wm_geo.Mesh (Z-up, millimetres)."""
import wm_geo as g

PARTS = [
    ("gear_60_hub_web", lambda: g.gear(60, 4.0, 0.3, 0.3, hub_h=0.2, web_drop=0.1)),
    ("gear_60_fine", lambda: g.gear(60, 4.0, 0.3, 0.3, per_tooth=8)),
    ("pinion_10", lambda: g.gear(10, 0.6, 0.4, 0.1)),
    ("ratchet_48", lambda: g.gear(48, 4.5, 0.25, 0.4, kind="ratchet")),
    ("date_ring", lambda: g.annulus(6.0, 5.0, 0.2, 96)),
    ("stud", lambda: g.disc_solid(1.0, 0.2, 4, dome=0.1)),
    ("screw", lambda: g.screw()),
    ("jewel", lambda: g.jewel()),
    ("bridge_arc", lambda: g.bridge_plate(g.arc_path(0, 0, 4, 0.2, 1.8, 12), 1.6, 0.4)),
    ("hairspring", lambda: g.sweep(g.spiral_path(0.6, 3.0, 7, 180), 0.05, 0.14, k=1)),
    ("rod", lambda: g.rod(0.1, 1.5)),
]
COLS = 4
STEP = 11.0


def layout():
    """[(name, factory, (x, y, z))]"""
    return [(n, f, ((i % COLS) * STEP, -(i // COLS) * STEP, 0.0)) for i, (n, f) in enumerate(PARTS)]
