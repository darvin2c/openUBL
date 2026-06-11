#!/usr/bin/env python3
"""Script único para crear releases: detecta label, hace bump, commit, tag y push opcional.

Modos de invocación (mutuamente excluyentes):
  uv run python scripts/release.py --from-label [--push] [--skip-tests]
  uv run python scripts/release.py --type patch|minor|major [--push] [--skip-tests]
  uv run python scripts/release.py 1.2.3 [--push] [--skip-tests]
  uv run python scripts/release.py --rollback
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

BUMP_FILES = [
    REPO_ROOT / "src" / "openubl" / "__init__.py",
    REPO_ROOT / "src" / "openubl" / "main.py",
    REPO_ROOT / "pyproject.toml",
    REPO_ROOT / "package.json",
    REPO_ROOT / "sdk" / "typescript" / "package.json",
    REPO_ROOT / "sdk" / "typescript" / "src" / "version.ts",
    REPO_ROOT / "openapi.json",
    REPO_ROOT / "sdk" / "typescript" / "src" / "openubl-types.ts",
    REPO_ROOT / "uv.lock",
    REPO_ROOT / "CHANGELOG.md",
]

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
RELEASE_LABEL_RE = re.compile(r"^release:(patch|minor|major)$")
RELEASE_COMMIT_RE = re.compile(r"^release: v(\d+\.\d+\.\d+)$")


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Ejecuta un comando; si check=True y falla, aborta con mensaje claro."""
    if cwd is None:
        cwd = REPO_ROOT
    kwargs: dict = {"cwd": cwd, "check": check}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    try:
        return subprocess.run(cmd, **kwargs)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: comando falló: {' '.join(cmd)}")
        if exc.stdout:
            print(exc.stdout)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        sys.exit(1)


def git_current_branch() -> str:
    result = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture=True)
    return result.stdout.strip()


def git_is_clean() -> bool:
    result = run(["git", "status", "--porcelain"], capture=True)
    return result.stdout.strip() == ""


def git_head_commit_message() -> str:
    result = run(["git", "log", "-1", "--format=%s"], capture=True)
    return result.stdout.strip()


def git_head_oid() -> str:
    result = run(["git", "rev-parse", "HEAD"], capture=True)
    return result.stdout.strip()


def git_tag_points_to_head(tag: str) -> bool:
    try:
        result = run(["git", "rev-list", "-n1", tag], capture=True, check=False)
        if result.returncode != 0:
            return False
        return result.stdout.strip() == git_head_oid()
    except Exception:
        return False


def git_is_ancestor(ancestor: str, descendant: str, max_commits: int = 5) -> bool:
    """Verifica si ancestor está en la historia reciente de descendant."""
    result = run(["git", "rev-list", "--max-count", str(max_commits), descendant], capture=True, check=False)
    if result.returncode != 0:
        return False
    commits = result.stdout.strip().splitlines()
    return ancestor in commits


def read_current_version() -> str:
    pyproject = REPO_ROOT / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    m = re.search(r'version\s*=\s*"([^"]+)"', content)
    if not m:
        print("ERROR: no se pudo leer la versión actual de pyproject.toml")
        sys.exit(1)
    return m.group(1)


def bump_semver(version: str, bump_type: str) -> str:
    m = SEMVER_RE.match(version)
    if not m:
        print(f"ERROR: versión actual '{version}' no es SemVer válida")
        sys.exit(1)
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if bump_type == "major":
        return f"{major + 1}.0.0"
    if bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def resolve_version_from_label() -> tuple[str, str]:
    gh = shutil.which("gh")
    if not gh:
        print("ERROR: '--from-label' requiere la CLI de GitHub (gh). Instálala o usa '--type'.")
        sys.exit(1)

    result = run(
        [gh, "pr", "list", "--state", "merged", "--limit", "1", "--json", "number,labels,mergeCommit", "--jq", ".[0]"],
        capture=True,
    )
    try:
        data = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        print("ERROR: no se pudo parsear la salida de 'gh pr list'.")
        sys.exit(1)

    if not data:
        print("ERROR: no se encontró ningún PR mergeado recientemente.")
        sys.exit(1)

    merge_oid = data.get("mergeCommit", {}).get("oid", "")
    if not merge_oid:
        print("ERROR: el último PR mergeado no tiene mergeCommit.oid.")
        sys.exit(1)

    if not git_is_ancestor(merge_oid, git_head_oid()):
        print(f"ERROR: el mergeCommit {merge_oid} no está en los últimos 5 commits de main.")
        sys.exit(1)

    labels = [label.get("name", "") for label in data.get("labels", [])]
    release_labels = [l for l in labels if RELEASE_LABEL_RE.match(l)]
    if len(release_labels) != 1:
        print(f"ERROR: se requiere exactamente un label release:(patch|minor|major). Encontrados: {release_labels or 'ninguno'}")
        sys.exit(1)

    bump_type = RELEASE_LABEL_RE.match(release_labels[0]).group(1)  # type: ignore[union-attr]
    current = read_current_version()
    new_version = bump_semver(current, bump_type)
    return new_version, bump_type


