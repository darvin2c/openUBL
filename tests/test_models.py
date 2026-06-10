"""
Tests for openUBL models.

RS N° 300-2014/SUNAT - Sistema de Emisión Electrónica.
"""
import pytest
from decimal import Decimal
from datetime import date

from openubl.models import (
    Invoice, CreditNote, DebitNote, VoidedDocuments,
    SummaryDocuments, Perception, Retention,
    Proveedor, Cliente, DocumentoVentaDetalle,
    VoidedDocumentsItem, SummaryDocumentsItem,
    Comprobante, ComprobanteImpuestos, ComprobanteValorVenta,
    PercepcionRetencionOperacion, ComprobanteAfectado,
)


class TestInvoiceModel:
    def test_invoice_valid_instantiation(self):
        """
        RS N° 188-2010/SUNAT - Sistema de Emisión Electrónica de Factura.
        RS N° 300-2014/SUNAT, Anexo 1 - Datos mínimos del comprobante.
        Verifica que una factura válida se puede instanciar sin errores.
        """
        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Softgreen S.A.C."),
            cliente=Cliente(nombre="Carlos Feria", numeroDocumentoIdentidad="12121212121", tipoDocumentoIdentidad="6"),
            detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("10"), precio=Decimal("100"))],
        )
        assert invoice.serie == "F001"
        assert invoice.numero == 1

    def test_invalid_ruc_raises_validation_error(self):
        """
        RS N° 300-2014/SUNAT, Anexo 1 - RUC del emisor es obligatorio y debe tener 11 dígitos.
        Error 2010 - RUC inválido.
        """
        with pytest.raises(Exception):
            Proveedor(ruc="1234567890", razonSocial="Test")

    def test_invalid_serie_pattern_raises(self):
        """
        RS N° 300-2014/SUNAT - Serie debe iniciar con F (factura) o B (boleta).
        Error 1001 - Serie no cumple formato.
        """
        with pytest.raises(Exception):
            Invoice(
                serie="X001", numero=1,
                proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
                cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
                detalles=[],
            )

    def test_tipo_documento_identidad_accepted(self):
        """
        Catálogo N.° 06 de SUNAT (RS N° 300-2014/SUNAT Anexo 8).
        El modelo acepta cualquier string; validación contra catálogo está en el validator.
        """
        cliente = Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="99")
        assert cliente.tipoDocumentoIdentidad == "99"


class TestCreditNoteModel:
    def test_credit_note_valid(self):
        """
        RS N° 300-2014/SUNAT - Nota de Crédito Electrónica (07).
        Verifica que una nota de crédito válida se puede instanciar.
        """
        cn = CreditNote(
            serie="BC01", numero=1,
            comprobanteAfectadoSerieNumero="F001-1",
            sustentoDescripcion="Anulación de venta",
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[],
        )
        assert cn.serie == "BC01"


class TestDebitNoteModel:
    def test_debit_note_valid(self):
        """
        RS N° 300-2014/SUNAT - Nota de Débito Electrónica (08).
        Verifica que una nota de débito válida se puede instanciar.
        """
        dn = DebitNote(
            serie="BD01", numero=1,
            comprobanteAfectadoSerieNumero="F001-1",
            sustentoDescripcion="Intereses moratorios",
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[],
        )
        assert dn.serie == "BD01"


class TestVoidedDocumentsModel:
    def test_voided_documents_valid(self):
        """
        RS N° 300-2014/SUNAT - Comunicación de Baja (RA).
        Verifica que una comunicación de baja válida se puede instanciar.
        """
        vd = VoidedDocuments(
            numero=1,
            fechaEmisionComprobantes=date(2024, 1, 1),
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            comprobantes=[VoidedDocumentsItem(serie="F001", numero=1, tipoComprobante="01", descripcionSustento="Error en datos")],
        )
        assert vd.numero == 1


class TestSummaryDocumentsModel:
    def test_summary_documents_valid(self):
        """
        RS N° 300-2014/SUNAT - Resumen Diario (RC).
        Verifica que un resumen diario válido se puede instanciar.
        """
        sd = SummaryDocuments(
            numero=1,
            fechaEmisionComprobantes=date(2024, 1, 1),
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            comprobantes=[
                SummaryDocumentsItem(
                    tipoOperacion="1",
                    comprobante=Comprobante(
                        tipoComprobante="03",
                        serieNumero="B001-1",
                        cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
                        impuestos=ComprobanteImpuestos(igv=Decimal("0.18")),
                        valorVenta=ComprobanteValorVenta(importeTotal=Decimal("1.18")),
                    ),
                ),
            ],
        )
        assert sd.numero == 1


class TestPerceptionModel:
    def test_perception_valid(self):
        """
        RS N° 274-2015/SUNAT - Comprobante de Percepción Electrónico (40).
        Verifica que un comprobante de percepción válido se puede instanciar.
        """
        p = Perception(
            serie="P001", numero=1,
            fechaEmision=date(2024, 1, 1),
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="20100066603", tipoDocumentoIdentidad="6"),
            importeTotalPercibido=Decimal("20.00"),
            importeTotalCobrado=Decimal("1020.00"),
            tipoRegimen="01",
            tipoRegimenPorcentaje=Decimal("0.02"),
            operaciones=[
                PercepcionRetencionOperacion(
                    numeroOperacion=1,
                    fechaOperacion=date(2024, 1, 1),
                    importeOperacion=Decimal("20.00"),
                    comprobante={"tipoComprobante": "01", "serieNumero": "F001-1", "fechaEmision": "2024-01-01", "importeTotal": "1000.00", "moneda": "PEN"},
                ),
            ],
        )
        assert p.serie == "P001"


class TestRetentionModel:
    def test_retention_valid(self):
        """
        RS N° 274-2015/SUNAT - Comprobante de Retención Electrónico (20).
        Verifica que un comprobante de retención válido se puede instanciar.
        """
        r = Retention(
            serie="R001", numero=1,
            fechaEmision=date(2024, 1, 1),
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="20100066603", tipoDocumentoIdentidad="6"),
            importeTotalRetenido=Decimal("30.00"),
            importeTotalPagado=Decimal("970.00"),
            tipoRegimen="01",
            tipoRegimenPorcentaje=Decimal("0.03"),
            operaciones=[
                PercepcionRetencionOperacion(
                    numeroOperacion=1,
                    fechaOperacion=date(2024, 1, 1),
                    importeOperacion=Decimal("30.00"),
                    comprobante={"tipoComprobante": "01", "serieNumero": "F001-1", "fechaEmision": "2024-01-01", "importeTotal": "1000.00", "moneda": "PEN"},
                ),
            ],
        )
        assert r.serie == "R001"
