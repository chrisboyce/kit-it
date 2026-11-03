# PrintableColfax — HO storefront kit PoC

A proof of concept for designing 3D-printable HO-scale (1:87.1) "nook"
storefronts as **snap-together kits printed flat on a sprue**, in Python with
[build123d](https://github.com/gumyr/build123d). One generic storefront, plus
a snap-fit test coupon.

![built](out/built_color_iso.png)

## Run it

```sh
nix develop          # first time: creates .venv and pip-installs ~1 GB of OCP wheels
just                 # = just both coupon  -> everything into ./out
```

| command | output |
|---|---|
| `just built` | interference check + `out/built_{iso,front,top}.{svg,png}` |
| `just print` | sprue + color checks, `out/kit.3mf` (4-color), `out/kit.stl`, `out/kit_T*_*.stl`, `out/plate_{top,color}.png` |
| `just both`  | both of the above + `out/both_iso.png` (model beside its plate) |
| `just coupon`| `out/coupon.3mf`, `out/coupon.stl`, `out/coupon_{top,iso}.png` |
| `just viewer`| browser OCP viewer on :3939 |
| `just show`  | checks + send the kit to the viewer, no file output |

**Viewer order matters:** run `just viewer`, open
http://127.0.0.1:3939/viewer in a browser, *then* `just show` (or any
`view.py` run). The standalone viewer forwards each model to the browser tab
that is open at that moment and keeps nothing for tabs opened later, so a tab
opened afterwards only shows the OCP logo. Reloading the tab also clears it;
just re-run `just show`.

`just` works from a plain shell too (it wraps itself in `nix develop`). Every
script runs headless; if VS Code's *OCP CAD Viewer* or `just viewer` is
listening on port 3939 the model is shown there as well. Exit status is
nonzero on any collision, sprue problem, or disconnected part.

## Environment: what and why

**flake dev shell + venv + pinned PyPI wheels.** build123d, OCP and
ocp_vscode are not in nixpkgs (cadquery was dropped as broken), and building
OCP/OCCT from source is hours of compiling for a PoC. The manylinux wheels
load fine through Nix's Python as long as five shared libraries are findable,
found by running `ldd` over every `.so` in the wheels:
`libstdc++ zlib expat libX11 libGL`. `flake.nix` puts exactly those on
`LD_LIBRARY_PATH` (no system-wide nix-ld needed), and also provides `just`,
`rsvg-convert` (SVG → PNG) and a pinned DejaVu font so embossed labels come out
identical everywhere. Python deps are pinned in `requirements.txt`.

## Layout

| file | role |
|---|---|
| `params.py` | every dimension and fit value. `ft()`/`inch()` for scale sizes; printer values in mm; `zq()` snaps Z heights to whole layers |
| `joints.py` | tab, socket (+ lead-in, crush ribs), barb tab, `Piece` |
| `parts.py` | one function per part → `Piece` in its print frame (bed face at Z=0) |
| `registry.py` | the part list: number, name, part function, **built pose** |
| `sprue.py` | **print pose**: shelf layout, rails, gates with snap notches, label pads, checks |
| `checks.py` | pairwise interference, part connectivity, feature-size warnings |
| `view.py` | `--mode built\|print\|both` entry point |
| `coupon.py` | the snap-fit test coupon |

