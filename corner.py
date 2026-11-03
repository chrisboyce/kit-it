"""Creative Corner: the two-story corner building at Main St and Church St, Colfax.

Sizes come from Street View (see README, "Creative Corner kit"). Church St is
really ~97 ft long; it's selectively compressed to three balcony bays plus the
solid west end, so it fits the bed in one piece.

Two tiers of joint:
  * Main panels (walls, base) use split tabs at split_clearance. They carry the
    model and set its alignment.
  * Features (storefront, balcony, overhang, railings, furniture) are 1.2-2 mm
    sheets, cross-lapped or tabbed at prop_clearance with no ribs or barbs. They
    only have to stay put, and they're what gives the building its depth.

World frame: X along Church St (west end at x=0, Main St corner at +x), Y from
the Church St curb into the building, Z up, base underside at z=0. The Church St
wall's front face is at y = sidewalk; the Main St wall's front face is at
x = church_length.
"""

import math
from dataclasses import dataclass

from build123d import Circle, Ellipse, Location, Plane, Polygon, Pos, Rectangle, Rot, extrude

from joints import EPS, UP, Piece, box, bridge_roof, socket, split_tab, tab
from params import Params, ft
from registry import Spec

X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
NEG_X, NEG_Y = (-1, 0, 0), (0, -1, 0)


@dataclass(frozen=True)
class CornerParams(Params):
    # --- color: four tools, see README ---------------------------------------
    palette: tuple = (
        ("sage", "#9dba97"),
        ("stone", "#ddd6c3"),
        ("iron", "#24483a"),
        ("rust", "#b5592d"),
    )
    color_wall: str = "sage"
    color_trim: str = "stone"
    color_sign: str = "stone"
    color_door: str = "rust"
    color_base: str = "stone"
    color_planter: str = "stone"
    color_shrub: str = "iron"
    color_sprue: str = "stone"
    color_label: str = "iron"
    color_post: str = "iron"           # posts, outriggers, railings, furniture

    # --- sprue: a bit tighter than the nook, there's a lot to fit -------------
    part_spacing: float = 7.0
    first_fit: bool = True

    # --- massing (scale) -----------------------------------------------------
    church_length: float = ft(52)      # west end to the Main St wall's front face
    main_width: float = ft(27)
    pavilion: float = ft(12)           # solid west end of the Church St wall
    west_return: float = ft(12)
    sidewalk: float = ft(11)           # curb face line to Church St wall
    street_strip: float = ft(1.5)
    roof_z: float = ft(30)             # Church St parapet
    pier_z: float = ft(31.5)           # corner piers
    main_parapet_z: float = ft(28.5)
    deck_z: float = ft(12.3)           # sidewalk to underside of the balcony
    upper_height: float = ft(9)        # balcony floor to underside of the overhang
    pier_width: float = ft(3)
    main_pier_proud: float = 1.2       # Main St wall sticks out past the Church St wall face
    storefront_top: float = ft(11)
    entry_center: float = 0.56         # along the Main St wall, as a fraction
    entry_width: float = ft(4.5)
    entry_inset: float = ft(4)         # door panel behind the storefront

    # --- feature sheets (printer-driven) -------------------------------------
    deck_t: float = 2.0
    deck_depth: float = ft(7.5)
    overhang_t: float = 1.6
    overhang_depth: float = ft(8)
    sheet_t: float = 1.2               # outriggers, rails, cheeks, cornice
    storefront_t: float = 1.6
    post_w: float = 2.0
    post_t: float = 1.6
    post_line_inset: float = 1.6       # post/rail centerline, in from the balcony's edge
    post_foot_w: float = 3.2
    post_foot_h: float = 1.5
    post_tab_len: float = 2.2
    head_h: float = 8.0
    head_half: float = 8.0
    head_tab_x: float = 4.0            # lower post's two tabs into the deck
    head_tab_w: float = 1.6
    outrigger_h: float = 6.0
    outrigger_stand_off: float = 0.5   # clear of wall relief
    rail_h: float = ft(3.2)
    rail_bar: float = 0.8
    rail_top_bar: float = 1.0
    rail_picket: float = 0.7
    rail_pitch: float = 2.0
    rail_tab_w: float = 2.0
    furniture_t: float = 1.0
    table_h: float = ft(2.5)
    outrigger_cross: float = 4.0       # how far the outrigger drops into the post's slot

    # --- panel joints --------------------------------------------------------
    corner_tab_len: float = 2.0        # blind pocket + its chamfered roof, in a 3 mm wall
    corner_tab_barb_at: float = 0.1
    base_tab_len: float = 3.3
    base_tab_barb_at: float = 1.2
    base_key_len: float = 5.0          # base A's tabs into base B
    base_key_t: float = 2.0            # they stay under the sidewalk's top skin
    deck_tab_pocket: float = 1.8       # feature tabs into a wall's front face

    # --- relief --------------------------------------------------------------
    relief: float = 0.4
    batten_raise: float = 0.2
    batten_pitch: float = 5.0
    seam_pitch: float = 7.0
    trim_w: float = 1.0
    door_recess: float = 0.6

    # --- derived -------------------------------------------------------------
    @property
    def church_panel(self):
        """Length of the Church St panel: it stops at the Main St wall's back."""
        return self.church_length - self.wall_thickness

    @property
    def deck_top(self):
        return self.deck_z + self.deck_t

    @property
    def eave_z(self):
        return self.deck_top + self.upper_height

    @property
    def main_panel(self):
        return self.main_width + self.main_pier_proud

    @property
    def base_a_x(self):
        return self.church_length + 6.0

    @property
    def base_x(self):
        return self.church_length + self.sidewalk

    @property
    def base_y(self):
        return self.sidewalk + self.main_width

    @property
    def church_post_xs(self):
        x0, x1, n = self.pavilion + 4.0, self.church_panel - 3.5, 4
        return tuple(x0 + (x1 - x0) * i / (n - 1) for i in range(n))

    @property
    def main_post_ys(self):
        # The last post stands far enough in that its bracket stays on the wall.
        y0, y1, n = self.sidewalk + 2.0, self.sidewalk + self.main_width - self.head_half - 0.5, 4
        return tuple(y0 + (y1 - y0) * i / (n - 1) for i in range(n))

    @property
    def bay_centers(self):
        xs = self.church_post_xs
        return tuple((a + b) / 2 for a, b in zip(xs, xs[1:]))

    @property
    def post_line_y(self):
        return self.sidewalk - self.deck_depth + self.post_line_inset

    @property
    def post_line_x(self):
        return self.church_length + self.deck_depth - self.post_line_inset

    @property
    def table_x(self):
        return self.church_post_xs[2] + 1.0

    # Tabs are asymmetric along each edge, so a panel only goes in one way round.
    @property
    def church_tab_xs(self):
        return (36.0, 125.0)

    @property
    def main_tab_xs(self):
        return (5.25, self.main_panel - 7.0)

    @property
    def corner_tab_ys(self):
        return (20.0, 70.0)

    @property
    def base_key_ys(self):
        return (self.sidewalk + 20.0, self.sidewalk + 65.0)

    @property
    def main_deck_tab_ys(self):
        return (self.sidewalk + 0.3 * self.main_width, self.sidewalk + 0.7 * self.main_width)

    # --- storefront ----------------------------------------------------------
    @property
    def store_w(self):
        return self.main_panel - 2 * self.pier_width + 4.0   # 2 mm behind each pier

    @property
    def store_h(self):
        return self.storefront_top + 2.0

    @property
    def store_y(self):
        return self.sidewalk - self.main_pier_proud + self.main_panel / 2

    @property
    def store_door_top(self):
        return ft(8)

    @property
    def store_tab_dx(self):
        return 0.4 * self.store_w

    @property
    def storefront_x(self):
        """World x of the storefront's back face; its front touches the wall's back."""
        return self.church_length - self.wall_thickness - self.storefront_t

    @property
    def door_panel_x(self):
        return self.storefront_x - self.entry_inset - self.storefront_t

    @property
    def door_panel_w(self):
        return self.entry_width + 10.0

    @property
    def door_tab_dx(self):
        return 9.0

    @property
    def entry_y(self):
        return self.sidewalk - self.main_pier_proud + self.main_panel * self.entry_center

    @property
    def entry_center_local(self):
        return (self.entry_y - (self.store_y - self.store_w / 2)) / self.store_w

    @property
    def cheek_dy(self):
        d = self.entry_width / 2 + 1.6
        return (-d, d)

    @property
    def cheek_ys(self):
        return tuple(self.entry_y + d for d in self.cheek_dy)

    @property
    def cheek_h(self):
        return self.store_door_top - 1.0

    @property
    def cheek_tab_y(self):
        return 0.55 * self.cheek_h

    # --- balcony details -----------------------------------------------------
    @property
    def outrigger_x(self):
        return self.deck_depth - self.post_line_inset - self.outrigger_stand_off

    @property
    def rail_return_len(self):
        return self.deck_depth - self.post_line_inset - self.post_t / 2 - 1.0

    @property
    def rail_return_local(self):
        """Its slot in deck_main's frame (x north, y toward the wall)."""
        return (self.main_post_ys[-1] - self.sidewalk + self.deck_depth,
                self.deck_depth - 0.6 - self.rail_return_len / 2)

    @property
    def sign_local(self):
        a, b = self.main_post_ys[:2]
        return ((a + b) / 2 - self.sidewalk + self.deck_depth, 0.35 * self.deck_depth)

    @property
    def chair_dx(self):
        return (-8.0, 8.0)

    @property
    def kit_xy_features(self):
        return {"rail_picket": self.rail_picket, "rail_bar": self.rail_bar,
                "post_w": self.post_w, "trim_w": self.trim_w}


