#!/usr/bin/env python3
"""Generate documentation aligned with openapi.json and sdk/typescript/README.md."""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENAPI_PATH = REPO_ROOT / "openapi.json"
API_DOCS_PATH = REPO_ROOT / "docs" / "src" / "content" / "docs" / "api" / "referencia.mdx"
SDK_README_PATH = REPO_ROOT / "sdk" / "typescript" / "README.md"
SDK_DOCS_PATH = REPO_ROOT / "docs" / "src" / "content" / "docs" / "sdk" / "typescript.mdx"


def _resolve_schema_name(ref: str) -> str:
    return ref.split("/")[-1]


def _schema_link(name: str) -> str:
    return f"[`{name}`](#{name.lower()})"


def _format_type(prop: dict) -> str:
    if "$ref" in prop:
        return _schema_link(_resolve_schema_name(prop["$ref"]))
    if "enum" in prop:
        return "enum"
    if "anyOf" in prop or "oneOf" in prop:
        return "union"
    return prop.get("type", "—")


def _format_constraints(prop: dict) -> str:
    parts = []
    if "pattern" in prop:
        parts.append("`pattern`")
    if "minLength" in prop:
        parts.append(f"min {prop['minLength']}")
    if "maxLength" in prop:
        parts.append(f"max {prop['maxLength']}")
    if "minimum" in prop:
        parts.append(f"≥ {prop['minimum']}")
    if "maximum" in prop:
        parts.append(f"≤ {prop['maximum']}")
    if "exclusiveMinimum" in prop:
        parts.append(f"> {prop['exclusiveMinimum']}")
    if "enum" in prop:
        values = ", ".join(f"`{v}`" for v in prop["enum"])
        parts.append(f"enum: {values}")
    if "default" in prop:
        parts.append(f"default: `{prop['default']}`")
    return "; ".join(parts) if parts else "—"


def _escape_pipe(value: str) -> str:
    return value.replace("|", "\\|")


def _format_schema_table(schema: dict) -> str:
    lines = ["| Propiedad | Tipo | Requerido | Constraints |", "|-----------|------|-----------|-------------|"]
    if "enum" in schema:
        values = ", ".join(f"`{v}`" for v in schema["enum"])
        lines.append(f"| Valores | enum | — | {values} |")
        return "\n".join(lines)
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    for name, prop in properties.items():
        prop_type = _format_type(prop)
        is_required = "Sí" if name in required else "No"
        constraints = _escape_pipe(_format_constraints(prop))
        lines.append(f"| `{name}` | {prop_type} | {is_required} | {constraints} |")
    return "\n".join(lines)

def generate_api_docs() -> None:
    data = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))

    lines = [
        "---",
        "title: Referencia de endpoints",
        "description: Endpoints y modelos de la API REST de openUBL.",
        "---",
        "",
        "Esta referencia se genera automáticamente desde `openapi.json`. No editar manualmente.",
        "",
        "## Endpoints",
        "",
        "| Método | Ruta | Cuerpo | Respuesta |",
        "|--------|------|--------|-----------|",
    ]

    paths = data.get("paths", {})
    for route, methods in sorted(paths.items()):
        for method, spec in sorted(methods.items()):
            if method == "parameters" or not isinstance(spec, dict):
                continue
            request_body = spec.get("requestBody", {})
            content = request_body.get("content", {})
            body_schema = "—"
            if "application/json" in content:
                ref = content["application/json"].get("schema", {})
                if "$ref" in ref:
                    body_schema = _schema_link(_resolve_schema_name(ref["$ref"]))
            responses = spec.get("responses", {})
            response_schema = "—"
            for code in sorted(responses.keys()):
                resp = responses[code]
                content = resp.get("content", {})
                if "application/json" in content:
                    ref = content["application/json"].get("schema", {})
                    if "$ref" in ref:
                        response_schema = _schema_link(_resolve_schema_name(ref["$ref"]))
                    break
            lines.append(f"| {method.upper()} | `{route}` | {body_schema} | {response_schema} |")

    lines.extend(["", "## Modelos", ""])

    schemas = data.get("components", {}).get("schemas", {})
    for name, schema in sorted(schemas.items()):
        description = schema.get("description", "")
        lines.extend([f"### `{name}`", ""])
        if description:
            lines.append(f"{description}")
            lines.append("")
        lines.append(_format_schema_table(schema))
        lines.append("")

    API_DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
    API_DOCS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"API docs generated at {API_DOCS_PATH}")


def generate_sdk_docs() -> None:
    content = SDK_README_PATH.read_text(encoding="utf-8")
    frontmatter = (
        "---\n"
        "title: TypeScript SDK\n"
        "description: Instalación y uso del SDK de TypeScript para openUBL.\n"
        "---\n\n"
        "{/* Este archivo se genera automáticamente desde sdk/typescript/README.md. No editar manualmente. */}\n\n"
    )
    SDK_DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SDK_DOCS_PATH.write_text(frontmatter + content, encoding="utf-8")
    print(f"SDK docs generated at {SDK_DOCS_PATH}")


def main() -> None:
    generate_api_docs()
    generate_sdk_docs()


if __name__ == "__main__":
    main()
