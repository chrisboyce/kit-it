"""Headless output: hidden-line SVG projections (+ PNG via rsvg-convert), 3MF, STL."""

import shutil
import socket
import subprocess
from pathlib import Path

from build123d import ExportSVG, LineType, Mesher, Unit, Vector, export_stl

VIEWER_PORT = 3939  # ocp_vscode / ocp_viewer default
VIEWER_URL = f"http://127.0.0.1:{VIEWER_PORT}/viewer"

VIEWS = {
    #        direction toward the camera, camera up
    "iso":   ((-1.0, -1.6, 1.1), (0, 0, 1)),
    "front": ((0, -1, 0), (0, 0, 1)),
    "top":   ((0, 0, 1), (0, 1, 0)),
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


def export_mesh(shape, stem: Path):
    """stem.3mf (preferred by modern slicers) and stem.stl."""
    m = Mesher(unit=Unit.MM)
    m.add_shape(shape)
    m.write(str(stem.with_suffix(".3mf")))
    export_stl(shape, str(stem.with_suffix(".stl")))


def viewer_available(port=VIEWER_PORT) -> bool:
    """ocp_vscode.show() silently does nothing when no viewer is listening,
    so check the port ourselves."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def show(objs, names):
    from ocp_vscode import set_port, show as ocp_show
    set_port(VIEWER_PORT)
    ocp_show(*objs, names=names)
