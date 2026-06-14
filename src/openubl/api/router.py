"""
FastAPI router for openUBL REST API.

openUBL Server es una capa puramente técnica SUNAT:
recibe JSON, enriquece, renderiza, valida opcionalmente y firma opcionalmente.
No genera ZIP, no envía a SUNAT ni recibe CDR.
"""
import base64
import binascii

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
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


# ---------------------------------------------------------------------------
XSD_INVOICE = "sunat_schemas/xsd_2.1/2.1/maindoc/UBL-Invoice-2.1.xsd"
XSD_CREDIT_NOTE = "sunat_schemas/xsd_2.1/2.1/maindoc/UBL-CreditNote-2.1.xsd"
XSD_DEBIT_NOTE = "sunat_schemas/xsd_2.1/2.1/maindoc/UBL-DebitNote-2.1.xsd"
XSD_VOIDED_DOCUMENTS = "sunat_schemas/xsd_2.1/2.0/maindoc/UBLPE-VoidedDocuments-1.0.xsd"
XSD_SUMMARY_DOCUMENTS = "sunat_schemas/xsd_2.1/2.0/maindoc/UBLPE-SummaryDocuments-1.0.xsd"
XSD_PERCEPTION = "sunat_schemas/xsd_2.1/2.0/maindoc/UBLPE-Perception-1.0.xsd"
XSD_RETENTION = "sunat_schemas/xsd_2.1/2.0/maindoc/UBLPE-Retention-1.0.xsd"


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class Credentials(BaseModel):
    """Credenciales para firma digital."""
    cert_pem: str | None = None
    key_pem: str | None = None
    pfx_base64: str | None = None
    pfx_password: str | None = None


class CreateResponse(BaseModel):
    """Respuesta unificada de los endpoints /create."""
    xml: str
    firmado: bool
    validado_sunat: bool
    valid: bool | None = None
    errors: list[dict] | None = None


class InvoiceCreateRequest(BaseModel):
    """Request para crear una factura."""
    documento: Invoice
    credenciales: Credentials | None = None
    firmar: bool = False
    validar_sunat: bool = True
    signature_id: str = "SignSUNAT"


class CreditNoteCreateRequest(BaseModel):
    """Request para crear una nota de crédito."""
    documento: CreditNote
    credenciales: Credentials | None = None
    firmar: bool = False
    validar_sunat: bool = True
    signature_id: str = "SignSUNAT"


class DebitNoteCreateRequest(BaseModel):
    """Request para crear una nota de débito."""
    documento: DebitNote
    credenciales: Credentials | None = None
    firmar: bool = False
    validar_sunat: bool = True
    signature_id: str = "SignSUNAT"


class VoidedDocumentsCreateRequest(BaseModel):
    """Request para crear una comunicación de baja."""
    documento: VoidedDocuments
    credenciales: Credentials | None = None
    firmar: bool = False
    validar_sunat: bool = True
    signature_id: str = "SignSUNAT"


class SummaryDocumentsCreateRequest(BaseModel):
    """Request para crear un resumen diario."""
    documento: SummaryDocuments
    credenciales: Credentials | None = None
    firmar: bool = False
    validar_sunat: bool = True
    signature_id: str = "SignSUNAT"


class PerceptionCreateRequest(BaseModel):
    """Request para crear una percepción."""
    documento: Perception
    credenciales: Credentials | None = None
    firmar: bool = False
    validar_sunat: bool = True
    signature_id: str = "SignSUNAT"


class RetentionCreateRequest(BaseModel):
    """Request para crear una retención."""
    documento: Retention
    credenciales: Credentials | None = None
    firmar: bool = False
    validar_sunat: bool = True
    signature_id: str = "SignSUNAT"


class SignedXmlResponse(BaseModel):
    """Response containing signed XML document."""
    signed_xml: str


validator = SunatValidator()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_credentials(cred: Credentials | None) -> tuple[str, str]:
    """Resolve PEM cert/key from credentials or raise HTTP 422."""
    if cred is None:
        raise HTTPException(
            status_code=422,
            detail=[{"code": "422", "message": "Debe proporcionar credenciales cuando firmar=true."}],
        )

    if cred.pfx_base64 and cred.pfx_password:
        try:
            pfx_bytes = base64.b64decode(cred.pfx_base64)
        except (ValueError, binascii.Error):
            raise HTTPException(
                status_code=422,
                detail=[{"code": "422", "message": "pfx_base64 no es un base64 válido."}],
            )
        try:
            key_pem, cert_pem = load_pfx(pfx_bytes, cred.pfx_password)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=[{"code": "422", "message": "No se pudo desencriptar el PFX: verifique el password."}],
            )
        return cert_pem, key_pem

    if cred.cert_pem and cred.key_pem:
        return cred.cert_pem, cred.key_pem

    raise HTTPException(
        status_code=422,
        detail=[{"code": "422", "message": "Debe proporcionar cert_pem y key_pem, o pfx_base64 y pfx_password."}],
    )


def _validate_document(xml: str, doc_type: str, xsd_path: str) -> list[dict]:
    """Run SUNAT validation (XSD + business rules) and return error dicts."""
    errors = validator.validate_schema(xml, xsd_path)
    if errors:
        return [e.to_dict() for e in errors]

    if doc_type == "invoice":
        errors = validator.validate_invoice(xml)
    elif doc_type == "credit_note":
        errors = validator.validate_credit_note(xml)
    elif doc_type == "debit_note":
        errors = validator.validate_debit_note(xml)
    elif doc_type == "voided_documents":
        errors = validator.validate_voided_documents(xml)
    elif doc_type == "summary_documents":
        errors = validator.validate_summary_documents(xml)
    elif doc_type == "perception":
        errors = validator.validate_perception(xml)
    elif doc_type == "retention":
        errors = validator.validate_retention(xml)
    else:
        return []

    return [e.to_dict() for e in errors]