Poses are written as `Plane(origin, x_dir, z_dir)` ("the part's local x goes
along x_dir, the face that was on the bed faces z_dir"), which reads much better
than Euler angles. Identical parts (the two returns) share one
function and are built once.

## Changing fit and dimensions

Edit `params.py`, or override any value for one run:

```sh
just both --set facade_width='ft(30)' --set clearance=0.2
just coupon --set rib_height=0.25
```

Fit knobs: `clearance` (per side), `rib_height`, `float_clearance`,
`prop_clearance`, `rib_base`, `lead_in`, `detent_height`, `facade_tab_widths`
(keep them different: that's the keying), `return_tab_width`. Tab *thickness* is always
the thickness of the part the tab is on (`wall_thickness`/`prop_thickness`),
because tabs are part of a flat part's outline.

## Color (4 toolheads)

The kit prints in up to `max_tools` = 4 filaments (Snapmaker U1). The palette
and every assignment are in `params.py`:

| tool | name | default use |
|---|---|---|
| T1 | brick | facade, returns |
| T2 | trim | window frames + transoms, cornice, coping, sprue labels |
| T3 | concrete | base, planter boxes, sprue rails/gates |
| T4 | accent | sign band, door, shrubs |

```sh
just both --set color_door=trim          # reassign one thing
```
Edit `palette` to rename or recolor a filament. The hex values only drive the
previews; the printer uses whatever is loaded in that tool.

**How it's modeled:** geometry is unchanged. Each part has a base color plus
*paint volumes* (`Piece.paints`): the window frames are trim, and so on. A
part's color regions are its body intersected with the paints, with later paints
winning, so they tile the part exactly and the joints and checks don't care.
Raised face features also color `color_depth` (0.6 mm) of the material under
them, so cream trim over red brick isn't just two translucent layers. On the
planter, the color split is in the outline, so every layer has both colors.
That's no problem on a toolchanger.

**Checks:** the color regions must tile the plate exactly (no overlap, no gap,
which `color_partition` checks), and the plate may use at most `max_tools`
colors.

**Slicing on the U1:** open `out/kit.3mf`. It loads as **one object with four
parts** named `T1 brick`, `T2 trim`, `T3 concrete` and `T4 accent`. In the
object list, set each part's filament to its tool number (four clicks), then
save as a project if you'll reprint it. Prefer the 3MF over the per-color STLs:
when OrcaSlicer combines separate STLs into one object it can re-center each
file, and the colors no longer line up.

Why it isn't automatic yet (tested headless against OrcaSlicer 2.4.2, the base
of Snapmaker Orca, with its Snapmaker U1 profile):
* Orca honors per-part extruder settings only inside its own project 3MF.
  For any other 3MF it logs "3mf from other vendor" and ignores them. Its
  project format also requires an embedded full printer/process config
  (`project_settings.config`); without one the CLI segfaults.
* The PrusaSlicer-style per-volume extruder config loads but is ignored too.
* 3MF color groups are read, but the CLI doesn't map them to filaments. The
  GUI may offer a color-mapping dialog; that's untested.
* The Orca CLI also segfaults with 4 filaments on the U1 profile, even for
  plain STLs, so a full 4-color U1 slice couldn't be run headless.
* Likely fix: save one real project from Snapmaker Orca (U1 + your 4
  filaments) and use its `project_settings.config` as a template, so
  `kit.3mf` opens as a native project with tools pre-assigned.

## The joints

Rule: **every precision feature is in the XY outline of the part it's on**
(accurate to about a nozzle width), never a Z feature (quantized to 0.2 mm
layers).

* **Keyed tab + socket with crush ribs** (all wall-to-base and return-to-facade
  joints). Small triangular ribs on the socket walls run along the insertion
  direction and squash as the tab goes in. The facade's two tabs are different
  widths, so it only goes in facing the street.
* **One locator per direction.** Ribs only press across a wall's thickness.
  Along the wall, exactly one socket fixes the part, and every other socket
  has `float_clearance` (0.4 mm) of room per side that way:
  * facade: the narrow (left) tab locates it in x; the wide tab floats in x.
  * returns: they're located front-to-back by their shoulder on the facade back
    and in height by standing on the base, so their base socket floats in y
    and the facade pockets float in height.

  Two tight pegs per part is fine, but three or more tight ones fight each
  other: any spacing error (shrink, warp, slicer rounding) has to be forced in,
  and the joint loosens with every assembly. Floating the extras removes that
  fight without losing grip, because the grip is in the other direction.
* **Cross-lap prop.** Two flat planter silhouettes slot into an X; piece A tabs
  into a pocket in the sidewalk. Plain friction at `prop_clearance` (0.10), no ribs.
* **Detent barbs** are on the coupon only (see rough edges).

Assembly: push the returns into the facade's back pockets, press that
subassembly into the base, put the planter together and press it in.

## Tuning from prints

First print (Snapmaker U1, PLA, 0.2 mm): the original kit (0.15 clearance +
0.25 ribs, i.e. 0.10 mm squeeze per side, plus wedge keys) was very tight, and
the keyed joint held so well that the wedge keys were unnecessary. On the
coupon, a split D10 tab slides with slight friction at 0.15 and is a nice firm
hold at 0.10. So the printer is accurate, and there's no need to squeeze
plastic hard. Changes from that:
* wedge keys, their windows and the base's key channel removed (2 fewer parts)
* base 5.0 → 3.6 mm (no channel to fit)
* `rib_height` 0.25 → 0.20 (squeeze 0.05 per side)
* props get their own `prop_clearance` = 0.10 with no ribs
* float sockets (above)

**Reading the coupon:** squeeze ≈ `rib_height` − `clearance`. Find your bare
clearance with the D/SP rows (smallest slot that slides with slight friction),
your favourite squeeze with the R row, then set
`rib_height = clearance + squeeze`. Kit sockets are deeper than the coupon
strips (3.6 vs 3 mm), so the kit feels a little tighter; if torn, pick the looser.

## What was verified (in this session)

* **Clean build:** `just` builds everything with exit 0. Check A finds 0
  collisions over 15 pairs. Check B shows all 16 crush ribs overlapping
  their mating part. Both plates fit: kit 154 × 142 mm, coupon 199 × 102 mm
  on a 220 bed. (Before the wedge removal: 28 pairs, 18 ribs, kit 178 × 153.)
* **The check catches real collisions:** `--set clearance=-0.10` gives 5
  collisions (base×facade, base×returns, facade×returns) and exit 1. The props
  use `prop_clearance`, so they don't react to that override.
* **Keying:** placing the facade turned 180° (facing backwards) gave a
  base×facade collision of 7.4 mm³ (checked before the float sockets; the wide
  tab still can't enter the narrow locating socket, so it should still hold).
* **Everything propagates:** I set `facade_width` 25 → 30 ft and
  `wall_thickness` 3.0 → 2.4 mm and rebuilt. The base and facade widened to
  105 mm, the right return moved to x = 101.6, the returns thinned to 2.4 mm,
  the tabs, sockets and keys moved to their new positions, the base got 0.6 mm
  shallower, and the plate repacked from 178 to 195 mm wide. All checks still
  passed. Restored afterwards.
* **Projections:** I looked at every PNG in both modes: hidden-line sockets
  in the right places, relief face-up on the plate, gates only on hidden edges.
* **A bug the checks didn't catch at first:** the crush ribs were modeled
  0.01 mm off their walls (a sign error). They were floating solids that still
  "gripped" their mates in check B. The coupon's fused plate came out as 15
  solids, which gave it away. Fixed, and `checks.connectivity()` now fails the
  build if any part or plate isn't exactly one solid.

* **Color:** 4 colors, and the regions sum to exactly the plate's volume
  (36 578.2 mm³) with 0 overlaps. The previews (`built_color_iso.png`,
  `plate_color.png`) show the expected assignment. Snapmaker Orca's U1
  profile loaded the pre-wedge-removal `kit.3mf` as one object with 4 parts
  and sliced it (single filament: 36.7 g, about 2 h 25 m).
* **Printed:** the first kit and coupon (see "Tuning from prints"). The
  current fits, float sockets and the SP/M coupon rows are not printed yet.

## Rough edges

**Snap-fit reliability at this scale.** A classic detent snaps by flexing.
With a 3 mm split prong, 0.8 mm wide, deflecting 0.15 mm, the bending strain
is about 2%, which is at PLA's limit for one assembly and above it for repeated
use. In practice a detent this small behaves like a friction fit that crushes a
little plastic. That's why the kit uses crush ribs, and detents
only appear on the coupon. Unknowns only a print will answer:
* how a slicer renders a 0.25 mm × 0.8 mm triangular rib (well below one
  extrusion width): it may become a slight bulge or vanish
* whether the 1.4 mm deep return pockets grip well enough
* elephant's foot: it narrows the bottom of every through-slot, and that's
  exactly where the detent barbs catch. Turn on your slicer's elephant-foot
  compensation.

**Gate placement.** Gate positions are chosen by hand per part, as
(x, y, ±y) points on edges that end up hidden. Gates only run straight in ±Y to
the rail above or below. That's simple and predictable, but a new part with no
suitable bottom or top edge would need rotating in the layout, which isn't
supported.

**Layout packing.** The packer is a plain shelf packer, tallest part first,
with no rotation. That's fine at 154 × 142 mm, but a bigger building will
need smarter packing or a second plate.

**Relief detail vs nozzle size.**
* Frames and transom bars are 0.8 mm (two extrusion widths).
* Raised relief is 0.4–0.8 mm (2–4 layers).
* Label text is 3 mm DejaVu Bold, with strokes of about 0.5 mm.
* The coupon's 2.2 mm slot labels are marginal.
* The `min_feature` check covers the feature sizes declared in `params.py`,
  not arbitrary geometry. A general thin-wall analysis of B-rep solids is a
  project of its own.
* The base is 3.6 mm thick (about 1 ft at scale), so it still reads a bit
  like a display plinth.

**build123d / environment gotchas.**
* `extrude()` follows the outline's winding: a clockwise polygon extrudes
  toward −Z. Every extrude here passes `dir=UP`.
* `a.intersect(b)` returns a `ShapeList`; `a & b` and summing `.volume` over
  `.solids()` is the reliable way to get an overlap volume.
* Fusing parts one at a time is slow. Fusing the 25-part coupon that way took
  51 s; a single `a.fuse(*others)` takes 2.5 s.
* `ocp_vscode.show()` silently does nothing when no viewer is running, so
  `view.py` checks the port itself.
* ocp_vscode 4.x moved the standalone viewer into the separate `ocp_viewer`
  package.
* Run times: the kit takes about 25 s and the coupon about 80 s, mostly
  booleans, the sprue checks and hidden-line projection.

**Color previews** use a small numpy z-buffer rasterizer in `render.py`
(`color_preview`). matplotlib's 3D plotting sorts whole triangles by depth and
drew the long facade triangles in the wrong order.

## Not done yet

* Awning with posts (deferred; the cross-lap prop proves the construction for
  the post).
* Real Colfax facades.
* Pre-assigned toolheads in the 3MF (needs a Snapmaker Orca project as a template).
* 8-color kits split across two plates.
* Layered/laminated facades.
