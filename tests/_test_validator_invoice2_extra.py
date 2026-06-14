"""Tests extra parametrizados para reglas SUNAT de Invoice (batch 2).

Cubre los códigos 3092-3217 del Excel "Reglas de validación actualizado al
24.04.2026" publicado en https://cpe.sunat.gob.pe/guias-y-manuales.

Fuente: rules_Invoice.txt
"""

from datetime import date
from decimal import Decimal

import pytest
from lxml import etree

from openubl.enricher import ContentEnricher
from openubl.models import Cliente, DocumentoVentaDetalle, Invoice, Proveedor
from openubl.renderer import render_invoice
from openubl.validators._extra_invoice2 import validate_invoice_extra2


_NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
_NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"


def _valid_invoice_root(op: str = "0101") -> etree._Element:
    invoice = Invoice(
        serie="F001",
        numero=1,
        tipoOperacion=op,  # type: ignore[arg-type]
        proveedor=Proveedor(ruc="20100066603", razonSocial="Softgreen S.A.C."),
        cliente=Cliente(nombre="Carlos Feria", numeroDocumentoIdentidad="12121212121", tipoDocumentoIdentidad="6"),
        detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("10"), precio=Decimal("100"))],
        fechaEmision=date(2024, 1, 1),
    )
    ContentEnricher().enrich(invoice)
    xml = render_invoice(invoice)
    root = etree.fromstring(xml.encode("utf-8"))
    return root


def _set_text(root: etree._Element, xpath: str, value: str) -> None:
    elem = root.xpath(xpath, namespaces={"cac": _NS_CAC, "cbc": _NS_CBC})[0]
    elem.text = value


def _remove_node(root: etree._Element, xpath: str) -> None:
    elem = root.xpath(xpath, namespaces={"cac": _NS_CAC, "cbc": _NS_CBC})[0]
    elem.getparent().remove(elem)


def _add_child(parent: etree._Element, ns: str, tag: str, text: str | None = None, attrs: dict | None = None) -> etree._Element:
    child = etree.SubElement(parent, f"{{{ns}}}{tag}")
    if text is not None:
        child.text = text
    if attrs:
        for k, v in attrs.items():
            child.set(k, v)
    return child


def _set_invoice_op(root: etree._Element, op: str) -> None:
    # El renderer usa Catalog51.NOMBRE en listID
    from openubl.models.catalog import Catalog51
    name = None
    for m in Catalog51:
        if m.value == op:
            name = m.name
            break
    list_id = f"Catalog51.{name}" if name else op
    root.xpath("//cbc:InvoiceTypeCode", namespaces={"cbc": _NS_CBC})[0].set("listID", list_id)


def _add_global_allowance_charge(root: etree._Element, indicator: str, reason: str, amount: str, base: str | None = None) -> None:
    ac = _add_child(root, _NS_CAC, "AllowanceCharge")
    _add_child(ac, _NS_CBC, "ChargeIndicator", indicator)
    _add_child(ac, _NS_CBC, "AllowanceChargeReasonCode", reason)
    _add_child(ac, _NS_CBC, "Amount", amount, {"currencyID": "Catalog2.PEN"})
    if base is not None:
        _add_child(ac, _NS_CBC, "BaseAmount", base, {"currencyID": "Catalog2.PEN"})


def _add_payment_terms(root: etree._Element, id_: str, means: str | None = None, amount: str | None = None, due_date: str | None = None) -> None:
    pt = _add_child(root, _NS_CAC, "PaymentTerms")
    _add_child(pt, _NS_CBC, "ID", id_)
    if means is not None:
        _add_child(pt, _NS_CBC, "PaymentMeansID", means)
    if amount is not None:
        _add_child(pt, _NS_CBC, "Amount", amount, {"currencyID": "Catalog2.PEN"})
    if due_date is not None:
        _add_child(pt, _NS_CBC, "PaymentDueDate", due_date)


