"""Witness coupons: a small go/no-go sheet per plate that proves its joints still fit.

The coupon (coupon.py) is for choosing a fit. A witness is for checking one: print it in the
same filament, on the same settings, and snap each numbered pair together. Each should go in
and hold. If one doesn't, the real parts won't either, and you've found out for a few grams.

Nothing here is written by hand, so a witness can't drift from its kit. Joints are found in the
assembled model: wherever part A enters a gap in part B, that's a joint. Each half is then
cropped out of the real part, in XY only, so it keeps its height, its print orientation and
its layers. Joints with the same shape count as one type, and a plate's witness has one pair of
each type that has a half on that plate.

Each half prints in its part's main color if that plate loads it, or else in the sprue's
color. Painted details aren't carried over, since they don't change the fit.

What a witness can't show: anything that needs the whole part. Warped panels, and pegs spread
along a long wall that have drifted apart, only show up on the real thing.

    python witness.py --kit caboose [--list] [--set name=value ...] [--out DIR]
"""

import argparse
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

from build123d import Compound

import registry
from joints import Piece, bboxes_touch, box
from params import with_overrides
from sprue import Item, assign, paginate
from view import KITS, default_out, run_plate

MARGIN = 3.0            # material kept around a joint: more than a slit's root, and the socket's walls
GRIP = 12.0             # a half is at least this wide and long, so it can be held and pushed
REACH = 0.8             # the host has to be this close on two opposite sides to hold what's in it
TOGETHER = 1.2          # pieces of an engagement this close are one joint: a split tab's two prongs
LONGEST = 40.0          # a joint longer than this keeps only this much of its length
DEEPEST = 0.2           # how much of a long engagement's far end counts as what really goes in


@dataclass
class Half:
    part: str
    piece: object
    window: tuple           # x0, x1, y0, y1 in the part's own frame


@dataclass
class Joint:
    key: tuple              # same key, same joint
    insert: Half            # the half that goes in: a tab, or either side of a cross-lap
    host: Half              # the half with the gap
    size: tuple             # the engagement in the host's frame: x, y, z
    held: tuple             # the same, as (bits in the host's frame, their bounding box)
    to_insert: object       # host's frame -> insert's frame
    pairs: list = field(default_factory=list)    # (insert, host) part names, one per joint in the kit


def _solids(shape):
    return [] if shape is None else list(shape.solids())


def _is_held(host, b):
    """Does the host hold this from two opposite sides? A neighbour resting against an edge
    doesn't count."""
    r, z0, z1 = REACH, b.min.Z, b.max.Z
    sides = (box(b.min.X - r, b.min.X, b.min.Y, b.max.Y, z0, z1), box(b.max.X, b.max.X + r, b.min.Y, b.max.Y, z0, z1),
             box(b.min.X, b.max.X, b.min.Y - r, b.min.Y, z0, z1), box(b.min.X, b.max.X, b.max.Y, b.max.Y + r, z0, z1))
    hit = [any(s.volume > 1e-4 for s in _solids(host & side)) for side in sides]
    return (hit[0] and hit[1]) or (hit[2] and hit[3])


def _clusters(bits):
    """Group solids whose bounding boxes nearly touch."""
    groups = []
    for bit in bits:
        near = [g for g in groups if any(bboxes_touch(bit, other, pad=TOGETHER) for other in g)]
        for g in near:
            groups.remove(g)
        groups.append([bit, *(b for g in near for b in g)])
    return groups


def _deepest(bits, e, hb):
    """What reaches furthest into the host, from a long engagement. A sheet can lie along a
    host inside its raised trim, with only its tabs going into pockets: those are the joint.
    Returns the same bits if there's no telling which way in it came."""
    from_top, from_bottom = e.max.Z >= hb.max.Z - 0.05, e.min.Z <= hb.min.Z + 0.05
    if from_top == from_bottom:
        return [bits]
    z0, z1 = (e.min.Z, e.min.Z + DEEPEST) if from_top else (e.max.Z - DEEPEST, e.max.Z)
    tips = _solids(Compound(bits) & box(e.min.X, e.max.X, e.min.Y, e.max.Y, z0, z1))
    return _clusters([s for s in tips if s.volume >= 0.001]) or [bits]


