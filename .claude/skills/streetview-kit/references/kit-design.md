# Kit design rules

These come from real prints and from building the Creative Corner. If print results in the README's
"Tuning from prints" disagree with anything here, the print results win.

## The printer

Snapmaker U1: four toolheads, 220 mm bed (210 usable), PLA, 0.2 mm layers, 0.4 mm nozzle. HO is
1:87.1. Use `ft()` and `inch()` for scale sizes, and plain mm for anything the printer limits.
On a different printer, its limits are in `params.py`. The fit values are only right after printing
the coupon on that printer. The numbers in this file are the U1's, so scale them to match.

- **Precision belongs in the XY outline** of a part, accurate to about a nozzle width. Z is
  quantized to layers, so send any height through `zq()` and never rely on one for a fit.
- **No supports.** Slopes stay at 45° or steeper, bridges at `max_bridge` or shorter, and pockets that
  open onto the bed get a chamfered roof (`bridge_roof`, `socket`). `checks.overhangs` enforces this.
- **Thin limits:** 0.6 mm is the thinnest trusted feature. Rails and pickets at 0.7-1.0 mm are at the
  edge of what prints well.
- **Everything prints flat**, face up, on a sprue. Depth comes from assembling flat sheets, not from
  3D parts, so think in layers: what's a separate sheet, and what's relief on one?

## Fitting the bed

A part has to fit in one piece, in about 195 mm: the rails and its label pad take the rest of the 210
mm. That's about 56 ft at HO, and real buildings are often longer. Add it all up for the base: the
longest wall, plus the sidewalk and street strip in front of it.

**Compress selectively, the way model railroaders do:** keep heights and the character of the bays,
and cut the number of repeats. The Creative Corner's 97 ft wall became 3 balcony bays plus its solid
end. Keep the recognizable face at full scale, and compress the plain ones. Say what you did.

The back is usually open, like a stage set, and that's fine: this is a street-facing model. A long side
can be a return shortened to the first few bays. Adding a roof is a design choice, so only do it when
the roof is part of what makes the building recognizable.

Two shelf-packing limits come up on most kits: a tall part forces a whole row, and the shelf packer
sorts tallest first. If a plate overflows, move tall or wide parts to a plate with the colors they
need, before shrinking anything.

## Objects, not buildings

The Colfax caboose showed that the same approach works for an object, with these differences:

- **There's no slab to build on.** Find the object's own structural sheet, like the caboose's floor, and
  let the panels' split tabs go into that. Anything that's a box still works as panels and sheets.
- **Give it something to stand on.** A small display base sets it off. Keep the object removable unless
  it needs to be fixed.
- **Don't compress it if it fits.** Objects often fit whole. Their proportions are the point.
- **Standard dimensions help.** Vehicles and machines have known sizes (HO gauge, wheel diameters, car
  widths), so use them as the ruler when photos are unclear. Mark them as assumed.
- **Think in cross-laps.** Wheel sets and small boxes like a cupola are good cross-lapped sheets, and they
  read as solid from any side. Put a dark sheet inside anything with windows.
- **Hidden interior tabs can meet.** The caboose's spine and truck both had tabs into the floor, from
  either side, and they collided when the truck moved. Keep them apart along the length.
- **Everything prints flat, so curves in section don't exist.** A slightly arched roof becomes a flat
  sheet. Say so, rather than trying to fake it with something fragile.

## Two tiers of joint

The person chose this split after tuning, so keep it.

- **Main panels use split tabs** (`joints.split_tab`, `split_clearance`): walls and base slabs. Two to
  an edge, placed asymmetrically, so a panel goes in only one way round. These carry the model and set
  its alignment.
- **Features use the loose fit** (`tab` and `prop_clearance`, plain friction, no barbs or ribs): sheets
  of 1-2 mm for storefronts, awnings, posts, railings, signs, plants. Cross-laps add depth cheaply: two
  slotted sheets look solid from any side. These only have to stay put.

