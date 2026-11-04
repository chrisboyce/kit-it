"""Reuse a kit's last good build, so showing it again doesn't mean rebuilding it.

An entry holds the colored solids the viewer needs, as BREP files, plus whether that
build also wrote its exports. It's used only if nothing that could change the result has
changed: the code, the parameters, the mode, the libraries or the font. The fingerprint
covers every source file, not only the kit's, so an edit anywhere means a rebuild. That's
coarse, but it can't show a stale model.

Only builds that passed their checks are saved, so a failing kit reports its errors every
time. Entries live in the output folder, so clearing that clears them with the files
they vouch for.
"""

import hashlib
import json
import os
import shutil
from pathlib import Path

import build123d
from build123d import export_brep, import_brep

ROOT = Path(__file__).parent
OTHER_INPUTS = ("requirements.txt", "flake.lock")
FORMAT = 1                  # bump if an entry's layout changes


def fingerprint(kit, mode, p):
    h = hashlib.sha256()
    for f in sorted(ROOT.glob("*.py")) + [ROOT / n for n in OTHER_INPUTS if (ROOT / n).exists()]:
        h.update(f.name.encode())
        h.update(f.read_bytes())
    # repr(p) is every parameter, with any --set overrides applied.
    for part in (FORMAT, kit, mode, repr(p), build123d.__version__, os.environ.get("COLFAX_FONT")):
        h.update(repr(part).encode())
    return h.hexdigest()[:16]


def _entry(out, mode, key):
    return Path(out) / ".cache" / f"{mode}-{key}"


def load(out, mode, key, need_exports):
    """[(name, solid, hex)], or None if there's no usable entry."""
    folder = _entry(out, mode, key)
    try:
        manifest = json.loads((folder / "manifest.json").read_text())
    except (OSError, ValueError):
        return None
    if need_exports and not manifest["exported"]:
        return None
    return [(o["name"], import_brep(str(folder / o["file"])), o["hex"]) for o in manifest["objects"]]


def save(out, mode, key, shown, exported):
    """Replaces this mode's older entries. It writes to a temporary folder first, so an
    interrupted run can't leave a partial entry that looks complete."""
    cache = Path(out) / ".cache"
    folder = _entry(out, mode, key)
    tmp = folder.with_name(folder.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    objects = []
    for i, (name, solid, hexcolor) in enumerate(shown):
        file = f"{i:04d}.brep"
        export_brep(solid, str(tmp / file))
        objects.append({"name": name, "file": file, "hex": hexcolor})
    (tmp / "manifest.json").write_text(json.dumps({"exported": exported, "objects": objects}))
    for old in cache.glob(f"{mode}-*"):
        if old != tmp:
            shutil.rmtree(old)
    tmp.rename(folder)
