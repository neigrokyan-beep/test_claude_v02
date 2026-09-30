# -*- coding: utf-8 -*-
"""
bf_controls -- все параметры Block Frame на null CONTROLS: вкладка, имя, подпись, тип, значение
по умолчанию, диапазон, подсказка (видна при наведении). Строка: (tab, name, label, type, default, range, help).
type: int / float / toggle / menu (range = список подписей). Используют bf_build.py (создаёт CONTROLS и
пресеты вкладки Simple) и Python SOP / вранглы (spare parms, ссылка ch() на CONTROLS).

Вкладка Simple — главное. Остальные вкладки (Adv ...) — сырые значения; часть из них завязана на Simple
выражениями (зелёный цвет параметра): чтобы править вручную, удали выражение.
"""

SIZES = [("Small 4x3x4", (4, 3, 4)), ("Medium 6x4x5", (6, 4, 5)), ("Large 9x5x8", (9, 5, 8)),
         ("Tower 4x8x4", (4, 8, 4)), ("Flat 8x2x8", (8, 2, 8))]

# характер конструкции: плотности панелей, вес видов панелей, раскосы / лестницы / стремянки
STYLES = [
    ("Scaffold: open frames, braces, ladders", dict(wall=0.18, interior=0.05, floor=0.50, roof=0.15, ground=0.10,
        perf=0.3, round=0.1, mesh=1.0, louver=0.1, solid=0.0, brace=0.55, stair=0.30, ladder=0.40)),
    ("Panel wall: dense perforated and round-cut", dict(wall=0.85, interior=0.30, floor=0.70, roof=0.60, ground=0.40,
        perf=1.2, round=1.0, mesh=0.3, louver=0.2, solid=0.3, brace=0.10, stair=0.30, ladder=0.10)),
    ("Industrial: mixed (default)", dict(wall=0.45, interior=0.12, floor=0.55, roof=0.35, ground=0.20,
        perf=1.0, round=0.8, mesh=0.7, louver=0.5, solid=0.3, brace=0.25, stair=0.35, ladder=0.25)),
    ("Lab: gratings and louvers, clean", dict(wall=0.60, interior=0.20, floor=0.70, roof=0.50, ground=0.30,
        perf=0.2, round=0.2, mesh=1.2, louver=1.2, solid=0.6, brace=0.10, stair=0.40, ladder=0.15)),
    ("Tower: tall, many stairs", dict(wall=0.40, interior=0.10, floor=0.80, roof=0.30, ground=0.20,
        perf=1.0, round=0.5, mesh=0.8, louver=0.3, solid=0.2, brace=0.35, stair=0.70, ladder=0.30)),
]
LOOKS = ["Palette (like the reference)", "Clean (white + orange)", "Blueprint (dark + colour)"]

