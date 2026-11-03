"""Build the kit and look at it, assembled (built) or on its sprue (print).

    python view.py [--kit nook|corner] --mode built|print|both [--set name=value ...] [--out DIR]

Headless it writes SVG/PNG projections, shaded color previews, and (print
mode) a multi-material 3MF plus STLs per plate to --out (default out/, or
out/<kit>/ for kits other than the nook). If an OCP viewer is listening
(VS Code's OCP CAD Viewer, or `just viewer` with its page open), the model is
also shown there, in color.

Exit status is nonzero if the interference check (built) or the sprue
verification (print) finds a problem.
"""

import argparse
import sys
import time
from pathlib import Path

from build123d import Compound, Pos

import checks
import corner
import registry
import render
from params import DEFAULT, with_overrides
from sprue import Item, layout, paginate, verify

# name: (default params, part list, assembled views to draw)
KITS = {
    "nook": (DEFAULT, registry.REGISTRY, ("iso", "front", "top")),
    "corner": (corner.DEFAULT, corner.REGISTRY, ("corner", "front", "right", "top")),
}


def assemble(kit, p):
    """[(name, world nominal, [world extras], world body)] in built poses."""
    out = []
    for spec, piece in kit:
        loc = spec.built(p)
        out.append((spec.name, loc * piece.nominal, [loc * e for e in piece.extras],
                    loc * piece.body))
    return out


def colored(kit, p, pose_of):
    """[(name, solid, hex)] for every color region of every part."""
    out = []
    for spec, piece in kit:
        loc = pose_of(spec)
        for color, region in piece.regions().items():
            out.append((f"{spec.name} ({color})", loc * region, p.hex(color)))
    return out


def run_built(kit, p, out: Path, export=True, views=("iso", "front", "top")):
    placed = assemble(kit, p)
    errors, lines = checks.interference([(n, nom, ex) for n, nom, ex, _ in placed])
    errors += checks.connectivity([(n, body) for n, *_, body in placed])
    for line in lines + errors:
        print("  " + line)
    model = Compound([body for *_, body in placed])
    regions = colored(kit, p, lambda spec: spec.built(p))
    if export:
        for view in views:
            f = render.projection(model, out / f"built_{view}.svg", view)
            print(f"  wrote {f} (+ .png)")
        for view in views:
            if view != "top":
                f = render.color_preview([(s, h) for _, s, h in regions], out / f"built_color_{view}.png", view)
                print(f"  wrote {f}")
    return model, regions, bool(errors)


def run_plate(items, p, out: Path, stem: str, export=True):
    """One sprue plate. Returns (solid, [(name, solid, hex)], failed)."""
    s = layout(items, p)
    plate = s.solid()
    errors, lines = verify(s, p)
    errors += checks.connectivity([(f"{stem} plate", plate)])
    e, l = checks.overhangs([(it.name, it.piece.body) for it in items], p)
    errors += e
    lines += l

    by_color = s.color_solids(p)
    tools = sorted((p.tool(c), c) for c in by_color)
    lines.append("colors: " + ", ".join(f"T{t} {c}" for t, c in tools))
    if len(tools) > p.max_tools:
        errors.append(f"TOO MANY COLORS: {len(tools)} > max_tools {p.max_tools}")
    e, l = checks.color_partition(plate, by_color)
    errors += e
    lines += l
    for line in lines + errors:
        print("  " + line)

    regions = [(c, t, p.hex(c), by_color[c]) for t, c in tools]
    if export:
        render.export_color_3mf(regions, out / f"{stem}.3mf", object_name=stem)
        render.export_mesh(plate, out / stem, formats=("stl",))
        stls = render.export_color_stls(regions, out / stem)
        print(f"  wrote {out / (stem + '.3mf')} ({len(regions)} colors), {out / (stem + '.stl')}, "
              f"{len(stls)} per-color STLs")
        # A single plate keeps the plate_* names; several get <stem>_top / <stem>_color.
        top, col = ("plate_top", "plate_color") if stem == "kit" else (f"{stem}_top", f"{stem}_color")
        f = render.projection(plate, out / f"{top}.svg", "top", hidden=False)
        print(f"  wrote {f} (+ .png)")
        f = render.color_preview([(sol, h) for _, _, h, sol in regions], out / f"{col}.png", "top")
        print(f"  wrote {f}")
    return plate, [(f"{stem} T{t} {c}", sol, h) for c, t, h, sol in regions], bool(errors)


def run_print(kit, p, out: Path, export=True):
    """Returns ([plate solids], [(name, solid, hex) per plate], failed)."""
    items = [Item(spec.name, piece, str(spec.num)) for spec, piece in kit]
    plates = paginate(items, p)
    solids, regions, failed = [], [], False
    for n, group in enumerate(plates, 1):
        stem = "kit" if len(plates) == 1 else f"kit_plate{n}"
        print(f" {stem}: {', '.join(it.label for it in group)}")
        plate, reg, bad = run_plate(group, p, out, stem, export)
        solids.append(plate)
        regions.append(reg)
        failed |= bad
    return solids, regions, failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["built", "print", "both"], default="built")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="override a param, e.g. --set facade_width=ft(30)")
    ap.add_argument("--kit", choices=list(KITS), default="nook")
    ap.add_argument("--out", default=None, type=Path)
    ap.add_argument("--no-viewer", action="store_true", help="don't send to an OCP viewer")
    ap.add_argument("--no-export", action="store_true",
                    help="skip SVG/PNG/3MF/STL output (fast path for the viewer)")
    args = ap.parse_args(argv)

    defaults, specs, views = KITS[args.kit]
    p = with_overrides(defaults, args.set)
    if args.out is None:
        args.out = Path("out") if args.kit == "nook" else Path("out") / args.kit
    args.out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    export = not args.no_export

    print("feature sizes:")
    for line in checks.feature_report(p) or ["all declared features >= min_feature"]:
        print("  " + line)

    kit = registry.build(p, specs)
    failed = False
    shown = []   # [(name, solid, hex)] for the viewer

    if args.mode in ("built", "both"):
        print("built:")
        model, regions, bad = run_built(kit, p, args.out, export, views)
        failed |= bad
        shown += regions

    if args.mode in ("print", "both"):
        print("print:")
        plates, plate_regions, bad = run_print(kit, p, args.out, export)
        failed |= bad
        # Beside the assembled model (if there is one), lying flat, in a row.
        x = model.bounding_box().max.X + 25 if args.mode == "both" else 0.0
        placed = []
        for plate, regions in zip(plates, plate_regions):
            shift = Pos(x - plate.bounding_box().min.X, 0, 0)
            shown += [(n, shift * s, h) for n, s, h in regions]
            placed.append(shift * plate)
            x = placed[-1].bounding_box().max.X + 15
        if args.mode == "both" and export:
            f = render.projection(Compound([model, *placed]), args.out / "both_iso.svg", "iso", hidden=False)
            print(f"  wrote {f} (+ .png)")

    if not args.no_viewer and render.viewer_available():
        render.show([s for _, s, _ in shown], [n for n, _, _ in shown], [h for _, _, h in shown])
        print(f"sent {len(shown)} objects to the OCP viewer on :{render.VIEWER_PORT}.\n"
              f"  Still seeing the logo? The viewer only draws into a browser tab that was\n"
              f"  already open: open {render.VIEWER_URL} first, then re-run (`just show`).")

    print(f"{'FAILED' if failed else 'OK'} in {time.time() - t0:.1f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
