{
  description = "A curses command-line CSV and list (tabular data) viewer";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    systems = ["x86_64-linux" "i686-linux" "aarch64-linux"];
    forAllSystems = f:
      nixpkgs.lib.genAttrs systems (system:
        f {
          pkgs = nixpkgs.legacyPackages.${system};
        });
  in {
    devShells = forAllSystems ({pkgs}: {
      default = pkgs.mkShell {
        packages =
          [pkgs.gnumake]
          ++ builtins.attrValues {
            inherit
              (pkgs.python3Packages)
              python
              flake8
              ;
          };
        shellHook = ''
          alias tabview="python -m tabview"
          export PYTHONPATH="$PYTHONPATH:$PWD"
        '';
      };
    });
    packages = forAllSystems ({pkgs}: {
      default = pkgs.python3Packages.buildPythonApplication {
        pname = "tabview";
        version = builtins.head (builtins.match
          "__version__ = \"([^\"]+)\".*"
          (builtins.readFile ./tabview/__init__.py));
        pyproject = true;
        src = ./.;
        build-system = [pkgs.python3Packages.setuptools];
        # Run the test suite as part of the build. The integration tests use
        # curses, so they run under script(1) for a pty.
        nativeCheckInputs = [pkgs.util-linux];
        checkPhase = ''
          runHook preCheck
          TERM=xterm script -qec "python -W error -m unittest discover -v" /dev/null
          runHook postCheck
        '';
        pythonImportsCheck = ["tabview"];
        meta = {
          description = "A curses command-line CSV and list (tabular data) viewer";
          homepage = "https://github.com/TabViewer/tabview";
          license = pkgs.lib.licenses.mit;
          maintainers = ["firecat53"];
          mainProgram = "tabview";
          platforms = systems;
        };
      };
    });
  };
}
