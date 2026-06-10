"""
Tests for XML rendering.

UBL 2.1 obligatorio por RS N° 043-2019/SUNAT.
"""
from decimal import Decimal
from datetime import date
from lxml import etree

from openubl.models import Invoice, Proveedor, Cliente, DocumentoVentaDetalle
from openubl.enricher import ContentEnricher
from openubl.renderer import render_invoice, render_credit_note


class TestRenderInvoice:
    def test_invoice_xml_root_namespace(self):
        """
        UBL 2.1 (OASIS) obligatorio por RS N° 043-2019/SUNAT.
        Error 2074 - UBLVersionID debe ser 2.1.
        """
        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Softgreen S.A.C."),
            cliente=Cliente(nombre="Carlos Feria", numeroDocumentoIdentidad="12121212121", tipoDocumentoIdentidad="6"),
            detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("10"), precio=Decimal("100"))],
            fechaEmision=date(2024, 1, 1),
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)
        xml = render_invoice(invoice)

        root = etree.fromstring(xml.encode("utf-8"))
        assert root.tag == "{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice"

    def test_ubl_version_id_is_21(self):
        """
        ERROR 2074. UBLVersionID="2.1" obligatorio desde enero 2019.
        """
        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100"))],
            fechaEmision=date(2024, 1, 1),
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)
        xml = render_invoice(invoice)

        root = etree.fromstring(xml.encode("utf-8"))
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        assert root.findtext("cbc:UBLVersionID", namespaces=ns) == "2.1"

    def test_customization_id_is_20(self):
        """
        ERROR 2072. CustomizationID="2.0" para factura electrónica.
        """
        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100"))],
            fechaEmision=date(2024, 1, 1),
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)
        xml = render_invoice(invoice)

        root = etree.fromstring(xml.encode("utf-8"))
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        assert root.findtext("cbc:CustomizationID", namespaces=ns) == "2.0"

    def test_invoice_type_code_with_catalog01(self):
        """
        Catálogo N.° 01 (RS N° 300-2014/SUNAT).
        Error 1004 - InvoiceTypeCode debe ser 01 (FACTURA) o 03 (BOLETA).
        """
        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100"))],
            fechaEmision=date(2024, 1, 1),
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)
        xml = render_invoice(invoice)

        root = etree.fromstring(xml.encode("utf-8"))
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        code = root.find("cbc:InvoiceTypeCode", namespaces=ns)
        assert code.text == "01"
        assert code.get("listAgencyName") == "PE:SUNAT"

    def test_supplier_ruc_scheme_id_6(self):
        """
        Catálogo N.° 06. Error 1007/1008.
        schemeID="6" para RUC del emisor.
        """
        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100"))],
            fechaEmision=date(2024, 1, 1),
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)
        xml = render_invoice(invoice)

        root = etree.fromstring(xml.encode("utf-8"))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        supplier_id = root.find("cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID", namespaces=ns)
        assert supplier_id.get("schemeID") == "6"
        assert supplier_id.text == "20100066603"

    def test_signature_block_structure(self):
        """
        RS N° 300-2014/SUNAT Anexo 1 - firma digital obligatoria.
        Error 2076 (Signature ID), 2078 (SignatoryParty RUC).
        """
        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100"))],
            fechaEmision=date(2024, 1, 1),
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)
        xml = render_invoice(invoice)

        root = etree.fromstring(xml.encode("utf-8"))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        sig_id = root.findtext("cac:Signature/cbc:ID", namespaces=ns)
        assert sig_id == "SignSUNAT"
        signatory_ruc = root.findtext("cac:Signature/cac:SignatoryParty/cac:PartyIdentification/cbc:ID", namespaces=ns)
        assert signatory_ruc == "20100066603"

    def test_tax_scheme_1000_igv(self):
        """
        Catálogo N.° 05. Error 2037.
        1000=IGV, 2000=ISC.
        """
        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100"))],
            fechaEmision=date(2024, 1, 1),
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)
        xml = render_invoice(invoice)

        root = etree.fromstring(xml.encode("utf-8"))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        tax_scheme_id = root.findtext("cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", namespaces=ns)
        assert tax_scheme_id == "1000"

    def test_legal_monetary_total_positive(self):
        """
        ERROR 2062. PayableAmount debe ser > 0.
        """
        invoice = Invoice(
            serie="F001", numero=1,
            proveedor=Proveedor(ruc="20100066603", razonSocial="Test"),
            cliente=Cliente(nombre="Test", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
            detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100"))],
            fechaEmision=date(2024, 1, 1),
        )
        enricher = ContentEnricher()
        enricher.enrich(invoice)
        xml = render_invoice(invoice)

        root = etree.fromstring(xml.encode("utf-8"))
        ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        payable = root.find("cac:LegalMonetaryTotal/cbc:PayableAmount", namespaces=ns)
        assert float(payable.text) > 0
