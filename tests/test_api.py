"""
Tests for FastAPI integration.

RS N° 300-2014/SUNAT - Sistema de Emisión Electrónica.
"""
import pytest
from fastapi.testclient import TestClient

from openubl.main import app


client = TestClient(app)


class TestApiInvoice:
    def test_api_invoice_create_success(self):
        """
        RS N° 300-2014/SUNAT - endpoint de emisión electrónica.
        Verifica que el endpoint /api/v1/invoice/create devuelve XML válido.
        """
        response = client.post("/api/v1/invoice/create", json={
            "serie": "F001", "numero": 1,
            "proveedor": {"ruc": "20100066603", "razonSocial": "Softgreen S.A.C."},
            "cliente": {"nombre": "Carlos Feria", "numeroDocumentoIdentidad": "12121212121", "tipoDocumentoIdentidad": "6"},
            "detalles": [{"descripcion": "Item1", "cantidad": "10", "precio": "100", "unidadMedida": "KGM"}],
            "moneda": "PEN",
            "fechaEmision": "2024-01-01",
        })
        assert response.status_code == 200
        data = response.json()
        assert "xml" in data
        assert data["xml"].startswith("<?xml")
        assert "F001-1" in data["xml"]

    def test_api_invoice_create_skip_validation(self):
        """
        Verifica que validate=false funciona para debugging.
        """
        response = client.post("/api/v1/invoice/create?validate=false", json={
            "serie": "F001", "numero": 1,
            "proveedor": {"ruc": "20100066603", "razonSocial": "Softgreen S.A.C."},
            "cliente": {"nombre": "Carlos Feria", "numeroDocumentoIdentidad": "12121212121", "tipoDocumentoIdentidad": "6"},
            "detalles": [{"descripcion": "Item1", "cantidad": "10", "precio": "100", "unidadMedida": "KGM"}],
        })
        assert response.status_code == 200
        assert "xml" in response.json()

    def test_api_invoice_create_invalid_payload(self):
        """
        Verifica Pydantic validation (RS N° 300-2014/SUNAT datos mínimos).
        """
        response = client.post("/api/v1/invoice/create", json={
            "serie": "F001", "numero": 1,
            # Missing proveedor
            "cliente": {"nombre": "Test", "numeroDocumentoIdentidad": "12345678", "tipoDocumentoIdentidad": "1"},
            "detalles": [],
        })
        assert response.status_code == 422


class TestApiSign:
    def test_api_sign_with_pem(self):
        """
        RS N° 300-2014/SUNAT - firma digital es obligatoria antes del envío.
        """
        from openubl.models import Invoice, Proveedor, Cliente, DocumentoVentaDetalle
        from openubl.enricher import ContentEnricher
        from openubl.renderer import render_invoice
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.x509 import CertificateBuilder, Name, NameAttribute
        from cryptography.x509.oid import NameOID
        import datetime

        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[{"descripcion": "Item1", "cantidad": "1", "precio": "100", "unidadMedida": "NIU"}],
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)
        xml = render_invoice(invoice)

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cert = CertificateBuilder().subject_name(Name([NameAttribute(NameOID.COMMON_NAME, "Test")])).issuer_name(Name([NameAttribute(NameOID.COMMON_NAME, "Test")])).serial_number(1).not_valid_before(datetime.datetime.utcnow()).not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1)).public_key(key.public_key()).sign(key, hashes.SHA256())
        key_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()).decode()
        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()

        response = client.post("/api/v1/sign", json={
            "xml": xml,
            "cert_pem": cert_pem,
            "key_pem": key_pem,
        })
        assert response.status_code == 200
        assert "signed_xml" in response.json()
        assert "ds:Signature" in response.json()["signed_xml"]

    def test_api_credit_note_create(self):
        """
        RS N° 300-2014/SUNAT - Nota de Crédito Electrónica (07).
        """
        response = client.post("/api/v1/credit-note/create", json={
            "serie": "BC01", "numero": 1,
            "comprobanteAfectadoSerieNumero": "F001-1",
            "sustentoDescripcion": "Anulación de venta",
            "proveedor": {"ruc": "20100066603", "razonSocial": "Test"},
            "cliente": {"nombre": "Test", "numeroDocumentoIdentidad": "12345678", "tipoDocumentoIdentidad": "1"},
            "detalles": [{"descripcion": "Item1", "cantidad": "1", "precio": "100"}],
            "fechaEmision": "2024-01-01",
        })
        assert response.status_code == 200
        assert "CreditNote" in response.json()["xml"]

    def test_api_voided_documents_create(self):
        """
        RS N° 300-2014/SUNAT - Comunicación de Baja (RA).
        """
        response = client.post("/api/v1/voided-documents/create", json={
            "numero": 1,
            "fechaEmisionComprobantes": "2024-01-01",
            "proveedor": {"ruc": "20100066603", "razonSocial": "Test"},
            "comprobantes": [{"serie": "F001", "numero": 1, "tipoComprobante": "01", "descripcionSustento": "Error"}],
        })
        assert response.status_code == 200
        assert "VoidedDocuments" in response.json()["xml"]


class TestApiVersion:
    def test_api_version_returns_current_version(self):
        from openubl import __version__
        response = client.get("/api/v1/version")
        assert response.status_code == 200
        assert response.json()["version"] == __version__
