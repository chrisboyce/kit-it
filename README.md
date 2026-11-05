# PrintableColfax: HO snap-together kits from Street View

3D-printable HO-scale (1:87.1) models of real buildings and objects, designed as
**snap-together kits printed flat on a sprue** in Python with
[build123d](https://github.com/gumyr/build123d). Each kit is checked before it's
exported: parts don't collide, every plate fits the bed and the toolheads, and
nothing overhangs. Plates come out as multi-color 3MFs, ready to slice.

So far there are three kits of landmarks in Colfax, California:
[Creative Corner](#creative-corner-kit), the [Colfax Market](#colfax-market-kit)
and the [caboose](#colfax-caboose-kit). There's also a generic storefront and a
snap-fit test coupon for tuning the fit to your printer.

Run `just` to generate the renders this README refers to, into `out/`.

## Make your own kit

The workflow from a photo to a kit is written down as a
[Claude Code](https://claude.com/claude-code) skill:
[`.claude/skills/streetview-kit/`](.claude/skills/streetview-kit/SKILL.md). Open
this repo in Claude Code, paste a Google Maps / Street View link, and ask for a
kit. The skill gathers reference views, writes a design brief, models the kit
in passes, and won't call it done until every check passes.

You can follow it by hand too. What to read:

* [`SKILL.md`](.claude/skills/streetview-kit/SKILL.md): the steps, from views to brief to model to plates
* [`references/kit-design.md`](.claude/skills/streetview-kit/references/kit-design.md):
  the design rules that real prints taught (joints, bed fitting, color, mistakes already made)
* `market.py` (small building), `corner.py` (showcase building), `caboose.py` (an object)
  are the worked examples. New kits subclass `CornerParams` and reuse its helpers.

Before printing any kit, **print the coupon and tune the fits** (see
[Tuning from prints](#tuning-from-prints)), because your printer won't match this one.

### Adapting to your printer

Everything was designed for a Snapmaker U1: four toolheads, 0.4 mm nozzle, PLA at
0.2 mm layers, no supports. The printer's limits are all in `params.py`:

| field | what it is |
|---|---|
| `bed_x`, `bed_y`, `bed_margin` | printable area. Parts and plates have to fit inside it |
| `max_tools` | filaments per plate. Fewer tools means changing a kit's `palette` and plates to match (not tried) |
| `nozzle`, `print_layer_height`, `min_feature` | what's thin enough to print |
| `max_bridge` | the longest span with nothing under it |
| `clearance`, `rib_height`, `float_clearance`, `prop_clearance`, `split_clearance` | the fits. Set these from the coupon |

The 3MF export is written as a Bambu Studio-style project, so it opens in Orca,
Bambu Studio and their forks with each part already on its own filament (see
"Slicing on the U1"). Only Snapmaker Orca has been tested.

### Reference images and names

`streetview.py` fetches images from undocumented Google Maps endpoints. They aren't a
licensed source, and they can stop working. The skill keeps images out of the repo
and fetches only what a design needs, so keep it that way. Real business names and
railroad marks on a kit may be someone's trademark. Check before you sell or widely
distribute a kit that carries them.

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
| `just corner`| the Creative Corner kit, built + 5 plates, into `out/corner/` (~13 min) |
| `just market`| the Colfax Market kit, built + 3 plates, into `out/market/` (~3 min) |
| `just caboose`| the Colfax caboose kit, built + 2 plates, into `out/caboose/` (~5 min) |
| `just coupon`| `out/coupon.3mf`, `out/coupon.stl`, `out/coupon_{top,iso}.png` |
| `just viewer`| browser OCP viewer on :3939 |
| `just show`  | checks + send the kit to the viewer, no file output |
| `just showcase` | every kit together in the viewer, one row each: assembled model, then its plates |
| `just both --kit all` | every kit's files, plus that scene as `out/showcase_color.png` |

**Showing a kit again is instant.** A passing build saves what the viewer needs in `out/<kit>/.cache/`,
so while the source and parameters are unchanged, `view.py` skips the build and sends that
(`viewcache.py`). It's safe but coarse: editing any `.py` file means a rebuild, even one the kit doesn't
use. Failed builds aren't saved. A run that wants exports only reuses a build that wrote them, so
`just corner` still rebuilds after `just show`. `--rebuild` forces a fresh build; `just clean` clears it all.

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

**Without Nix** (untested): on an ordinary Linux or macOS machine the wheels find
their libraries on their own. Use Python 3.12, `python -m venv .venv`,
`source .venv/bin/activate` and `pip install -r requirements.txt`. Then install
`just` and `rsvg-convert` (librsvg), and point `COLFAX_FONT` at a copy of
`DejaVuSans-Bold.ttf`. In that shell, `just` runs plain `python` rather than
wrapping itself in `nix develop`, as long as you set `IN_NIX_SHELL=1`.

## Layout

| file | role |
|---|---|
| `corner.py`, `market.py`, `caboose.py` | the kits: params, parts, poses, plates. New ones come from the `streetview-kit` skill |
| `viewcache.py` | reuses a kit's last passing build while nothing has changed |
| `vary.py` | seeded randomness for variety within one model (see "Variety") |
| `params.py` | every dimension and fit value. `ft()`/`inch()` for scale sizes; printer values in mm; `zq()` snaps Z heights to whole layers |
| `joints.py` | tab, socket (+ lead-in, crush ribs), barb tab, `Piece` |
| `parts.py` | one function per part → `Piece` in its print frame (bed face at Z=0) |
| `registry.py` | the part list: number, name, part function, **built pose** |
| `sprue.py` | **print pose**: shelf layout, rails, gates with snap notches, label pads, checks |
| `checks.py` | pairwise interference, part connectivity, overhang/bridge spans, feature-size warnings |
| `view.py` | `--mode built\|print\|both` entry point |
| `corner.py` | the Creative Corner kit: its params, parts, poses and part list in one file |
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
which `color_partition` checks), and everything on a plate has to be in a loaded
tool. A kit can use more colors than the printer has tools by naming its plates
(`sprue.Plate`: parts, the color in each tool, sprue and label colors); the
Creative Corner does. Without named plates, the palette is T1..T4.

**Slicing on the U1:** open the plate's 3MF in Snapmaker Orca. It opens as **one
object with one part per filament** (`T1 brick`, `T2 trim`, ...), each part already
on its own filament, with the plate centered on the bed. Your printer and print
settings stay as they are, so you only match the listed filaments to your spools.
Prefer the 3MF over the per-color STLs: when OrcaSlicer combines separate STLs into
one object it can re-center each file, and the colors no longer line up.

**How the 3MF gets its filaments** (`render.export_color_3mf`). A plain 3MF with
color groups shows no filaments in Orca, so ours is laid out like a slicer project.
A Bambu Studio project from MakerWorld was the reference. What matters:

| piece | why |
|---|---|
| `Application` tag in `3D/3dmodel.model` | Orca reads per-part filaments only from Bambu or Orca projects; otherwise it logs "3mf from other vendor". Must be no newer than the slicer: Orca 2.4.2 rejects `02.08.02.61`, so we use `BambuStudio-01.10.00.00` |
| meshes in `3D/Objects/object_1.model`, joined by components in the root model | the same layout the reference project uses |
| `extruder` per part in `Metadata/model_settings.config` | this is the filament assignment |
| `model_instance` in that file's `<plate>` | without it, slicing a plate reports the file as empty |
| `filament_colour`, `filament_type` in `Metadata/project_settings.config` | the filament list, with a slot for every tool, even one this plate doesn't use |
| build item translated to the bed center | our meshes are built from the origin, so this puts the plate on the bed |

Leave printer and process settings out of `project_settings.config`: the reference
project's 578 keys are tied to its P1S, and without them Snapmaker Orca keeps yours.
3MF color groups don't help, so they aren't written.

Confirmed in the Snapmaker Orca app with a balcony plate. **The Orca CLI can't check
this:** 2.4.2 segfaults on these projects, with or without the U1 profiles, and it
has segfaulted on 4-filament U1 jobs even from plain STLs. Check changes in the app.

## Variety: making one model more interesting

A model can vary its repeated features without any two prints differing: the variation
is fixed by a seed, so every build of the kit comes out the same.

```python
v = Vary(p, f"planter{i}")          # vary.py: a stream for this one instance
height = H * v.between(0.82, 1.0, 1.0)      # low, high, nominal
band = v.pick(("rim", "double", "plain"))   # the first option is the nominal
```

* `variation_seed` picks a different set: `--set variation_seed=2`.
* `variety` scales it, from 0 (every instance is the plain template) to 1.
* Streams are keyed by name, so adding a part or a draw elsewhere reshuffles nothing else.
* A part made once and reused can't vary, because `registry.build` builds each `make`
  function once. Give each instance its own, as `corner._planter(i, sheet)` does.

The Creative Corner uses seed 30, chosen for its mix of blooms, heights and pots. A new
seed needs a full `just corner` run, since only that checks collisions and plate fit.

**What keeps it safe:** vary what's decorative and hold what mates. On the Creative
Corner's plants, baskets and pots, the pot, tabs and slot height stay fixed, so the
sheets still lock. Foliage only varies inside the template's envelope, so it can't reach
a neighbor or grow a plate. Details drop out rather than clip: a shadow that would run
off the foliage or into the slot isn't drawn, and enclosed pinholes get filled. The usual
collision, connectivity and bed checks still run on the result.

**Good candidates next:** anything repeated that doesn't mate: shop display wares, which
blinds are down and how far, sign word blocks, sidewalk cracks and patches, utility cover
positions.

## The joints

Rule: **every precision feature is in the XY outline of the part it's on**
(accurate to about a nozzle width), never a Z feature (quantized to 0.2 mm
layers).

Second rule: **nothing needs supports.** Every face that points down over air
is either a 45° slope or a bridge of at most `max_bridge` (2.5 mm).
`checks.overhangs()` scans each part in its print frame and fails the build on
a longer flat span. Blind pockets that open onto the bed (the facade's back
pockets) get a 45° chamfered roof above their full-depth section, which turns
a 3.3 × 4.3 mm flat roof into a 2.5 mm bridge (leaving 1.0 mm of facade in
front). The first print's sag came from the wedge key channels under the base,
which bridged about 8 mm; those are gone.

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

**New rows for the Creative Corner:** HS (its panel joint) and XL (its feature
joint, cross-laps at four clearances); see the docstring in `coupon.py`.

**Reading the coupon:** squeeze ≈ `rib_height` − `clearance`. Find your bare
clearance with the D/SP rows (smallest slot that slides with slight friction),
your favourite squeeze with the R row, then set
`rib_height = clearance + squeeze`. Kit sockets are deeper than the coupon
strips (3.6 vs 3 mm), so the kit feels a little tighter; if torn, pick the looser.

## Creative Corner kit

The two-story corner building at S Main St and Church St, Colfax (55 S Main is
the gift shop; 11 Church is Heilaman Hall). `just corner` builds it; `--set` works
as usual. Printing the kit needs the coupon's **HS** and **XL** rows checked first:
all the joints below depend on them, and neither has been printed yet.

![corner](out/corner/built_color_corner.png)

**Scale and compression.** The model is 220 x 133 mm on its base, 110 mm tall.
Only one of the two street faces is shortened:

| | real (estimated) | model |
|---|---|---|
| Main St face | ~27 ft | 27 ft (94.5 mm) |
| Church St face | ~97 ft, ~6 bays + west end | 52 ft: 3 bays + west end (182 mm) |
| Roofline / corner piers | ~30 ft / ~31.5 ft | same |
| Balcony underside | ~12.3 ft | same |
| Balcony to overhang | ~7.5 ft | 9 ft, so the doors fit under it |

Real sizes come from Street View thumbnails. With the panos' spacing from their
metadata, parallax gives ~50 px/m at the Church St wall plane (with a ~90 degree
FOV, which puts the wall ~10 m from the camera). The double doors come out 5 ft
wide, which is believable. Treat these as ±10%; a tape measure would beat them.
Reference panos, for `streetviewpixels-pa.googleapis.com/v1/thumbnail?panoid=..&yaw=..&pitch=..&w=1024&h=640`
(**negative pitch looks up**; images aren't kept in this repo):

| view | panoid | yaw |
|---|---|---|
| corner | `CQ4656yR8m5Y-VzA1hrWhA` | 311, 331 |
| Church St, straight on | `YCbsBCcdsBSHS9mKA-j7eA`, `Z2um6euyGu35YptXq3tpAQ`, `xlZEZVgetbZ5qM1M6BZ6zQ` | 11 |
| Main St, straight on | `uCS1xOhDVxhoQF4wfL7MWA` | 282 |

**Two tiers of joint:**
* **Main panels use split tabs** (three walls, two base slabs). These are the
  coupon's D10 tab: 4 mm wide, 1 mm slit, 0.10 barbs, in a 0.10 socket. Two to a
  panel edge, placed asymmetrically, so a panel only goes in one way round. Split
  prongs can take up spacing error, so these sockets don't float.
  `joints.split_tab` stops the slit `split_skin` (0.6 mm) short of the front face
  inside the panel, so a wall's show face stays closed. Base B's keys are 2 mm thick
  and slide in from the side under a skin, so that seam reads as a sidewalk joint.
* **Features use the loose fit** (`prop_clearance`, plain friction, no barbs or
  ribs): storefront, door panel, entry cheeks, decks, overhang, posts, outriggers,
  railings, cornice, sign, furniture, plants. Their sheets are 1–2 mm. Window
  backers have square pegs on their front, into blind pockets in the panel's back;
  one peg locates the sheet and the others float (`_peg_grid`).

**Colors:** eight filaments, at most four on a plate. Each plate is its own 3MF, set
up as in "Slicing on the U1", and its part names give that plate's tool numbers.

| filament | used for |
|---|---|
| sage | walls |
| iron | posts, outriggers, rails, furniture frames; pilasters, piers, belt courses, cornice; bulkheads; overhang top; basket hangers. Accents: window-sill shadows, door panels, roof seams, sign lettering, utility covers, foliage shadows, pot bands, display shelves |
| stone | window frames, Main St panel, screen doors, hanging sign. Accents: curb edge, shop door frame, post plinths and collars, sign-band pinstripe |
| rust | doors, storefront frame, deck and overhang edges, coping. Accents: shutters, bulkhead panels, Main St pinstripe, doormats, cornice edge, chair seats and backs, table top |
| concrete | sidewalk, deck tops, overhang roof seams |
| smoke | window backers. Load a translucent filament instead if you'll light it from inside |
| terra | planters, pots, baskets; window blinds and display wares on the backers |
| moss | foliage; little plants in the shop displays |

| plate | T1 | T2 | T3 | T4 | parts |
|---|---|---|---|---|---|
| `kit_plate1_ground` | concrete | stone | iron | rust | base, shop door panel |
| `kit_plate2_balcony` | concrete | stone | iron | rust | storefront, cheeks, decks, overhang, sign, cornice, 3 posts |
| `kit_plate3_church` | **sage** | stone | iron | rust | Church St wall, 4 posts, Church St rails, return rail |
| `kit_plate4_main` | sage | stone | iron | rust | Main St and west walls, post, upper posts, outriggers, furniture |
| `kit_plate5_green` | **smoke** | **terra** | iron | **moss** | backers, plants, Main St rails, corner rails |

Printing in this order, only the tools in bold need a new spool. Base B prints a
quarter turn round, as a long strip above base A.

**Accents** are paint only, so they change no geometry: fits and joints stay as they
were. Each one reuses a color already on its plate, and the rule that makes it work is:
* A part made for several plates can only use colors all of them load. Posts land on
  three plates, so their accent is stone. Rails land on the church and green plates,
  which share only iron, so they stay plain.
* Sheets seen from both sides (plants, posts, furniture, the hanging sign) are painted
  through; panels seen from the front get `color_depth` on that face.
* Painted lines stay at least `accent_w` (0.8 mm, two nozzle widths) wide. Foliage
  shadows are half discs because their square corners leave no sliver tips to drop.
* Details are stylized where type or fine lines can't print: signs carry word blocks,
  not letters. The shutter color, doormats, wares and blinds are invented, not from the photos.

**Plates:** all within the 210 mm usable bed, ~218 cm³ in total
(about 270 g if it were solid; not sliced yet, so no time estimate).

**Assembly** (part numbers are on the sprue label pads):
1. Slide base A's keys into base B on a flat surface.
2. Press the backers into the backs of the Church St wall (52 on 3) and the Main St
   wall (53 on 4). Push the west return (5) into the back of the Church St wall,
   then the Church St wall's end tabs into the back of the Main St wall. Press that
   whole unit into base A.
3. Entry: push both cheeks (8, 9) into the door panel (7), slide the storefront
   (6) onto their front tabs, and press the backers on behind (54 on 6, 55 on 7).
   Lower it all into the base from behind, so the storefront sits against the back
   of the Main St wall.
4. Stand the lower posts (13–20) in the sidewalk. Drop an outrigger (25–32) onto
   each post's head, so the two slots cross, with its plain end at the wall.
5. Church St deck (10): hook its back tabs into the wall with the front edge raised,
   then swing it down over the post tabs. Same for the Main St deck (11), whose
   pocket takes the Church St deck's end tab.
6. Upper posts (21–24) down through the Church St deck, then the overhang (12) the
   same way as the deck: back tabs first, then down over the post tops.
7. Railings (33–42), cornice (43), sign (44, up through the deck from below),
   table (45–47: cross a and b, top on a's tab), chairs (48–51).
8. Greenery. Each plant is a cross-lapped pair, with the tab on `a`: planters
   (56–63) into the sidewalk, pots (64–69) through the decks, baskets (70–72) up
   through the overhang from below.

**Not checked:** this hasn't been printed, and step 5's swing-in is reasoned from
the clearances, not simulated. If the decks won't swing in, shorten `deck_tab_pocket`.
Rails, posts and chairs are at the limit of what prints well, at 0.7–1.0 mm. The
backers' pegs are new and aren't on the coupon; if they don't hold, a drop of glue
will do, since nothing bears on them.

**Left out for now:** no roof or back wall (it's open behind, like the nook). Also
the lamp post, street signs, and any lettering.

## Colfax Market kit

The false-front store at Main St and W Grass Valley St, Colfax (the first kit made with the
`streetview-kit` skill). `just market` builds it, in about 3 minutes. It's the small end of
what a kit can be: 16 parts, 3 plates, 5 filaments. The joints are the Creative Corner's two
tiers, so printing it needs the coupon's **HS** and **XL** rows checked first.

**Sizes** come from Street View, with the door (taken as 7 ft) as the ruler, so treat them as
±10%:

| | real | kit |
|---|---|---|
| front width | ~27.5 ft | 96 mm |
| false front height | ~25.6 ft | 90 mm |
| side wall | well over 100 ft, not measured | **compressed to 46 ft**, 161 mm |
| side eave | ~11 ft | 39 mm |
| front sidewalk | ~8 ft | 28 mm |
| roof pitch | ~12°, rough estimate | 12° |

The compressed side wall keeps the corner end, the mural and the rear door, which is in fact
much farther from the corner. The linked panorama is from February 2025.

| view | panoid | yaw | pitch |
|---|---|---|---|
| corner, as linked | `xjdWnY6N6IsWqPeGN6KGWQ` | 329 | 3 |
| front, straight on | `6qb1psUT8N03tLUVvRG1xQ` | 283 | 0 |
| side, straight on | `6ATpL5PiIHVWoZT0CR7RRg`, `TB7cw90SYluMWqsVLXuWzQ` | 12 | 0 |

**Sloped roofs** are new here. The tin roof and the awning are sheets on a slope, and their supports
have vertical tabs up through angled slots (`market.roof_slot`). Each slot is longer up the slope than
the tab is thick, so the tab passes at the sheet's angle, and the sheet lowers straight onto its
supports. The awning also hooks two back tabs into the wall, in pockets tall enough for the angle.

**Colors:** five filaments, at most four on a plate.

| filament | used for |
|---|---|
| brick | walls, false front, awning, rafters, tree planter, the red curb |
| cream | lettering, window and door frames, sign word blocks, front post collars |
| coal | posts, mural, sign boards, roof ribs and fascias, top rail, utility cover, window backer |
| tin | sidewalk, roof, air conditioner, and posters on the backer |
| moss | the tree, and posters on the backer |

| plate | T1 | T2 | T3 | T4 | parts |
|---|---|---|---|---|---|
| `kit_plate1_ground` | brick | cream | coal | tin | base, 6 posts |
| `kit_plate2_walls` | brick | cream | coal | tin | false front, side wall, rear rafter |
| `kit_plate3_roof` | brick | **moss** | coal | tin | roof, awning, backer, middle rafter, tree |

Printing in this order, only moss needs a new spool. Plates 1 and 3 are close to full, so moving a
part means re-checking them.

**Assembly** (part numbers are on the sprue label pads):
1. Press the backer (4) into the back of the false front (2). Push the side wall's (3) end tabs into
   the back of the false front, then press that unit into the base (1).
2. Stand both rafters (7, 8) and all the posts (9-14) in the base.
3. Lower the roof (5) straight down onto the rafters' and side posts' tabs. The posts are thin, so
   guide them in from one end.
4. Hook the awning's (6) back tabs into the false front with its front edge raised, then lower it
   onto the front posts' tabs.
5. Cross the tree's sheets (15, 16) and press the tab into the sidewalk.

**Not checked:** nothing here has been printed or sliced. The angled slots are new and aren't on the
coupon, and the awning's swing-in is reasoned from the clearances, not simulated. Side posts are
1.6 x 1.2 mm and about 40 mm tall, the most fragile parts in the kit. Colors are judged from photos.

**Changed or invented:** the green Grocery and Liquor boards are coal with word blocks here, since
green is only loaded on the roof plate. The miners are simple figures in the spirit of the mural, not
copies of it. The tree stands on the sidewalk under the eave, where the real, taller one stands
beyond the curb. Posters are random blocks.

**Left out:** the neighboring buildings, the gooseneck lights on the false front, the lamp post, the
flag, the planter's rocks and the bike racks. The north roof slope and the back are open.

## Colfax caboose kit

The red wood-sided Southern Pacific caboose on display in Colfax, by N Main St. It's the first
object rather than a building, made with the `streetview-kit` skill. `just caboose` builds it, in
about 5 minutes: 25 parts, 2 plates, 4 filaments and no spool change. The joints are the usual two
tiers, so printing it needs the coupon's **HS** and **XL** rows checked first.

**Sizes** come from Street View, with the body height as the ruler, so treat them as ±10%. It isn't
compressed: it fits as it is.

| | real | kit | source |
|---|---|---|---|
| body length | ~33 ft | 116 mm | photos, against the height |
| body width | ~9.5 ft | 33 mm | the end view |
| body height | ~8.5 ft | 30 mm | **assumed**, from typical cars |
| floor above rail | ~4 ft | 14 mm | **assumed**, typical |
| wheels | 33 in | 9.6 mm | **assumed**, typical |
| cupola | ~9.7 ft long, 3 ft high | 34 x 10.5 mm | photos |
| track gauge | 4 ft 8.5 in | 16.5 mm | HO standard |

| view | panoid | yaw | pitch |
|---|---|---|---|
| west side, as linked | `aCtmU6m3CjrTEHB-KLOqEg` | 127 | 9 |
| west side, straight on | `6qb1psUT8N03tLUVvRG1xQ` | 110 | -3 |
| east side, at an angle | `DgVLALzWQlXZhYBqXpNObQ` | 175 | -5 |
| north end | `h4Cd1FBkB29TxjRNjgwirw` | 195 | -5 |

**Construction:** it's a box of split-tab panels on a floor, and everything else is loose-fit: the
cupola and trucks are cross-lapped, and a dark sheet down the middle is what you see through the
windows. Each wheel sheet sits on the base's rails at HO gauge. It doesn't roll, and it has no flanges to
stay on real track. Nothing fixes the car to the base, so it lifts off.

**Colors:** four filaments, on both plates, so there's no spool change.

| filament | used for |
|---|---|
| red | body, cupola, roofs, truck frames, platform decks, the base's border |
| cream | lettering, grab irons, end rungs, railings, the base's rails |
| coal | underframe, wheels, steps, spine, window glass, roof seams, sill shadows, ties |
| ballast | the base |

| plate | parts |
|---|---|
| `kit_plate1_frame` | display base, floor, roof, trucks, steps |
| `kit_plate2_body` | sides, ends, spine, cupola, railings |

**Assembly** (part numbers are on the sprue label pads):
1. Push the sides' (3, 4) end tabs into the backs of the ends (5, 6), then press the box into the floor (2).
2. Drop the spine (7) in from above, into the floor.
3. Trucks: cross a bolster with two frames (18 with 14 and 15; 19 with 16 and 17), then press its tab up
   into the floor.
4. Steps (20-23) up into the floor's corners, railings (24, 25) down into the platforms.
5. Cupola: cross its ends (11, 12) with its sides (9, 10), press the tabs into the roof (8), then add its
   roof (13).
6. Lower the roof onto the spine's tabs, and set the car on the base (1).

**First print** (this two-plate layout): nearly all the parts came off the sprues cleanly, and the
split-tab box holds together. Known flaws: the roof has no joint to the walls, only two friction
tabs on the spine, so it doesn't stay put, and the wheels don't stay attached. Both need redesigning.

**Not checked:** the lettering's smallest strokes are about
0.6 mm. Railings and steps are 0.8-0.9 mm bars, and the cupola ends' thin legs are about 0.8 mm wide.

**Read from photos, so uncertain:** the east side's windows were only seen at an angle, past the fence.
The south end wasn't seen close up, so it's assumed to match the north end.

**The car's number is left blank.** It reads as "?63" in the imagery, and a wrong number on a town
landmark would be worse than none. Once someone reads it off the car, set `road_number` in
`CabooseParams`; it'll print at a size that needs checking, or stay as the block if it's too fine.

**Changed or invented:** the real roof is very slightly arched, and it's flat here because everything
prints flat. The roof seams, end ladder rungs and platform deck color are assumptions. The emblem under
the name is a simple block pattern, not the real logo.

**Name and marks:** "Southern Pacific" and its logos may be trademarks of the railroad's successor.
Check before selling this or giving it out widely. The name is a single paint volume, so it's easy to change.

**Left out:** the plaza's iron fence, benches and flagpoles; brake wheel, chimney and couplers.

## What was verified (the generic storefront)

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
with no rotation. A kit too big for one bed gets split into plates by whole
rows (`sprue.paginate`), and `first_fit` lets small parts drop back into earlier
rows, but it doesn't nest parts inside others' bounding boxes or holes.

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
* The other Colfax landmarks (Creative Corner, the Market and the caboose so far, above).
* Layered/laminated facades.

## License

MIT, see [LICENSE](LICENSE). That covers the code and the kit designs. It grants no rights
to the real buildings' names or to any trademarks a kit depicts.
