"""
Tests for SUNAT rule validation.

Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
https://cpe.sunat.gob.pe/guias-y-manuales
"""
import os
import re
from copy import deepcopy
import pytest
from decimal import Decimal
from datetime import date, timedelta
from lxml import etree

from openubl.models import Invoice, CreditNote, DebitNote, Proveedor, Cliente, DocumentoVentaDetalle, Perception, Retention, PercepcionRetencionOperacion
from openubl.models.perception import ComprobanteAfectado
from openubl.enricher import ContentEnricher
from openubl.renderer import render_invoice, render_credit_note, render_debit_note, render_perception, render_retention
from openubl.validator import SunatValidator


def remove_attr(root: etree._Element, xpath: str, attr: str, namespaces: dict | None = None) -> None:
    ns = namespaces or {
        "ds": "http://www.w3.org/2000/09/xmldsig#",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    }
    for elem in root.xpath(xpath, namespaces=ns):
        if attr in elem.attrib:
            del elem.attrib[attr]


def set_attr(root: etree._Element, xpath: str, attr: str, value: str, namespaces: dict | None = None) -> None:
    ns = namespaces or {
        "ds": "http://www.w3.org/2000/09/xmldsig#",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    }
    elem = root.xpath(xpath, namespaces=ns)[0]
    elem.set(attr, value)


def remove_node(root: etree._Element, xpath: str, namespaces: dict | None = None) -> None:
    ns = namespaces or {
        "ds": "http://www.w3.org/2000/09/xmldsig#",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    }
    elem = root.xpath(xpath, namespaces=ns)[0]
    elem.getparent().remove(elem)


def set_text(root: etree._Element, xpath: str, value: str, namespaces: dict | None = None) -> None:
    ns = namespaces or {
        "ds": "http://www.w3.org/2000/09/xmldsig#",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    }
    elem = root.xpath(xpath, namespaces=ns)[0]
    elem.text = value



class TestValidatorInvoice:
    def setup_method(self):
        self.validator = SunatValidator()
        self.invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Softgreen S.A.C."),
            cliente=Cliente(nombre="Carlos Feria", numeroDocumentoIdentidad="12121212121", tipoDocumentoIdentidad="6"),
            detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("10"), precio=Decimal("100"))],
            fechaEmision=date(2024, 1, 1),
        )
        enricher = ContentEnricher()
        enricher.enrich(self.invoice)
        self.xml = render_invoice(self.invoice)

    def test_schema_validation_invoice(self):
        """RS N° 300-2014/SUNAT - XML debe cumplir esquema UBL 2.1."""
        xsd_path = os.path.join("sunat_schemas", "xsd_2.1", "2.1", "maindoc", "UBL-Invoice-2.1.xsd")
        if os.path.exists(xsd_path):
            errors = self.validator.validate_schema(self.xml, xsd_path)
            if errors and "does not resolve" in errors[0].message:
                pytest.skip("SUNAT XSD dependencies not fully resolved")
            assert errors == []

    def test_invoice_ubl_version_error_2074(self):
        """ERROR 2074: UBLVersionID != '2.1' → rechazo inmediato."""
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cbc:UBLVersionID", namespaces=ns).text = "2.0"
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any(e.code == "2074" for e in errors)

    def test_invoice_customization_id_error_2072(self):
        """ERROR 2072: CustomizationID != '2.0' → rechazo."""
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cbc:CustomizationID", namespaces=ns).text = "1.0"
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any(e.code == "2072" for e in errors)

    def test_invoice_invalid_id_error_1001(self):
        """ERROR 1001: ID no cumple formato."""
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cbc:ID", namespaces=ns).text = "INVALID"
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any(e.code == "1001" for e in errors)

    def test_invoice_missing_currency_error_2070(self):
        """ERROR 2070: DocumentCurrencyCode vacío → rechazo."""
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        elem = root.find("cbc:DocumentCurrencyCode", namespaces=ns)
        root.remove(elem)
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any(e.code == "2070" for e in errors)

    def test_invoice_missing_supplier_name_error_1037(self):
        """ERROR 1037: RegistrationName vacío → rechazo."""
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName", namespaces=ns).text = ""
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any(e.code == "1037" for e in errors)

    def test_invoice_tax_total_mismatch_error_3294(self):
        """ERROR 3294: TaxTotal global no cuadra con sumatoria de líneas ±1."""
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cac:TaxTotal/cbc:TaxAmount", namespaces=ns).text = "999.99"
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any(e.code == "3294" for e in errors)

    def test_invoice_line_extension_amount_error_3278(self):
        """ERROR 3278: LineExtensionAmount global no cuadra con sumatoria de líneas ±1."""
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cac:LegalMonetaryTotal/cbc:LineExtensionAmount", namespaces=ns).text = "500.00"
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any(e.code == "3278" for e in errors)

    def test_invoice_payable_amount_zero_error_2062(self):
        """ERROR 2062: PayableAmount ≤ 0 → rechazo."""
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cac:LegalMonetaryTotal/cbc:PayableAmount", namespaces=ns).text = "0.00"
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any(e.code == "2062" for e in errors)


class TestValidatorSignedXml:
    """Tests for SUNAT signature sheet rules (codes 2076-2101).

    Fuente: Excel "Reglas de validación actualizado al 24.04.2026",
    hoja "Firma" (códigos 2076-2101, 2084-2098).
    """

    def setup_method(self):
        self.validator = SunatValidator()

    def _render_and_sign(self):
        from openubl.signer import sign_ubl_xml
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.x509 import CertificateBuilder, Name, NameAttribute
        from cryptography.x509.oid import NameOID
        import datetime

        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100"))],
            fechaEmision=date(2024, 1, 1),
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)
        xml = render_invoice(invoice)

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cert = CertificateBuilder().subject_name(Name([NameAttribute(NameOID.COMMON_NAME, "Test")])).issuer_name(Name([NameAttribute(NameOID.COMMON_NAME, "Test")])).serial_number(1).not_valid_before(datetime.datetime.utcnow()).not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1)).public_key(key.public_key()).sign(key, hashes.SHA256())
        key_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()).decode()
        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()

        return sign_ubl_xml(xml, cert_pem, key_pem)

    def _signed_root(self):
        return etree.fromstring(self._render_and_sign().encode("utf-8"))

    @pytest.mark.parametrize("code,mutator", [
        ("2085", lambda r: r.xpath("//ds:Signature", namespaces={"ds": "http://www.w3.org/2000/09/xmldsig#"})[0].attrib.pop("Id", None)),
        ("2084", lambda r: r.xpath("//ds:Signature", namespaces={"ds": "http://www.w3.org/2000/09/xmldsig#"})[0].set("Id", "x" * 3001)),
        ("2087", lambda r: remove_attr(r, "//ds:CanonicalizationMethod", "Algorithm")),
        ("2086", lambda r: set_attr(r, "//ds:CanonicalizationMethod", "Algorithm", "x" * 3001)),
        ("2089", lambda r: set_attr(r, "//ds:SignatureMethod", "Algorithm", "http://www.w3.org/2000/09/xmldsig#rsa-sha1")),
        ("2088", lambda r: set_attr(r, "//ds:SignatureMethod", "Algorithm", "x" * 3001)),
        ("2091", lambda r: remove_attr(r, "//ds:Reference", "URI")),
        ("2090", lambda r: set_attr(r, "//ds:Reference", "URI", "   ")),
        ("2093", lambda r: [t.attrib.pop("Algorithm", None) for t in r.xpath("//ds:Transform", namespaces={"ds": "http://www.w3.org/2000/09/xmldsig#"})]),
        ("2092", lambda r: set_attr(r, "//ds:Transform", "Algorithm", "x" * 3001)),
        ("2095", lambda r: set_attr(r, "//ds:DigestMethod", "Algorithm", "http://www.w3.org/2000/09/xmldsig#sha1")),
        ("2099", lambda r: remove_node(r, "//ds:SignatureValue")),
        ("2098", lambda r: set_text(r, "//ds:SignatureValue", "!!")),
        ("2101", lambda r: remove_node(r, "//ds:X509Certificate")),
        ("2100", lambda r: set_text(r, "//ds:X509Certificate", "!!")),
        ("2076", lambda r: remove_node(r, "//cac:Signature/cbc:ID")),
        ("2077", lambda r: set_text(r, "//cac:Signature/cbc:ID", "x" * 3001)),
        ("2079", lambda r: remove_node(r, "//cac:Signature/cac:SignatoryParty/cac:PartyIdentification/cbc:ID")),
        ("2078", lambda r: set_text(r, "//cac:Signature/cac:SignatoryParty/cac:PartyIdentification/cbc:ID", "12345678901")),
        ("2081", lambda r: remove_node(r, "//cac:Signature/cac:SignatoryParty/cac:PartyName/cbc:Name")),
        ("2080", lambda r: set_text(r, "//cac:Signature/cac:SignatoryParty/cac:PartyName/cbc:Name", "x" * 3001)),
        ("2083", lambda r: remove_node(r, "//cac:Signature/cac:DigitalSignatureAttachment/cac:ExternalReference/cbc:URI")),
        ("2082", lambda r: set_text(r, "//cac:Signature/cac:DigitalSignatureAttachment/cac:ExternalReference/cbc:URI", "x" * 3001)),
    ])
    def test_signature_rule(self, code, mutator):
        root = self._signed_root()
        mutator(root)
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_signature(bad_xml)
        codes = [e.code for e in errors]
        assert code in codes, f"Expected error {code} in {codes}"

    def test_signed_xml_uses_sha256(self):
        """INDECOPI/IOFE y PCM Directiva 002-2024 exigen SHA-256."""
        signed = self._render_and_sign()
        errors = self.validator.validate_signature(signed)
        assert errors == []

    def test_validate_signature_no_signature_returns_2085(self):
        """validate_signature debe funcionar para XML arbitrario sin firma."""
        errors = self.validator.validate_signature("<root/>")
        assert any(e.code == "2085" for e in errors)

    def test_validate_signature_arbitrary_xml_with_bad_signature(self):
        """XML arbitrario con estructura de firma inválida reporta errores."""
        xml = '''<root xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
            <ds:Signature Id="S"><ds:SignedInfo><ds:Reference URI=""/></ds:SignedInfo></ds:Signature>
        </root>'''
        errors = self.validator.validate_signature(xml)
        codes = {e.code for e in errors}
        assert "2085" not in codes
        assert "2087" in codes  # falta CanonicalizationMethod


