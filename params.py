"""All dimensions and fit parameters for the storefront nook kit.

Two kinds of numbers live here:
  * Scale dimensions, written in real-world feet/inches through ft()/inch().
  * Printer-driven values (wall thickness, clearances, min feature), written
    directly in mm, because a 0.4 mm nozzle doesn't shrink at 1:87.1.

Anything that ends up as a height in Z on the print bed goes through zq(), which
snaps it to a whole number of layers.

Override values on the command line with:  --set name=value  (see view.py).
"""

from dataclasses import dataclass, fields, replace

SCALE = 87.1  # HO
MM_PER_FT = 304.8 / SCALE  # ~3.499 mm


def ft(x: float) -> float:
    """Real-world feet -> model mm."""
    return x * MM_PER_FT


def inch(x: float) -> float:
    """Real-world inches -> model mm."""
    return x * MM_PER_FT / 12.0


@dataclass(frozen=True)
class Params:
    # --- printer -----------------------------------------------------------
    nozzle: float = 0.4
    print_layer_height: float = 0.2
    min_feature: float = 0.6         # thinnest XY feature we trust to print
    bed_x: float = 270.0             # Snapmaker U1, from Snapmaker Orca's own profile
    bed_y: float = 270.0
    bed_margin: float = 5.0
    # Left free at the bed's back-left corner, from its edges. The U1's prime tower
    # is 30 mm wide with a 5 mm brim, and its ribs reach 8 mm further out.
    tower_x: float = 60.0
    tower_y: float = 60.0

    # Model variety (vary.py): fixed for a given seed, so every build is the same.
    variation_seed: int = 1
    variety: float = 1.0             # 0: every instance is the plain template
    # Longest flat span we'll print with nothing under it. Blind pockets that
    # open onto the bed get a 45° chamfered roof that shrinks their bridge to this.
    max_bridge: float = 2.5

    # --- walls (printer-driven) -------------------------------------------
    wall_thickness: float = 3.0      # facade + returns; ~10" at scale (brick)
    base_thickness: float = 3.6      # sidewalk slab / plinth (18 layers)
    prop_thickness: float = 1.2      # cross-lap prop sheets (3 nozzle widths)

    # --- fit (mm, per side) --------------------------------------------------
    clearance: float = 0.15          # gap between tab and socket wall, per side
    rib_height: float = 0.20         # crush rib protrusion into the socket
    # Along a wall, only one socket per part locates it; the others get this
    # much room per side so peg spacing errors don't have to be forced in.
    float_clearance: float = 0.40
    prop_clearance: float = 0.10     # cross-lap slots + prop pocket: plain friction, no ribs
    # Split tabs (joints.split_tab). 4 mm wide, 1 mm slit, 0.10 barb in a 0.10
    # socket is the coupon's D10 tab at the clearance that gave a firm hold.
    split_clearance: float = 0.10
    split_width: float = 4.0
    split_barb: float = 0.10
    split_slit: float = 1.0
    split_skin: float = 0.6          # slit stops this short of the show face
    rib_base: float = 0.8            # crush rib width where it meets the wall
    lead_in: float = 0.4             # 45° chamfer at socket mouths & tab tips
    detent_height: float = 0.15      # barb bump (coupon only)

    # --- tabs ------------------------------------------------------------------
    # Tabs are extensions of a flat part's outline, so tab *thickness* is always
    # the thickness of the part it's on (wall_thickness / prop_thickness).
    facade_tab_widths: tuple = (5.0, 6.5)   # different widths = keyed (one way in)
    return_tab_width: float = 3.5
    return_front_tab_len: float = 1.4       # into blind pockets in the facade back
    prop_tab_width: float = 2.0
    prop_tab_len: float = 2.4

    # --- building (scale) -----------------------------------------------------
    facade_width: float = ft(25)
    storefront_height: float = ft(18)   # top of wall; parapet sits above
    parapet_height: float = ft(2.5)
    sidewalk_depth: float = ft(10)      # curb face to facade face
    return_depth: float = ft(3)
    return_inset: float = 1.0           # mm, returns sit in from facade edges
    street_strip: float = ft(1.5)       # gutter strip in front of the curb
    curb_height: float = inch(6)
    joint_spacing: float = ft(5)
    joint_width: float = 0.6
    joint_depth: float = 0.4

    door_width: float = ft(3.5)
    door_height: float = ft(7.5)
    door_recess: float = 0.6
    window_margin: float = ft(1.5)      # facade edge to window
    window_door_gap: float = ft(1.0)
    window_sill: float = ft(2.0)        # bulkhead height
    window_top: float = ft(9.0)
    window_frame: float = 0.8           # frame band width (XY)
    window_frame_raise: float = 0.4
    transom_at: float = ft(7.5)         # height of the transom bar
    transom_bar: float = 0.8
    sign_bottom: float = ft(10.5)
    sign_top: float = ft(13.0)
    sign_inset: float = ft(1.0)
    sign_raise: float = 0.6
    cornice_bottom: float = ft(17.0)
    cornice_step: float = ft(1.0)       # each of two cornice steps
    cornice_raise: float = 0.4          # per step
    coping_height: float = ft(0.5)

    prop_x: float = ft(6.0)             # planter position on the sidewalk
    prop_y: float = ft(3.5)             # (from the street edge)
    prop_width: float = ft(2.5)
    prop_height: float = ft(4.5)

    # --- sprue -----------------------------------------------------------------
    rail_width: float = 2.0
    rail_height: float = 1.6
    gate_width: float = 1.2
    gate_height: float = 1.0
    gate_neck: float = 0.8           # snap point where the gate meets the part: two nozzle widths
    gate_gap: float = 3.0            # rail-to-part distance
    gate_max: float = 10.0           # longest gate, rail to part
    gate_pitch: float = 35.0         # a part gets about one gate per this much of its outline...
    gate_most: int = 12              # ...up to this many
    part_spacing: float = 4.0        # between parts in a row (room for cutters)
    stile_over: float = 15.0         # rows taller than this get a rail between their parts
    pack_tries: int = 400            # layouts sprue.pack tries per sheet
    label_size: float = 3.6
    label_raise: float = 0.4

    # --- color ------------------------------------------------------------------
    # One filament per toolhead. Palette order = tool number (T1..T4), unless the
    # kit names its plates (sprue.Plate); then a kit may use more colors than the
    # printer has tools, as long as each plate stays within max_tools. Hex is only
    # for previews; the printer uses whatever filament is loaded in that tool.
    max_tools: int = 4
    palette: tuple = (
        ("brick", "#8e3b2e"),
        ("trim", "#e8e0cc"),
        ("concrete", "#9c9a94"),
        ("accent", "#2e5b3c"),
    )
    # Which filament each thing gets (names from the palette).
    color_wall: str = "brick"        # facade + returns
    color_trim: str = "trim"         # window frames, transoms, cornice, coping
    color_sign: str = "accent"       # sign band
    color_door: str = "accent"
    color_base: str = "concrete"
    color_planter: str = "concrete"
    color_shrub: str = "accent"
    color_sprue: str = "concrete"    # rails, gates, label pads
    color_label: str = "trim"        # embossed part numbers
    # A colored face feature also colors this much material *under* it, so a
    # light color over a dark one isn't just 2 translucent layers.
    color_depth: float = 0.6

    def hex(self, color: str) -> str:
        return dict(self.palette)[color]

    # --- derived --------------------------------------------------------------
    def zq(self, z: float) -> float:
        """Snap a Z height to a whole number of layers (at least one)."""
        lh = self.print_layer_height
        return max(lh, round(z / lh) * lh)

    @property
    def wall_height(self) -> float:
        return self.storefront_height + self.parapet_height

    @property
    def base_depth(self) -> float:
        return self.sidewalk_depth + self.wall_thickness + self.return_depth

    @property
    def facade_tab_xs(self) -> tuple:
        """X centers of the two facade tabs (asymmetric widths do the keying)."""
        return (0.2 * self.facade_width, 0.8 * self.facade_width)

    @property
    def facade_tab_len(self) -> float:
        # Through the base, stopping 0.3 mm above the table.
        return self.base_thickness - 0.3

    @property
    def return_tab_ys(self) -> tuple:
        """Heights (return-local) of the front tabs into the facade."""
        return (0.3 * self.storefront_height, 0.7 * self.storefront_height)

    @property
    def return_xs(self) -> tuple:
        """World X of the -X face of the (left, right) return."""
        w, t, i = self.facade_width, self.wall_thickness, self.return_inset
        return (i, w - i - t)

    @property
    def prop_tab_x(self) -> float:
        return self.prop_width / 2


def with_overrides(p: Params, pairs: list[str]) -> Params:
    """Apply ['name=value', ...] overrides, e.g. from --set on the CLI.

    Values are Python expressions evaluated with ft/inch available, so
    --set facade_width=ft(30) works.
    """
    known = {f.name for f in fields(p)}
    changes = {}
    for pair in pairs:
        name, _, expr = pair.partition("=")
        if name not in known:
            raise SystemExit(f"unknown param {name!r}")
        try:
            changes[name] = eval(expr, {"ft": ft, "inch": inch})
        except NameError:
            changes[name] = expr   # bare word, e.g. --set color_door=trim
    p = replace(p, **changes)
    check_colors(p)
    return p


def check_colors(p: Params):
    """Every color_* must name a palette entry. view.run_plate checks each plate
    against the printer's tools."""
    names = [n for n, _ in p.palette]
    for f in fields(p):
        if f.name.startswith("color_") and f.name != "color_depth":
            if getattr(p, f.name) not in names:
                raise SystemExit(f"{f.name}={getattr(p, f.name)!r} is not in palette {names}")


DEFAULT = Params()
