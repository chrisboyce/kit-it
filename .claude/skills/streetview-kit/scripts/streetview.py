#!/usr/bin/env python3
"""Fetch Street View images of a building, for reference while designing a kit.

    streetview.py info URL_OR_PANO [--target LAT,LNG] [--out DIR]
    streetview.py grab --out DIR NAME:PANO:YAW:PITCH [...]
    streetview.py sweep URL_OR_PANO --out DIR
    streetview.py sheet OUT.jpg COLUMNS IMAGE [IMAGE ...]

This uses the thumbnail and metadata endpoints behind Google Maps. They need no API key,
but they're undocumented, so they can change or stop working, and they aren't a licensed
source. Keep images out of the repo, and fetch only what the design needs.
"""

import argparse
import json
import math
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

THUMB = ("https://streetviewpixels-pa.googleapis.com/v1/thumbnail?cb_client=maps_sv.tactile"
         "&w={w}&h={h}&pitch={pitch}&panoid={pano}&yaw={yaw}")
META = ("https://www.google.com/maps/photometa/v1?authuser=0&hl=en&gl=us"
        "&pb=!1m4!1smaps_sv.tactile!11m2!2m1!1b1!2m2!1sen!2sus!3m3!1m2!1e2!2s{pano}!4m6!1e1!1e2!1e3!1e4!1e8!1e6")
UA = "Mozilla/5.0"
# Requests above this come back at this size anyway, so asking for more only wastes a request.
MAX_W, MAX_H = 1024, 640
PANO_ID = r"[\w-]{22}"


def curl(url, out=None):
    cmd = ["curl", "-sSL", "-m", "40", "-A", UA]
    if out:
        cmd += ["-o", str(out)]
    return subprocess.run(cmd + [url], check=True, capture_output=True, text=not out).stdout


def resolve(link):
    """(pano, details from the URL). Takes a pano id, a Maps URL or a short share link."""
    if re.fullmatch(PANO_ID, link):
        return link, {}
    if "maps.app.goo.gl" in link or "goo.gl/maps" in link:
        link = subprocess.run(["curl", "-sSL", "-m", "40", "-A", UA, "-o", "/dev/null", "-w", "%{url_effective}", link],
                              check=True, capture_output=True, text=True).stdout
    text = urllib.parse.unquote(link)
    found = re.search(rf"panoid=({PANO_ID})", text) or re.search(rf"!1s({PANO_ID})!2e", text)
    if not found:
        raise SystemExit("No Street View panorama in that link. Open the building in Street View "
                         "(the yellow person view) and copy the URL from there.")
    details = {}
    if m := re.search(r"@(-?[\d.]+),(-?[\d.]+)", text):
        details["camera"] = (float(m[1]), float(m[2]))
    if m := re.search(r",([\d.]+)h,", text):
        details["yaw"] = float(m[1])
    if m := re.search(r",([\d.]+)t[/,]", text):
        details["pitch"] = round(90 - float(m[1]), 1)      # URL tilt: 90 is level, higher looks up
    if m := re.search(r"!3d(-?[\d.]+)!4d(-?[\d.]+)", text):
        details["pin"] = (float(m[1]), float(m[2]))        # the place's pin: can be a whole town
    return found[1], details


def panos(pano):
    """Metadata text and [(id, lat, lng, road heading)] for this panorama and its neighbors."""
    text = curl(META.format(pano=pano))
    pattern = rf'\[\[2,"({PANO_ID})"\],null,\[\[null,null,([\d.-]+),([\d.-]+)\],\[[^\]]*\],\[([\d.-]+)'
    seen, out = set(), []
    for m in re.finditer(pattern, text):
        if m[1] not in seen:
            seen.add(m[1])
            out.append((m[1], float(m[2]), float(m[3]), float(m[4])))
    return text, out


def offset(lat0, lng0, lat, lng):
    """Meters east and north, close enough at the scale of one building."""
    return (lng - lng0) * math.cos(math.radians(lat0)) * 111320, (lat - lat0) * 111320


