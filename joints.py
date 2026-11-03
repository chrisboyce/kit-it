"""Joint geometry shared by the kit parts and the test coupon.

Design rule: every precision feature lives in the XY outline of the part it's on
(where FDM is accurate to ~a nozzle width), never in Z (where it's quantized to
0.2 mm layers). Concretely:

  * Tabs are extensions of a flat part's outline; tab thickness = part thickness.
  * Sockets are holes/pockets whose walls run along the insertion direction.
  * Crush ribs are small triangular ridges on socket walls, running along the
    insertion direction. They deform on insertion and hold by friction, which
    suits stiff, brittle PLA better than a flexing snap.
  * Only one socket per part locates it along a wall; the rest float that way
    (float_clearance) so several pegs never fight each other.
  * Detent barbs (coupon only) are bumps on a split-prong tab's outline.
"""

import math
from dataclasses import dataclass, field

from build123d import Box, Location, Plane, Polygon, Pos, Rectangle, Rot, Solid, extrude, loft

EPS = 0.01  # overcut so boolean cuts never leave coplanar skins
# extrude() follows the outline's winding (clockwise goes -Z), so always say which way.
UP = (0, 0, 1)


@dataclass
class Piece:
    """One printable part in its local print frame (print face on Z=0).

    nominal: the part with every intentionally-interfering feature left off.
    extras:  features that are *meant* to overlap a mating part once assembled
             (crush ribs, detent barbs). body = nominal + extras.
    gates:   [(x, y, dir)] points on edges that are hidden once assembled, where
             the sprue may attach. dir is '-y' or '+y' (direction toward a rail).
    """
    nominal: object
    extras: list = field(default_factory=list)
    gates: list = field(default_factory=list)
    color: str = "default"
    paints: list = field(default_factory=list)   # [(color, volume)]; later ones win

    @property
    def body(self):
        out = self.nominal
        for e in self.extras:
            out = out + e
        return out

    def regions(self):
        """{color: solid}: the body split by its paint volumes.

        The regions partition the body exactly (they only share faces), so a
        slicer sees clean, non-overlapping parts. Computed once per piece.
        """
        if getattr(self, "_regions", None) is None:
            remaining, out = self.body, {}
            for color, vol in reversed(self.paints):
                part = remaining & vol
                if part is not None and part.solids() and part.volume > 1e-6:
                    out[color] = out[color] + part if color in out else part
                    remaining = remaining - vol
            if remaining.solids() and remaining.volume > 1e-6:
                out[self.color] = out[self.color] + remaining if self.color in out else remaining
            self._regions = out
        return self._regions


def box(x0, x1, y0, y1, z0, z1):
    """Axis-aligned box from min/max coordinates (much easier to read than centers)."""
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def tab(x, y, width, length, thickness, lead, direction="-y"):
    """A tab sticking out of an edge at (x, y), with chamfered tip corners.

    Built pointing -y, then rotated for other directions. It overlaps the parent
    by EPS so the union is clean.
    """
    w, L, c = width / 2, length, min(lead, width / 4, length / 2)
    outline = Polygon(
        (-w, EPS), (w, EPS), (w, -L + c), (w - c, -L), (-w + c, -L), (-w, -L + c),
        align=None,
    )
    solid = extrude(outline, thickness, dir=UP)
    angle = {"-y": 0, "+x": 90, "+y": 180, "-x": -90}[direction]
    return Pos(x, y, 0) * Rot(0, 0, angle) * solid


def socket(cx, cy, sx, sy, z0, z1, p, mouth="top", ribs="y", rib_height=None):
    """A rectangular socket (cutter) with a 45° lead-in at its mouth, plus crush ribs.

    sx, sy are the *socket* sizes (tab size + 2*clearance). The socket spans
    z0..z1, with its mouth at z1 ('top') or z0 ('bottom'). Ribs sit on the two
    walls facing the `ribs` axis and press on the tab's faces.

    Returns (cutter, [rib solids]). Cut the cutter from the host, then add the ribs.
    """
    rh = p.rib_height if rib_height is None else rib_height
    li = p.lead_in
    cutter = box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z0 - EPS, z1 + EPS)
    zm, inward = (z1, -1) if mouth == "top" else (z0, +1)
    outer = Plane.XY.offset(zm - inward * EPS) * Rectangle(sx + 2 * (li + EPS), sy + 2 * (li + EPS))
    inner = Plane.XY.offset(zm + inward * li) * Rectangle(sx, sy)
    cutter = cutter + Pos(cx, cy, 0) * loft([outer, inner])

    ribs_out = []
    if rh > 0:
        # Ribs stop where the lead-in chamfer starts.
        rz0, rz1 = (z0, z1 - li) if mouth == "top" else (z0 + li, z1)
        b = min(p.rib_base, (sx if ribs == "y" else sy) - 0.2) / 2
        for side in (-1, 1):
            wall = (sy if ribs == "y" else sx) / 2 * side
            # Base sits EPS inside the wall so the rib fuses to it; apex points into the slot.
            tri = Polygon((-b, wall + side * EPS), (b, wall + side * EPS), (0, wall - side * rh),
                          align=None)
            rib = extrude(Plane.XY.offset(rz0) * tri, rz1 - rz0, dir=UP)
            if ribs == "x":
                rib = Rot(0, 0, 90) * rib  # walls facing x: rotate the y-version
            ribs_out.append(Pos(cx, cy, 0) * rib)
    return cutter, ribs_out


def barb_tab(x, y, p, width, length, barb_at, barb_h, thickness, slit=1.0):
    """Split-prong tab with a barb on each outer edge (coupon detent test).

    barb_at is the distance from the edge (y) to the barb's trailing face, i.e.
    the thickness of the plate it has to pass through plus a hair. The two prongs
    flex inward as the barbs pass through the slot, then spring out under it.
    """
    w = width / 2
    ramp, back = 1.2, 0.3          # leading ramp length, trailing face length
    yb = -barb_at                  # trailing (catching) face of the barb
    L = length
    pts = [(-w, EPS), (w, EPS),
           (w, yb), (w + barb_h, yb - back), (w, yb - back - ramp),
           (w, -L + p.lead_in), (w - p.lead_in, -L), (-w + p.lead_in, -L), (-w, -L + p.lead_in),
           (-w, yb - back - ramp), (-w - barb_h, yb - back), (-w, yb)]
    solid = extrude(Polygon(*pts, align=None), thickness, dir=UP)
    # The slit runs up into the parent part so the prongs are long enough to
    # flex, so it's returned separately: parent + tab - slit.
    slit_cut = box(-slit / 2, slit / 2, -L - EPS, 2.0, -EPS, thickness + EPS)
    return Pos(x, y, 0) * solid, Pos(x, y, 0) * slit_cut


def bboxes_touch(a, b, pad=0.01) -> bool:
    A, B = a.bounding_box(), b.bounding_box()
    return all(getattr(A.min, k) <= getattr(B.max, k) + pad and
               getattr(B.min, k) <= getattr(A.max, k) + pad for k in "XYZ")


def overlap(a, b) -> float:
    """Boolean intersection volume of two shapes (0 if they don't touch)."""
    if not bboxes_touch(a, b):
        return 0.0
    try:
        r = a & b
    except Exception:
        return 0.0
    if r is None:
        return 0.0
    return sum(s.volume for s in r.solids())
