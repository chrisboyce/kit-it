"""Lay flat parts out on a sprue frame, attach gates, emboss labels, verify.

pack() finds the layout: it tries many orders and keeps the smallest sheet, turning parts
90 degrees where that helps, and keeps the bed corner the prime tower needs free. A kit too
big for one sheet goes through paginate() first. A kit with more colors than the printer
has tools names its sheets instead (Plate, assign()); those can be big, because a kit's
parts are spread over as few as its colors allow.

Every part gets gates from gates_for(): the ones its Piece declares, plus enough more,
spread around its outline, to hold it on the sheet. Each part's label pad sits on the rail
below it, so labels take no room from the parts.

This is used for both the kit (view.py) and the test coupon (coupon.py).
"""

import math
import random
from dataclasses import dataclass, field

from build123d import Location, Pos
from OCP.gp import gp_Dir, gp_Lin, gp_Pnt
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector

from joints import EPS, box, overlap
from params import Params
from parts import label


@dataclass
class Item:
    name: str
    piece: object            # joints.Piece
    label: str | None = None


@dataclass(frozen=True)
class Plate:
    """A hand-picked plate: which parts, and which filament is in which tool."""
    name: str
    tools: tuple             # color names; index + 1 = tool number
    parts: tuple             # part names
    sprue: str               # rails and gates
    label: str               # embossed part numbers


def assign(items, plates):
    """[[Item]] per Plate. Every item has to be on exactly one plate."""
    by_name = {it.name: it for it in items}
    listed = [name for plate in plates for name in plate.parts]
    wrong = sorted({n for n in listed if listed.count(n) > 1} | (set(listed) ^ set(by_name)))
    if wrong:
        raise SystemExit(f"plate assignment: not on exactly one plate: {', '.join(wrong)}")
    return [[by_name[name] for name in plate.parts] for plate in plates]


@dataclass
class Sprue:
    names: list
    poses: list              # print pose (Location) per item
    parts: list              # part bodies in print pose
    rails: object            # rails + label pads
    labels: list             # embossed label text, one solid per pad (may be empty)
    gates: list = field(default_factory=list)   # [(item index, solid)]
    size: tuple = (0, 0)
    pieces: list = field(default_factory=list)
    rail_rects: list = field(default_factory=list)   # (x0, x1, y0, y1)
    gate_rects: list = field(default_factory=list)   # (x0, x1, y0, y1), matching gates
    boxes: list = field(default_factory=list)        # parts' footprints, (x0, x1, y0, y1)
    pad_rects: list = field(default_factory=list)    # (x0, x1, y0, y1)
    left_over: list = field(default_factory=list)    # names that didn't fit

    def bed_offset(self, p: Params):
        """Where the sheet's origin goes on the bed: its front-right corner, as far from
        the prime tower as it can be."""
        return p.bed_x - p.bed_margin - self.size[0], p.bed_margin

    def solid(self):
        """Everything fused into one printable object.

        One multi-argument fuse: much faster than adding pieces one at a time.
        """
        return self.rails.fuse(*self.labels, *[g for _, g in self.gates], *self.parts)

    def color_solids(self, p: Params):
        """{color: solid} for a multi-material print. Regions only share faces:
        the sprue is cut back wherever a part or a label occupies the space."""
        by_color = {}
        for pose, piece in zip(self.poses, self.pieces):
            for color, region in piece.regions().items():
                by_color.setdefault(color, []).append(pose * region)
        sprue = self.rails.fuse(*[g for _, g in self.gates])
        sprue = sprue.cut(*self.labels, *self.parts)
        by_color.setdefault(p.color_sprue, []).append(sprue)
        if self.labels:
            by_color.setdefault(p.color_label, []).extend(self.labels)
        out = {}
        for color, solids in by_color.items():
            out[color] = solids[0].fuse(*solids[1:]) if len(solids) > 1 else solids[0]
        return out


def _pad_width(text, p):
    return 0 if not text else max(5.0, 0.7 * p.label_size * len(text) + 2.0)


# ---------------------------------------------------------------------------
# Packing. Pure rectangles, no geometry, so it can afford many tries.
# ---------------------------------------------------------------------------
@dataclass
class Spot:
    index: int               # into the sizes given to pack()
    x: float                 # lower-left of the part's bounding box, in sheet coordinates
    y: float
    turned: bool             # rotated 90 degrees about Z


@dataclass
class Packing:
    spots: list
    rails: list              # (x0, x1, y0, y1)
    size: tuple
    left_over: list          # indices that didn't fit

    @property
    def area(self):
        return self.size[0] * self.size[1]


