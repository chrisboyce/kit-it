"""One function per part. Each takes Params and returns a Piece in its local
print frame: the face that sits on the bed is Z=0, relief (if any) points +Z.

World frame (used by the built poses in registry.py):
  X along the facade, Y from the street (y=0) back into the building, Z up,
  base underside at z=0. The facade's front face sits at y = sidewalk_depth.
"""

import os

from build123d import Align, Circle, Pos, Rectangle, Text, extrude

from joints import EPS, UP, Piece, box, socket, tab
from params import Params

FONT = os.environ.get("COLFAX_FONT")  # pinned by flake.nix; None -> build123d default


def label(text, x, y, z, p, size=None):
    """Raised text, centered at (x, y), standing on z."""
    t = Text(text, size or p.label_size, font_path=FONT, align=(Align.CENTER, Align.CENTER))
    return Pos(x, y, z - EPS) * extrude(t, p.zq(p.label_raise) + EPS, dir=UP)


# ---------------------------------------------------------------------------
def base(p: Params) -> Piece:
    """Sidewalk slab with curb, expansion joints and every socket.

    Prints right side up. Each wall gets one *locating* socket that fixes it
    along its length; its other sockets float that way (float_clearance) and
    only grip across the wall's thickness, where the ribs are.
    """
    W, D, tb, tw = p.facade_width, p.base_depth, p.base_thickness, p.wall_thickness
    Ds, c, fc = p.sidewalk_depth, p.clearance, p.float_clearance
    body = box(0, W, 0, D, 0, tb)

    # Curb: the street strip in front is one curb height lower.
    curb = p.zq(p.curb_height)
    body -= box(-EPS, W + EPS, -EPS, p.street_strip, tb - curb, tb + EPS)

    # Expansion joints on the sidewalk (engraved, 2 layers deep).
    jd, jw = p.zq(p.joint_depth), p.joint_width
    y0 = p.street_strip + 0.8   # leave the curb top intact
    n = 1
    while n * p.joint_spacing < W - 1:
        x = n * p.joint_spacing
        body -= box(x - jw / 2, x + jw / 2, y0, Ds - 0.6, tb - jd, tb + EPS)  # stop short of sockets
        n += 1
    yj = p.street_strip + p.joint_spacing
    if yj < Ds - 1:
        body -= box(0.5, W - 0.5, yj - jw / 2, yj + jw / 2, tb - jd, tb + EPS)

    ribs = []
    # Facade sockets: straight through. Ribs press the facade's faces (y walls).
    # The narrow tab locates the facade in x; the wide one floats in x.
    for i, (x, w) in enumerate(zip(p.facade_tab_xs, p.facade_tab_widths)):
        cut, r = socket(x, Ds + tw / 2, w + 2 * (c if i == 0 else fc), tw + 2 * c, 0, tb, p,
                        ribs="y")
        body -= cut
        ribs += r

    # Return sockets: straight through. Ribs press the returns' faces (x walls).
    # The return is located in y by its shoulder on the facade back, so these float in y.
    for x0 in p.return_xs:
        cut, r = socket(x0 + tw / 2, Ds + tw + p.return_depth / 2,
                        tw + 2 * c, p.return_tab_width + 2 * fc, 0, tb, p, ribs="x")
        body -= cut
        ribs += r

    # Prop socket: blind pocket, plain friction fit; prop piece A stands in the XZ plane.
    pt, pc = p.prop_thickness, p.prop_clearance
    cut, _ = socket(p.prop_x, p.prop_y, p.prop_tab_width + 2 * pc, pt + 2 * pc,
                    tb - p.zq(p.prop_tab_len + 0.2), tb, p, rib_height=0)
    body -= cut

    gates = [(0.4 * W, D, "+y"), (0.6 * W, D, "+y")]   # back edge: hidden
    return Piece(body, ribs, gates, color=p.color_base)


