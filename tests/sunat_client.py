"""
SUNAT SOAP Client for beta and production web services.
Based on Manual del Programador SUNAT (RS N° 097-2012/SUNAT).

Servicios Beta:
- Factura/Notas: https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService?wsdl
- Retenciones/Percepciones: https://e-beta.sunat.gob.pe/ol-ti-itemision-otroscpe-gem-beta/billService?wsdl
- Guía: https://e-beta.sunat.gob.pe/ol-ti-itemision-guia-gem-beta/billService?wsdl

Credenciales Beta:
- Usuario: {RUC}MODDATOS
- Password: MODDATOS
"""
import base64
from typing import Any

from zeep import Client, Transport
from requests import Session
from requests.auth import HTTPBasicAuth


class SunatConnectionError(Exception):
    """Error connecting to SUNAT web service."""
    pass


class SunatBetaClient:
    WSDL_FACTURA = "https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService?wsdl"
    WSDL_RETENCIONES = "https://e-beta.sunat.gob.pe/ol-ti-itemision-otroscpe-gem-beta/billService?wsdl"
    WSDL_GUIA = "https://e-beta.sunat.gob.pe/ol-ti-itemision-guia-gem-beta/billService?wsdl"

    def __init__(self, ruc: str, username_suffix: str = "MODDATOS", password: str = "MODDATOS"):
        self.ruc = ruc
        self.username = f"{ruc}{username_suffix}"
        self.password = password

    def _get_client(self, wsdl_url: str) -> Client:
        session = Session()
        session.auth = HTTPBasicAuth(self.username, self.password)
        return Client(wsdl_url, transport=Transport(session=session))

    def send_bill(self, filename: str, zip_bytes: bytes, document_type: str = "invoice") -> dict:
        """Send synchronous document (invoice, credit note, debit note, perception, retention)."""
        wsdl = self.WSDL_FACTURA if document_type in ("invoice", "credit_note", "debit_note") else self.WSDL_RETENCIONES
        client = self._get_client(wsdl)
        
        try:
            response = client.service.sendBill(
                fileName=filename,
                contentFile=zip_bytes,
            )
            cdr_zip = response
            return {
                "cdr_zip": cdr_zip,
                "status": "RECEIVED",
            }
        except Exception as e:
            raise SunatConnectionError(f"SUNAT sendBill error: {e}") from e

    def send_summary(self, filename: str, zip_bytes: bytes) -> str:
        """Send async document (summary, voided) and return ticket."""
        client = self._get_client(self.WSDL_FACTURA)
        
        try:
            response = client.service.sendSummary(
                fileName=filename,
                contentFile=zip_bytes,
            )
            return str(response)
        except Exception as e:
            raise SunatConnectionError(f"SUNAT sendSummary error: {e}") from e

    def get_status(self, ticket: str) -> dict:
        """Retrieve CDR for async documents using ticket."""
        client = self._get_client(self.WSDL_FACTURA)
        
        try:
            response = client.service.getStatus(ticket)
            return {
                "cdr_zip": response.content,
                "status_code": response.statusCode,
            }
        except Exception as e:
            raise SunatConnectionError(f"SUNAT getStatus error: {e}") from e

    def get_status_cdr(self, tipo: str, serie: str, numero: str) -> dict:
        """Query CDR for existing document."""
        client = self._get_client(self.WSDL_FACTURA)
        
        try:
            response = client.service.getStatusCdr(
                rucComprobante=self.ruc,
                tipoComprobante=tipo,
                serieComprobante=serie,
                numeroComprobante=numero,
            )
            return {
                "cdr_zip": response.content,
                "status_code": response.statusCode,
            }
        except Exception as e:
            raise SunatConnectionError(f"SUNAT getStatusCdr error: {e}") from e
