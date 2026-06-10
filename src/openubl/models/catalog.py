"""
SUNAT Catalog constants for electronic documents.
Based on RS N° 300-2014/SUNAT and its annexes.
"""
from enum import Enum


class Catalog1(str, Enum):
    """Tipo de Comprobante - Catálogo N.° 01"""
    FACTURA = "01"
    BOLETA = "03"
    NOTA_CREDITO = "07"
    NOTA_DEBITO = "08"
    GUIA_REMISION = "09"
    COMPROBANTE_RETENCION = "20"
    COMPROBANTE_PERCEPCION = "40"


class Catalog6(str, Enum):
    """Tipo de Documento de Identidad - Catálogo N.° 06"""
    DOC_NO_DOMICILIADO = "0"
    DNI = "1"
    CE = "4"
    RUC = "6"
    PASAPORTE = "7"


class Catalog7(str, Enum):
    """Tipo de Afectación del IGV - Catálogo N.° 07"""
    GRAVADO_OPERACION_ONEROSA = "10"
    EXONERADO_OPERACION_ONEROSA = "20"
    INAFECTO_OPERACION_ONEROSA = "30"


class Catalog16(str, Enum):
    """Tipo de Precio - Catálogo N.° 16"""
    PRECIO_UNITARIO_INCLUYE_IGV = "01"
    VALOR_REFERENCIAL_UNITARIO_EN_OPERACIONES_NO_ONEROSAS = "02"


class Catalog19(str, Enum):
    """Tipo de Operación - Resumen Diario - Catálogo N.° 19"""
    ADICIONAR = "1"
    MODIFICAR = "2"
    ANULADO = "3"


class Catalog22(str, Enum):
    """Régimen de Percepción - Catálogo N.° 22"""
    VENTA_INTERNA = "01"
    ADQUISICION_COMBUSTIBLE = "02"
    TASA_TRES = "03"


class Catalog23(str, Enum):
    """Régimen de Retención - Catálogo N.° 23"""
    TASA_TRES = "01"
    TASA_SEIS = "02"
    TASA_MIXTA = "03"


class Catalog2(str, Enum):
    """Tipo de Moneda - Catálogo N.° 02"""
    PEN = "PEN"
    USD = "USD"
    EUR = "EUR"


class Catalog5(str, Enum):
    """Tipo de Tributo - Catálogo N.° 05"""
    IGV = "1000"
    ISC = "2000"
    EXPORTACION = "9995"
    GRATUITAS = "9996"
    EXONERADO = "9997"
    INAFECTO = "9998"
    OTROS_TRIBUTOS = "9999"
    ICBPER = "7152"
    IVAP = "1016"


class Catalog20(str, Enum):
    """Motivo de Traslado - Catálogo N.° 20"""
    VENTA = "01"
    COMPRA = "02"
    VENTA_SUJETA_A_CONFIRMAR = "03"
    TRASLADO_ENTRE_ESTABLECIMIENTOS = "04"
    CONSIGNACION = "05"
    DEVOLUCION = "06"
    IMPORTACION = "08"
    EXPORTACION = "09"
    TRASLADO_EMISOR_ITINERANTE = "13"
    OTROS = "14"
