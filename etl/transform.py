#!/usr/bin/env python3
"""Transform step placeholder."""

from __future__ import annotations

import argparse
import os
import sys


def configure_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("manifest", help="Path to manifest.json produced by the extract step.")
    return parser


def run_from_args(args: argparse.Namespace) -> None:
    manifest_path = os.path.abspath(args.manifest)
    if not os.path.exists(manifest_path):
        print(f"Error: manifest not found → {manifest_path}", file=sys.stderr)
        raise SystemExit(2)
    print("Transform step placeholder: no operations performed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Placeholder transform step (no-op).")
    configure_parser(parser)
    args = parser.parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
