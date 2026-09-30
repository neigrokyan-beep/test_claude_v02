# -*- coding: utf-8 -*-
"""
layout -- Python SOP «раскладка»: где что стоит. Считается один раз (при смене параметров), ~0.02 с.
Ничего не рисует: на выходе ТОЧКИ, по одной на каждую деталь конструкции (трубы, узлы, хомуты, панели,
клипсы, болты, лестницы, ножки), с атрибутами:
  variant  ключ детали (тип + размер + цвет, напр. tube_r24_l1180_c3) — по нему kit строит саму деталь
  orient   поворот детали (кватернион)      scale   (1, 1, 1)
  cls      класс: 0 ножка, 1 труба, 2 узел/гильза, 3 раскос, 4 хомут, 5 панель, 6 лестница, 7 клипса, 8 болт
  order    очерёдность сборки 0..1 (ножки -> рама снизу вверх -> панели -> клипсы -> болты)
  fdir     откуда деталь прилетает (вдоль оси / по нормали панели / вверх)
  spin     оборотов болта при закручивании        lvl  этаж x 100
Как строится: сетка ячеек со случайными размерами -> где стоят блоки (шум + столбцы + нависающие) ->
рёбра рамы и узлы (по маске направлений выбирается муфта на 1-6 труб или гильза) -> панели на гранях
(вид по весам) -> раскосы на хомутах, лестницы, стремянки -> клипсы и болты на панелях.
Параметры (spare parms, ссылки на CONTROLS — подсказки там):
  seed_layout, seed_parts     сиды формы и деталей          nx, ny, nz          ячеек по осям
  cell, cell_var              размер ячейки и разброс       fill, height_bias   заполнение и высота
  overhang                    нависающие блоки              tube_r, lift, foot_h  труба, ножки
  wall/interior/floor/roof_density, ground_floor            плотности панелей
  w_perf, w_round, w_mesh, w_louver, w_solid                 веса видов панелей
  panel_t, perf_pitch, clips, bolts                          панель: толщина, шаг перфорации, крепёж
  brace_prob, stair_prob, ladder_prob                        раскосы, лестницы, стремянки
"""
# @@BF_CORE@@
import hou


def run():
    node = hou.pwd()
    geo = node.geometry()
    bm, bk, bl = _bf_load(("bf_mesh", "bf_kit", "bf_layout"))
    params = {}
    for name in bl.DEFAULTS:
        if node.parm(name) is not None:
            params[name] = node.evalParm(name)
    items, info = bl.generate(params)
    geo.clear()
    for nm, dv in (("orient", (0.0, 0.0, 0.0, 1.0)), ("scale", (1.0, 1.0, 1.0)), ("fdir", (0.0, 1.0, 0.0))):
        geo.addAttrib(hou.attribType.Point, nm, dv)
    geo.addAttrib(hou.attribType.Point, "variant", "")
    geo.addAttrib(hou.attribType.Point, "cls", 0)
    geo.addAttrib(hou.attribType.Point, "lvl", 0)
    geo.addAttrib(hou.attribType.Point, "order", 0.0)
    geo.addAttrib(hou.attribType.Point, "spin", 0.0)
    geo.createPoints([it["P"] for it in items])
    geo.setPointFloatAttribValues("orient", [c for it in items for c in it["q"]])
    geo.setPointFloatAttribValues("scale", [c for it in items for c in it["s"]])
    geo.setPointFloatAttribValues("fdir", [c for it in items for c in it["fdir"]])
    geo.setPointStringAttribValues("variant", [it["v"] for it in items])
    geo.setPointIntAttribValues("cls", [it["cls"] for it in items])
    geo.setPointIntAttribValues("lvl", [int(round(it["lvl"] * 100)) for it in items])
    geo.setPointFloatAttribValues("order", [it["order"] for it in items])
    geo.setPointFloatAttribValues("spin", [it["spin"] for it in items])
    geo.addAttrib(hou.attribType.Global, "bf_info", "")
    geo.setGlobalAttribValue("bf_info", str(info))


run()
