#!/usr/bin/env python3
"""CI check: ensure committed openapi.json matches the running FastAPI schema
and all version sources are synchronized."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMITTED_OPENAPI = REPO_ROOT / "openapi.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract_python_init_version(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]*)"', content, re.MULTILINE)
    if not match:
        raise ValueError(f"No __version__ found in {path}")
    return match.group(1)


def _extract_python_main_version(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    match = re.search(r'version="([^"]*)"', content)
    if not match:
        raise ValueError(f"No version= found in {path}")
    return match.group(1)


def _extract_pyproject_version(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]*)"', content, re.MULTILINE)
    if not match:
        raise ValueError(f"No version found in {path}")
    return match.group(1)


def _extract_package_json_version(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("version", "")


def _extract_ts_version(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    match = re.search(r'export const SDK_VERSION = "([^"]*)"', content)
    if not match:
        raise ValueError(f"No SDK_VERSION found in {path}")
    return match.group(1)


def _extract_openapi_version(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("info", {}).get("version", "")


def check_all_versions_match() -> list[str]:
    """Return a list of mismatch messages (empty if all match)."""
    sources = {
        "src/openubl/__init__.py": _extract_python_init_version(REPO_ROOT / "src" / "openubl" / "__init__.py"),
        "src/openubl/main.py": _extract_python_main_version(REPO_ROOT / "src" / "openubl" / "main.py"),
        "pyproject.toml": _extract_pyproject_version(REPO_ROOT / "pyproject.toml"),
        "package.json": _extract_package_json_version(REPO_ROOT / "package.json"),
        "sdk/typescript/package.json": _extract_package_json_version(REPO_ROOT / "sdk" / "typescript" / "package.json"),
        "sdk/typescript/src/version.ts": _extract_ts_version(REPO_ROOT / "sdk" / "typescript" / "src" / "version.ts"),
        "openapi.json": _extract_openapi_version(REPO_ROOT / "openapi.json"),
    }

    versions = set(sources.values())
    if len(versions) == 1:
        return []

    mismatches = []
    expected = next(iter(sources.values()))
    for path, version in sources.items():
        if version != expected:
            mismatches.append(f"  MISMATCH {path}: {version} (expected {expected})")
    return mismatches


def main() -> int:
    mismatches = check_all_versions_match()
    if mismatches:
        print("ERROR: version sources are out of sync:")
        for m in mismatches:
            print(m)
        return 1

    print("OK: all version sources are synchronized.")

    before = file_hash(COMMITTED_OPENAPI)

    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "export_openapi.py")],
        check=True,
    )

    after = file_hash(COMMITTED_OPENAPI)

    if before != after:
        print("ERROR: openapi.json is stale. Run: uv run python scripts/export_openapi.py")
        return 1

    print("OK: openapi.json is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
