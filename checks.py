"""Geometry checks: pairwise interference (built mode) and feature-size warnings."""

from itertools import combinations

from joints import overlap
from params import Params

THRESHOLD = 1e-3  # mm^3; tangent contact between faces comes out as ~0


def interference(placed, threshold=THRESHOLD):
    """placed: [(name, nominal_solid, [extra_solids])], all in world coords.

    Check A: nominal bodies must not overlap at all (beyond `threshold`).
    Check B: extras (crush ribs, barbs) are *meant* to overlap their mate; we
    report how much, and flag any extra that touches nothing (rib too small
    for the clearance, so it won't grip).

    Returns (errors, report_lines).
    """
    errors, lines = [], []
    for (na, a, _), (nb, b, _) in combinations(placed, 2):
        v = overlap(a, b)
        if v > threshold:
            errors.append(f"COLLISION {na} x {nb}: {v:.4f} mm^3")
    lines.append(f"check A (bodies): {len(placed)} parts, "
                 f"{len(list(combinations(placed, 2)))} pairs, {len(errors)} collisions")

    for name, _, extras in placed:
        if not extras:
            continue
        per_mate, idle = {}, 0
        for e in extras:
            hit = False
            for other, b, _ in placed:
                if other == name:
                    continue
                v = overlap(e, b)
                if v > threshold:
                    per_mate[other] = per_mate.get(other, 0) + v
                    hit = True
            idle += not hit
        mates = ", ".join(f"{m} {v:.3f} mm^3" for m, v in per_mate.items()) or "nothing"
        lines.append(f"check B (ribs/barbs on {name}): {len(extras)} features grip {mates}"
                     + (f"; {idle} grip NOTHING" if idle else ""))
        if idle:
            lines.append(f"  WARNING {idle} rib(s) on {name} don't reach their mate "
                         f"(rib_height <= clearance?)")
    return errors, lines


def connectivity(named_solids):
    """Each printable piece must be one solid; a floating rib or barb is a bug."""
    errors = []
    for name, shape in named_solids:
        n = len(shape.solids())
        if n != 1:
            errors.append(f"DISCONNECTED {name}: {n} separate solids (expected 1)")
    return errors


def color_partition(whole, by_color, tol=1e-3):
    """Color regions must tile the plate exactly: no two colors claim the same
    space (slicers resolve overlapping parts unpredictably), and nothing is
    left uncolored."""
    errors, lines = [], []
    names = list(by_color)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            v = overlap(by_color[a], by_color[b])
            if v > tol:
                errors.append(f"COLOR OVERLAP {a} x {b}: {v:.4f} mm^3")
    total = sum(s.volume for s in by_color.values())
    gap = whole.volume - total
    lines.append(f"color regions: {total:.1f} mm^3 of {whole.volume:.1f} mm^3 "
                 f"({len(names)} colors, {len(errors)} overlaps)")
    if abs(gap) > 0.01 * whole.volume / 100 + tol:   # 0.01 % slack for tessellation-free rounding
        errors.append(f"COLOR GAP: regions sum to {total:.3f} mm^3, plate is {whole.volume:.3f}")
    return errors, lines


def feature_report(p: Params):
    """Warn about features thinner than min_feature (XY) or off the layer grid (Z).

    This checks the *declared* feature sizes in params, not arbitrary geometry:
    a general thin-wall analysis of a B-rep is a project of its own.
    """
    xy = {
        "window_frame": p.window_frame,
        "transom_bar": p.transom_bar,
        "joint_width (engraved)": p.joint_width,
        "gate_neck": p.gate_neck,
    }
    z = {
        "wall_thickness": p.wall_thickness, "base_thickness": p.base_thickness,
        "prop_thickness": p.prop_thickness,
        "door_recess": p.door_recess, "window_frame_raise": p.window_frame_raise,
        "sign_raise": p.sign_raise, "cornice_raise": p.cornice_raise,
        "joint_depth": p.joint_depth, "curb_height": p.curb_height,
        "label_raise": p.label_raise,
        "rail_height": p.rail_height, "gate_height": p.gate_height,
        "color_depth": p.color_depth,
    }
    # Intentionally below the nozzle width: these are the fit features the
    # coupon exists to validate.
    fit = {"rib_height": p.rib_height, "detent_height": p.detent_height,
           "clearance": p.clearance, "prop_clearance": p.prop_clearance}

    lines = []
    for k, v in xy.items():
        if v < p.min_feature - 1e-9:
            lines.append(f"WARNING thin XY feature {k} = {v:.2f} mm < min_feature {p.min_feature}")
    for k, v in z.items():
        q = p.zq(v)
        if abs(q - v) > 1e-6:
            lines.append(f"note: {k} = {v:.3f} mm is not a whole number of "
                         f"{p.print_layer_height} mm layers; it will print as ~{q:.2f}")
    for k, v in fit.items():
        if v < p.nozzle:
            lines.append(f"note: {k} = {v:.2f} mm is below the {p.nozzle} mm nozzle "
                         f"(intentional fit feature; validate on the coupon)")
    return lines

