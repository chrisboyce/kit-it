"""Colfax Market: the false-front store at Main St and W Grass Valley St, Colfax.

Sizes come from Street View (see README, "Colfax Market kit"). The front is at full
scale. The long brick side is really well over 100 ft; it's selectively compressed to
46 ft, so it fits the bed in one piece and keeps the corner end, the mural and the
rear door.

The joints follow the Creative Corner's two tiers: the walls and base use split tabs,
and everything else is a loose-fit sheet. New here are the sloped roofs: a support's
vertical tab goes up through an angled slot in the sheet (roof_slot), so each sheet
just lowers straight down onto its supports.

World frame, as in corner.py: X along W Grass Valley St (rear at x=0, Main St at +x),
Y from the Grass Valley curb into the building, Z up. The side wall's front face is
at y = sidewalk and the front wall's front face is at x = side_len.
"""

import math
import os
from dataclasses import dataclass

from build123d import Align, Circle, Location, Plane, Polygon, Pos, Text, extrude

from corner import (CornerParams, Face, _backer, _base_slab, _behind, _curb_edge, _peg_pockets, _plant_a, _plant_b,
                    _plant_pose, _sidewalk_joints, _sock, _steps, _utility_cover, stand)
from joints import EPS, UP, Piece, box, split_tab, tab
from params import ft
from registry import Spec
from sprue import Plate
from vary import Vary

X, Y = (1, 0, 0), (0, 1, 0)
NEG_Y = (0, -1, 0)
# The sign's letters are a slab-ish serif. flake.nix pins the DejaVu package.
_FONT = os.environ.get("COLFAX_FONT")
SERIF = _FONT.replace("DejaVuSans-Bold", "DejaVuSerif-Bold") if _FONT else None


@dataclass(frozen=True)
class MarketParams(CornerParams):
    # --- color: five filaments, sampled from the photos ---------------------
    palette: tuple = (
        ("brick", "#7d4632"),
        ("cream", "#e9e4d6"),
        ("coal", "#2a2a2b"),
        ("tin", "#a9a89f"),
        ("moss", "#5b7a3d"),
    )
    color_wall: str = "brick"
    color_band: str = "coal"
    color_trim: str = "cream"
    color_sign: str = "cream"
    color_door: str = "brick"
    color_bulkhead: str = "coal"
    color_base: str = "tin"
    color_deck_top: str = "tin"
    color_roof: str = "tin"
    color_glass: str = "coal"
    color_planter: str = "brick"
    color_shrub: str = "moss"
    color_shade: str = "coal"
    color_sprue: str = "tin"
    color_label: str = "coal"
    color_post: str = "coal"
    variation_seed: int = 1

    # --- massing ------------------------------------------------------------
    side_len: float = ft(46)            # really well over 100 ft: see the docstring
    front_w: float = ft(27.5)
    front_h: float = ft(25.6)
    shoulder: float = ft(4)             # how far the false front's shoulder passes the corner
    front_proud: float = 1.2            # past the side wall's face: room for the corner sockets
    shoulder_high: float = ft(21)
    sidewalk: float = ft(8.5)           # curb face line to the side wall, with the street strip
    street_strip: float = ft(1.5)
    front_walk: float = ft(8)
    eave_z: float = ft(11)              # above the sidewalk
    roof_pitch: float = 12.0            # degrees
    roof_t: float = 1.6
    awning_top: float = ft(13.3)
    awning_eave: float = ft(9.8)
    awning_t: float = 1.2
    tree_half: float = 9.5
    tree_pot_h: float = 6.0
    tree_h: float = 25.0

    @property
    def base_x(self):
        return self.side_len + self.front_walk + self.street_strip

    @property
    def base_y(self):
        return self.sidewalk + self.wall_thickness + self.front_w + 3.0

    @property
    def side_panel(self):
        return self.side_len - self.wall_thickness

    @property
    def roof_x1(self):
        """It stops just short of the back of the front wall."""
        return self.side_panel - 0.2

    @property
    def eave_y(self):
        return self.street_strip + 1.0

    @property
    def ridge_y(self):
        return self.sidewalk + self.wall_thickness + self.front_w / 2

    @property
    def post_y(self):
        return self.eave_y + 1.6

    @property
    def side_post_xs(self):
        return (self.side_len * 0.12, self.side_len * 0.38, self.side_len * 0.62, self.side_len * 0.86)

    @property
    def rafter_xs(self):
        return (3.0, self.side_len * 0.55)

    @property
    def side_h(self):
        """The wall stops just under the roof sheet."""
        return self.eave_z + (self.sidewalk - self.eave_y) * math.tan(math.radians(self.roof_pitch)) - 0.3

    @property
    def awning_x(self):
        return self.side_len + ft(7.2)

    @property
    def awning_pitch(self):
        return math.degrees(math.atan((self.awning_top - self.awning_eave) / (self.awning_x - self.side_len)))

    @property
    def front_post_ys(self):
        return (self.sidewalk + ft(5), self.sidewalk + ft(20))

    @property
    def tree_xy(self):
        return (self.side_len * 0.74, self.street_strip + 9.0)

    @property
    def front_tab_ys(self):
        return (ft(3.0), ft(15.0))

    @property
    def side_tab_xs(self):
        return (self.side_len * 0.2, self.side_len * 0.72)

    @property
    def corner_ys(self):
        return (self.side_h * 0.25, self.side_h * 0.7)