def _add_payment_means(root: etree._Element, id_: str, account: str | None = None) -> None:
    pm = _add_child(root, _NS_CAC, "PaymentMeans")
    _add_child(pm, _NS_CBC, "ID", id_)
    if account is not None:
        pfa = _add_child(pm, _NS_CAC, "PayeeFinancialAccount")
        _add_child(pfa, _NS_CBC, "ID", account)


def _add_prepaid_payment(root: etree._Element, id_: str, amount: str) -> None:
    pp = _add_child(root, _NS_CAC, "PrepaidPayment")
    _add_child(pp, _NS_CBC, "ID", id_)
    _add_child(pp, _NS_CBC, "PaidAmount", amount, {"currencyID": "Catalog2.PEN"})


def _add_additional_document_reference(root: etree._Element, doc_type: str, status: str, doc_id: str, issuer_ruc: str) -> None:
    adr = _add_child(root, _NS_CAC, "AdditionalDocumentReference")
    _add_child(adr, _NS_CBC, "ID", doc_id)
    _add_child(adr, _NS_CBC, "DocumentTypeCode", doc_type)
    _add_child(adr, _NS_CBC, "DocumentStatusCode", status)
    issuer = _add_child(adr, _NS_CAC, "IssuerParty")
    party = _add_child(issuer, _NS_CAC, "Party")
    pi = _add_child(party, _NS_CAC, "PartyIdentification")
    _add_child(pi, _NS_CBC, "ID", issuer_ruc, {"schemeID": "6"})


def _add_item_property(root: etree._Element, code: str, value: str | None = None, value_quantity: str | None = None, unit_code: str | None = None) -> None:
    item = root.xpath("//cac:InvoiceLine/cac:Item", namespaces={"cac": _NS_CAC})[0]
    prop = _add_child(item, _NS_CAC, "AdditionalItemProperty")
    _add_child(prop, _NS_CBC, "NameCode", code)
    if value is not None:
        _add_child(prop, _NS_CBC, "Value", value)
    if value_quantity is not None:
        vq = _add_child(prop, _NS_CBC, "ValueQuantity", value_quantity)
        if unit_code is not None:
            vq.set("unitCode", unit_code)


def _add_line_delivery_terms(root: etree._Element, ref_type: str, amount: str) -> None:
    line = root.xpath("//cac:InvoiceLine", namespaces={"cac": _NS_CAC})[0]
    delivery = _add_child(line, _NS_CAC, "Delivery")
    terms = _add_child(delivery, _NS_CAC, "DeliveryTerms")
    _add_child(terms, _NS_CBC, "ID", ref_type)
    _add_child(terms, _NS_CBC, "Amount", amount, {"currencyID": "Catalog2.PEN"})


def _add_line_delivery_cargo(root: etree._Element) -> None:
    line = root.xpath("//cac:InvoiceLine", namespaces={"cac": _NS_CAC})[0]
    delivery = line.find("cac:Delivery", namespaces={"cac": _NS_CAC})
    if delivery is None:
        delivery = _add_child(line, _NS_CAC, "Delivery")
    despatch = _add_child(delivery, _NS_CAC, "Despatch")
    addr = _add_child(despatch, _NS_CAC, "DespatchAddress")
    al = _add_child(addr, _NS_CAC, "AddressLine")
    _add_child(al, _NS_CBC, "Line", "Origen")
    _add_child(despatch, _NS_CBC, "Instructions", "Detalle viaje")
    loc = _add_child(delivery, _NS_CAC, "DeliveryLocation")
    addr2 = _add_child(loc, _NS_CAC, "Address")
    _add_child(addr2, _NS_CBC, "ID", "150101")
    al2 = _add_child(addr2, _NS_CAC, "AddressLine")
    _add_child(al2, _NS_CBC, "Line", "Destino")


