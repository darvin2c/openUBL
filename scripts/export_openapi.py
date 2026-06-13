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
VERSION_TS_PATH = REPO_ROOT / "sdk" / "typescript" / "src" / "version.ts"

VERSION_TS_TEMPLATE = '''export const SDK_VERSION = "{version}";

export async function checkApiVersion(
  baseUrl: string = "http://localhost:8000"
): Promise<{{ ok: boolean; sdkVersion: string; apiVersion: string }}> {{
  const res = await fetch(`${{baseUrl}}/api/v1/version`);
  if (!res.ok) {{
    throw new Error(`Failed to fetch API version: ${{res.status}}`);
  }}
  const {{ version }} = (await res.json()) as {{ version: string }};
  return {{ ok: version === SDK_VERSION, sdkVersion: SDK_VERSION, apiVersion: version }};
}}
'''


def write_version_ts(version: str) -> None:
    VERSION_TS_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERSION_TS_PATH.write_text(VERSION_TS_TEMPLATE.format(version=version), encoding="utf-8")
    print(f"version.ts exported to {VERSION_TS_PATH}")


def main() -> None:
    schema = app.openapi()
    with open(OPENAPI_PATH, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    print(f"openapi.json exported to {OPENAPI_PATH}")

    version = schema.get("info", {}).get("version", "")
    if version:
        write_version_ts(version)


if __name__ == "__main__":
    main()
