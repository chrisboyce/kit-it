"""Lay flat parts out on a sprue frame, attach gates, emboss labels, verify.

Layout is a simple shelf packer: parts sorted tallest-first, filled into rows
left to right. Every row has a rail below and above it, so a gate always runs
straight in Y from a hidden part edge to the nearest rail. Each part gets a
small label pad on the rail just to its left.

This is used for both the kit (view.py) and the test coupon (coupon.py).
"""

from dataclasses import dataclass, field

from build123d import Location, Pos

from joints import EPS, box, overlap
from params import Params
from parts import label


@dataclass
class Item:
    name: str
    piece: object            # joints.Piece
    label: str | None = None


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


def layout(items, p: Params) -> Sprue:
    rw, gap = p.rail_width, p.gate_gap
    max_w = p.bed_x - 2 * p.bed_margin - 2 * rw
    boxes = [it.piece.body.bounding_box() for it in items]
    order = sorted(range(len(items)), key=lambda i: -boxes[i].size.Y)

    # --- shelf pack ---------------------------------------------------------
    rows, row, x = [], [], 1.0
    for i in order:
        cell = _pad_width(items[i].label, p) + 2.0 + boxes[i].size.X + p.part_spacing - 2.0
        if row and x + cell > max_w:
            rows.append(row)
            row, x = [], 1.0
        row.append((i, x))
        x += cell
    rows.append(row)

    # --- place parts row by row, building rails as we go ----------------------
    poses = [None] * len(items)
    rails_y = [0.0]                       # bottom edge of each horizontal rail
    pads = []                             # (x0, x1, y0, y1, text)
    rails_below = [None] * len(items)
    y = rw + gap
    width = 0.0
    for row in rows:
        row_h = max(boxes[i].size.Y for i, _ in row)
        rail_top = y - gap
        for i, cx in row:
            pw = _pad_width(items[i].label, p)
            px = rw + cx + pw + 2.0 if pw else rw + cx
            b = boxes[i]
            poses[i] = Location((px - b.min.X, y - b.min.Y, 0))
            rails_below[i] = (rail_top, y + row_h + gap)   # (top of rail below, bottom of rail above)
            if pw:
                pads.append((rw + cx + 0.5, rw + cx + 0.5 + pw, rail_top - EPS,
                             rail_top + p.label_size + 1.6, items[i].label))
            width = max(width, px + b.size.X + 3.0)
        y += row_h + gap
        rails_y.append(y)
        y += rw + gap

    W = width + rw
    H = rails_y[-1] + rw
    rh = p.zq(p.rail_height)

    # --- frame: horizontal rails, two side rails, label pads ------------------
    frame = box(0, rw, 0, H, 0, rh) + box(W - rw, W, 0, H, 0, rh)
    for ry in rails_y:
        frame += box(0, W, ry, ry + rw, 0, rh)
    texts = []
    for x0, x1, y0, y1, text in pads:
        frame += box(x0, x1, y0, y1, 0, rh)
        texts.append(label(text, (x0 + x1) / 2, (y0 + y1) / 2 + 0.3, rh, p))
    labels = texts

    # --- gates ------------------------------------------------------------------
    gates = []
    gw, gn, gh = p.gate_width, p.gate_neck, p.zq(p.gate_height)
    neck_len = 0.6
    for i, it in enumerate(items):
        dx, dy = poses[i].position.X, poses[i].position.Y
        below, above = rails_below[i]
        for gx, gy, d in it.piece.gates:
            x, ye = gx + dx, gy + dy
            if d == "-y":   # rail is below the part
                g = box(x - gw / 2, x + gw / 2, below - EPS, ye - neck_len, 0, gh)
                g += box(x - gn / 2, x + gn / 2, ye - neck_len - EPS, ye + 0.1, 0, gh)
            else:           # rail is above the part
                g = box(x - gw / 2, x + gw / 2, ye + neck_len, above + EPS, 0, gh)
                g += box(x - gn / 2, x + gn / 2, ye - 0.1, ye + neck_len + EPS, 0, gh)
            gates.append((i, g))

    placed = [pose * it.piece.body for pose, it in zip(poses, items)]
    return Sprue([it.name for it in items], poses, placed, frame, labels, gates, (W, H),
                 [it.piece for it in items])


def verify(s: Sprue, p: Params, threshold=1e-3):
    """Plate fits the bed; parts don't touch each other, the rails, or other parts' gates."""
    errors, lines = [], []
    W, H = s.size
    lim_x, lim_y = p.bed_x - 2 * p.bed_margin, p.bed_y - 2 * p.bed_margin
    lines.append(f"plate {W:.1f} x {H:.1f} mm (bed {p.bed_x:.0f} x {p.bed_y:.0f}, "
                 f"usable {lim_x:.0f} x {lim_y:.0f})")
    if W > lim_x or H > lim_y:
        errors.append(f"PLATE TOO BIG: {W:.1f} x {H:.1f} > {lim_x:.0f} x {lim_y:.0f}")

    n = len(s.parts)
    for i in range(n):
        for j in range(i + 1, n):
            v = overlap(s.parts[i], s.parts[j])
            if v > threshold:
                errors.append(f"OVERLAP {s.names[i]} x {s.names[j]}: {v:.3f} mm^3")
        v = overlap(s.parts[i], s.rails) + sum(overlap(s.parts[i], t) for t in s.labels)
        if v > threshold:
            errors.append(f"OVERLAP {s.names[i]} x rails/labels: {v:.3f} mm^3")
    for gi, g in s.gates:
        for j in range(n):
            v = overlap(g, s.parts[j])
            if j == gi and v <= threshold:
                errors.append(f"GATE for {s.names[gi]} doesn't reach its part")
            if j != gi and v > threshold:
                errors.append(f"GATE for {s.names[gi]} hits {s.names[j]}: {v:.3f} mm^3")
        if overlap(g, s.rails) <= threshold:
            errors.append(f"GATE for {s.names[gi]} doesn't reach a rail")
    lines.append(f"sprue: {n} parts, {len(s.gates)} gates, {len(errors)} problems")
    return errors, lines
