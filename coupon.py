"""Snap-fit test coupon: print this before trusting a fit change on a real kit.

Every tab is wall_thickness thick, like the kit, and all of them use the same
joint functions as the kit. Rows:

  D10 / D15  detent barbs (0.10 / 0.15 mm) on split-prong tabs, through a plate
             with six slots at clearances 0.05 .. 0.30 mm (labels in 1/100 mm).
             Tabs within a row are identical: try one in every slot.
  R          crush ribs 0.15 / 0.20 / 0.25 mm at the kit's clearance.
  SP         plain sockets at 0.05 / 0.10 / 0.15 mm, no ribs, for two tab styles:
             solid tabs (panels "S") and split, barb-less tabs (panels "P").
  M1 / M2    one 3-peg panel ("M"), two strips. M1: every socket is tight both
             ways (over-constrained). M2: the left socket locates, the other two
             float along the row (float_clearance), as the kit now does.
  KEY        keyed pair: the two facade tab widths. It should only go in one way.

    python coupon.py [--set name=value ...] [--out out]
"""

import argparse
import sys
from pathlib import Path

import checks
import render
from joints import EPS, Piece, barb_tab, box, socket, tab
from params import DEFAULT, with_overrides
from parts import label
from sprue import Item, layout, verify

CLEARANCES = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
DETENTS = (0.10, 0.15)
RIBS = (0.15, 0.20, 0.25)
PLAIN = (0.05, 0.10, 0.15)
PEGS = (8.0, 20.0, 32.0)   # M-row tab centers
PITCH = 10.0
STRIP_D = 13.0  # strip depth (Y)


def strip(p, n, thickness, title):
    """Flat plate with room for n sockets and a title at its left end."""
    w = 12 + n * PITCH
    body = box(0, w, 0, STRIP_D, 0, thickness)
    body += label(title, 6, STRIP_D / 2, thickness, p, size=2.5)
    return body, [(w * 0.3, 0, "-y"), (w * 0.8, 0, "-y")]


def slot_x(i):
    return 12 + PITCH * (i + 0.5)


def tab_panel(p, width, text, height=7.0):
    tw = p.wall_thickness
    body = box(0, width, 0, height, 0, tw)
    body += label(text, width / 2, height / 2, tw, p, size=2.5)
    return body, [(width * 0.5, height, "+y")]


def detent_row(p, h):
    tw, plate_t = p.wall_thickness, 2.0
    tab_w, sy = 4.0, STRIP_D / 2
    body, gates = strip(p, len(CLEARANCES), plate_t, f"D{round(h * 100)}")
    for i, c in enumerate(CLEARANCES):
        cut, _ = socket(slot_x(i), sy, tab_w + 2 * c, tw + 2 * c, 0, plate_t, p, rib_height=0)
        body -= cut
        body += label(f"{round(c * 100):02d}", slot_x(i), sy + 4.5, plate_t, p, size=2.2)
    items = [Item(f"detent_strip_{h}", Piece(body, [], gates))]
    for k in range(len(CLEARANCES)):
        panel, pg = tab_panel(p, 10, f"D{round(h * 100)}")
        t, slit = barb_tab(5, 0, p, tab_w, plate_t + 0.1 + 0.3 + 1.2 + 0.8, plate_t + 0.1, h, tw)
        items.append(Item(f"detent_tab_{h}_{k}", Piece(panel + t - slit, [], pg)))
    return items


def rib_row(p):
    tw, plate_t, tab_w, c = p.wall_thickness, 3.0, p.facade_tab_widths[0], p.clearance
    body, gates = strip(p, len(RIBS), plate_t, "R")
    ribs = []
    for i, rh in enumerate(RIBS):
        cut, r = socket(slot_x(i), STRIP_D / 2, tab_w + 2 * c, tw + 2 * c, 0, plate_t, p,
                        ribs="y", rib_height=rh)
        body -= cut
        ribs += r
        body += label(f"{round(rh * 100)}", slot_x(i), STRIP_D / 2 + 4.5, plate_t, p, size=2.2)
    items = [Item("rib_strip", Piece(body, ribs, gates))]
    for k in range(len(RIBS)):
        panel, pg = tab_panel(p, 10, "R")
        items.append(Item(f"rib_tab_{k}", Piece(panel + tab(5, 0, tab_w, plate_t - 0.2, tw, p.lead_in), [], pg)))
    return items


