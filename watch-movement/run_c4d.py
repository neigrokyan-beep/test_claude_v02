# Cinema 4D: paste into the Script Manager (or run via the bridge). Builds the sample parts in a NEW document.
import sys, os
HERE = r"C:\studio\watch-movement"          # <- the folder with wm_geo.py (git checkout of this repo)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import importlib
import wm_geo, wm_demo, wm_c4d
for m in (wm_geo, wm_demo, wm_c4d):
    importlib.reload(m)
doc = wm_c4d.new_doc("watch_demo")
for name, factory, pos in wm_demo.layout():
    wm_c4d.add_part(doc, factory(), name, pos)
c4d = wm_c4d.c4d
c4d.EventAdd()
print("watch_demo: %d parts" % len(wm_demo.PARTS))
