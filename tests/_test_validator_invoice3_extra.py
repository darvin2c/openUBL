"""Tests para reglas SUNAT de Invoice - batch 3.

Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
https://cpe.sunat.gob.pe/guias-y-manuales
"""

from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest
from lxml import etree

from openubl.enricher import ContentEnricher
from openubl.models import (
    Catalog6,
    Catalog7,
    Cliente,
    DocumentoVentaDetalle,
    Invoice,
    Proveedor,
)
from openubl.renderer import render_invoice
from openubl.validators._extra_invoice3 import validate_invoice_extra3


_NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
_NS_CAC = "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}"
_NS_CBC = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"


def _valid_invoice_xml() -> str:
    """Invoice válido para las reglas de este batch (sin errores batch-3)."""
    inv = Invoice(
        serie="F001",
        numero=1,
        proveedor=Proveedor(ruc="20100066603", razonSocial="Softgreen S.A.C."),
        cliente=Cliente(
            nombre="Carlos Feria",
            numeroDocumentoIdentidad="12121212121",
            tipoDocumentoIdentidad=Catalog6.RUC,
        ),
        detalles=[
            DocumentoVentaDetalle(
                descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100")
            )
        ],
        fechaEmision=date(2024, 1, 1),
    )
    ContentEnricher().enrich(inv)
    xml = render_invoice(inv)
    return xml


def _root() -> etree._Element:
    return etree.fromstring(_valid_invoice_xml().encode("utf-8"))


def _set_text(root: etree._Element, xpath: str, value: str) -> None:
    root.xpath(xpath, namespaces=_NS)[0].text = value


def _set_attr(root: etree._Element, xpath: str, attr: str, value: str) -> None:
    root.xpath(xpath, namespaces=_NS)[0].set(attr, value)


def _remove(root: etree._Element, xpath: str) -> None:
    elem = root.xpath(xpath, namespaces=_NS)[0]
    elem.getparent().remove(elem)


def _add_child(parent: etree._Element, tag: str, text: str | None = None) -> etree._Element:
    ns = _NS_CBC if tag.startswith("cbc:") else _NS_CAC
    child = etree.SubElement(parent, ns + tag.split(":")[-1])
    if text is not None:
        child.text = text
    return child


def _add_payment_terms(
    root: etree._Element, pt_id: str, means: str, amount: str | None = None, due: str | None = None
) -> etree._Element:
    pt = etree.SubElement(root, _NS_CAC + "PaymentTerms")
    _add_child(pt, "cbc:ID", pt_id)
    _add_child(pt, "cbc:PaymentMeansID", means)
    if amount is not None:
        _add_child(pt, "cbc:Amount", amount)
    if due is not None:
        _add_child(pt, "cbc:PaymentDueDate", due)
    return pt


def _add_allowance_charge(
    root: etree._Element,
    indicator: str,
    reason: str,
    amount: str,
    base: str | None = None,
    factor: str | None = None,
) -> etree._Element:
    ac = etree.SubElement(root, _NS_CAC + "AllowanceCharge")
    _add_child(ac, "cbc:ChargeIndicator", indicator)
    _add_child(ac, "cbc:AllowanceChargeReasonCode", reason)
    if base is not None:
        _add_child(ac, "cbc:BaseAmount", base)
    if factor is not None:
        _add_child(ac, "cbc:MultiplierFactorNumeric", factor)
    _add_child(ac, "cbc:Amount", amount)
    return ac

def _set_or_add_total(root: etree._Element, tag: str, value: str) -> None:
    """Setea o crea un hijo cbc:tag bajo cac:LegalMonetaryTotal."""
    lmt = root.xpath("cac:LegalMonetaryTotal", namespaces=_NS)[0]
    elem = lmt.find(f"{{{_NS_CBC}}}{tag}")
    if elem is None:
        elem = etree.SubElement(lmt, _NS_CBC + tag)
    elem.text = value



