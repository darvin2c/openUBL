"""
Credit Note model for SUNAT electronic invoicing.
RS N° 300-2014/SUNAT - Nota de Crédito Electrónica (07).
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from .common import Cliente, Proveedor
from .invoice import DocumentoVentaDetalle


class CreditNote(BaseModel):
    """Nota de Crédito Electrónica - Tipo 07.
    
    RS N° 300-2014/SUNAT, Anexo 1:
    - Serie: debe iniciar con B/C o F/E según tipo de documento afectado
    - Debe referenciar el comprobante afectado
    """
    serie: str = Field(
        pattern=r"^[BCbc][A-Za-z0-9]{2,3}$",
        description="Serie de nota de crédito",
    )
    numero: int
    comprobanteAfectadoSerieNumero: str
    sustentoDescripcion: str
    proveedor: Proveedor
    cliente: Cliente
    detalles: list[DocumentoVentaDetalle]
    moneda: str = "PEN"
    fechaEmision: date | None = None
    igvTotal: Decimal | None = None
    valorVentaTotal: Decimal | None = None
    importeTotal: Decimal | None = None
