"""The Colfax caboose: the red wood-sided caboose on display in town.

An object rather than a building, so it's built up from its own floor instead of a
sidewalk: a box of split-tab panels (two sides and two ends on a floor), and loose-fit
sheets for everything else. The cupola and the trucks are cross-lapped, and a dark sheet
down the middle stops you seeing sky through the windows.

Sizes come from Street View (see README, "Colfax caboose kit"). Nothing is compressed.
The wheel sheets sit at HO gauge, on the display base's rails. It doesn't roll.

World frame: X along the car (north end at -X), Y across it (the west side at -Y), Z up,
with the car centered on the origin and the display base's underside at z=0.
"""

import os
from dataclasses import dataclass
from itertools import groupby

from build123d import Align, Circle, Location, Pos, Text, extrude

from corner import CornerParams, Face, _sock, _steps, stand
from joints import EPS, UP, Piece, box, split_tab, tab
from params import ft
from registry import Spec
from sprue import Plate

FONT = os.environ.get("COLFAX_FONT")   # bold enough that small letters keep printable strokes


@dataclass(frozen=True)
class CabooseParams(CornerParams):
    # --- color: four filaments, sampled from the photos ---------------------
    palette: tuple = (
        ("red", "#a83a2c"),
        ("cream", "#e9e4d6"),
        ("coal", "#2a2a2b"),
        ("ballast", "#8d8b84"),
    )
    color_wall: str = "red"
    color_band: str = "coal"
    color_trim: str = "cream"
    color_sign: str = "cream"
    color_door: str = "red"
    color_bulkhead: str = "coal"
    color_base: str = "ballast"
    color_deck_top: str = "ballast"
    color_roof: str = "red"
    color_glass: str = "coal"
    color_planter: str = "red"
    color_shrub: str = "red"
    color_shade: str = "coal"
    color_sprue: str = "ballast"
    color_label: str = "coal"
    color_post: str = "coal"

    # --- the car ------------------------------------------------------------
    body_len: float = ft(33)
    body_w: float = ft(9.5)
    body_h: float = ft(8.5)
    platform: float = ft(3)             # each end, past the body
    floor_t: float = 3.6                # the underframe; it also takes the panels' tabs
    wall_proud: float = 1.2             # the ends pass the sides by this: room for their sockets
    roof_t: float = 1.6
    roof_over_end: float = ft(2.2)
    roof_over_side: float = 1.6
    cupola_len: float = ft(9.7)
    cupola_w: float = ft(6.7)           # just inside the side walls: its tabs pass the roof beside them
    cupola_h: float = ft(3)
    cupola_at: float = 0.7              # along the body, from the north end
    cup_over: float = 1.5               # how far the cupola's ends pass its sides
    sheathing_pitch: float = 2.6
    rail_h: float = ft(3.2)

    # --- trucks and track -----------------------------------------------------
    gauge: float = 16.5                 # HO: between the rails' inner faces
    floor_up: float = 10.4              # rail top to the floor's underside: 4 ft to the floor's top
    wheel_r: float = 4.8                # 33 in wheels
    wheelbase: float = ft(5.5)
    truck_at: float = 0.30              # from the center, as a fraction of the body
    base_t: float = 2.4
    base_rail_h: float = 0.6
    base_len: float = 158.0
    base_w: float = 46.0

    # The car's number isn't legible in the imagery ("?63"). Set it to print real digits.
    road_number: str = ""

    @property
    def frame_y(self):
        """Wheel sheet's center line: its inner face is on the gauge."""
        return self.gauge / 2 + self.sheet_t / 2

    @property
    def z_rail(self):
        return self.base_t + self.base_rail_h

    @property
    def z_floor(self):
        return self.z_rail + self.floor_up

    @property
    def z_deck(self):
        return self.z_floor + self.floor_t

    @property
    def z_roof(self):
        return self.z_deck + self.body_h

    @property
    def floor_len(self):
        return self.body_len + 2 * self.platform

    @property
    def side_len(self):
        return self.body_len - 2 * self.wall_thickness

    @property
    def cupola_x(self):
        return self.body_len * (self.cupola_at - 0.5)

    @property
    def side_tab_xs(self):
        """Asymmetric, so a side only goes in one way round."""
        return (self.side_len * 0.2, self.side_len * 0.72)

    @property
    def end_tab_xs(self):
        return (self.body_w * 0.2, self.body_w * 0.72)

    @property
    def corner_ys(self):
        return (self.body_h * 0.22, self.body_h * 0.68)

    @property
    def side_y(self):
        return self.body_w / 2 - self.wall_proud - self.wall_thickness / 2

    @property
    def spine_tab_xs(self):
        """Clear of the trucks, whose tabs come up into the same floor."""
        return (-self.side_len * 0.15, self.side_len * 0.12)

    @property
    def step_x(self):
        return self.body_len / 2 + self.platform - 5.0

    @property
    def truck_xs(self):
        return (-self.body_len * self.truck_at, self.body_len * self.truck_at)


