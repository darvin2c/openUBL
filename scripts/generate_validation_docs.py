"""Genera documentación de cobertura de validaciones SUNAT a partir de coverage_report.json.

Emite:
- docs/src/content/docs/engine/validaciones-sunat.mdx (resumen)
- docs/src/content/docs/engine/validaciones-sunat-detallado.mdx (detalle)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = REPO_ROOT / "coverage_report.json"
DOCS_DIR = REPO_ROOT / "docs" / "src" / "content" / "docs" / "engine"

EXCEL_URL = (
    "https://cpe.sunat.gob.pe/sites/default/files/2026-05/"
    "Reglas%20de%20validaci%C3%B3n%20actualizado%20al%2024.04.2026%20%281%29.xlsx"
)
SUNAT_PAGE = "https://cpe.sunat.gob.pe/guias-y-manuales"


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _pct(a: int, b: int) -> str:
    return f"{(a / b * 100) if b else 0.0:.1f}%"


def _oos_reason(desc: str) -> str:
    low = desc.lower()
    if "nombre del archivo" in low or "nombre del xml" in low:
        return "Depende del nombre del archivo/XML."
    if "fecha de recepción" in low or "fecha de envío" in low:
        return "Depende de la fecha de recepción/envío de SUNAT."
    if "listado" in low or "padrón" in low or "padron" in low:
        return "Requiere consulta a listados o padrones SUNAT."
    if "estado anulado" in low or "estado rechazado" in low or "estado del comprobante" in low:
        return "Depende del estado del comprobante en SUNAT."
    if "see-empresas supervisadas" in low:
        return "Depende del padrón SEE-Empresas supervisadas."
    if "sunat" in low and ("producto" in low or "código" in low):
        return "Requiere listado/código SUNAT."
    return "Requiere información externa no disponible localmente."


def _oos_item(code: str, desc: str) -> str:
    if desc:
        return f"- `{code}` — {_escape_cell(desc)}"
    return f"- `{code}` — Regla general de validación de archivo/servicio (hoja General del Excel SUNAT)."


def generate_summary(report: dict) -> str:
    lines: list[str] = [
        "---",
        "title: Validaciones SUNAT",
        "description: Reglas de validación SUNAT implementadas en openUBL Server.",
        "---",
        "",
        f"openUBL Server aplica las reglas de validación del Excel **[Reglas de validación actualizado al 24.04.2026]({EXCEL_URL})** publicado por SUNAT Perú en [{SUNAT_PAGE}]({SUNAT_PAGE}).",
        "",
        "## Fuente de verdad",
        "",
        f"- **Documento**: Excel *Reglas de validación actualizado al 24.04.2026*.",
        f"- **Descarga directa**: [Reglas de validación actualizado al 24.04.2026]({EXCEL_URL}).",
        f"- **Página oficial**: [{SUNAT_PAGE}]({SUNAT_PAGE}).",
        "",
        "## Alcance",
        "",
        "openUBL implementa **todas las reglas de tipo ERROR que se pueden evaluar localmente**, es decir, sin consultar padrones, listados ni servicios web de SUNAT.",
        "",
        "La tabla inferior muestra el estado por tipo de documento. Para el listado completo de códigos, descripciones y tests, consulta [Validaciones SUNAT detalladas](./validaciones-sunat-detallado).",
        "",
        "Las reglas que requieren listados/padrones quedan **documentadas como fuera de alcance** en esta página.",
        "",
        "## Tabla resumen por documento",
        "",
        "| Documento | Implementadas | Con test | Fuera de alcance | Pendientes | % Validaciones | % Testing |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for doc, data in report["documents"].items():
        total = data["total_sunat_error"]
        impl = len(data["implemented"])
        tested = len(data["tested"])
        oos = len(data["out_of_scope"])
        pending = len(data["local_missing"])
        implementable = len(data["implementable"])
        pct_valid = _pct(impl, implementable)
        pct_test = _pct(tested, impl)
        lines.append(
            f"| {doc} | {impl} | {tested} | {oos} | {pending} | {pct_valid} | {pct_test} |"
        )
    lines.extend([
        "",
        "* `% Validaciones` = Implementadas / (Total SUNAT ERROR − Fuera de alcance) × 100.",
        "* `% Testing` = Con test / Implementadas × 100.",
        "* `Pendientes` son reglas ERROR implementables localmente que aún no están en el validador.",
        "",
        "## Códigos fuera de alcance",
        "",
        "Ejemplos de reglas que requieren listados o padrones SUNAT y no se evalúan localmente:",
        "",
    ])
    for doc, data in report["documents"].items():
        oos = data["out_of_scope"]
        if not oos:
            continue
        lines.append(f"### {doc}")
        lines.append("")
        for code in oos:
            desc = data["descriptions"].get(code, "")
            lines.append(_oos_item(code, desc))
        lines.append("")
    lines.extend([
        "## Formato de respuesta de errores",
        "",
        "Cuando `validar_sunat=true` y el XML no cumple una o más reglas, el endpoint responde HTTP 422:",
        "",
        "```json",
        '{"detail":[{"code":"2074","message":"El valor del Tag UBL cbc:UBLVersionID es diferente de \'2.1\'"}]}',
        "```",
        "",
        "El campo `code` es el código SUNAT exacto del Excel.",
        "",
        "## Cómo verificar cobertura",
        "",
        "```bash",
        "uv run python scripts/validation_coverage.py",
        "```",
        "",
        "## Enlaces útiles",
        "",
        "- [Validaciones SUNAT detalladas](./validaciones-sunat-detallado): listado completo de códigos implementados, descripción de cada regla y test de cobertura.",
        "",
    ])
    return "\n".join(lines)


def generate_detailed(report: dict) -> str:
    lines: list[str] = [
        "---",
        "title: Validaciones SUNAT detalladas",
        "description: Listado completo de códigos SUNAT implementados, su descripción y test de cobertura.",
        "---",
        "",
        f"Esta página lista cada código SUNAT del Excel **[Reglas de validación actualizado al 24.04.2026]({EXCEL_URL})** implementado en openUBL, su descripción y si cuenta con test parametrizado. También indica los códigos fuera de alcance por requerir padrones o listados SUNAT.",
        "",
        f"- **Descarga directa**: [Reglas de validación actualizado al 24.04.2026]({EXCEL_URL}).",
        f"- **Página oficial**: [{SUNAT_PAGE}]({SUNAT_PAGE}).",
        "",
        "## Tabla resumen por documento",
        "",
        "| Documento | Implementadas | Con test | Fuera de alcance | Pendientes | % Validaciones | % Testing |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for doc, data in report["documents"].items():
        total = data["total_sunat_error"]
        impl = len(data["implemented"])
        tested = len(data["tested"])
        oos = len(data["out_of_scope"])
        pending = len(data["local_missing"])
        implementable = len(data["implementable"])
        pct_valid = _pct(impl, implementable)
        pct_test = _pct(tested, impl)
        lines.append(
            f"| {doc} | {impl} | {tested} | {oos} | {pending} | {pct_valid} | {pct_test} |"
        )
    lines.extend([
        "",
        "## Detalle por documento",
        "",
    ])
    for doc, data in report["documents"].items():
        impl_set = set(data["implemented"])
        tested_set = set(data["tested"])
        oos_set = set(data["out_of_scope"])
        all_codes = sorted(set(data["descriptions"].keys()))
        lines.append(f"### {doc}")
        lines.append("")
        lines.append(
            f"- **Total ERROR**: {data['total_sunat_error']} | **Implementadas**: {len(impl_set)} | "
            f"**Con test**: {len(tested_set)} | **Fuera de alcance**: {len(oos_set)} | "
            f"**Pendientes**: {len(data['local_missing'])}"
        )
        lines.append("")
        lines.append("| Código | Descripción | Implementada | Test |")
        lines.append("|---|---|:---:|:---:|")
        for code in all_codes:
            if code in oos_set:
                continue
            desc = _escape_cell(data["descriptions"].get(code, ""))
            impl = "Sí" if code in impl_set else "No"
            test = "Sí" if code in tested_set else "No"
            lines.append(f"| `{code}` | {desc} | {impl} | {test} |")
        lines.append("")
        if oos_set:
            lines.append(f"#### Fuera de alcance en {doc}")
            lines.append("")
            lines.append("| Código | Descripción | Motivo |")
            lines.append("|---|---|---|")
            for code in sorted(oos_set):
                desc = data["descriptions"].get(code, "")
                display_desc = _escape_cell(desc) if desc else "Regla general de validación de archivo/servicio."
                reason = _oos_reason(desc)
                lines.append(f"| `{code}` | {display_desc} | {reason} |")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    if not REPORT_PATH.exists():
        print(f"No existe {REPORT_PATH}; ejecuta scripts/validation_coverage.py primero", file=sys.stderr)
        return 1
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "validaciones-sunat.mdx").write_text(generate_summary(report), encoding="utf-8")
    (DOCS_DIR / "validaciones-sunat-detallado.mdx").write_text(generate_detailed(report), encoding="utf-8")
    print(f"Documentación generada en {DOCS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
