from pathlib import Path

import pytest

from mgsf.catalog import load_catalog


def test_repository_catalog_is_valid() -> None:
    catalog = load_catalog(Path("catalog/services.yaml"))
    assert catalog["version"] == 1
    assert len(catalog["services"]) >= 1


def test_duplicate_service_ids_fail(tmp_path: Path) -> None:
    path = tmp_path / "services.yaml"
    path.write_text(
        """
version: 1
services:
  - id: same
    name: A
    stage: candidate
  - id: same
    name: B
    stage: incubation
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate service id"):
        load_catalog(path)