def run_tests(skip: bool) -> None:
    if skip:
        print("INFO: saltando tests por --skip-tests")
        return

    print("INFO: ejecutando tests de Python…")
    run(["uv", "run", "pytest", "-m", "not e2e"])

    ts_package = REPO_ROOT / "sdk" / "typescript" / "package.json"
    if ts_package.exists():
        print("INFO: ejecutando tests de TypeScript…")
        run(["npm", "test"], cwd=REPO_ROOT / "sdk" / "typescript")
    else:
        print("WARN: no se encontró sdk/typescript/package.json; saltando tests TS")

    print("INFO: ejecutando check_sdk_sync.py…")
    run(["uv", "run", "python", "scripts/check_sdk_sync.py"])


def run_bump(version: str) -> None:
    print(f"INFO: ejecutando bump_version.py a {version}…")
    run(["uv", "run", "python", "scripts/bump_version.py", version])


def run_changelog(version: str) -> None:
    git_cliff = shutil.which("git-cliff")
    if not git_cliff:
        print("WARN: git-cliff no está en PATH; saltando regeneración de CHANGELOG.md")
        return
    print(f"INFO: generando CHANGELOG.md con git-cliff…")
    run([git_cliff, "--config", "cliff.toml", "--tag", f"v{version}", "--output", "CHANGELOG.md"])


def stage_files() -> None:
    existing = [str(p.relative_to(REPO_ROOT)) for p in BUMP_FILES if p.exists()]
    if existing:
        run(["git", "add", "-f"] + existing)
    else:
        print("WARN: no hay archivos para stagear")


def commit_and_tag(version: str) -> None:
    msg = f"release: v{version}"
    run(["git", "commit", "-m", msg])
    run(["git", "tag", "-a", f"v{version}", "-m", f"Release v{version}"])
    print(f"INFO: commit y tag v{version} creados localmente")


def push(version: str) -> None:
    print("INFO: haciendo push a origin/main…")
    result = run(["git", "push", "origin", "main"], check=False)
    if result.returncode != 0:
        print("ERROR: push a origin/main falló (¿branch protection?)")
        print(f"Sugerencia: crea un PR manualmente desde el commit actual ({git_head_oid()[:8]})")
        print(f"Luego ejecuta: git push origin v{version}")
        sys.exit(1)

    print(f"INFO: haciendo push del tag v{version}…")
    run(["git", "push", "origin", f"v{version}"])


def do_rollback() -> None:
    head_msg = git_head_commit_message()
    m = RELEASE_COMMIT_RE.match(head_msg)
    if not m:
        print(f"ERROR: HEAD no es un commit de release. Mensaje actual: '{head_msg}'")
        sys.exit(1)

    version = m.group(1)
    tag = f"v{version}"

    if not git_tag_points_to_head(tag):
        print(f"ERROR: el tag {tag} no apunta a HEAD; abortando rollback por seguridad.")
        sys.exit(1)

    print(f"INFO: eliminando tag local {tag}…")
    run(["git", "tag", "-d", tag])

    print("INFO: haciendo reset --hard HEAD~1…")
    run(["git", "reset", "--hard", "HEAD~1"])

    print(f"Rollback completado. Commit y tag {tag} eliminados. Working tree restaurado.")


def do_release(version: str, bump_type: str | None, *, push_flag: bool, skip_tests: bool) -> None:
    branch = git_current_branch()
    if branch != "main":
        print(f"ERROR: debes estar en la rama 'main'. Actual: '{branch}'")
        sys.exit(1)

    if not git_is_clean():
        print("ERROR: working tree no está limpio. Commit o stash tus cambios antes de continuar.")
        sys.exit(1)

    run_tests(skip_tests)
    run_bump(version)
    run_changelog(version)
    stage_files()
    commit_and_tag(version)

    if push_flag:
        push(version)
        print(f"Release v{version} creado y pusheado. El workflow publish.yml se disparará automáticamente en GitHub Actions.")
    else:
        print(f"Release v{version} creado localmente. Tag: v{version}.")
        print(f"Para completar: git push origin main && git push origin v{version}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea un release de openUBL")
    parser.add_argument("version", nargs="?", help="Versión explícita (ej. 1.2.3)")
    parser.add_argument("--from-label", action="store_true", help="Detectar tipo de bump desde el label del último PR mergeado")
    parser.add_argument("--type", choices=["patch", "minor", "major"], help="Tipo de bump SemVer explícito")
    parser.add_argument("--push", action="store_true", help="Hacer push de main y del tag a origin")
    parser.add_argument("--skip-tests", action="store_true", help="Saltar tests previos al release")
    parser.add_argument("--rollback", action="store_true", help="Deshacer el último release (commit + tag)")
    args = parser.parse_args()

    modes = [m for m in [args.from_label, args.type, args.version, args.rollback] if m]
    if len(modes) != 1:
        parser.error("Debes usar exactamente uno de: --from-label, --type, versión posicional, o --rollback")

    if args.rollback:
        do_rollback()
        return 0

    if args.from_label:
        version, bump_type = resolve_version_from_label()
    elif args.type:
        bump_type = args.type
        current = read_current_version()
        version = bump_semver(current, bump_type)
    else:
        version = args.version
        if not SEMVER_RE.match(version):
            parser.error(f"Versión '{version}' no es SemVer válida (formato esperado: X.Y.Z)")
        bump_type = None

    do_release(version, bump_type, push_flag=args.push, skip_tests=args.skip_tests)
    return 0


if __name__ == "__main__":
    sys.exit(main())