class _Packer:
    """Fills the sheet by guillotine cuts, and every cut is a rail.

    A region is a rectangle with rails on its sides. A row of similar parts goes in its
    lower-left corner, and what's left splits into the space to the row's right and the
    space above it, each filled the same way. Since every rail runs from rail to rail, the
    frame is connected by construction, and a part always has rails close by. The right
    and top of the whole sheet aren't rails yet: they land wherever the parts stop.
    """

    def __init__(self, sizes, order, p, rng=None):
        self.sizes, self.left, self.p, self.rng = sizes, list(order), p, rng
        self.spots, self.rails = [], []

    def _ways(self, i):
        w, h = self.sizes[i][:2]
        ways = [(w, h, False), (h, w, True)]
        # Lying down is the better habit, but not always.
        if (w < h) != bool(self.rng and self.rng.random() < 0.3):
            ways.reverse()
        return ways

    def _cell(self, i, w):
        return max(w, self.sizes[i][2])      # a part narrower than its label reserves the label's width

    def fill(self, x0, y0, x1, y1, top_is_rail, right_is_rail):
        """Returns whether anything was placed. x0..y1 are the rails' inner faces."""
        p = self.p
        g, rw = p.gate_gap, p.rail_width
        room_w, room_h = x1 - x0 - 2 * g, y1 - y0 - 2 * g
        row = []
        for i in self.left:
            for w, h, turned in self._ways(i):
                if self._cell(i, w) <= room_w and h <= room_h:
                    row.append((i, w, h, turned))
                    break
            if row:
                break
        if not row:
            return False
        self.left.remove(row[0][0])
        row_h = row[0][2]
        end = self._cell(row[0][0], row[0][1])
        # A tall row gets a rail between its parts, so their long sides can be held too.
        stiled = row_h > p.stile_over
        step = 2 * g + rw if stiled else p.part_spacing
        # Its row mates must be nearly as tall, so their far gates aren't long and flimsy.
        for i in list(self.left):
            for w, h, turned in self._ways(i):
                cell = self._cell(i, w)
                if row_h - (p.gate_max - g) <= h <= row_h and end + step + cell <= room_w:
                    row.append((i, w, h, turned))
                    self.left.remove(i)
                    end += step + cell
                    break
        top = y0 + g + row_h + g             # bottom of the rail above the row
        x = x0 + g
        for n, (i, w, h, turned) in enumerate(row):
            self.spots.append(Spot(i, x, y0 + g, turned))
            x += self._cell(i, w) + step
            if stiled and n < len(row) - 1:
                self.rails.append((x - g - rw, x - g, y0, top))
        right = x0 + g + end + g             # left of the rail to the row's right
        area_right = (x1 - right) * (y1 - y0)
        area_top = (x1 - x0) * (y1 - top)
        tall_right = self.rng.random() < 0.5 if self.rng else area_right > area_top

        right_top = y1 if tall_right else top
        used_right = self.fill(right + rw, y0, x1, right_top,
                               top_is_rail if tall_right else True, right_is_rail)
        if used_right:
            self.rails.append((right, right + rw, y0, right_top))
        top_x1 = right if used_right and tall_right else x1
        top_right_is_rail = (used_right and tall_right) or right_is_rail
        used_top = self.fill(x0, top + rw, top_x1, y1, top_is_rail, top_right_is_rail)
        # With nothing above it and a real rail close by, the row can just use that one.
        if used_top or not top_is_rail or y1 - (top - g) > p.gate_max:
            self.rails.append((x0, top_x1, top, top + rw))
        return True


