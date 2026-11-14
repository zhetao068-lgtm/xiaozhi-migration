"""生成 Xmini-C3 普通 Wi-Fi 版的口袋外壳。所有尺寸均为毫米。"""

from pathlib import Path

import numpy as np
import trimesh
from manifold3d import CrossSection, Manifold


WIDTH, LENGTH = 70.0, 52.0
TRAY_HEIGHT, LID_HEIGHT = 22.6, 2.4
FLOOR = 2.0
PCB_X = 10.4
SPEAKER_X = -20.0
SCREWS = tuple((x, y) for x in (-31.8, 31.8) for y in (-22.5, 22.5))


def rounded(width, length, radius):
    return CrossSection.square((width - 2 * radius, length - 2 * radius), center=True).offset(
        radius, circular_segments=32
    )


def prism(profile, z, height):
    return profile.extrude(height).translate((0, 0, z))


def box(x, y, z, width, length, height):
    return Manifold.cube((width, length, height)).translate((x - width / 2, y - length / 2, z))


def cylinder(x, y, z, height, radius, top_radius=None):
    return Manifold.cylinder(height, radius, radius if top_radius is None else top_radius, 36).translate((x, y, z))


def tray():
    outside = rounded(WIDTH, LENGTH, 3.5)
    shell = prism(outside, 0, TRAY_HEIGHT)
    shell -= prism(rounded(65.6, 47.6, 2.2), FLOOR, TRAY_HEIGHT)

    # 开口一直通到盒口，装板和打印时都无需跨过封闭的侧壁孔。
    shell -= box(PCB_X, -25.8, 7.5, 16.0, 6, 16.0)
    shell -= box(34.2, 0, 10.8, 5.0, 30.0, 13.0)

    # 四个短台阶承托 PCB 的两条边，板子下方留出电池空间。
    for x in (PCB_X - 13.7, PCB_X + 13.7):
        for side in (-1, 1):
            shell += box(x, side * 19.0, FLOOR - 0.2, 3.8, 4.0, 10.4)
        shell += box(x, 19.3, 11.9, 3.8, 1.6, 2.4)
    for side in (-1, 1):
        for y in (-15.7, 15.7):
            shell += box(PCB_X + side * 19.1, y, FLOOR - 0.2, 1.5, 3.0, 12.5)

    # 喇叭平放于左仓，格栅在盖上。底座不碰发声膜。
    shell += box(SPEAKER_X, 0, FLOOR - 0.2, 13.0, 30.0, 12.7)
    for side in (-1, 1):
        shell += box(SPEAKER_X + side * 8.0, 0, FLOOR - 0.2, 1.6, 24.0, 16.2)

    # 挂绳孔沿打印方向贯通。
    shell += prism(rounded(11.0, 12.0, 3.0).translate((-36.0, 0)), 0, 4.0)
    shell -= cylinder(-37.4, 0, -0.1, 4.2, 2.35)

    for x, y in SCREWS:
        shell += cylinder(x, y, FLOOR - 0.2, TRAY_HEIGHT - FLOOR + 0.2, 2.85)
        shell -= cylinder(x, y, TRAY_HEIGHT - 7.5, 7.6, 0.90)
    return shell


def lid():
    # 盖板以外表面贴床导出，装配时翻过来。
    cover = prism(rounded(WIDTH, LENGTH, 3.5), 0, LID_HEIGHT)
    cover -= prism(rounded(30.4, 22.5, 1.35).translate((PCB_X, 3.0)), -0.1, LID_HEIGHT + 0.2)
    cover -= prism(rounded(16.0, 2.7, 1.1).translate((PCB_X - 5.0, 17.2)), -0.1, LID_HEIGHT + 0.2)
    for y in (-12, -8, -4, 0, 4, 8, 12):
        cover -= prism(rounded(12.0, 1.9, 0.8).translate((SPEAKER_X, y)), -0.1, LID_HEIGHT + 0.2)
    for x, y in SCREWS:
        cover -= cylinder(x, y, -0.1, LID_HEIGHT + 0.2, 1.20)
    return cover.mirror((1, 0, 0))


def checked_mesh(solid):
    assert len(solid.decompose()) == 1
    raw = solid.to_mesh()
    mesh = trimesh.Trimesh(vertices=raw.vert_properties[:, :3], faces=raw.tri_verts, process=False)
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0
    assert np.min(mesh.area_faces) > 0 and np.isclose(mesh.bounds[0, 2], 0)
    return mesh


if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    for name, solid in (("Xmini-C3底壳", tray()), ("Xmini-C3面盖", lid())):
        mesh = checked_mesh(solid)
        mesh.export(folder / f"{name}.stl")
        print(f"{name}: {mesh.extents.round(2)} mm, {len(mesh.faces)} triangles")