DEFAULT = CabooseParams()
_T = DEFAULT.sheet_t


# ---------------------------------------------------------------------------
# Lettering
# ---------------------------------------------------------------------------
def _small_caps(p, text, x_mid, y, big, small, z, t):
    """Capitals print at `big` and lowercase as capitals at `small` (both font sizes).
    Returns the paint volumes, and the width they take up."""
    gap, space = 0.25, 1.9
    pieces, x = [], 0.0
    for word in text.split():
        for upper, run in groupby(word, str.isupper):
            chunk, size = "".join(run).upper(), big if upper else small
            align = (Align.MIN, Align.NONE)
            shape = Text(chunk, size, font_path=FONT, align=align)
            bb = shape.bounding_box()
            # The letters sit on y, and a comma's tail hangs below them.
            bottom = Text(chunk.rstrip(","), size, font_path=FONT, align=align).bounding_box().min.Y
            pieces.append(Pos(x - bb.min.X, y - bottom) * shape)
            x += bb.size.X + gap
        x += space
    width = x - space - gap
    return [Pos(x_mid - width / 2, 0, z) * extrude(c, t + 10 - z, dir=UP) for c in pieces], width


def side_lettering(p, L, z, t):
    return _small_caps(p, "Colfax, CA", L * 0.63, p.body_h * 0.79, 4.3, 3.3, z, t)


# ---------------------------------------------------------------------------
# The box: split tabs
# ---------------------------------------------------------------------------
def _sheathing(f, p, x0, x1, H, clear):
    """Vertical boards: shallow grooves, split around whatever's in `clear` (x0, x1, y0, y1),
    so they don't cut through letters, frames or sills."""
    d = p.zq(0.2)
    for x in _steps(x0 + p.sheathing_pitch, x1 - 1.0, p.sheathing_pitch):
        y = 0.0
        for a, b, c0, c1 in sorted((r for r in clear if r[0] - 0.3 < x < r[1] + 0.3), key=lambda r: r[2]):
            if c0 - y > 1.0:
                f.cuts.append(box(x - 0.3, x + 0.3, y, c0, f.t - d, f.t + 10))
            y = max(y, c1)
        if H - y > 1.0:
            f.cuts.append(box(x - 0.3, x + 0.3, y, H, f.t - d, f.t + 10))


