# Build everything into ./out. Works inside `nix develop` or from a plain shell.

py := if env_var_or_default("IN_NIX_SHELL", "") == "" { "nix develop --command python" } else { "python" }

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

# snap-fit test coupon -> out/coupon.3mf, coupon.stl
coupon *ARGS:
    {{py}} coupon.py {{ARGS}}

# browser-based OCP viewer on :3939 (view.py sends models to it when it's running)
viewer:
    {{py}} -m ocp_viewer

clean:
    rm -rf out
