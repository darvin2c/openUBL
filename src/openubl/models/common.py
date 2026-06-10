"""
Common models for electronic documents.
Based on RS N° 300-2014/SUNAT - Sistema de Emisión Electrónica.
"""
from pydantic import BaseModel, Field


class Address(BaseModel):
    """Dirección según esquema UBL 2.1 de SUNAT."""
    ubigeo: str | None = None
    direccion: str | None = None
    urbanizacion: str | None = None
    provincia: str | None = None
    departamento: str | None = None
    distrito: str | None = None
    codigoPais: str = "PE"


class Proveedor(BaseModel):
    """Datos del emisor del comprobante.
    
    RS N° 300-2014/SUNAT, Anexo 1:
    - RUC del emisor: 11 dígitos numéricos (Catálogo N.° 06, valor 6)
    - Razón social: obligatoria
    """
    ruc: str = Field(
        min_length=11,
        max_length=11,
        pattern=r"^\d{11}$",
        description="RUC del emisor - 11 dígitos numéricos",
    )
    razonSocial: str
    nombreComercial: str | None = None
    address: Address | None = None


class Cliente(BaseModel):
    """Datos del adquirente o usuario.
    
    RS N° 300-2014/SUNAT, Anexo 1:
    - Tipo de documento: Catálogo N.° 06
    - Número de documento: según tipo
    """
    nombre: str
    numeroDocumentoIdentidad: str
    tipoDocumentoIdentidad: str  # Catalog6 code