def _side(p, windows) -> Piece:
    """A long side. Local: x along it, y up, z out of the front."""
    L, H, tw = p.side_len, p.body_h, p.wall_thickness
    body = box(0, L, 0, H, 0, tw)
    f = Face(p, tw)
    z = tw - p.zq(p.color_depth)
    letters, width = side_lettering(p, L, z, tw)

    # Windows with a frame and a shelf of a sill, from the close-ups.
    w, y0, y1 = ft(1.9), ft(3.0), ft(5.8)
    clear = [(L * 0.63 - width / 2 - 1, L * 0.63 + width / 2 + 1, p.body_h * 0.79 - 1, H)]
    for frac in windows:
        x = L * frac
        f.raised(x - w / 2 - 0.8, x + w / 2 + 0.8, y0 - 0.8, y1 + 0.8)
        f.raised(x - w / 2 - 1.3, x + w / 2 + 1.3, y0 - 1.6, y0 - 0.8)
        f.paint(p.color_band, x - w / 2 - 1.3, x + w / 2 + 1.3, y0 - 2.4, y0 - 1.6)
        f.hole(x - w / 2, x + w / 2, y0, y1)
        clear.append((x - w / 2 - 1.8, x + w / 2 + 1.8, y0 - 2.8, y1 + 1.2))

    # The number and the small emblem under the name: blocks, too fine for type.
    mid = L * 0.63
    if not p.road_number:
        f.paint(p.color_trim, mid - 2.6, mid + 2.6, H * 0.55, H * 0.55 + 1.2)
    f.paint_all(p.color_trim, [(mid - 7.0, mid - 1.0, H * 0.33, H * 0.33 + 0.8), (mid + 1.0, mid + 7.0, H * 0.33, H * 0.33 + 0.8),
                               (mid - 0.4, mid + 0.4, H * 0.28, H * 0.28 + 3.2)])
    clear += [(mid - 3, mid + 3, H * 0.55 - 0.6, H * 0.55 + 1.8), (mid - 7.5, mid + 7.5, H * 0.28 - 0.5, H * 0.28 + 3.7)]
    # The pale grab irons at each end.
    f.paint_all(p.color_trim, [(1.0, 1.8, 3.0, 17.0), (L - 1.8, L - 1.0, 3.0, 17.0)])
    clear += [(0.7, 2.1, 2.5, 17.5), (L - 2.1, L - 0.7, 2.5, 17.5)]
    _sheathing(f, p, 0, L, H, clear)

    adds, cuts = [], []
    for x in p.side_tab_xs:
        t, slit = split_tab(x, 0, p, p.base_tab_len, p.base_tab_barb_at, tw)
        adds.append(t)
        cuts.append(slit)
    for y in p.corner_ys:
        for x, way in ((L, "+x"), (0, "-x")):
            t, slit = split_tab(x, y, p, p.corner_tab_len, p.corner_tab_barb_at, tw, direction=way)
            adds.append(t)
            cuts.append(slit)
    body = f.finish(body).fuse(*adds).cut(*cuts)
    number = []
    if p.road_number:
        shape = Text(p.road_number, 3.0, font_path=FONT, align=(Align.CENTER, Align.CENTER))
        number = [(p.color_trim, Pos(mid, H * 0.58, z) * extrude(shape, tw + 10 - z, dir=UP))]
    paints = f.paints + number + [(p.color_trim, c) for c in letters]
    return Piece(body, [], [(L * 0.08, 0, "-y"), (L * 0.92, 0, "-y")], color=p.color_wall, paints=paints)


def side_west(p) -> Piece:
    return _side(p, (0.2, 0.42, 0.86))


def side_east(p) -> Piece:
    """Seen only at an angle, past the fence: its windows are the least certain thing here."""
    return _side(p, (0.3, 0.86))


def end_wall(p) -> Piece:
    """Door in the middle. Local: x across the car, y up, z out of the front."""
    W, H, tw, pr = p.body_w, p.body_h, p.wall_thickness, p.wall_proud
    body = box(0, W, 0, H, 0, tw)
    f = Face(p, tw)
    dw, dh = ft(3), ft(7)
    x0, x1 = W / 2 - dw / 2, W / 2 + dw / 2
    f.raised(x0 - 0.8, x1 + 0.8, 0, dh + 0.8)
    f.pocket(x0, x1, 0, dh, p.door_recess)
    f.floor(p.color_band, x0 + 2.0, x1 - 2.0, ft(3.6), dh - 2.0, p.door_recess)
    _sheathing(f, p, 0, W, H, [(x0 - 1.3, x1 + 1.3, 0, dh + 1.3)])
    # A ladder up the end, as paint: rungs on the wall beside the door.
    rungs = [(W - 5.8, W - 2.2, y, y + 0.8) for y in _steps(9.0, H - 1.0, 3.2)]
    f.paint_all(p.color_trim, rungs)

    adds, cuts = [], []
    for x in p.end_tab_xs:
        t, slit = split_tab(x, 0, p, p.base_tab_len, p.base_tab_barb_at, tw)
        adds.append(t)
        cuts.append(slit)
    cs = p.split_clearance
    for y in p.corner_ys:
        for x in (pr + tw / 2, W - pr - tw / 2):
            cuts.append(_sock(x, y, tw + 2 * cs, p.split_width + 2 * cs, 0, p.zq(p.corner_tab_len + 0.2), p, mouth="bottom"))
    body = f.finish(body).fuse(*adds).cut(*cuts)
    return Piece(body, [], [(2.0, 0, "-y"), (W - 2.0, 0, "-y")], color=p.color_wall, paints=f.paints)


