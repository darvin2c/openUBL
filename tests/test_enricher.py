"""
Tests for ContentEnricher tax calculations.

IGV Ley N° 30296 (tasa 18%).
RS N° 300-2014/SUNAT Anexo 1 - Estructura del comprobante.
"""
from decimal import Decimal
from datetime import date

from openubl.models import Invoice, Proveedor, Cliente, DocumentoVentaDetalle
from openubl.enricher import ContentEnricher


class TestEnricher:
    def test_invoice_igv_calculation_two_lines(self):
        """
        IGV Ley N° 30296 (tasa 18%).
        RS N° 300-2014/SUNAT Anexo 1.
        Verifica que IGV lineal = valor_venta * 0.18.
        Error 3294 - TaxTotal debe cuadrar con sumatoria de líneas.
        """
        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[
                DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("10"), precio=Decimal("100")),
                DocumentoVentaDetalle(descripcion="Item2", cantidad=Decimal("5"), precio=Decimal("200")),
            ],
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)

        assert invoice.valorVentaTotal == Decimal("2000.00")
        assert invoice.igvTotal == Decimal("360.00")
        assert invoice.importeTotal == Decimal("2360.00")

    def test_mixed_afectacion_items(self):
        """
        Catálogo N.° 07 (RS N° 300-2014/SUNAT).
        Verifica que ítems exonerados (20) no generan IGV.
        Error 2371 - TaxExemptionReasonCode inválido.
        """
        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[
                DocumentoVentaDetalle(descripcion="Gravado", cantidad=Decimal("1"), precio=Decimal("100"), tipoAfectacionIGV="10"),
                DocumentoVentaDetalle(descripcion="Exonerado", cantidad=Decimal("1"), precio=Decimal("50"), tipoAfectacionIGV="20"),
            ],
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)

        assert invoice.detalles[0].igv == Decimal("18.00")
        assert invoice.detalles[1].igv == Decimal("0.00")
        assert invoice.igvTotal == Decimal("18.00")

    def test_voided_documents_auto_fecha(self):
        """
        RS N° 300-2014/SUNAT - fecha de emisión del resumen debe ser la fecha de envío.
        Verifica que VoidedDocuments obtiene fechaEmision automáticamente.
        """
        from openubl.models import VoidedDocuments, VoidedDocumentsItem
        vd = VoidedDocuments(
            numero=1,
            fechaEmisionComprobantes=date(2024, 1, 1),
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            comprobantes=[VoidedDocumentsItem(serie="F001", numero=1, tipoComprobante="01", descripcionSustento="Error")],
        )
        enricher = ContentEnricher()
        enricher.enrich(vd)

        assert vd.fechaEmision is not None
