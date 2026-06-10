#!/usr/bin/env python3
"""CI check: ensure committed openapi.json matches the running FastAPI schema."""

import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMITTED_OPENAPI = REPO_ROOT / "openapi.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
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
