"""Source-integrity and offline-boundary tests for Sakuga Interaction Lab M0.1.

These tests do not claim visual, mobile, keyboard or screen-reader verification.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

LAB = Path(__file__).resolve().parents[1] / "services" / "incubation" / "sakuga-interaction"
EXPECTED_GIT_BLOBS = {
    "button.js": "193839309385ae7769e663cacd1f64f0be588781",
    "checkbox.js": "6305d6c181210392261572f06c8bf57e21b30160",
    "progress.js": "6c42866f7f94c1fbf55925e37867ab6fe8685715",
    "LICENSE": "bf2147a1d5a077081d8e9e4492f5510a007f0717",
}


def _git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def test_vendor_is_byte_identical_to_reviewed_upstream() -> None:
    for filename, blob_sha in EXPECTED_GIT_BLOBS.items():
        data = (LAB / "vendor" / filename).read_bytes()
        assert _git_blob_sha1(data) == blob_sha, filename


def test_demo_is_offline_and_clearly_labeled_as_simulation() -> None:
    html = (LAB / "index.html").read_text(encoding="utf-8")
    assert 'src="./vendor/button.js"' in html
    assert 'src="./vendor/checkbox.js"' in html
    assert 'src="./vendor/progress.js"' in html
    assert "https://" not in html and "http://" not in html
    assert "Simulation" in html
    assert "Human review" in html
    assert "no real QA passed" in html
    assert "sakuga:done" in html
    assert "role=\"status\"" in html
    assert "aria-live=\"polite\"" in html
    assert "demo attribute" not in html
    assert '<sakuga-progress id="progress"' in html
    assert '<sakuga-checkbox id="review" name="review"' in html