def _fit_key(host, bits, e, hb, pad):
    """What decides how a joint fits, so that same key means same test: the size of what goes
    in, the clearance on each side, whether it's split, and whether the socket is open at the
    top or bottom of the print. How deep it goes doesn't count, and neither does the length
    of an open slot, which is how a cross-lap's depth varies from part to part.

    Clearance is measured halfway in, below any lead-in chamfer."""
    mid = (e.min.Z + e.max.Z) / 2
    room = box(e.min.X - pad, e.max.X + pad, e.min.Y - pad, e.max.Y + pad, mid - 0.05, mid + 0.05)
    voids = _solids(room - host)
    v = Compound(voids).bounding_box() if voids else e
    fit = lambda x: round(x * 20) / 20

    def walls(low, high):
        return [None if c >= pad - 0.01 else fit(c) for c in (low, high)]

    wx, wy = walls(e.min.X - v.min.X, v.max.X - e.max.X), walls(e.min.Y - v.min.Y, v.max.Y - e.max.Y)
    closed = lambda w: None not in w
    described = []
    for size, w in ((e.size.X, wx), (e.size.Y, wy)):
        described.append((fit(size), tuple(sorted(w))) if closed(w) else ("open",))
    return (*sorted(described, key=str), len(bits), e.min.Z <= hb.min.Z + 0.05, e.max.Z >= hb.max.Z - 0.05)


def _engagements(a, to_b, b):
    """Where a enters a gap in b: [(key, bits, bounding box)] in b's frame. a is clipped to b's
    bounding box, and since parts don't overlap, what's left can only be in b's gaps or past
    its outline."""
    host, out = b.nominal, []
    hb = host.bounding_box()
    moved = to_b * a.nominal
    if not bboxes_touch(moved, host, pad=-0.01):
        return out
    clip = moved & box(hb.min.X, hb.max.X, hb.min.Y, hb.max.Y, hb.min.Z, hb.max.Z)
    found = []
    for bits in _clusters([s for s in _solids(clip) if s.volume >= 0.05]):
        e = Compound(bits).bounding_box()
        found += _deepest(bits, e, hb) if max(e.size.X, e.size.Y) > LONGEST else [bits]
    for bits in found:
        e = Compound(bits).bounding_box()
        pad = REACH + 0.1
        room = box(e.min.X - pad, e.max.X + pad, e.min.Y - pad, e.max.Y + pad, hb.min.Z, hb.max.Z)
        near = host & room
        if not _solids(near) or not _is_held(near, e):
            continue
        out.append((_fit_key(host, bits, e, hb, pad), bits, e))
    return out


def _window(b, whole):
    """A crop around bounding box b, kept inside the part and big enough to hold."""
    def span(lo, hi, part_lo, part_hi):
        if hi - lo > LONGEST:
            mid = (lo + hi) / 2
            lo, hi = mid - LONGEST / 2, mid + LONGEST / 2
        lo, hi = lo - MARGIN, hi + MARGIN
        short = GRIP - (hi - lo)
        if short > 0:
            lo, hi = lo - short / 2, hi + short / 2
        # Slid back inside the part rather than cut short, which keeps the grip.
        if lo < part_lo:
            lo, hi = part_lo, min(part_hi, hi + part_lo - lo)
        if hi > part_hi:
            lo, hi = max(part_lo, lo - (hi - part_hi)), part_hi
        return lo, hi
    return (*span(b.min.X, b.max.X, whole.min.X, whole.max.X), *span(b.min.Y, b.max.Y, whole.min.Y, whole.max.Y))


def _crop(half):
    """The largest connected piece of a part inside its window, at the part's full height."""
    body = half.piece.body
    b = body.bounding_box()
    solids = _solids(body & box(*half.window, b.min.Z - 1, b.max.Z + 1))
    return max(solids, key=lambda s: s.volume) if solids else None


