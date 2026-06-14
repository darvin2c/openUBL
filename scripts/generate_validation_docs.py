"""Genera documentación detallada de cobertura SUNAT."""

import ast
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOC_TYPES = {
    "_extra_invoice1.py": "Invoice",
    "_extra_invoice2.py": "Invoice",
    "_extra_invoice3.py": "Invoice",
    "_extra_credit_note.py": "CreditNote",
    "_extra_debit_note.py": "DebitNote",
    "_extra_perception_retention.py": "Perception/Retention",
    "_extra_voided_summary.py": "Voided/Summary",
}

EXTRA_DOC_SPLIT = {
    "Perception/Retention": {
        "_extra_perception_retention.py": {
            "validate_perception_extra": "Perception",
            "validate_retention_extra": "Retention",
        }
    },
    "Voided/Summary": {
        "_extra_voided_summary.py": {
            "validate_voided_documents_extra": "VoidedDocuments",
            "validate_summary_documents_extra": "SummaryDocuments",
        }
    },
}

TEST_FILES = {
    "Invoice": ["tests/test_validator.py", "tests/_test_validator_invoice1_extra.py", "tests/_test_validator_invoice2_extra.py", "tests/_test_validator_invoice3_extra.py"],
    "CreditNote": ["tests/test_validator.py", "tests/_test_validator_credit_note_extra.py"],
    "DebitNote": ["tests/test_validator.py", "tests/_test_validator_debit_note_extra.py"],
    "Perception": ["tests/test_validator.py", "tests/_test_validator_perception_retention_extra.py"],
    "Retention": ["tests/test_validator.py", "tests/_test_validator_perception_retention_extra.py"],
    "VoidedDocuments": ["tests/test_validator.py", "tests/_test_validator_voided_summary_extra.py"],
    "SummaryDocuments": ["tests/test_validator.py", "tests/_test_validator_voided_summary_extra.py"],
    "Firma digital": ["tests/test_validator.py", "tests/_test_validator_signature_extra.py"],
}

RULES = {}
for f in ["rules_Invoice.txt", "rules_CreditNote.txt", "rules_DebitNote.txt"]:
    p = ROOT / f
    if p.exists():
        RULES[f.replace("rules_", "").replace(".txt", "")] = p.read_text(encoding="utf-8", errors="ignore")


def get_description(code: str, doc_type: str) -> str:
    keys = []
    mapping = {"Invoice": "Invoice", "CreditNote": "CreditNote", "DebitNote": "DebitNote"}
    if doc_type in mapping:
        keys.append(mapping[doc_type])
    keys.extend(["Invoice", "CreditNote", "DebitNote"])
    for key in keys:
        text = RULES.get(key, "")
        m = re.search(
            rf"===\s*{re.escape(code)}\s*===\s*.*?Msg:\s*(.+?)(?=\n===|\Z)",
            text,
            re.DOTALL,
        )
        if m:
            return " ".join(m.group(1).split())
    return ""


def extract_string_args(call: ast.Call) -> list[str]:
    out = []
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            out.append(arg.value)
    for kw in call.keywords:
        if kw.arg == "code" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            out.append(kw.value.value)
    return out


def extract_codes_from_text(text: str) -> set[str]:
    codes = set()
    for m in re.finditer(r'_add\s*\(\s*errors\s*,\s*["\'](\d{4})["\']', text):
        codes.add(m.group(1))
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return codes
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in ("SunatError", "ValidationError", "_add"):
                for code in extract_string_args(node):
                    if re.fullmatch(r"\d{4}", code):
                        codes.add(code)
    for m in re.finditer(r'#\s*ERROR\s+(\d{4})', text):
        codes.add(m.group(1))
    return codes


def extract_out_of_scope_codes(text: str) -> set[str]:
    codes = set()
    for m in re.finditer(r'#\s*FUERA\s*DE\s*ALCANCE.*?\b(\d{4})\b', text, re.IGNORECASE | re.DOTALL):
        codes.add(m.group(1))
    return codes


def extract_tested_codes(text: str) -> set[str]:
    codes = set()
    for m in re.finditer(r'\b_m(\d{4})\b', text):
        codes.add(m.group(1))
    for m in re.finditer(r'"(\d{4})"', text):
        codes.add(m.group(1))
    for m in re.finditer(r"'(\d{4})'", text):
        codes.add(m.group(1))
    return codes


def doc_type_for_function(name: str) -> str | None:
    lowered = name.lower()
    if "signature" in lowered or "sign" in lowered:
        return "Firma digital"
    if "credit_note" in lowered or "creditnote" in lowered:
        return "CreditNote"
    if "debit_note" in lowered or "debitnote" in lowered:
        return "DebitNote"
    if "perception" in lowered:
        return "Perception"
    if "retention" in lowered:
        return "Retention"
    if "voided" in lowered:
        return "VoidedDocuments"
    if "summary" in lowered:
        return "SummaryDocuments"
    if "invoice" in lowered:
        return "Invoice"
    return None


