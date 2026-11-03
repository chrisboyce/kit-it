"""Build the kit and look at it, assembled (built) or on its sprue (print).

    python view.py --mode built|print|both [--set name=value ...] [--out out]

Headless it writes SVG/PNG projections (and 3MF/STL in print mode) to --out.
If an OCP viewer is listening (VS Code's OCP CAD Viewer, or `just viewer`),
the model is also shown there.

Exit status is nonzero if the interference check (built) or the sprue
verification (print) finds a problem.
"""

import argparse
import sys
import time
from pathlib import Path

from build123d import Compound, Pos

import checks
import registry
import render
from params import DEFAULT, with_overrides
from sprue import Item, layout, verify


def assemble(kit, p):
    """[(name, world nominal, [world extras], world body)] in built poses."""
    out = []
    for spec, piece in kit:
        loc = spec.built(p)
        out.append((spec.name, loc * piece.nominal, [loc * e for e in piece.extras],
                    loc * piece.body))
    return out


def run_built(kit, p, out: Path, export=True):
    placed = assemble(kit, p)
    errors, lines = checks.interference([(n, nom, ex) for n, nom, ex, _ in placed])
    errors += checks.connectivity([(n, body) for n, *_, body in placed])
    for line in lines + errors:
        print("  " + line)
    model = Compound([body for *_, body in placed])
    for view in ("iso", "front", "top") if export else ():
        f = render.projection(model, out / f"built_{view}.svg", view)
        print(f"  wrote {f} (+ .png)")
    return model, [n for n, *_ in placed], [b for *_, b in placed], bool(errors)


def run_print(kit, p, out: Path, export=True):
    items = [Item(spec.name, piece, str(spec.num)) for spec, piece in kit]
    s = layout(items, p)
    plate = s.solid()
    errors, lines = verify(s, p)
    errors += checks.connectivity([("sprue plate", plate)])
    for line in lines + errors:
        print("  " + line)
    if export:
        render.export_mesh(plate, out / "kit")
        print(f"  wrote {out / 'kit.3mf'}, {out / 'kit.stl'}")
        f = render.projection(plate, out / "plate_top.svg", "top", hidden=False)
        print(f"  wrote {f} (+ .png)")
    return plate, bool(errors)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["built", "print", "both"], default="built")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="override a param, e.g. --set facade_width=ft(30)")
    ap.add_argument("--out", default="out", type=Path)
    ap.add_argument("--no-viewer", action="store_true", help="don't send to an OCP viewer")
    ap.add_argument("--no-export", action="store_true",
                    help="skip SVG/PNG/3MF/STL output (fast path for the viewer)")
    args = ap.parse_args(argv)

    p = with_overrides(DEFAULT, args.set)
    args.out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("feature sizes:")
    for line in checks.feature_report(p) or ["all declared features >= min_feature"]:
        print("  " + line)

    kit = registry.build(p)
    failed = False
    shown, names = [], []

    if args.mode in ("built", "both"):
        print("built:")
        model, part_names, bodies, bad = run_built(kit, p, args.out, not args.no_export)
        failed |= bad
        shown += bodies
        names += part_names

    if args.mode in ("print", "both"):
        print("print:")
        plate, bad = run_print(kit, p, args.out, not args.no_export)
        failed |= bad
        if args.mode == "both":
            # Put the plate beside the assembled model, lying flat.
            plate = Pos(model.bounding_box().max.X + 25, 0, 0) * plate
        if args.mode == "both" and not args.no_export:
            f = render.projection(Compound([model, plate]), args.out / "both_iso.svg", "iso",
                                  hidden=False)
            print(f"  wrote {f} (+ .png)")
        shown.append(plate)
        names.append("sprue")

    if not args.no_viewer and render.viewer_available():
        render.show(shown, names)
        print(f"sent {len(shown)} objects to the OCP viewer on :{render.VIEWER_PORT}.\n"
              f"  Still seeing the logo? The viewer only draws into a browser tab that was\n"
              f"  already open: open {render.VIEWER_URL} first, then re-run (`just show`).")

    print(f"{'FAILED' if failed else 'OK'} in {time.time() - t0:.1f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
