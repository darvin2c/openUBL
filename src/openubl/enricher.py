"""
ContentEnricher - Auto-calculates tax fields and totals.

RS N° 300-2014/SUNAT, Anexo 1:
- IGV: 18% (Ley N° 30296)
- ICBPER: S/ 0.20 (Ley N° 30830)
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .models.defaults import DateProvider, Defaults
from .models.invoice import DocumentoVentaDetalle, Invoice
from .models.credit_note import CreditNote
from .models.debit_note import DebitNote
from .models.voided import VoidedDocuments


def _round(value: Decimal) -> Decimal:
    """Round to 2 decimal places using HALF_UP."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ContentEnricher:
    """Enriches documents with auto-calculated tax fields."""
    
    def __init__(self, defaults: Defaults | None = None, date_provider: DateProvider | None = None):
        self.defaults = defaults or Defaults()
        self.date_provider = date_provider or DateProvider()
    
    def enrich(self, doc):
        """Enrich a document in-place."""
        if isinstance(doc, (Invoice, CreditNote, DebitNote)):
            self._enrich_invoice_like(doc)
        elif isinstance(doc, VoidedDocuments):
            self._enrich_voided(doc)
        # Summary, Perception, Retention: no enrichment needed
    
    def _enrich_invoice_like(self, doc: Invoice | CreditNote | DebitNote):
        """Enrich invoice, credit note, or debit note."""
        if doc.fechaEmision is None:
            doc.fechaEmision = self.date_provider.now()
        
        for detalle in doc.detalles:
            self._enrich_detalle(detalle)
        
        doc.valorVentaTotal = _round(sum(d.valorVenta or Decimal("0") for d in doc.detalles))
        doc.igvTotal = _round(sum(d.igv or Decimal("0") for d in doc.detalles))
        doc.importeTotal = _round(doc.valorVentaTotal + doc.igvTotal)
    
    def _enrich_detalle(self, detalle: DocumentoVentaDetalle):
        """Enrich a single line item."""
        if detalle.valorVenta is None:
            detalle.valorVenta = _round(detalle.cantidad * detalle.precio)
        
        if detalle.igv is None:
            if detalle.tipoAfectacionIGV == "10":  # Gravado
                detalle.igv = _round(detalle.valorVenta * self.defaults.igvTasa)
            else:
                detalle.igv = Decimal("0")
        
        if detalle.precioVenta is None:
            detalle.precioVenta = _round((detalle.valorVenta + detalle.igv) / detalle.cantidad)
    
    def _enrich_voided(self, doc: VoidedDocuments):
        """Enrich voided documents."""
        if doc.fechaEmision is None:
            doc.fechaEmision = self.date_provider.now()
