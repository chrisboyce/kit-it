"""Headless output: hidden-line SVG projections (+ PNG via rsvg-convert), shaded
color previews, 3MF (single and multi-material) and STL."""

import copy
import json
import shutil
import socket
import subprocess
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from build123d import ExportSVG, LineType, Mesher, Unit, Vector, export_stl

VIEWER_PORT = 3939  # ocp_vscode / ocp_viewer default
VIEWER_URL = f"http://127.0.0.1:{VIEWER_PORT}/viewer"

VIEWS = {
    #        direction toward the camera, camera up
    "iso":   ((-1.0, -1.6, 1.1), (0, 0, 1)),
    "front": ((0, -1, 0), (0, 0, 1)),
    "top":   ((0, 0, 1), (0, 1, 0)),
    "right": ((1, 0, 0), (0, 0, 1)),
    "corner": ((1.0, -1.5, 0.75), (0, 0, 1)),  # from the +x,-y corner, as seen from the street
}


def projection(shape, path: Path, view: str, hidden=True):
    """Write `path` (.svg) and a matching .png of `shape` seen from `view`."""
    direction, up = VIEWS[view]
    bb = shape.bounding_box()
    center = bb.center()
    origin = center + Vector(*direction).normalized() * (bb.diagonal * 4)
    visible, hidden_edges = shape.project_to_viewport(origin, up, center)

    svg = ExportSVG(margin=4, line_weight=0.18)
    svg.add_layer("hidden", line_color=0xAFAFAF, line_type=LineType.ISO_DOT,
                  line_weight=0.1)
    svg.add_layer("visible", line_color=0x141414)
    if hidden and hidden_edges:
        svg.add_shape(hidden_edges, layer="hidden")
    svg.add_shape(visible, layer="visible")
    svg.write(str(path))
    to_png(path)
    return path


def to_png(svg_path: Path, width=1600):
    exe = shutil.which("rsvg-convert")
    if not exe:
        print(f"  (no rsvg-convert on PATH; skipping {svg_path.with_suffix('.png').name})")
        return
    subprocess.run([exe, "-b", "white", "-w", str(width), "-o",
                    str(svg_path.with_suffix(".png")), str(svg_path)], check=True)


def export_mesh(shape, stem: Path, formats=("3mf", "stl")):
    """Single-material stem.3mf (preferred by modern slicers) and/or stem.stl."""
    if "3mf" in formats:
        m = Mesher(unit=Unit.MM)
        m.add_shape(shape)
        m.write(str(stem.with_suffix(".3mf")))
    if "stl" in formats:
        export_stl(shape, str(stem.with_suffix(".stl")))