CTRL = [
    # ---------------------------------------------------------------- Simple
    ("Simple", "s_seed", "Seed", "int", 7, (0, 999),
     "Сид: другая расстановка блоков, панелей, лестниц и порядка сборки. Пересчитывает раскладку (~1 с)."),
    ("Simple", "s_size", "Size", "menu", 1, [s[0] for s in SIZES],
     "Размер конструкции: сетка ячеек по X x Y (этажи) x Z. Точные числа — на вкладке Adv Layout."),
    ("Simple", "s_style", "Style", "menu", 2, [s[0] for s in STYLES],
     "Характер: сколько и каких панелей, раскосы, лестницы. Задаёт плотности и веса на вкладках Adv."),
    ("Simple", "s_density", "Density", "float", 0.62, (0.15, 1.0),
     "Заполнение площади блоками: меньше -> редкие башни, больше -> сплошной массив."),
    ("Simple", "s_panels", "Panels Amount", "float", 1.0, (0.0, 2.0),
     "Во сколько раз больше или меньше панелей (стены, полы, крыши). 0 = голый каркас."),
    ("Simple", "s_fasteners", "Fasteners", "toggle", 1, None,
     "Клипсы и болты на панелях — сотни мелких деталей. Выключить — легче сцена, панели просто висят на раме."),
    ("Simple", "s_look", "Look", "menu", 0, LOOKS,
     "Цвета деталей: палитра как в референсе / светлый комплект с оранжевыми узлами / тёмный с цветными узлами."),
    ("Simple", "auto", "Play With Timeline", "toggle", 1, None,
     "Сборка идёт по таймлайну: от кадра Assembly Start, длиной Assembly Length. Выключить — двигать Progress руками или ключами."),
    ("Simple", "manual", "Progress (manual)", "float", 0.0, (0.0, 1.0),
     "Ручной прогресс сборки 0..1 (работает при выключенном Play With Timeline). Можно анимировать ключами."),
    ("Simple", "s_start", "Assembly Start (frame)", "int", 1, (1, 500),
     "Кадр, с которого начинается сборка."),
    ("Simple", "s_len", "Assembly Length (s)", "float", 9.6, (1.0, 60.0),
     "Сколько секунд идёт сборка. Часы — по FPS на вкладке Adv Layout (25)."),
    ("Simple", "s_spread", "Cloud Size (m)", "float", 6.0, (0.5, 30.0),
     "Насколько далеко от своего места детали стартуют (облако). Для большой конструкции — больше."),
    ("Simple", "s_snap", "Snap", "float", 4.0, (1.0, 8.0),
     "Резкость посадки: 1 = линейно, 4 = быстро подлетает и мягко садится (как easeOutQuart), 8 = очень резко."),
    ("Simple", "s_chaos", "Order Randomness", "float", 1.0, (0.0, 3.0),
     "Насколько перемешан порядок сборки: 0 = строго снизу вверх, 1 = живая россыпь, 3 = всё вперемешку."),
    # ---------------------------------------------------------------- Adv Layout
    ("Adv Layout", "fps", "FPS", "float", 25.0, (1, 60), "Кадров в секунду (как у сцены)."),
    ("Adv Layout", "seed_layout", "Seed (layout)", "int", 7, (0, 999),
     "Сид формы: где стоят блоки, какой высоты столбцы, какие размеры у ячеек. От Seed на Simple."),
    ("Adv Layout", "seed_parts", "Seed (parts)", "int", 3, (0, 999),
     "Сид панелей, раскосов, лестниц и шума порядка сборки. От Seed на Simple."),
    ("Adv Layout", "nx", "Cells X", "int", 6, (1, 14), "Ячеек по X (ширина)."),
    ("Adv Layout", "ny", "Cells Y (levels)", "int", 4, (1, 10), "Этажей (высота)."),
    ("Adv Layout", "nz", "Cells Z", "int", 5, (1, 14), "Ячеек по Z (глубина)."),
    ("Adv Layout", "cell", "Cell Size (m)", "float", 1.2, (0.6, 3.0),
     "Базовый размер ячейки. У каждой линии сетки размер берётся из трёх значений: база, минус и плюс разброс, округлено до 5 см."),
    ("Adv Layout", "cell_var", "Cell Size Variation", "float", 0.35, (0.0, 0.6),
     "Разброс размеров ячеек: 0 = все одинаковые, 0.35 = от 0.8 до 1.6 м при базе 1.2."),
    ("Adv Layout", "fill", "Footprint Fill", "float", 0.62, (0.05, 1.0),
     "Доля площади под блоками (Density на Simple)."),
    ("Adv Layout", "height_bias", "Height Bias", "float", 1.0, (0.2, 2.5),
     "Выше или ниже столбцы блоков: больше -> выше башни."),
    ("Adv Layout", "overhang", "Overhang Cells", "float", 0.15, (0.0, 1.0),
     "Вероятность блока, висящего сбоку на этаже без опоры снизу."),
    ("Adv Layout", "tube_r", "Tube Radius (m)", "float", 0.024, (0.012, 0.06),
     "Радиус круглой трубы. От него считается всё крепление (муфты, хомуты, клипсы)."),
    ("Adv Layout", "lift", "Lift On Legs (m)", "float", 0.0, (0.0, 4.0),
     "Поднять всю конструкцию на длинных ножках (как леса на опорах)."),
    ("Adv Layout", "foot_h", "Foot Height (m)", "float", 0.10, (0.06, 0.4), "Высота опорной пятки с винтом."),
    # ---------------------------------------------------------------- Adv Panels
    ("Adv Panels", "wall_density", "Wall Panels", "float", 0.45, (0.0, 1.0), "Доля внешних стен с панелью. От Style и Panels Amount."),
    ("Adv Panels", "interior_density", "Interior Walls", "float", 0.12, (0.0, 1.0), "Доля внутренних стен между блоками."),
    ("Adv Panels", "floor_density", "Floors", "float", 0.55, (0.0, 1.0),
     "Доля полов между этажами (над лестницей пола нет — проём)."),
    ("Adv Panels", "roof_density", "Roofs", "float", 0.35, (0.0, 1.0), "Доля крыш на верхних блоках."),
    ("Adv Panels", "ground_floor", "Ground Floors", "float", 0.2, (0.0, 1.0), "Доля полов на самом низу."),
    ("Adv Panels", "w_perf", "Weight: Perforated", "float", 1.0, (0.0, 3.0), "Вес вида: перфорированная (пегборд), с отверстиями по сетке."),
    ("Adv Panels", "w_round", "Weight: Round Cut", "float", 0.8, (0.0, 3.0), "Вес вида: панель с большим круглым вырезом."),
    ("Adv Panels", "w_mesh", "Weight: Grating", "float", 0.7, (0.0, 3.0), "Вес вида: решётка (прорези), основной вид для полов."),
    ("Adv Panels", "w_louver", "Weight: Louver", "float", 0.5, (0.0, 3.0), "Вес вида: жалюзи."),
    ("Adv Panels", "w_solid", "Weight: Solid", "float", 0.3, (0.0, 3.0), "Вес вида: глухая панель с накладкой."),
    ("Adv Panels", "panel_t", "Panel Thickness (m)", "float", 0.012, (0.006, 0.03), "Толщина панели."),
    ("Adv Panels", "perf_pitch", "Perforation Pitch (m)", "float", 0.075, (0.04, 0.2),
     "Шаг отверстий перфорации. Меньше -> больше полигонов у панели (варианты панелей считаются один раз)."),
    ("Adv Panels", "clips", "Panel Clips", "toggle", 1, None, "Клипсы-скобы на серединах кромок панели (4 на панель). От Fasteners."),
    ("Adv Panels", "bolts", "Panel Bolts", "toggle", 1, None, "Болты по углам панели (4 на панель, закручиваются при сборке). От Fasteners."),
    # ---------------------------------------------------------------- Adv Extras
    ("Adv Extras", "brace_prob", "X Braces", "float", 0.25, (0.0, 1.0),
     "Доля открытых квадратных граней с раскосом: две трубы накрест на поворотных хомутах, с обеих сторон рамы."),
    ("Adv Extras", "stair_prob", "Stairs", "float", 0.35, (0.0, 1.0), "Доля блоков с лестницей наверх (в потолке проём)."),
    ("Adv Extras", "ladder_prob", "Ladders", "float", 0.25, (0.0, 1.0), "Доля стремянок на открытых внешних гранях."),
    # ---------------------------------------------------------------- Adv Assembly
    ("Adv Assembly", "f_start", "Start Frame", "int", 1, (1, 2000), "Кадр начала сборки. От Assembly Start на Simple."),
    ("Adv Assembly", "f_len", "Length (frames)", "int", 240, (10, 4000), "Длина сборки в кадрах. От Assembly Length на Simple (секунды x FPS)."),
    ("Adv Assembly", "dur", "Part Flight Time", "float", 0.22, (0.03, 1.0),
     "Доля всей сборки, за которую каждая деталь долетает до места. Меньше -> резкий короткий полёт, больше -> все летят одновременно."),
    ("Adv Assembly", "ease", "Ease Power", "float", 4.0, (1.0, 8.0), "Степень замедления перед посадкой (4 = quart out). От Snap на Simple."),
    ("Adv Assembly", "jitter", "Order Jitter", "float", 1.0, (0.0, 3.0), "Шум в порядке сборки. От Order Randomness на Simple."),
    ("Adv Assembly", "dist", "Start Distance (m)", "float", 6.0, (0.5, 30.0), "Расстояние, с которого деталь стартует (у каждой своё от 0.5 до 1.5 этого значения). От Cloud Size на Simple."),
    ("Adv Assembly", "dir_bias", "Along-Axis Bias", "float", 0.65, (0.0, 1.0),
     "Откуда прилетает: 0 = из случайной точки облака, 1 = строго вдоль оси детали (панель — по нормали, труба — вдоль себя)."),
    ("Adv Assembly", "spin_amt", "Tumble Amount", "float", 1.0, (0.0, 3.0), "Насколько детали кувыркаются в полёте (0 = летят без вращения)."),
    ("Adv Assembly", "bolt_dist", "Bolt Travel (m)", "float", 0.12, (0.0, 0.5), "Путь болта вдоль своей оси — вкручивается с вращением."),
    ("Adv Assembly", "anim_seed", "Seed (motion)", "int", 0, (0, 999), "Сид движения: другие направления и порядок полёта при той же конструкции."),
    ("Adv Assembly", "hide_before", "Hide Until Start", "toggle", 0, None, "Прятать деталь, пока не начала лететь (иначе всё облако видно с первого кадра)."),
    # ---------------------------------------------------------------- Adv Look
    ("Adv Look", "look", "Look", "menu", 0, LOOKS, "Цветовая схема деталей. От Look на Simple."),
]
TABS = ("Simple", "Adv Layout", "Adv Panels", "Adv Extras", "Adv Assembly", "Adv Look")

