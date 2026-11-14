"""生成微雪 ESP32-C6-LCD-0.85 的外套式腕带托架。尺寸单位为毫米。"""

from math import cos, pi, sin
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import CrossSection, Manifold


CASE_SIZE = 46.0
CASE_RADIUS = 5.8
CASE_HEIGHT = 22.5
SIDE_CLEARANCE = 0.45
BASE_HEIGHT = 3.0
OUTER_WIDTH = 51.1
CLIP_SPACING = 16.9
CLIP_WIDTH = 4.8
STRAP_SLOT = (3.5, 22.6)


def rounded_rectangle(width, length, radius, x=0, y=0):
    """中心坐标为 (x, y) 的圆角矩形。"""
    points = []
    for quadrant in range(4):
        first_angle = quadrant * pi / 2
        center_x = x + (width / 2 - radius) * (1 if quadrant in (0, 3) else -1)
        center_y = y + (length / 2 - radius) * (1 if quadrant in (0, 1) else -1)
        for step in range(13):
            angle = first_angle + step * pi / 24
            points.append((center_x + radius * cos(angle), center_y + radius * sin(angle)))
    return CrossSection([np.array(points)])


def prism(profile, low, high):
    return profile.extrude(high - low).translate((0, 0, low))


def clip(x, y_sign):
    """从侧面看，卡扣上下斜面均为 45 度。"""
    inner = CASE_SIZE / 2 + SIDE_CLEARANCE
    outer = OUTER_WIDTH / 2 - 0.30
    tip = CASE_SIZE / 2 - 0.70
    ramp_start = BASE_HEIGHT + CASE_HEIGHT - 0.18
    ramp = inner - tip
    profile = CrossSection([np.array([
        (inner, 1.6),
        (outer, 1.6),
        (outer, ramp_start + 2 * ramp),
        (inner, ramp_start + 2 * ramp),
        (tip, ramp_start + ramp),
        (inner, ramp_start),
    ])])
    # 将侧面坐标 (y, z) 转到成品坐标，再按卡扣宽度沿 x 延伸。
    solid = profile.extrude(CLIP_WIDTH).transform((
        (0, 0, 1, x - CLIP_WIDTH / 2),
        (1, 0, 0, 0),
        (0, 1, 0, 0),
    ))
    return solid if y_sign == 1 else solid.mirror((0, 1, 0))


def build():
    outer = rounded_rectangle(OUTER_WIDTH, OUTER_WIDTH, 8.25)
    inner = rounded_rectangle(CASE_SIZE + 2 * SIDE_CLEARANCE,
                              CASE_SIZE + 2 * SIDE_CLEARANCE, CASE_RADIUS + SIDE_CLEARANCE)
    foot = outer
    for side in (-1, 1):
        foot += rounded_rectangle(10.4, 29.2, 3.1, x=26.8 * side)
        foot -= rounded_rectangle(*STRAP_SLOT, 1.2, x=27.45 * side)
    foot -= rounded_rectangle(31.0, 31.0, 4.4)
    solid = prism(foot, 0, BASE_HEIGHT)

    # 短围边只出现在四角，四个侧面的中间保持敞开。
    corners = CrossSection()
    for x_sign in (-1, 1):
        for y_sign in (-1, 1):
            corners += CrossSection.square((13, 12), center=True).translate((23 * x_sign, 24 * y_sign))
    # 围边略内缩，底部接合处避开共面三角形。
    corner_outer = rounded_rectangle(OUTER_WIDTH - 0.36, OUTER_WIDTH - 0.36, 8.07)
    solid += prism((corner_outer - inner) ^ corners, BASE_HEIGHT - 0.2, BASE_HEIGHT + 3.0)
    for x in (-CLIP_SPACING, CLIP_SPACING):
        for y_sign in (-1, 1):
            solid += clip(x, y_sign)
    return solid


def to_mesh(solid):
    raw = solid.to_mesh()
    return trimesh.Trimesh(vertices=raw.vert_properties[:, :3], faces=raw.tri_verts, process=False)


if __name__ == "__main__":
    carrier = build()
    mesh = to_mesh(carrier)
    if not mesh.is_volume or len(carrier.decompose()) != 1:
        raise RuntimeError("托架必须是单件闭合实体")
    output = Path(__file__).with_name("C6腕带保护壳.stl")
    mesh.export(output)
    print(f"{output.name} | {mesh.extents.round(2)} mm | {mesh.volume / 1000:.2f} cm^3")