def cmd_info(args):
    pano, details = resolve(args.link)
    text, near = panos(pano)
    if args.out:
        Path(args.out).mkdir(parents=True, exist_ok=True)
        (Path(args.out) / f"meta_{pano}.txt").write_text(text)
    print(f"panorama {pano}")
    for key, value in details.items():
        print(f"  {key}: {value}")
    if m := re.search(r'\[\["([^"]+)","[a-z]{2}"\],\["([^"]+)","[a-z]{2}"\]\]', text):
        print(f"  address: {m[1]}, {m[2]}")
    # Older imagery of the same spot comes first, and this panorama's own date last.
    if dates := re.findall(r"\[(20\d\d),(\d{1,2})\]", text):
        print(f"  captured: {dates[-1][0]}-{int(dates[-1][1]):02d} (the building may have changed since)")
        if len(dates) > 1:
            print("  older imagery from: " + ", ".join(y for y, _ in dates[:-1]))
    if not near:
        print("  no neighbors in the metadata")
        return
    target = tuple(map(float, args.target.split(","))) if args.target else None
    lat0, lng0 = near[0][1], near[0][2]
    head = f"{'pano':24}{'E m':>7}{'N m':>7}{'road':>6}"
    print(head + (f"{'to target':>11}{'dist m':>8}" if target else ""))
    for pid, lat, lng, heading in near:
        e, n = offset(lat0, lng0, lat, lng)
        row = f"{pid:24}{e:7.1f}{n:7.1f}{heading:6.0f}"
        if target:
            te, tn = offset(lat, lng, *target)
            row += f"{math.degrees(math.atan2(te, tn)) % 360:11.0f}{math.hypot(te, tn):8.1f}"
        print(row)


def grab(out, name, pano, yaw, pitch):
    path = Path(out) / f"{name}.jpg"
    curl(THUMB.format(w=MAX_W, h=MAX_H, pitch=pitch, pano=pano, yaw=yaw), path)
    time.sleep(0.2)
    if path.read_bytes()[:2] != b"\xff\xd8":
        raise SystemExit(f"{name}: got no image for pano {pano}")
    return path


def cmd_grab(args):
    Path(args.out).mkdir(parents=True, exist_ok=True)
    for spec in args.views:
        name, pano, yaw, pitch = spec.split(":")
        print(grab(args.out, name, pano, float(yaw), float(pitch)))


def cmd_sweep(args):
    """Eight compass views from one spot, level, to find out where things are."""
    pano, _ = resolve(args.link)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    files = [grab(args.out, f"sweep_{yaw:03d}", pano, yaw, 0) for yaw in range(0, 360, 45)]
    make_sheet(Path(args.out) / "sweep.jpg", 3, files)
    print(Path(args.out) / "sweep.jpg")


def make_sheet(out, cols, files, w=600, h=375):
    from PIL import Image, ImageDraw

    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), "white")
    for k, f in enumerate(files):
        im = Image.open(f).convert("RGB").resize((w, h))
        ImageDraw.Draw(im).text((6, 6), Path(f).stem, fill="yellow")
        sheet.paste(im, ((k % cols) * w, (k // cols) * h))
    sheet.save(out)


def cmd_sheet(args):
    make_sheet(args.out, args.cols, args.images)
    print(args.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("info", help="panorama details and neighbors")
    a.add_argument("link")
    a.add_argument("--target", help="LAT,LNG of the building: adds the yaw to it from each panorama")
    a.add_argument("--out")
    a.set_defaults(run=cmd_info)
    a = sub.add_parser("grab", help="download views, each NAME:PANO:YAW:PITCH (negative pitch looks UP)")
    a.add_argument("--out", required=True)
    a.add_argument("views", nargs="+")
    a.set_defaults(run=cmd_grab)
    a = sub.add_parser("sweep", help="eight compass views from one panorama, plus a contact sheet")
    a.add_argument("link")
    a.add_argument("--out", required=True)
    a.set_defaults(run=cmd_sweep)
    a = sub.add_parser("sheet", help="contact sheet with each image's name on it")
    a.add_argument("out")
    a.add_argument("cols", type=int)
    a.add_argument("images", nargs="+")
    a.set_defaults(run=cmd_sheet)
    args = ap.parse_args()
    args.run(args)


if __name__ == "__main__":
    sys.exit(main())
