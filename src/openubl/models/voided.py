"""
Voided Documents model for SUNAT electronic invoicing.
RS N° 300-2014/SUNAT - Comunicación de Baja (RA).
"""
from datetime import date

from pydantic import BaseModel, Field

from .catalog import Catalog1
from .common import Proveedor

class VoidedDocumentsItem(BaseModel):
    """Item de comunicación de baja.
    
    RS N° 300-2014/SUNAT, Anexo 1:
    - Tipo de comprobante: Catálogo N.° 01
    - Serie y número del comprobante a dar de baja
    """
    serie: str
    numero: int = Field(ge=1)
    tipoComprobante: Catalog1
    descripcionSustento: str

class VoidedDocuments(BaseModel):
    """Comunicación de Baja - RA.
    
    RS N° 300-2014/SUNAT, Anexo 1:
    - Identificador: RA-YYYYMMDD-NNNN
    - Fecha de emisión de los comprobantes que se dan de baja
    """
    numero: int = Field(ge=1)
    fechaEmision: date | None = None
    fechaEmisionComprobantes: date
    proveedor: Proveedor
    comprobantes: list[VoidedDocumentsItem]
