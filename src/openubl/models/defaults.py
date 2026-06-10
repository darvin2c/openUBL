"""
Default values for document generation.
"""
from decimal import Decimal

from pydantic import BaseModel


class Defaults(BaseModel):
    """Valores por defecto para cálculos de impuestos.
    
    Ley N° 30296 - IGV tasa 18%
    Ley N° 30830 - ICBPER tasa S/ 0.20
    """
    igvTasa: Decimal = Decimal("0.18")
    icbTasa: Decimal = Decimal("0.2")


class DateProvider:
    """Proveedor de fechas para facilitar testing."""
    
    @staticmethod
    def now():
        from datetime import date
        return date.today()
