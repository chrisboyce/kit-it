# Build everything into ./out. Works inside `nix develop` or from a plain shell.

# -X faulthandler: if OCCT (C++) crashes, print the Python stack instead of just "signal 11".
py := if env_var_or_default("IN_NIX_SHELL", "") == "" { "nix develop --command python -X faulthandler" } else { "python -X faulthandler" }

# build the kit (both modes) and the coupon
all: both coupon

# assembled model + interference check -> out/built_*.svg/png
built *ARGS:
    {{py}} view.py --mode built {{ARGS}}

# sprue plate -> out/kit.3mf, kit.stl, plate_top.svg/png
print *ARGS:
    {{py}} view.py --mode print {{ARGS}}

# both, plus a side-by-side view
both *ARGS:
    {{py}} view.py --mode both {{ARGS}}

# the Creative Corner building, all modes -> out/corner/
corner *ARGS:
    {{py}} view.py --kit corner --mode both {{ARGS}}

# the Colfax Market, all modes -> out/market/
market *ARGS:
    {{py}} view.py --kit market --mode both {{ARGS}}

# the Colfax caboose, all modes -> out/caboose/
caboose *ARGS:
    {{py}} view.py --kit caboose --mode both {{ARGS}}

# snap-fit test coupon -> out/coupon.3mf, coupon.stl
coupon *ARGS:
    {{py}} coupon.py {{ARGS}}

# a kit's go/no-go witness coupons, one per plate -> out/<kit>/witness*.3mf
witness KIT="nook" *ARGS:
    {{py}} witness.py --kit {{KIT}} {{ARGS}}

# just check + send the kit to the open viewer (no file output, faster)
show *ARGS:
    {{py}} view.py --mode both --no-export {{ARGS}}

# every kit together, built and flat, in the open viewer
showcase *ARGS:
    {{py}} view.py --kit all --mode both --no-export {{ARGS}}

# The viewer doesn't keep models for browser tabs opened later, so open the URL first.
# browser OCP viewer on :3939 (open the page, then `just show`)
viewer:
    @echo "Open http://127.0.0.1:3939/viewer in a browser, then run 'just show' in another terminal."
    {{py}} -m ocp_viewer

clean:
    rm -rf out