**Sloped sheets** (roofs, awnings) print flat and pose at their angle. Their supports keep vertical
tabs, through slots made longer up the slope (`market.roof_slot`), and a shoulder that stops where the
underside would hit it, so the sheet lowers straight down. Tabs into a wall arrive at the angle, so
their pocket has to be taller than the sheet is thick. The first try at these collided in three
places, so run the checks early.

Other things that keep assembly sane:

- One socket per part locates it, and the rest float (`float_clearance`), so spacing errors don't have
  to be forced in. Heavy interference was hard on the first print.
- Check the assembly order: every part needs a way in. A sheet with back tabs and front tabs has to
  hook and then swing down, and a closed box can't take a part from inside.
- Gates go on edges hidden after assembly, because that's where a snipped nub won't show.
- `Piece.nominal` is the part's real shape, and `extras` are deliberate interference. Collisions in
  check A are real, so don't paper over them.

## Color

Each part has a base color plus paint volumes (`Piece.paints`, later ones win). Paint changes no
geometry, so fits and checks don't care about it.

- **A plate loads four colors, and tools can differ between plates.** Plan the print order so the
  fewest spools change. Keep tool numbers stable where you can.
- **A part made for several plates can only use colors all of them load.** Group small parts by the
  colors they share. If a plate overflows, small dark parts can move to plates with room.
- **Raised features** also color `color_depth` of the material under them, so a pale color over a dark
  one isn't just two translucent layers.
- **Sheets seen from both sides are painted through.** Panels seen from the front get `color_depth` on
  that face.
- **Painted lines stay at least 0.8 mm** (`accent_w`, two nozzle widths). Avoid sharp sliver tips, which
  slicers drop: half discs work where crescents don't.
- **Lettering:** real type only prints if the strokes are about 0.6 mm or wider, which means big signs
  only. For small signs, use word blocks. A building's big name sign is worth doing as real type: the
  Market's false front uses `Text` as a paint volume, in a serif font derived from `COLFAX_FONT`
  (`market._lettering`). Keep battens and other relief out from under the letters.
- **Backers:** a dark sheet behind windows stops you seeing through the building, and can carry painted
  displays and blinds, which is cheap and effective.

Slicing is handled by `render.export_color_3mf`: parts stay on their own filaments, and the person
reconciles them to spools in Snapmaker Orca. Orca's CLI crashes on these files, so it can't verify
them. Say so rather than treating that as a result.

## Detail that pays off

Paint gives the most for the least risk, in roughly this order:

1. Shadows: a dark strip under sills and overhangs, half discs in foliage. These read as depth.
2. Contrast at edges: copings, trim, curb edges, posts' plinths and collars.
3. Texture from repeated lines: seams, battens, brick courses at wide spacing.
4. Story: signs, shop displays, furniture.

**Variety:** give repeated decorative things their own `vary.Vary(p, name)` stream, and their own make
function (`registry.build` builds each function once). Vary what's decorative, and hold what mates. Stay
inside the template's envelope, so a variation can't reach a neighbor or grow a plate. Try a few seeds
and pick a good mix, then note it in the params.

## Mistakes already made

- **Generated shapes that only work by luck.** Randomized plant foliage floated free of its pot on some
  seeds, and it took a differently proportioned plant to show that. Give anything random a fixed part
  that guarantees it's connected, and try several seeds.
- **Relief cutting through features.** `Face` applies cuts after raised features, so a texture of grooves
  slices through door frames and signs on the same wall. Keep those cuts away from them.
- **Textures that read as something else.** Continuous grooves made brick look like log siding, and
  staggered dashes fixed it. Rust patches on a roof looked like skylights, so they came out. Look at
  renders from an angle, not only straight on.
- **Corner sockets at a panel's edge.** A socket for a wall that meets the edge breaks through it. Let the
  panel run past the corner by a millimeter or so.
- **Gates on tabs.** A snipped nub spoils the fit. Gate onto an edge that's hidden but doesn't mate.
- **Late plate surprises.** Estimate packing once parts exist, before detailing them.
- **Taking a passing build as proof that it looks right.** Open the images.
