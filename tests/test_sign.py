"""
Tests for XML digital signing.

RS N° 300-2014/SUNAT Anexo 1 - Firma Digital con certificado X.509.
Algoritmos SHA-256 según INDECOPI/IOFE y PCM Directiva 002-2024.
"""
from decimal import Decimal
from datetime import date

from openubl.models import Invoice, Proveedor, Cliente, DocumentoVentaDetalle
from openubl.enricher import ContentEnricher
from openubl.renderer import render_invoice
from openubl.signer import sign_ubl_xml
from lxml import etree

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.x509 import CertificateBuilder, Name, NameAttribute
from cryptography.x509.oid import NameOID
import datetime


class TestSign:
    def setup_method(self):
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

        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.cert = CertificateBuilder().subject_name(Name([NameAttribute(NameOID.COMMON_NAME, "Test")])).issuer_name(Name([NameAttribute(NameOID.COMMON_NAME, "Test")])).serial_number(1).not_valid_before(datetime.datetime.utcnow()).not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1)).public_key(self.key.public_key()).sign(self.key, hashes.SHA256())

        self.key_pem = self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()).decode()
        self.cert_pem = self.cert.public_bytes(serialization.Encoding.PEM).decode()

    def test_sign_invoice_with_pem(self):
        """
        RS N° 300-2014/SUNAT Anexo 1 - firma con certificado X.509.
        Verifica estructura completa de firma y algoritmos SHA-256.
        """
        signed = sign_ubl_xml(self.xml, self.cert_pem, self.key_pem)
        assert "ds:Signature" in signed
        assert "SignSUNAT" in signed
        assert "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256" in signed
        assert "http://www.w3.org/2001/04/xmlenc#sha256" in signed
        assert "http://www.w3.org/2000/09/xmldsig#rsa-sha1" not in signed
        assert "http://www.w3.org/2000/09/xmldsig#sha1" not in signed

    def test_signature_id_is_signsunat(self):
        """
        ERROR 2085 - ds:Signature/@Id debe existir.
        """
        signed = sign_ubl_xml(self.xml, self.cert_pem, self.key_pem)
        root = etree.fromstring(signed.encode("utf-8"))
        ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        sig = root.xpath("//ds:Signature", namespaces=ns)[0]
        assert sig.get("Id") == "SignSUNAT"

    def test_x509_certificate_present(self):
        """
        ERROR 2101 - ds:X509Certificate es obligatorio.
        """
        signed = sign_ubl_xml(self.xml, self.cert_pem, self.key_pem)
        root = etree.fromstring(signed.encode("utf-8"))
        ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        x509 = root.xpath("//ds:X509Certificate", namespaces=ns)
        assert len(x509) > 0
        assert len(x509[0].text.strip()) > 2

    def test_signature_value_present(self):
        """
        ERROR 2099 - ds:SignatureValue es obligatorio.
        """
        signed = sign_ubl_xml(self.xml, self.cert_pem, self.key_pem)
        root = etree.fromstring(signed.encode("utf-8"))
        ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        sig_val = root.xpath("//ds:SignatureValue", namespaces=ns)
        assert len(sig_val) > 0
        assert len(sig_val[0].text.strip()) > 2

    def test_signature_verifies_with_signxml(self):
        """
        Verifica que la firma criptográfica es matemáticamente válida.
        """
        from signxml.verifier import XMLVerifier
        signed = sign_ubl_xml(self.xml, self.cert_pem, self.key_pem)
        root = etree.fromstring(signed.encode("utf-8"))
        XMLVerifier().verify(root, x509_cert=self.cert_pem)