class TestValidatorVoidedDocuments:
    """Tests para reglas SUNAT de VoidedDocuments (Comunicación de Baja).

    Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
    https://cpe.sunat.gob.pe/guias-y-manuales
    """

    def _valid_xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<VoidedDocuments xmlns="urn:sunat:names:specification:ubl:peru:schema:xsd:VoidedDocuments-1"'
            ' xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"'
            ' xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"'
            ' xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1">'
            '<cbc:UBLVersionID>2.0</cbc:UBLVersionID>'
            '<cbc:CustomizationID>1.0</cbc:CustomizationID>'
            '<cbc:ID>RA-20240101-1</cbc:ID>'
            '<cbc:ReferenceDate>2024-01-01</cbc:ReferenceDate>'
            '<cbc:IssueDate>2024-01-01</cbc:IssueDate>'
            '<cac:AccountingSupplierParty>'
            '<cbc:CustomerAssignedAccountID>20100066603</cbc:CustomerAssignedAccountID>'
            '<cbc:AdditionalAccountID>6</cbc:AdditionalAccountID>'
            '<cac:Party><cac:PartyLegalEntity><cbc:RegistrationName>Test SA</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party>'
            '</cac:AccountingSupplierParty>'
            '<sac:VoidedDocumentsLine>'
            '<cbc:LineID>1</cbc:LineID>'
            '<cbc:DocumentTypeCode>01</cbc:DocumentTypeCode>'
            '<cbc:DocumentSerialID>F001</cbc:DocumentSerialID>'
            '<cbc:DocumentNumberID>1</cbc:DocumentNumberID>'
            '<cbc:VoidReasonDescription>Error</cbc:VoidReasonDescription>'
            '</sac:VoidedDocumentsLine>'
            '</VoidedDocuments>'
        )

    def test_voided_documents_valid(self):
        errors = SunatValidator().validate_voided_documents(self._valid_xml())
        assert errors == []

    @pytest.mark.parametrize("code,mutator", [
        ("2074", lambda xml: xml.replace("<cbc:UBLVersionID>2.0</cbc:UBLVersionID>", "<cbc:UBLVersionID>2.1</cbc:UBLVersionID>")),
        ("2075", lambda xml: xml.replace("<cbc:UBLVersionID>2.0</cbc:UBLVersionID>", "<cbc:UBLVersionID></cbc:UBLVersionID>")),
        ("2072", lambda xml: xml.replace("<cbc:CustomizationID>1.0</cbc:CustomizationID>", "<cbc:CustomizationID>2.0</cbc:CustomizationID>")),
        ("2220", lambda xml: xml.replace("<cbc:ID>RA-20240101-1</cbc:ID>", "<cbc:ID>RA-20240101</cbc:ID>")),
        ("2346", lambda xml: xml.replace("<cbc:ID>RA-20240101-1</cbc:ID>", "<cbc:ID>RA-20240102-1</cbc:ID>")),
        ("2301", lambda xml: xml.replace("<cbc:IssueDate>2024-01-01</cbc:IssueDate>", f"<cbc:IssueDate>{(date.today() + timedelta(days=1)).isoformat()}</cbc:IssueDate>")),
        ("2671", lambda xml: xml.replace("<cbc:ReferenceDate>2024-01-01</cbc:ReferenceDate>", "<cbc:ReferenceDate>2024-01-02</cbc:ReferenceDate>")),
        ("2288", lambda xml: xml.replace("<cbc:CustomerAssignedAccountID>20100066603</cbc:CustomerAssignedAccountID>", "")),
        ("1034", lambda xml: xml.replace("<cbc:CustomerAssignedAccountID>20100066603</cbc:CustomerAssignedAccountID>", "<cbc:CustomerAssignedAccountID>2010006660</cbc:CustomerAssignedAccountID>")),
        ("2287", lambda xml: xml.replace("<cbc:AdditionalAccountID>6</cbc:AdditionalAccountID>", "<cbc:AdditionalAccountID>1</cbc:AdditionalAccountID>")),
        ("2229", lambda xml: xml.replace("<cbc:RegistrationName>Test SA</cbc:RegistrationName>", "<cbc:RegistrationName></cbc:RegistrationName>")),
        ("2228", lambda xml: xml.replace("<cbc:RegistrationName>Test SA</cbc:RegistrationName>", "<cbc:RegistrationName>AB</cbc:RegistrationName>")),
        ("2307", lambda xml: xml.replace("<cbc:LineID>1</cbc:LineID>", "<cbc:LineID></cbc:LineID>")),
        ("2305", lambda xml: xml.replace("<cbc:LineID>1</cbc:LineID>", "<cbc:LineID>abc</cbc:LineID>")),
        ("2306", lambda xml: xml.replace("<cbc:LineID>1</cbc:LineID>", "<cbc:LineID>0</cbc:LineID>")),
        ("2752", lambda xml: xml.replace(
            "</sac:VoidedDocumentsLine>",
            "</sac:VoidedDocumentsLine><sac:VoidedDocumentsLine>"
            "<cbc:LineID>1</cbc:LineID><cbc:DocumentTypeCode>01</cbc:DocumentTypeCode>"
            "<cbc:DocumentSerialID>F002</cbc:DocumentSerialID><cbc:DocumentNumberID>2</cbc:DocumentNumberID>"
            "<cbc:VoidReasonDescription>Error 2</cbc:VoidReasonDescription></sac:VoidedDocumentsLine>",
        )),
        ("2309", lambda xml: xml.replace("<cbc:DocumentTypeCode>01</cbc:DocumentTypeCode>", "<cbc:DocumentTypeCode></cbc:DocumentTypeCode>")),
        ("2308", lambda xml: xml.replace("<cbc:DocumentTypeCode>01</cbc:DocumentTypeCode>", "<cbc:DocumentTypeCode>99</cbc:DocumentTypeCode>")),
        ("2311", lambda xml: xml.replace("<cbc:DocumentSerialID>F001</cbc:DocumentSerialID>", "<cbc:DocumentSerialID></cbc:DocumentSerialID>")),
        ("2310", lambda xml: xml.replace("<cbc:DocumentSerialID>F001</cbc:DocumentSerialID>", "<cbc:DocumentSerialID>B001</cbc:DocumentSerialID>")),
        ("2313", lambda xml: xml.replace("<cbc:DocumentNumberID>1</cbc:DocumentNumberID>", "<cbc:DocumentNumberID></cbc:DocumentNumberID>")),
        ("2312", lambda xml: xml.replace("<cbc:DocumentNumberID>1</cbc:DocumentNumberID>", "<cbc:DocumentNumberID>123456789</cbc:DocumentNumberID>")),
        ("2348", lambda xml: xml.replace(
            "</sac:VoidedDocumentsLine>",
            "</sac:VoidedDocumentsLine><sac:VoidedDocumentsLine>"
            "<cbc:LineID>2</cbc:LineID><cbc:DocumentTypeCode>01</cbc:DocumentTypeCode>"
            "<cbc:DocumentSerialID>F001</cbc:DocumentSerialID><cbc:DocumentNumberID>1</cbc:DocumentNumberID>"
            "<cbc:VoidReasonDescription>Dup</cbc:VoidReasonDescription></sac:VoidedDocumentsLine>",
        )),
        ("2315", lambda xml: xml.replace("<cbc:VoidReasonDescription>Error</cbc:VoidReasonDescription>", "<cbc:VoidReasonDescription></cbc:VoidReasonDescription>")),
    ])
    def test_voided_documents_rule(self, code, mutator):
        xml = self._valid_xml()
        xml = mutator(xml)
        errors = SunatValidator().validate_voided_documents(xml)
        codes = [e.code for e in errors]
        assert code in codes, f"Expected error {code} in {codes}"


# ------------------------------------------------------------------
# Helpers para tests de Perception / Retention
# ------------------------------------------------------------------
P_NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
}
R_NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
}
_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
_SAC = "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"


def _set_text(root: etree._Element, xpath: str, value: str, ns: dict) -> None:
    elem = root.xpath(xpath, namespaces=ns)[0]
    elem.text = value


def _set_attr(root: etree._Element, xpath: str, attr: str, value: str, ns: dict) -> None:
    elem = root.xpath(xpath, namespaces=ns)[0]
    elem.set(attr, value)


def _remove_attr(root: etree._Element, xpath: str, attr: str, ns: dict) -> None:
    elem = root.xpath(xpath, namespaces=ns)[0]
    if attr in elem.attrib:
        del elem.attrib[attr]