def _gates(crop, half):
    """The real part's own gates that fall inside the crop, then the middle of each edge the
    crop cut, or the nearest place to it with material: those are never part of the joint, and
    a post too thin for edge_spots still has somewhere to be held."""
    c, w = crop.bounding_box(), half.piece.body.bounding_box()
    x0, x1, y0, y1 = half.window
    mx, my, tol = (c.min.X + c.max.X) / 2, (c.min.Y + c.max.Y) / 2, 0.01
    spots = [(x0 > w.min.X + tol and c.min.X <= x0 + tol, c.min.X, None, "-x"),
             (x1 < w.max.X - tol and c.max.X >= x1 - tol, c.max.X, None, "+x"),
             (y0 > w.min.Y + tol and c.min.Y <= y0 + tol, None, c.min.Y, "-y"),
             (y1 < w.max.Y - tol and c.max.Y >= y1 - tol, None, c.max.Y, "+y")]

    def solid_here(x, y, d):
        """The gate's neck is 0.8 wide and reaches 0.1 in: all of that has to be material,
        since the middle of a cut edge can land on a notch."""
        into = 0.1 if d[0] == "-" else -0.1
        a, b = (x, x + into) if d[1] == "x" else (x - 0.4, x + 0.4)
        e, f = (y - 0.4, y + 0.4) if d[1] == "x" else (y, y + into)
        probe = box(min(a, b), max(a, b), min(e, f), max(e, f), c.min.Z, c.min.Z + 0.8)
        return sum(s.volume for s in _solids(crop & probe)) > 0.95 * probe.volume

    def along(x, y, d):
        """The place on this edge nearest its middle that a gate can land."""
        lo, hi, mid = (c.min.Y, c.max.Y, my) if d[1] == "x" else (c.min.X, c.max.X, mx)
        for k in range(int((hi - lo) / 0.5) + 1):
            for u in (mid - k * 0.5, mid + k * 0.5):
                at = (x, u) if d[1] == "x" else (u, y)
                if lo + 0.4 <= u <= hi - 0.4 and solid_here(*at, d):
                    return (*at, d)
        return None

    # The part's own gates already work on its real plate, even on a tab's tip or a curved
    # edge, so these only have to still be touching the crop.
    def touching(x, y):
        return _solids(crop & box(x - 0.15, x + 0.15, y - 0.15, y + 0.15, c.min.Z, c.max.Z))

    own = [g for g in half.piece.gates if x0 <= g[0] <= x1 and y0 <= g[1] <= y1 and touching(g[0], g[1])]
    return own + [g for g in (along(x, y, d) for cut, x, y, d in spots if cut) if g]


def find_joints(kit, p):
    """Every type of joint in a kit, as [Joint]. A pair found both ways round is either a
    cross-lap, or a tab and the strip of host between two tabs, which looks like a slot from
    the other side. Either way the smaller one is the joint."""
    placed = [(spec.name, piece, spec.built(p)) for spec, piece in kit]
    world = [loc * piece.nominal for _, piece, loc in placed]
    found = {}
    for i, (name_a, a, loc_a) in enumerate(placed):
        for j, (name_b, b, loc_b) in enumerate(placed[i + 1:], i + 1):
            if not bboxes_touch(world[i], world[j], pad=0.5):
                continue
            ways = [(name_a, a, loc_a, name_b, b, loc_b, _engagements(a, loc_b.inverse() * loc_a, b)),
                    (name_b, b, loc_b, name_a, a, loc_a, _engagements(b, loc_a.inverse() * loc_b, a))]
            used = [w for w in ways if w[-1]]
            if not used:
                continue
            ins_name, ins, loc_i, host_name, host, loc_h, got = min(
                used, key=lambda w: sum(s.volume for _, bits, _ in w[-1] for s in bits))
            for key, bits, e in got:
                if key not in found:
                    to_ins = loc_i.inverse() * loc_h
                    ea = (to_ins * Compound(bits)).bounding_box()
                    found[key] = Joint(key, Half(ins_name, ins, _window(ea, ins.nominal.bounding_box())),
                                       Half(host_name, host, _window(e, host.nominal.bounding_box())),
                                       (e.size.X, e.size.Y, e.size.Z), (bits, e), to_ins)
                found[key].pairs.append((ins_name, host_name))
    return list(found.values())


