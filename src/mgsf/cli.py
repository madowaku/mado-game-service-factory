from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import load_catalog


def _catalog_path(value: str | None) -> Path:
    return Path(value or "catalog/services.yaml")


def main() -> int:
    parser = argparse.ArgumentParser(prog="mgsf")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-catalog", help="Validate the service catalog")
    validate.add_argument("--path")

    listing = sub.add_parser("list", help="List services")
    listing.add_argument("--path")
    listing.add_argument("--stage")

    args = parser.parse_args()
    catalog = load_catalog(_catalog_path(args.path))

    if args.command == "validate-catalog":
        print(f"catalog ok: {len(catalog['services'])} services")
        return 0

    services = catalog["services"]
    if args.stage:
        services = [s for s in services if s["stage"] == args.stage]

    for service in services:
        print(f"{service['id']}\t{service['stage']}\t{service['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