DEFAULT = MarketParams()


def roof_under(p, y):
    """World height (above the sidewalk) of the side roof's underside at y."""
    return p.eave_z + (y - p.eave_y) * math.tan(math.radians(p.roof_pitch))


def awning_under(p, x):
    return p.awning_eave + (p.awning_x - x) * math.tan(math.radians(p.awning_pitch))


def roof_slot(p, x, run, tab_w, tab_t, sheet_t, pitch):
    """Slot in a sloped sheet for a vertical tab, in the sheet's local frame. `run` is the
    horizontal distance up the slope from the eave. It's longer up the slope than the tab
    is thick, so the tab passes at the sheet's angle."""
    a = math.radians(pitch)
    cl = p.prop_clearance
    y = run / math.cos(a)
    half = tab_t / 2 / math.cos(a) + sheet_t * math.tan(a) / 2 + cl
    return box(x - tab_w / 2 - cl, x + tab_w / 2 + cl, y - half, y + half, -EPS, sheet_t + EPS)


# ---------------------------------------------------------------------------
# Main panels (split tabs)
# ---------------------------------------------------------------------------
def _lettering(p, text, x, y, size, z, t):
    letters = Text(text, size, font_path=SERIF, align=(Align.CENTER, Align.CENTER))
    return Pos(x, y, z) * extrude(letters, t + 10 - z, dir=UP)


def _store_pegs(p):
    return (ft(1.6), ft(25.8), 3.6, ft(10.4))