DEFAULT = CornerParams()


# ---------------------------------------------------------------------------
class Face:
    """Collects relief on a flat panel's front face (z = t), so it can all be
    fused and cut in one go: one boolean per feature is very slow on a wall."""

    def __init__(self, p, t):
        self.p, self.t = p, t
        self.adds, self.cuts, self.late, self.paints = [], [], [], []
        self.z_paint = t - p.zq(p.color_depth)

    def raised(self, x0, x1, y0, y1, h=None, color=None):
        h = self.p.zq(self.p.relief if h is None else h)
        self.adds.append(box(x0, x1, y0, y1, self.t - EPS, self.t + h))
        if color:
            self.paint(color, x0, x1, y0, y1)

    def paint(self, color, x0, x1, y0, y1):
        self.paints.append((color, box(x0, x1, y0, y1, self.z_paint, self.t + 10)))

    def pocket(self, x0, x1, y0, y1, depth, color=None):
        d = self.p.zq(depth)
        self.cuts.append(box(x0, x1, y0, y1, self.t - d, self.t + 10))
        if color:
            self.floor(color, x0, x1, y0, y1, depth)

    def floor(self, color, x0, x1, y0, y1, depth):
        """Color the floor of a pocket that's `depth` deep."""
        d = self.p.zq(depth)
        self.paints.append((color, box(x0, x1, y0, y1, self.t - d - self.p.zq(self.p.color_depth),
                                       self.t - d + EPS)))

    def hole(self, x0, x1, y0, y1):
        self.cuts.append(box(x0, x1, y0, y1, -EPS, self.t + 10))

    def window(self, x0, x1, y0, y1, bar_at=None):
        """Open window: raised stone frame, sill, optional full-depth bar."""
        p, f = self.p, self.p.trim_w
        self.raised(x0 - f, x1 + f, y0 - f, y1 + f, color=p.color_trim)
        self.hole(x0, x1, y0, y1)
        if bar_at is not None:
            b = p.transom_bar / 2
            self.late.append(box(x0 - EPS, x1 + EPS, bar_at - b, bar_at + b, 0, self.t))
            self.paints.append((p.color_trim, box(x0, x1, bar_at - b, bar_at + b, -EPS, self.t + 10)))

    def door(self, x0, x1, y0, y1, transom=0.0, screen=True):
        """Recessed rust door in a stone frame, with a pale screen door and a transom."""
        p, f = self.p, self.p.trim_w
        top = y1 + transom
        self.raised(x0 - f, x1 + f, y0, top + f, color=p.color_trim)
        self.pocket(x0, x1, y0, y1, p.door_recess, color=p.color_door)
        if screen:
            m = 1.6
            self.pocket(x0 + m, x1 - m, y0 + 4.0, y1 - m, p.door_recess + 0.2, color=p.color_trim)
        if transom:
            self.hole(x0, x1, y1 + f, top)

    def finish(self, body):
        if self.adds:
            body = body.fuse(*self.adds)
        if self.cuts:
            body = body.cut(*self.cuts)
        if self.late:
            body = body.fuse(*self.late)
        return body


def stand(p, cx, cy, z0, run, t):
    """Pose for a flat part standing on z0 with local x along `run` and y up, and
    its thickness centered on (cx, cy). Its front (local z=t) is `run` turned -90
    degrees, so X faces -Y and Y faces +X, the two street faces."""
    rx, ry = run
    zd = (ry, -rx, 0)
    origin = (cx - zd[0] * t / 2, cy - zd[1] * t / 2, z0)
    return Location(Plane(origin, (rx, ry, 0), zd))


# ---------------------------------------------------------------------------
# Main panels (split tabs)
# ---------------------------------------------------------------------------
def _sock(cx, cy, sx, sy, z0, z1, p, mouth="top"):
    return socket(cx, cy, sx, sy, z0, z1, p, mouth=mouth, rib_height=0)[0]


