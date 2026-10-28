"""Command-line entry point: ``processkit-pfd spec.yaml -o diagram.svg``."""

from __future__ import annotations

import argparse
import sys

from .model import Flowsheet, render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="processkit-pfd", description="Render a process flow diagram from YAML.")
    parser.add_argument("spec", help="path to the YAML flowsheet specification")
    parser.add_argument("-o", "--output", default="pfd.svg", help="output file (format from extension; default pfd.svg)")
    parser.add_argument("--dot", action="store_true", help="print the Graphviz DOT source to stdout instead of rendering")
    args = parser.parse_args(argv)

    try:
        flowsheet = Flowsheet.from_yaml(args.spec)
        if args.dot:
            sys.stdout.write(flowsheet.to_dot())
            return 0
        out = render(flowsheet, args.output)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