def _sheet(sizes, order, p: Params, rng=None, tall=False) -> Packing:
    """Pack in one order, leaving a corner of the bed for the prime tower.

    Sheet coordinates: the usable bed's lower-left is (0, 0), and the tower gets its
    upper-left corner. That leaves an L, cut in two one of two ways: a wide region under the
    tower plus a short one to its right, or (tall) a full-height region to its right plus a
    narrow one under it. The second region, and its rails, only exist if it gets used.
    """
    rw, g = p.rail_width, p.gate_gap
    use_x, use_y = p.bed_x - 2 * p.bed_margin, p.bed_y - 2 * p.bed_margin
    tx, ty = p.tower_x - p.bed_margin, p.tower_y - p.bed_margin
    under = use_y - ty - rw                  # top of the space under the tower
    seeds = (((tx + rw, rw, use_x - rw, use_y - rw), (rw, rw, tx, under)) if tall else
             ((rw, rw, use_x - rw, under), (tx + rw, under + rw, use_x - rw, use_y - rw)))

    k = _Packer(sizes, order, p, rng)
    groups = []                              # [(spots, rails)] per region
    for seed in seeds:
        spots, rails = len(k.spots), len(k.rails)
        k.fill(*seed, False, False)
        groups.append((k.spots[spots:], k.rails[rails:]))
    placed = {s.index for s in k.spots}
    left_over = [i for i in order if i not in placed]
    if not k.spots:
        return Packing([], [], (0.0, 0.0), left_over)

    def far(s):
        w, h = sizes[s.index][:2]
        w, h = (h, w) if s.turned else (w, h)
        return s.x + max(w, sizes[s.index][2]) + g + rw, s.y + h + g + rw

    W = max(far(s)[0] for s in k.spots)
    tops = [max((far(s)[1] for s in spots), default=0.0) for spots, _ in groups]
    both = bool(groups[1][0])
    if tall:
        rects = [(tx, 0.0, W, tops[0]), (0.0, 0.0, tx + rw, tops[1])]
    else:
        rects = [(0.0, 0.0, W, under + rw if both else tops[0]), (tx, under, W, tops[1])]

    out = []
    for (x0, y0, x1, y1), (_, rails) in zip(rects[:1 + both], groups):
        frame = [(x0, x1, y0, y0 + rw), (x0, x1, y1 - rw, y1), (x0, x0 + rw, y0, y1), (x1 - rw, x1, y0, y1)]
        for a0, a1, b0, b1 in rails + frame:
            a1, b1 = min(a1, x1), min(b1, y1)
            if a1 > a0 and b1 > b0:
                out.append((a0, a1, b0, b1))
    H = max(r[3] for r in out)
    if tall and not both:                    # nothing left of the tower's edge: close up
        k.spots = [Spot(s.index, s.x - tx, s.y, s.turned) for s in k.spots]
        out = [(a0 - tx, a1 - tx, b0, b1) for a0, a1, b0, b1 in out]
        W -= tx
    return Packing(k.spots, out, (W, H), left_over)


def pack(sizes, p: Params) -> Packing:
    """sizes: [(width, height, label pad width)]. Keeps the best of many tries: whatever
    leaves out the least, then the smallest sheet. Seeded, so every build is the same."""
    n = range(len(sizes))
    biggest = sorted(n, key=lambda i: (-max(sizes[i][:2]), -sizes[i][0] * sizes[i][1]))
    # What's left out counts by its area: leaving out one big part isn't a near miss.
    score = lambda t: (sum(sizes[i][0] * sizes[i][1] for i in t.left_over), t.area)
    best = min(_sheet(sizes, biggest, p), _sheet(sizes, biggest, p, tall=True), key=score)
    rng = random.Random(0)
    for i in range(p.pack_tries):
        # Big things first, roughly: a little noise is what finds the better layouts.
        order = sorted(n, key=lambda i: -max(sizes[i][:2]) * rng.uniform(0.6, 1.4))
        t = _sheet(sizes, order, p, rng, tall=bool(i % 2))
        if score(t) < score(best):
            best = t
    return best


def _sizes(items, p):
    sizes = []
    for it in items:
        b = it.piece.body.bounding_box()
        sizes.append((b.size.X, b.size.Y, _pad_width(it.label, p)))
    return sizes


def paginate(items, p: Params):
    """Split items into as few sheets as it takes, filling each in turn."""
    sheets, rest = [], list(items)
    while rest:
        got = pack(_sizes(rest, p), p)
        if not got.spots:
            raise SystemExit(f"too big for the bed: {', '.join(it.name for it in rest)}")
        placed = {s.index for s in got.spots}
        sheets.append([it for i, it in enumerate(rest) if i in placed])
        rest = [it for i, it in enumerate(rest) if i not in placed]
    return sheets


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------
_DIRS = {"-y": (0, -1), "+y": (0, 1), "-x": (-1, 0), "+x": (1, 0)}
_FLAT = 0.02            # hits closer than this are the same edge
_SCAN = 0.5             # mm between rays
_JOINT = 8.0            # an edge narrower than this could well be a tab or a socket
_RECESS = 6.0           # don't reach further into a part than this