def wall_church(p) -> Piece:
    """Church St wall. Local: x east along the wall, y up, z out of the front."""
    Lc, H, tw, pav = p.church_panel, p.roof_z, p.wall_thickness, p.pavilion
    dz, dt, ev = p.deck_z, p.deck_top, p.eave_z
    body = box(0, Lc, 0, H, 0, tw) + box(Lc - p.pier_width, Lc, H - EPS, p.pier_z, 0, tw)
    f = Face(p, tw)
    c = p.bay_centers

    # --- solid west end ------------------------------------------------------
    f.raised(0, 4, 0, dz - 1, color=None)
    f.raised(pav - 4, pav, 0, dz - 1)
    f.raised(0, pav, dz - 1, dz + 4)
    f.door(9, 19.5, 0, ft(7), screen=False)
    f.window(20.5, 32, 3.5, ft(7) - 0.5)
    f.window(pav / 2 - 5.5, pav / 2 + 5.5, dz + 8, dz + 26, bar_at=dz + 17)
    f.raised(0, 4, dz + 4, ev)
    f.raised(pav - 4, pav, dz + 4, ev)
    f.raised(0, pav, ev, ev + 1.6)

    # --- ground floor, one bay each ------------------------------------------
    f.window(c[0] - 18, c[0] - 5, 3.5, 17.5, bar_at=10.5)          # shuttered window
    f.door(c[0] + 2, c[0] + 19.5, 0, ft(7), transom=0.0, screen=False)  # the double doors
    f.late.append(box(c[0] + 10.35, c[0] + 11.15, 0, ft(7), tw - p.zq(p.door_recess) - EPS, tw))
    f.paint(p.color_trim, c[0] + 10.35, c[0] + 11.15, 0, ft(7))
    f.raised(c[0] + 1, c[0] + 20.5, ft(7) + 1, ft(9), color=p.color_trim)  # hall sign
    f.window(c[1] - 9, c[1] + 9, 22.75, 32.75)                     # small high window
    f.window(c[2] - 12, c[2] + 12, 10.5, 32.5)                     # gift shop display

    # --- upper floor ---------------------------------------------------------
    f.door(c[0] - 12, c[0] - 2.5, dt + 0.2, dt + ft(7), transom=5.0)
    f.window(c[0] + 6, c[0] + 16, dt + 10, dt + 23, bar_at=dt + 16.5)
    f.door(c[1] - 5, c[1] + 4.5, dt + 0.2, dt + ft(7), transom=5.0)
    f.door(c[2] - 5, c[2] + 4.5, dt + 0.2, dt + ft(7), transom=5.0)

    # Board and batten behind the balcony and on the west end's upper floor.
    x = 6.5
    while x < Lc - 1:
        if not pav - 5 < x < pav + 1:
            y0 = dz + 4 if x < pav else dt
            f.raised(x - 0.4, x + 0.4, y0, ev, h=p.batten_raise)
        x += p.batten_pitch
    # Standing-seam mansard, and the rust coping along the top.
    x = 3.5
    while x < Lc - p.pier_width:
        f.raised(x - 0.4, x + 0.4, ev + 1.6, H - 1.4, h=p.batten_raise)
        x += p.seam_pitch
    f.raised(0, Lc - p.pier_width + EPS, H - 1.4, H, color=p.color_door)
    f.raised(Lc - p.pier_width, Lc, ev + 1.6, p.pier_z - 1.4)
    f.raised(Lc - p.pier_width, Lc, p.pier_z - 1.4, p.pier_z, color=p.color_door)

    # --- pockets on the front face for the balcony and overhang --------------
    d, cl = p.zq(p.deck_tab_pocket), p.prop_clearance
    for x in c:
        f.cuts.append(box(x - 4 - cl, x + 4 + cl, dz - cl, dt + cl, tw - d, tw + 10))
        f.cuts.append(box(x - 4 - cl, x + 4 + cl, ev - cl, ev + p.overhang_t + cl, tw - d, tw + 10))

    # --- panel joints --------------------------------------------------------
    adds, cuts = [], []
    for x in p.church_tab_xs:
        t, s = split_tab(x, 0, p, p.base_tab_len, p.base_tab_barb_at, tw)
        adds.append(t)
        cuts.append(s)
    for y in p.corner_tab_ys:
        t, s = split_tab(Lc, y, p, p.corner_tab_len, p.corner_tab_barb_at, tw, direction="+x")
        adds.append(t)
        cuts.append(s)
    # Blind pockets in the back (mouth on the bed) for the west return.
    cs = p.split_clearance
    for y in p.corner_tab_ys:
        cuts.append(_sock(p.return_inset + tw / 2, y, tw + 2 * cs, p.split_width + 2 * cs,
                          0, p.zq(p.corner_tab_len + 0.2), p, mouth="bottom"))
    body = f.finish(body).fuse(*adds).cut(*cuts)
    return Piece(body, [], [(0.45 * Lc, 0, "-y"), (0.60 * Lc, 0, "-y"), (0.08 * Lc, 0, "-y")],
                 color=p.color_wall, paints=f.paints)


def wall_main(p) -> Piece:
    """Main St wall. Local: x north along the wall, y up, z out of the front."""
    W, tw, pw = p.main_panel, p.wall_thickness, p.pier_width
    dz, dt = p.deck_z, p.deck_top
    top = p.main_parapet_z
    body = box(0, W, 0, top, 0, tw) + box(0, pw, top - EPS, p.pier_z, 0, tw) \
        + box(W - pw, W, top - EPS, p.pier_z, 0, tw)
    f = Face(p, tw)

    # Piers top and bottom; left off behind the deck so it can sit against the wall.
    for x0, x1 in ((0, pw), (W - pw, W)):
        f.raised(x0, x1, 0, dz - 0.2)
        f.raised(x0, x1, dt + 0.2, p.pier_z)
        f.raised(x0, x1, p.pier_z - 1.6, p.pier_z, h=0.6, color=p.color_door)
    # Cream panel with two tall windows, in a sage surround.
    ux0, ux1 = pw + 4, W - pw - 4
    uy0, uy1 = dt + 4, 84.0
    f.pocket(ux0, ux1, uy0, uy1, 0.4, color=p.color_trim)
    win_w, win_h = 11.0, 23.0
    for cx in (W * 0.35, W * 0.65):
        f.window(cx - win_w / 2, cx + win_w / 2, dt + 7.5, dt + 7.5 + win_h, bar_at=dt + 7.5 + win_h / 2)
    # Stripe under the cornice, and the coping.
    f.pocket(pw, W - pw, 88.5, 90.5, 0.2, color=p.color_trim)
    f.raised(pw - EPS, W - pw + EPS, top - 1.2, top, color=p.color_door)

    # Storefront opening: a big notch in the bottom edge.
    f.cuts.append(box(pw, W - pw, -1, p.storefront_top, -EPS, tw + 10))

    d, cl = p.zq(p.deck_tab_pocket), p.prop_clearance
    for y in p.main_deck_tab_ys:
        x = y - p.sidewalk + p.main_pier_proud
        f.cuts.append(box(x - 4 - cl, x + 4 + cl, dz - cl, dt + cl, tw - d, tw + 10))
    for x in (W * 0.3, W * 0.7):
        f.cuts.append(box(x - 3 - cl, x + 3 + cl, 91.5 - cl, 91.5 + p.sheet_t + cl, tw - d, tw + 10))

    adds, cuts = [], []
    for x in p.main_tab_xs:
        t, s = split_tab(x, 0, p, p.base_tab_len, p.base_tab_barb_at, tw)
        adds.append(t)
        cuts.append(s)
    # Blind pockets in the back for the Church St wall's end tabs.
    cs = p.split_clearance
    for y in p.corner_tab_ys:
        cuts.append(_sock(p.main_pier_proud + tw / 2, y, tw + 2 * cs, p.split_width + 2 * cs,
                          0, p.zq(p.corner_tab_len + 0.2), p, mouth="bottom"))
    body = f.finish(body).fuse(*adds).cut(*cuts)
    return Piece(body, [], [(8.8, 0, "-y"), (W - 2.0, 0, "-y")], color=p.color_wall, paints=f.paints)