# шпаргалка рядом с CONTROLS (стикер)
CHEAT = """ШПАРГАЛКА — всё управление здесь, на CONTROLS (наведи на параметр — подсказка)

SIMPLE    главное. Seed — другая расстановка. Size / Style — пресеты размера и характера.
          Density — заполнение, Panels Amount — сколько панелей, Fasteners — клипсы и болты, Look — цвета.
          Сборка: Play With Timeline (по таймлайну) или Progress руками/ключами;
          Assembly Start / Length, Cloud Size (откуда летят), Snap (резкость посадки), Order Randomness.
ADV ...   сырые значения. Зелёные параметры завязаны на Simple выражением; правь — удали выражение.
          Layout: сетка, разброс размеров, нависающие блоки, радиус трубы, ножки.
          Panels: плотности стен / полов / крыш, веса видов панелей, толщина, шаг перфорации.
          Extras: раскосы на хомутах, лестницы, стремянки.  Assembly: время полёта, хаос, вращение болтов.

СОСТАВ    трубы (оранжевые стойки, бирюзовые балки, голубые трубы) + узлы на 3-6 труб и гильзы +
          поворотные хомуты + панели на клипсах и болтах (перфорация, круглый вырез, решётка, жалюзи) +
          лестницы, стремянки, ножки. Каждая деталь — свой подвид (тип, размер, цвет в имени variant).
ПЕРЕСЧЁТ  Seed / Size / Density / Style / Panels -> раскладка и детали (~1 с).
          Assembly / Snap / Cloud -> только движение, мгновенно. Всё — упакованные инстансы: сцена лёгкая.
ЭКСПОРТ   бокс 06 EXPORT выключен: unpack даёт настоящую геометрию (тяжело). Включай только для выгрузки."""