def _scan(d, z, b, shooter):
    """[(u, first hit, material behind it)] for rays coming in from direction d, at height z.
    u runs along the side, and a hit is measured in from the bounding box's edge."""
    dx, dy = _DIRS[d]
    lo, hi = (b.min.X, b.max.X) if dx == 0 else (b.min.Y, b.max.Y)
    span = b.size.Y if dx == 0 else b.size.X
    n = max(1, int((hi - lo) / _SCAN))
    rows = []
    for k in range(n):
        u = lo + (k + 0.5) * (hi - lo) / n
        if dx == 0:
            start = (u, b.max.Y + 1 if dy > 0 else b.min.Y - 1, z)
        else:
            start = (b.max.X + 1 if dx > 0 else b.min.X - 1, u, z)
        shooter.Perform(gp_Lin(gp_Pnt(*start), gp_Dir(-dx, -dy, 0)), 0.0, span + 2)
        ws = sorted(shooter.WParameter(i + 1) - 1 for i in range(shooter.NbPnt()))
        if ws:
            rows.append((u, ws[0], ws[1] - ws[0] if len(ws) > 1 else 0.0))
    return rows


def edge_spots(piece, p: Params):
    """Where a gate could go on this part: ([good], [fallback]), each [(x, y, dir)] in its
    local frame.

    A spot has to be on a straight edge at both the top and bottom of the gate, near the
    outline, with solid part behind it. Good ones are on edges too long to be a tab or a
    socket, since a nub left on those would spoil the fit. Fallbacks are any other edge,
    for parts too small or too fancy to have good ones.
    """
    cached = getattr(piece, "_edge_spots", None)
    if cached is not None:
        return cached
    body = piece.body
    b = body.bounding_box()
    shooter = IntCurvesFace_ShapeIntersector()
    shooter.Load(body.wrapped, 1e-4)
    z0, z1 = b.min.Z + 0.15, b.min.Z + p.zq(p.gate_height) - 0.15
    margin = p.gate_width / 2 + 0.5
    good, fallback = [], []
    for d, (dx, dy) in _DIRS.items():
        low = {u: hit for u, hit, _ in _scan(d, z0, b, shooter)}
        side = b.size.X if dx == 0 else b.size.Y
        runs, run = [], []
        for u, hit, behind in _scan(d, z1, b, shooter):
            flat = u in low and abs(low[u] - hit) < _FLAT and hit <= _RECESS and behind >= p.min_feature
            if flat and run and abs(run[-1][1] - hit) < _FLAT:
                run.append((u, hit))
                continue
            if run:
                runs.append(run)
            run = [(u, hit)] if flat else []
        if run:
            runs.append(run)
        for run in runs:
            u0, u1, hit = run[0][0], run[-1][0], run[0][1]
            width = u1 - u0
            if width < 2 * margin:
                continue
            at = u0 + margin
            spots = []
            while at <= u1 - margin + 1e-6:
                if dx == 0:
                    spots.append((at, b.max.Y - hit if dy > 0 else b.min.Y + hit, d))
                else:
                    spots.append((b.max.X - hit if dx > 0 else b.min.X + hit, at, d))
                at += 1.0
            (good if width >= _JOINT or width >= 0.6 * side else fallback).extend(spots)
    piece._edge_spots = good, fallback
    return piece._edge_spots


def _to_sheet(pt, pose_xy, turned):
    x, y = pt
    if turned:
        x, y = -y, x
    return x + pose_xy[0], y + pose_xy[1]


def _dir_on_sheet(d, turned):
    dx, dy = _DIRS[d]
    return (-dy, dx) if turned else (dx, dy)


def _route(x, y, v, rails, boxes, own, p):
    """The gate from a spot on the part to the nearest rail: its (x0, x1, y0, y1), or None."""
    half = p.gate_width / 2
    best = None
    for r0, r1, s0, s1 in rails:
        if v[0] == 0:
            if r0 <= x - half and x + half <= r1:
                far = s0 - y if v[1] > 0 else y - s1
            else:
                continue
        else:
            if s0 <= y - half and y + half <= s1:
                far = r0 - x if v[0] > 0 else x - r1
            else:
                continue
        if far >= 0 and (best is None or far < best):
            best = far
    if best is None or best > p.gate_max:
        return None
    if v[0] == 0:
        y1 = y + v[1] * best
        rect = (x - half, x + half, min(y, y1), max(y, y1))
    else:
        x1 = x + v[0] * best
        rect = (min(x, x1), max(x, x1), y - half, y + half)
    for j, (a0, a1, b0, b1) in enumerate(boxes):
        if j != own and rect[0] < a1 and a0 < rect[1] and rect[2] < b1 and b0 < rect[3]:
            return None
    return rect