def wall_front(p) -> Piece:
    """Main St false front. Local: x north along the wall, from the side wall's front
    face; y up; z out of the front. The shoulder passes the corner at negative x."""
    W, H, tw, s = p.front_w, p.front_h, p.wall_thickness, p.shoulder
    body = box(-p.front_proud, W, 0, H, 0, tw)
    low = p.awning_top + 0.2            # closes the gap above the awning
    wing = Polygon((-s, low), (EPS, low), (EPS, p.shoulder_high), align=None)
    body = body.fuse(extrude(wing, tw, dir=UP))
    f = Face(p, tw)

    # Vertical boards above the awning, and a top rail. They stop short of the lettering.
    y0 = p.awning_top + 1.5
    lx0, lx1, ly0, ly1 = W / 2 - ft(7.5), W / 2 + ft(7.5), ft(15.1), ft(21.0)
    x = -s + 3.0
    while x < W - 1.0:
        top = H - 1.6 if x >= 0 else low + (x + s) / s * (p.shoulder_high - low) - 1.0
        if top > y0 + 2:
            spans = [(y0, ly0), (ly1, top)] if lx0 < x < lx1 else [(y0, top)]
            for a, b in spans:
                f.raised(x - 0.4, x + 0.4, a, b, h=p.batten_raise)
        x += 3.5
    f.raised(0, W, H - 1.6, H, h=0.4, color=p.color_band)

    # Ground floor: the display windows and the door.
    sx0, sx1 = ft(3.1), ft(19.4)
    sill, head = ft(2.0), ft(8.1)
    f.window(sx0, sx1, sill, head)
    for m in (0.25, 0.5, 0.75):
        xm = sx0 + m * (sx1 - sx0)
        f.late.append(box(xm - 0.4, xm + 0.4, sill - EPS, head + EPS, 0, tw))
        f.paints.append((p.color_trim, box(xm - 0.4, xm + 0.4, sill, head, -EPS, tw + 10)))
    dx0, dx1 = ft(21.8), ft(24.5)
    f.raised(dx0 - 0.8, dx1 + 0.8, 0, ft(7.2) + 0.8, color=p.color_trim)
    f.hole(dx0 + 0.8, dx1 - 0.8, ft(2.2), ft(6.6))

    # The sign band over the windows, with its lettering as word blocks.
    by0, by1 = ft(8.5), ft(9.5)
    f.raised(ft(1.5), W - ft(1.2), by0, by1, color=p.color_band)
    ym = (by0 + by1) / 2
    f.paint_all(p.color_trim, [(ft(3.5), ft(9.5), ym - 0.5, ym + 0.5), (ft(10.7), ft(16.5), ym - 0.5, ym + 0.5),
                               (ft(17.7), ft(24.5), ym - 0.5, ym + 0.5)])

    # Pockets for the awning's back tabs: they arrive at the awning's angle.
    a = math.radians(p.awning_pitch)
    d, cl = p.zq(p.deck_tab_pocket), p.prop_clearance
    rise = p.awning_t / math.cos(a) + d * math.tan(a)
    for y in _awning_tab_ys(p):
        f.cuts.append(box(y - 4 - cl, y + 4 + cl, p.awning_top - cl, p.awning_top + rise + cl, tw - d, tw + 10))

    adds, cuts = [], []
    for x in p.front_tab_ys:
        t, slit = split_tab(x, 0, p, p.base_tab_len, p.base_tab_barb_at, tw)
        adds.append(t)
        cuts.append(slit)
    # Blind pockets in the back for the side wall's end tabs.
    cs = p.split_clearance
    for y in p.corner_ys:
        cuts.append(_sock(tw / 2, y, tw + 2 * cs, p.split_width + 2 * cs, 0, p.zq(p.corner_tab_len + 0.2), p,
                          mouth="bottom"))
    cuts += _peg_pockets(p, _store_pegs(p))
    body = f.finish(body).fuse(*adds).cut(*cuts)
    z = tw - p.zq(p.color_depth)
    paints = f.paints + [(p.color_trim, _lettering(p, "COLFAX", W / 2, ft(19.3), ft(3.3), z, tw)),
                         (p.color_trim, _lettering(p, "MARKET", W / 2, ft(16.4), ft(3.3), z, tw))]
    return Piece(body, [], [(2.0, 0, "-y"), (W - 2.0, 0, "-y")], color=p.color_wall, paints=paints)


def _figure(p, x, kind, z, t):
    """A miner from the mural, flat on the wall. At least 0.8 mm wide everywhere."""
    def b(x0, x1, y0, y1):
        return box(x + x0, x + x1, y0, y1, z, t + 10)

    def head(cx, cy, r=1.2):
        return Pos(x + cx, cy, z) * extrude(Circle(r), t + 10 - z, dir=UP)

    if kind == "pick":          # walking, with a pick over his shoulder
        pick = Polygon((-6.0, 15.2), (-5.5, 16.0), (2.5, 13.2), (2.0, 12.4), align=None)
        return [b(-1.6, -0.3, 0, 8), b(0.3, 1.6, 0, 8), b(-1.8, 1.8, 7.5, 15.5), head(0, 17.2),
                b(-2.2, 2.2, 18.1, 18.9), Pos(x, 0, z) * extrude(pick, t + 10 - z, dir=UP)]
    if kind == "dress":         # in a long dress and a broad hat
        skirt = Polygon((-3.4, 0), (3.4, 0), (1.6, 11), (-1.6, 11), align=None)
        return [Pos(x, 0, z) * extrude(skirt, t + 10 - z, dir=UP), b(-1.6, 1.6, 10.5, 15.5), head(0, 17.0),
                b(-2.6, 2.6, 18.0, 18.8)]
    # Bent over a mining pan, on one knee.
    back = Polygon((-1.0, 7.5), (0.8, 8.5), (6.5, 11.5), (6.0, 7.5), align=None)
    return [b(-1.6, 0.2, 0, 8), b(1.8, 3.4, 0, 5), Pos(x, 0, z) * extrude(back, t + 10 - z, dir=UP),
            head(7.4, 10.6), b(5.6, 8.6, 0, 1.0), b(6.6, 7.6, 0.5, 8)]