def make_pair(joint):
    """(insert solid, host solid, [problems]), each half checked to still have its joint."""
    ins, host = _crop(joint.insert), _crop(joint.host)
    bits, e = joint.held
    problems = []
    name = f"{joint.insert.part} into {joint.host.part}"
    if ins is None or host is None:
        return ins, host, [f"WITNESS: nothing left of {name} after cropping"]
    want = sum(s.volume for s in bits)
    kept = sum(s.volume for s in _solids(ins & (joint.to_insert * Compound(bits))))
    if kept < 0.99 * want:
        problems.append(f"WITNESS: the crop of {joint.insert.part} lost part of its tab for {name}")
    if not _is_held(host, e):
        problems.append(f"WITNESS: the crop of {joint.host.part} no longer holds {name}")
    return ins, host, problems


def _describe(n, j, parts):
    here = [(a, b) for a, b in j.pairs if a in parts or b in parts]
    x, y, z = j.size
    # Same fit, different parts: the one that gets printed speaks for all of these.
    also = sorted({f"{a} into {b}" for a, b in j.pairs} - {f"{j.insert.part} into {j.host.part}"})
    return (f"{n:2d}  {j.insert.part} into {j.host.part}: {x:.2f} x {y:.2f} x {z:.2f} mm, "
            f"{len(here)} on this plate, {len(j.pairs)} in the kit"
            + (f"\n      stands for: {', '.join(also)}" if also else ""))


def run_witness(joints, group, spec, p, out, stem, export=True):
    """One plate's witness. Returns whether it failed."""
    parts = {it.name for it in group}
    mine = [j for j in joints if any(a in parts or b in parts for a, b in j.pairs)]
    if not mine:
        print(f" {stem}: no joints on this plate")
        return False
    tools = list(spec.tools if spec else [n for n, _ in p.palette])[:p.max_tools]
    pp = replace(p, color_sprue=spec.sprue, color_label=spec.label) if spec else p

    def color(half):
        return half.piece.color if half.piece.color in tools else pp.color_sprue

    items, lines, problems = [], [], []
    for n, j in enumerate(mine, 1):
        ins, host, bad = make_pair(j)
        problems += bad
        if ins is None or host is None:
            continue
        items.append(Item(f"{n}_in_{j.insert.part}", Piece(ins, color=color(j.insert), gates=_gates(ins, j.insert)), str(n)))
        items.append(Item(f"{n}_host_{j.host.part}", Piece(host, color=color(j.host), gates=_gates(host, j.host)), str(n)))
        lines.append(_describe(n, j, parts))
    print(f" {stem}: {len(mine)} joint types")
    for line in lines:
        print("  " + line)
    for line in problems:
        print("  " + line)
    _, _, failed = run_plate(items, pp, out, stem, export, tools)
    if export:
        card = out / f"{stem}.txt"
        card.write_text(f"{stem}: snap each numbered pair together. Each should go in by hand and hold.\n"
                        f"Too tight or too loose means the same joint on the real parts is too.\n\n"
                        + "\n".join(lines) + "\n")
        print(f"  wrote {card}")
    return failed or bool(problems)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kit", choices=list(KITS), default="nook")
    ap.add_argument("--list", action="store_true", help="only list the joints found")
    ap.add_argument("--no-export", action="store_true", help="check the witnesses, but write no files")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    ap.add_argument("--out", default=None, type=Path)
    args = ap.parse_args(argv)

    defaults, specs, _, named = KITS[args.kit]
    p = with_overrides(defaults, args.set)
    out = args.out or default_out(args.kit)
    out.mkdir(parents=True, exist_ok=True)

    kit = registry.build(p, specs)
    joints = find_joints(kit, p)
    print(f"{args.kit}: {len(joints)} joint types, {sum(len(j.pairs) for j in joints)} joints")
    every = {spec.name for spec, _ in kit}
    if args.list:
        for n, j in enumerate(joints, 1):
            print("  " + _describe(n, j, every))
        return 0

    items = [Item(spec.name, piece, str(spec.num)) for spec, piece in kit]
    plates = assign(items, named) if named else paginate(items, p)
    failed = False
    for n, group in enumerate(plates, 1):
        spec = named[n - 1] if named else None
        stem = "witness" if len(plates) == 1 else f"witness{n}" + (f"_{spec.name}" if spec else "")
        failed |= run_witness(joints, group, spec, p, out, stem, not args.no_export)
    print("FAILED" if failed else "OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
