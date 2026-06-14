"""
Tests for FastAPI integration.

RS N° 300-2014/SUNAT - Sistema de Emisión Electrónica.
"""
import base64
import datetime

import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509 import CertificateBuilder, Name, NameAttribute
from cryptography.x509.oid import NameOID

from openubl.main import app
from openubl.models import Invoice, Proveedor, Cliente, DocumentoVentaDetalle
from openubl.enricher import ContentEnricher
from openubl.renderer import render_invoice


client = TestClient(app)


def _valid_invoice_dict():
    return {
        "serie": "F001", "numero": 1,
        "proveedor": {"ruc": "20100066603", "razonSocial": "Softgreen S.A.C."},
        "cliente": {"nombre": "Carlos Feria", "numeroDocumentoIdentidad": "12121212121", "tipoDocumentoIdentidad": "6"},
        "detalles": [{"descripcion": "Item1", "cantidad": "10", "precio": "100", "unidadMedida": "KGM"}],
        "moneda": "PEN",
        "fechaEmision": "2024-01-01",
    }


def _generate_cert():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = CertificateBuilder().subject_name(Name([NameAttribute(NameOID.COMMON_NAME, "Test")])).issuer_name(Name([NameAttribute(NameOID.COMMON_NAME, "Test")])).serial_number(1).not_valid_before(datetime.datetime.utcnow()).not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1)).public_key(key.public_key()).sign(key, hashes.SHA256())
    key_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()).decode()
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    return key_pem, cert_pem


def _generate_pfx(password: str = "testpass"):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = CertificateBuilder().subject_name(Name([NameAttribute(NameOID.COMMON_NAME, "Test")])).issuer_name(Name([NameAttribute(NameOID.COMMON_NAME, "Test")])).serial_number(1).not_valid_before(datetime.datetime.utcnow()).not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=1)).public_key(key.public_key()).sign(key, hashes.SHA256())
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode()),
    )
    return base64.b64encode(pfx_bytes).decode("ascii")