def solid_split_row(p):
    """Same plain sockets, two tab styles: does a slit buy an easier push?"""
    tw, plate_t, tab_w = p.wall_thickness, 3.0, 4.0
    body, gates = strip(p, len(PLAIN), plate_t, "SP")
    for i, c in enumerate(PLAIN):
        cut, _ = socket(slot_x(i), STRIP_D / 2, tab_w + 2 * c, tw + 2 * c, 0, plate_t, p, rib_height=0)
        body -= cut
        body += label(f"{round(c * 100):02d}", slot_x(i), STRIP_D / 2 + 4.5, plate_t, p, size=2.2)
    items = [Item("sp_strip", Piece(body, [], gates))]
    L = plate_t + 0.6          # pokes out the far side, so it can be pushed back out
    for k in range(len(PLAIN)):
        panel, pg = tab_panel(p, 10, "S")
        items.append(Item(f"solid_tab_{k}", Piece(panel + tab(5, 0, tab_w, L, tw, p.lead_in), [], pg)))
        panel, pg = tab_panel(p, 10, "P")
        slit = box(5 - 0.5, 5 + 0.5, -L - EPS, 2.0, -EPS, tw + EPS)
        items.append(Item(f"split_tab_{k}",
                          Piece(panel + tab(5, 0, tab_w, L, tw, p.lead_in) - slit, [], pg)))
    return items


def multi_peg_row(p):
    """Three pegs in a row, tight everywhere (M1) vs one locator + two floaters (M2)."""
    tw, c, fc, plate_t, tab_w = p.wall_thickness, p.clearance, p.float_clearance, 3.0, 5.0
    width = PEGS[-1] + PEGS[0]
    items = []
    for name, floats in (("M1", False), ("M2", True)):
        body = box(0, width, 0, STRIP_D, 0, plate_t)
        ribs = []
        for i, x in enumerate(PEGS):
            cx = fc if floats and i else c
            cut, r = socket(x, STRIP_D / 2, tab_w + 2 * cx, tw + 2 * c, 0, plate_t, p, ribs="y")
            body -= cut
            ribs += r
        for x in ((PEGS[0] + PEGS[1]) / 2, (PEGS[1] + PEGS[2]) / 2):
            body += label(name, x, STRIP_D / 2, plate_t, p, size=2.5)
        items.append(Item(f"multi_strip_{name}", Piece(body, ribs, [(width / 2, 0, "-y")])))
    panel, pg = tab_panel(p, width, "M")
    for x in PEGS:
        panel += tab(x, 0, tab_w, plate_t - 0.2, tw, p.lead_in)
    items.append(Item("multi_tab", Piece(panel, [], pg)))
    return items


def keyed_row(p):
    tw, c, plate_t = p.wall_thickness, p.clearance, 3.0
    (wa, wb), xa, xb = p.facade_tab_widths, 8.0, 24.0
    body = box(0, 32, 0, STRIP_D, 0, plate_t)
    ribs = []
    for x, w in ((xa, wa), (xb, wb)):
        cut, r = socket(x, STRIP_D / 2, w + 2 * c, tw + 2 * c, 0, plate_t, p, ribs="y")
        body -= cut
        ribs += r
    body += label("KEY", 16, STRIP_D / 2, plate_t, p, size=2.5)
    panel, pg = tab_panel(p, 32, "KEY")
    for x, w in ((xa, wa), (xb, wb)):
        panel += tab(x, 0, w, plate_t - 0.2, tw, p.lead_in)
    return [Item("keyed_strip", Piece(body, ribs, [(16, 0, "-y")])),
            Item("keyed_tab", Piece(panel, [], pg))]


def build(p):
    items = []
    for h in DETENTS:
        items += detent_row(p, h)
    items += rib_row(p) + solid_split_row(p) + multi_peg_row(p) + keyed_row(p)
    return items


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    ap.add_argument("--out", default="out", type=Path)
    args = ap.parse_args(argv)
    p = with_overrides(DEFAULT, args.set)
    args.out.mkdir(parents=True, exist_ok=True)

    s = layout(build(p), p)
    plate = s.solid()
    errors, lines = verify(s, p)
    errors += checks.connectivity([("coupon plate", plate)])
    for line in lines + errors:
        print("  " + line)
    render.export_mesh(plate, args.out / "coupon")
    render.projection(plate, args.out / "coupon_top.svg", "top", hidden=False)
    render.projection(plate, args.out / "coupon_iso.svg", "iso", hidden=False)
    print(f"  wrote {args.out}/coupon.3mf, coupon.stl, coupon_top/iso.svg (+ .png)")
    print("FAILED" if errors else "OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
