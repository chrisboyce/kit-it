"""Build the kit and look at it, assembled (built) or on its sprue (print).

    python view.py [--kit nook|corner|market|caboose|all] --mode built|print|both
                   [--set name=value ...] [--out DIR]

Headless it writes SVG/PNG projections, shaded color previews, and (print
mode) a multi-material 3MF plus STLs per plate to --out (default out/, or
out/<kit>/ for kits other than the nook). If an OCP viewer is listening
(VS Code's OCP CAD Viewer, or `just viewer` with its page open), the model is
also shown there, in color.

Exit status is nonzero if the interference check (built) or the sprue
verification (print) finds a problem.

If nothing has changed since the last passing build, it isn't repeated: the saved result
goes straight to the viewer (viewcache.py). --rebuild forces a fresh build.

--kit all shows every kit together at true relative scale, one row per kit, each with its
assembled model followed by its plates. Unless --no-export is given, it also renders that
scene to out/showcase_color.png.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from dataclasses import replace

from build123d import Compound, Pos

import checks
import caboose
import corner
import market
import registry
import render
import viewcache
from params import DEFAULT, with_overrides
from sprue import Item, assign, layout, paginate, verify

# name: (default params, part list, assembled views to draw, plates or None to paginate)
KITS = {
    "nook": (DEFAULT, registry.REGISTRY, ("iso", "front", "top"), None),
    "corner": (corner.DEFAULT, corner.REGISTRY, ("corner", "front", "right", "top"), corner.PLATES),
    "market": (market.DEFAULT, market.REGISTRY, ("corner", "front", "right", "top"), market.PLATES),
    "caboose": (caboose.DEFAULT, caboose.REGISTRY, ("corner", "front", "right", "top"), caboose.PLATES),
}
SHOWCASE = ("caboose", "nook", "market", "corner")      # front row to back, so small kits aren't hidden
SHOWCASE_GAP = 60.0                                     # mm between rows


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


def run_plate(items, p, out: Path, stem: str, export=True, tools=None):
    """One sprue plate; tools is the color in T1, T2, ... (default: the palette).
    Returns (solid, [(name, solid, hex)], failed)."""
    s = layout(items, p)
    plate = s.solid()
    errors, lines = verify(s, p)
    errors += checks.connectivity([(f"{stem} plate", plate)])
    e, l = checks.overhangs([(it.name, it.piece.body) for it in items], p)
    errors += e
    lines += l

    by_color = s.color_solids(p)
    loaded = list(tools or [n for n, _ in p.palette])[:p.max_tools]
    missing = sorted(set(by_color) - set(loaded))
    if missing:
        errors.append(f"COLORS NOT LOADED: {', '.join(missing)} (tools: {', '.join(loaded)})")
    tools = sorted((loaded.index(c) + 1, c) for c in by_color if c in loaded)
    lines.append("colors: " + ", ".join(f"T{t} {c}" for t, c in tools))
    e, l = checks.color_partition(plate, by_color)
    errors += e
    lines += l
    for line in lines + errors:
        print("  " + line)

    regions = [(c, t, p.hex(c), by_color[c]) for t, c in tools]
    if export:
        render.export_color_3mf(regions, out / f"{stem}.3mf", [p.hex(c) for c in loaded],
                                (p.bed_x, p.bed_y), object_name=stem)
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


def run_print(kit, p, out: Path, export=True, named=None):
    """named: [sprue.Plate], or None to paginate by size.
    Returns ([plate solids], [(name, solid, hex) per plate], failed)."""
    items = [Item(spec.name, piece, str(spec.num)) for spec, piece in kit]
    plates = assign(items, named) if named else paginate(items, p)
    solids, regions, failed = [], [], False
    for n, group in enumerate(plates, 1):
        spec = named[n - 1] if named else None
        stem = "kit" if len(plates) == 1 else f"kit_plate{n}" + (f"_{spec.name}" if spec else "")
        print(f" {stem}: {', '.join(it.label for it in group)}")
        pp = replace(p, color_sprue=spec.sprue, color_label=spec.label) if spec else p
        plate, reg, bad = run_plate(group, pp, out, stem, export, spec.tools if spec else None)
        solids.append(plate)
        regions.append(reg)
        failed |= bad
    return solids, regions, failed


def _send(shown, no_viewer):
    if no_viewer or not shown or not render.viewer_available():
        return
    render.show([s for _, s, _ in shown], [n for n, _, _ in shown], [h for _, _, h in shown])
    print(f"sent {len(shown)} objects to the OCP viewer on :{render.VIEWER_PORT}.\n"
          f"  Still seeing the logo? The viewer only draws into a browser tab that was\n"
          f"  already open: open {render.VIEWER_URL} first, then re-run (`just show`).")


def default_out(name):
    return Path("out") if name == "nook" else Path("out") / name


def run_kit(name, mode, overrides, out, export, rebuild):
    """Build and check one kit, or reuse its last passing build.
    Returns ([(name, solid, hex)] for the viewer, failed)."""
    defaults, specs, views, named = KITS[name]
    p = with_overrides(defaults, overrides)
    if out is None:
        out = default_out(name)
    out.mkdir(parents=True, exist_ok=True)

    key = viewcache.fingerprint(name, mode, p)
    if not rebuild:
        shown = viewcache.load(out, mode, key, export)
        if shown is not None:
            print("Nothing has changed since the last passing build (--rebuild to build it again).")
            return shown, False

    print("feature sizes:")
    for line in checks.feature_report(p) or ["all declared features >= min_feature"]:
        print("  " + line)

    kit = registry.build(p, specs)
    failed = False
    shown = []   # [(name, solid, hex)] for the viewer

    if mode in ("built", "both"):
        print("built:")
        model, regions, bad = run_built(kit, p, out, export, views)
        failed |= bad
        shown += regions

    if mode in ("print", "both"):
        print("print:")
        plates, plate_regions, bad = run_print(kit, p, out, export, named)
        failed |= bad
        # Beside the assembled model (if there is one), lying flat, in a row.
        x = model.bounding_box().max.X + 25 if mode == "both" else 0.0
        placed = []
        for plate, regions in zip(plates, plate_regions):
            shift = Pos(x - plate.bounding_box().min.X, 0, 0)
            shown += [(n, shift * s, h) for n, s, h in regions]
            placed.append(shift * plate)
            x = placed[-1].bounding_box().max.X + 15
        if mode == "both" and export:
            f = render.projection(Compound([model, *placed]), out / "both_iso.svg", "iso", hidden=False)
            print(f"  wrote {f} (+ .png)")

    if not failed:
        viewcache.save(out, mode, key, shown, export)
    return shown, failed


def showcase_scene(name, mode, export, rebuild):
    """A kit's saved build, building it first if needed. Each build gets its own process,
    so a crash costs one kit rather than the whole showcase, and a big kit's memory is
    freed before the next one starts.
    Returns the shown list, or None if the kit didn't pass."""
    def saved():
        key = viewcache.fingerprint(name, mode, KITS[name][0])
        return viewcache.load(default_out(name), mode, key, export)

    shown = None if rebuild else saved()
    if shown is not None:
        print("Nothing has changed since the last passing build.")
        return shown
    flags = ["--no-viewer"] + ["--no-export"] * (not export) + ["--rebuild"] * rebuild
    cmd = [sys.executable, "-X", "faulthandler", __file__, "--kit", name, "--mode", mode, *flags]
    code = subprocess.run(cmd).returncode
    if code != 0:
        print(f"{name} FAILED (exit status {code}), so it's left out")
        return None
    return saved()