class TestApiInvoice:
    def test_create_invoice_returns_unsigned_xml_when_firmar_false(self):
        """RS N° 300-2014/SUNAT - endpoint /create sin firma."""
        response = client.post("/api/v1/invoice/create", json={
            "documento": _valid_invoice_dict(),
            "firmar": False,
            "validar_sunat": True,
        })
        assert response.status_code == 200
        data = response.json()
        assert "xml" in data
        assert data["xml"].startswith("<?xml")
        assert "F001-1" in data["xml"]
        assert data["firmado"] is False
        assert data["validado_sunat"] is True
        assert data["valid"] is True
        assert data["errors"] == []

    def test_create_invoice_returns_signed_xml_when_firmar_true(self):
        """RS N° 300-2014/SUNAT - endpoint /create con firma PEM."""
        key_pem, cert_pem = _generate_cert()
        response = client.post("/api/v1/invoice/create", json={
            "documento": _valid_invoice_dict(),
            "credenciales": {"cert_pem": cert_pem, "key_pem": key_pem},
            "firmar": True,
            "validar_sunat": True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["firmado"] is True
        assert "ds:Signature" in data["xml"]

    def test_create_invoice_returns_422_on_sunat_error(self):
        """RS N° 300-2014/SUNAT - validación SUNAT rechaza ID inválido."""
        doc = _valid_invoice_dict()
        doc["serie"] = "INVALID"
        response = client.post("/api/v1/invoice/create", json={
            "documento": doc,
            "firmar": False,
            "validar_sunat": True,
        })
        assert response.status_code == 422
        detail = response.json()["detail"]
        codes = [e["code"] for e in detail]
        assert "1001" in codes

    def test_create_invoice_returns_422_on_missing_credentials(self):
        """El endpoint debe rechazar firmar=true sin credenciales."""
        response = client.post("/api/v1/invoice/create", json={
            "documento": _valid_invoice_dict(),
            "firmar": True,
            "validar_sunat": False,
        })
        assert response.status_code == 422

    def test_create_invoice_no_validation(self):
        """validar_sunat=false omite validación y devuelve None."""
        response = client.post("/api/v1/invoice/create", json={
            "documento": _valid_invoice_dict(),
            "firmar": False,
            "validar_sunat": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["validado_sunat"] is False
        assert data["valid"] is None
        assert data["errors"] is None

    def test_create_invoice_with_pfx(self):
        """RS N° 300-2014/SUNAT - endpoint /create con firma PFX."""
        pfx_base64 = _generate_pfx()
        response = client.post("/api/v1/invoice/create", json={
            "documento": _valid_invoice_dict(),
            "credenciales": {"pfx_base64": pfx_base64, "pfx_password": "testpass"},
            "firmar": True,
            "validar_sunat": True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["firmado"] is True
        assert "ds:Signature" in data["xml"]

    def test_create_invoice_with_bad_pfx_password(self):
        """PFX con password incorrecto debe retornar 422."""
        pfx_base64 = _generate_pfx()
        response = client.post("/api/v1/invoice/create", json={
            "documento": _valid_invoice_dict(),
            "credenciales": {"pfx_base64": pfx_base64, "pfx_password": "wrongpass"},
            "firmar": True,
            "validar_sunat": False,
        })
        assert response.status_code == 422


class TestApiSign:
    def test_api_sign_with_pem(self):
        """RS N° 300-2014/SUNAT - firma digital es obligatoria antes del envío."""
        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[{"descripcion": "Item1", "cantidad": "1", "precio": "100", "unidadMedida": "NIU"}],
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)
        xml = render_invoice(invoice)

        key_pem, cert_pem = _generate_cert()
        response = client.post("/api/v1/sign", json={
            "xml": xml,
            "cert_pem": cert_pem,
            "key_pem": key_pem,
        })
        assert response.status_code == 200
        data = response.json()
        assert "signed_xml" in data
        assert "ds:Signature" in data["signed_xml"]
        assert "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256" in data["signed_xml"]
        assert "http://www.w3.org/2001/04/xmlenc#sha256" in data["signed_xml"]
        assert "http://www.w3.org/2000/09/xmldsig#rsa-sha1" not in data["signed_xml"]

    def test_api_sign_missing_credentials(self):
        """El endpoint debe rechazar peticiones sin credenciales."""
        response = client.post("/api/v1/sign", json={"xml": "<test/>"})
        assert response.status_code == 422

    def test_api_sign_invalid_base64(self):
        """El endpoint debe rechazar pfx_base64 con formato inválido."""
        response = client.post("/api/v1/sign", json={
            "xml": "<test/>",
            "pfx_base64": "!!!no_es_base64!!!",
            "pfx_password": "x",
        })
        assert response.status_code == 422

    def test_api_sign_wrong_pfx_password(self):
        """El endpoint debe rechazar un PFX cuando el password es incorrecto."""
        pfx_base64 = _generate_pfx()
        response = client.post("/api/v1/sign", json={
            "xml": "<test/>",
            "pfx_base64": pfx_base64,
            "pfx_password": "wrongpass",
        })
        assert response.status_code == 422


class TestApiCreditNote:
    def test_api_credit_note_create(self):
        """RS N° 300-2014/SUNAT - Nota de Crédito Electrónica (07)."""
        response = client.post("/api/v1/credit-note/create", json={
            "documento": {
                "serie": "FC01", "numero": 1,
                "comprobanteAfectadoSerieNumero": "F001-1",
                "sustentoDescripcion": "Anulación de venta",
                "proveedor": {"ruc": "20100066603", "razonSocial": "Test"},
                "cliente": {"nombre": "Test", "numeroDocumentoIdentidad": "12345678", "tipoDocumentoIdentidad": "1"},
                "detalles": [{"descripcion": "Item1", "cantidad": "1", "precio": "100"}],
                "fechaEmision": "2024-01-01",
            },
            "firmar": False,
            "validar_sunat": True,
        })
        assert response.status_code == 200
        assert "CreditNote" in response.json()["xml"]


class TestApiVoidedDocuments:
    def test_api_voided_documents_create(self):
        """RS N° 300-2014/SUNAT - Comunicación de Baja (RA)."""
        response = client.post("/api/v1/voided-documents/create", json={
            "documento": {
                "numero": 1,
                "fechaEmisionComprobantes": "2024-01-01",
                "proveedor": {"ruc": "20100066603", "razonSocial": "Test"},
                "comprobantes": [{"serie": "F001", "numero": 1, "tipoComprobante": "01", "descripcionSustento": "Error"}],
            },
            "firmar": False,
            "validar_sunat": True,
        })
        assert response.status_code == 200
        assert "VoidedDocuments" in response.json()["xml"]


class TestApiVersion:
    def test_api_version_returns_current_version(self):
        from openubl import __version__
        response = client.get("/api/v1/version")
        assert response.status_code == 200
        assert response.json()["version"] == __version__
