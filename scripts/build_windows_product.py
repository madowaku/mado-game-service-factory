from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from mgsf.gameplay_capture import run_capture_playtest
from mgsf.product_cli import PRODUCT_NAME, PRODUCT_VERSION


ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = ROOT / "build" / "windows-product"
DIST_DIR = ROOT / "dist"
PRODUCT_DIR = BUILD_ROOT / f"MADO-Playtest-Evidence-{PRODUCT_VERSION}-win-x64"
ZIP_PATH = DIST_DIR / f"MADO-Playtest-Evidence-{PRODUCT_VERSION}-win-x64.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def git_head() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()
    except Exception:
        return os.environ.get("GITHUB_SHA", "unknown")


def run_pyinstaller() -> Path:
    work = BUILD_ROOT / "pyinstaller-work"
    spec = BUILD_ROOT / "pyinstaller-spec"
    out = BUILD_ROOT / "pyinstaller-dist"
    for directory in (work, spec, out):
        directory.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "mado-playtest",
        "--paths",
        str(ROOT / "src"),
        "--distpath",
        str(out),
        "--workpath",
        str(work),
        "--specpath",
        str(spec),
        str(ROOT / "packaging" / "windows" / "entrypoint.py"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    exe = out / "mado-playtest.exe"
    if not exe.is_file():
        raise RuntimeError(f"PyInstaller output missing: {exe}")
    return exe


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def build_sample_report() -> None:
    sample_capture = PRODUCT_DIR / "examples" / "sample-capture"
    evidence_root = BUILD_ROOT / "sample-evidence-build"
    if evidence_root.exists():
        shutil.rmtree(evidence_root)
    result = run_capture_playtest(sample_capture, evidence_root)
    if result.status != "PASS":
        raise RuntimeError("bundled sample did not pass capture-playtest eval")

    sample_report = PRODUCT_DIR / "examples" / "sample-report"
    sample_report.mkdir(parents=True, exist_ok=True)
    for name in ("report.md", "report.json", "eval.json"):
        shutil.copy2(result.report_root / name, sample_report / name)


def build_notices_snapshot() -> dict[str, str]:
    versions: dict[str, str] = {}
    for distribution in ("PyYAML", "pyinstaller"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "not-installed"
    return versions


def write_manifest() -> None:
    files = []
    for path in sorted(PRODUCT_DIR.rglob("*")):
        if path.is_file() and path.name != "RELEASE-MANIFEST.json":
            files.append(
                {
                    "path": path.relative_to(PRODUCT_DIR).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )

    manifest = {
        "product": PRODUCT_NAME,
        "version": PRODUCT_VERSION,
        "platform": "windows-x64",
        "source_sha": git_head(),
        "python": sys.version.split()[0],
        "build_dependencies": build_notices_snapshot(),
        "files": files,
    }
    (PRODUCT_DIR / "RELEASE-MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def make_zip() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    import zipfile

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(PRODUCT_DIR.rglob("*")):
            if not path.is_file():
                continue
            relative = Path(PRODUCT_DIR.name) / path.relative_to(PRODUCT_DIR)
            info = zipfile.ZipInfo(relative.as_posix())
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    if os.name != "nt":
        raise SystemExit("Windows product pack must be built on Windows.")

    if PRODUCT_DIR.exists():
        shutil.rmtree(PRODUCT_DIR)
    PRODUCT_DIR.mkdir(parents=True)

    exe = run_pyinstaller()
    shutil.copy2(exe, PRODUCT_DIR / "mado-playtest.exe")

    for filename in (
        "README.txt",
        "PRIVACY.txt",
        "PRODUCT_LICENSE.txt",
        "THIRD_PARTY_NOTICES.txt",
        "SUPPORT.txt",
        "RELEASE_NOTES.txt",
    ):
        shutil.copy2(ROOT / "product" / filename, PRODUCT_DIR / filename)

    sample_source = ROOT / "fixtures" / "gameplay-capture" / "vertical-slice-reconstruction"
    copy_tree(sample_source, PRODUCT_DIR / "examples" / "sample-capture")
    build_sample_report()
    write_manifest()
    make_zip()

    print(f"PRODUCT_DIR={PRODUCT_DIR}")
    print(f"ZIP_PATH={ZIP_PATH}")
    print(f"ZIP_SHA256={sha256(ZIP_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