def wall_west(p) -> Piece:
    """West return. Local x runs toward the Church St wall; the slit skin faces out."""
    D, H, tw = p.west_return, p.roof_z, p.wall_thickness
    body = box(0, D, 0, H, 0, tw)
    adds, cuts = [], []
    t, s = split_tab(D / 2, 0, p, p.base_tab_len, p.base_tab_barb_at, tw)
    adds.append(t)
    cuts.append(s)
    for y in p.corner_tab_ys:
        t, s = split_tab(D, y, p, p.corner_tab_len, p.corner_tab_barb_at, tw, direction="+x")
        adds.append(t)
        cuts.append(s)
    body = body.fuse(*adds).cut(*cuts)
    return Piece(body, [], [(0.15 * D, 0, "-y"), (0.85 * D, 0, "-y")], color=p.color_wall)


def _base_slab(p, x0, x1, y0, y1, corner=False):
    """Slab with the curb step, from its plan outline."""
    tb, st = p.base_thickness, p.street_strip
    curb = p.zq(p.curb_height)
    if not corner:
        body = box(x0, x1, y0, y1, 0, tb)
        body -= box(x0 - 1, x1 + 1, y0 - 1, st, tb - curb, tb + EPS)
        return body
    # Rounded street corner: outer radius on the slab, inner on the walk.
    R = 14.0
    rc = R - st
    cx, cy = x1 - R, y0 + R
    plan = Pos((x0 + x1) / 2, (cy + y1) / 2) * Rectangle(x1 - x0, y1 - cy)
    plan += Pos((x0 + cx) / 2, (y0 + cy) / 2) * Rectangle(cx - x0, cy - y0)
    plan += Pos(cx, cy) * Circle(R)
    body = extrude(plan, tb, dir=UP)
    walk = Pos((x0 + x1 - st) / 2, (cy + y1) / 2) * Rectangle(x1 - st - x0, y1 - cy)
    walk += Pos((x0 + cx) / 2, (y0 + st + cy) / 2) * Rectangle(cx - x0, cy - y0 - st)
    walk += Pos(cx, cy) * Circle(rc)
    slab_top = box(x0 - 1, x1 + 1, y0 - 1, y1 + 1, tb - curb, tb + 1) - Pos(0, 0, tb - curb - 1) * extrude(walk, curb + 2, dir=UP)
    return body - slab_top


def _sidewalk_joints(p, x0, x1, y1, step, cuts):
    jd, jw = p.zq(p.joint_depth), p.joint_width
    tb = p.base_thickness
    y0 = p.street_strip + 0.8
    x = x0 + step
    while x < x1 - 1:
        cuts.append(box(x - jw / 2, x + jw / 2, y0, y1, tb - jd, tb + EPS))
        x += step


def base_a(p) -> Piece:
    """The main slab: Church St sidewalk and the building's floor ring."""
    W, D, tb, tw, S = p.base_a_x, p.base_y, p.base_thickness, p.wall_thickness, p.sidewalk
    Lx = p.church_length
    cs, cl = p.split_clearance, p.prop_clearance
    body = _base_slab(p, 0, W, 0, D)
    cuts = []
    _sidewalk_joints(p, 0, W, S - 0.6, p.joint_spacing, cuts)
    yj = p.street_strip + p.joint_spacing
    cuts.append(box(0.5, W - 0.5, yj - p.joint_width / 2, yj + p.joint_width / 2,
                    tb - p.zq(p.joint_depth), tb + EPS))
    # Open up the floor: nothing inside shows.
    cuts.append(box(10, Lx - 26, S + 10, D - 8, -EPS, tb + EPS))

    # --- split tab sockets ---------------------------------------------------
    for x in p.church_tab_xs:
        cuts.append(_sock(x, S + tw / 2, p.split_width + 2 * cs, tw + 2 * cs, 0, tb, p))
    for x in p.main_tab_xs:
        y = S - p.main_pier_proud + x
        cuts.append(_sock(Lx - tw / 2, y, tw + 2 * cs, p.split_width + 2 * cs, 0, tb, p))
    xr = p.return_inset + tw / 2
    cuts.append(_sock(xr, S + tw + p.west_return / 2, tw + 2 * cs, p.split_width + 2 * cs, 0, tb, p))

    # --- feature pockets: plain friction, blind ------------------------------
    def pocket(cx, cy, sx, sy, length):
        return _sock(cx, cy, sx + 2 * cl, sy + 2 * cl, tb - p.zq(length + 0.2), tb, p)

    for x in p.church_post_xs:
        cuts.append(pocket(x, p.post_line_y, p.post_w, p.post_t, p.post_tab_len))
    xs, xd, ycs, cheeks = p.storefront_x, p.door_panel_x, p.store_y, p.cheek_ys
    for dy in (-p.store_tab_dx, p.store_tab_dx):
        cuts.append(pocket(xs + p.storefront_t / 2, ycs + dy, p.storefront_t, 4.0, p.post_tab_len))
    for dy in (-p.door_tab_dx, p.door_tab_dx):
        cuts.append(pocket(xd + p.storefront_t / 2, p.entry_y + dy, p.storefront_t, 3.0, p.post_tab_len))
    for y in cheeks:
        cuts.append(pocket(xd + p.storefront_t + p.entry_inset / 2, y, 3.0, p.sheet_t, p.post_tab_len))

    # --- key into base B -----------------------------------------------------
    adds = []
    for y in p.base_key_ys:
        t, s = split_tab(W, y, p, p.base_key_len, 1.5, p.base_key_t, direction="+x")
        adds.append(t)
        cuts.append(s)
    body = body.fuse(*adds).cut(*cuts)
    return Piece(body, [], [(0.3 * W, D, "+y"), (0.7 * W, D, "+y")], color=p.color_base)


def base_b(p) -> Piece:
    """Main St sidewalk with the rounded corner. Base A's keys slide into it from
    the side, under its top skin, so the seam reads as one more sidewalk joint."""
    x0, x1, D, tb = p.base_a_x, p.base_x, p.base_y, p.base_thickness
    cs, cl = p.split_clearance, p.prop_clearance
    body = _base_slab(p, x0, x1, 0, D, corner=True)
    cuts = []
    # Key pockets open onto the bed and the side. A 45 degree roof keeps the flat
    # part under max_bridge, and leaves a skin on the sidewalk.
    s, h = p.split_width / 2 + cs, p.zq(p.base_key_t + 0.2)
    rise = bridge_roof(2 * s, 99, p)
    section = Polygon((-s, -EPS), (s, -EPS), (s, h), (s - rise, h + rise), (rise - s, h + rise), (-s, h), align=None)
    pocket = extrude(section, p.base_key_len + cs + EPS, dir=UP)
    for y in p.base_key_ys:
        # Local z of the extrusion runs along world +x, local x along world +y.
        cuts.append(Location(Plane((x0 - EPS, y, 0), Y, X)) * pocket)
    jd, jw = p.zq(p.joint_depth), p.joint_width
    y = p.sidewalk + p.joint_spacing
    while y < D - 1:
        cuts.append(box(x0 + 0.5, x1 - p.street_strip - 0.8, y - jw / 2, y + jw / 2, tb - jd, tb + EPS))
        y += p.joint_spacing
    for y in p.main_post_ys:
        cuts.append(_sock(p.post_line_x, y, p.post_t + 2 * cl, p.post_w + 2 * cl,
                          tb - p.zq(p.post_tab_len + 0.2), tb, p))
    body = body.cut(*cuts)
    # Modeled in world coordinates; sprue.layout() works from the bounding box.
    return Piece(body, [], [(x0 + 0.5 * (x1 - x0), D, "+y")], color=p.color_base)


