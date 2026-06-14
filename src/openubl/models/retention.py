"""
Retention model for SUNAT electronic invoicing.
RS N° 274-2015/SUNAT - Comprobante de Retención Electrónico (20).
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from .catalog import Catalog23
from .common import Cliente, Proveedor
from .perception import ComprobanteAfectado, PercepcionRetencionOperacion


class Retention(BaseModel):
    """Comprobante de Retención Electrónico - Tipo 20.
    
    RS N° 274-2015/SUNAT, Anexo 1:
    - Serie: R### (R001, R002, etc.)
    - Régimen: Catálogo N.° 23
    """
    serie: str = Field(
        pattern=r"^R\d{3}$",
        description="Serie de retención (R###)",
    )
    numero: int = Field(ge=1)
    fechaEmision: date
    proveedor: Proveedor
    cliente: Cliente
    importeTotalRetenido: Decimal
    importeTotalPagado: Decimal
    tipoRegimen: Catalog23
    tipoRegimenPorcentaje: Decimal
    operaciones: list[PercepcionRetencionOperacion]
