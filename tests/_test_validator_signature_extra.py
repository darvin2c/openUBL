"""
Tests extra parametrizados para reglas SUNAT de firma cac:Signature (2076-2083).

Estas reglas ya están cubiertas en tests/test_validator.py::TestValidatorSignedXml.
Este archivo existe como verificación adicional siguiendo la convención del plan.

Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú,
hoja "Firma" (códigos 2076-2101, 2084-2098).
https://cpe.sunat.gob.pe/guias-y-manuales
"""
import datetime
from datetime import date
from decimal import Decimal

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from openubl.enricher import ContentEnricher
from openubl.models import Cliente, DocumentoVentaDetalle, Invoice, Proveedor
from openubl.renderer import render_invoice
from openubl.signer import sign_ubl_xml
from openubl.validator import SunatValidator


NS = {
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}


def _signed_invoice_root() -> etree._Element:
    invoice = Invoice(
        serie="F001",
        numero=1,
        proveedor=Proveedor(ruc="20100066603", razonSocial="Test S.A.C."),
        cliente=Cliente(
            nombre="Test",
            numeroDocumentoIdentidad="12345678",
            tipoDocumentoIdentidad="1",
        ),
        detalles=[
            DocumentoVentaDetalle(
                descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100")
            )
        ],
        fechaEmision=date(2024, 1, 1),
    )
    ContentEnricher().enrich(invoice)
    xml = render_invoice(invoice)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test")]))
        .serial_number(1)
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1))
        .public_key(key.public_key())
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()

    signed_xml = sign_ubl_xml(xml, cert_pem, key_pem)
    return etree.fromstring(signed_xml.encode("utf-8"))


def _remove_node(root: etree._Element, xpath: str) -> None:
    elem = root.xpath(xpath, namespaces=NS)[0]
    elem.getparent().remove(elem)


def _set_text(root: etree._Element, xpath: str, value: str) -> None:
    elem = root.xpath(xpath, namespaces=NS)[0]
    elem.text = value


@pytest.fixture
def validator() -> SunatValidator:
    return SunatValidator()


@pytest.mark.parametrize(
    "code,mutator",
    [
        # 2076: No existe cac:Signature/cbc:ID
        ("2076", lambda r: _remove_node(r, "//cac:Signature/cbc:ID")),
        # 2077: Formato del cac:Signature/cbc:ID > 3000 caracteres
        ("2077", lambda r: _set_text(r, "//cac:Signature/cbc:ID", "x" * 3001)),
        # 2079: No existe SignatoryParty/PartyIdentification/ID
        (
            "2079",
            lambda r: _remove_node(
                r, "//cac:Signature/cac:SignatoryParty/cac:PartyIdentification/cbc:ID"
            ),
        ),
        # 2078: SignatoryParty/PartyIdentification/ID diferente al RUC del emisor
        (
            "2078",
            lambda r: _set_text(
                r,
                "//cac:Signature/cac:SignatoryParty/cac:PartyIdentification/cbc:ID",
                "12345678901",
            ),
        ),
        # 2081: No existe SignatoryParty/PartyName/Name
        (
            "2081",
            lambda r: _remove_node(
                r, "//cac:Signature/cac:SignatoryParty/cac:PartyName/cbc:Name"
            ),
        ),
        # 2080: Formato del SignatoryParty/PartyName/Name > 3000 caracteres
        (
            "2080",
            lambda r: _set_text(
                r, "//cac:Signature/cac:SignatoryParty/cac:PartyName/cbc:Name", "x" * 3001
            ),
        ),
        # 2083: No existe DigitalSignatureAttachment/ExternalReference/URI
        (
            "2083",
            lambda r: _remove_node(
                r,
                "//cac:Signature/cac:DigitalSignatureAttachment/cac:ExternalReference/cbc:URI",
            ),
        ),
        # 2082: Formato del DigitalSignatureAttachment/ExternalReference/URI > 3000 caracteres
        (
            "2082",
            lambda r: _set_text(
                r,
                "//cac:Signature/cac:DigitalSignatureAttachment/cac:ExternalReference/cbc:URI",
                "x" * 3001,
            ),
        ),
    ],
)
def test_signature_party_rule(code: str, mutator, validator: SunatValidator) -> None:
    root = _signed_invoice_root()
    mutator(root)
    bad_xml = etree.tostring(root, encoding="unicode")
    errors = validator.validate_signature(bad_xml)
    codes = [e.code for e in errors]
    assert code in codes, f"Expected error {code} in {codes}"


def test_signed_invoice_valid_signature_party(validator: SunatValidator) -> None:
    """Un XML firmado válido no reporta errores en cac:Signature."""
    root = _signed_invoice_root()
    xml = etree.tostring(root, encoding="unicode")
    errors = validator.validate_signature(xml)
    party_errors = [e for e in errors if e.code in {"2076", "2077", "2078", "2079", "2080", "2081", "2082", "2083"}]
    assert party_errors == [], f"Unexpected signature party errors: {party_errors}"
