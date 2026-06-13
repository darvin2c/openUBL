"""
FastAPI router for openUBL REST API.
"""
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from openubl import __version__

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
from ..signer import load_pfx, sign_ubl_xml
from ..validator import SunatValidator


router = APIRouter()

class XmlResponse(BaseModel):
    """Response containing generated XML document."""
    xml: str


class SignedXmlResponse(BaseModel):
    """Response containing signed XML document."""
    signed_xml: str

validator = SunatValidator()


@router.get("/version", operation_id="getVersion")
def get_version():
    """Return the current API version.

    Returns:
        200: `{"version": "..."}` with the current API version.
    """
    return {"version": __version__}


def _validate_xml(xml_string: str, doc_type: str) -> list[str]:
    """Run SUNAT validation on rendered XML."""
    if doc_type == "invoice":
        return validator.validate_invoice(xml_string)
    elif doc_type == "credit_note":
        return validator.validate_credit_note(xml_string)
    elif doc_type == "voided":
        return validator.validate_voided_documents(xml_string)
    return []


@router.post("/invoice/create", response_model=XmlResponse, operation_id="createInvoice")
def create_invoice(doc: Invoice, validate: bool = Query(default=True)):
    """Generate an Invoice XML document.

    The `validate` query parameter controls SUNAT validation and defaults to `true`.

    Returns:
        200: `{"xml": "..."}` with the generated XML.
        422: Validation failed or the request body is invalid.
    """
    enricher = ContentEnricher()
    enricher.enrich(doc)
    xml = render_invoice(doc)
    if validate:
        errors = _validate_xml(xml, "invoice")
        if errors:
            raise HTTPException(status_code=422, detail=errors)
    return {"xml": xml}


@router.post("/credit-note/create", response_model=XmlResponse, operation_id="createCreditNote")
def create_credit_note(doc: CreditNote, validate: bool = Query(default=True)):
    """Generate a CreditNote XML document.

    The `validate` query parameter controls SUNAT validation and defaults to `true`.

    Returns:
        200: `{"xml": "..."}` with the generated XML.
        422: Validation failed or the request body is invalid.
    """
    enricher = ContentEnricher()
    enricher.enrich(doc)
    xml = render_credit_note(doc)
    if validate:
        errors = _validate_xml(xml, "credit_note")
        if errors:
            raise HTTPException(status_code=422, detail=errors)
    return {"xml": xml}


@router.post("/debit-note/create", response_model=XmlResponse, operation_id="createDebitNote")
def create_debit_note(doc: DebitNote, validate: bool = Query(default=True)):
    """Generate a DebitNote XML document.

    The `validate` query parameter controls SUNAT validation and defaults to `true`.

    Returns:
        200: `{"xml": "..."}` with the generated XML.
        422: Validation failed or the request body is invalid.
    """
    enricher = ContentEnricher()
    enricher.enrich(doc)
    xml = render_debit_note(doc)
    if validate:
        errors = _validate_xml(xml, "credit_note")
        if errors:
            raise HTTPException(status_code=422, detail=errors)
    return {"xml": xml}


@router.post("/voided-documents/create", response_model=XmlResponse, operation_id="createVoidedDocuments")
def create_voided_documents(doc: VoidedDocuments, validate: bool = Query(default=True)):
    """Generate a VoidedDocuments XML document.

    The `validate` query parameter controls SUNAT validation and defaults to `true`.

    Returns:
        200: `{"xml": "..."}` with the generated XML.
        422: Validation failed or the request body is invalid.
    """
    enricher = ContentEnricher()
    enricher.enrich(doc)
    xml = render_voided_documents(doc)
    if validate:
        errors = _validate_xml(xml, "voided")
        if errors:
            raise HTTPException(status_code=422, detail=errors)
    return {"xml": xml}


@router.post("/summary-documents/create", response_model=XmlResponse, operation_id="createSummaryDocuments")
def create_summary_documents(doc: SummaryDocuments, validate: bool = Query(default=True)):
    """Generate a SummaryDocuments XML document.

    The `validate` query parameter controls SUNAT validation and defaults to `true`.

    Returns:
        200: `{"xml": "..."}` with the generated XML.
        422: Validation failed or the request body is invalid.
    """
    xml = render_summary_documents(doc)
    return {"xml": xml}


@router.post("/perception/create", response_model=XmlResponse, operation_id="createPerception")
def create_perception(doc: Perception, validate: bool = Query(default=True)):
    """Generate a Perception XML document.

    The `validate` query parameter controls SUNAT validation and defaults to `true`.

    Returns:
        200: `{"xml": "..."}` with the generated XML.
        422: Validation failed or the request body is invalid.
    """
    xml = render_perception(doc)
    return {"xml": xml}


@router.post("/retention/create", response_model=XmlResponse, operation_id="createRetention")
def create_retention(doc: Retention, validate: bool = Query(default=True)):
    """Generate a Retention XML document.

    The `validate` query parameter controls SUNAT validation and defaults to `true`.

    Returns:
        200: `{"xml": "..."}` with the generated XML.
        422: Validation failed or the request body is invalid.
    """
    xml = render_retention(doc)
    return {"xml": xml}


@router.post("/sign", response_model=SignedXmlResponse, operation_id="signXml")
def sign_xml(payload: dict):
    """Sign an arbitrary UBL XML document with a PEM certificate/key pair or a PFX/P12 container.

    Required body fields (choose one credential mode):
        * PEM mode: `cert_pem` and `key_pem`.
        * PFX/P12 mode: `pfx_base64` (standard base64 of the file) and `pfx_password`.

    Optional body fields:
        * `xml`: The XML string to sign.
        * `signature_id`: The signature ID (defaults to `SignSUNAT`).

    Returns:
        200: `{"signed_xml": "..."}` with the signed XML.
    """
    xml = payload.get("xml", "")
    signature_id = payload.get("signature_id", "SignSUNAT")

    if "pfx_base64" in payload and "pfx_password" in payload:
        import base64
        import binascii

        try:
            pfx_bytes = base64.b64decode(payload["pfx_base64"])
        except (ValueError, binascii.Error):
            raise HTTPException(
                status_code=422,
                detail="pfx_base64 no es un base64 válido.",
            )
        try:
            key_pem, cert_pem = load_pfx(pfx_bytes, payload["pfx_password"])
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="No se pudo desencriptar el PFX: verifique el password.",
            )
        signed = sign_ubl_xml(xml, cert_pem, key_pem, signature_id)
    elif "cert_pem" in payload and "key_pem" in payload:
        cert_pem = payload["cert_pem"]
        key_pem = payload["key_pem"]
        signed = sign_ubl_xml(xml, cert_pem, key_pem, signature_id)
    else:
        raise HTTPException(
            status_code=422,
            detail="Debe proporcionar cert_pem y key_pem, o pfx_base64 y pfx_password.",
        )

    return {"signed_xml": signed}