def wall_side(p) -> Piece:
    """W Grass Valley St wall. Local: x east along the wall, y up, z out of the front."""
    L, H, tw = p.side_panel, p.side_h, p.wall_thickness
    body = box(0, L, 0, H, 0, tw)
    f = Face(p, tw)

    dx = ft(3.5)
    by0, by1 = ft(8.6), ft(10.2)
    boards = ((L * 0.36, L * 0.36 + 17.0), (L * 0.52, L * 0.52 + 15.0))
    keep_clear = [(dx - 1.5, dx + 12.5, -1, ft(8.8) + 1), (dx + 15, dx + 25, H - 11.5, H - 3.5),
                  *[(x0 - 1, x1 + 1, by0 - 1, by1 + 1) for x0, x1 in boards]]
    # Brick: staggered dashes for the courses, stopping at the plastered end by the corner,
    # and kept off the raised features so they don't cut through them.
    plain = L - ft(9)
    jd = p.zq(0.2)
    for row, y in enumerate(_steps(2.0, H - 1.5, 2.6)):
        for x in _steps(-4.0 * (row % 2), plain - 7.0, 9.0):
            x0, x1 = max(x, 0.0), x + 8.0
            if not any(x1 > a and x0 < b and y + 0.3 > c and y - 0.3 < d for a, b, c, d in keep_clear):
                f.cuts.append(box(x0, x1, y - 0.3, y + 0.3, tw - jd, tw + 10))
    f.raised(plain, L, 0, H, h=0.2)

    # The rear door, with a transom, and an air conditioner above it.
    f.door(dx, dx + 11.0, 0, ft(7), screen=True)
    f.raised(dx - 0.8, dx + 11.8, ft(7), ft(8.8), color=p.color_trim)
    f.raised(dx + 16, dx + 24, H - 10.5, H - 4.5, h=0.6, color=p.color_roof)

    # Grocery and liquor boards: green in life, in a kit color here.
    z = tw - p.zq(p.color_depth)
    for x0, x1 in boards:
        f.raised(x0, x1, by0, by1, color=p.color_band)
        f.paint(p.color_trim, x0 + 1.5, x1 - 1.5, (by0 + by1) / 2 - 0.7, (by0 + by1) / 2 + 0.7)

    adds, cuts = [], []
    for x in p.side_tab_xs:
        t, slit = split_tab(x, 0, p, p.base_tab_len, p.base_tab_barb_at, tw)
        adds.append(t)
        cuts.append(slit)
    for y in p.corner_ys:
        t, slit = split_tab(L, y, p, p.corner_tab_len, p.corner_tab_barb_at, tw, direction="+x")
        adds.append(t)
        cuts.append(slit)
    body = f.finish(body).fuse(*adds).cut(*cuts)

    # The miners, one paint for all: they're the first thing you see on this wall.
    figures = []
    for x, kind in ((L * 0.20, "pick"), (L * 0.34, "dress"), (L * 0.48, "pick"), (L * 0.56, "bend")):
        figures += _figure(p, x, kind, z, tw)
    mural = figures[0].fuse(*figures[1:])
    return Piece(body, [], [(0.08 * L, 0, "-y"), (0.9 * L, 0, "-y")], color=p.color_wall,
                 paints=[*f.paints, (p.color_band, mural)])


