---
name: streetview-kit
description: Turn a Google Street View link of a real building or landmark object (a caboose, a locomotive, a gazebo, a statue) into a complete, checked, snap-together HO-scale kit in this repo. Gathers reference views, works out the subject's size and features, then models it in build123d with sprue plates and multi-color 3MFs. Use this whenever someone gives a Google Maps or Street View URL and wants a kit, model or printable version of what's in it, or says things like "make a kit of this building" or "let's do this storefront next", even if they don't say "skill" or "Street View".
---

# Street View to kit

Go from a link to a finished kit without stopping for approval: images, design, model, plates,
checks, commit. Pause only if the link doesn't reach a usable view of the subject. Record every
assumption as you go, because the person reviews the finished model and needs to see what you
guessed.

The subject is usually a building, but it can be an object. If so, also read "Objects, not
buildings" in `references/kit-design.md`, and use `caboose.py` as the example.

Read `references/kit-design.md` before designing. It holds the rules that came from real prints.
Read the README's "Creative Corner kit" and "Variety" sections and skim `corner.py`: that's the
worked example, and most of what you need can be reused from it.

## 1. Gather views

The helper script is `scripts/streetview.py` in this skill. Run it with `python -I`, and keep
images in the session's scratchpad, never in the repo: they're reference material, and the source
is an undocumented Google endpoint, not a licensed one. Fetch what the design needs and no more.

```sh
S=.claude/skills/streetview-kit/scripts/streetview.py
python -I $S info "$URL" --out $D           # panorama, address, capture date, nearby panoramas
python -I $S sweep "$URL" --out $D          # eight compass views, as one contact sheet
python -I $S info "$URL" --target LAT,LNG   # adds the yaw from each panorama to the building
python -I $S grab --out $D name:PANO:YAW:PITCH ...
python -I $S sheet $D/faces.jpg 3 $D/a.jpg $D/b.jpg ...
```

Things that aren't obvious:

- **Negative pitch looks up.** Roofs and parapets usually need about -20 to -25.
- **The link's place pin can be a whole town**, not the building. Trust the panorama, and check
  the address the metadata gives against what's in the image.
- **Images come back at 1024x640 at most**, and the field of view is fixed. To see more detail,
  move to a closer panorama.
- **`info` lists neighbors with offsets in meters.** To view a face straight on, pick a panorama
  opposite its middle and look perpendicular to the road. The `road` column gives the road's
  direction there, so the yaw to look across it is `road` ± 90.
- **Panorama dates vary**, and neighbors can be years apart. If the views disagree, prefer the
  link's own panorama: that's the building as the person saw it.
- **Aim, don't sweep, for a small subject.** Compass views from nearby mostly miss it. Work out where it
  is from the linked view, then pick panoramas on each side and yaw straight at it.
- **Read fine details by enlarging a crop** with PIL before relying on them. Don't guess at numbers or
  names. If text can't be read, leave a blank and say what to fill in.

Keep going until you can answer these. Use contact sheets to scan, then open the best views at
full size:

- Which faces show, and what's on each one, from the ground to the roofline?
- How do the faces meet, and what's the depth of anything that sticks out?
- What makes this building recognizable? If it were one feature, which would it be?
- How long is each face? Use panorama offsets for lengths, and doors (about 7 ft high, 3 ft wide)
  for heights. Treat results as ±10%.

If a face can't be seen, say so and design it plainly.

## 2. Write the brief

Write this to the scratchpad and reuse it for the kit's docstring and README section. Deciding this
before modeling is what keeps a kit coherent.

- **Identity:** what makes it recognizable. Those features get the modeling effort.
- **Massing:** real sizes, then what's selectively compressed to fit the bed, and how.
- **Effort tier:** match it to the building and to what the person asked for. A simple building
  should be a small kit: fewer plates, four colors or fewer. Eight filaments and five plates was
  accepted for a showcase piece, and isn't a default. Say which tier you chose.
- **Parts:** panels (split tabs) and features (loose fit), with what each feature adds in depth.
- **Colors and plates:** filaments sampled from the photos, and what goes on each plate.
- **Left out**, and anything **invented**.
- **Names and marks:** a business name or a railroad's logo may be someone's trademark. Modeling it
  is usually fine for a personal kit, but say so in the report if it's going to be shared or sold.

## 3. Build it

Create `<kit>.py` next to `corner.py` and `market.py`, following their shape: a frozen dataclass
params class, one function per part, poses, `_LIST`, `REGISTRY` and `PLATES`. `market.py` is the
shorter example, and the better one for a small kit. Subclass `CornerParams` and import what you can
reuse from `corner` (`Face`, `stand`, `_base_slab`, `_curb_edge`, `_backer`, `_plant_a`, `_plant_b`)
and `joints`, rather than copying it. Add the kit to `KITS` in `view.py` and a recipe to the `justfile`.

Work in passes, and look at each one. Build time depends on the kit, from about 3 minutes for a small
one to over 13 for a showcase, so get fast feedback:

1. Panels and base. Run `python -X faulthandler view.py --kit <kit> --mode built --no-viewer`.
2. Depth features. Collisions tell you what's wrong while it's still small. It's fine to write all
   the parts at once on a small kit, as long as you run this straight away.
3. Compare the color render against the photos, face by face and from the corner view. Ask what would
   make someone recognize the building, and list what's different before fixing anything. This pass
   finds what the checks can't, and it's worth doing properly.
4. Plates: `--mode both`. Fix what doesn't fit the bed or tool limits.
5. Accents and variety, as paint where you can, so fits stay untouched. Look at these on single
   parts: write a throwaway script rendering `piece.regions()` with `render.color_preview`, which
   takes seconds instead of a full build.

## 4. Finish

The kit isn't done until `--mode both` exits 0, which means:

- no collisions, and every part is one solid
- every plate fits the bed with at most `max_tools` colors, and color regions tile exactly
- no overhang over `max_bridge`

Open the final renders and each plate image yourself: passing checks doesn't mean it looks right.

Add a README section like "Creative Corner kit": sizes and their source, reference panorama ids,
joints, filament and plate tables, assembly steps in part order, "not checked", "left out". Commit
with `jj`, on a new change, not moving `main`. This project uses jj rather than git.

## Reporting back

Lead with the result: what the kit is, and whether checks passed. Then:

- the plates and filaments, including the order that needs the fewest spool swaps
- what you compressed or invented, and which sizes are the least certain
- what isn't verified: it hasn't been printed or sliced, plus any joint new to this kit that isn't
  on the coupon
- where the renders and 3MFs are, and how to open them in the viewer