def floor(p) -> Piece:
    """Underframe and platforms, printed top up. Local: world x and y, centered."""
    Lf, W, tb, L, tw = p.floor_len, p.body_w, p.floor_t, p.body_len, p.wall_thickness
    cs, cl = p.split_clearance, p.prop_clearance
    body = box(-Lf / 2, Lf / 2, -W / 2, W / 2, 0, tb)
    cuts = []
    for x in p.side_tab_xs:
        cuts.append(_sock(-p.side_len / 2 + x, -p.side_y, p.split_width + 2 * cs, tw + 2 * cs, 0, tb, p))
        cuts.append(_sock(p.side_len / 2 - x, p.side_y, p.split_width + 2 * cs, tw + 2 * cs, 0, tb, p))
    for x in p.end_tab_xs:
        cuts.append(_sock(L / 2 - tw / 2, -W / 2 + x, tw + 2 * cs, p.split_width + 2 * cs, 0, tb, p))
        cuts.append(_sock(-L / 2 + tw / 2, W / 2 - x, tw + 2 * cs, p.split_width + 2 * cs, 0, tb, p))
    # The spine's tabs, from the top.
    for x in p.spine_tab_xs:
        cuts.append(_sock(x, 0, 6.0 + 2 * cl, p.sheet_t + 2 * cl, tb - p.zq(2.4), tb, p))
    # The end railings' tabs, from the top.
    for sx in (-1, 1):
        for y in (-W * 0.36, W * 0.36):
            cuts.append(_sock(sx * _rail_x(p), y, p.sheet_t + 2 * cl, 2.0 + 2 * cl, tb - p.zq(2.4), tb, p))
    # Trucks: right through, for more grip. The walls hide the tabs' ends.
    for x in p.truck_xs:
        cuts.append(_sock(x, 0, p.sheet_t + 2 * cl, _bolster_tab_w(p) + 2 * cl, 0, tb, p, mouth="bottom"))
    # Steps, blind from underneath.
    d = p.zq(2.4)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cuts.append(_sock(sx * p.step_x, sy * _step_y(p), 4.0 + 2 * cl, p.sheet_t + 2 * cl, 0, d, p, mouth="bottom"))
    body = body.cut(*cuts)
    # The platforms' deck boards, as paint on the coal frame.
    z = tb - p.zq(p.color_depth)
    decks = [(p.color_wall, box(s * (L / 2 + 0.4), s * (Lf / 2 - 0.8), -W / 2 + 0.8, W / 2 - 0.8, z, tb + 1)
              if s > 0 else box(s * (Lf / 2 - 0.8), s * (L / 2 + 0.4), -W / 2 + 0.8, W / 2 - 0.8, z, tb + 1)) for s in (-1, 1)]
    return Piece(body, [], [(-Lf * 0.25, -W / 2, "-y"), (Lf * 0.25, -W / 2, "-y")], color=p.color_band, paints=decks)


def _rail_x(p):
    return p.floor_len / 2 - 1.2


def _step_y(p):
    return p.body_w / 2 - 1.0           # keeps its socket inside the floor's edge


def roof(p) -> Piece:
    """Flat, though the real one is very slightly arched. It overhangs the platforms."""
    L, W, t = p.body_len + 2 * p.roof_over_end, p.body_w + 2 * p.roof_over_side, p.roof_t
    cl = p.prop_clearance
    body = box(-L / 2, L / 2, -W / 2, W / 2, 0, t)
    cuts = [box(x - 2.5 - cl, x + 2.5 + cl, -_T / 2 - cl, _T / 2 + cl, -EPS, t + EPS) for x in p.spine_tab_xs]
    for sy in (-1, 1):
        for dx in _cup_tab_xs(p):
            x = p.cupola_x + dx
            cuts.append(box(x - 2 - cl, x + 2 + cl, sy * p.cupola_w / 2 - _T / 2 - cl, sy * p.cupola_w / 2 + _T / 2 + cl,
                            -EPS, t + EPS))
    body = body.cut(*cuts)
    z = t - p.zq(p.color_depth)
    seams = [box(x - 0.4, x + 0.4, -W / 2, W / 2, z, t + 1) for x in _steps(-L / 2 + 6.0, L / 2 - 1.0, 9.0)]
    return Piece(body, [], [(-L * 0.25, -W / 2, "-y"), (L * 0.25, -W / 2, "-y")], color=p.color_roof,
                 paints=[(p.color_band, seams[0].fuse(*seams[1:]))])


