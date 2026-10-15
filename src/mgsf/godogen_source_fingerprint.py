"""Bounded source fingerprint for cross-run Godogen evidence binding."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json

PATH_EXCLUDES = {".git", ".godot", ".mgsf", "bin", "obj", "screenshots", "assets", ".agents", ".claude"}
SOURCE_EXTENSIONS = {".cs", ".csproj", ".tscn", ".gd", ".godot"}
MAX_SOURCE_FILES = 512
MAX_SOURCE_BYTES = 16 * 1024 * 1024


class SourceFingerprintError(ValueError):
    pass


def fingerprint_project(project: str | Path) -> dict:
    root = Path(project).resolve()
    if not root.is_dir() or not (root / "project.godot").is_file():
        raise SourceFingerprintError("Godot project.godot not found")
    paths = []
    for file in root.rglob("*"):
        rel = file.relative_to(root)
        if any(part in PATH_EXCLUDES for part in rel.parts):
            continue
        if file.is_symlink():
            raise SourceFingerprintError("linked source files are not allowed")
        if not file.is_file() or (file.suffix not in SOURCE_EXTENSIONS and file.name != "project.godot"):
            continue
        paths.append(file)
    if len(paths) > MAX_SOURCE_FILES:
        raise SourceFingerprintError("too many source files to fingerprint")
    total = sum(file.stat().st_size for file in paths)
    if total > MAX_SOURCE_BYTES:
        raise SourceFingerprintError("source inventory size limit exceeded")
    names = {file.relative_to(root).as_posix() for file in paths}
    if "project.godot" not in names or not any(p.endswith(".csproj") for p in names) or not any(
        p.endswith(".cs") for p in names
    ) or not any(p.endswith(".tscn") for p in names):
        raise SourceFingerprintError("C# Godot project, script and scene sources required")
    hashes = {file.relative_to(root).as_posix(): sha256(file.read_bytes()).hexdigest()
              for file in sorted(paths)}
    canonical = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return {
        "algorithm": "sha256-sorted-source-files-v1",
        "files": hashes,
        "digest": sha256(canonical).hexdigest(),
        "bytes": total,
    }