def _create_document_response(
    xml: str,
    req,
    doc_type: str,
    xsd_path: str,
) -> CreateResponse:
    """Common flow: validate, sign, build response."""
    errors: list[dict] = []
    signed = False

    if req.validar_sunat:
        errors = _validate_document(xml, doc_type, xsd_path)
        if errors:
            raise HTTPException(status_code=422, detail=errors)

    if req.firmar:
        cert_pem, key_pem = _resolve_credentials(req.credenciales)
        xml = sign_ubl_xml(xml, cert_pem, key_pem, req.signature_id)
        signed = True
    return CreateResponse(
        xml=xml,
        firmado=signed,
        validado_sunat=req.validar_sunat,
        valid=(len(errors) == 0) if req.validar_sunat else None,
        errors=errors if req.validar_sunat else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/version", operation_id="getVersion")
def get_version():
    """Return the current API version.

    Returns:
        200: `{"version": "..."}` with the current API version.
    """
    return {"version": __version__}


@router.post("/invoice/create", response_model=CreateResponse, operation_id="createInvoice")
def create_invoice(req: InvoiceCreateRequest):
    """Generate an Invoice XML document.

    - `documento`: modelo `Invoice`.
    - `credenciales`: opcional; obligatorio si `firmar=true`.
    - `firmar`: firma el XML antes de responder.
    - `validar_sunat`: ejecuta validación XSD + reglas SUNAT.
    """
    doc = req.documento
    ContentEnricher().enrich(doc)
    xml = render_invoice(doc)
    return _create_document_response(xml, req, "invoice", XSD_INVOICE)
@router.post("/credit-note/create", response_model=CreateResponse, operation_id="createCreditNote")
def create_credit_note(req: CreditNoteCreateRequest):
    """Generate a CreditNote XML document."""
    doc = req.documento
    ContentEnricher().enrich(doc)
    xml = render_credit_note(doc)
    return _create_document_response(xml, req, "credit_note", XSD_CREDIT_NOTE)


@router.post("/debit-note/create", response_model=CreateResponse, operation_id="createDebitNote")
def create_debit_note(req: DebitNoteCreateRequest):
    """Generate a DebitNote XML document."""
    doc = req.documento
    ContentEnricher().enrich(doc)
    xml = render_debit_note(doc)
    return _create_document_response(xml, req, "debit_note", XSD_DEBIT_NOTE)


@router.post("/voided-documents/create", response_model=CreateResponse, operation_id="createVoidedDocuments")
def create_voided_documents(req: VoidedDocumentsCreateRequest):
    """Generate a VoidedDocuments XML document."""
    doc = req.documento
    ContentEnricher().enrich(doc)
    xml = render_voided_documents(doc)
    return _create_document_response(xml, req, "voided_documents", XSD_VOIDED_DOCUMENTS)


@router.post("/summary-documents/create", response_model=CreateResponse, operation_id="createSummaryDocuments")
def create_summary_documents(req: SummaryDocumentsCreateRequest):
    """Generate a SummaryDocuments XML document."""
    xml = render_summary_documents(req.documento)
    return _create_document_response(xml, req, "summary_documents", XSD_SUMMARY_DOCUMENTS)


@router.post("/perception/create", response_model=CreateResponse, operation_id="createPerception")
def create_perception(req: PerceptionCreateRequest):
    """Generate a Perception XML document."""
    xml = render_perception(req.documento)
    return _create_document_response(xml, req, "perception", XSD_PERCEPTION)


@router.post("/retention/create", response_model=CreateResponse, operation_id="createRetention")
def create_retention(req: RetentionCreateRequest):
    """Generate a Retention XML document."""
    xml = render_retention(req.documento)
    return _create_document_response(xml, req, "retention", XSD_RETENTION)


@router.post("/sign", response_model=SignedXmlResponse, operation_id="signXml")
def sign_xml(payload: dict):
    """Sign an arbitrary UBL XML document with PEM or PFX credentials.

    Required body fields (choose one credential mode):
        * PEM mode: `cert_pem` and `key_pem`.
        * PFX/P12 mode: `pfx_base64` and `pfx_password`.

    Optional body fields:
        * `xml`: The XML string to sign.
        * `signature_id`: The signature ID (defaults to `SignSUNAT`).

    Returns:
        200: `{"signed_xml": "..."}` with the signed XML.
    """
    xml = payload.get("xml", "")
    signature_id = payload.get("signature_id", "SignSUNAT")

    cred = Credentials(
        cert_pem=payload.get("cert_pem"),
        key_pem=payload.get("key_pem"),
        pfx_base64=payload.get("pfx_base64"),
        pfx_password=payload.get("pfx_password"),
    )
    cert_pem, key_pem = _resolve_credentials(cred)
    signed = sign_ubl_xml(xml, cert_pem, key_pem, signature_id)

    sig_errors = validator.validate_signature(signed)
    if sig_errors:
        raise HTTPException(status_code=422, detail=[e.to_dict() for e in sig_errors])

    return {"signed_xml": signed}