def process_function_node(node, text, impl, out_scope):
    doc = doc_type_for_function(node.name)
    if doc is None:
        return
    start, end = node.lineno, node.end_lineno
    segment = "\n".join(text.splitlines()[start - 1 : end])
    impl[doc] |= extract_codes_from_text(segment)
    out_scope[doc] |= extract_out_of_scope_codes(segment)


def parse_validator_py():
    path = ROOT / "src" / "openubl" / "validator.py"
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    impl = defaultdict(set)
    out_scope = defaultdict(set)

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    process_function_node(child, text, impl, out_scope)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            process_function_node(node, text, impl, out_scope)

    return impl, out_scope


def parse_extra_modules():
    impl = defaultdict(set)
    out_scope = defaultdict(set)
    for path in (ROOT / "src" / "openubl" / "validators").glob("_extra_*.py"):
        text = path.read_text(encoding="utf-8")
        doc = DOC_TYPES.get(path.name, path.name)
        if doc in EXTRA_DOC_SPLIT and path.name in EXTRA_DOC_SPLIT[doc]:
            split = EXTRA_DOC_SPLIT[doc][path.name]
            for node in ast.parse(text).body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in split:
                    start, end = node.lineno, node.end_lineno
                    segment = "\n".join(text.splitlines()[start - 1 : end])
                    sub_doc = split[node.name]
                    impl[sub_doc] |= extract_codes_from_text(segment)
                    out_scope[sub_doc] |= extract_out_of_scope_codes(segment)
        else:
            impl[doc] |= extract_codes_from_text(text)
            out_scope[doc] |= extract_out_of_scope_codes(text)
    return impl, out_scope


def parse_tests():
    tested = defaultdict(set)
    for doc, files in TEST_FILES.items():
        for f in files:
            path = ROOT / f
            if path.exists():
                tested[doc] |= extract_tested_codes(path.read_text(encoding="utf-8", errors="ignore"))
    return tested


def main():
    impl_main, out_main = parse_validator_py()
    impl_extra, out_extra = parse_extra_modules()
    tested = parse_tests()

    implemented = defaultdict(set)
    out_of_scope = defaultdict(set)
    for doc in set(impl_main) | set(impl_extra):
        implemented[doc] = impl_main.get(doc, set()) | impl_extra.get(doc, set())
        out_of_scope[doc] = out_main.get(doc, set()) | out_extra.get(doc, set())

    lines = []
    lines.append("---")
    lines.append("title: Validaciones SUNAT detalladas")
    lines.append("description: Listado completo de códigos SUNAT implementados, su descripción y test de cobertura.")
    lines.append("---")
    lines.append("")
    lines.append("Esta página lista cada código SUNAT implementado en openUBL, su descripción, el tipo de documento y si cuenta con test parametrizado. También indica los códigos fuera de alcance por requerir padrones o listados SUNAT.")
    lines.append("")
    lines.append("## Tabla resumen por documento")
    lines.append("")
    lines.append("| Documento | Implementadas | Con test | Fuera de alcance |")
    lines.append("|-----------|--------------:|---------:|-----------------:|")
    docs_order = ["Invoice", "CreditNote", "DebitNote", "VoidedDocuments", "SummaryDocuments", "Perception", "Retention", "Firma digital"]
    for doc in docs_order:
        codes = implemented.get(doc, set())
        out = out_of_scope.get(doc, set())
        test_set = tested.get(doc, set())
        lines.append(f"| {doc} | {len(codes)} | {len(codes & test_set)} | {len(out)} |")
    lines.append("")

    for doc in docs_order:
        codes = sorted(implemented.get(doc, set()), key=lambda x: int(x))
        out = out_of_scope.get(doc, set())
        test_set = tested.get(doc, set())
        lines.append(f"## {doc}")
        lines.append("")
        lines.append(f"- **Implementadas**: {len(codes)}")
        lines.append(f"- **Con test**: {len(set(codes) & test_set)}")
        lines.append(f"- **Fuera de alcance**: {len(out)}")
        lines.append("")
        lines.append("| Código | Descripción | Test |")
        lines.append("|--------|-------------|------|")
        for code in codes:
            desc = get_description(code, doc)
            has_test = "Sí" if code in test_set else "No"
            lines.append(f"| {code} | {desc} | {has_test} |")
        if out:
            lines.append("")
            lines.append(f"### Fuera de alcance en {doc}")
            lines.append("")
            lines.append("| Código | Descripción |")
            lines.append("|--------|-------------|")
            for code in sorted(out, key=lambda x: int(x)):
                desc = get_description(code, doc)
                lines.append(f"| {code} | {desc} |")
        lines.append("")

    output = ROOT / "docs" / "src" / "content" / "docs" / "engine" / "validaciones-sunat-detallado.mdx"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {output}")

    total_impl = sum(len(implemented[d]) for d in implemented)
    total_tested = sum(len(implemented[d] & tested.get(d, set())) for d in implemented)
    total_out = sum(len(out_of_scope[d]) for d in out_of_scope)
    print(f"Total implementadas: {total_impl}")
    print(f"Total con test: {total_tested}")
    print(f"Total fuera de alcance: {total_out}")


if __name__ == "__main__":
    main()
