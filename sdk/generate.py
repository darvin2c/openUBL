#!/usr/bin/env python3
"""Orchestrate multi-language SDK generation from openapi.json."""

import shutil
import subprocess
import sys
from pathlib import Path

OPENAPI = Path(__file__).resolve().parent.parent / "openapi.json"
SDK_DIR = Path(__file__).resolve().parent

NPX = shutil.which("npx") or shutil.which("npx.cmd") or "npx"

GENERATORS = {
    "typescript": [
        NPX,
        "openapi-typescript",
        str(OPENAPI),
        "--output",
        str(SDK_DIR / "typescript" / "src" / "openubl-types.ts"),
    ],
    "java": [
        NPX,
        "@openapitools/openapi-generator-cli",
        "generate",
        "-i",
        str(OPENAPI),
        "-g",
        "java",
        "--library",
        "native",
        "-o",
        str(SDK_DIR / "java"),
    ],
    "go": [
        NPX,
        "@openapitools/openapi-generator-cli",
        "generate",
        "-i",
        str(OPENAPI),
        "-g",
        "go",
        "-o",
        str(SDK_DIR / "go"),
    ],
    "python": [
        NPX,
        "@openapitools/openapi-generator-cli",
        "generate",
        "-i",
        str(OPENAPI),
        "-g",
        "python",
        "-o",
        str(SDK_DIR / "python"),
    ],
    "csharp": [
        NPX,
        "@openapitools/openapi-generator-cli",
        "generate",
        "-i",
        str(OPENAPI),
        "-g",
        "csharp",
        "-o",
        str(SDK_DIR / "csharp"),
    ],
}


def run(lang: str) -> None:
    cmd = GENERATORS[lang]
    print(f"Generating {lang} …")
    subprocess.run(cmd, check=True)
    print(f"Done: {SDK_DIR / lang}")


def main() -> None:
    targets = sys.argv[1:] or list(GENERATORS.keys())
    for t in targets:
        if t not in GENERATORS:
            print(f"Unknown target: {t}")
            print(f"Available: {', '.join(GENERATORS.keys())}")
            sys.exit(1)
        run(t)


if __name__ == "__main__":
    main()