def gates_for(piece, pose_xy, turned, own, rails, boxes, p: Params):
    """[(x, y, v, rect)] on the sheet: the part's declared gates that have a way to a rail,
    then more, each as far as possible from those already chosen. That spreads them
    around the outline, so a part is held from more than one side."""
    b = piece.body.bounding_box()
    want = min(p.gate_most, max(2, math.ceil(2 * (b.size.X + b.size.Y) / p.gate_pitch)))

    def routed(spots):
        out = []
        for x, y, d in spots:
            sx, sy = _to_sheet((x, y), pose_xy, turned)
            v = _dir_on_sheet(d, turned)
            rect = _route(sx, sy, v, rails, boxes, own, p)
            if rect:
                out.append((sx, sy, v, rect))
        return out

    good, fallback = edge_spots(piece, p)
    chosen = routed(piece.gates)
    for pool in (routed(good), routed(fallback)):
        while len(chosen) < want and pool:
            far = lambda g: min(((g[0] - c[0]) ** 2 + (g[1] - c[1]) ** 2 for c in chosen), default=math.inf)
            pick = max(pool, key=far)
            if far(pick) < 9.0:      # closer than 3 mm to another gate adds nothing
                break
            chosen.append(pick)
            pool.remove(pick)
    return chosen


def _gate_solid(x, y, v, rect, p: Params):
    """A gate from the rail end of rect, narrowing to its neck at the part."""
    gh, neck, n = p.zq(p.gate_height), 0.6, p.gate_neck / 2
    x0, x1, y0, y1 = rect
    if v[0] == 0:
        if v[1] > 0:
            return box(x0, x1, y + neck, y1 + EPS, 0, gh) + box(x - n, x + n, y - 0.1, y + neck + EPS, 0, gh)
        return box(x0, x1, y0 - EPS, y - neck, 0, gh) + box(x - n, x + n, y - neck - EPS, y + 0.1, 0, gh)
    if v[0] > 0:
        return box(x + neck, x1 + EPS, y0, y1, 0, gh) + box(x - 0.1, x + neck + EPS, y - n, y + n, 0, gh)
    return box(x0 - EPS, x - neck, y0, y1, 0, gh) + box(x - neck - EPS, x + 0.1, y - n, y + n, 0, gh)


# ---------------------------------------------------------------------------
# The sheet
# ---------------------------------------------------------------------------
def layout(items, p: Params) -> Sprue:
    got = pack(_sizes(items, p), p)
    rw = p.rail_width
    rh = p.zq(p.rail_height)

    placed_items, poses, xys, turned, boxes = [], [], [], [], []
    for s in got.spots:
        it = items[s.index]
        b = it.piece.body.bounding_box()
        placed_items.append(it)
        turned.append(s.turned)
        if s.turned:     # (x, y) -> (-y, x)
            xy = (s.x + b.max.Y, s.y - b.min.X)
            poses.append(Location((*xy, 0), (0, 0, 90)))
            boxes.append((s.x, s.x + b.size.Y, s.y, s.y + b.size.X))
        else:
            xy = (s.x - b.min.X, s.y - b.min.Y)
            poses.append(Location((*xy, 0)))
            boxes.append((s.x, s.x + b.size.X, s.y, s.y + b.size.Y))
        xys.append(xy)

    # --- frame: the packer's rails, and a label pad straddling the rail under each part --
    solids = [box(x0, x1, y0, y1, 0, rh) for x0, x1, y0, y1 in got.rails]
    labels, pads = [], []
    pad_h = p.label_size + 1.6
    for it, (x0, _, y0, _) in zip(placed_items, boxes):
        pw = _pad_width(it.label, p)
        if pw:
            mid = y0 - p.gate_gap - rw / 2
            pads.append((x0, x0 + pw, mid - pad_h / 2, mid + pad_h / 2))
            solids.append(box(*pads[-1], 0, rh))
            labels.append(label(it.label, x0 + pw / 2, mid, rh, p))
    frame = solids[0].fuse(*solids[1:]) if len(solids) > 1 else solids[0]

    # --- gates ------------------------------------------------------------------
    gates, gate_rects = [], []
    for i, it in enumerate(placed_items):
        for x, y, v, rect in gates_for(it.piece, xys[i], turned[i], i, got.rails, boxes, p):
            gates.append((i, _gate_solid(x, y, v, rect, p)))
            gate_rects.append(rect)

    parts = [pose * it.piece.body for pose, it in zip(poses, placed_items)]
    return Sprue([it.name for it in placed_items], poses, parts, frame, labels, gates, got.size,
                 [it.piece for it in placed_items], got.rails, gate_rects, boxes, pads,
                 [items[i].name for i in got.left_over])