def _remove_node(root: etree._Element, xpath: str, ns: dict) -> None:
    elem = root.xpath(xpath, namespaces=ns)[0]
    elem.getparent().remove(elem)


def _add_child(parent: etree._Element, ns_uri: str, tag: str, text: str | None = None, attrs: dict | None = None) -> etree._Element:
    child = etree.SubElement(parent, f"{{{ns_uri}}}{tag}")
    if text is not None:
        child.text = text
    for k, v in (attrs or {}).items():
        child.set(k, v)
    return child


def _valid_perception() -> str:
    p = Perception(
        serie="P001", numero=1, fechaEmision=date(2024, 1, 1),
        proveedor=Proveedor(ruc="20100066603", razonSocial="Agente S.A.C."),
        cliente=Cliente(nombre="Cliente SAC", numeroDocumentoIdentidad="12121212121", tipoDocumentoIdentidad="6"),
        importeTotalPercibido=Decimal("30.00"), importeTotalCobrado=Decimal("270.00"),
        tipoRegimen="01", tipoRegimenPorcentaje=Decimal("1"),
        operaciones=[
            PercepcionRetencionOperacion(
                numeroOperacion=1, fechaOperacion=date(2024, 1, 1), importeOperacion=Decimal("10.00"),
                comprobante=ComprobanteAfectado(tipoComprobante="01", serieNumero="F001-1", fechaEmision=date(2024, 1, 1), importeTotal=Decimal("100.00"), moneda="PEN"),
            ),
            PercepcionRetencionOperacion(
                numeroOperacion=2, fechaOperacion=date(2024, 1, 15), importeOperacion=Decimal("20.00"),
                comprobante=ComprobanteAfectado(tipoComprobante="01", serieNumero="F001-2", fechaEmision=date(2024, 1, 15), importeTotal=Decimal("200.00"), moneda="PEN"),
            ),
        ],
    )
    return render_perception(p)


def _valid_retention() -> str:
    r = Retention(
        serie="R001", numero=1, fechaEmision=date(2024, 1, 1),
        proveedor=Proveedor(ruc="20100066603", razonSocial="Agente S.A.C."),
        cliente=Cliente(nombre="Cliente SAC", numeroDocumentoIdentidad="20100066604", tipoDocumentoIdentidad="6"),
        importeTotalRetenido=Decimal("30.00"), importeTotalPagado=Decimal("270.00"),
        tipoRegimen="01", tipoRegimenPorcentaje=Decimal("3"),
        operaciones=[
            PercepcionRetencionOperacion(
                numeroOperacion=1, fechaOperacion=date(2024, 1, 1), importeOperacion=Decimal("10.00"),
                comprobante=ComprobanteAfectado(tipoComprobante="01", serieNumero="F001-1", fechaEmision=date(2024, 1, 1), importeTotal=Decimal("100.00"), moneda="PEN"),
            ),
            PercepcionRetencionOperacion(
                numeroOperacion=2, fechaOperacion=date(2024, 1, 15), importeOperacion=Decimal("20.00"),
                comprobante=ComprobanteAfectado(tipoComprobante="01", serieNumero="F001-2", fechaEmision=date(2024, 1, 15), importeTotal=Decimal("200.00"), moneda="PEN"),
            ),
        ],
    )
    return render_retention(r)


# ------------------------------------------------------------------
# Tests Perception
# ------------------------------------------------------------------
class TestValidatorPerception:
    @pytest.fixture
    def xml(self):
        return _valid_perception()

    @pytest.mark.parametrize("code,mutator", [
        ("2111", lambda r: _set_text(r, ".//cbc:UBLVersionID", "", P_NS)),
        ("2110", lambda r: _set_text(r, ".//cbc:UBLVersionID", "2.1", P_NS)),
        ("2113", lambda r: _set_text(r, ".//cbc:CustomizationID", "", P_NS)),
        ("2112", lambda r: _set_text(r, ".//cbc:CustomizationID", "2.0", P_NS)),
        ("1001", lambda r: _set_text(r, ".//cbc:ID", "INVALID", P_NS)),
        ("3322", lambda r: _add_child(r, _SAC, "ExceptionalIndicator", "02")),
        ("2678", lambda r: _remove_attr(r, ".//cac:AgentParty/cac:PartyIdentification/cbc:ID", "schemeID", P_NS)),
        ("2511", lambda r: _set_attr(r, ".//cac:AgentParty/cac:PartyIdentification/cbc:ID", "schemeID", "1", P_NS)),
        ("1037", lambda r: _set_text(r, ".//cac:AgentParty/cac:PartyLegalEntity/cbc:RegistrationName", "", P_NS)),
        ("1038", lambda r: _set_text(r, ".//cac:AgentParty/cac:PartyLegalEntity/cbc:RegistrationName", "x" * 1501, P_NS)),
        ("2548", lambda r: _add_agent_country(r, "US")),
        ("2679", lambda r: _remove_node(r, ".//cac:ReceiverParty/cac:PartyIdentification/cbc:ID", P_NS)),
        ("2680", lambda r: _set_text(r, ".//cac:ReceiverParty/cac:PartyIdentification/cbc:ID", "x" * 16, P_NS)),
        ("2604", lambda r: _set_text(r, ".//cac:ReceiverParty/cac:PartyIdentification/cbc:ID", "20100066603", P_NS)),
        ("2516", lambda r: _remove_attr(r, ".//cac:ReceiverParty/cac:PartyIdentification/cbc:ID", "schemeID", P_NS)),
        ("2134", lambda r: _set_text(r, ".//cac:ReceiverParty/cac:PartyLegalEntity/cbc:RegistrationName", "", P_NS)),
        ("2133", lambda r: _set_text(r, ".//cac:ReceiverParty/cac:PartyLegalEntity/cbc:RegistrationName", "x" * 1501, P_NS)),
        ("2669", lambda r: _set_text(r, ".//cbc:TotalInvoiceAmount", "0.00", P_NS)),
        ("2685", lambda r: _set_attr(r, ".//cbc:TotalInvoiceAmount", "currencyID", "USD", P_NS)),
        ("2687", lambda r: _set_text(r, ".//sac:SUNATTotalCashed", "0.00", P_NS)),
        ("2690", lambda r: _set_attr(r, ".//sac:SUNATTotalCashed", "currencyID", "USD", P_NS)),
        ("3303", lambda r: _add_child(r, _CBC, "PayableRoundingAmount", "1.01", {"currencyID": "PEN"})),
        ("3304", lambda r: _add_child(r, _CBC, "PayableRoundingAmount", "0.10", {"currencyID": "USD"})),
        ("3323", lambda r: _set_exceptional_and_duplicate_ref(r)),
        ("2691", lambda r: _remove_attr(r, ".//sac:SUNATPerceptionDocumentReference/cbc:ID", "schemeID", P_NS)),
        ("2692", lambda r: _set_attr(r, ".//sac:SUNATPerceptionDocumentReference/cbc:ID", "schemeID", "99", P_NS)),
        ("3324", lambda r: _set_exceptional_and_ref_type(r, "03")),
        ("2693", lambda r: _set_text(r, ".//sac:SUNATPerceptionDocumentReference/cbc:ID", "", P_NS)),
        ("2694", lambda r: _set_ref_type_and_id(r, "12", "x" * 21)),
        ("2696", lambda r: _set_text(r, ".//sac:SUNATPerceptionDocumentReference/cbc:TotalInvoiceAmount", "0.00", P_NS)),
        ("2702", lambda r: _remove_node(r, ".//sac:SUNATPerceptionDocumentReference/cac:Payment/cbc:PaidDate", P_NS)),
        ("2659", lambda r: _set_text(r, "(//sac:SUNATPerceptionDocumentReference/cac:Payment/cbc:PaidDate)[2]", "2024-02-15", P_NS)),
        ("2612", lambda r: _set_text(r, ".//sac:SUNATPerceptionDocumentReference/cac:Payment/cbc:PaidDate", "2024-02-01", P_NS)),
        ("2697", lambda r: _remove_node(r, ".//sac:SUNATPerceptionDocumentReference/cac:Payment/cbc:ID", P_NS)),
        ("2698", lambda r: _set_text(r, ".//sac:SUNATPerceptionDocumentReference/cac:Payment/cbc:ID", "abc", P_NS)),
        ("2626", lambda r: _duplicate_ref_for_uniqueness(r)),
        ("2699", lambda r: _remove_node(r, ".//sac:SUNATPerceptionDocumentReference/cac:Payment/cbc:PaidAmount", P_NS)),
        ("2700", lambda r: _set_text(r, ".//sac:SUNATPerceptionDocumentReference/cac:Payment/cbc:PaidAmount", "0.00", P_NS)),
        ("2607", lambda r: _set_attr(r, ".//sac:SUNATPerceptionDocumentReference/cac:Payment/cbc:PaidAmount", "currencyID", "USD", P_NS)),
        ("2705", lambda r: _set_text(r, ".//sac:SUNATPerceptionDocumentReference/sac:SUNATPerceptionInformation/sac:SUNATPerceptionAmount", "0.00", P_NS)),
        ("2608", lambda r: _set_text(r, ".//sac:SUNATPerceptionDocumentReference/cbc:TotalInvoiceAmount", "50.00", P_NS)),
        ("2707", lambda r: _set_attr(r, ".//sac:SUNATPerceptionDocumentReference/sac:SUNATPerceptionInformation/sac:SUNATPerceptionAmount", "currencyID", "USD", P_NS)),
        ("2711", lambda r: _set_text(r, ".//sac:SUNATPerceptionDocumentReference/sac:SUNATPerceptionInformation/sac:SUNATNetTotalCashed", "0.00", P_NS)),
        ("2713", lambda r: _set_attr(r, ".//sac:SUNATPerceptionDocumentReference/sac:SUNATPerceptionInformation/sac:SUNATNetTotalCashed", "currencyID", "USD", P_NS)),
        ("2719", lambda r: _set_ref_currency_and_remove_exchange(r, "USD")),
        ("2749", lambda r: _add_exchange_rate(r, "XYZ", "3.5", "2024-01-01")),
        ("2715", lambda r: _add_exchange_rate(r, "USD", "3.5", "2024-01-01")),
        ("2721", lambda r: _add_exchange_rate_no_calc(r)),
        ("2716", lambda r: _add_exchange_rate(r, "PEN", "0.000000", "2024-01-01")),
        ("2722", lambda r: _add_exchange_rate_no_date(r)),
        ("2667", lambda r: _set_text(r, ".//cbc:TotalInvoiceAmount", "40.00", P_NS)),
        ("2668", lambda r: _set_text(r, ".//sac:SUNATTotalCashed", "200.00", P_NS)),
    ])
    def test_perception_rule(self, xml, code, mutator):
        root = etree.fromstring(xml.encode("utf-8"))
        mutator(root)
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = SunatValidator().validate_perception(bad_xml)
        codes = [e.code for e in errors]
        assert code in codes, f"Expected error {code} in {codes}"

    def test_perception_valid(self):
        errors = SunatValidator().validate_perception(_valid_perception())
        assert errors == []