def _add_tax_subtotal_to_line(root: etree._Element, tax_code: str, taxable: str, tax_amount: str, percent: str | None = None, tier: str | None = None) -> None:
    line = root.xpath("//cac:InvoiceLine", namespaces={"cac": _NS_CAC})[0]
    tt = line.find("cac:TaxTotal", namespaces={"cac": _NS_CAC})
    if tt is None:
        tt = _add_child(line, _NS_CAC, "TaxTotal")
        _add_child(tt, _NS_CBC, "TaxAmount", tax_amount, {"currencyID": "Catalog2.PEN"})
    ts = _add_child(tt, _NS_CAC, "TaxSubtotal")
    _add_child(ts, _NS_CBC, "TaxableAmount", taxable, {"currencyID": "Catalog2.PEN"})
    _add_child(ts, _NS_CBC, "TaxAmount", tax_amount, {"currencyID": "Catalog2.PEN"})
    tc = _add_child(ts, _NS_CAC, "TaxCategory")
    if percent is not None:
        _add_child(tc, _NS_CBC, "Percent", percent)
    if tier is not None:
        _add_child(tc, _NS_CBC, "TierRange", tier)
    exemp = _add_child(tc, _NS_CBC, "TaxExemptionReasonCode", "10")
    if tax_code == "9996":
        exemp.text = "11"
    tsch = _add_child(tc, _NS_CAC, "TaxScheme")
    _add_child(tsch, _NS_CBC, "ID", tax_code)
    names = {"1000": "IGV", "1016": "IVAP", "2000": "ISC", "9995": "EXP", "9996": "GRATUITA", "9997": "EXO", "9998": "INA", "9999": "OTROS", "7152": "ICBPER"}
    _add_child(tsch, _NS_CBC, "Name", names.get(tax_code, "OTROS"))
    _add_child(tsch, _NS_CBC, "TaxTypeCode", "VAT")


def _remove_line_tax_total(root: etree._Element) -> None:
    line = root.xpath("//cac:InvoiceLine", namespaces={"cac": _NS_CAC})[0]
    tt = line.find("cac:TaxTotal", namespaces={"cac": _NS_CAC})
    if tt is not None:
        line.remove(tt)


# ---------------------------------------------------------------------------
# Mutadores por código
# ---------------------------------------------------------------------------

def _mut_3092(root: etree._Element) -> None:
    _add_global_allowance_charge(root, "true", "45", "10.00", "0.00")


def _mut_3093(root: etree._Element) -> None:
    _set_invoice_op(root, "2001")
    _add_payment_terms(root, "FormaPago", "Contado")


def _mut_3098(root: etree._Element) -> None:
    _set_invoice_op(root, "0201")


def _mut_3102(root: etree._Element) -> None:
    _set_text(root, "//cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent", "invalid")