def spine(p) -> Piece:
    """A dark sheet down the middle: what you see through the windows. Holds the roof, too."""
    L, H, t = p.side_len - 1.0, p.body_h, p.sheet_t
    body = box(-L / 2, L / 2, 0, H, 0, t)
    adds = []
    for x in p.spine_tab_xs:
        adds.append(tab(x, 0, 6.0, 2.2, t, p.lead_in))
        adds.append(tab(x, H, 5.0, p.roof_t - 0.1, t, 0.3, "+y"))
    # The top tabs show on the roof, so they're the roof's color.
    return Piece(body.fuse(*adds), [], [(-L * 0.45, 0, "-y"), (L * 0.45, 0, "-y")], color=p.color_band,
                 paints=[(p.color_roof, box(-L, L, H, H + 5, -1, t + 1))])


# ---------------------------------------------------------------------------
# The cupola: cross-lapped sheets
# ---------------------------------------------------------------------------
_CUP_TAB_PAST = 0.4     # how far the cupola's tabs stick out past the far side of a roof


def _cup_tab_xs(p):
    return (-p.cupola_len * 0.27, p.cupola_len * 0.27)


def _cup_end_x(p):
    return p.cupola_len / 2 - 1.5


def cupola_side(p) -> Piece:
    """Three windows, painted in a pocket: you can't see inside anyway. Local: x along, y up."""
    L, H, t = p.cupola_len, p.cupola_h, p.sheet_t
    cl = p.prop_clearance
    body = box(-L / 2, L / 2, 0, H, 0, t)
    f = Face(p, t)
    for x in (-L * 0.28, 0, L * 0.28):
        f.pocket(x - 2.4, x + 2.4, 2.2, H - 2.2, 0.4, color=p.color_band)
    body = f.finish(body)
    # Long enough to pass through the roofs, so the chamfered tips don't take up the hole's grip.
    adds = [tab(dx, 0, 4.0, p.roof_t + _CUP_TAB_PAST, t, 0.3) for dx in _cup_tab_xs(p)]
    adds += [tab(dx, H, 3.0, _cup_roof_t(p) + _CUP_TAB_PAST, t, 0.3, "+y") for dx in _cup_tab_xs(p)]
    body = body.fuse(*adds)
    s = t / 2 + cl
    for sx in (-1, 1):
        x = sx * _cup_end_x(p)
        body -= box(x - s, x + s, H / 2, H + EPS, -EPS, t + EPS)
    return Piece(body, [], [(0, 0, "-y")], color=p.color_wall, paints=f.paints)


def cupola_end(p) -> Piece:
    W, H, t = p.cupola_w + 2 * p.cup_over, p.cupola_h, p.sheet_t
    cl = p.prop_clearance
    body = box(-W / 2, W / 2, 0, H, 0, t)
    f = Face(p, t)
    for x in (-W * 0.2, W * 0.2):
        f.pocket(x - 2.4, x + 2.4, 2.2, H - 2.2, 0.4, color=p.color_band)
    body = f.finish(body)
    s = t / 2 + cl
    for sx in (-1, 1):
        x = sx * p.cupola_w / 2
        body -= box(x - s, x + s, -EPS, H / 2, -EPS, t + EPS)
    return Piece(body, [], [(0, H, "+y")], color=p.color_wall, paints=f.paints)


def _cup_roof_t(p):
    return 1.2


def cupola_roof(p) -> Piece:
    L, W, t = p.cupola_len + 4.0, p.cupola_w + 2 * p.cup_over + 2.0, _cup_roof_t(p)
    cl = p.prop_clearance
    body = box(-L / 2, L / 2, -W / 2, W / 2, 0, t)
    cuts = [box(dx - 1.5 - cl, dx + 1.5 + cl, sy * p.cupola_w / 2 - _T / 2 - cl, sy * p.cupola_w / 2 + _T / 2 + cl, -EPS, t + EPS)
            for dx in _cup_tab_xs(p) for sy in (-1, 1)]
    return Piece(body.cut(*cuts), [], [(0, -W / 2, "-y")], color=p.color_roof)