# ---------------------------------------------------------------------------
# Storefront: the inset entry (features, cross-fit)
# ---------------------------------------------------------------------------
def storefront(p) -> Piece:
    """Sits behind the Main St wall's opening. Local x north, front up."""
    W, H, t = p.store_w, p.store_h, p.storefront_t
    e0, e1 = W * p.entry_center_local - p.entry_width / 2, W * p.entry_center_local + p.entry_width / 2
    body = box(0, W, 0, H, 0, t)
    cuts, adds, paints = [], [], []
    # Inset entry: a full-height opening.
    cuts.append(box(e0, e1, -1, p.store_door_top, -EPS, t + EPS))
    # Display windows on either side, above a stone bulkhead.
    sill, head = ft(2), ft(8)
    margin = 3.0
    for x0, x1 in ((margin, e0 - 3.4), (e1 + 3.4, W - margin)):
        cuts.append(box(x0, x1, sill, head, -EPS, t + EPS))
        m = (x0 + x1) / 2
        adds.append(box(m - 0.4, m + 0.4, sill - EPS, head + EPS, 0, t))
    # Clerestory lights above the rust band.
    band = ft(9)
    n = 5
    w = (W - 2 * margin - (n - 1)) / n
    for i in range(n):
        x = margin + i * (w + 1)
        cuts.append(box(x, x + w, band, H - 1.2, -EPS, t + EPS))
    paints.append((p.color_trim, box(-1, W + 1, -1, sill, -1, t + 10)))
    # Slots for the cheeks' front tabs.
    cl = p.prop_clearance
    for dy in p.cheek_dy:
        x = W * p.entry_center_local + dy
        cuts.append(box(x - p.sheet_t / 2 - cl, x + p.sheet_t / 2 + cl,
                        p.cheek_tab_y - 4 - cl, p.cheek_tab_y + 4 + cl, -EPS, t + EPS))
    for dx in (-p.store_tab_dx, p.store_tab_dx):
        adds.append(tab(W / 2 + dx, 0, 4.0, p.post_tab_len, t, p.lead_in))
    body = body.fuse(*adds).cut(*cuts)
    return Piece(body, [], [(1.2, 0, "-y"), (W - 1.2, 0, "-y")], color=p.color_door, paints=paints)


def door_panel(p) -> Piece:
    """The real shop door, set back behind the storefront by entry_inset."""
    W, H, t = p.door_panel_w, p.store_door_top + 1.0, p.storefront_t
    body = box(0, W, 0, H, 0, t)
    cuts, adds = [], []
    dw = ft(3)
    x0, x1 = W / 2 - dw / 2, W / 2 + dw / 2
    cuts.append(box(x0, x1, ft(1.2), ft(6.6), -EPS, t + EPS))   # glazed door
    cuts.append(box(x0, x1, ft(7), H - 0.8, -EPS, t + EPS))     # transom
    cl = p.prop_clearance
    for dy in p.cheek_dy:
        x = W / 2 + dy
        cuts.append(box(x - p.sheet_t / 2 - cl, x + p.sheet_t / 2 + cl,
                        p.cheek_tab_y - 4 - cl, p.cheek_tab_y + 4 + cl, -EPS, t + EPS))
    for dx in (-p.door_tab_dx, p.door_tab_dx):
        adds.append(tab(W / 2 + dx, 0, 3.0, p.post_tab_len, t, p.lead_in))
    body = body.fuse(*adds).cut(*cuts)
    return Piece(body, [], [(1.0, 0, "-y"), (W - 1.0, 0, "-y")], color=p.color_door,
                 paints=[(p.color_trim, box(x0, x1, 2.0, ft(1.2), -1, t + 10))])


def entry_cheek(p) -> Piece:
    """Side of the inset entry: a little display return. Tabs through the storefront
    (+x) and door panel (-x), and into the floor."""
    L, H, t = p.entry_inset, p.cheek_h, p.sheet_t
    body = box(0, L, 0, H, 0, t)
    body -= box(2.0, L - 2.0, ft(2), H - 2.0, -EPS, t + EPS)
    y = p.cheek_tab_y
    adds = [tab(L, y, 8.0, p.storefront_t - 0.2, t, p.lead_in, "+x"),
            tab(0, y, 8.0, p.storefront_t - 0.2, t, p.lead_in, "-x"),
            tab(L / 2, 0, 3.0, p.post_tab_len, t, p.lead_in)]
    body = body.fuse(*adds)
    return Piece(body, [], [(1.0, 0, "-y"), (L - 1.0, 0, "-y")], color=p.color_door,
                 paints=[(p.color_trim, box(-5, L + 5, -5, ft(2), -1, t + 10))])


# ---------------------------------------------------------------------------
# Balcony and overhang
# ---------------------------------------------------------------------------
def _post_holes(p, x, y, t):
    """Through-holes for one post station in a deck plate: the two lower-post
    tabs and the upper post in the middle. Local x runs along the balcony."""
    cl = p.prop_clearance
    hy = p.post_t / 2 + cl
    out = [box(x - p.post_w / 2 - cl, x + p.post_w / 2 + cl, y - hy, y + hy, -EPS, t + EPS)]
    for dx in (-p.head_tab_x, p.head_tab_x):
        out.append(box(x + dx - p.head_tab_w / 2 - cl, x + dx + p.head_tab_w / 2 + cl,
                       y - hy, y + hy, -EPS, t + EPS))
    return out


def _rail_slot(p, x, y, t, run=(1, 0)):
    cl = p.prop_clearance
    a = p.rail_tab_w / 2 + cl
    b = p.sheet_t / 2 + cl
    return Pos(x, y, 0) * Rot(0, 0, math.degrees(math.atan2(run[1], run[0]))) * box(-a, a, -b, b, -EPS, t + EPS)


def deck_church(p) -> Piece:
    """Church St balcony floor. Local: x east, y toward the wall, z up.

    Goes on after the posts: hook the back tabs into the wall with the front
    raised, then lower it over the post tabs.
    """
    x0, Lx, D, t = p.pavilion, p.church_length, p.deck_depth, p.deck_t
    L = Lx - x0
    body = box(0, L, 0, D, 0, t)
    adds, cuts = [], []
    for x in p.bay_centers:
        adds.append(tab(x - x0, D, 8.0, p.zq(p.deck_tab_pocket) - 0.2, t, p.lead_in, "+y"))
    # Clear the Main St pier, which sticks out past the Church St wall.
    cl = p.prop_clearance
    cuts.append(box(p.church_panel - x0 - cl, L + 1, D - p.main_pier_proud - cl, D + 1, -EPS, t + EPS))
    # Tab into the rounded corner piece.
    adds.append(tab(L, D / 2, 6.0, 3.0, t, p.lead_in, "+x"))
    yl = p.post_line_inset
    for x in p.church_post_xs:
        cuts += _post_holes(p, x - x0, yl, t)
    xs = p.church_post_xs
    for a, b in zip(xs, xs[1:]):
        m = (a + b) / 2 - x0
        q = (b - a) / 4
        cuts += [_rail_slot(p, m - q, yl, t), _rail_slot(p, m + q, yl, t)]
    # Bistro set.
    tx = p.table_x - x0
    ty = D * 0.45
    cuts += _furniture_holes(p, tx, ty, t)
    body = body.fuse(*adds).cut(*cuts)
    return Piece(body, [], [(0.25 * L, D, "+y"), (0.75 * L, D, "+y")], color=p.color_door)