def _set_exceptional_and_duplicate_ref(root: etree._Element) -> None:
    _add_child(root, _SAC, "ExceptionalIndicator", "01")
    refs = root.xpath(".//sac:SUNATPerceptionDocumentReference", namespaces=P_NS)
    if len(refs) == 1:
        refs.append(deepcopy(refs[0]))


def _set_exceptional_and_ref_type(root: etree._Element, ref_type: str) -> None:
    _add_child(root, _SAC, "ExceptionalIndicator", "01")
    refs = root.xpath(".//sac:SUNATPerceptionDocumentReference/cbc:ID", namespaces=P_NS)
    refs[0].set("schemeID", ref_type)


def _set_ref_type_and_id(root: etree._Element, ref_type: str, ref_id: str) -> None:
    ref = root.xpath(".//sac:SUNATPerceptionDocumentReference/cbc:ID", namespaces=P_NS)[0]
    ref.set("schemeID", ref_type)
    ref.text = ref_id


def _set_ref_type_and_id_with_exchange(root: etree._Element, ref_type: str, ref_id: str) -> None:
    _set_ref_type_and_id(root, ref_type, ref_id)
    _add_exchange_rate(root, "PEN", "3.5", "2024-01-01")


def _duplicate_ref_for_uniqueness(root: etree._Element) -> None:
    refs = root.xpath(".//sac:SUNATPerceptionDocumentReference", namespaces=P_NS)
    if refs:
        root.append(deepcopy(refs[0]))


def _set_ref_currency_and_remove_exchange(root: etree._Element, currency: str) -> None:
    ref = root.xpath(".//sac:SUNATPerceptionDocumentReference", namespaces=P_NS)[0]
    total = ref.xpath("cbc:TotalInvoiceAmount", namespaces=P_NS)[0]
    total.set("currencyID", currency)
    paid = ref.xpath("cac:Payment/cbc:PaidAmount", namespaces=P_NS)[0]
    paid.set("currencyID", currency)
    for ex in ref.xpath("cac:ExchangeRate", namespaces=P_NS):
        ref.remove(ex)


def _add_exchange_rate(root: etree._Element, target: str, calc: str, dt: str) -> None:
    ref = root.xpath(".//sac:SUNATPerceptionDocumentReference", namespaces=P_NS)[0]
    ref.xpath("cbc:TotalInvoiceAmount", namespaces=P_NS)[0].set("currencyID", "USD")
    ref.xpath("cac:Payment/cbc:PaidAmount", namespaces=P_NS)[0].set("currencyID", "USD")
    info = ref.xpath("sac:SUNATPerceptionInformation", namespaces=P_NS)[0]
    ex = _add_child(info, _CAC, "ExchangeRate")
    _add_child(ex, _CBC, "TargetCurrencyCode", target)
    _add_child(ex, _CBC, "CalculationRate", calc)
    _add_child(ex, _CBC, "Date", dt)


def _add_exchange_rate_no_calc(root: etree._Element) -> None:
    ref = root.xpath(".//sac:SUNATPerceptionDocumentReference", namespaces=P_NS)[0]
    ref.xpath("cbc:TotalInvoiceAmount", namespaces=P_NS)[0].set("currencyID", "USD")
    ref.xpath("cac:Payment/cbc:PaidAmount", namespaces=P_NS)[0].set("currencyID", "USD")
    info = ref.xpath("sac:SUNATPerceptionInformation", namespaces=P_NS)[0]
    ex = _add_child(info, _CAC, "ExchangeRate")
    _add_child(ex, _CBC, "TargetCurrencyCode", "PEN")
    _add_child(ex, _CBC, "Date", "2024-01-01")


def _add_exchange_rate_no_date(root: etree._Element) -> None:
    ref = root.xpath(".//sac:SUNATPerceptionDocumentReference", namespaces=P_NS)[0]
    ref.xpath("cbc:TotalInvoiceAmount", namespaces=P_NS)[0].set("currencyID", "USD")
    ref.xpath("cac:Payment/cbc:PaidAmount", namespaces=P_NS)[0].set("currencyID", "USD")
    info = ref.xpath("sac:SUNATPerceptionInformation", namespaces=P_NS)[0]
    ex = _add_child(info, _CAC, "ExchangeRate")
    _add_child(ex, _CBC, "TargetCurrencyCode", "PEN")
    _add_child(ex, _CBC, "CalculationRate", "3.5")


def _add_agent_country(root: etree._Element, country: str) -> None:
    agent = root.xpath(".//cac:AgentParty", namespaces=P_NS)[0]
    pa = _add_child(agent, _CAC, "PostalAddress")
    c = _add_child(pa, _CAC, "Country")
    _add_child(c, _CBC, "IdentificationCode", country)


# ------------------------------------------------------------------
# Tests Retention
# ------------------------------------------------------------------
class TestValidatorRetention:
    @pytest.fixture
    def xml(self):
        return _valid_retention()

    @pytest.mark.parametrize("code,mutator", [
        ("2723", lambda r: _remove_node(r, ".//cac:ReceiverParty/cac:PartyIdentification/cbc:ID", R_NS)),
        ("2724", lambda r: _set_text(r, ".//cac:ReceiverParty/cac:PartyIdentification/cbc:ID", "1234567890", R_NS)),
        ("2620", lambda r: _set_text(r, ".//cac:ReceiverParty/cac:PartyIdentification/cbc:ID", "20100066603", R_NS)),
        ("2628", lambda r: _set_text(r, ".//cbc:TotalInvoiceAmount", "40.00", R_NS)),
        ("2728", lambda r: _set_attr(r, ".//cbc:TotalInvoiceAmount", "currencyID", "USD", R_NS)),
        ("2730", lambda r: _set_text(r, ".//sac:SUNATTotalPaid", "0.00", R_NS)),
        ("2732", lambda r: _set_attr(r, ".//sac:SUNATTotalPaid", "currencyID", "USD", R_NS)),
        ("2985", lambda r: (_set_text(r, ".//sac:SUNATRetentionSystemCode", "02", R_NS), _set_text(r, ".//cbc:IssueDate", "2024-01-01", R_NS))[0]),
        ("2737", lambda r: _remove_node(r, ".//sac:SUNATRetentionDocumentReference/cac:Payment/cbc:PaidDate", R_NS)),
        ("2661", lambda r: _set_text(r, "(//sac:SUNATRetentionDocumentReference/cac:Payment/cbc:PaidDate)[2]", "2024-02-15", R_NS)),
        ("2625", lambda r: _set_text(r, ".//sac:SUNATRetentionDocumentReference/cac:Payment/cbc:PaidDate", "2024-02-01", R_NS)),
        ("2985", lambda r: _set_retention_regime_and_issue_date(r, "02", "2024-01-01")),
        ("2734", lambda r: _set_text(r, ".//sac:SUNATRetentionDocumentReference/cac:Payment/cbc:ID", "abc", R_NS)),
        ("2735", lambda r: _remove_node(r, ".//sac:SUNATRetentionDocumentReference/cac:Payment/cbc:PaidAmount", R_NS)),
        ("2736", lambda r: _set_text(r, ".//sac:SUNATRetentionDocumentReference/cac:Payment/cbc:PaidAmount", "0.00", R_NS)),
        ("2622", lambda r: _set_attr(r, ".//sac:SUNATRetentionDocumentReference/cac:Payment/cbc:PaidAmount", "currencyID", "USD", R_NS)),
        ("2740", lambda r: _set_text(r, ".//sac:SUNATRetentionDocumentReference/sac:SUNATRetentionInformation/sac:SUNATRetentionAmount", "0.00", R_NS)),
        ("2623", lambda r: _set_text(r, ".//sac:SUNATRetentionDocumentReference/cbc:TotalInvoiceAmount", "50.00", R_NS)),
        ("2742", lambda r: _set_attr(r, ".//sac:SUNATRetentionDocumentReference/sac:SUNATRetentionInformation/sac:SUNATRetentionAmount", "currencyID", "USD", R_NS)),
        ("2746", lambda r: _set_text(r, ".//sac:SUNATRetentionDocumentReference/sac:SUNATRetentionInformation/sac:SUNATNetTotalPaid", "0.00", R_NS)),
        ("2748", lambda r: _set_attr(r, ".//sac:SUNATRetentionDocumentReference/sac:SUNATRetentionInformation/sac:SUNATNetTotalPaid", "currencyID", "USD", R_NS)),
        ("2629", lambda r: _set_text(r, ".//sac:SUNATTotalPaid", "200.00", R_NS)),
    ])
    def test_retention_rule(self, xml, code, mutator):
        root = etree.fromstring(xml.encode("utf-8"))
        mutator(root)
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = SunatValidator().validate_retention(bad_xml)
        codes = [e.code for e in errors]
        assert code in codes, f"Expected error {code} in {codes}"

    def test_retention_valid(self):
        errors = SunatValidator().validate_retention(_valid_retention())
        assert errors == []