def stack_rows(scenes):
    """One row per (kit name, shown), left edges aligned, front row first."""
    out, y = [], 0.0
    for name, shown in scenes:
        boxes = [s.bounding_box() for _, s, _ in shown]
        y0 = min(b.min.Y for b in boxes)
        shift = Pos(-min(b.min.X for b in boxes), y - y0, 0)
        out += [(f"{name}: {n}", shift * s, h) for n, s, h in shown]
        y += max(b.max.Y for b in boxes) - y0 + SHOWCASE_GAP
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["built", "print", "both"], default="built")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="override a param, e.g. --set facade_width=ft(30)")
    ap.add_argument("--kit", choices=[*KITS, "all"], default="nook")
    ap.add_argument("--out", default=None, type=Path)
    ap.add_argument("--no-viewer", action="store_true", help="don't send to an OCP viewer")
    ap.add_argument("--no-export", action="store_true",
                    help="skip SVG/PNG/3MF/STL output (fast path for the viewer)")
    ap.add_argument("--rebuild", action="store_true", help="build and check even if nothing has changed")
    args = ap.parse_args(argv)
    if args.kit == "all" and (args.set or args.out):
        ap.error("--kit all uses each kit's own parameters and folder, so it can't take --set or --out")

    t0 = time.time()
    export = not args.no_export

    if args.kit == "all":
        scenes, failed = [], False
        for name in SHOWCASE:
            print(f"== {name} ==")
            shown = showcase_scene(name, args.mode, export, args.rebuild)
            if shown is None:
                failed = True
            else:
                scenes.append((name, shown))
        shown = stack_rows(scenes)
        if export and not failed:
            f = render.color_preview([(s, h) for _, s, h in shown], Path("out") / "showcase_color.png",
                                     "corner", width=2400, height=1400)
            print(f"wrote {f}")
    else:
        shown, failed = run_kit(args.kit, args.mode, args.set, args.out, export, args.rebuild)

    _send(shown, args.no_viewer)

    print(f"{'FAILED' if failed else 'OK'} in {time.time() - t0:.1f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
