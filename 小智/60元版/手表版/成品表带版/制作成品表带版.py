"""40 mm 小智主板的穿带式表壳，单位为毫米。"""

from pathlib import Path

import numpy as np
import trimesh
from manifold3d import CrossSection, Manifold


BODY = (54.0, 66.0)
PCB = 40.0
BOARD_Y = 7.0
TRAY_HEIGHT, LID_HEIGHT, FLOOR = 24.6, 3.2, 3.2
DECK_Z = 11.6
SCREWS = tuple((x, y) for x in (-23.9, 23.9) for y in (-29.1, 29.1))
STRAP_SLOT = (24.4, 4.6)
STRAP_Y = 39.6
DISPLAY_WINDOW = (31.0, 23.0, 0.0, 8.0)


def rounded(width, length, radius, x=0, y=0):
    rectangle = CrossSection.square((width - 2 * radius, length - 2 * radius), center=True)
    return rectangle.offset(radius, circular_segments=40).translate((x, y))


def prism(profile, z, height):
    return profile.extrude(height).translate((0, 0, z))


def box(x, y, z, width, length, height):
    profile = CrossSection.square((width, length), center=True).translate((x, y))
    return prism(profile, z, height)


def cylinder(x, y, z, height, radius):
    return Manifold.cylinder(height, radius, radius, 40).translate((x, y, z))


def strap_eye(side):
    """左右两侧的材料围成闭环，外横梁直接承受带子的拉力。"""
    band_y = side * 35.4
    outline = rounded(44.4, 24.4, 5.1, y=band_y)
    # 贴床面略收，让腕侧的边缘形成斜面。上面再收边，减少磨带。
    eye = Manifold.batch_hull([
        prism(rounded(42.8, 22.8, 4.3, y=band_y), 0, 0.05),
        prism(outline, 0.85, 5.45),
        prism(rounded(42.0, 22.0, 3.9, y=band_y), 7.45, 0.05),
    ])
    center = side * STRAP_Y
    throat = rounded(*STRAP_SLOT, 1.8, y=center)
    entrance = rounded(25.6, 5.8, 2.4, y=center)
    # 对两个穿入口倒角，中间保留全厚的承力截面。
    lower = Manifold.batch_hull([prism(entrance, -0.1, 0.05), prism(throat, 0.9, 0.1)])
    upper = Manifold.batch_hull([prism(throat, 6.4, 0.1), prism(entrance, 7.56, 0.1)])
    bore = prism(throat, 0.8, 5.8) + lower + upper
    return eye - bore


def tray():
    outline = rounded(*BODY, 4.6)
    shell = prism(outline, 0, FLOOR)
    eyes = strap_eye(-1) + strap_eye(1)
    # 把高出的表耳根部限在壳外及侧壁，留出平整的电池仓。
    eyes -= prism(rounded(47.6, 59.6, 2.6), FLOOR - 0.05, 6.0)
    shell += eyes
    walls = prism(rounded(53.64, 65.64, 4.42) - rounded(47.6, 59.6, 2.6),
                  FLOOR - 0.15, TRAY_HEIGHT - FLOOR + 0.15)
    for side in (-1, 1):
        walls -= box(side * 26.8, BOARD_Y, 10.0, 8.0, 40.0, 16.0)
    walls -= box(0, 32.8, 10.0, 33.0, 8.0, 16.0)
    shell += walls
    for side in (-1, 1):
        for y in (-9.0, 22.0):
            shell += box(side * 21.6, y, FLOOR - 0.1, 3.8, 5.2, DECK_Z - FLOOR + 0.1)
    for x, y in SCREWS:
        shell += cylinder(x, y, FLOOR - 0.1, TRAY_HEIGHT - FLOOR + 0.1, 2.8)
        shell -= cylinder(x, y, TRAY_HEIGHT - 7.4, 7.5, 0.92)
    shell += box(0, -22.6, FLOOR - 0.1, 34.0, 11.0, 16.1 - FLOOR)
    return shell


def faceplate(window):
    plate = prism(rounded(*BODY, 4.6), 0, LID_HEIGHT)
    width, length, x, y = window
    plate -= prism(rounded(width, length, 1.8, x, y), -0.1, LID_HEIGHT + 0.2)
    if width < PCB:
        plate -= prism(rounded(21.0, 3.0, 1.2, y=24.0), -0.1, LID_HEIGHT + 0.2)
    for y in (-27.0, -23.5, -20.0, -16.5):
        plate -= prism(rounded(30.0, 1.65, 0.65, y=y), -0.1, LID_HEIGHT + 0.2)
    for x, y in SCREWS:
        plate -= cylinder(x, y, -0.1, LID_HEIGHT + 0.2, 1.23)
    return plate.mirror((1, 0, 0))


def board_deck():
    outline = rounded(45.0, 42.7, 2.0, y=BOARD_Y)
    outline -= rounded(13.5, 5.0, 1.5, y=BOARD_Y - 21.3)
    for x, y in SCREWS:
        outline -= CrossSection.circle(3.15, 40).translate((x, y))
    deck = prism(outline, 0, 2.0)
    for x in (-15.5, 15.5):
        for side in (-1, 1):
            y = BOARD_Y + side * (PCB / 2 + 0.8)
            deck += box(x, y, 1.9, 4.0, 1.0, 2.2)
    return deck


def fit_gauge():
    gap = CrossSection.square((PCB + 1.2, PCB + 1.2), center=True)
    return prism(rounded(PCB + 6.0, PCB + 6.0, 2.4) - gap, 0, 1.8)


def mesh_for(solid):
    assert len(solid.decompose()) == 1
    raw = solid.to_mesh()
    mesh = trimesh.Trimesh(vertices=raw.vert_properties[:, :3], faces=raw.tri_verts, process=False)
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0
    assert np.min(mesh.area_faces) > 0 and np.isclose(mesh.bounds[0, 2], 0)
    return mesh


if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    parts = (
        ("01-闭环表耳底壳", tray(), (35, 55)),
        ("02-开放试装面框", faceplate((PCB + 1.2, PCB + 1.2, 0, BOARD_Y)), (103, 41)),
        ("03-屏幕小窗面框", faceplate(DISPLAY_WINDOW), (33, 141)),
        ("04-主板托盘", board_deck(), (98, 108)),
        ("05-主板尺寸试片", fit_gauge(), (148, 145)),
    )
    placed = []
    for name, solid, (x, y) in parts:
        mesh = mesh_for(solid)
        mesh.export(folder / f"{name}.stl")
        print(f"{name} {mesh.extents.round(2)} mm")
        mesh.apply_translation((x, y, 0))
        placed.append(mesh)
    trimesh.util.concatenate(placed).export(folder / "小智手表成品表带版-一盘打印.stl")