def _furniture_holes(p, tx, ty, t):
    cl = p.prop_clearance
    ff = p.furniture_t
    out = []
    # Table: piece A's two feet straddle the crossing.
    for dx in (-2.2, 2.2):
        out.append(box(tx + dx - 0.45 - cl, tx + dx + 0.45 + cl, ty - ff / 2 - cl, ty + ff / 2 + cl, -EPS, t + EPS))
    # Chairs: one locating leg each, facing the table along x.
    for dx in p.chair_dx:
        leg = tx + dx + (2.1 if dx < 0 else -2.1)
        out.append(box(leg - 0.4 - cl, leg + 0.4 + cl, ty - ff / 2 - cl, ty + ff / 2 + cl, -EPS, t + EPS))
    return out


def deck_main(p) -> Piece:
    """Main St balcony floor and the rounded corner. Local: x north (x=D is the
    Church St wall's face line), y toward the wall, z up."""
    D, t = p.deck_depth, p.deck_t
    Ly = p.main_post_ys[-1] + 2.0 - p.sidewalk      # stops just past the last post
    plan = Pos(D + Ly / 2, D / 2) * Rectangle(Ly, D)
    plan += Pos(D, D) * Circle(D)
    body = extrude(plan, t, dir=UP) - box(-1, D + Ly + 1, D, 2 * D + 1, -EPS, t + EPS)
    adds, cuts = [], []
    for y in p.main_deck_tab_ys:
        adds.append(tab(y - p.sidewalk + D, D, 8.0, p.zq(p.deck_tab_pocket) - 0.2, t, p.lead_in, "+y"))
    # Pocket for deck_church's end tab.
    cl = p.prop_clearance
    cuts.append(box(D / 2 - 3 - cl, D / 2 + 3 + cl, D - 3 - cl, D + EPS, -EPS, t + EPS))
    yl = p.post_line_inset
    ys = p.main_post_ys
    for y in ys:
        cuts += _post_holes(p, y - p.sidewalk + D, yl, t)
    for a, b in zip(ys, ys[1:]):
        m = (a + b) / 2 - p.sidewalk + D
        q = (b - a) / 4
        cuts += [_rail_slot(p, m - q, yl, t), _rail_slot(p, m + q, yl, t)]
    # Return rail at the north end, running back to the wall.
    rx, ry = p.rail_return_local
    cuts.append(_rail_slot(p, rx, ry, t, run=(0, 1)))
    # Rail facets around the corner.
    for x, y, run in _facets_local(p):
        cuts.append(_rail_slot(p, x, y, t, run=run))
    # Hanging sign.
    sx, sy = p.sign_local
    cuts.append(box(sx - p.rail_tab_w / 2 - cl, sx + p.rail_tab_w / 2 + cl,
                    sy - p.sheet_t / 2 - cl, sy + p.sheet_t / 2 + cl, -EPS, t + EPS))
    body = body.fuse(*adds).cut(*cuts)
    return Piece(body, [], [(D + 0.2 * Ly, D, "+y"), (D + 0.85 * Ly, D, "+y")], color=p.color_door)


def _facets_local(p):
    """(x, y, run direction) of the three corner rail facets in deck_main's frame."""
    D = p.deck_depth
    r = D - p.post_line_inset
    out = []
    for deg in (15, 45, 75):
        th = math.radians(deg)
        rc = r * math.cos(math.radians(15))
        out.append((D - rc * math.sin(th), D - rc * math.cos(th), (-math.cos(th), math.sin(th))))
    return out


def overhang(p) -> Piece:
    """Roof over the Church St balcony. Local: x east, y toward the wall, z up."""
    x0, x1, D, t = p.pavilion + 1.0, p.church_panel + 2.5, p.overhang_depth, p.overhang_t
    L = x1 - x0
    body = box(0, L, 0, D, 0, t)
    adds, cuts = [], []
    for x in p.bay_centers:
        adds.append(tab(x - x0, D, 8.0, p.zq(p.deck_tab_pocket) - 0.2, t, p.lead_in, "+y"))
    cl = p.prop_clearance
    cuts.append(box(p.church_panel - x0 - cl, L + 1, D - p.main_pier_proud - cl, D + 1, -EPS, t + EPS))
    yl = D - p.deck_depth + p.post_line_inset
    for x in p.church_post_xs:
        hy = p.post_t / 2 + cl
        cuts.append(box(x - x0 - p.post_w / 2 - cl, x - x0 + p.post_w / 2 + cl, yl - hy, yl + hy, -EPS, t + EPS))
    body = body.fuse(*adds).cut(*cuts)
    return Piece(body, [], [(0.25 * L, D, "+y"), (0.75 * L, D, "+y")], color=p.color_door)


def _spandrel_cuts(half, h, top, t):
    """Openings in those brackets, leaving ~0.8 mm of iron all round."""
    y0 = top - h
    out = []
    for s in (-1, 1):
        a = (s * 1.7, y0 + 2.9)
        b = (s * (half - 2.2), top - 0.8)
        c = (s * 1.7, top - 0.8)
        if abs(b[0]) > abs(a[0]) + 0.6 and top - 0.8 > a[1] + 0.6:
            out.append(extrude(Polygon(a, b, c, align=None), t + 2 * EPS, dir=UP))
    return [Pos(0, 0, -EPS) * o for o in out]


def _head(half, h, top, t):
    """Stem top with brackets, as one solid t thick."""
    y0 = top - h
    solids = []
    for s in (-1, 1):
        poly = Polygon((s * 0.9, y0), (s * half, top), (s * 0.9, top), align=None)
        solids.append(extrude(poly, t, dir=UP))
    return solids


def post_lower(p) -> Piece:
    """Sidewalk to balcony. Crosses an outrigger at its head, and carries the deck."""
    H, t, w = p.deck_z, p.post_t, p.post_w
    body = box(-w / 2, w / 2, 0, H, 0, t) + box(-p.post_foot_w / 2, p.post_foot_w / 2, 0, p.post_foot_h, 0, t)
    adds = _head(p.head_half, p.head_h, H, t)
    adds.append(tab(0, 0, w, p.post_tab_len, t, p.lead_in))
    for dx in (-p.head_tab_x, p.head_tab_x):
        adds.append(tab(dx, H, p.head_tab_w, 0.9, t, 0.2, "+y"))
    body = body.fuse(*adds)
    cl = p.prop_clearance
    cuts = _spandrel_cuts(p.head_half, p.head_h, H, t)
    cuts.append(box(-p.sheet_t / 2 - cl, p.sheet_t / 2 + cl, H - p.outrigger_cross, H + EPS, -EPS, t + EPS))
    body = body.cut(*cuts)
    return Piece(body, [], [(0, -p.post_tab_len, "-y")], color=p.color_post)


def post_upper(p) -> Piece:
    """Balcony to overhang (Church St only)."""
    H, t, w = p.upper_height, p.post_t, p.post_w
    body = box(-w / 2, w / 2, 0, H, 0, t) + box(-p.post_foot_w / 2, p.post_foot_w / 2, 0, p.post_foot_h, 0, t)
    half, h = 6.0, 6.5
    adds = _head(half, h, H, t)
    adds.append(tab(0, 0, w, p.deck_t - 0.1, t, 0.3))
    adds.append(tab(0, H, w, p.overhang_t - 0.1, t, 0.3, "+y"))
    body = body.fuse(*adds).cut(*_spandrel_cuts(half, h, H, t))
    return Piece(body, [], [(0, -(p.deck_t - 0.1), "-y")], color=p.color_post)