def _set_retention_regime_and_issue_date(root: etree._Element, regime: str, issue_date: str) -> None:
    _set_text(root, ".//sac:SUNATRetentionSystemCode", regime, R_NS)
    _set_text(root, ".//cbc:IssueDate", issue_date, R_NS)


class TestValidatorSummaryDocuments:
    """Tests para reglas SUNAT de SummaryDocuments (Resumen Diario).

    Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
    https://cpe.sunat.gob.pe/guias-y-manuales
    """

    NS = {
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
    }

    def _valid_xml(self) -> str:
        return '''<?xml version="1.0" encoding="UTF-8"?>
<SummaryDocuments xmlns="urn:sunat:names:specification:ubl:peru:schema:xsd:SummaryDocuments-1"
                  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
                  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
                  xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1">
  <cbc:UBLVersionID>2.0</cbc:UBLVersionID>
  <cbc:CustomizationID>1.1</cbc:CustomizationID>
  <cbc:ID>RC-20240101-1</cbc:ID>
  <cbc:ReferenceDate>2024-01-01</cbc:ReferenceDate>
  <cbc:IssueDate>2024-01-01</cbc:IssueDate>
  <cac:AccountingSupplierParty>
    <cbc:CustomerAssignedAccountID>20100066603</cbc:CustomerAssignedAccountID>
    <cbc:AdditionalAccountID>6</cbc:AdditionalAccountID>
    <cac:Party>
      <cac:PartyLegalEntity>
        <cbc:RegistrationName>Test SA</cbc:RegistrationName>
      </cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <sac:SummaryDocumentsLine>
    <cbc:LineID>1</cbc:LineID>
    <cbc:DocumentTypeCode>03</cbc:DocumentTypeCode>
    <cbc:ID>B001-1</cbc:ID>
    <cac:AccountingCustomerParty>
      <cbc:CustomerAssignedAccountID>12345678</cbc:CustomerAssignedAccountID>
      <cbc:AdditionalAccountID>1</cbc:AdditionalAccountID>
      <cac:Party>
        <cac:PartyLegalEntity>
          <cbc:RegistrationName>Carlos Feria</cbc:RegistrationName>
        </cac:PartyLegalEntity>
      </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:Status>
      <cbc:ConditionCode>1</cbc:ConditionCode>
    </cac:Status>
    <sac:TotalAmount currencyID="PEN">1000.00</sac:TotalAmount>
    <sac:BillingPayment>
      <cbc:PaidAmount currencyID="PEN">847.46</cbc:PaidAmount>
      <cbc:InstructionID>01</cbc:InstructionID>
    </sac:BillingPayment>
    <cac:TaxTotal>
      <cbc:TaxAmount currencyID="PEN">152.54</cbc:TaxAmount>
      <cac:TaxSubtotal>
        <cbc:TaxAmount currencyID="PEN">152.54</cbc:TaxAmount>
        <cac:TaxCategory>
          <cbc:Percent>18.00</cbc:Percent>
          <cac:TaxScheme>
            <cbc:ID>1000</cbc:ID>
            <cbc:Name>IGV</cbc:Name>
            <cbc:TaxTypeCode>VAT</cbc:TaxTypeCode>
          </cac:TaxScheme>
        </cac:TaxCategory>
      </cac:TaxSubtotal>
    </cac:TaxTotal>
  </sac:SummaryDocumentsLine>
</SummaryDocuments>'''

    def _with_second_line(self, base_xml: str | None = None, op: str = "1", line_id: str = "B001-2") -> str:
        base = base_xml or self._valid_xml()
        second = (
            base
            .replace("<cbc:LineID>1</cbc:LineID>", "<cbc:LineID>2</cbc:LineID>", 1)
            .replace("<cbc:ID>B001-1</cbc:ID>", f"<cbc:ID>{line_id}</cbc:ID>", 1)
        )
        second = re.sub(r"<cbc:ConditionCode>.*?</cbc:ConditionCode>", f"<cbc:ConditionCode>{op}</cbc:ConditionCode>", second, count=1, flags=re.DOTALL)
        line_start = second.index("<sac:SummaryDocumentsLine>")
        line_end = second.index("</sac:SummaryDocumentsLine>") + len("</sac:SummaryDocumentsLine>")
        line_xml = second[line_start:line_end]
        base_without_close = base.replace("</SummaryDocuments>", "")
        return base_without_close + line_xml + "</SummaryDocuments>"

    def test_summary_documents_valid(self):
        errors = SunatValidator().validate_summary_documents(self._valid_xml())
        assert errors == []

    @pytest.mark.parametrize("code,mutator", [
        ("2074", lambda xml: xml.replace("<cbc:UBLVersionID>2.0</cbc:UBLVersionID>", "<cbc:UBLVersionID>2.1</cbc:UBLVersionID>")),
        ("2075", lambda xml: xml.replace("<cbc:UBLVersionID>2.0</cbc:UBLVersionID>", "<cbc:UBLVersionID></cbc:UBLVersionID>")),
        ("2072", lambda xml: xml.replace("<cbc:CustomizationID>1.1</cbc:CustomizationID>", "<cbc:CustomizationID>2.0</cbc:CustomizationID>")),
        ("2220", lambda xml: xml.replace("<cbc:ID>RC-20240101-1</cbc:ID>", "<cbc:ID>BAD</cbc:ID>")),
        ("2346", lambda xml: xml.replace("<cbc:ID>RC-20240101-1</cbc:ID>", "<cbc:ID>RC-20240102-1</cbc:ID>")),
        ("2236", lambda xml: xml.replace("<cbc:IssueDate>2024-01-01</cbc:IssueDate>", f"<cbc:IssueDate>{(date.today() + timedelta(days=1)).isoformat()}</cbc:IssueDate>")),
        ("2671", lambda xml: xml.replace("<cbc:ReferenceDate>2024-01-01</cbc:ReferenceDate>", "<cbc:ReferenceDate>2024-01-02</cbc:ReferenceDate>")),
        ("1034", lambda xml: xml.replace("<cbc:CustomerAssignedAccountID>20100066603</cbc:CustomerAssignedAccountID>", "<cbc:CustomerAssignedAccountID>2010006660</cbc:CustomerAssignedAccountID>", 1)),
        ("2219", lambda xml: xml.replace("<cbc:AdditionalAccountID>6</cbc:AdditionalAccountID>", "", 1)),
        ("2218", lambda xml: xml.replace("<cbc:AdditionalAccountID>6</cbc:AdditionalAccountID>", "<cbc:AdditionalAccountID>1</cbc:AdditionalAccountID>", 1)),
        ("2229", lambda xml: xml.replace("<cbc:RegistrationName>Test SA</cbc:RegistrationName>", "<cbc:RegistrationName></cbc:RegistrationName>")),
        ("2228", lambda xml: xml.replace("<cbc:RegistrationName>Test SA</cbc:RegistrationName>", "<cbc:RegistrationName>AB</cbc:RegistrationName>")),
        ("2238", lambda xml: xml.replace("<cbc:LineID>1</cbc:LineID>", "<cbc:LineID>abc</cbc:LineID>", 1)),
        ("2239", lambda xml: xml.replace("<cbc:LineID>1</cbc:LineID>", "<cbc:LineID>0</cbc:LineID>", 1)),
        ("2512", lambda xml: xml.replace("<cbc:ID>B001-1</cbc:ID>", "", 1)),
        ("2513", lambda xml: xml.replace("<cbc:ID>B001-1</cbc:ID>", "<cbc:ID>F001-1</cbc:ID>", 1)),
        ("2242", lambda xml: xml.replace("<cbc:DocumentTypeCode>03</cbc:DocumentTypeCode>", "<cbc:DocumentTypeCode></cbc:DocumentTypeCode>", 1)),
        ("2241", lambda xml: xml.replace("<cbc:DocumentTypeCode>03</cbc:DocumentTypeCode>", "<cbc:DocumentTypeCode>01</cbc:DocumentTypeCode>", 1)),
        ("2522", lambda xml: xml.replace("<cbc:ConditionCode>1</cbc:ConditionCode>", "", 1)),
        ("2251", lambda xml: xml.replace("<sac:TotalAmount currencyID=\"PEN\">1000.00</sac:TotalAmount>", "<sac:TotalAmount currencyID=\"PEN\">-10.00</sac:TotalAmount>", 1)),
        ("2071", lambda xml: xml.replace('currencyID="PEN">152.54</cbc:TaxAmount>', 'currencyID="USD">152.54</cbc:TaxAmount>', 1)),
        ("2255", lambda xml: xml.replace("<cbc:PaidAmount currencyID=\"PEN\">847.46</cbc:PaidAmount>", "", 1)),
        ("2254", lambda xml: xml.replace("<cbc:PaidAmount currencyID=\"PEN\">847.46</cbc:PaidAmount>", "<cbc:PaidAmount currencyID=\"PEN\">0.00</cbc:PaidAmount>", 1)),
        ("2257", lambda xml: xml.replace("<cbc:InstructionID>01</cbc:InstructionID>", "", 1)),
        ("2357", lambda xml: xml.replace(
            "</sac:BillingPayment>",
            "</sac:BillingPayment><sac:BillingPayment><cbc:PaidAmount currencyID=\"PEN\">100.00</cbc:PaidAmount><cbc:InstructionID>01</cbc:InstructionID></sac:BillingPayment>",
            1,
        )),
        ("2263", lambda xml: xml.replace(
            "</sac:BillingPayment>",
            "</sac:BillingPayment><cac:AllowanceCharge><cbc:ChargeIndicator>false</cbc:ChargeIndicator><cbc:Amount currencyID=\"PEN\">10.00</cbc:Amount></cac:AllowanceCharge>",
            1,
        )),
        ("2411", lambda xml: xml.replace(
            "</sac:BillingPayment>",
            "</sac:BillingPayment><cac:AllowanceCharge><cbc:ChargeIndicator>true</cbc:ChargeIndicator><cbc:Amount currencyID=\"PEN\">10.00</cbc:Amount></cac:AllowanceCharge><cac:AllowanceCharge><cbc:ChargeIndicator>true</cbc:ChargeIndicator><cbc:Amount currencyID=\"PEN\">20.00</cbc:Amount></cac:AllowanceCharge>",
            1,
        )),
        ("2261", lambda xml: xml.replace(
            "</sac:BillingPayment>",
            "</sac:BillingPayment><cac:AllowanceCharge><cbc:ChargeIndicator>true</cbc:ChargeIndicator><cbc:Amount currencyID=\"PEN\">0.00</cbc:Amount></cac:AllowanceCharge>",
            1,
        )),
        ("2278", lambda xml: xml.replace("<cbc:ID>1000</cbc:ID>", "<cbc:ID>9999</cbc:ID>").replace("<cbc:Name>IGV</cbc:Name>", "<cbc:Name>OTROS</cbc:Name>")),
        ("2048", lambda xml: xml.replace("<cbc:TaxAmount currencyID=\"PEN\">152.54</cbc:TaxAmount>", "<cbc:TaxAmount currencyID=\"PEN\">0.00</cbc:TaxAmount>", 1)),
        ("2344", lambda xml: xml.replace(
            "      <cac:TaxSubtotal>\n        <cbc:TaxAmount currencyID=\"PEN\"\u003e152.54</cbc:TaxAmount>",
            "      <cac:TaxSubtotal>\n        <cbc:TaxAmount currencyID=\"PEN\"\u003e100.00</cbc:TaxAmount>",
            1,
        )),
        ("2269", lambda xml: xml.replace("<cbc:ID>1000</cbc:ID>", "", 1)),
        ("2355", lambda xml: xml.replace(
            "</cac:TaxSubtotal>",
            "</cac:TaxSubtotal><cac:TaxSubtotal><cbc:TaxAmount currencyID=\"PEN\">152.54</cbc:TaxAmount><cac:TaxCategory><cbc:Percent>18.00</cbc:Percent><cac:TaxScheme><cbc:ID>1000</cbc:ID><cbc:Name>IGV</cbc:Name><cbc:TaxTypeCode>VAT</cbc:TaxTypeCode></cac:TaxScheme></cac:TaxCategory></cac:TaxSubtotal>",
            1,
        )),
        ("2271", lambda xml: xml.replace("<cbc:Name>IGV</cbc:Name>", "", 1)),
        ("2276", lambda xml: xml.replace("<cbc:Name>IGV</cbc:Name>", "<cbc:Name>IVA</cbc:Name>", 1)),
        ("3051", lambda xml: xml.replace("<cbc:ID>1000</cbc:ID>", "<cbc:ID>1016</cbc:ID>", 1)),
        ("2275", lambda xml: xml.replace("<cbc:ID>1000</cbc:ID>", "<cbc:ID>2000</cbc:ID>", 1)),
        ("2992", lambda xml: xml.replace("<cbc:Percent>18.00</cbc:Percent>", "", 1)),
        ("3504", lambda xml: xml.replace("<cbc:Percent>18.00</cbc:Percent>", "<cbc:Percent>20.00</cbc:Percent>", 1)),
        ("3102", lambda xml: xml.replace("<cbc:Percent>18.00</cbc:Percent>", "<cbc:Percent>18.123456</cbc:Percent>", 1)),
        ("2514", lambda xml: re.sub(r"<cac:AccountingCustomerParty>.*?</cac:AccountingCustomerParty>", "", xml, count=1, flags=re.DOTALL)),
        ("2014", lambda xml: xml.replace("<cbc:CustomerAssignedAccountID>12345678</cbc:CustomerAssignedAccountID>", "", 1)),
        ("2017", lambda xml: xml.replace("<cbc:AdditionalAccountID>1</cbc:AdditionalAccountID>", "<cbc:AdditionalAccountID>6</cbc:AdditionalAccountID>", 1)),
        ("2015", lambda xml: xml.replace("<cbc:AdditionalAccountID>1</cbc:AdditionalAccountID>", "", 1)),
        ("2022", lambda xml: xml.replace("<cbc:RegistrationName>Carlos Feria</cbc:RegistrationName>", "<cbc:RegistrationName>AB</cbc:RegistrationName>", 1)),
        ("2582", lambda xml: xml.replace(
            "<cac:Status>",
            "<cac:BillingReference><cac:InvoiceDocumentReference><cbc:ID>B001-0</cbc:ID><cbc:DocumentTypeCode>03</cbc:DocumentTypeCode></cac:InvoiceDocumentReference></cac:BillingReference><cac:Status>",
            1,
        )),
        ("2524", lambda xml: (
            xml.replace("<cbc:DocumentTypeCode>03</cbc:DocumentTypeCode>", "<cbc:DocumentTypeCode>07</cbc:DocumentTypeCode>", 1)
            .replace("<cac:Status>", "<cac:BillingReference><cac:InvoiceDocumentReference><cbc:ID></cbc:ID></cac:InvoiceDocumentReference></cac:BillingReference><cac:Status>", 1)
        )),
        ("2920", lambda xml: (
            xml.replace("<cbc:DocumentTypeCode>03</cbc:DocumentTypeCode>", "<cbc:DocumentTypeCode>07</cbc:DocumentTypeCode>", 1)
            .replace("<cac:Status>", "<cac:BillingReference><cac:InvoiceDocumentReference><cbc:ID>X</cbc:ID><cbc:DocumentTypeCode>12</cbc:DocumentTypeCode></cac:InvoiceDocumentReference></cac:BillingReference><cac:Status>", 1)
        )),
        ("2583", lambda xml: (
            xml.replace("<cbc:DocumentTypeCode>03</cbc:DocumentTypeCode>", "<cbc:DocumentTypeCode>07</cbc:DocumentTypeCode>", 1)
            .replace("<cac:Status>", "<cac:BillingReference><cac:InvoiceDocumentReference><cbc:ID>B001-0</cbc:ID></cac:InvoiceDocumentReference></cac:BillingReference><cac:Status>", 1)
        )),
        ("2986", lambda xml: xml.replace("<cbc:ConditionCode>1</cbc:ConditionCode>", "<cbc:ConditionCode>2</cbc:ConditionCode>", 1).replace(
            "</sac:SummaryDocumentsLine>",
            "<sac:SUNATPerceptionSummaryDocumentReference><sac:SUNATPerceptionSystemCode>01</sac:SUNATPerceptionSystemCode><sac:SUNATPerceptionPercent>2.00</sac:SUNATPerceptionPercent><cbc:TotalInvoiceAmount currencyID=\"PEN\">2.00</cbc:TotalInvoiceAmount><sac:SUNATTotalCashed currencyID=\"PEN\">1002.00</sac:SUNATTotalCashed><cbc:TaxableAmount currencyID=\"PEN\">100.00</cbc:TaxableAmount></sac:SUNATPerceptionSummaryDocumentReference></sac:SummaryDocumentsLine>",
            1,
        )),
        ("2893", lambda xml: xml.replace(
            "</sac:SummaryDocumentsLine>",
            "<sac:SUNATPerceptionSummaryDocumentReference><sac:SUNATPerceptionSystemCode>01</sac:SUNATPerceptionSystemCode><sac:SUNATPerceptionPercent>2.00</sac:SUNATPerceptionPercent><cbc:TotalInvoiceAmount currencyID=\"PEN\">0.00</cbc:TotalInvoiceAmount><sac:SUNATTotalCashed currencyID=\"PEN\">1002.00</sac:SUNATTotalCashed><cbc:TaxableAmount currencyID=\"PEN\">100.00</cbc:TaxableAmount></sac:SUNATPerceptionSummaryDocumentReference></sac:SummaryDocumentsLine>",
            1,
        )),
        ("2608", lambda xml: xml.replace(
            "</sac:SummaryDocumentsLine>",
            "<sac:SUNATPerceptionSummaryDocumentReference><sac:SUNATPerceptionSystemCode>01</sac:SUNATPerceptionSystemCode><sac:SUNATPerceptionPercent>2.00</sac:SUNATPerceptionPercent><cbc:TotalInvoiceAmount currencyID=\"PEN\">999.00</cbc:TotalInvoiceAmount><sac:SUNATTotalCashed currencyID=\"PEN\">1000.00</sac:SUNATTotalCashed><cbc:TaxableAmount currencyID=\"PEN\">100.00</cbc:TaxableAmount></sac:SUNATPerceptionSummaryDocumentReference></sac:SummaryDocumentsLine>",
            1,
        )),
        ("2685", lambda xml: xml.replace(
            "</sac:SummaryDocumentsLine>",
            "<sac:SUNATPerceptionSummaryDocumentReference><sac:SUNATPerceptionSystemCode>01</sac:SUNATPerceptionSystemCode><sac:SUNATPerceptionPercent>2.00</sac:SUNATPerceptionPercent><cbc:TotalInvoiceAmount currencyID=\"USD\">2.00</cbc:TotalInvoiceAmount><sac:SUNATTotalCashed currencyID=\"PEN\">1002.00</sac:SUNATTotalCashed><cbc:TaxableAmount currencyID=\"PEN\">100.00</cbc:TaxableAmount></sac:SUNATPerceptionSummaryDocumentReference></sac:SummaryDocumentsLine>",
            1,
        )),
        ("2895", lambda xml: xml.replace(
            "</sac:SummaryDocumentsLine>",
            "<sac:SUNATPerceptionSummaryDocumentReference><sac:SUNATPerceptionSystemCode>01</sac:SUNATPerceptionSystemCode><sac:SUNATPerceptionPercent>2.00</sac:SUNATPerceptionPercent><cbc:TotalInvoiceAmount currencyID=\"PEN\">2.00</cbc:TotalInvoiceAmount><sac:SUNATTotalCashed currencyID=\"PEN\">0.00</sac:SUNATTotalCashed><cbc:TaxableAmount currencyID=\"PEN\">100.00</cbc:TaxableAmount></sac:SUNATPerceptionSummaryDocumentReference></sac:SummaryDocumentsLine>",
            1,
        )),
        ("2690", lambda xml: xml.replace(
            "</sac:SummaryDocumentsLine>",
            "<sac:SUNATPerceptionSummaryDocumentReference><sac:SUNATPerceptionSystemCode>01</sac:SUNATPerceptionSystemCode><sac:SUNATPerceptionPercent>2.00</sac:SUNATPerceptionPercent><cbc:TotalInvoiceAmount currencyID=\"PEN\">2.00</cbc:TotalInvoiceAmount><sac:SUNATTotalCashed currencyID=\"USD\">1002.00</sac:SUNATTotalCashed><cbc:TaxableAmount currencyID=\"PEN\">100.00</cbc:TaxableAmount></sac:SUNATPerceptionSummaryDocumentReference></sac:SummaryDocumentsLine>",
            1,
        )),
        ("2897", lambda xml: xml.replace(
            "</sac:SummaryDocumentsLine>",
            "<sac:SUNATPerceptionSummaryDocumentReference><sac:SUNATPerceptionSystemCode>01</sac:SUNATPerceptionSystemCode><sac:SUNATPerceptionPercent>2.00</sac:SUNATPerceptionPercent><cbc:TotalInvoiceAmount currencyID=\"PEN\">2.00</cbc:TotalInvoiceAmount><sac:SUNATTotalCashed currencyID=\"PEN\">1002.00</sac:SUNATTotalCashed><cbc:TaxableAmount currencyID=\"PEN\">0.00</cbc:TaxableAmount></sac:SUNATPerceptionSummaryDocumentReference></sac:SummaryDocumentsLine>",
            1,
        )),
    ])
    def test_summary_documents_rule(self, code, mutator):
        xml = self._valid_xml()
        xml = mutator(xml)
        errors = SunatValidator().validate_summary_documents(xml)
        codes = [e.code for e in errors]
        assert code in codes, f"Expected error {code} in {codes}"

    @pytest.mark.parametrize("code,base_xml", [
        ("2752", lambda self: self._with_second_line()),
        ("3094", lambda self: self._with_second_line(line_id="B001-1", op="1")),
        ("3095", lambda self: self._with_second_line(line_id="B001-1", op="2")),
        ("3096", lambda self: self._with_second_line(
            base_xml=self._valid_xml().replace("<cbc:ConditionCode>1</cbc:ConditionCode>", "<cbc:ConditionCode>2</cbc:ConditionCode>", 1),
            line_id="B001-1",
            op="3",
        )),
    ])
    def test_summary_documents_multi_line_rule(self, code, base_xml):
        xml = base_xml(self)
        if code == "2752":
            xml = xml.replace("<cbc:LineID>2</cbc:LineID>", "<cbc:LineID>1</cbc:LineID>", 1)
        errors = SunatValidator().validate_summary_documents(xml)
        codes = [e.code for e in errors]
        assert code in codes, f"Expected error {code} in {codes}"


