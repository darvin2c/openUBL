"""Verify that every Pydantic model is reflected in the exported OpenAPI schema."""

import json
from pathlib import Path

from openubl.models import (
    Address,
    Cliente,
    CreditNote,
    DebitNote,
    DocumentoVentaDetalle,
    Invoice,
    Perception,
    Proveedor,
    Retention,
    SummaryDocuments,
    VoidedDocuments,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENAPI_PATH = REPO_ROOT / "openapi.json"


def test_all_models_present_in_openapi_schema():
    with open(OPENAPI_PATH, encoding="utf-8") as f:
        schemas = json.load(f)["components"]["schemas"]

    document_models = [
        Invoice,
        CreditNote,
        DebitNote,
        VoidedDocuments,
        SummaryDocuments,
        Perception,
        Retention,
    ]

    for cls in document_models:
        assert cls.__name__ in schemas, f"{cls.__name__} missing from openapi.json"

    common_models = [
        Address,
        Cliente,
        Proveedor,
        DocumentoVentaDetalle,
    ]

    for cls in common_models:
        assert cls.__name__ in schemas, f"{cls.__name__} missing from openapi.json"
