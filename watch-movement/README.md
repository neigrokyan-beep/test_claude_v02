# watch-movement

Генератор деталей часового механизма под сабдив. Чистый Python, работает в Cinema 4D, Houdini и без них.

- `wm_geo.py` — генераторы: `gear` (шестерня, трещотка), `annulus`, `disc_solid`, `screw`, `jewel`, `sweep` / `bridge_plate` (мосты, рычаги, пружины), `rod`. Только квады, замкнутые, валентность ≤ 4, без полюсов. `validate(mesh)` проверяет топологию.
- `wm_c4d.py` — адаптер C4D: Null > SDS > PolygonObject. `wm_hou.py` — адаптер Houdini: geo + Python SOP.
- `wm_demo.py` — 11 образцов деталей. `run_c4d.py` / `run_houdini.py` — собрать образцы в программе.

## Установка на ПК
```
cd C:\studio
git fetch origin claude/mcp-cinema-houdini-cloud-fvh761
git checkout FETCH_HEAD -- watch-movement
```
Дальше: Cinema 4D — Script Manager, открыть `C:\studio\watch-movement\run_c4d.py`, Execute.
Houdini — Python Shell, `exec(open(r"C:\studio\watch-movement\run_houdini.py").read())`.
Сборка идёт в новом документе (C4D) / в `/obj/watch_demo` (Houdini), чужие сцены не трогает.
