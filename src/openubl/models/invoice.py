"""
Invoice model for SUNAT electronic invoicing.
RS N° 300-2014/SUNAT - Factura Electrónica (01).
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from .common import Cliente, Proveedor


class DocumentoVentaDetalle(BaseModel):
    """Línea de detalle de un documento de venta.
    
    RS N° 300-2014/SUNAT, Anexo 1:
    - Descripción del bien o servicio
    - Cantidad y unidad de medida (Catálogo N.° 03)
    - Valor unitario (sin IGV)
    - Tipo de afectación del IGV (Catálogo N.° 07)
    """
    descripcion: str
    cantidad: Decimal
    precio: Decimal
    unidadMedida: str = "NIU"
    tipoAfectacionIGV: str = "10"  # Catalog7 default: GRAVADO_OPERACION_ONEROSA
    igv: Decimal | None = None
    valorVenta: Decimal | None = None
    precioVenta: Decimal | None = None


class Invoice(BaseModel):
    """Factura Electrónica - Tipo 01.
    
    RS N° 300-2014/SUNAT, Anexo 1:
    - Serie: debe iniciar con F (factura) o B (boleta)
    - Número: correlativo
    - Tipo de operación: Catálogo N.° 51, default 0101 (Venta interna)
    """
    serie: str = Field(
        pattern=r"^[FBfb][A-Za-z0-9]{2,3}$",
        description="Serie de factura (F001) o boleta (B001)",
    )
    numero: int
    proveedor: Proveedor
    cliente: Cliente
    detalles: list[DocumentoVentaDetalle]
    moneda: str = "PEN"
    fechaEmision: date | None = None
    igvTotal: Decimal | None = None
    valorVentaTotal: Decimal | None = None
    importeTotal: Decimal | None = None
    tipoOperacion: str = "0101"  # Default: Venta interna
