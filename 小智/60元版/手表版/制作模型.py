"""生成约 40 mm 方板的小智手表外壳及 22 mm TPU 表带，单位为毫米。"""

from pathlib import Path

import numpy as np
import trimesh
from manifold3d import CrossSection, Manifold


BODY = (52.0, 64.0)
PCB = 40.0                 # 用卡尺量 PCB 本体后修改
BOARD_Y = 7.0
TRAY_H, FACE_H = 24.6, 2.2
FLOOR = 2.2
DECK_Z = 11.6
SCREWS = tuple((x, y) for x in (-22.7, 22.7) for y in (-28.4, 28.4))
STRAP_WIDTH, STRAP_THICKNESS = 22.0, 1.8
STRAP_SLOT_Y = 34.0
STRAP_HOLE = 4.4
# 默认试装面框露出整块 PCB。量好屏幕后，可填 (窗口宽, 窗口长, 中心X, 中心Y)。
DISPLAY_WINDOW = None


def rounded(width, length, radius, x=0, y=0):
    profile = CrossSection.square((width - 2 * radius, length - 2 * radius), center=True)
    return profile.offset(radius, circular_segments=48).translate((x, y))


def prism(profile, z, height):
    return profile.extrude(height).translate((0, 0, z))


def box(x, y, z, width, length, height):
    return prism(CrossSection.square((width, length), center=True).translate((x, y)), z, height)


def cone(x, y, z, height, radius, top=None):
    return Manifold.cylinder(height, radius, radius if top is None else top, 48).translate((x, y, z))


def bottom_shell():
    outline = rounded(*BODY, 4.0)
    floor = outline
    for side in (-1, 1):
        y = side * STRAP_SLOT_Y
        floor += rounded(29.0, 11.0, 2.5, y=y - side)
        floor -= rounded(23.2, 3.6, 1.1, y=y)
    shell = prism(floor, 0, FLOOR)

    walls = prism(outline - rounded(47.6, 59.6, 2.6), FLOOR - 0.1, TRAY_H - FLOOR + 0.1)
    # 左、右、上三面预留贯通到盒口的插线与按键区域，供样机核对。
    for side in (-1, 1):
        walls -= box(side * 26.0, 7.0, 10.0, 7.0, 40.0, 16.0)
    walls -= box(0, 31.8, 10.0, 33.0, 6.0, 16.0)
    shell += walls

    # 四根柱子承托电路板托盘，电池位于它们之间。
    for side in (-1, 1):
        for y in (-9.0, 22.0):
            shell += box(side * 21.6, y, FLOOR - 0.1, 3.8, 4.6, DECK_Z - FLOOR + 0.1)
    for x, y in SCREWS:
        shell += cone(x, y, FLOOR - 0.1, TRAY_H - FLOOR + 0.1, 2.75)
        shell -= cone(x, y, TRAY_H - 7.4, 7.5, 0.92)

    # 下方独立喇叭位，底座支撑背面，格栅在上盖。
    shell += box(0, -22.6, FLOOR - 0.1, 34.0, 11.0, 14.0)
    return shell


def faceplate(window):
    plate = prism(rounded(*BODY, 4.0), 0, FACE_H)
    width, length, x, y = window
    plate -= prism(rounded(width, length, 1.8, x, y), -0.1, FACE_H + 0.2)
    if width < PCB:
        plate -= prism(rounded(21.0, 3.0, 1.2, y=24.0), -0.1, FACE_H + 0.2)
    for y in (-27.0, -23.5, -20.0, -16.5):
        plate -= prism(rounded(30.0, 1.65, 0.65, y=y), -0.1, FACE_H + 0.2)
    for x, y in SCREWS:
        plate -= cone(x, y, -0.1, FACE_H + 0.2, 1.23)
    return plate.mirror((1, 0, 0))


def board_deck():
    outline = rounded(45.0, 42.7, 2.0, y=BOARD_Y)
    outline -= rounded(13.5, 5.0, 1.5, y=BOARD_Y - 21.3)
    for x, y in SCREWS:
        outline -= CrossSection.circle(3.15, 48).translate((x, y))
    deck = prism(outline, 0, 1.8)
    # 软垫压在空白板边，定位块远离接插件侧。
    for x in (-15.5, 15.5):
        for side in (-1, 1):
            y = BOARD_Y + side * (PCB / 2 + 0.8)
            deck += box(x, y, 1.7, 4.0, 1.0, 2.2)
    return deck


def strap(length, first_hole, last_hole):
    profile = rounded(STRAP_WIDTH, length, 5.0, y=length / 2)
    # 短端两孔装扣钉，长端每隔 5 mm 两孔配合短端。
    for y in (9, 19, *range(first_hole, last_hole + 1, 5)):
        profile -= CrossSection.circle(STRAP_HOLE / 2, 48).translate((0, y))
    return prism(profile, 0, STRAP_THICKNESS)


def button():
    # 两头各有圆盘，TPU 两层扣在中间；连续锥度适合平放打印。
    stud = cone(0, 0, 0, 0.45, 3.0, 3.55)
    stud += cone(0, 0, 0.44, 0.66, 3.55, 2.05)
    stud += cone(0, 0, 1.09, 4.05, 2.05)
    stud += cone(0, 0, 5.13, 1.45, 2.05, 3.40)
    stud += cone(0, 0, 6.57, 1.45, 3.40, 1.85)
    return stud


def keeper():
    outside = rounded(27.4, 8.2, 2.7)
    inside = rounded(23.1, 4.4, 1.4)
    return prism(outside - inside, 0, 6.0)


def fit_gauge():
    outer = rounded(PCB + 6, PCB + 6, 2.4)
    inner = CrossSection.square((PCB + 1.2, PCB + 1.2), center=True)
    return prism(outer - inner, 0, 1.8)


def save(name, solid):
    assert len(solid.decompose()) == 1, name
    raw = solid.to_mesh()
    mesh = trimesh.Trimesh(vertices=raw.vert_properties[:, :3], faces=raw.tri_verts, process=False)
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0, name
    assert np.min(mesh.area_faces) > 0 and np.isclose(mesh.bounds[0, 2], 0), name
    mesh.export(Path(__file__).resolve().with_name(f"{name}.stl"))
    print(f"{name} {mesh.extents.round(2)} mm")


if __name__ == "__main__":
    for name, model in (
        ("01-手表底壳", bottom_shell()),
        ("02-开放试装面框", faceplate((PCB + 1.2, PCB + 1.2, 0.0, BOARD_Y))),
        ("03-主板托盘", board_deck()),
        ("04-TPU表带-短", strap(209, 149, 199)),
        ("05-TPU表带-长", strap(229, 169, 219)),
        ("06-表带扣钉-打印2个", button()),
        ("07-TPU表带收尾环", keeper()),
        ("08-主板尺寸试片", fit_gauge()),
        ("09-屏幕小窗面框", faceplate(DISPLAY_WINDOW or (31.0, 23.0, 0.0, BOARD_Y + 1.0))),
    ):
        save(name, model)