def base(p) -> Piece:
    """One slab: both sidewalks and the floor ring, with the rounded street corner."""
    X1, D, tb, tw, S, L = p.base_x, p.base_y, p.base_thickness, p.wall_thickness, p.sidewalk, p.side_len
    cs, cl = p.split_clearance, p.prop_clearance
    body = _base_slab(p, 0, X1, 0, D, corner=True)
    cuts = []
    _sidewalk_joints(p, 0, L - 3.0, S - 0.6, p.joint_spacing, cuts)
    # Open up the floor between the rafters: nothing inside shows.
    xm = p.rafter_xs[1]
    cuts.append(box(10, xm - 5, S + 10, D - 8, -EPS, tb + EPS))
    cuts.append(box(xm + 5, L - 12, S + 10, D - 8, -EPS, tb + EPS))

    for x in p.side_tab_xs:
        cuts.append(_sock(x, S + tw / 2, p.split_width + 2 * cs, tw + 2 * cs, 0, tb, p))
    for y in p.front_tab_ys:
        cuts.append(_sock(L - tw / 2, S + y, tw + 2 * cs, p.split_width + 2 * cs, 0, tb, p))

    def pocket(cx, cy, sx, sy, length):
        return _sock(cx, cy, sx + 2 * cl, sy + 2 * cl, tb - p.zq(length + 0.2), tb, p)

    for x in p.side_post_xs:
        cuts.append(pocket(x, p.post_y, _SIDE_POST_W, _SIDE_POST_T, p.post_tab_len))
    for y in p.front_post_ys:
        cuts.append(pocket(p.awning_x - 2.0, y, _FRONT_POST_T, _FRONT_POST_W, p.post_tab_len))
    for x in p.rafter_xs:
        cuts.append(pocket(x, _rafter_tab_y(p), p.sheet_t, 6.0, p.post_tab_len))
    # Both sheets of the tree stand on sheet A's tab.
    tx, ty = p.tree_xy
    cuts.append(pocket(tx, ty, p.prop_tab_width, p.prop_thickness, p.prop_tab_len))
    body = body.cut(*cuts)
    paints = [(p.color_wall, _curb_edge(p, 0, X1, 0, D, corner=True)),
              (p.color_band, _utility_cover(p, L * 0.3, 14.0, 2.4))]
    return Piece(body, [], [(0.3 * X1, D, "+y"), (0.7 * X1, D, "+y")], color=p.color_base, paints=paints)


# ---------------------------------------------------------------------------
# Sloped roofs: sheets that lower straight down onto vertical tabs
# ---------------------------------------------------------------------------
_SIDE_POST_W, _SIDE_POST_T = 1.6, 1.2
_FRONT_POST_W, _FRONT_POST_T = 2.4, 1.6


def _awning_tab_ys(p):
    """In the front wall's local x."""
    return (ft(5.5), ft(22))


def _rafter_tab_y(p):
    return (p.sidewalk + p.wall_thickness + p.ridge_y) / 2


def roof_side(p) -> Piece:
    """The tin roof: one sheet from the ridge, over the wall and sidewalk, to the eave.
    Local: x east, y up the slope from the eave, z out of the top."""
    L, t = p.roof_x1, p.roof_t
    a = math.radians(p.roof_pitch)
    D = (p.ridge_y - p.eave_y) / math.cos(a)
    body = box(0, L, 0, D, 0, t)
    cuts = [roof_slot(p, x, p.post_y - p.eave_y, _SIDE_POST_W, _SIDE_POST_T, t, p.roof_pitch) for x in p.side_post_xs]
    run = _rafter_top_y(p) - p.eave_y
    cuts += [roof_slot(p, x, run, p.sheet_t, 3.0, t, p.roof_pitch) for x in p.rafter_xs]
    body = body.cut(*cuts)

    z = t - p.zq(p.color_depth)
    ribs = [box(x - p.accent_w / 2, x + p.accent_w / 2, 0, D, z, t + 1) for x in _steps(4.0, L - 1.0, 9.0)]
    paints = [(p.color_band, ribs[0].fuse(*ribs[1:])),
              (p.color_band, box(-1, L + 1, -1, p.accent_w, -1, t + 1))]     # the fascia
    return Piece(body, [], [(0.25 * L, D, "+y"), (0.75 * L, D, "+y")], color=p.color_roof, paints=paints)


