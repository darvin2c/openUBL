"""
FastAPI router for openUBL REST API.
"""
from fastapi import APIRouter, Query, HTTPException

from ..models import (
    Invoice, CreditNote, DebitNote, VoidedDocuments,
    SummaryDocuments, Perception, Retention,
)
from ..enricher import ContentEnricher
from ..renderer import (
    render_invoice, render_credit_note, render_debit_note,
    render_voided_documents, render_summary_documents,
    render_perception, render_retention,
)
from ..signer import sign_ubl_xml
from ..validator import SunatValidator


router = APIRouter()
validator = SunatValidator()


def _validate_xml(xml_string: str, doc_type: str) -> list[str]:
    """Run SUNAT validation on rendered XML."""
    if doc_type == "invoice":
        return validator.validate_invoice(xml_string)
    elif doc_type == "credit_note":
        return validator.validate_credit_note(xml_string)
    elif doc_type == "voided":
        return validator.validate_voided_documents(xml_string)
    return []


@router.post("/invoice/create")
def create_invoice(doc: Invoice, validate: bool = Query(default=True)):
    """Create an Invoice XML."""
    enricher = ContentEnricher()
    enricher.enrich(doc)
    xml = render_invoice(doc)
    if validate:
        errors = _validate_xml(xml, "invoice")
        if errors:
            raise HTTPException(status_code=422, detail=errors)
    return {"xml": xml}


@router.post("/credit-note/create")
def create_credit_note(doc: CreditNote, validate: bool = Query(default=True)):
    """Create a CreditNote XML."""
    enricher = ContentEnricher()
    enricher.enrich(doc)
    xml = render_credit_note(doc)
    if validate:
        errors = _validate_xml(xml, "credit_note")
        if errors:
            raise HTTPException(status_code=422, detail=errors)
    return {"xml": xml}


@router.post("/debit-note/create")
def create_debit_note(doc: DebitNote, validate: bool = Query(default=True)):
    """Create a DebitNote XML."""
    enricher = ContentEnricher()
    enricher.enrich(doc)
    xml = render_debit_note(doc)
    if validate:
        errors = _validate_xml(xml, "credit_note")
        if errors:
            raise HTTPException(status_code=422, detail=errors)
    return {"xml": xml}


@router.post("/voided-documents/create")
def create_voided_documents(doc: VoidedDocuments, validate: bool = Query(default=True)):
    """Create a VoidedDocuments XML."""
    enricher = ContentEnricher()
    enricher.enrich(doc)
    xml = render_voided_documents(doc)
    if validate:
        errors = _validate_xml(xml, "voided")
        if errors:
            raise HTTPException(status_code=422, detail=errors)
    return {"xml": xml}


@router.post("/summary-documents/create")
def create_summary_documents(doc: SummaryDocuments, validate: bool = Query(default=True)):
    """Create a SummaryDocuments XML."""
    xml = render_summary_documents(doc)
    return {"xml": xml}


@router.post("/perception/create")
def create_perception(doc: Perception, validate: bool = Query(default=True)):
    """Create a Perception XML."""
    xml = render_perception(doc)
    return {"xml": xml}


@router.post("/retention/create")
def create_retention(doc: Retention, validate: bool = Query(default=True)):
    """Create a Retention XML."""
    xml = render_retention(doc)
    return {"xml": xml}


@router.post("/sign")
def sign_xml(payload: dict):
    """Sign an XML document with PEM cert/key."""
    xml = payload.get("xml", "")
    cert_pem = payload.get("cert_pem", "")
    key_pem = payload.get("key_pem", "")
    signature_id = payload.get("signature_id", "SignSUNAT")
    signed = sign_ubl_xml(xml, cert_pem, key_pem, signature_id)
    return {"signed_xml": signed}
