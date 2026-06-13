"""
Tests for SUNAT rule validation.

RS N° 300-2014/SUNAT - Reglas de validación actualizado al 24.04.2026.
"""
import pytest
from decimal import Decimal
from datetime import date
from lxml import etree

from openubl.models import Invoice, Proveedor, Cliente, DocumentoVentaDetalle
from openubl.enricher import ContentEnricher
from openubl.renderer import render_invoice
from openubl.validator import SunatValidator


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
        """
        RS N° 300-2014/SUNAT - XML debe cumplir esquema UBL 2.1.
        Valida contra UBL-Invoice-2.1.xsd.
        """
        import os
        xsd_path = os.path.join("sunat_schemas", "xsd_2.1", "2.1", "maindoc", "UBL-Invoice-2.1.xsd")
        if os.path.exists(xsd_path):
            errors = self.validator.validate_schema(self.xml, xsd_path)
            # SUNAT XSDs have complex dependencies; skip if dependency resolution fails
            if errors and "does not resolve" in errors[0]:
                pytest.skip("SUNAT XSD dependencies not fully resolved")
            assert errors == []
    def test_invoice_ubl_version_error_2074(self):
        """
        RS N° 043-2019/SUNAT amplía plazo UBL 2.1.
        ERROR 2074: UBLVersionID != '2.1' → rechazo inmediato.
        """
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cbc:UBLVersionID", namespaces=ns).text = "2.0"
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any("2074" in e for e in errors)

    def test_invoice_customization_id_error_2072(self):
        """
        RS N° 300-2014/SUNAT Anexo 1.
        ERROR 2072: CustomizationID != '2.0' → rechazo.
        """
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cbc:CustomizationID", namespaces=ns).text = "1.0"
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any("2072" in e for e in errors)

    def test_invoice_invalid_serie_error_1001(self):
        """
        RS N° 300-2014/SUNAT.
        ERROR 1001: Serie no cumple formato [A-Z0-9]{3}-[0-9]{1,8}.
        """
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cbc:ID", namespaces=ns).text = "INVALID"
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any("1001" in e for e in errors)

    def test_invoice_missing_currency_error_2070(self):
        """
        Catálogo N.° 02.
        ERROR 2070: DocumentCurrencyCode vacío → rechazo.
        """
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        elem = root.find("cbc:DocumentCurrencyCode", namespaces=ns)
        root.remove(elem)
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any("2070" in e for e in errors)

    def test_invoice_missing_supplier_name_error_1037(self):
        """
        RS N° 300-2014/SUNAT.
        ERROR 1037: RegistrationName vacío → rechazo.
        """
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName", namespaces=ns).text = ""
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any("1037" in e for e in errors)

    def test_invoice_tax_total_mismatch_error_3294(self):
        """
        ERROR 3294: TaxTotal global no cuadra con sumatoria de líneas ±1.
        SUNAT valida aritmética.
        """
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cac:TaxTotal/cbc:TaxAmount", namespaces=ns).text = "999.99"
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any("3294" in e for e in errors)

    def test_invoice_line_extension_amount_error_3278(self):
        """
        ERROR 3278: LineExtensionAmount global no cuadra con sumatoria de líneas ±1.
        """
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cac:LegalMonetaryTotal/cbc:LineExtensionAmount", namespaces=ns).text = "500.00"
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any("3278" in e for e in errors)

    def test_invoice_payable_amount_zero_error_2062(self):
        """
        ERROR 2062: PayableAmount ≤ 0 → rechazo.
        """
        root = etree.fromstring(self.xml.encode("utf-8"))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        root.find("cac:LegalMonetaryTotal/cbc:PayableAmount", namespaces=ns).text = "0.00"
        bad_xml = etree.tostring(root, encoding="unicode")
        errors = self.validator.validate_invoice(bad_xml)
        assert any("2062" in e for e in errors)


class TestValidatorSignedXml:
    def setup_method(self):
        self.validator = SunatValidator()

    def test_signed_xml_missing_signature_id_error_2085(self):
        """
        RS N° 300-2014/SUNAT Anexo 1 - Firma Digital.
        ERROR 2085: Falta ds:Signature/@Id.
        """
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

        signed = sign_ubl_xml(xml, cert_pem, key_pem)
        root = etree.fromstring(signed.encode("utf-8"))
        ns = {"ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
              "ds": "http://www.w3.org/2000/09/xmldsig#"}
        sig = root.xpath("//ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/ds:Signature", namespaces=ns)[0]
        del sig.attrib["Id"]
        bad_xml = etree.tostring(root, encoding="unicode")

        errors = self.validator.validate_signed_xml(bad_xml)
        assert any("2085" in e for e in errors)

    def test_signed_xml_missing_x509_error_2101(self):
        """
        ERROR 2101: Falta ds:X509Certificate → firma inválida.
        """
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

        signed = sign_ubl_xml(xml, cert_pem, key_pem)
        root = etree.fromstring(signed.encode("utf-8"))
        ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        x509 = root.xpath("//ds:X509Certificate", namespaces=ns)[0]
        x509.text = ""
        bad_xml = etree.tostring(root, encoding="unicode")

        errors = self.validator.validate_signed_xml(bad_xml)
        assert any("2101" in e for e in errors)

    def test_signed_xml_uses_sha256(self):
        """
        INDECOPI/IOFE y PCM Directiva 002-2024 exigen SHA-256.
        """
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

        signed = sign_ubl_xml(xml, cert_pem, key_pem)
        errors = self.validator.validate_signed_xml(signed)
        assert errors == []

    def test_signed_xml_rejects_sha1(self):
        """
        SHA-1 debe ser rechazado según INDECOPI/IOFE y PCM Directiva 002-2024.
        """
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

        signed = sign_ubl_xml(xml, cert_pem, key_pem)
        root = etree.fromstring(signed.encode("utf-8"))
        ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        sig_method = root.xpath("//ds:SignatureMethod", namespaces=ns)[0]
        sig_method.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#rsa-sha1")
        digest_method = root.xpath("//ds:DigestMethod", namespaces=ns)[0]
        digest_method.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#sha1")
        bad_xml = etree.tostring(root, encoding="unicode")

        errors = self.validator.validate_signed_xml(bad_xml)
        assert any("2089" in e for e in errors)
        assert any("2095" in e for e in errors)
        assert any("SHA-1" in e for e in errors)


class TestValidatorVoidedDocuments:
    def test_voided_documents_ubl_version_20(self):
        """
        RS N° 300-2014/SUNAT.
        VoidedDocuments usa UBL 2.0 (CustomizationID 1.0), no 2.1.
        """
        from openubl.models import VoidedDocuments, VoidedDocumentsItem
        vd = VoidedDocuments(
            numero=1,
            fechaEmisionComprobantes=date(2024, 1, 1),
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            comprobantes=[VoidedDocumentsItem(serie="F001", numero=1, tipoComprobante="01", descripcionSustento="Error")],
        )
        from openubl.enricher import ContentEnricher
        enricher = ContentEnricher()
        enricher.enrich(vd)
        from openubl.renderer import render_voided_documents
        xml = render_voided_documents(vd)

        errors = SunatValidator().validate_voided_documents(xml)
        assert errors == []
