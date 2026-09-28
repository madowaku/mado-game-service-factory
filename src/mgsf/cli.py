from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import load_catalog
from .gameplay_capture import run_capture_playtest, run_gameplay_capture
from .playtest_report import run_playtest_report
from .real_game_bridge import run_real_game_bridge, run_real_game_dogfood


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

    capture = sub.add_parser(
        "gameplay-capture",
        help="Package gameplay media and timeline into integrity-checked evidence",
    )
    capture.add_argument(
        "capture_root",
        type=Path,
        help="capture directory containing capture.json, timeline.jsonl, and media",
    )
    capture.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence"),
        help="root directory for gameplay capture evidence",
    )

    capture_report = sub.add_parser(
        "capture-playtest-report",
        help="Package gameplay capture evidence and turn captured friction into a playtest report",
    )
    capture_report.add_argument(
        "capture_root",
        type=Path,
        help="capture directory containing capture.json, timeline.jsonl, and media",
    )
    capture_report.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence"),
        help="root directory for capture and report evidence",
    )

    bridge = sub.add_parser(
        "real-game-bridge",
        help="Bridge recorded real-project headless evidence into an MGEL bundle",
    )
    bridge.add_argument("record", type=Path, help="recorded real-game contract JSON")
    bridge.add_argument("runtime_log", type=Path, help="recorded runtime log")
    bridge.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence"),
        help="root directory for bridge evidence",
    )

    dogfood = sub.add_parser(
        "dogfood-playtest-report",
        help="Run real-game bridge and feed the result into playtest-report",
    )
    dogfood.add_argument("record", type=Path, help="recorded real-game contract JSON")
    dogfood.add_argument("runtime_log", type=Path, help="recorded runtime log")
    dogfood.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence"),
        help="root directory for bridge and service evidence",
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

    if args.command == "gameplay-capture":
        result = run_gameplay_capture(args.capture_root, args.output_root)
        print(f"Capture evidence: {result.root}")
        print(
            f"service=gameplay-capture media={result.media_count} "
            f"events={result.event_count} eval={result.eval_status}"
        )
        return 0 if result.eval_status == "PASS" else 1

    if args.command == "capture-playtest-report":
        result = run_capture_playtest(args.capture_root, args.output_root)
        print(f"Capture evidence: {result.capture.root}")
        print(f"MGEL bridge: {result.mgel_root}")
        print(f"Playtest report: {result.report_root}")
        print(
            f"capture-playtest findings={result.finding_count} "
            f"eval={result.status}"
        )
        return 0 if result.status == "PASS" else 1

    if args.command == "real-game-bridge":
        result = run_real_game_bridge(args.record, args.runtime_log, args.output_root)
        print(f"Bridge evidence: {result.root}")
        print(f"MGEL bundle: {result.mgel_root}")
        print(f"bridge=real-game-bridge eval={result.eval_status}")
        return 0 if result.eval_status == "PASS" else 1

    if args.command == "dogfood-playtest-report":
        result = run_real_game_dogfood(
            args.record,
            args.runtime_log,
            args.output_root,
        )
        print(f"Bridge evidence: {result.bridge.root}")
        print(f"Playtest report: {result.report_root}")
        print(
            f"dogfood=playtest-report findings={result.finding_count} "
            f"eval={result.status}"
        )
        return 0 if result.status == "PASS" else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