def outrigger(p) -> Piece:
    """Joist from the wall out to a post, crossing the post's head. Local x runs out
    from the wall, y up. Slot from the bottom; the post's slot comes from the top."""
    L = p.outrigger_x + 1.4
    t, h = p.sheet_t, p.outrigger_h
    cl = p.prop_clearance
    body = box(0, L, 0, h, 0, t)
    body -= box(p.outrigger_x - p.post_t / 2 - cl, p.outrigger_x + p.post_t / 2 + cl,
                -EPS, h - p.outrigger_cross, -EPS, t + EPS)
    return Piece(body, [], [(3.0, 0, "-y"), (L - 5.0, 0, "-y")], color=p.color_post)


def _rail(p, L, tabs, gates) -> Piece:
    """Flat railing: top rail, bottom rail, pickets. Local x centered on L, y up."""
    H, t, b = p.rail_h, p.sheet_t, p.rail_bar
    body = box(-L / 2, L / 2, 0, H, 0, t)
    cuts = []
    pw, pitch = p.rail_picket, p.rail_pitch
    y0, y1 = b, H - p.rail_top_bar
    n = max(1, round((L - 2 * b + pw) / pitch))            # openings that fit
    gap = (L - 2 * b - (n - 1) * pw) / n
    for i in range(n):
        x = -L / 2 + b + i * (gap + pw)
        cuts.append(box(x, x + gap, y0, y1, -EPS, t + EPS))
    adds = [tab(x, 0, p.rail_tab_w, p.deck_t - 0.2, t, p.lead_in) for x in tabs]
    body = body.fuse(*adds).cut(*cuts)
    return Piece(body, [], [(x, 0, "-y") for x in gates], color=p.color_post)


def _span_rail(p, span):
    """A railing panel between two posts that are `span` apart."""
    L = span - p.post_foot_w - 0.3       # the upper posts' feet are the widest part
    q = span / 4
    return _rail(p, L, (-q, q), (-L * 0.42, 0, L * 0.42))


def rail_facet(p) -> Piece:
    r = p.deck_depth - p.post_line_inset
    L = 2 * r * math.sin(math.radians(15)) - 0.5
    return _rail(p, L, (0,), (-L * 0.38, L * 0.38))


def rail_return(p) -> Piece:
    L = p.rail_return_len
    return _rail(p, L, (0,), (-L * 0.38, L * 0.38))


# ---------------------------------------------------------------------------
# Small features
# ---------------------------------------------------------------------------
def cornice(p) -> Piece:
    """Shed cornice on the Main St parapet. Local x along it, y out from the wall."""
    L, D, t = p.main_panel - 2 * p.pier_width - 0.4, ft(1.6), p.sheet_t
    body = box(-L / 2, L / 2, 0, D, 0, t)
    adds = [tab(x, D, 6.0, p.zq(p.deck_tab_pocket) - 0.2, t, p.lead_in, "+y")
            for x in (-0.2 * p.main_panel, 0.2 * p.main_panel)]
    body = body.fuse(*adds)
    return Piece(body, [], [(0, D, "+y")], color=p.color_wall)


def hanging_sign(p) -> Piece:
    """The oval shop sign under the Main St balcony. Local y=0 is the deck's underside."""
    a, b, t = 6.5, 4.5, p.sheet_t
    cy = -1.5 - b
    plan = Pos(0, cy) * Ellipse(a, b)
    body = extrude(plan, t, dir=UP)
    body += box(-0.5, 0.5, -1.5 - 0.5, 0, 0, t)
    body += tab(0, 0, p.rail_tab_w, p.deck_t - 0.2, t, p.lead_in, "+y")
    inner = extrude(Pos(0, cy) * Ellipse(a - 0.8, b - 0.8), t + 1, dir=UP)
    rim = box(-a - 1, a + 1, cy - b - 1, cy + b + 1, -1, t + 1) - inner
    return Piece(body, [], [(0, p.deck_t - 0.2, "+y")], color=p.color_sign, paints=[(p.color_door, rim)])


def table_top(p) -> Piece:
    t, cl = p.furniture_t, p.prop_clearance
    r = 4.6
    body = extrude(Circle(r), t, dir=UP)
    body -= box(-0.8 - cl, 0.8 + cl, -t / 2 - cl, t / 2 + cl, -EPS, t + EPS)
    return Piece(body, [], [(0, -r, "-y")], color=p.color_post)


def table_a(p) -> Piece:
    """Pedestal: feet straddle the crossing, tab up into the top."""
    H, t, cl = p.table_h, p.furniture_t, p.prop_clearance
    body = box(-3, 3, 0, 0.8, 0, t) + box(-1.5, 1.5, 0, H, 0, t)
    adds = [tab(0, H, 1.6, 0.8, t, 0.2, "+y"), tab(-2.2, 0, 0.9, p.deck_t - 0.2, t, 0.2),
            tab(2.2, 0, 0.9, p.deck_t - 0.2, t, 0.2)]
    body = body.fuse(*adds)
    body -= box(-t / 2 - cl, t / 2 + cl, -EPS, H / 2, -EPS, t + EPS)
    return Piece(body, [], [(-2.2, -(p.deck_t - 0.2), "-y")], color=p.color_post)


def table_b(p) -> Piece:
    H, t, cl = p.table_h, p.furniture_t, p.prop_clearance
    body = box(-3, 3, 0, 0.8, 0, t) + box(-1.5, 1.5, 0, H, 0, t)
    body -= box(-t / 2 - cl, t / 2 + cl, H / 2, H + EPS, -EPS, t + EPS)
    return Piece(body, [], [(-2.2, 0, "-y")], color=p.color_post)


def chair_side(p) -> Piece:
    """Local x: -2.5 is the seat's front, +2.5 the back. Crosses chair_back near the rear."""
    t, cl = p.furniture_t, p.prop_clearance
    s = 1.75 - t / 2 - cl
    body = box(-2.5, -1.7, 0, 5.6, 0, t) + box(-2.5, s, 4.4, 5.6, 0, t) + box(s - EPS, 2.5, 5.0, 5.6, 0, t)
    body += box(1.0, 2.5, 5.0, 10.5, 0, t)
    body += tab(-2.1, 0, 0.8, p.deck_t - 0.2, t, 0.2)
    return Piece(body, [], [(-2.1, -(p.deck_t - 0.2), "-y")], color=p.color_post)


def chair_back(p) -> Piece:
    """Back and rear legs, seen from behind. Slot from the top, down to the seat."""
    t, cl = p.furniture_t, p.prop_clearance
    body = box(-2.3, -1.5, 0, 10.5, 0, t) + box(1.5, 2.3, 0, 10.5, 0, t) + box(-2.3, 2.3, 4.4, 5.2, 0, t)
    body += box(-2.3, 2.3, 7.8, 10.5, 0, t)
    body -= box(-t / 2 - cl, t / 2 + cl, 5.0, 10.5 + EPS, -EPS, t + EPS)
    return Piece(body, [], [(-1.9, 0, "-y")], color=p.color_post)


# ---------------------------------------------------------------------------
# Poses
# ---------------------------------------------------------------------------
def _pose_church(p):
    return Location(Plane((0, p.sidewalk + p.wall_thickness, p.base_thickness), X, NEG_Y))


