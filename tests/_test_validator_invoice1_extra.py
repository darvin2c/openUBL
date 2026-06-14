"""Tests parametrizados para validaciones SUNAT de Invoice - lote 1.

Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
https://cpe.sunat.gob.pe/guias-y-manuales
"""

from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest
from lxml import etree

from openubl.models import Invoice, Proveedor, Cliente, DocumentoVentaDetalle
from openubl.enricher import ContentEnricher
from openubl.renderer import render_invoice
from openubl.validators._extra_invoice1 import validate_invoice_extra1
from openubl.validators.common import NS_INVOICE


_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"


def _q(uri: str, tag: str) -> str:
    return f"{{{uri}}}{tag}"


def _find(root: etree._Element, xpath: str) -> etree._Element | None:
    return root.find(xpath, namespaces=NS_INVOICE)


def _set_text(root: etree._Element, xpath: str, value: str) -> None:
    elem = _find(root, xpath)
    if elem is not None:
        elem.text = value


def _remove(root: etree._Element, xpath: str) -> None:
    elem = _find(root, xpath)
    if elem is not None:
        elem.getparent().remove(elem)


def _remove_attr(root: etree._Element, xpath: str, attr: str) -> None:
    elem = _find(root, xpath)
    if elem is not None and attr in elem.attrib:
        del elem.attrib[attr]


def _add_child(parent: etree._Element, uri: str, tag: str, text: str | None = None, attrs: dict | None = None) -> etree._Element:
    child = etree.SubElement(parent, _q(uri, tag))
    if text is not None:
        child.text = text
    if attrs:
        for k, v in attrs.items():
            child.set(k, v)
    return child


def _valid_invoice_root() -> etree._Element:
    doc = Invoice(
        serie="F001",
        numero=1,
        proveedor=Proveedor(ruc="20100066603", razonSocial="Softgreen S.A.C."),
        cliente=Cliente(nombre="Carlos Feria", numeroDocumentoIdentidad="12121212121", tipoDocumentoIdentidad="6"),
        detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("10"), precio=Decimal("100"))],
        fechaEmision=date(2024, 1, 1),
    )
    ContentEnricher().enrich(doc)
    xml = render_invoice(doc)
    return etree.fromstring(xml.encode("utf-8"))


@pytest.fixture
def root():
    return _valid_invoice_root()


# ---------------------------------------------------------------------------
# Mutadores por código SUNAT
# ---------------------------------------------------------------------------


def _m1004(root: etree._Element) -> None:
    _remove(root, "cbc:InvoiceTypeCode")


