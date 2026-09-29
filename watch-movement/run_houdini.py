# Houdini: paste into the Python Shell (or run via the bridge). Builds the sample parts under /obj/watch_demo.
import sys
HERE = r"C:\studio\watch-movement"          # <- the folder with wm_geo.py (git checkout of this repo)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import importlib
import hou
import wm_geo, wm_demo, wm_hou
for m in (wm_geo, wm_demo, wm_hou):
    importlib.reload(m)
obj = hou.node("/obj")
old = obj.node("watch_demo")
if old:
    old.destroy()
holder = obj.createNode("subnet", "watch_demo")
for i, (name, factory, pos) in enumerate(wm_demo.layout()):
    wm_hou.add_part(holder, name, "wm_demo.PARTS[%d][1]()" % i, pos)
print("watch_demo: %d parts" % len(wm_demo.PARTS))