def _touches_rail(rect, rails, tol=0.01):
    x0, x1, y0, y1 = rect
    return any(x0 <= r1 + tol and r0 <= x1 + tol and y0 <= s1 + tol and s0 <= y1 + tol
               for r0, r1, s0, s1 in rails)


def verify(s: Sprue, p: Params, threshold=1e-3):
    """Sheet fits the bed and misses the prime tower; every part is on it and well held;
    parts don't touch each other, the rails, or other parts' gates."""
    errors, lines = [], []
    W, H = s.size
    lim_x, lim_y = p.bed_x - 2 * p.bed_margin, p.bed_y - 2 * p.bed_margin
    n = len(s.parts)
    area = sum((x1 - x0) * (y1 - y0) for x0, x1, y0, y1 in s.boxes)
    lines.append(f"sheet {W:.1f} x {H:.1f} mm (bed {p.bed_x:.0f} x {p.bed_y:.0f}, usable {lim_x:.0f} x {lim_y:.0f}), "
                 f"parts fill {100 * area / max(W * H, 1):.0f}% of it, {sum(abs(q.orientation.Z) > 1 for q in s.poses)} turned")
    if W > lim_x + 1e-6 or H > lim_y + 1e-6:
        errors.append(f"SHEET TOO BIG: {W:.1f} x {H:.1f} > {lim_x:.0f} x {lim_y:.0f}")
    if s.left_over:
        errors.append(f"DIDN'T FIT ON THE SHEET: {', '.join(s.left_over)}")

    dx, dy = s.bed_offset(p)
    for x0, x1, y0, y1 in [*s.rail_rects, *s.boxes]:
        if x0 + dx < p.tower_x and y1 + dy > p.bed_y - p.tower_y:
            errors.append(f"IN THE PRIME TOWER'S CORNER: {x0:.1f}..{x1:.1f} x {y0:.1f}..{y1:.1f}")

    for i in range(n):
        for j in range(i + 1, n):
            v = overlap(s.parts[i], s.parts[j])
            if v > threshold:
                errors.append(f"OVERLAP {s.names[i]} x {s.names[j]}: {v:.3f} mm^3")
        # The frame is all rectangles, so these need no booleans: much faster than one per part.
        x0, x1, y0, y1 = s.boxes[i]
        for r0, r1, q0, q1 in [*s.rail_rects, *s.pad_rects]:
            if x0 < r1 and r0 < x1 and y0 < q1 and q0 < y1:
                errors.append(f"OVERLAP {s.names[i]} x rails/labels at {r0:.1f}, {q0:.1f}")
    counts = [0] * n
    for (gi, g), rect in zip(s.gates, s.gate_rects):
        counts[gi] += 1
        for j in range(n):
            v = overlap(g, s.parts[j])
            if j == gi and v <= threshold:
                errors.append(f"GATE for {s.names[gi]} doesn't reach its part")
            if j != gi and v > threshold:
                errors.append(f"GATE for {s.names[gi]} hits {s.names[j]}: {v:.3f} mm^3")
        if not _touches_rail(rect, s.rail_rects):
            errors.append(f"GATE for {s.names[gi]} doesn't reach a rail")
    for name, c in zip(s.names, counts):
        if c == 0:
            errors.append(f"NO GATES: nothing holds {name}")
        elif c == 1:
            lines.append(f"WARNING {name} has only one gate")
    lines.append(f"sprue: {n} parts, {len(s.gates)} gates "
                 f"({min(counts, default=0)} to {max(counts, default=0)} a part), {len(errors)} problems")
    return errors, lines


def could_share(plates, items, p: Params):
    """Named plates that could be one sheet: their colors fit the tools, and their parts fit
    the bed. Plate lists are written by hand, so this keeps them honest."""
    by_name = {it.name: it for it in items}
    colors = lambda pl: {c for n in pl.parts for c in by_name[n].piece.regions()} | {pl.sprue, pl.label}
    out = []
    for i, a in enumerate(plates):
        for b in plates[i + 1:]:
            if len(colors(a) | colors(b)) <= p.max_tools:
                group = [by_name[n] for n in (*a.parts, *b.parts)]
                if not pack(_sizes(group, p), p).left_over:
                    out.append((a.name, b.name))
    return out
