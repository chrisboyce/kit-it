"""The single list of parts in the kit.

Each entry names a part function from parts.py and its *built* pose: where the
part's local print frame goes in the assembled model. Poses are written as
Plane(origin, x_dir, z_dir): "the part's local x axis points along x_dir, its
local z (out of the print bed) along z_dir". That reads much better than Euler
angles.

The *print* pose is the part's spot on the sprue, computed by sprue.layout()
from the same geometry. No part geometry is defined twice: identical parts
(the two returns, the two keys) share one function and are built once.
"""

from dataclasses import dataclass
from typing import Callable

from build123d import Location, Plane

import parts
from params import Params

X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
NEG_X, NEG_Y = (-1, 0, 0), (0, -1, 0)


@dataclass
class Spec:
    num: int
    name: str
    make: Callable[[Params], "parts.Piece"]
    built: Callable[[Params], Location]


def _facade_pose(p):
    # Back face on the facade line, standing on the base top, relief facing the street.
    return Location(Plane((0, p.sidewalk_depth + p.wall_thickness, p.base_thickness), X, NEG_Y))


def _return_pose(side):
    def pose(p):
        x0 = p.return_xs[side]
        return Location(Plane((x0, p.sidewalk_depth + p.wall_thickness, p.base_thickness), Y, X))
    return pose


def _key_pose(side):
    def pose(p):
        kg = parts.key_geometry(p)
        x = p.facade_tab_xs[side] + p.key_thickness / 2
        # Thin end toward the street, flat edge up against the channel ceiling,
        # tapered edge down, bearing on the bottom of the tab's window.
        return Location(Plane((x, kg["y_front"], p.zq(p.key_channel_depth)), Y, NEG_X))
    return pose


def _prop_a_pose(p):
    t = p.prop_thickness
    return Location(Plane((p.prop_x - p.prop_tab_x, p.prop_y + t / 2, p.base_thickness), X, NEG_Y))


def _prop_b_pose(p):
    t = p.prop_thickness
    return Location(Plane((p.prop_x - t / 2, p.prop_y - p.prop_width / 2, p.base_thickness), Y, X))


REGISTRY = [
    Spec(1, "base", parts.base, lambda p: Location(Plane.XY)),
    Spec(2, "facade", parts.facade, _facade_pose),
    Spec(3, "return_left", parts.side_return, _return_pose(0)),
    Spec(4, "return_right", parts.side_return, _return_pose(1)),
    Spec(5, "key_left", parts.key, _key_pose(0)),
    Spec(6, "key_right", parts.key, _key_pose(1)),
    Spec(7, "prop_a", parts.prop_a, _prop_a_pose),
    Spec(8, "prop_b", parts.prop_b, _prop_b_pose),
]


def build(p: Params):
    """[(spec, piece)] for the whole kit, building each distinct part function once."""
    cache = {}
    out = []
    for spec in REGISTRY:
        if spec.make not in cache:
            cache[spec.make] = spec.make(p)
        out.append((spec, cache[spec.make]))
    return out