# ---------------------------------------------------------------------------
# Trucks, steps, railings: loose-fit sheets
# ---------------------------------------------------------------------------
def truck_frame(p) -> Piece:
    """One side of a truck, with its two wheels. Local: x along the car, y up from the rail.
    It's one sheet at the gauge, so the wheels' faces and the frame are the same thickness.
    Its slot opens downward and its top stops just under the floor, so once the bolster is in
    the floor the frame is trapped between them and can't drop out."""
    t, r, a = p.sheet_t, p.wheel_r, p.wheelbase / 2
    cl = p.prop_clearance
    wheels = [Pos(x, r) * Circle(r) for x in (-a, a)]
    body = extrude(wheels[0] + wheels[1], t, dir=UP)
    body = body.fuse(box(-a, a, 3.0, 7.6, 0, t), box(-4.0, 4.0, 3.0, p.floor_up - cl, 0, t))
    s = t / 2 + cl
    body -= box(-s, s, 3.0 - EPS, _lap(p), -EPS, t + EPS)
    discs = [(p.color_band, Pos(x, r, -1) * extrude(Circle(r), t + 2, dir=UP)) for x in (-a, a)]
    hubs = [(p.color_wall, Pos(x, r, -1) * extrude(Circle(1.4), t + 2, dir=UP)) for x in (-a, a)]
    return Piece(body, [], [(-3.0, 3.0, "-y")], color=p.color_wall, paints=[*discs, *hubs])


def _lap(p):
    return 6.0


def _bolster_tab_w(p):
    return 8.0


def bolster(p) -> Piece:
    """The frames drop into its slots from above, and its tab holds the whole truck in the
    floor. The tab stops just short of the floor's top, under the spine. Local: x across the car."""
    t, cl = p.sheet_t, p.prop_clearance
    half = p.frame_y + t / 2 + 1.2
    body = box(-half, half, 3.6, p.floor_up, 0, t)
    s = t / 2 + cl
    for sx in (-1, 1):
        x = sx * p.frame_y
        body -= box(x - s, x + s, _lap(p), p.floor_up + EPS, -EPS, t + EPS)
    body = body.fuse(tab(0, p.floor_up, _bolster_tab_w(p), p.floor_t - 0.1, t, p.lead_in, "+y"))
    return Piece(body, [], [(0, 3.6, "-y")], color=p.color_band)


def step(p) -> Piece:
    """Hangs under a platform's corner. Local: y = 0 is the floor's underside."""
    t = p.sheet_t
    body = box(-3.5, 3.5, -7.5, 0, 0, t)
    body -= box(-2.7, 2.7, -3.6, -0.8, -EPS, t + EPS)
    body -= box(-2.7, 2.7, -6.7, -4.4, -EPS, t + EPS)
    body = body.fuse(tab(0, 0, 4.0, 2.2, t, p.lead_in, "+y"))
    return Piece(body, [], [(0, -7.5, "-y")], color=p.color_band)


def end_rail(p) -> Piece:
    """Platform railing with the gate opening in the middle. Local: x across the car."""
    W, H, t = p.body_w - 1.6, p.rail_h, p.sheet_t
    body = box(-W / 2, W / 2, 0, H, 0, t)
    b = 0.9
    cuts = [box(-4.4, 4.4, -EPS, H - b, -EPS, t + EPS)]                   # the gate
    for sx in (-1, 1):
        x0, x1 = sorted((sx * 5.3, sx * (W / 2 - b)))
        mid = H * 0.5
        cuts.append(box(x0, x1, b, mid - b / 2, -EPS, t + EPS))
        cuts.append(box(x0, x1, mid + b / 2, H - b, -EPS, t + EPS))
    body = body.cut(*cuts)
    adds = [tab(sx * p.body_w * 0.36, 0, 2.0, 2.2, t, 0.3) for sx in (-1, 1)]
    return Piece(body.fuse(*adds), [], [(-W * 0.36, -2.2, "-y")], color=p.color_trim)


def display_base(p) -> Piece:
    """A short length of track on ballast, with the paved border the real one has. The car
    just sits on it, so it lifts off."""
    L, D, t = p.base_len, p.base_w, p.base_t
    body = box(-L / 2, L / 2, -D / 2, D / 2, 0, t)
    y = p.frame_y
    rails = [box(-L / 2 + 2, L / 2 - 2, sy * y - _T / 2, sy * y + _T / 2, t - EPS, t + p.base_rail_h) for sy in (-1, 1)]
    body = body.fuse(*rails)
    z = t - p.zq(p.color_depth)
    ties = [box(x - 1.3, x + 1.3, -14.0, 14.0, z, t + 1) for x in _steps(-L / 2 + 5.0, L / 2 - 3.0, 5.5)]
    border = box(-L / 2 - 1, L / 2 + 1, -D / 2 - 1, D / 2 + 1, z, t + 1) - box(-L / 2 + 2, L / 2 - 2, -D / 2 + 2, D / 2 - 2, z - 1, t + 2)
    rail_paint = [box(-L / 2, L / 2, sy * y - _T, sy * y + _T, t, t + 1) for sy in (-1, 1)]
    return Piece(body, [], [(-L * 0.3, -D / 2, "-y"), (L * 0.3, -D / 2, "-y")], color=p.color_base,
                 paints=[(p.color_band, ties[0].fuse(*ties[1:])), (p.color_wall, border),
                         (p.color_trim, rail_paint[0].fuse(rail_paint[1]))])


