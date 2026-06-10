#!/usr/bin/env python3
"""Export FastAPI OpenAPI schema to openapi.json with deterministic ordering."""
import json
import sys
from pathlib import Path

# repo root is two levels up from this file
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from openubl.main import app

OPENAPI_PATH = REPO_ROOT / "openapi.json"


def main() -> None:
    schema = app.openapi()
    with open(OPENAPI_PATH, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    print(f"openapi.json exported to {OPENAPI_PATH}")


if __name__ == "__main__":
    main()
