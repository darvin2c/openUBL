#!/usr/bin/env python3
"""Bump version across all project sources in one transaction."""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FILES = {
    "python_init": REPO_ROOT / "src" / "openubl" / "__init__.py",
    "python_main": REPO_ROOT / "src" / "openubl" / "main.py",
    "pyproject": REPO_ROOT / "pyproject.toml",
    "root_package": REPO_ROOT / "package.json",
    "ts_package": REPO_ROOT / "sdk" / "typescript" / "package.json",
}


def rewrite_python_init(path: Path, version: str) -> None:
    content = path.read_text(encoding="utf-8")
    new_content = re.sub(
        r'^__version__\s*=\s*"[^"]*"',
        f'__version__ = "{version}"',
        content,
        flags=re.MULTILINE,
    )
    path.write_text(new_content, encoding="utf-8")


def rewrite_python_main(path: Path, version: str) -> None:
    content = path.read_text(encoding="utf-8")
    new_content = re.sub(
        r'version="[^"]*"',
        f'version="{version}"',
        content,
    )
    path.write_text(new_content, encoding="utf-8")


def rewrite_pyproject(path: Path, version: str) -> None:
    content = path.read_text(encoding="utf-8")
    new_content = re.sub(
        r'^version\s*=\s*"[^"]*"',
        f'version = "{version}"',
        content,
        flags=re.MULTILINE,
    )
    path.write_text(new_content, encoding="utf-8")


def rewrite_package_json(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_export_openapi() -> None:
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "export_openapi.py")],
        check=True,
    )


def run_ts_generate() -> None:
    npm = shutil.which("npm")
    if not npm:
        raise FileNotFoundError("npm not found in PATH")
    subprocess.run(
        [npm, "run", "generate"],
        cwd=REPO_ROOT / "sdk" / "typescript",
        check=True,
    )

def run_uv_lock() -> None:
    uv = shutil.which("uv")
    if not uv:
        raise FileNotFoundError("uv not found in PATH")
    subprocess.run([uv, "lock"], cwd=REPO_ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump version across all sources")
    parser.add_argument("version", help="New semver version (e.g. 0.2.0)")
    args = parser.parse_args()
    version = args.version

    missing = [name for name, path in FILES.items() if not path.exists()]
    if missing:
        for name in missing:
            print(f"ERROR: missing file {FILES[name]}")
        return 1

    rewrite_python_init(FILES["python_init"], version)
    rewrite_python_main(FILES["python_main"], version)
    rewrite_pyproject(FILES["pyproject"], version)
    rewrite_package_json(FILES["root_package"], version)
    rewrite_package_json(FILES["ts_package"], version)

    run_export_openapi()
    run_ts_generate()
    run_uv_lock()

    print(f"OK: bumped to {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