def _m2014(root: etree._Element) -> None:
    _remove(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID")


def _m2017(root: etree._Element) -> None:
    elem = _find(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID")
    if elem is not None:
        elem.set("schemeID", "6")
        elem.text = "12345"


def _m2023(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cbc:ID", "0")


def _m2024(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cbc:InvoicedQuantity", "0")


def _m2025(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cbc:InvoicedQuantity", "1.12345678901")


def _m2026(root: etree._Element) -> None:
    _remove(root, "cac:InvoiceLine/cac:Item/cbc:Description")


def _m2027(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cac:Item/cbc:Description", "x" * 501)


def _m2028(root: etree._Element) -> None:
    _remove(root, "cac:InvoiceLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount")


def _m2031(root: etree._Element) -> None:
    _set_text(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount", "0")


def _m2033(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0")


def _m2037(root: etree._Element) -> None:
    _remove(root, "cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID")


def _m2048(root: etree._Element) -> None:
    _set_text(root, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0")


def _m2052(root: etree._Element) -> None:
    _remove(root, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode")


def _m2054(root: etree._Element) -> None:
    _remove(root, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name")


def _m2064(root: etree._Element) -> None:
    total = _find(root, "cac:LegalMonetaryTotal")
    if total is not None:
        _add_child(total, _CBC, "ChargeTotalAmount", "0.00", {"currencyID": "PEN"})


def _m2065(root: etree._Element) -> None:
    total = _find(root, "cac:LegalMonetaryTotal")
    if total is not None:
        _add_child(total, _CBC, "AllowanceTotalAmount", "0.00", {"currencyID": "PEN"})


def _m2068(root: etree._Element) -> None:
    _remove(root, "cac:InvoiceLine/cac:Price/cbc:PriceAmount")


def _m2108(root: etree._Element) -> None:
    # Fuera de alcance: no se puede validar localmente.
    _set_text(root, "cbc:IssueDate", "1900-01-01")


def _m2367(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount", "0")


def _m2369(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cac:Price/cbc:PriceAmount", "0")


def _m2370(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cbc:LineExtensionAmount", "0")


def _m2371(root: etree._Element) -> None:
    _remove(root, "cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode")


def _m2373(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is None:
        return
    tt = _add_child(line, _CAC, "TaxTotal")
    _add_child(tt, _CBC, "TaxAmount", "10.00", {"currencyID": "PEN"})
    ts = _add_child(tt, _CAC, "TaxSubtotal")
    _add_child(ts, _CBC, "TaxableAmount", "100.00", {"currencyID": "PEN"})
    _add_child(ts, _CBC, "TaxAmount", "10.00", {"currencyID": "PEN"})
    tc = _add_child(ts, _CAC, "TaxCategory")
    _add_child(tc, _CBC, "Percent", "10.00")
    tsc = _add_child(tc, _CAC, "TaxScheme")
    _add_child(tsc, _CBC, "ID", "2000")
    _add_child(tsc, _CBC, "Name", "ISC")
    _add_child(tsc, _CBC, "TaxTypeCode", "EXC")


def _m2409(root: etree._Element) -> None:
    pricing = _find(root, "cac:InvoiceLine/cac:PricingReference")
    if pricing is not None:
        existing = _find(pricing, "cac:AlternativeConditionPrice")
        if existing is not None:
            pricing.append(deepcopy(existing))


def _m2416(root: etree._Element) -> None:
    note = _find(root, "cbc:Note")
    if note is not None:
        note.set("languageLocaleID", "1002")
    for ts in root.findall("cac:TaxTotal/cac:TaxSubtotal", namespaces=NS_INVOICE):
        id_elem = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID")
        if id_elem is not None and id_elem.text == "1000":
            id_elem.text = "9996"
            name = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name")
            if name is not None:
                name.text = "GRATUITA"
            taxable = _find(ts, "cbc:TaxableAmount")
            if taxable is not None:
                taxable.text = "0.00"


def _m2503(root: etree._Element) -> None:
    pp = _add_child(root, _CAC, "PrepaidPayment")
    _add_child(pp, _CBC, "PaidAmount", "0.00", {"currencyID": "PEN"})


def _m2509(root: etree._Element) -> None:
    pp = _add_child(root, _CAC, "PrepaidPayment")
    _add_child(pp, _CBC, "PaidAmount", "100.00", {"currencyID": "PEN"})
    total = _find(root, "cac:LegalMonetaryTotal")
    if total is not None:
        _add_child(total, _CBC, "PrepaidAmount", "50.00", {"currencyID": "PEN"})


def _m2521(root: etree._Element) -> None:
    # Fuera de alcance parcial; el mutador no genera error.
    pp = _add_child(root, _CAC, "PrepaidPayment")
    _add_child(pp, _CBC, "ID", "P001")
    _add_child(pp, _CBC, "PaidAmount", "100.00", {"currencyID": "PEN"})


def _m2638(root: etree._Element) -> None:
    # Línea con tributo 9995; el total global sigue siendo 1000
    line = _find(root, "cac:InvoiceLine")
    if line is None:
        return
    for ts in line.findall("cac:TaxTotal/cac:TaxSubtotal", namespaces=NS_INVOICE):
        id_elem = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID")
        if id_elem is not None and id_elem.text == "1000":
            id_elem.text = "9995"
            name = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name")
            if name is not None:
                name.text = "EXP"


def _m2640(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is None:
        return
    for ts in line.findall("cac:TaxTotal/cac:TaxSubtotal", namespaces=NS_INVOICE):
        id_elem = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID")
        if id_elem is not None and id_elem.text == "1000":
            id_elem.text = "9996"
            name = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name")
            if name is not None:
                name.text = "GRATUITA"
    _set_text(root, "cac:InvoiceLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount", "0")


def _m2641(root: etree._Element) -> None:
    # Total gratuito 0 con línea gratuita y precio 02 > 0
    line = _find(root, "cac:InvoiceLine")
    if line is not None:
        for ts in line.findall("cac:TaxTotal/cac:TaxSubtotal", namespaces=NS_INVOICE):
            id_elem = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID")
            if id_elem is not None and id_elem.text == "1000":
                id_elem.text = "9996"
                name = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name")
                if name is not None:
                    name.text = "GRATUITA"
    price_type = _find(root, "cac:InvoiceLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceTypeCode")
    if price_type is not None:
        price_type.text = "02"
    for ts in root.findall("cac:TaxTotal/cac:TaxSubtotal", namespaces=NS_INVOICE):
        id_elem = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID")
        if id_elem is not None and id_elem.text == "1000":
            id_elem.text = "9996"
            name = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name")
            if name is not None:
                name.text = "GRATUITA"
            taxable = _find(ts, "cbc:TaxableAmount")
            if taxable is not None:
                taxable.text = "0.00"


def _m2642(root: etree._Element) -> None:
    _set_text(root, "cbc:InvoiceTypeCode", "0200")
    _set_text(root, "cbc:Note", "0200")
    _set_text(root, "cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "10")


def _m2644(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is None:
        return
    new_line = deepcopy(line)
    _set_text(new_line, "cbc:ID", "2")
    _set_text(new_line, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "17")
    root.append(new_line)


def _m2650(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is None:
        return
    _set_text(line, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "17")
    id_elem = _find(line, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID")
    if id_elem is not None:
        id_elem.text = "1016"
    new_line = deepcopy(line)
    _set_text(new_line, "cbc:ID", "2")
    _set_text(new_line, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "10")
    id_elem2 = _find(new_line, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID")
    if id_elem2 is not None:
        id_elem2.text = "2000"
    root.append(new_line)


def _m2752(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is not None:
        root.append(deepcopy(line))


def _m2797(root: etree._Element) -> None:
    _set_text(root, "cbc:DocumentCurrencyCode", "PEN")
    ac = _add_child(root, _CAC, "AllowanceCharge")
    _add_child(ac, _CBC, "ChargeIndicator", "true")
    _add_child(ac, _CBC, "AllowanceChargeReasonCode", "51")
    _add_child(ac, _CBC, "Amount", "999999.00", {"currencyID": "PEN"})


def _m2801(root: etree._Element) -> None:
    elem = _find(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID")
    if elem is not None:
        elem.set("schemeID", "1")
        elem.text = "1234567"


def _m2802(root: etree._Element) -> None:
    elem = _find(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID")
    if elem is not None:
        elem.set("schemeID", "4")
        elem.text = "abc def"


def _m2883(root: etree._Element) -> None:
    _remove_attr(root, "cac:InvoiceLine/cbc:InvoicedQuantity", "unitCode")


def _m2892(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is None:
        return
    ts = _find(line, "cac:TaxTotal/cac:TaxSubtotal")
    if ts is not None:
        _add_child(ts, _CBC, "BaseUnitMeasure", "abcdef")


def _m2898(root: etree._Element) -> None:
    _set_text(root, "cbc:InvoiceTypeCode", "2104")
    _set_text(root, "cbc:Note", "2104")


def _m2899(root: etree._Element) -> None:
    _set_text(root, "cbc:InvoiceTypeCode", "2104")
    _set_text(root, "cbc:Note", "2104")


def _m2936(root: etree._Element) -> None:
    elem = _find(root, "cac:InvoiceLine/cbc:InvoicedQuantity")
    if elem is not None:
        elem.set("unitCode", "XYZ")


def _m2949(root: etree._Element) -> None:
    _set_text(root, "cbc:IssueDate", "2019-01-01")
    tax_total = _find(root, "cac:TaxTotal")
    if tax_total is not None:
        ts = _add_child(tax_total, _CAC, "TaxSubtotal")
        _add_child(ts, _CBC, "TaxableAmount", "1.00", {"currencyID": "PEN"})
        _add_child(ts, _CBC, "TaxAmount", "0.50", {"currencyID": "PEN"})
        tc = _add_child(ts, _CAC, "TaxCategory")
        tsc = _add_child(tc, _CAC, "TaxScheme")
        _add_child(tsc, _CBC, "ID", "7152")
        _add_child(tsc, _CBC, "Name", "ICBPER")
        _add_child(tsc, _CBC, "TaxTypeCode", "OTH")


def _m2955(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is not None:
        ac = _add_child(line, _CAC, "AllowanceCharge")
        _add_child(ac, _CBC, "ChargeIndicator", "false")
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", "00")
        _add_child(ac, _CBC, "Amount", "0.00", {"currencyID": "PEN"})


def _m2956(root: etree._Element) -> None:
    _remove(root, "cac:TaxTotal")


def _m2968(root: etree._Element) -> None:
    ac = _add_child(root, _CAC, "AllowanceCharge")
    _add_child(ac, _CBC, "ChargeIndicator", "true")
    _add_child(ac, _CBC, "AllowanceChargeReasonCode", "45")
    _add_child(ac, _CBC, "Amount", "0.00", {"currencyID": "PEN"})


def _m2992(root: etree._Element) -> None:
    _remove(root, "cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent")


def _m2993(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is None:
        return
    for ts in line.findall("cac:TaxTotal/cac:TaxSubtotal", namespaces=NS_INVOICE):
        id_elem = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID")
        if id_elem is not None and id_elem.text == "1000":
            id_elem.text = "9996"
            name = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name")
            if name is not None:
                name.text = "GRATUITA"
            exempt = _find(ts, "cac:TaxCategory/cbc:TaxExemptionReasonCode")
            if exempt is not None:
                exempt.text = "11"
            percent = _find(ts, "cac:TaxCategory/cbc:Percent")
            if percent is not None:
                percent.text = "0"
    # Agregar total global 9996 para evitar 2638
    tax_total = _find(root, "cac:TaxTotal")
    if tax_total is not None:
        ts = _add_child(tax_total, _CAC, "TaxSubtotal")
        _add_child(ts, _CBC, "TaxableAmount", "1000.00", {"currencyID": "PEN"})
        _add_child(ts, _CBC, "TaxAmount", "0.00", {"currencyID": "PEN"})
        tc = _add_child(ts, _CAC, "TaxCategory")
        _add_child(tc, _CBC, "Percent", "0")
        _add_child(tc, _CBC, "TaxExemptionReasonCode", "11")
        tsc = _add_child(tc, _CAC, "TaxScheme")
        _add_child(tsc, _CBC, "ID", "9996")
        _add_child(tsc, _CBC, "Name", "GRATUITA")
        _add_child(tsc, _CBC, "TaxTypeCode", "FRE")


def _m2996(root: etree._Element) -> None:
    _remove(root, "cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name")


def _m2999(root: etree._Element) -> None:
    _set_text(root, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "0")


def _m3000(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is None:
        return
    for ts in line.findall("cac:TaxTotal/cac:TaxSubtotal", namespaces=NS_INVOICE):
        id_elem = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID")
        if id_elem is not None and id_elem.text == "1000":
            id_elem.text = "9995"
            name = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name")
            if name is not None:
                name.text = "EXP"


def _m3003(root: etree._Element) -> None:
    _remove(root, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount")


def _m3006(root: etree._Element) -> None:
    _set_text(root, "cbc:Note", "x" * 201)


def _m3014(root: etree._Element) -> None:
    note = _find(root, "cbc:Note")
    if note is not None:
        note.set("languageLocaleID", "1000")
        note2 = deepcopy(note)
        root.insert(list(root).index(note) + 1, note2)


def _m3016(root: etree._Element) -> None:
    ac = _add_child(root, _CAC, "AllowanceCharge")
    _add_child(ac, _CBC, "ChargeIndicator", "true")
    _add_child(ac, _CBC, "AllowanceChargeReasonCode", "45")
    _add_child(ac, _CBC, "BaseAmount", "0.00", {"currencyID": "PEN"})
    _add_child(ac, _CBC, "Amount", "10.00", {"currencyID": "PEN"})


def _m3019(root: etree._Element) -> None:
    _set_text(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", "0")


def _m3020(root: etree._Element) -> None:
    _set_text(root, "cac:TaxTotal/cbc:TaxAmount", "0")


def _m3021(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cac:TaxTotal/cbc:TaxAmount", "0")


def _m3024(root: etree._Element) -> None:
    tax_total = _find(root, "cac:TaxTotal")
    if tax_total is not None:
        root.insert(list(root).index(tax_total) + 1, deepcopy(tax_total))


def _m3025(root: etree._Element) -> None:
    ac = _add_child(root, _CAC, "AllowanceCharge")
    _add_child(ac, _CBC, "ChargeIndicator", "true")
    _add_child(ac, _CBC, "AllowanceChargeReasonCode", "45")
    _add_child(ac, _CBC, "MultiplierFactorNumeric", "abc")
    _add_child(ac, _CBC, "Amount", "10.00", {"currencyID": "PEN"})


def _m3026(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is not None:
        tax_total = _find(line, "cac:TaxTotal")
        if tax_total is not None:
            line.insert(list(line).index(tax_total) + 1, deepcopy(tax_total))


def _m3030(root: etree._Element) -> None:
    _remove(root, "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cac:RegistrationAddress/cbc:AddressTypeCode")


def _m3031(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "0")


def _m3034(root: etree._Element) -> None:
    _set_text(root, "cbc:InvoiceTypeCode", "1001")
    _set_text(root, "cbc:Note", "1001")


def _m3035(root: etree._Element) -> None:
    pt = _add_child(root, _CAC, "PaymentTerms")
    _add_child(pt, _CBC, "ID", "Detraccion")


def _m3037(root: etree._Element) -> None:
    pt = _add_child(root, _CAC, "PaymentTerms")
    _add_child(pt, _CBC, "ID", "Detraccion")
    _add_child(pt, _CBC, "Amount", "0.00", {"currencyID": "PEN"})


def _m3050(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is None:
        return
    ts = _find(line, "cac:TaxTotal/cac:TaxSubtotal")
    if ts is not None:
        id_elem = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID")
        if id_elem is not None:
            id_elem.text = "2000"
            name = _find(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name")
            if name is not None:
                name.text = "ISC"
        tc = _find(ts, "cac:TaxCategory")
        if tc is not None:
            _add_child(tc, _CBC, "TaxExemptionReasonCode", "10")


def _m3052(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is not None:
        ac = _add_child(line, _CAC, "AllowanceCharge")
        _add_child(ac, _CBC, "ChargeIndicator", "false")
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", "00")
        _add_child(ac, _CBC, "MultiplierFactorNumeric", "abc")
        _add_child(ac, _CBC, "Amount", "10.00", {"currencyID": "PEN"})


def _m3053(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is not None:
        ac = _add_child(line, _CAC, "AllowanceCharge")
        _add_child(ac, _CBC, "ChargeIndicator", "false")
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", "00")
        _add_child(ac, _CBC, "BaseAmount", "0.00", {"currencyID": "PEN"})
        _add_child(ac, _CBC, "Amount", "10.00", {"currencyID": "PEN"})


def _m3059(root: etree._Element) -> None:
    _remove(root, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID")


def _m3063(root: etree._Element) -> None:
    _set_text(root, "cbc:InvoiceTypeCode", "1002")
    _set_text(root, "cbc:Note", "1002")


def _m3065(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is None:
        return
    item = _find(line, "cac:Item")
    if item is None:
        return
    prop = _add_child(item, _CAC, "AdditionalItemProperty")
    _add_child(prop, _CBC, "NameCode", "3059")


def _m3067(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is None:
        return
    tax_total = _find(line, "cac:TaxTotal")
    if tax_total is not None:
        ts = _find(tax_total, "cac:TaxSubtotal")
        if ts is not None:
            tax_total.append(deepcopy(ts))


def _m3068(root: etree._Element) -> None:
    tax_total = _find(root, "cac:TaxTotal")
    if tax_total is not None:
        ts = _find(tax_total, "cac:TaxSubtotal")
        if ts is not None:
            tax_total.append(deepcopy(ts))


def _m3072(root: etree._Element) -> None:
    ac = _add_child(root, _CAC, "AllowanceCharge")
    _add_child(ac, _CBC, "ChargeIndicator", "true")
    _add_child(ac, _CBC, "Amount", "10.00", {"currencyID": "PEN"})


def _m3073(root: etree._Element) -> None:
    line = _find(root, "cac:InvoiceLine")
    if line is not None:
        ac = _add_child(line, _CAC, "AllowanceCharge")
        _add_child(ac, _CBC, "ChargeIndicator", "false")
        _add_child(ac, _CBC, "Amount", "10.00", {"currencyID": "PEN"})


def _m3074(root: etree._Element) -> None:
    ac = _add_child(root, _CAC, "AllowanceCharge")
    _add_child(ac, _CBC, "ChargeIndicator", "true")
    _add_child(ac, _CBC, "AllowanceChargeReasonCode", "45")
    _add_child(ac, _CBC, "Amount", "0.00", {"currencyID": "PEN"})


def _m3089(root: etree._Element) -> None:
    party = _find(root, "cac:AccountingSupplierParty/cac:Party")
    if party is not None:
        pi = _find(party, "cac:PartyIdentification")
        if pi is not None:
            party.insert(list(party).index(pi) + 1, deepcopy(pi))


def _m3090(root: etree._Element) -> None:
    party = _find(root, "cac:AccountingCustomerParty/cac:Party")
    if party is not None:
        pi = _find(party, "cac:PartyIdentification")
        if pi is not None:
            party.insert(list(party).index(pi) + 1, deepcopy(pi))


MUTATORS = [
    ("1004", _m1004),
    ("2014", _m2014),
    ("2017", _m2017),
    ("2023", _m2023),
    ("2024", _m2024),
    ("2025", _m2025),
    ("2026", _m2026),
    ("2027", _m2027),
    ("2028", _m2028),
    ("2031", _m2031),
    ("2033", _m2033),
    ("2037", _m2037),
    ("2048", _m2048),
    ("2052", _m2052),
    ("2054", _m2054),
    ("2064", _m2064),
    ("2065", _m2065),
    ("2068", _m2068),
    ("2108", _m2108),
    ("2367", _m2367),
    ("2369", _m2369),
    ("2370", _m2370),
    ("2371", _m2371),
    ("2373", _m2373),
    ("2409", _m2409),
    ("2416", _m2416),
    ("2503", _m2503),
    ("2509", _m2509),
    ("2521", _m2521),
    ("2638", _m2638),
    ("2640", _m2640),
    ("2641", _m2641),
    ("2642", _m2642),
    ("2644", _m2644),
    ("2650", _m2650),
    ("2752", _m2752),
    ("2797", _m2797),
    ("2801", _m2801),
    ("2802", _m2802),
    ("2883", _m2883),
    ("2892", _m2892),
    ("2898", _m2898),
    ("2899", _m2899),
    ("2936", _m2936),
    ("2949", _m2949),
    ("2955", _m2955),
    ("2956", _m2956),
    ("2968", _m2968),
    ("2992", _m2992),
    ("2993", _m2993),
    ("2996", _m2996),
    ("2999", _m2999),
    ("3000", _m3000),
    ("3003", _m3003),
    ("3006", _m3006),
    ("3014", _m3014),
    ("3016", _m3016),
    ("3019", _m3019),
    ("3020", _m3020),
    ("3021", _m3021),
    ("3024", _m3024),
    ("3025", _m3025),
    ("3026", _m3026),
    ("3030", _m3030),
    ("3031", _m3031),
    ("3034", _m3034),
    ("3035", _m3035),
    ("3037", _m3037),
    ("3050", _m3050),
    ("3052", _m3052),
    ("3053", _m3053),
    ("3059", _m3059),
    ("3063", _m3063),
    ("3065", _m3065),
    ("3067", _m3067),
    ("3068", _m3068),
    ("3072", _m3072),
    ("3073", _m3073),
    ("3074", _m3074),
    ("3089", _m3089),
    ("3090", _m3090),
]


@pytest.mark.parametrize("code,mutator", MUTATORS)
def test_invoice_extra1(code: str, mutator, root: etree._Element) -> None:
    mutator(root)
    errs: list = []
    validate_invoice_extra1(root, errs)
    codes = [e.code for e in errs]
    if code in {"2108", "2521"}:
        # FUERA DE ALCANCE: la regla no debe reportarse localmente.
        assert code not in codes, f"Code {code} should be out of scope, but found in {codes}"
    else:
        assert code in codes, f"Expected error {code} in {codes}"