# ---------------------------------------------------------------------------
def facade(p: Params) -> Piece:
    """Storefront wall. Local: x along the wall, y up, z out of the front face.

    Back face on the bed, all relief on the front face (prints face up).
    """
    W, H, tw, c = p.facade_width, p.wall_height, p.wall_thickness, p.clearance
    body = box(0, W, 0, H, 0, tw)

    # Keyed bottom tabs (different widths, so it only goes in one way).
    for x, w in zip(p.facade_tab_xs, p.facade_tab_widths):
        body += tab(x, 0, w, p.facade_tab_len, tw, p.lead_in)

    # Color: each face feature also claims color_depth of material beneath it.
    paints = []
    z_paint = tw - p.zq(p.color_depth)
    top = tw + 10

    # Door: recessed into the front face, centered.
    dx0, dx1 = W / 2 - p.door_width / 2, W / 2 + p.door_width / 2
    door_floor = tw - p.zq(p.door_recess)
    body -= box(dx0, dx1, -EPS, p.door_height, door_floor, tw + EPS)
    paints.append((p.color_door, box(dx0, dx1, -EPS, p.door_height,
                                     door_floor - p.zq(p.color_depth), door_floor + EPS)))

    # Display windows: open, with a raised frame and a full-depth transom bar.
    f, fr = p.window_frame, p.zq(p.window_frame_raise)
    for wx0, wx1 in ((p.window_margin, dx0 - p.window_door_gap),
                     (dx1 + p.window_door_gap, W - p.window_margin)):
        y0, y1 = p.window_sill, p.window_top
        frame = box(wx0 - f, wx1 + f, y0 - f, y1 + f, tw - EPS, tw + fr)
        body = body + frame - box(wx0, wx1, y0, y1, -EPS, tw + fr + EPS)
        ty = p.transom_at
        body += box(wx0 - EPS, wx1 + EPS, ty - p.transom_bar / 2, ty + p.transom_bar / 2, 0, tw + fr)
        paints.append((p.color_trim, box(wx0 - f, wx1 + f, y0 - f, y1 + f, z_paint, top)))
        # The transom bar is full depth, so it's trim all the way through.
        paints.append((p.color_trim, box(wx0, wx1, ty - p.transom_bar / 2,
                                         ty + p.transom_bar / 2, -EPS, top)))

    # Sign band.
    body += box(p.sign_inset, W - p.sign_inset, p.sign_bottom, p.sign_top, tw - EPS,
                tw + p.zq(p.sign_raise))
    paints.append((p.color_sign, box(p.sign_inset, W - p.sign_inset, p.sign_bottom,
                                     p.sign_top, z_paint, top)))

    # Two-step cornice at the roofline, and a coping band on the parapet.
    cr, cs, cb = p.zq(p.cornice_raise), p.cornice_step, p.cornice_bottom
    body += box(0, W, cb, cb + 2 * cs, tw - EPS, tw + cr)
    body += box(0, W, cb + cs, cb + 2 * cs, tw - EPS, tw + 2 * cr)
    body += box(0, W, H - p.coping_height, H, tw - EPS, tw + cr)
    paints.append((p.color_trim, box(-EPS, W + EPS, cb, cb + 2 * cs, z_paint, top)))
    paints.append((p.color_trim, box(-EPS, W + EPS, H - p.coping_height, H + EPS, z_paint, top)))

    # Blind pockets in the back face for the returns' front tabs. The pocket
    # mouth is on the bed (z=0); its roof prints as a short bridge. The return
    # stands on the base, so these float in height and only grip its faces.
    ribs = []
    pd = p.zq(p.return_front_tab_len + 0.2)
    for x0 in p.return_xs:
        for ty in p.return_tab_ys:
            cut, r = socket(x0 + tw / 2, ty, tw + 2 * c, p.return_tab_width + 2 * p.float_clearance,
                            0, pd, p, mouth="bottom", ribs="x")
            body -= cut
            ribs += r

    # Gates on the bottom edge (sits on the base, never seen), clear of tabs and door.
    gates = [(0.35 * W, 0, "-y"), (0.65 * W, 0, "-y")]
    return Piece(body, ribs, gates, color=p.color_wall, paints=paints)


# ---------------------------------------------------------------------------
def side_return(p: Params) -> Piece:
    """Short side wall. Local: x = depth back from the facade, y up, z thickness.

    No relief, so the same part works on either side.
    """
    Dr, H, tw = p.return_depth, p.storefront_height, p.wall_thickness
    body = box(0, Dr, 0, H, 0, tw)
    for ty in p.return_tab_ys:
        body += tab(0, ty, p.return_tab_width, p.return_front_tab_len, tw, p.lead_in, "-x")
    body += tab(Dr / 2, 0, p.return_tab_width, p.base_thickness - 0.4, tw, p.lead_in)
    gates = [(0.15 * Dr, 0, "-y"), (0.85 * Dr, 0, "-y")]
    return Piece(body, [], gates, color=p.color_wall)


# ---------------------------------------------------------------------------
def _planter_outline(p: Params):
    """Sidewalk planter with a shrub, as a flat silhouette (x width, y up)."""
    w, H = p.prop_width, p.prop_height
    ph = H / 3
    r1, rt = 0.3 * w, 0.32 * w
    s = Pos(w / 2, ph / 2) * Rectangle(w, ph)
    s += Pos(w * 0.3, ph + r1 * 0.6) * Circle(r1)
    s += Pos(w * 0.7, ph + r1 * 0.6) * Circle(r1)
    s += Pos(w * 0.5, H - rt) * Circle(rt)
    s += Pos(w / 2, (ph + H - rt) / 2) * Rectangle(0.5 * w, H - rt - ph)
    return s


def _planter_paints(p: Params):
    """Shrub above the planter box. The split is in the outline (XY), so every
    layer of the prop has both colors: easy on a toolchanger."""
    w, H = p.prop_width, p.prop_height
    return [(p.color_shrub, box(-1, w + 1, H / 3, H + 1, -1, 10))]


def prop_a(p: Params) -> Piece:
    """Cross-lap prop, piece A: slot from the top, tab into the sidewalk."""
    w, H, t, c = p.prop_width, p.prop_height, p.prop_thickness, p.prop_clearance
    body = extrude(_planter_outline(p), t, dir=UP)
    body -= box(w / 2 - t / 2 - c, w / 2 + t / 2 + c, H / 2, H + EPS, -EPS, t + EPS)
    body += tab(p.prop_tab_x, 0, p.prop_tab_width, p.prop_tab_len, t, p.lead_in)
    return Piece(body, [], [(0.12 * w, 0, "-y")], color=p.color_planter, paints=_planter_paints(p))


def prop_b(p: Params) -> Piece:
    """Cross-lap prop, piece B: slot from the bottom, so it straddles piece A."""
    w, H, t, c = p.prop_width, p.prop_height, p.prop_thickness, p.prop_clearance
    body = extrude(_planter_outline(p), t, dir=UP)
    body -= box(w / 2 - t / 2 - c, w / 2 + t / 2 + c, -EPS, H / 2, -EPS, t + EPS)
    return Piece(body, [], [(0.15 * w, 0, "-y"), (0.85 * w, 0, "-y")],
                 color=p.color_planter, paints=_planter_paints(p))
