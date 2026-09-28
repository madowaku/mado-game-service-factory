from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import load_catalog
from .playtest_report import run_playtest_report


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

    playtest = sub.add_parser(
        "playtest-report",
        help="Turn an MGEL M0 Evidence Bundle into an actionable playtest report",
    )
    playtest.add_argument("bundle", type=Path, help="MGEL Evidence Bundle directory")
    playtest.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence"),
        help="root directory for the service Evidence Bundle",
    )

    args = parser.parse_args()

    if args.command in {"validate-catalog", "list"}:
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

    if args.command == "playtest-report":
        result = run_playtest_report(args.bundle, args.output_root)
        print(f"Evidence bundle: {result.root}")
        print(
            f"service=playtest-report findings={result.finding_count} "
            f"eval={result.eval_status}"
        )
        return 0 if result.eval_status == "PASS" else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