# ------------------------------------------------------------------
# CreditNote / DebitNote helpers
# ------------------------------------------------------------------

_CN_NS = {
    "": "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}

_DN_NS = {
    "": "urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}


def _valid_credit_note_xml() -> str:
    doc = CreditNote(
        serie="B001", numero=1,
        comprobanteAfectadoSerieNumero="B001-1",
        sustentoDescripcion="Error en precio",
        proveedor=Proveedor(ruc="20100066603", razonSocial="Test SA"),
        cliente=Cliente(nombre="Carlos", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
        detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100"))],
        fechaEmision=date(2024, 1, 1),
    )
    ContentEnricher().enrich(doc)
    xml = render_credit_note(doc)
    root = etree.fromstring(xml.encode("utf-8"))
    ref_type = root.find("cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", namespaces=_CN_NS)
    if ref_type is not None:
        ref_type.text = "03"  # nota de crédito serie B modifica boleta
    return etree.tostring(root, encoding="unicode")


def _valid_debit_note_xml() -> str:
    doc = DebitNote(
        serie="B001", numero=1,
        comprobanteAfectadoSerieNumero="B001-1",
        sustentoDescripcion="Error en precio",
        proveedor=Proveedor(ruc="20100066603", razonSocial="Test SA"),
        cliente=Cliente(nombre="Carlos", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
        detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100"))],
        fechaEmision=date(2024, 1, 1),
    )
    ContentEnricher().enrich(doc)
    xml = render_debit_note(doc)
    root = etree.fromstring(xml.encode("utf-8"))
    ref_type = root.find("cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", namespaces=_DN_NS)
    if ref_type is not None:
        ref_type.text = "03"
    return etree.tostring(root, encoding="unicode")


def _cn_remove(root: etree._Element, xpath: str) -> None:
    elem = root.find(xpath, namespaces=_CN_NS)
    if elem is not None:
        elem.getparent().remove(elem)


def _cn_set_text(root: etree._Element, xpath: str, text: str) -> None:
    elem = root.find(xpath, namespaces=_CN_NS)
    if elem is not None:
        elem.text = text


def _cn_set_attr(root: etree._Element, xpath: str, attr: str, value: str) -> None:
    elem = root.find(xpath, namespaces=_CN_NS)
    if elem is not None:
        elem.set(attr, value)


def _cn_remove_attr(root: etree._Element, xpath: str, attr: str) -> None:
    elem = root.find(xpath, namespaces=_CN_NS)
    if elem is not None and attr in elem.attrib:
        del elem.attrib[attr]


def _cn_duplicate_billing_reference(root: etree._Element) -> None:
    br = root.find("cac:BillingReference", namespaces=_CN_NS)
    if br is not None:
        root.insert(list(root).index(br) + 1, deepcopy(br))


def _cn_add_document_reference(root: etree._Element, type_code: str, id_text: str) -> etree._Element:
    ns_cac = "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}"
    ns_cbc = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"
    adr = etree.Element(ns_cac + "AdditionalDocumentReference")
    etree.SubElement(adr, ns_cbc + "ID").text = id_text
    etree.SubElement(adr, ns_cbc + "DocumentTypeCode").text = type_code
    return adr


def _cn_add_tax_subtotal(root: etree._Element, tax_code: str) -> None:
    line = root.find("cac:CreditNoteLine", namespaces=_CN_NS)
    tt = line.find("cac:TaxTotal", namespaces=_CN_NS)
    ts = tt.find("cac:TaxSubtotal", namespaces=_CN_NS)
    ts2 = deepcopy(ts)
    _cn_set_text(ts2, "cac:TaxCategory/cac:TaxScheme/cbc:ID", tax_code)
    _cn_set_text(ts2, "cac:TaxCategory/cac:TaxScheme/cbc:Name", "XXX")
    _cn_set_text(ts2, "cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode", "XXX")
    _cn_set_text(ts2, "cbc:TaxAmount", "0.00")
    _cn_set_text(ts2, "cbc:TaxableAmount", "0.00")
    tt.append(ts2)


def _cn_add_percent_to_line(root: etree._Element, percent: str) -> None:
    ns_cbc = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"
    line = root.find("cac:CreditNoteLine", namespaces=_CN_NS)
    tc = line.find("cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory", namespaces=_CN_NS)
    etree.SubElement(tc, ns_cbc + "Percent").text = percent


def _cn_add_payment_terms(root: etree._Element, means_id: str) -> None:
    ns_cac = "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}"
    ns_cbc = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"
    pt = etree.SubElement(root, ns_cac + "PaymentTerms")
    etree.SubElement(pt, ns_cbc + "ID").text = "FormaPago"
    etree.SubElement(pt, ns_cbc + "PaymentMeansID").text = means_id


def _dn_remove(root: etree._Element, xpath: str) -> None:
    elem = root.find(xpath, namespaces=_DN_NS)
    if elem is not None:
        elem.getparent().remove(elem)


def _dn_set_text(root: etree._Element, xpath: str, text: str) -> None:
    elem = root.find(xpath, namespaces=_DN_NS)
    if elem is not None:
        elem.text = text


def _dn_set_attr(root: etree._Element, xpath: str, attr: str, value: str) -> None:
    elem = root.find(xpath, namespaces=_DN_NS)
    if elem is not None:
        elem.set(attr, value)


def _dn_remove_attr(root: etree._Element, xpath: str, attr: str) -> None:
    elem = root.find(xpath, namespaces=_DN_NS)
    if elem is not None and attr in elem.attrib:
        del elem.attrib[attr]


def _dn_add_tax_subtotal(root: etree._Element, tax_code: str, amount: str = "1.00") -> None:
    line = root.find("cac:DebitNoteLine", namespaces=_DN_NS)
    tt = line.find("cac:TaxTotal", namespaces=_DN_NS)
    ts = tt.find("cac:TaxSubtotal", namespaces=_DN_NS)
    ts2 = deepcopy(ts)
    _dn_set_text(ts2, "cac:TaxCategory/cac:TaxScheme/cbc:ID", tax_code)
    _dn_set_text(ts2, "cac:TaxCategory/cac:TaxScheme/cbc:Name", "XXX")
    _dn_set_text(ts2, "cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode", "XXX")
    _dn_set_text(ts2, "cbc:TaxAmount", amount)
    _dn_set_text(ts2, "cbc:TaxableAmount", amount)
    tt.append(ts2)


def _dn_add_percent_to_line(root: etree._Element, percent: str) -> None:
    ns_cbc = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"
    line = root.find("cac:DebitNoteLine", namespaces=_DN_NS)
    tc = line.find("cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory", namespaces=_DN_NS)
    etree.SubElement(tc, ns_cbc + "Percent").text = percent


def _dn_add_payment_terms(root: etree._Element, id_text: str) -> None:
    ns_cac = "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}"
    ns_cbc = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"
    pt = etree.SubElement(root, ns_cac + "PaymentTerms")
    etree.SubElement(pt, ns_cbc + "ID").text = id_text


def _dn_add_payment_means(root: etree._Element, id_text: str) -> None:
    ns_cac = "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}"
    ns_cbc = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"
    pm = etree.SubElement(root, ns_cac + "PaymentMeans")
    etree.SubElement(pm, ns_cbc + "ID").text = id_text


class TestValidatorCreditNote:
    """Tests para reglas SUNAT de CreditNote (Nota de Crédito) - Fase C.

    Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
    https://cpe.sunat.gob.pe/guias-y-manuales
    """

    def test_credit_note_valid(self):
        errors = SunatValidator().validate_credit_note(_valid_credit_note_xml())
        assert errors == []

    @pytest.mark.parametrize("code,mutator", [
        ("2128", lambda r: _cn_remove(r, "cac:DiscrepancyResponse/cbc:ResponseCode")),
        ("3203", lambda r: (
            dr := r.find("cac:DiscrepancyResponse", namespaces=_CN_NS),
            r.insert(list(r).index(dr) + 1, deepcopy(dr)),
        )[0]),
        ("2136", lambda r: _cn_remove(r, "cac:DiscrepancyResponse/cbc:Description")),
        ("2135", lambda r: _cn_set_text(r, "cac:DiscrepancyResponse/cbc:Description", "x" * 501)),
        ("3029", lambda r: _cn_remove_attr(r, "cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID", "schemeID")),
        ("2511", lambda r: _cn_set_attr(r, "cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID", "schemeID", "1")),
        ("2679", lambda r: _cn_remove(r, "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID")),
        ("2524", lambda r: _cn_remove(r, "cac:BillingReference")),
        ("3261", lambda r: _cn_duplicate_billing_reference(r)),
        ("3194", lambda r: (
            _cn_set_text(r, "cac:DiscrepancyResponse/cbc:ResponseCode", "11"),
            _cn_duplicate_billing_reference(r),
        )),
        ("2117", lambda r: (
            _cn_set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01"),
            _cn_set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID", "B001-1"),
        )),
        ("2116", lambda r: _cn_set_text(r, "cbc:ID", "F001-1")),
        ("2399", lambda r: _cn_set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01")),
        ("2594", lambda r: (
            _cn_set_text(r, "cbc:ID", "0001-1"),
            _cn_set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "07"),
        )),
        ("3259", lambda r: (
            _cn_set_text(r, "cac:DiscrepancyResponse/cbc:ResponseCode", "13"),
            _cn_set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "03"),
        )),
        ("2884", lambda r: (
            br2 := deepcopy(r.find("cac:BillingReference", namespaces=_CN_NS)),
            _cn_set_text(br2, "cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "07"),
            r.insert(list(r).index(r.find("cac:BillingReference", namespaces=_CN_NS)) + 1, br2),
        )),
        ("2426", lambda r: (
            adr := _cn_add_document_reference(r, "01", "X"),
            r.insert(0, adr),
            r.insert(1, deepcopy(adr)),
        )),
        ("2636", lambda r: (
            _cn_set_text(r, "cac:DiscrepancyResponse/cbc:ResponseCode", "07"),
            r.insert(0, _cn_add_document_reference(r, "99", "X")),
        )),
        ("2635", lambda r: (
            _cn_set_text(r, "cac:DiscrepancyResponse/cbc:ResponseCode", "10"),
            r.insert(0, _cn_add_document_reference(r, "99", "X")),
            r.insert(1, _cn_add_document_reference(r, "99", "X")),
        )),
        ("2637", lambda r: (
            _cn_set_text(r, "cac:DiscrepancyResponse/cbc:ResponseCode", "10"),
            r.insert(0, _cn_add_document_reference(r, "01", "X")),
        )),
        ("2137", lambda r: _cn_set_text(r, "cac:CreditNoteLine/cbc:ID", "abc")),
        ("2138", lambda r: _cn_remove_attr(r, "cac:CreditNoteLine/cbc:CreditedQuantity", "unitCode")),
        ("2139", lambda r: _cn_set_text(r, "cac:CreditNoteLine/cbc:CreditedQuantity", "abc")),
        ("3230", lambda r: _cn_set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "17")),
        ("3221", lambda r: (
            _cn_set_text(r, "cac:DiscrepancyResponse/cbc:ResponseCode", "12"),
            _cn_add_tax_subtotal(r, "9995"),
        )),
        ("3315", lambda r: (
            _cn_set_text(r, "cac:DiscrepancyResponse/cbc:ResponseCode", "13"),
            _cn_add_percent_to_line(r, "18"),
        )),
        ("3257", lambda r: (
            _cn_set_text(r, "cac:DiscrepancyResponse/cbc:ResponseCode", "13"),
            [_cn_remove(r, "cac:PaymentTerms") for _ in r.findall("cac:PaymentTerms", namespaces=_CN_NS)],
        )),
        ("3320", lambda r: (
            _cn_set_text(r, "cac:DiscrepancyResponse/cbc:ResponseCode", "13"),
            _cn_add_payment_terms(r, "Credito"),
        )),
        ("3321", lambda r: _cn_add_payment_terms(r, "Cuota001")),
    ])
    def test_credit_note_rule(self, code, mutator):
        root = etree.fromstring(_valid_credit_note_xml().encode("utf-8"))
        mutator(root)
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = SunatValidator().validate_credit_note(bad_xml)
        codes = [e.code for e in errors]
        assert code in codes, f"Expected error {code} in {codes}"


class TestValidatorDebitNote:
    """Tests para reglas SUNAT de DebitNote (Nota de Débito) - Fase C.

    Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
    https://cpe.sunat.gob.pe/guias-y-manuales
    """

    def test_debit_note_valid(self):
        errors = SunatValidator().validate_debit_note(_valid_debit_note_xml())
        assert errors == []

    @pytest.mark.parametrize("code,mutator", [
        ("2205", lambda r: (
            _dn_set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01"),
            _dn_set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID", "B001-1"),
        )),
        ("2204", lambda r: _dn_set_text(r, "cbc:ID", "F001-1")),
        ("2400", lambda r: _dn_set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01")),
        ("2188", lambda r: _dn_remove_attr(r, "cac:DebitNoteLine/cbc:DebitedQuantity", "unitCode")),
        ("2643", lambda r: (
            _dn_set_text(r, "cac:DiscrepancyResponse/cbc:ResponseCode", "12"),
            _dn_set_text(r, "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "1016"),
            _dn_add_percent_to_line(r, "18"),
        )),
        ("3507", lambda r: _dn_set_text(r, "cac:DiscrepancyResponse/cbc:ResponseCode", "13")),
        ("3101", lambda r: _dn_add_tax_subtotal(r, "9995")),
        ("3313", lambda r: _dn_add_payment_terms(r, "Detraccion")),
        ("3314", lambda r: _dn_add_payment_means(r, "Detraccion")),
    ])
    def test_debit_note_rule(self, code, mutator):
        root = etree.fromstring(_valid_debit_note_xml().encode("utf-8"))
        mutator(root)
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = SunatValidator().validate_debit_note(bad_xml)
        codes = [e.code for e in errors]
        assert code in codes, f"Expected error {code} in {codes}"