def _pose_main(p):
    return Location(Plane((p.church_length - p.wall_thickness, p.sidewalk - p.main_pier_proud,
                           p.base_thickness), Y, X))


def _pose_west(p):
    x = p.return_inset + p.wall_thickness
    return Location(Plane((x, p.sidewalk + p.wall_thickness + p.west_return, p.base_thickness), NEG_Y, NEG_X))


def _pose_store(p):
    return Location(Plane((p.storefront_x, p.store_y - p.store_w / 2, p.base_thickness), Y, X))


def _pose_door(p):
    return Location(Plane((p.door_panel_x, p.entry_y - p.door_panel_w / 2, p.base_thickness), Y, X))


def _pose_cheek(i):
    def pose(p):
        x = p.door_panel_x + p.storefront_t
        return Location(Plane((x, p.cheek_ys[i] + p.sheet_t / 2, p.base_thickness), X, NEG_Y))
    return pose


def _deck_z(p):
    return p.base_thickness + p.deck_z


def _pose_deck_church(p):
    return Location((p.pavilion, p.sidewalk - p.deck_depth, _deck_z(p)))


def _pose_deck_main(p):
    # local x -> +Y, local y -> -X, z up. x=D is the Church St face line.
    return Location(Plane((p.church_length + p.deck_depth, p.sidewalk - p.deck_depth, _deck_z(p)), Y, Z))


def _pose_overhang(p):
    x0 = p.pavilion + 1.0
    return Location((x0, p.sidewalk - p.overhang_depth, p.base_thickness + p.eave_z))


def _post_pose(kind, i):
    def pose(p):
        z = p.base_thickness + (0 if kind.startswith("l") else p.deck_top)
        if kind.endswith("c"):
            return stand(p, p.church_post_xs[i], p.post_line_y, z, (1, 0), p.post_t)
        return stand(p, p.post_line_x, p.main_post_ys[i], z, (0, 1), p.post_t)
    return pose


def _rig_pose(side, i):
    def pose(p):
        so, t = p.outrigger_stand_off, p.sheet_t
        z = _deck_z(p) - p.outrigger_h
        if side == "c":
            return stand(p, p.church_post_xs[i], p.sidewalk - so, z, (0, -1), t)
        return stand(p, p.church_length + so, p.main_post_ys[i], z, (1, 0), t)
    return pose


def _rail_pose(side, i):
    def pose(p):
        z = _deck_z(p) + p.deck_t
        if side == "c":
            xs = p.church_post_xs
            return stand(p, (xs[i] + xs[i + 1]) / 2, p.post_line_y, z, (1, 0), p.sheet_t)
        ys = p.main_post_ys
        return stand(p, p.post_line_x, (ys[i] + ys[i + 1]) / 2, z, (0, 1), p.sheet_t)
    return pose


def _pose_rail_return(p):
    x = p.church_length + 0.6 + p.rail_return_len / 2
    return stand(p, x, p.main_post_ys[-1], _deck_z(p) + p.deck_t, (1, 0), p.sheet_t)


def _facet_pose(i):
    def pose(p):
        D = p.deck_depth
        x, y, run = _facets_local(p)[i]
        # deck_main local -> world: local x -> +Y, local y -> -X.
        wx = p.church_length + D - y
        wy = p.sidewalk - D + x
        return stand(p, wx, wy, _deck_z(p) + p.deck_t, (-run[1], run[0]), p.sheet_t)
    return pose


def _pose_cornice(p):
    y = p.sidewalk - p.main_pier_proud + p.main_panel / 2
    D = ft(1.6)
    # local x -> +Y, local y (out from wall... toward it) -> -X, z up.
    return Location(Plane((p.church_length + D, y, p.base_thickness + 91.5), Y, Z))


def _pose_sign(p):
    return stand(p, p.church_length + p.deck_depth - p.sign_local[1], p.sidewalk - p.deck_depth + p.sign_local[0],
                 _deck_z(p), (0, 1), p.sheet_t)


def _table_center(p):
    return p.table_x, p.sidewalk - p.deck_depth + p.deck_depth * 0.45


def _pose_table_a(p):
    x, y = _table_center(p)
    return stand(p, x, y, _deck_z(p) + p.deck_t, (1, 0), p.furniture_t)


def _pose_table_b(p):
    x, y = _table_center(p)
    return stand(p, x, y, _deck_z(p) + p.deck_t, (0, 1), p.furniture_t)


def _pose_table_top(p):
    x, y = _table_center(p)
    return Location((x, y, _deck_z(p) + p.deck_t + p.table_h))


def _chair_pose(i, part):
    def pose(p):
        x, y = _table_center(p)
        dx = p.chair_dx[i]
        # Chair faces the table: its local -x (front) points at it.
        run = (-1, 0) if dx < 0 else (1, 0)
        cx = x + dx
        if part == "side":
            return stand(p, cx, y, _deck_z(p) + p.deck_t, run, p.furniture_t)
        return stand(p, cx + run[0] * 1.75, y, _deck_z(p) + p.deck_t, (0, 1), p.furniture_t)
    return pose


def _rail_church(p):
    xs = p.church_post_xs
    return _span_rail(p, xs[1] - xs[0])


def _rail_main(p):
    ys = p.main_post_ys
    return _span_rail(p, ys[1] - ys[0])


_LIST = [
    ("base_a", base_a, lambda p: Location(Plane.XY)),
    ("base_b", base_b, lambda p: Location(Plane.XY)),
    ("wall_church", wall_church, _pose_church),
    ("wall_main", wall_main, _pose_main),
    ("wall_west", wall_west, _pose_west),
    ("storefront", storefront, _pose_store),
    ("door_panel", door_panel, _pose_door),
    ("cheek_s", entry_cheek, _pose_cheek(0)),
    ("cheek_n", entry_cheek, _pose_cheek(1)),
    ("deck_church", deck_church, _pose_deck_church),
    ("deck_main", deck_main, _pose_deck_main),
    ("overhang", overhang, _pose_overhang),
    *[(f"post_c{i}", post_lower, _post_pose("lc", i)) for i in range(4)],
    *[(f"post_m{i}", post_lower, _post_pose("lm", i)) for i in range(4)],
    *[(f"upper_c{i}", post_upper, _post_pose("uc", i)) for i in range(4)],
    *[(f"rig_c{i}", outrigger, _rig_pose("c", i)) for i in range(4)],
    *[(f"rig_m{i}", outrigger, _rig_pose("m", i)) for i in range(4)],
    *[(f"rail_c{i}", _rail_church, _rail_pose("c", i)) for i in range(3)],
    *[(f"rail_m{i}", _rail_main, _rail_pose("m", i)) for i in range(3)],
    ("rail_return", rail_return, _pose_rail_return),
    *[(f"facet{i}", rail_facet, _facet_pose(i)) for i in range(3)],
    ("cornice", cornice, _pose_cornice),
    ("sign", hanging_sign, _pose_sign),
    ("table_top", table_top, _pose_table_top),
    ("table_a", table_a, _pose_table_a),
    ("table_b", table_b, _pose_table_b),
    *[(f"chair{i}_side", chair_side, _chair_pose(i, "side")) for i in range(2)],
    *[(f"chair{i}_back", chair_back, _chair_pose(i, "back")) for i in range(2)],
]

REGISTRY = [Spec(i + 1, name, make, pose) for i, (name, make, pose) in enumerate(_LIST)]