def awning(p) -> Piece:
    """Over the Main St sidewalk, and past the corner under the false front's shoulder.
    Local: x north, y up the slope from the eave, z out of the top."""
    W, t = p.front_w + p.shoulder, p.awning_t
    a = math.radians(p.awning_pitch)
    D = (p.awning_x - p.side_len) / math.cos(a)
    body = box(0, W, 0, D, 0, t)
    y0 = p.sidewalk - p.shoulder
    adds = [tab(y + p.shoulder, D, 8.0, p.zq(p.deck_tab_pocket) - 0.4, t, p.lead_in, "+y") for y in _awning_tab_ys(p)]
    body = body.fuse(*adds)
    body = body.cut(*[roof_slot(p, y - y0, 2.0, _FRONT_POST_W, _FRONT_POST_T, t, p.awning_pitch)
                      for y in p.front_post_ys])
    z = t - p.zq(p.color_depth)
    ribs = [box(x - p.accent_w / 2, x + p.accent_w / 2, 0, D, z, t + 1) for x in _steps(3.0, W - 1.0, 4.5)]
    paints = [(p.color_band, ribs[0].fuse(*ribs[1:])), (p.color_band, box(-1, W + 1, -1, p.accent_w, -1, t + 1))]
    # The gate goes between the tabs: its edge is hidden against the wall, and a nub on a
    # tab could spoil its fit in the pocket.
    gate = sum(_awning_tab_ys(p)) / 2 + p.shoulder
    return Piece(body, [], [(gate, D, "+y")], color=p.color_wall, paints=paints)


def _post(p, h, w, t, tab_len, collar=True) -> Piece:
    """A plain post up to a shoulder, with a tab for the sheet above."""
    body = box(-w / 2, w / 2, 0, h, 0, t)
    adds = [tab(0, 0, w, p.post_tab_len, t, p.lead_in), tab(0, h, w, tab_len, t, 0.2, "+y")]
    body = body.fuse(*adds)
    paints = [(p.color_trim, box(-w, w, h - 1.5, h, -1, t + 1))] if collar else []
    return Piece(body, [], [(0, -p.post_tab_len, "-y")], color=p.color_post, paints=paints)


def post_side(p) -> Piece:
    """Thin iron post at the curb. Its shoulder stops where the sloped underside would hit it."""
    a = math.tan(math.radians(p.roof_pitch))
    h = roof_under(p, p.post_y) - _SIDE_POST_T / 2 * a - 0.05
    return _post(p, h, _SIDE_POST_W, _SIDE_POST_T, p.roof_t * 0.8, collar=False)


def post_front(p) -> Piece:
    a = math.tan(math.radians(p.awning_pitch))
    h = awning_under(p, p.awning_x - 2.0) - _FRONT_POST_T / 2 * a - 0.05
    return _post(p, h, _FRONT_POST_W, _FRONT_POST_T, p.awning_t * 0.8)


def _rafter_top_y(p):
    return p.ridge_y - 6.0


def rafter(p) -> Piece:
    """A brick end under the roof's upper part: holds it up, and closes the rear gable.
    Local: x into the building from the side wall's back, y up."""
    y0 = p.sidewalk + p.wall_thickness + 0.3
    L = p.ridge_y - y0
    h0, h1 = roof_under(p, y0) - 0.1, roof_under(p, p.ridge_y) - 0.1
    t = p.sheet_t
    plate = Polygon((0, 0), (L, 0), (L, h1), (0, h0), align=None)
    body = extrude(plate, t, dir=UP)
    xt = _rafter_top_y(p) - y0
    top = roof_under(p, _rafter_top_y(p))
    adds = [tab(_rafter_tab_y(p) - y0, 0, 6.0, p.post_tab_len, t, p.lead_in),
            box(xt - 1.5, xt + 1.5, top - 1.5, top + p.roof_t * 0.8, 0, t)]
    body = body.fuse(*adds)
    return Piece(body, [], [(_rafter_tab_y(p) - y0, -p.post_tab_len, "-y")], color=p.color_wall)


