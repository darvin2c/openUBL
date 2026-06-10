"""openUBL models package."""

from .catalog import (
    Catalog1,
    Catalog2,
    Catalog5,
    Catalog6,
    Catalog7,
    Catalog16,
    Catalog19,
    Catalog22,
    Catalog23,
)
from .common import Address, Cliente, Proveedor
from .defaults import DateProvider, Defaults
from .invoice import DocumentoVentaDetalle, Invoice
from .credit_note import CreditNote
from .debit_note import DebitNote
from .voided import VoidedDocuments, VoidedDocumentsItem
from .summary import (
    Comprobante,
    ComprobanteAfectado,
    ComprobanteImpuestos,
    ComprobanteValorVenta,
    SummaryDocuments,
    SummaryDocumentsItem,
)
from .perception import Perception, PercepcionRetencionOperacion
from .retention import Retention

__all__ = [
    "Catalog1",
    "Catalog2",
    "Catalog5",
    "Catalog6",
    "Catalog7",
    "Catalog16",
    "Catalog19",
    "Catalog22",
    "Catalog23",
    "Address",
    "Cliente",
    "Proveedor",
    "DateProvider",
    "Defaults",
    "DocumentoVentaDetalle",
    "Invoice",
    "CreditNote",
    "DebitNote",
    "VoidedDocuments",
    "VoidedDocumentsItem",
    "Comprobante",
    "ComprobanteAfectado",
    "ComprobanteImpuestos",
    "ComprobanteValorVenta",
    "SummaryDocuments",
    "SummaryDocumentsItem",
    "Perception",
    "PercepcionRetencionOperacion",
    "Retention",
]
