"""
Perception model for SUNAT electronic invoicing.
RS N° 274-2015/SUNAT - Comprobante de Percepción Electrónico (40).
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from .catalog import Catalog2, Catalog22
from .common import Cliente, Proveedor

class ComprobanteAfectado(BaseModel):
    """Comprobante afectado por la percepción."""
    tipoComprobante: str
    serieNumero: str
    fechaEmision: date
    importeTotal: Decimal
    moneda: Catalog2


class PercepcionRetencionOperacion(BaseModel):
    """Operación de percepción."""
    numeroOperacion: int
    fechaOperacion: date
    importeOperacion: Decimal
    comprobante: ComprobanteAfectado

class Perception(BaseModel):
    """Comprobante de Percepción Electrónico - Tipo 40.
    
    RS N° 274-2015/SUNAT, Anexo 1:
    - Serie: P### (P001, P002, etc.)
    - Régimen: Catálogo N.° 22
    """
    serie: str = Field(
        pattern=r"^P\d{3}$",
        description="Serie de percepción (P###)",
    )
    numero: int = Field(ge=1)
    fechaEmision: date
    proveedor: Proveedor
    cliente: Cliente
    importeTotalPercibido: Decimal
    importeTotalCobrado: Decimal
    tipoRegimen: Catalog22
    tipoRegimenPorcentaje: Decimal
    operaciones: list[PercepcionRetencionOperacion]