def _line(root: etree._Element) -> etree._Element:
    return root.xpath("cac:InvoiceLine", namespaces=_NS)[0]


def _add_line_tax_subtotal(
    line: etree._Element,
    code: str,
    taxable: str,
    tax: str,
    percent: str | None = None,
    afectacion: str | None = None,
) -> None:
    tax_total = line.xpath("cac:TaxTotal", namespaces=_NS)[0]
    sub = etree.SubElement(tax_total, _NS_CAC + "TaxSubtotal")
    _add_child(sub, "cbc:TaxableAmount", taxable)
    _add_child(sub, "cbc:TaxAmount", tax)
    cat = etree.SubElement(sub, _NS_CAC + "TaxCategory")
    if percent is not None:
        _add_child(cat, "cbc:Percent", percent)
    if afectacion is not None:
        _add_child(cat, "cbc:TaxExemptionReasonCode", afectacion)
    scheme = etree.SubElement(cat, _NS_CAC + "TaxScheme")
    _add_child(scheme, "cbc:ID", code)
    _add_child(scheme, "cbc:Name", code)
    _add_child(scheme, "cbc:TaxTypeCode", "VAT")


def _global_tax_subtotal(root: etree._Element, code: str, taxable: str, tax: str) -> None:
    tax_total = root.xpath("cac:TaxTotal", namespaces=_NS)[0]
    sub = etree.SubElement(tax_total, _NS_CAC + "TaxSubtotal")
    _add_child(sub, "cbc:TaxableAmount", taxable)
    _add_child(sub, "cbc:TaxAmount", tax)
    cat = etree.SubElement(sub, _NS_CAC + "TaxCategory")
    _add_child(cat, "cbc:Percent", "18.00")
    scheme = etree.SubElement(cat, _NS_CAC + "TaxScheme")
    _add_child(scheme, "cbc:ID", code)
    _add_child(scheme, "cbc:Name", code)
    _add_child(scheme, "cbc:TaxTypeCode", "VAT")

# ---------------------------------------------------------------------------
# Mutators
# ---------------------------------------------------------------------------

def _m3220(root: etree._Element) -> None:
    pp = etree.SubElement(root, _NS_CAC + "PrepaidPayment")
    _add_child(pp, "cbc:ID", "001")
    _add_child(pp, "cbc:PaidAmount", "100.00")


def _m3223(root: etree._Element) -> None:
    line = _line(root)
    _add_line_tax_subtotal(line, "9995", "100.00", "0.00", afectacion="40")
    line_total = line.xpath("cac:TaxTotal/cbc:TaxAmount", namespaces=_NS)[0]
    line_total.text = "180.00"


def _m3224(root: etree._Element) -> None:
    _set_text(
        root,
        "cac:InvoiceLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceTypeCode",
        "02",
    )


def _m3233(root: etree._Element) -> None:
    _set_attr(root, "cbc:InvoiceTypeCode", "listID", "2001")
    _set_text(root, "cbc:Note", "2001")
    _add_payment_terms(root, "Percepcion", "")
    _add_allowance_charge(root, "true", "51", "10.00")


def _m3234(root: etree._Element) -> None:
    line = _line(root)
    _set_text(line, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "9996")
    _set_text(line, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "11")
    _set_text(
        line,
        "cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceTypeCode",
        "01",
    )


def _m3241(root: etree._Element) -> None:
    _set_attr(root, "cbc:InvoiceTypeCode", "listID", "2100")
    _set_text(root, "cbc:Note", "2100")


def _m3242(root: etree._Element) -> None:
    _set_attr(root, "cbc:InvoiceTypeCode", "listID", "2104")
    _set_text(root, "cbc:Note", "2104")


def _m3243(root: etree._Element) -> None:
    line = _line(root)
    item = line.xpath("cac:Item", namespaces=_NS)[0]
    prop = etree.SubElement(item, _NS_CAC + "AdditionalItemProperty")
    _add_child(prop, "cbc:NameCode", "7014")
    _add_child(prop, "cbc:Value", "x")