def viewer_available(port=VIEWER_PORT) -> bool:
    """ocp_vscode.show() silently does nothing when no viewer is listening,
    so check the port ourselves."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def show(objs, names, colors=None):
    from ocp_vscode import set_port, show as ocp_show
    set_port(VIEWER_PORT)
    ocp_show(*objs, names=names, colors=colors)


# ---------------------------------------------------------------------------
# Multi-material
# ---------------------------------------------------------------------------
def _rgb(hexcolor):
    h = hexcolor.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# Orca only reads per-part filaments from a project written by Bambu Studio or
# itself. It rejects tags newer than it is, so this is deliberately old.
PROJECT_APP = "BambuStudio-01.10.00.00"
_3MF_NS = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
           'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
           'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
           'requiredextensions="p" unit="millimeter" xml:lang="en-US"')
_3MF_REL = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            ' <Relationship Target="{}" Id="rel-1" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
            '</Relationships>\n')
_3MF_TYPES = ('<?xml version="1.0" encoding="UTF-8"?>\n'
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
              ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
              ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
              '</Types>\n')


def export_color_3mf(regions, path: Path, filaments, bed=(220.0, 220.0), object_name="kit"):
    """One object made of one part per filament, as a slicer project, so it opens
    with each part already on its own filament (see "Slicing on the U1" in the README).

    regions: [(color name, tool number, hex, solid)]. All parts share one
    coordinate frame, so they stay registered, and each is named "T<n> <color>".
    filaments: hex for T1, T2, ..., including tools with no part on this plate, so
    a tool number means the same filament in every part name and in the slicer.
    bed: (x, y). Projects keep positions, so the plate is centered on it.
    """
    parts, lo, hi = [], [float("inf")] * 3, [float("-inf")] * 3
    for i, (name, tool, _, solid) in enumerate(regions, 1):
        # Mesher has no public "mesh this into my own object" call; these two
        # static helpers are what add_shape() uses internally.
        verts, tris = Mesher._mesh_shape(copy.deepcopy(solid), 0.001, 0.1)
        v3, t3 = Mesher._create_3mf_mesh(verts, tris)
        coords = [tuple(v.Coordinates) for v in v3]
        for axis, values in enumerate(zip(*coords)):
            lo[axis], hi[axis] = min(lo[axis], *values), max(hi[axis], *values)
        vs = "\n".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in coords)
        ts = "\n".join('<triangle v1="{}" v2="{}" v3="{}"/>'.format(*t.Indices) for t in t3)
        parts.append((i, tool, f"T{tool} {name}",
                      f'<mesh><vertices>\n{vs}\n</vertices><triangles>\n{ts}\n</triangles></mesh>'))

    meshes = "\n".join(f'  <object id="{i}" p:UUID="{uuid.uuid4()}" type="model">{mesh}</object>'
                       for i, _, _, mesh in parts)
    sub = (f'<?xml version="1.0" encoding="UTF-8"?>\n<model {_3MF_NS}>\n'
           f' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
           f' <resources>\n{meshes}\n </resources>\n <build/>\n</model>\n')

    obj = len(parts) + 1
    comps = "\n".join(f'    <component p:path="/3D/Objects/object_1.model" objectid="{i}" '
                      f'p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
                      for i, *_ in parts)
    dx, dy = (bed[a] / 2 - (lo[a] + hi[a]) / 2 for a in (0, 1))
    title = escape(object_name)
    root = (f'<?xml version="1.0" encoding="UTF-8"?>\n<model {_3MF_NS}>\n'
            f' <metadata name="Application">{PROJECT_APP}</metadata>\n'
            f' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
            f' <metadata name="Title">{title}</metadata>\n'
            f' <resources>\n  <object id="{obj}" p:UUID="{uuid.uuid4()}" type="model">\n'
            f'   <components>\n{comps}\n   </components>\n  </object>\n </resources>\n'
            f' <build p:UUID="{uuid.uuid4()}">\n'
            f'  <item objectid="{obj}" p:UUID="{uuid.uuid4()}" '
            f'transform="1 0 0 0 1 0 0 0 1 {dx:.4f} {dy:.4f} {-lo[2]:.4f}" printable="1"/>\n'
            f' </build>\n</model>\n')

    part_cfg = "\n".join(
        f'    <part id="{i}" subtype="normal_part">\n'
        f'      <metadata key="name" value="{escape(label)}"/>\n'
        f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
        f'      <metadata key="extruder" value="{tool}"/>\n'
        f'    </part>' for i, tool, label, _ in parts)
    # Without the model_instance, the slicer treats the plate as empty.
    settings = (f'<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  <object id="{obj}">\n'
                f'    <metadata key="name" value="{title}"/>\n{part_cfg}\n  </object>\n'
                f'  <plate>\n    <metadata key="plater_id" value="1"/>\n'
                f'    <metadata key="plater_name" value="{title}"/>\n'
                f'    <metadata key="locked" value="false"/>\n'
                f'    <model_instance>\n      <metadata key="object_id" value="{obj}"/>\n'
                f'      <metadata key="instance_id" value="0"/>\n'
                f'      <metadata key="identify_id" value="{1000 + obj}"/>\n    </model_instance>\n'
                f'  </plate>\n  <assemble>\n  </assemble>\n</config>\n')

    # Only the filament list: the printer and print settings stay the slicer's own.
    project = {"filament_colour": [h.upper() for h in filaments],
               "filament_type": ["PLA"] * len(filaments)}

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _3MF_TYPES)
        z.writestr("_rels/.rels", _3MF_REL.format("/3D/3dmodel.model"))
        z.writestr("3D/3dmodel.model", root)
        z.writestr("3D/_rels/3dmodel.model.rels", _3MF_REL.format("/3D/Objects/object_1.model"))
        z.writestr("3D/Objects/object_1.model", sub)
        z.writestr("Metadata/model_settings.config", settings)
        z.writestr("Metadata/project_settings.config", json.dumps(project, indent=1))


def export_color_stls(regions, stem: Path):
    """stem_T1_brick.stl, ... : load them together as one multi-part object."""
    out = []
    for name, tool, _, solid in regions:
        f = stem.parent / f"{stem.name}_T{tool}_{name}.stl"
        export_stl(solid, str(f))
        out.append(f)
    return out


def color_preview(items, path: Path, view="iso", width=1600, height=1200):
    """Flat-shaded color render of [(solid, hex)], headless.

    A tiny orthographic z-buffer rasterizer in numpy: correct occlusion (unlike
    painter's-algorithm plotting), no GL, no extra dependencies. Outlines are
    drawn where depth jumps, so edges read like the line drawings.
    """
    import numpy as np

    d = np.array(VIEWS[view][0], dtype=float)
    d /= np.linalg.norm(d)                              # toward camera
    up = np.array(VIEWS[view][1], dtype=float)
    right = np.cross(up, d)
    right /= np.linalg.norm(right)
    up = np.cross(d, right)
    light = d + np.array([0.35, -0.25, 0.7])
    light /= np.linalg.norm(light)

    tris, cols = [], []
    for solid, hexcolor in items:
        verts, faces = solid.tessellate(0.05, 0.3)
        v = np.array([(x.X, x.Y, x.Z) for x in verts])
        f = np.array(faces)
        t = v[f]                                         # (n, 3, 3)
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        shade = 0.5 + 0.5 * np.abs(n @ light)            # two-sided
        base = np.array(_rgb(hexcolor), dtype=float)
        tris.append(t)
        cols.append(np.clip(base[None, :] * shade[:, None], 0, 255))
    tris, cols = np.concatenate(tris), np.concatenate(cols)

    # Project: screen x/y in model units, depth = toward the camera.
    sx, sy, sz = tris @ right, tris @ up, tris @ d
    margin = 0.05
    xmin, xmax, ymin, ymax = sx.min(), sx.max(), sy.min(), sy.max()
    scale = (1 - 2 * margin) * min(width / (xmax - xmin), height / (ymax - ymin))
    px = (sx - (xmin + xmax) / 2) * scale + width / 2
    py = height / 2 - (sy - (ymin + ymax) / 2) * scale

    img = np.full((height, width, 3), 255.0)
    zbuf = np.full((height, width), -np.inf)
    for i in range(len(tris)):
        x, y, z = px[i], py[i], sz[i]
        x0, x1 = max(int(x.min()), 0), min(int(x.max()) + 1, width - 1)
        y0, y1 = max(int(y.min()), 0), min(int(y.max()) + 1, height - 1)
        if x0 > x1 or y0 > y1:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(den) < 1e-12:
            continue
        a = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / den
        b = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / den
        c = 1 - a - b
        inside = (a >= -1e-6) & (b >= -1e-6) & (c >= -1e-6)
        depth = a * z[0] + b * z[1] + c * z[2]
        win = zbuf[y0:y1 + 1, x0:x1 + 1]
        hit = inside & (depth > win)
        win[hit] = depth[hit]
        img[y0:y1 + 1, x0:x1 + 1][hit] = cols[i]

    # Outlines where depth jumps by more than ~0.25 mm. Second differences, since a
    # plane seen at a steep angle changes depth by more than that on every pixel.
    z = np.where(np.isfinite(zbuf), zbuf, zbuf[np.isfinite(zbuf)].min() - 10)
    jump = 0.25   # model units (mm)
    edge = np.zeros_like(z, dtype=bool)
    edge[:, 1:-1] |= np.abs(np.diff(z, n=2, axis=1)) > jump
    edge[1:-1, :] |= np.abs(np.diff(z, n=2, axis=0)) > jump
    img[edge] *= 0.35
    _write_png(path, img.astype(np.uint8))
    return path


def _write_png(path, rgb):
    """Minimal PNG writer (8-bit RGB), so previews need nothing beyond numpy."""
    import struct
    import zlib

    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[r].tobytes() for r in range(h))

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 6)))
        f.write(chunk(b"IEND", b""))