# ---------------------------------------------------------------------------
# Backer, tree
# ---------------------------------------------------------------------------
def backer_store(p) -> Piece:
    """Dark sheet behind the windows, with the posters that fill them."""
    W, t = p.front_w, p.backer_t
    z = t - p.zq(p.color_depth)
    v = Vary(p, "posters")
    sx0, sx1, sill, head = ft(3.1), ft(19.4), ft(2.0), ft(8.1)
    colors = (p.color_roof, p.color_shrub, p.color_wall)    # what its plate has loaded
    paints = []
    for x in _steps(sx0 + 1.0, sx1 - 3.0, 4.2):
        y = sill + 1.0
        while y < head - 3.0:
            h = v.between(3.0, 6.5, 4.5)
            top = min(y + h, head - 1.0)
            w = v.between(2.0, 3.4, 3.0)
            if v.chance(0.8):
                paints.append((v.pick(colors), box(x, x + w, y, top, z, t)))
            y = top + 1.0
    # A poster in the door's glass.
    paints.append((p.color_roof, box(ft(21.8) + 2.5, ft(24.5) - 2.5, ft(3.0), ft(5.4), z, t)))
    x0 = p.wall_thickness + 0.3         # clear of the side wall, which meets the front wall's back
    return _backer(p, x0, W - 1.0, 1.0, ft(10.8), _store_pegs(p), (8.0, W - 6.0), paints=paints)


def _tree_a(p):
    return _plant_a(p, "tree", p.tree_half, p.tree_pot_h, p.tree_h, p.prop_tab_len, p.prop_tab_width)


def _tree_b(p):
    return _plant_b(p, "tree", p.tree_half, p.tree_pot_h, p.tree_h)


# ---------------------------------------------------------------------------
# Poses
# ---------------------------------------------------------------------------
def _pose_side(p):
    return Location(Plane((0, p.sidewalk + p.wall_thickness, p.base_thickness), X, NEG_Y))


def _pose_front(p):
    return Location(Plane((p.side_len - p.wall_thickness, p.sidewalk, p.base_thickness), Y, X))


def _pose_roof(p):
    a = math.radians(p.roof_pitch)
    return Location(Plane((0, p.eave_y, p.base_thickness + p.eave_z), X, (0, -math.sin(a), math.cos(a))))


def _pose_awning(p):
    a = math.radians(p.awning_pitch)
    return Location(Plane((p.awning_x, p.sidewalk - p.shoulder, p.base_thickness + p.awning_eave), Y,
                          (math.sin(a), 0, math.cos(a))))


def _pose_side_post(i):
    def pose(p):
        return stand(p, p.side_post_xs[i], p.post_y, p.base_thickness, (1, 0), _SIDE_POST_T)
    return pose


def _pose_front_post(i):
    def pose(p):
        return stand(p, p.awning_x - 2.0, p.front_post_ys[i], p.base_thickness, (0, 1), _FRONT_POST_T)
    return pose


def _pose_rafter(i):
    def pose(p):
        y0 = p.sidewalk + p.wall_thickness + 0.3
        return stand(p, p.rafter_xs[i], y0, p.base_thickness, (0, 1), p.sheet_t)
    return pose


def _tree_place(p):
    return (*p.tree_xy, X, p.base_thickness)


_LIST = [
    ("base", base, lambda p: Location(Plane.XY)),
    ("wall_front", wall_front, _pose_front),
    ("wall_side", wall_side, _pose_side),
    ("backer", backer_store, _behind(_pose_front)),
    ("roof", roof_side, _pose_roof),
    ("awning", awning, _pose_awning),
    ("rafter_rear", rafter, _pose_rafter(0)),
    ("rafter_mid", rafter, _pose_rafter(1)),
    *[(f"post_s{i}", post_side, _pose_side_post(i)) for i in range(4)],
    *[(f"post_f{i}", post_front, _pose_front_post(i)) for i in range(2)],
    ("tree_a", _tree_a, _plant_pose(_tree_place, False)),
    ("tree_b", _tree_b, _plant_pose(_tree_place, True)),
]

REGISTRY = [Spec(i + 1, name, make, pose) for i, (name, make, pose) in enumerate(_LIST)]

_MAIN = ("brick", "cream", "coal", "tin")
# Printed in this order, only plate 3 needs a spool change: moss for cream.
PLATES = (
    Plate("ground", _MAIN, ("base", "post_s0", "post_s1", "post_s2", "post_s3", "post_f0", "post_f1"),
          sprue="tin", label="coal"),
    Plate("walls", _MAIN, ("wall_front", "wall_side", "rafter_rear"), sprue="tin", label="coal"),
    Plate("roof", ("brick", "moss", "coal", "tin"), ("roof", "awning", "backer", "rafter_mid", "tree_a", "tree_b"),
          sprue="tin", label="coal"),
)
