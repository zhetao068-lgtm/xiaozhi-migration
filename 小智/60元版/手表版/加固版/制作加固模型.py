"""生成加固小智表壳、转轴表带和试片。尺寸单位为毫米。"""

from pathlib import Path

import numpy as np
import trimesh
from manifold3d import CrossSection, Manifold


BODY = (54.0, 66.0)
PCB = 40.0
BOARD_Y = 7.0
TRAY_H, FACE_H, FLOOR = 24.6, 3.2, 2.8
DECK_Z = 11.6
SCREWS = tuple((x, y) for x in (-23.9, 23.9) for y in (-29.1, 29.1))
AXIS_Z, EAR_Y = 3.65, 36.8
PIN_RADIUS = 1.50
HINGE_RADIUS = 3.55
PITCH = 13.0
WIDTH = 22.0
FORK = ((-11.0, -5.5), (5.5, 11.0))
TONGUE = ((-5.05, 5.05),)
# 小窗宽、长和中心坐标。上方为正 y。
DISPLAY_WINDOW = (31.0, 23.0, 0.0, 8.0)


def rounded(width, length, radius, x=0, y=0):
    shape = CrossSection.square((width - 2 * radius, length - 2 * radius), center=True)
    return shape.offset(radius, circular_segments=40).translate((x, y))


def prism(profile, z, height):
    return profile.extrude(height).translate((0, 0, z))


def box(x, y, z, width, length, height):
    return prism(CrossSection.square((width, length), center=True).translate((x, y)), z, height)


def cylinder(x, y, z, height, radius):
    return Manifold.cylinder(height, radius, radius, 40).translate((x, y, z))


def along_x(profile, x0, x1):
    """将截面的 (y,z) 坐标沿 x 轴拉伸。"""
    return profile.extrude(x1 - x0).transform(((0, 0, 1, x0), (1, 0, 0, 0), (0, 1, 0, 0)))


def pin_hole(y):
    # 尖顶缩短横向圆孔的顶部跨距，圆弧给螺杆留出转动间隙。
    radius = PIN_RADIUS
    h = radius / np.sqrt(2)
    circle = CrossSection.circle(radius, 40)
    roof = CrossSection([np.array([(-h, h), (0, 2 * h), (h, h), (0, 0)])])
    return (circle + roof).translate((y, AXIS_Z))


def hinge(y, intervals, toward, base=None):
    ring = CrossSection.circle(HINGE_RADIUS, 40).translate((y, AXIS_Z))
    root = rounded(8.8, 6.4, 1.25, x=y + toward * 3.1, y=3.35)
    profile = ring + root
    if base is not None:
        profile += base
    profile -= pin_hole(y)
    solid = Manifold()
    for x0, x1 in intervals:
        solid += along_x(profile, x0, x1)
    return solid


def tray_body(floor_thickness=FLOOR):
    outline = rounded(*BODY, 4.6)
    shell = prism(outline, 0, floor_thickness)
    walls = prism(rounded(53.64, 65.64, 4.42) - rounded(47.6, 59.6, 2.6),
                  FLOOR - 0.15, TRAY_H - FLOOR + 0.15)
    for side in (-1, 1):
        # 保留宽开口给尚未实测的接口，上盖跨接角部。
        walls -= box(side * 26.8, 7.0, 10.0, 8.0, 40.0, 16.0)
    walls -= box(0, 32.8, 10.0, 33.0, 8.0, 16.0)
    shell += walls

    for side in (-1, 1):
        for y in (-9.0, 22.0):
            shell += box(side * 21.6, y, FLOOR - 0.1, 3.8, 5.2, DECK_Z - FLOOR + 0.1)
    for x, y in SCREWS:
        shell += cylinder(x, y, FLOOR - 0.1, TRAY_H - FLOOR + 0.1, 2.8)
        shell -= cylinder(x, y, TRAY_H - 7.4, 7.5, 0.92)
    shell += box(0, -22.6, FLOOR - 0.1, 34.0, 11.0, 16.1 - FLOOR)
    return shell


def tray():
    shell = tray_body()
    for side in (-1, 1):
        y = side * EAR_Y
        intervals = TONGUE if side == 1 else FORK
        # 底部支撑延伸到轴心前方，避开相邻链节的转动范围。
        points = np.array([(29.0, 0.05), (36.6, 0.05), (36.6, 3.55), (29.0, 6.6)])
        if side < 0:
            points[:, 0] *= -1
            points = points[::-1]
        shell += hinge(y, intervals, -side, CrossSection([points]))

    return shell


def faceplate(window):
    plate = prism(rounded(*BODY, 4.6), 0, FACE_H)
    width, length, x, y = window
    plate -= prism(rounded(width, length, 1.8, x, y), -0.1, FACE_H + 0.2)
    if width < PCB:
        plate -= prism(rounded(21.0, 3.0, 1.2, y=24.0), -0.1, FACE_H + 0.2)
    for y in (-27.0, -23.5, -20.0, -16.5):
        plate -= prism(rounded(30.0, 1.65, 0.65, y=y), -0.1, FACE_H + 0.2)
    for x, y in SCREWS:
        plate -= cylinder(x, y, -0.1, FACE_H + 0.2, 1.23)
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


def link():
    center = prism(rounded(WIDTH - 0.15, 4.4, 1.35), 0, 4.7)
    return center + hinge(-PITCH / 2, FORK, 1) + hinge(PITCH / 2, TONGUE, -1)


def closure_link():
    # M2.5 普通六角螺母对边 5 mm，留 0.25 mm 公差。
    # 六角形尖角朝上，保留较窄的横向跨距。
    radius = 5.25 / np.sqrt(3)
    angles = np.pi / 6 + np.arange(6) * np.pi / 3
    points = radius * np.column_stack((np.cos(angles), np.sin(angles)))
    pocket = CrossSection([points]).translate((-PITCH / 2, AXIS_Z))
    return link() - along_x(pocket, -11.1, -8.75)


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
    for name, solid in (
        ("01-加固底壳", tray()),
        ("02-试装面框", faceplate((PCB + 1.2, PCB + 1.2, 0, BOARD_Y))),
        ("03-屏幕小窗面框", faceplate(DISPLAY_WINDOW)),
        ("04-主板托盘", board_deck()),
        ("05-活动链节", link()),
        ("06-主板尺寸试片", fit_gauge()),
        ("07-开合链节", closure_link()),
    ):
        save(name, solid)
