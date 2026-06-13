"""
Summary Documents model for SUNAT electronic invoicing.
RS N° 300-2014/SUNAT - Resumen Diario (RC).
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from .catalog import Catalog1, Catalog19
from .common import Cliente, Proveedor


class ComprobanteImpuestos(BaseModel):
    """Impuestos del comprobante resumido."""
    igv: Decimal
    icb: Decimal | None = None


class ComprobanteValorVenta(BaseModel):
    """Valores de venta del comprobante resumido."""
    importeTotal: Decimal = Field(ge=0)
    gravado: Decimal | None = None
    exonerado: Decimal | None = None
    inafecto: Decimal | None = None

class ComprobanteAfectado(BaseModel):
    """Comprobante afectado para notas."""
    tipoComprobante: Catalog1
    serieNumero: str
    fechaEmision: date
    importeTotal: Decimal
    moneda: str


class Comprobante(BaseModel):
    """Comprobante dentro del resumen diario."""
    tipoComprobante: Catalog1
    serieNumero: str
    cliente: Cliente
    impuestos: ComprobanteImpuestos
    valorVenta: ComprobanteValorVenta
    comprobanteAfectado: ComprobanteAfectado | None = None


class SummaryDocumentsItem(BaseModel):
    """Item del resumen diario.
    
    RS N° 300-2014/SUNAT, Anexo 1:
    - Tipo de operación: Catálogo N.° 19 (ADICIONAR, MODIFICAR, ANULADO)
    """
    tipoOperacion: Catalog19
    comprobante: Comprobante


class SummaryDocuments(BaseModel):
    """Resumen Diario - RC.
    
    RS N° 300-2014/SUNAT, Anexo 1:
    - Identificador: RC-YYYYMMDD-NNNN
    - Fecha de emisión de los comprobantes resumidos
    """
    numero: int
    fechaEmisionComprobantes: date
    proveedor: Proveedor
    comprobantes: list[SummaryDocumentsItem]
