{
  description = "PrintableColfax: HO-scale snap-together storefront kits (build123d)";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (s: f nixpkgs.legacyPackages.${s});
    in {
      devShells = forAll (pkgs:
        let
          # build123d/OCP are not in nixpkgs, so we use the PyPI manylinux wheels
          # in a venv. These are the only shared libs those wheels link against
          # that a NixOS box can't find on its own (checked with ldd).
          wheelLibs = with pkgs; [ stdenv.cc.cc.lib zlib expat libx11 libGL ];
        in {
          default = pkgs.mkShell {
            packages = with pkgs; [
              python312   # cadquery-ocp wheels exist for 3.12
              just        # task runner (justfile)
              librsvg     # rsvg-convert: SVG -> PNG for headless previews
              dejavu_fonts
            ];
            LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath wheelLibs;
            # Pin the label font so embossed text is identical on every machine.
            COLFAX_FONT = "${pkgs.dejavu_fonts}/share/fonts/truetype/DejaVuSans-Bold.ttf";
            shellHook = ''
              # (Re)create the venv if missing or if the Nix python it points at changed.
              if ! .venv/bin/python -c "" 2>/dev/null; then
                rm -rf .venv && python -m venv .venv
              fi
              source .venv/bin/activate
              if [ ! -f .venv/.stamp ] || [ requirements.txt -nt .venv/.stamp ]; then
                echo "Installing Python deps into .venv (first run downloads ~1 GB of OCP wheels)..."
                pip install -q --upgrade pip && pip install -q -r requirements.txt && touch .venv/.stamp
              fi
            '';
          };
        });
    };
}