# ---------------------------------------------------------------------------
# Poses
# ---------------------------------------------------------------------------
def _pose_side(sign):
    def pose(p):
        t = p.wall_thickness
        return (stand(p, -p.side_len / 2, -p.side_y, p.z_deck, (1, 0), t) if sign < 0
                else stand(p, p.side_len / 2, p.side_y, p.z_deck, (-1, 0), t))
    return pose


def _pose_end(sign):
    def pose(p):
        t = p.wall_thickness
        x = p.body_len / 2 - t / 2
        return (stand(p, x, -p.body_w / 2, p.z_deck, (0, 1), t) if sign > 0
                else stand(p, -x, p.body_w / 2, p.z_deck, (0, -1), t))
    return pose


def _pose_cup_side(sign):
    def pose(p):
        z = p.z_roof + p.roof_t
        return (stand(p, p.cupola_x, -p.cupola_w / 2, z, (1, 0), _T) if sign < 0
                else stand(p, p.cupola_x, p.cupola_w / 2, z, (-1, 0), _T))
    return pose


def _pose_cup_end(sign):
    def pose(p):
        z = p.z_roof + p.roof_t
        x = p.cupola_x + sign * _cup_end_x(p)
        return stand(p, x, 0, z, (0, sign), _T)
    return pose


def _pose_frame(truck, sign):
    def pose(p):
        return stand(p, p.truck_xs[truck], sign * p.frame_y, p.z_rail, (1, 0), _T)
    return pose


def _pose_bolster(truck):
    def pose(p):
        return stand(p, p.truck_xs[truck], 0, p.z_rail, (0, 1), _T)
    return pose


def _pose_step(sx, sy):
    def pose(p):
        return stand(p, sx * p.step_x, sy * _step_y(p), p.z_floor, (1, 0), _T)
    return pose


def _pose_rail(sign):
    def pose(p):
        return stand(p, sign * _rail_x(p), 0, p.z_deck, (0, sign), _T)
    return pose


_LIST = [
    ("display_base", display_base, lambda p: Location((0, 0, 0))),
    ("floor", floor, lambda p: Location((0, 0, p.z_floor))),
    ("side_west", side_west, _pose_side(-1)),
    ("side_east", side_east, _pose_side(1)),
    ("end_south", end_wall, _pose_end(1)),
    ("end_north", end_wall, _pose_end(-1)),
    ("spine", spine, lambda p: stand(p, 0, 0, p.z_deck, (1, 0), _T)),
    ("roof", roof, lambda p: Location((0, 0, p.z_roof))),
    ("cup_side_w", cupola_side, _pose_cup_side(-1)),
    ("cup_side_e", cupola_side, _pose_cup_side(1)),
    ("cup_end_s", cupola_end, _pose_cup_end(1)),
    ("cup_end_n", cupola_end, _pose_cup_end(-1)),
    ("cup_roof", cupola_roof, lambda p: Location((p.cupola_x, 0, p.z_roof + p.roof_t + p.cupola_h))),
    *[(f"frame_{t}{s}", truck_frame, _pose_frame(i, sign)) for i, t in enumerate("ns")
      for s, sign in (("w", -1), ("e", 1))],
    *[(f"bolster_{t}", bolster, _pose_bolster(i)) for i, t in enumerate("ns")],
    *[(f"step_{a}{b}", step, _pose_step(sx, sy)) for a, sx in (("n", -1), ("s", 1)) for b, sy in (("w", -1), ("e", 1))],
    ("rail_s", end_rail, _pose_rail(1)),
    ("rail_n", end_rail, _pose_rail(-1)),
]

REGISTRY = [Spec(i + 1, name, make, pose) for i, (name, make, pose) in enumerate(_LIST)]

_TOOLS = ("red", "cream", "coal", "ballast")
PLATES = (
    Plate("all", _TOOLS, tuple(name for name, *_ in _LIST), sprue="ballast", label="coal"),
)