def _mut_3103(root: etree._Element) -> None:
    _set_text(root, "//cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "999.00")


def _mut_3104(root: etree._Element) -> None:
    _add_tax_subtotal_to_line(root, "2000", "1000.00", "0.00", "0.00")


def _mut_3105(root: etree._Element) -> None:
    line = root.xpath("//cac:InvoiceLine", namespaces={"cac": _NS_CAC})[0]
    for ts in line.xpath("cac:TaxTotal/cac:TaxSubtotal", namespaces={"cac": _NS_CAC}):
        ts.getparent().remove(ts)


def _mut_3107(root: etree._Element) -> None:
    _set_invoice_op(root, "0200")
    _add_tax_subtotal_to_line(root, "9997", "100.00", "0.00")
def _mut_3108(root: etree._Element) -> None:
    _add_tax_subtotal_to_line(root, "2000", "1000.00", "1.00", "5.00")


def _mut_3109(root: etree._Element) -> None:
    _add_tax_subtotal_to_line(root, "9999", "1000.00", "1.00", "5.00")


def _mut_3110(root: etree._Element) -> None:
    _add_tax_subtotal_to_line(root, "9995", "100.00", "10.00")


def _mut_3111(root: etree._Element) -> None:
    _add_tax_subtotal_to_line(root, "9996", "100.00", "0.00", "18.00")
    root.xpath("//cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", namespaces={"cac": _NS_CAC, "cbc": _NS_CBC})[-1].text = "11"


def _mut_3114_line(root: etree._Element) -> None:
    line = root.xpath("//cac:InvoiceLine", namespaces={"cac": _NS_CAC})[0]
    ac = _add_child(line, _NS_CAC, "AllowanceCharge")
    _add_child(ac, _NS_CBC, "ChargeIndicator", "false")
    _add_child(ac, _NS_CBC, "AllowanceChargeReasonCode", "47")
    _add_child(ac, _NS_CBC, "Amount", "10.00", {"currencyID": "Catalog2.PEN"})


def _mut_3114_global(root: etree._Element) -> None:
    _add_global_allowance_charge(root, "false", "45", "10.00")


def _mut_3115(root: etree._Element) -> None:
    _set_invoice_op(root, "1002")
    _add_item_property(root, "3006", value_quantity="10.00", unit_code="NIU")


def _mut_3117(root: etree._Element) -> None:
    _set_invoice_op(root, "1004")
    _add_line_delivery_terms(root, "01", "100.00")


def _mut_3118(root: etree._Element) -> None:
    _set_invoice_op(root, "1004")
    _add_line_delivery_terms(root, "01", "100.00")
    _add_line_delivery_cargo(root)
    root.xpath("//cac:InvoiceLine/cac:Delivery/cac:DeliveryLocation/cac:Address/cbc:ID", namespaces={"cac": _NS_CAC, "cbc": _NS_CBC})[0].text = ""


def _mut_3119(root: etree._Element) -> None:
    _set_invoice_op(root, "1004")
    _add_line_delivery_terms(root, "01", "100.00")
    _add_line_delivery_cargo(root)
    node = root.xpath("//cac:InvoiceLine/cac:Delivery/cac:DeliveryLocation/cac:Address/cac:AddressLine", namespaces={"cac": _NS_CAC})[0]
    node.getparent().remove(node)


def _mut_3120(root: etree._Element) -> None:
    _set_invoice_op(root, "1004")
    _add_line_delivery_terms(root, "01", "100.00")
    _add_line_delivery_cargo(root)
    root.xpath("//cac:InvoiceLine/cac:Delivery/cac:Despatch/cbc:Instructions", namespaces={"cac": _NS_CAC, "cbc": _NS_CBC})[0].text = ""


def _mut_3122(root: etree._Element) -> None:
    _set_invoice_op(root, "1004")
    _add_line_delivery_cargo(root)
    _add_payment_terms(root, "Detraccion", "004", "100.00")
    _add_payment_means(root, "Detraccion", "00012345678")

def _mut_3123(root: etree._Element) -> None:
    _set_invoice_op(root, "1004")
    _add_line_delivery_terms(root, "01", "0.00")


def _mut_3124(root: etree._Element) -> None:
    _set_invoice_op(root, "1004")
    _add_line_delivery_terms(root, "01", "100.00")
    _add_line_delivery_terms(root, "01", "200.00")


def _mut_3125(root: etree._Element) -> None:
    _set_invoice_op(root, "1004")
    _add_line_delivery_terms(root, "01", "100.00")


def _mut_3126(root: etree._Element) -> None:
    _set_invoice_op(root, "1004")
    _add_line_delivery_terms(root, "01", "100.00")


def _mut_3127_no_terms(root: etree._Element) -> None:
    _set_invoice_op(root, "1002")


def _mut_3127_no_bbss(root: etree._Element) -> None:
    _set_invoice_op(root, "1002")
    _add_payment_terms(root, "Detraccion")


def _mut_3129(root: etree._Element) -> None:
    _set_invoice_op(root, "1002")
    _add_payment_terms(root, "Detraccion", "999")
    _add_payment_means(root, "Detraccion", "00012345678")


def _mut_3130(root: etree._Element) -> None:
    _set_invoice_op(root, "1002")
    _add_item_property(root, "3001")


def _mut_3131(root: etree._Element) -> None:
    _set_invoice_op(root, "1002")
    _add_item_property(root, "3001")
    _add_item_property(root, "3002")


def _mut_3132(root: etree._Element) -> None:
    _set_invoice_op(root, "1002")
    _add_item_property(root, "3001")
    _add_item_property(root, "3002")
    _add_item_property(root, "3003")


def _mut_3133(root: etree._Element) -> None:
    _set_invoice_op(root, "1002")
    _add_item_property(root, "3001")
    _add_item_property(root, "3002")
    _add_item_property(root, "3003")
    _add_item_property(root, "3004")


def _mut_3135(root: etree._Element) -> None:
    _set_invoice_op(root, "1002")
    _add_item_property(root, "3001")
    _add_item_property(root, "3002")
    _add_item_property(root, "3003")
    _add_item_property(root, "3004")
    _add_item_property(root, "3006")


def _mut_3136(root: etree._Element) -> None:
    _set_invoice_op(root, "0202")


def _mut_3137(root: etree._Element) -> None:
    _set_invoice_op(root, "0202")
    _add_item_property(root, "4009")


def _mut_3138(root: etree._Element) -> None:
    _set_invoice_op(root, "0202")
    _add_item_property(root, "4009")
    _add_item_property(root, "4008")


def _mut_3139(root: etree._Element) -> None:
    _set_invoice_op(root, "0202")
    _add_item_property(root, "4009")
    _add_item_property(root, "4008")
    _add_item_property(root, "4000")


def _mut_3140(root: etree._Element) -> None:
    _set_invoice_op(root, "0202")
    _add_item_property(root, "4009")
    _add_item_property(root, "4008")
    _add_item_property(root, "4000")
    _add_item_property(root, "4007")


def _mut_3141(root: etree._Element) -> None:
    _set_invoice_op(root, "0202")
    _add_item_property(root, "4009")
    _add_item_property(root, "4008")
    _add_item_property(root, "4000")
    _add_item_property(root, "4007")
    _add_item_property(root, "4001")


def _mut_3142(root: etree._Element) -> None:
    _set_invoice_op(root, "0202")
    for c in ("4009", "4008", "4000", "4007", "4001", "4002"):
        _add_item_property(root, c)


def _mut_3143(root: etree._Element) -> None:
    _set_invoice_op(root, "0202")
    for c in ("4009", "4008", "4000", "4007", "4001", "4002", "4003"):
        _add_item_property(root, c)


def _mut_3144(root: etree._Element) -> None:
    _set_invoice_op(root, "0202")
    for c in ("4009", "4008", "4000", "4007", "4001", "4002", "4003", "4004"):
        _add_item_property(root, c)


def _mut_3145(root: etree._Element) -> None:
    _set_invoice_op(root, "0202")
    for c in ("4009", "4008", "4000", "4007", "4001", "4002", "4003", "4004", "4006"):
        _add_item_property(root, c)


def _mut_3146(root: etree._Element) -> None:
    _add_item_property(root, "5001")


def _mut_3147(root: etree._Element) -> None:
    _add_item_property(root, "5000")


def _mut_3148(root: etree._Element) -> None:
    _add_item_property(root, "5000")
    _add_item_property(root, "5001")


def _mut_3149(root: etree._Element) -> None:
    _add_item_property(root, "5000")
    _add_item_property(root, "5001")
    _add_item_property(root, "5002")


def _mut_3151(root: etree._Element) -> None:
    _add_item_property(root, "7000")
    _add_item_property(root, "7002")


def _mut_3152(root: etree._Element) -> None:
    _add_item_property(root, "7000")


def _mut_3153(root: etree._Element) -> None:
    _add_item_property(root, "7000")
    _add_item_property(root, "7004")


def _mut_3154(root: etree._Element) -> None:
    _add_item_property(root, "7000")
    _add_item_property(root, "7002")
    _add_item_property(root, "7004")
    _add_item_property(root, "7005")


def _mut_3155(root: etree._Element) -> None:
    _add_item_property(root, "7000")
    _add_item_property(root, "7002")
    _add_item_property(root, "7004")
    _add_item_property(root, "7005")
    _add_item_property(root, "7006")


def _mut_3156(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")


def _mut_3158(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")
    party = root.xpath("//cac:AccountingSupplierParty/cac:Party", namespaces={"cac": _NS_CAC})[0]
    agent = _add_child(party, _NS_CAC, "AgentParty")
    pi = _add_child(agent, _NS_CAC, "PartyIdentification")
    _add_child(pi, _NS_CBC, "ID", "20100066603", {"schemeID": "1"})


def _mut_3159(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")


def _mut_3160(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")
    _add_item_property(root, "4040")


def _mut_3161(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")
    for c in ("4040", "4041"):
        _add_item_property(root, c)


def _mut_3162(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")
    for c in ("4040", "4041", "4049"):
        _add_item_property(root, c)


def _mut_3163(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")
    for c in ("4040", "4041", "4049", "4042"):
        _add_item_property(root, c)


def _mut_3164(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")
    for c in ("4040", "4041", "4049", "4042", "4043"):
        _add_item_property(root, c)


def _mut_3165(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")
    for c in ("4040", "4041", "4049", "4042", "4043", "4044"):
        _add_item_property(root, c)


def _mut_3166(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")
    for c in ("4040", "4041", "4049", "4042", "4043", "4044", "4045"):
        _add_item_property(root, c)


def _mut_3167(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")
    for c in ("4040", "4041", "4049", "4042", "4043", "4044", "4045", "4046"):
        _add_item_property(root, c)


def _mut_3168(root: etree._Element) -> None:
    _set_invoice_op(root, "0301")


def _mut_3169(root: etree._Element) -> None:
    _set_invoice_op(root, "0301")
    _add_item_property(root, "4030")


def _mut_3170(root: etree._Element) -> None:
    _set_invoice_op(root, "0301")
    for c in ("4030", "4031"):
        _add_item_property(root, c)


def _mut_3171(root: etree._Element) -> None:
    _set_invoice_op(root, "0301")
    for c in ("4030", "4031", "4032"):
        _add_item_property(root, c)


def _mut_3172(root: etree._Element) -> None:
    _add_item_property(root, "3060")


def _mut_3173(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")


def _mut_3175(root: etree._Element) -> None:
    _set_invoice_op(root, "0302")
    _add_payment_means(root, "Detraccion", "00012345678")


def _mut_3195(root: etree._Element) -> None:
    _remove_line_tax_total(root)


def _mut_3205(root: etree._Element) -> None:
    root.xpath("//cbc:InvoiceTypeCode", namespaces={"cbc": _NS_CBC})[0].attrib.pop("listID", None)


def _mut_3208(root: etree._Element) -> None:
    _set_invoice_op(root, "1002")
    _add_payment_terms(root, "Detraccion", "004", "100.00")
    _add_payment_means(root, "Detraccion", "00012345678")
    root.xpath("//cac:PaymentTerms/cbc:Amount", namespaces={"cac": _NS_CAC, "cbc": _NS_CBC})[-1].set("currencyID", "USD")


def _mut_3210(root: etree._Element) -> None:
    _add_tax_subtotal_to_line(root, "1000", "100.00", "18.00", "18.00", "01")


def _mut_3211(root: etree._Element) -> None:
    pp = _add_child(root, _NS_CAC, "PrepaidPayment")
    _add_child(pp, _NS_CBC, "PaidAmount", "100.00", {"currencyID": "Catalog2.PEN"})


def _mut_3212(root: etree._Element) -> None:
    _add_prepaid_payment(root, "P001", "100.00")
    _add_prepaid_payment(root, "P001", "200.00")


def _mut_3213(root: etree._Element) -> None:
    _add_prepaid_payment(root, "P001", "100.00")


def _mut_3214(root: etree._Element) -> None:
    _add_additional_document_reference(root, "02", "P001", "F001-1", "20100066603")


def _mut_3215(root: etree._Element) -> None:
    _add_additional_document_reference(root, "02", "P001", "F001-1", "20100066603")
    _add_additional_document_reference(root, "02", "P001", "F001-2", "20100066603")


def _mut_3216(root: etree._Element) -> None:
    adr = _add_child(root, _NS_CAC, "AdditionalDocumentReference")
    _add_child(adr, _NS_CBC, "ID", "F001-1")
    _add_child(adr, _NS_CBC, "DocumentTypeCode", "02")


def _mut_3217(root: etree._Element) -> None:
    adr = _add_child(root, _NS_CAC, "AdditionalDocumentReference")
    _add_child(adr, _NS_CBC, "ID", "F001-1")
    _add_child(adr, _NS_CBC, "DocumentTypeCode", "02")
    _add_child(adr, _NS_CBC, "DocumentStatusCode", "P001")


# Tests de Forma de Pago

def _mut_3244(root: etree._Element) -> None:
    for pt in root.xpath("//cac:PaymentTerms", namespaces={"cac": _NS_CAC}):
        pt.getparent().remove(pt)


def _mut_3245(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago")


def _mut_3246(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Invalido")


def _mut_3247(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Contado")
    _add_payment_terms(root, "FormaPago", "Credito")


def _mut_3248(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Contado")
    _add_payment_terms(root, "FormaPago", "Contado")


def _mut_3250(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Credito", "invalid")


def _mut_3251(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Credito")
    _add_payment_terms(root, "FormaPago", "Cuota001", "100.00", "2024-02-01")


def _mut_3252(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Contado")
    _add_payment_terms(root, "FormaPago", "Cuota001", "100.00", "2024-02-01")


def _mut_3253(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Credito")
    _add_payment_terms(root, "FormaPago", "Cuota001", "invalid", "2024-02-01")


def _mut_3254(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Credito")
    _add_payment_terms(root, "FormaPago", "Cuota001")


def _mut_3255(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Credito")
    _add_payment_terms(root, "FormaPago", "Cuota001", "100.00", "invalid")


def _mut_3256(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Credito")
    _add_payment_terms(root, "FormaPago", "Cuota001", "100.00")


def _mut_3265(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Credito", "9999.00")


def _mut_3266(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Credito")
    _add_payment_terms(root, "FormaPago", "Cuota001", "9999.00", "2024-02-01")


def _mut_3267(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Credito")
    _add_payment_terms(root, "FormaPago", "Cuota001", "100.00", "2024-01-01")


def _mut_3319(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Credito", "100.00")
    _add_payment_terms(root, "FormaPago", "Cuota001", "50.00", "2024-02-01")


@pytest.mark.parametrize(
    "code,mutator",
    [
        ("3092", _mut_3092),
        ("3093", _mut_3093),
        ("3098", _mut_3098),
        ("3102", _mut_3102),
        ("3103", _mut_3103),
        ("3104", _mut_3104),
        ("3105", _mut_3105),
        ("3107", _mut_3107),
        ("3108", _mut_3108),
        ("3109", _mut_3109),
        ("3110", _mut_3110),
        ("3111", _mut_3111),
        ("3114", _mut_3114_line),
        ("3114", _mut_3114_global),
        ("3115", _mut_3115),
        ("3117", _mut_3117),
        ("3118", _mut_3118),
        ("3119", _mut_3119),
        ("3120", _mut_3120),
        ("3122", _mut_3122),
        ("3123", _mut_3123),
        ("3124", _mut_3124),
        ("3125", _mut_3125),
        ("3126", _mut_3126),
        ("3127", _mut_3127_no_terms),
        ("3127", _mut_3127_no_bbss),
        ("3129", _mut_3129),
        ("3130", _mut_3130),
        ("3131", _mut_3131),
        ("3132", _mut_3132),
        ("3133", _mut_3133),
        ("3135", _mut_3135),
        ("3136", _mut_3136),
        ("3137", _mut_3137),
        ("3138", _mut_3138),
        ("3139", _mut_3139),
        ("3140", _mut_3140),
        ("3141", _mut_3141),
        ("3142", _mut_3142),
        ("3143", _mut_3143),
        ("3144", _mut_3144),
        ("3145", _mut_3145),
        ("3146", _mut_3146),
        ("3147", _mut_3147),
        ("3148", _mut_3148),
        ("3149", _mut_3149),
        ("3151", _mut_3151),
        ("3152", _mut_3152),
        ("3153", _mut_3153),
        ("3154", _mut_3154),
        ("3155", _mut_3155),
        ("3156", _mut_3156),
        ("3158", _mut_3158),
        ("3159", _mut_3159),
        ("3160", _mut_3160),
        ("3161", _mut_3161),
        ("3162", _mut_3162),
        ("3163", _mut_3163),
        ("3164", _mut_3164),
        ("3165", _mut_3165),
        ("3166", _mut_3166),
        ("3167", _mut_3167),
        ("3168", _mut_3168),
        ("3169", _mut_3169),
        ("3170", _mut_3170),
        ("3171", _mut_3171),
        ("3172", _mut_3172),
        ("3173", _mut_3173),
        ("3175", _mut_3175),
        ("3195", _mut_3195),
        ("3205", _mut_3205),
        ("3208", _mut_3208),
        ("3210", _mut_3210),
        ("3211", _mut_3211),
        ("3212", _mut_3212),
        ("3213", _mut_3213),
        ("3214", _mut_3214),
        ("3215", _mut_3215),
        ("3216", _mut_3216),
        ("3217", _mut_3217),
        ("3244", _mut_3244),
        ("3245", _mut_3245),
        ("3246", _mut_3246),
        ("3247", _mut_3247),
        ("3248", _mut_3248),
        ("3250", _mut_3250),
        ("3251", _mut_3251),
        ("3252", _mut_3252),
        ("3253", _mut_3253),
        ("3254", _mut_3254),
        ("3255", _mut_3255),
        ("3256", _mut_3256),
        ("3265", _mut_3265),
        ("3266", _mut_3266),
        ("3267", _mut_3267),
        ("3319", _mut_3319),
    ],
)
def test_invoice_extra2(code: str, mutator) -> None:
    root = _valid_invoice_root()
    mutator(root)
    errors: list = []
    validate_invoice_extra2(root, errors)
    codes = [e.code for e in errors]
    assert code in codes, f"Expected error {code} in {codes}"


def test_invoice_extra2_valid() -> None:
    root = _valid_invoice_root()
    errors: list = []
    validate_invoice_extra2(root, errors)
    # El documento base no debe disparar reglas de este batch.
    assert all(e.code not in {
        "3092", "3093", "3098", "3102", "3103", "3104", "3105", "3107",
        "3108", "3109", "3110", "3111", "3114", "3115", "3117", "3118",
        "3119", "3120", "3122", "3123", "3124", "3125", "3126", "3127",
        "3129", "3130", "3131", "3132", "3133", "3135", "3136", "3137",
        "3138", "3139", "3140", "3141", "3142", "3143", "3144", "3145",
        "3146", "3147", "3148", "3149", "3151", "3152", "3153", "3154",
        "3155", "3156", "3158", "3159", "3160", "3161", "3162", "3163",
        "3164", "3165", "3166", "3167", "3168", "3169", "3170", "3171",
        "3172", "3173", "3175", "3195", "3205", "3208", "3210", "3211",
        "3212", "3213", "3214", "3215", "3216", "3217", "3244", "3245",
        "3246", "3247", "3248", "3250", "3251", "3252", "3253", "3254",
        "3255", "3256", "3265", "3266", "3267", "3319",
    } for e in errors)
