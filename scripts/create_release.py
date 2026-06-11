#!/usr/bin/env python3
"""Create a release: bump version, commit, and tag.

Usage:
    uv run python scripts/create_release.py 0.2.0

This will:
1. Validate the version string (semver X.Y.Z).
2. Run bump_version.py to update all sources.
3. Stage the changed files.
4. Create a commit: 'release: vX.Y.Z'.
5. Create an annotated tag: vX.Y.Z.
6. Print the next steps (push).

The commit and tag are authored with the email configured in
user.email; if unset, the script exits with an error.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def run(cmd: list[str], **kwargs) -> None:
    subprocess.run(cmd, cwd=REPO_ROOT, check=True, **kwargs)


def git_config(key: str) -> str | None:
    result = subprocess.run(
        ["git", "config", key],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a versioned release")
    parser.add_argument("version", help="New semver version (e.g. 0.2.0)")
    args = parser.parse_args()
    version = args.version

    if not SEMVER_RE.match(version):
        print(f"ERROR: '{version}' is not a valid semver string (expected X.Y.Z)")
        return 1

    email = git_config("user.email")
    if not email:
        print("ERROR: git user.email is not set. Run:")
        print('  git config user.email "you@example.com"')
        return 1

    # 1. Bump version across all sources
    run([sys.executable, str(REPO_ROOT / "scripts" / "bump_version.py"), version])

    # 2. Stage only the files that bump_version.py touches
    files_to_stage = [
        "src/openubl/__init__.py",
        "src/openubl/main.py",
        "pyproject.toml",
        "package.json",
        "sdk/typescript/package.json",
        "sdk/typescript/src/version.ts",
        "openapi.json",
        "sdk/typescript/src/openubl-types.ts",
        "uv.lock",
    ]
    changelog_path = REPO_ROOT / "CHANGELOG.md"
    if changelog_path.exists():
        files_to_stage.append("CHANGELOG.md")
    else:
        print("WARNING: CHANGELOG.md not found; skipping changelog in release commit.")
    run(["git", "add"] + files_to_stage)

    # 3. Commit
    run(["git", "commit", "-m", f"release: v{version}"])

    # 4. Annotated tag
    run(["git", "tag", "-a", f"v{version}", "-m", f"Release v{version}"])

    print(f"\nOK: release v{version} created locally.")
    print(f"Author: {email}")
    print("\nNext steps:")
    print(f"  git push origin feat/sdk-publish-version-sync")
    print(f"  git push origin v{version}")
    print("\nThe CI workflows will trigger on the tag and publish to npm/PyPI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