def _m3244(root: etree._Element) -> None:
    for pt in root.xpath("cac:PaymentTerms", namespaces=_NS):
        pt.getparent().remove(pt)


def _m3245(root: etree._Element) -> None:
    for pt in root.xpath("cac:PaymentTerms", namespaces=_NS):
        for m in pt.xpath("cbc:PaymentMeansID", namespaces=_NS):
            m.getparent().remove(m)


def _m3246(root: etree._Element) -> None:
    _set_text(
        root, "cac:PaymentTerms[cbc:ID='FormaPago']/cbc:PaymentMeansID", "Otro"
    )


def _m3247(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Credito")


def _m3248(root: etree._Element) -> None:
    _add_payment_terms(root, "FormaPago", "Contado")


def _m3249(root: etree._Element) -> None:
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Credito", amount="100.00")


def _m3250(root: etree._Element) -> None:
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Credito", amount="-10.00")


def _m3251(root: etree._Element) -> None:
    _remove(root, "cac:PaymentTerms")
    pt = _add_payment_terms(root, "FormaPago", "Credito")


def _m3252(root: etree._Element) -> None:
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Cuota001", amount="50.00")


def _m3253(root: etree._Element) -> None:
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Credito", amount="100.00")
    _add_payment_terms(root, "FormaPago", "Cuota001", amount="-5.00")


def _m3254(root: etree._Element) -> None:
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Credito", amount="100.00")
    _add_payment_terms(root, "FormaPago", "Cuota001")


def _m3255(root: etree._Element) -> None:
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Credito", amount="100.00")
    _add_payment_terms(root, "FormaPago", "Cuota001", amount="50.00", due="2024/01/10")


def _m3256(root: etree._Element) -> None:
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Credito", amount="100.00")
    _add_payment_terms(root, "FormaPago", "Cuota001", amount="50.00")


def _m3262(root: etree._Element) -> None:
    _set_attr(
        root,
        "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
        "schemeID",
        "Catalog6.DNI",
    )
    _add_allowance_charge(root, "false", "62", "10.00", base="100.00", factor="0.10")


def _m3263(root: etree._Element) -> None:
    _add_allowance_charge(root, "false", "62", "5.00", base="100.00", factor="0.10")


def _m3264(root: etree._Element) -> None:
    _add_allowance_charge(root, "false", "62", "20.00", base="200.00", factor="0.10")


def _m3265(root: etree._Element) -> None:
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Credito", amount="200.00")


def _m3266(root: etree._Element) -> None:
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Credito", amount="100.00")
    _add_payment_terms(root, "FormaPago", "Cuota001", amount="200.00", due="2024-01-10")


def _m3267(root: etree._Element) -> None:
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Credito", amount="100.00")
    _add_payment_terms(
        root, "FormaPago", "Cuota001", amount="50.00", due="2024-01-01"
    )


def _m3270(root: etree._Element) -> None:
    _set_text(
        root,
        "cac:InvoiceLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount",
        "200.00",
    )


def _m3271(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cbc:LineExtensionAmount", "50.00")


def _m3272(root: etree._Element) -> None:
    line = _line(root)
    _add_line_tax_subtotal(line, "2000", "100.00", "10.00")
    line_total = line.xpath("cac:TaxTotal/cbc:TaxAmount", namespaces=_NS)[0]
    line_total.text = "190.00"


def _m3273(root: etree._Element) -> None:
    _global_tax_subtotal(root, "9995", "999.00", "0.00")


def _m3274(root: etree._Element) -> None:
    _global_tax_subtotal(root, "9998", "999.00", "0.00")


def _m3275(root: etree._Element) -> None:
    _global_tax_subtotal(root, "9997", "999.00", "0.00")


def _m3276(root: etree._Element) -> None:
    _global_tax_subtotal(root, "9996", "999.00", "0.00")


def _m3277(root: etree._Element) -> None:
    _set_text(root, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "999.00")


def _m3278(root: etree._Element) -> None:
    _set_text(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount", "50.00")


def _m3279(root: etree._Element) -> None:
    _set_text(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", "50.00")


def _m3280(root: etree._Element) -> None:
    _set_text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount", "50.00")


def _m3282(root: etree._Element) -> None:
    _add_allowance_charge(root, "false", "04", "10.00")


def _m3287(root: etree._Element) -> None:
    _set_or_add_total(root, "PrepaidAmount", "100.00")


def _m3288(root: etree._Element) -> None:
    _remove(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount")


def _m3290(root: etree._Element) -> None:
    line = _line(root)
    _add_allowance_charge(line, "false", "01", "5.00", base="100.00", factor="0.10")


def _m3291(root: etree._Element) -> None:
    _set_text(root, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "50.00")


def _m3292(root: etree._Element) -> None:
    line = _line(root)
    _add_line_tax_subtotal(line, "9999", "0.00", "0.00")
    line.xpath("cac:TaxTotal/cbc:TaxAmount", namespaces=_NS)[0].text = "999.00"


def _m3293(root: etree._Element) -> None:
    _global_tax_subtotal(root, "1016", "999.00", "0.00")


def _m3294(root: etree._Element) -> None:
    _set_text(root, "cac:TaxTotal/cbc:TaxAmount", "999.00")


def _m3295(root: etree._Element) -> None:
    _global_tax_subtotal(root, "1016", "0.00", "50.00")


def _m3296(root: etree._Element) -> None:
    _global_tax_subtotal(root, "2000", "100.00", "0.00")


def _m3297(root: etree._Element) -> None:
    _global_tax_subtotal(root, "9999", "100.00", "0.00")


def _m3298(root: etree._Element) -> None:
    _global_tax_subtotal(root, "2000", "0.00", "50.00")


def _m3299(root: etree._Element) -> None:
    _global_tax_subtotal(root, "9999", "0.00", "50.00")


def _m3300(root: etree._Element) -> None:
    line = _line(root)
    _add_allowance_charge(line, "false", "01", "10.00")
    _set_or_add_total(root, "AllowanceTotalAmount", "5.00")


def _m3301(root: etree._Element) -> None:
    line = _line(root)
    _add_allowance_charge(line, "true", "48", "10.00")
    _set_or_add_total(root, "ChargeTotalAmount", "5.00")


def _m3302(root: etree._Element) -> None:
    _global_tax_subtotal(root, "9996", "0.00", "18.00")


def _m3303(root: etree._Element) -> None:
    lmt = root.xpath("cac:LegalMonetaryTotal", namespaces=_NS)[0]
    elem = etree.SubElement(lmt, _NS_CBC + "PayableRoundingAmount")
    elem.text = "1.50"


def _m3305(root: etree._Element) -> None:
    _remove(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount")


def _m3306(root: etree._Element) -> None:
    _global_tax_subtotal(root, "7152", "0.00", "1.50")



def _m3307(root: etree._Element) -> None:
    _add_allowance_charge(root, "true", "49", "5.00", base="100.00", factor="0.10")


def _m3308(root: etree._Element) -> None:
    _add_allowance_charge(root, "true", "51", "10.00", base="10.00")


def _m3309(root: etree._Element) -> None:
    _set_attr(root, "cbc:InvoiceTypeCode", "listID", "2001")
    _set_text(root, "cbc:Note", "2001")


def _m3310(root: etree._Element) -> None:
    _set_attr(root, "cbc:InvoiceTypeCode", "listID", "2001")
    _set_text(root, "cbc:Note", "2001")
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Contado")
    _add_payment_terms(root, "Percepcion", "")


def _m3311(root: etree._Element) -> None:
    _set_attr(root, "cbc:InvoiceTypeCode", "listID", "2001")
    _set_text(root, "cbc:Note", "2001")
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Contado")
    _add_payment_terms(root, "Percepcion", "", amount="-10.00")


def _m3318(root: etree._Element) -> None:
    _add_allowance_charge(root, "false", "63", "10.00")


def _m3319(root: etree._Element) -> None:
    _remove(root, "cac:PaymentTerms")
    _add_payment_terms(root, "FormaPago", "Credito", amount="100.00")
    _add_payment_terms(root, "FormaPago", "Cuota001", amount="40.00", due="2024-01-10")
    _add_payment_terms(root, "FormaPago", "Cuota002", amount="30.00", due="2024-02-10")


def _m3330(root: etree._Element) -> None:
    _set_attr(root, "cbc:InvoiceTypeCode", "listID", "2001")
    _set_text(root, "cbc:Note", "2001")
    # Cambiar forma de pago a Credito para una operación 2001 con percepción
    for pt in root.xpath("cac:PaymentTerms", namespaces=_NS):
        id_elem = pt.find("{" + _NS_CBC.strip("{}") + "}ID")
        if id_elem is not None and id_elem.text == "FormaPago":
            means = pt.find("{" + _NS_CBC.strip("{}") + "}PaymentMeansID")
            if means is not None:
                means.text = "Credito"
            break
    # Agregar cargo de percepción (reason 51)
    _add_allowance_charge(root, "true", "51", "10.00", base="100.00", factor="0.10")


def _m3461(root: etree._Element) -> None:
    pt = root.xpath("cac:PaymentTerms", namespaces=_NS)[0]
    _add_child(pt, "cbc:PaymentMeansID", "Contado")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_invoice_extra3_default_is_valid():
    errors = validate_invoice_extra3(_root(), [])
    assert [e.code for e in errors] == []


@pytest.mark.parametrize(
    "code,mutator",
    [
        ("3220", _m3220),
        ("3223", _m3223),
        ("3224", _m3224),
        ("3233", _m3233),
        ("3234", _m3234),
        ("3241", _m3241),
        ("3242", _m3242),
        ("3243", _m3243),
        ("3244", _m3244),
        ("3245", _m3245),
        ("3246", _m3246),
        ("3247", _m3247),
        ("3248", _m3248),
        ("3249", _m3249),
        ("3250", _m3250),
        ("3251", _m3251),
        ("3252", _m3252),
        ("3253", _m3253),
        ("3254", _m3254),
        ("3255", _m3255),
        ("3256", _m3256),
        ("3262", _m3262),
        ("3263", _m3263),
        ("3264", _m3264),
        ("3265", _m3265),
        ("3266", _m3266),
        ("3267", _m3267),
        ("3270", _m3270),
        ("3271", _m3271),
        ("3272", _m3272),
        ("3273", _m3273),
        ("3274", _m3274),
        ("3275", _m3275),
        ("3276", _m3276),
        ("3277", _m3277),
        ("3278", _m3278),
        ("3279", _m3279),
        ("3280", _m3280),
        ("3282", _m3282),
        ("3287", _m3287),
        ("3288", _m3288),
        ("3290", _m3290),
        ("3291", _m3291),
        ("3292", _m3292),
        ("3293", _m3293),
        ("3294", _m3294),
        ("3295", _m3295),
        ("3296", _m3296),
        ("3297", _m3297),
        ("3298", _m3298),
        ("3299", _m3299),
        ("3300", _m3300),
        ("3301", _m3301),
        ("3302", _m3302),
        ("3303", _m3303),
        ("3305", _m3305),
        ("3306", _m3306),
        ("3307", _m3307),
        ("3308", _m3308),
        ("3309", _m3309),
        ("3310", _m3310),
        ("3311", _m3311),
        ("3318", _m3318),
        ("3319", _m3319),
        ("3330", _m3330),
        ("3461", _m3461),
    ],
)
def test_invoice_extra3(code: str, mutator) -> None:
    root = _root()
    mutator(root)
    errors = validate_invoice_extra3(root, [])
    codes = [e.code for e in errors]
    assert code in codes, f"Expected error {code} in {codes}"
