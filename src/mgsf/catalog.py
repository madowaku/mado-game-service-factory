from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

VALID_STAGES = {"candidate", "incubation", "active", "retired"}


def load_catalog(path: str | Path) -> dict[str, Any]:
    catalog_path = Path(path)
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("catalog root must be a mapping")
    if data.get("version") != 1:
        raise ValueError("catalog version must be 1")

    services = data.get("services")
    if not isinstance(services, list):
        raise ValueError("services must be a list")

    seen: set[str] = set()
    for service in services:
        if not isinstance(service, dict):
            raise ValueError("each service must be a mapping")

        service_id = service.get("id")
        if not isinstance(service_id, str) or not service_id:
            raise ValueError("each service needs a non-empty id")
        if service_id in seen:
            raise ValueError(f"duplicate service id: {service_id}")
        seen.add(service_id)

        stage = service.get("stage")
        if stage not in VALID_STAGES:
            raise ValueError(f"invalid stage for {service_id}: {stage}")

    return data
