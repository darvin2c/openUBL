"""Tests parametrizados para validaciones SUNAT adicionales de DebitNote.

Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
https://cpe.sunat.gob.pe/guias-y-manuales
"""

from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest
from lxml import etree

from openubl.enricher import ContentEnricher
from openubl.models import DebitNote, Cliente, DocumentoVentaDetalle, Proveedor
from openubl.renderer import render_debit_note
from openubl.validators._extra_debit_note import validate_debit_note_extra
from openubl.validators._extra_debit_note2 import validate_debit_note_extra2
from openubl.validators.common import NS_DEBIT_NOTE


_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
_NS = NS_DEBIT_NOTE


def _valid_debit_note_xml() -> str:
    doc = DebitNote(
        serie="B001", numero=1,
        comprobanteAfectadoSerieNumero="B001-1",
        sustentoDescripcion="Error en precio",
        proveedor=Proveedor(ruc="20100066603", razonSocial="Test SA"),
        cliente=Cliente(nombre="Carlos", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
        detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100"))],
        fechaEmision=date(2024, 1, 1),
    )
    ContentEnricher().enrich(doc)
    xml = render_debit_note(doc)
    root = etree.fromstring(xml.encode("utf-8"))
    ref_type = root.find("cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", namespaces=_NS)
    if ref_type is not None:
        ref_type.text = "03"
    return etree.tostring(root, encoding="unicode")


def _root():
    return etree.fromstring(_valid_debit_note_xml().encode("utf-8"))


def _find(root, xpath):
    return root.find(xpath, namespaces=_NS)


def _set_text(root, xpath, value):
    elem = _find(root, xpath)
    if elem is not None:
        elem.text = str(value)


def _remove(root, xpath):
    elem = _find(root, xpath)
    if elem is not None:
        elem.getparent().remove(elem)


def _remove_attr(root, xpath, attr):
    elem = _find(root, xpath)
    if elem is not None and attr in elem.attrib:
        del elem.attrib[attr]


def _add_child(parent, ns, tag, text=None, attrs=None):
    child = etree.SubElement(parent, f"{{{ns}}}{tag}")
    if text is not None:
        child.text = str(text)
    if attrs:
        for k, v in attrs.items():
            child.set(k, v)
    return child


def _set_ref_type_01(root):
    ref = _find(root, "cac:BillingReference/cac:InvoiceDocumentReference")
    if ref is not None:
        id_el = ref.find("cbc:ID", namespaces=_NS)
        if id_el is not None:
            id_el.text = "F001-1"
        type_el = ref.find("cbc:DocumentTypeCode", namespaces=_NS)
        if type_el is not None:
            type_el.text = "01"
    _set_text(root, "cbc:ID", "F001-1")


def _set_resp_code(root, code):
    _set_text(root, "cac:DiscrepancyResponse/cbc:ResponseCode", code)


def _line(root, index=0):
    return root.findall("cac:DebitNoteLine", namespaces=_NS)[index]


def _set_line_tax_code(root, code):
    _set_text(
        root,
        "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID",
        code,
    )


def _set_line_tax_amount(root, value):
    _set_text(
        root,
        "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount",
        value,
    )


def _set_line_tax_base(root, value):
    _set_text(
        root,
        "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount",
        value,
    )


def _set_line_tax_percent(root, value):
    _set_text(
        root,
        "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent",
        value,
    )


def _remove_line_tax_exemption(root):
    _remove(
        root,
        "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode",
    )


def _add_line_tax_subtotal(
    root,
    line_index,
    code,
    base,
    tax,
    percent=None,
    exemption=None,
    tier=None,
    base_unit=None,
    per_unit=None,
):
    line = _line(root, line_index)
    tax_total = line.find("cac:TaxTotal", namespaces=_NS)
    ts = etree.SubElement(tax_total, f"{{{_CAC}}}TaxSubtotal")
    if base is not None:
        b = _add_child(ts, _CBC, "TaxableAmount", base, {"currencyID": "Catalog2.PEN"})
    t = _add_child(ts, _CBC, "TaxAmount", tax, {"currencyID": "Catalog2.PEN"})
    tc = etree.SubElement(ts, f"{{{_CAC}}}TaxCategory")
    if percent is not None:
        _add_child(tc, _CBC, "Percent", percent)
    if exemption is not None:
        _add_child(tc, _CBC, "TaxExemptionReasonCode", exemption)
    if tier is not None:
        _add_child(tc, _CBC, "TierRange", tier)
    if per_unit is not None:
        _add_child(tc, _CBC, "PerUnitAmount", per_unit)
    if base_unit is not None:
        _add_child(ts, _CBC, "BaseUnitMeasure", base_unit)
    tsch = etree.SubElement(tc, f"{{{_CAC}}}TaxScheme")
    _add_child(tsch, _CBC, "ID", code)
    _add_child(tsch, _CBC, "Name", "X")
    _add_child(tsch, _CBC, "TaxTypeCode", "X")


def _add_global_tax_subtotal(root, code, base=None, tax=None):
    tax_total = _find(root, "cac:TaxTotal")
    ts = etree.SubElement(tax_total, f"{{{_CAC}}}TaxSubtotal")
    if base is not None:
        _add_child(ts, _CBC, "TaxableAmount", base, {"currencyID": "Catalog2.PEN"})
    if tax is not None:
        _add_child(ts, _CBC, "TaxAmount", tax, {"currencyID": "Catalog2.PEN"})
    tc = etree.SubElement(ts, f"{{{_CAC}}}TaxCategory")
    tsch = etree.SubElement(tc, f"{{{_CAC}}}TaxScheme")
    _add_child(tsch, _CBC, "ID", code)
    _add_child(tsch, _CBC, "Name", "X")
    _add_child(tsch, _CBC, "TaxTypeCode", "X")


def _duplicate_line(root):
    lines = root.findall("cac:DebitNoteLine", namespaces=_NS)
    new_line = deepcopy(lines[0])
    root.append(new_line)


def _add_alt_price(root, price_type, amount):
    line = _line(root)
    pr = line.find("cac:PricingReference", namespaces=_NS)
    acp = etree.SubElement(pr, f"{{{_CAC}}}AlternativeConditionPrice")
    _add_child(acp, _CBC, "PriceAmount", amount, {"currencyID": "Catalog2.PEN"})
    _add_child(acp, _CBC, "PriceTypeCode", price_type)


def _set_price_type_02(root):
    line = _line(root)
    acp = line.find(
        "cac:PricingReference/cac:AlternativeConditionPrice", namespaces=_NS
    )
    if acp is not None:
        ptc = acp.find("cbc:PriceTypeCode", namespaces=_NS)
        if ptc is not None:
            ptc.text = "02"


def _set_price_amount(root, value):
    _set_text(
        root,
        "cac:DebitNoteLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount",
        value,
    )


def _set_unit_price(root, value):
    _set_text(root, "cac:DebitNoteLine/cac:Price/cbc:PriceAmount", value)


def _set_quantity(root, value):
    _set_text(root, "cac:DebitNoteLine/cbc:DebitedQuantity", value)


def _add_allowance_charge(root, indicator, reason, amount, base=None, factor=None):
    ac = etree.SubElement(root, f"{{{_CAC}}}AllowanceCharge")
    _add_child(ac, _CBC, "ChargeIndicator", indicator)
    if reason is not None:
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", reason)
    if base is not None:
        _add_child(ac, _CBC, "BaseAmount", base, {"currencyID": "Catalog2.PEN"})
    if factor is not None:
        _add_child(ac, _CBC, "MultiplierFactorNumeric", factor)
    _add_child(ac, _CBC, "Amount", amount, {"currencyID": "Catalog2.PEN"})


def _add_line_allowance_charge(root, indicator, reason, amount, base=None, factor=None):
    line = _line(root)
    ac = etree.SubElement(line, f"{{{_CAC}}}AllowanceCharge")
    _add_child(ac, _CBC, "ChargeIndicator", indicator)
    if reason is not None:
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", reason)
    if base is not None:
        _add_child(ac, _CBC, "BaseAmount", base, {"currencyID": "Catalog2.PEN"})
    if factor is not None:
        _add_child(ac, _CBC, "MultiplierFactorNumeric", factor)
    _add_child(ac, _CBC, "Amount", amount, {"currencyID": "Catalog2.PEN"})


def _add_payment_terms(root, id_, means_id=None, amount=None, currency="PEN"):
    pt = etree.SubElement(root, f"{{{_CAC}}}PaymentTerms")
    _add_child(pt, _CBC, "ID", id_)
    if means_id is not None:
        _add_child(pt, _CBC, "PaymentMeansID", means_id)
    if amount is not None:
        _add_child(pt, _CBC, "Amount", amount, {"currencyID": currency})
    return pt


def _add_payment_means(root, id_, account=None):
    pm = etree.SubElement(root, f"{{{_CAC}}}PaymentMeans")
    _add_child(pm, _CBC, "ID", id_)
    if account is not None:
        pfa = etree.SubElement(pm, f"{{{_CAC}}}PayeeFinancialAccount")
        _add_child(pfa, _CBC, "ID", account)
    return pm


def _add_item_property(root, code):
    line = _line(root)
    item = line.find("cac:Item", namespaces=_NS)
    prop = etree.SubElement(item, f"{{{_CAC}}}AdditionalItemProperty")
    _add_child(prop, _CBC, "NameCode", code)
    return prop

def _add_despatch_document_reference(root, doc_type, doc_id):
    ref = etree.SubElement(root, f"{{{_CAC}}}DespatchDocumentReference")
    _add_child(ref, _CBC, "ID", doc_id)
    _add_child(ref, _CBC, "DocumentTypeCode", doc_type)
    return ref

def _add_additional_document_reference(root, doc_type, doc_id):
    ref = etree.SubElement(root, f"{{{_CAC}}}AdditionalDocumentReference")
    _add_child(ref, _CBC, "ID", doc_id)
    _add_child(ref, _CBC, "DocumentTypeCode", doc_type)
    return ref

def _add_billing_reference(root, doc_type, doc_id):
    ref = etree.SubElement(root, f"{{{_CAC}}}BillingReference")
    idr = etree.SubElement(ref, f"{{{_CAC}}}InvoiceDocumentReference")
    _add_child(idr, _CBC, "ID", doc_id)
    _add_child(idr, _CBC, "DocumentTypeCode", doc_type)
    return ref

def _add_item_property_with_value(root, code, value):
    prop = _add_item_property(root, code)
    _add_child(prop, _CBC, "Value", value)
    return prop

def _add_requested_monetary_total_child(root, tag, value):
    total = _find(root, "cac:RequestedMonetaryTotal")
    _add_child(total, _CBC, tag, value, {"currencyID": "Catalog2.PEN"})


def _make_gratuita_line(root):
    """Convierte la línea existente en operación gratuita (9996)."""
    _set_line_tax_code(root, "9996")
    _set_line_tax_amount(root, "18.00")
    _set_line_tax_base(root, "100.00")
    _set_line_tax_percent(root, "18.00")
    _set_text(
        root,
        "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode",
        "11",
    )
    _set_price_type_02(root)
    _set_price_amount(root, "100.00")


@pytest.mark.parametrize(
    "code,mutator",
    [
        # ------------------------------------------------------------------
        # Emisor / receptor
        # ------------------------------------------------------------------
        (
            "2017",
            lambda r: (
                _set_text(
                    r,
                    "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
                    "12345",
                ),
                _find(
                    r,
                    "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
                ).set("schemeID", "6"),
            ),
        ),
        (
            "3089",
            lambda r: _add_child(
                _find(r, "cac:AccountingSupplierParty/cac:Party"),
                _CAC,
                "PartyIdentification",
            ),
        ),
        (
            "3090",
            lambda r: _add_child(
                _find(r, "cac:AccountingCustomerParty/cac:Party"),
                _CAC,
                "PartyIdentification",
            ),
        ),
        # ------------------------------------------------------------------
        # Líneas
        # ------------------------------------------------------------------
        ("2752", lambda r: _duplicate_line(r)),
        ("2936", lambda r: _find(r, "cac:DebitNoteLine/cbc:DebitedQuantity").set("unitCode", "XYZ")),
        ("2369", lambda r: _set_unit_price(r, "0")),
        ("2370", lambda r: _set_text(r, "cac:DebitNoteLine/cbc:LineExtensionAmount", "0")),
        ("2367", lambda r: _set_price_amount(r, "0")),
        ("2409", lambda r: _add_alt_price(r, "01", "50.00")),
        # ------------------------------------------------------------------
        # Impuestos por línea
        # ------------------------------------------------------------------
        ("2033", lambda r: _set_line_tax_amount(r, "0")),
        (
            "2037",
            lambda r: _set_text(
                r,
                "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID",
                "",
            ),
        ),
        ("2993", lambda r: _set_line_tax_percent(r, "0")),
        ("3105", lambda r: _remove(r, "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal")),
        ("3052", lambda r: _add_line_allowance_charge(r, "true", "45", "10", "10", factor="abc")),
        ("3053", lambda r: _add_line_allowance_charge(r, "true", "45", "10", "-1")),
        ("3021", lambda r: _set_text(r, "cac:DebitNoteLine/cac:TaxTotal/cbc:TaxAmount", "0")),
        ("3026", lambda r: _add_child(_line(r), _CAC, "TaxTotal")),
        ("3195", lambda r: _remove(r, "cac:DebitNoteLine/cac:TaxTotal")),
        ("3031", lambda r: _set_line_tax_base(r, "0")),
        ("2992", lambda r: _remove(r, "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent")),
        ("3102", lambda r: _set_line_tax_percent(r, "0")),
        ("3103", lambda r: _set_line_tax_amount(r, "10.00")),
        ("2371", lambda r: _remove_line_tax_exemption(r)),
        ("3050", lambda r: _add_line_tax_subtotal(r, 0, "2000", "100", "18", "10", exemption="10", tier="1")),
        (
            "2373",
            lambda r: _add_line_tax_subtotal(r, 0, "2000", "100", "18", "10"),
        ),
        (
            "3210",
            lambda r: _add_child(
                _find(r, "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory"),
                _CBC,
                "TierRange",
                "1",
            ),
        ),
        ("3067", lambda r: _add_line_tax_subtotal(r, 0, "1000", "100", "18", "18")),
        (
            "3104",
            lambda r: _add_line_tax_subtotal(r, 0, "2000", "100", "0", "0", tier="1"),
        ),
        (
            "3108",
            lambda r: _add_line_tax_subtotal(r, 0, "2000", "100", "10", "5", tier="1"),
        ),
        (
            "3109",
            lambda r: _add_line_tax_subtotal(r, 0, "9999", "100", "10", "5"),
        ),
        (
            "3110",
            lambda r: _add_line_tax_subtotal(r, 0, "9997", "100", "10"),
        ),
        (
            "3111",
            lambda r: (
                _set_line_tax_base(r, "100"),
                _set_line_tax_amount(r, "0"),
            ),
        ),
        (
            "2640",
            lambda r: (
                _set_line_tax_code(r, "9996"),
                _set_line_tax_base(r, "100"),
                _set_line_tax_amount(r, "0"),
                _set_line_tax_percent(r, "18"),
                _set_text(
                    r,
                    "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode",
                    "11",
                ),
            ),
        ),
        (
            "3224",
            lambda r: (
                _set_price_type_02(r),
                _set_price_amount(r, "100.00"),
            ),
        ),
        (
            "3234",
            lambda r: (
                _make_gratuita_line(r),
                _set_price_type_02(r),
                _add_alt_price(r, "01", "118.00"),
                _remove(r, "cac:DebitNoteLine/cac:PricingReference/cac:AlternativeConditionPrice[cbc:PriceTypeCode='02']"),
            ),
        ),
        # ICBPER
        (
            "2892_base",
            lambda r: _add_line_tax_subtotal(
                r, 0, "7152", None, "0.50", base_unit="ABCDEF"
            ),
        ),
        (
            "2892_perunit",
            lambda r: _add_line_tax_subtotal(
                r, 0, "7152", None, "0.50", base_unit="1", per_unit="0"
            ),
        ),
        (
            "3237",
            lambda r: _add_line_tax_subtotal(r, 0, "7152", None, "0.50"),
        ),
        (
            "3236",
            lambda r: _add_line_tax_subtotal(
                r, 0, "7152", None, "0.50", base_unit="5"
            ),
        ),
        (
            "3238",
            lambda r: _add_line_tax_subtotal(
                r, 0, "7152", None, "0.50", base_unit="1", per_unit="0.00"
            ),
        ),
        # ------------------------------------------------------------------
        # Impuestos globales
        # ------------------------------------------------------------------
        ("2956", lambda r: _remove(r, "cac:TaxTotal")),
        ("3020", lambda r: _set_text(r, "cac:TaxTotal/cbc:TaxAmount", "0")),
        ("3024", lambda r: _add_child(r, _CAC, "TaxTotal")),
        ("3059", lambda r: _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "")),
        ("2054", lambda r: _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name", "")),
        ("2052", lambda r: _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode", "")),
        ("3068", lambda r: _add_global_tax_subtotal(r, "1000", "100", "18")),
        ("2999", lambda r: _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "0")),
        ("3003", lambda r: _remove(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount")),
        ("2048", lambda r: _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0")),
        (
            "3000",
            lambda r: (
                _add_line_tax_subtotal(r, 0, "9997", "100", "0"),
                _add_global_tax_subtotal(r, "9997", "100", "10"),
            ),
        ),
        (
            "2638",
            lambda r: _remove(r, "cac:TaxTotal/cac:TaxSubtotal"),
        ),
        (
            "2641",
            lambda r: (
                _set_ref_type_01(r),
                _make_gratuita_line(r),
                _set_text(r, "cac:DebitNoteLine/cbc:LineExtensionAmount", "0"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "0"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "9996"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name", "GRATUITA"),
            ),
        ),
        (
            "2642",
            lambda r: (
                _set_resp_code(r, "11"),
                _set_line_tax_percent(r, "18"),
                _set_text(
                    r,
                    "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode",
                    "10",
                ),
            ),
        ),
        (
            "2644",
            lambda r: (
                _set_resp_code(r, "12"),
                _set_text(
                    r,
                    "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode",
                    "10",
                ),
            ),
        ),
        (
            "3107",
            lambda r: (
                _set_resp_code(r, "11"),
            ),
        ),
        (
            "2949",
            lambda r: (
                _set_text(r, "cbc:IssueDate", "2019-01-01"),
                _add_global_tax_subtotal(r, "7152", "100", "1.00"),
            ),
        ),
        # ------------------------------------------------------------------
        # Cuadres globales (solo cuando modifica factura 01)
        # ------------------------------------------------------------------
        (
            "3270",
            lambda r: (
                _set_ref_type_01(r),
                _set_price_amount(r, "200.00"),
            ),
        ),
        (
            "3271",
            lambda r: (
                _set_ref_type_01(r),
                _set_unit_price(r, "50.00"),
            ),
        ),
        (
            "3272",
            lambda r: (
                _set_ref_type_01(r),
                _set_line_tax_base(r, "50.00"),
            ),
        ),
        (
            "3273",
            lambda r: (
                _set_ref_type_01(r),
                _add_line_tax_subtotal(r, 0, "9995", "100", "0"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "50"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "9995"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name", "EXP"),
            ),
        ),
        (
            "3274",
            lambda r: (
                _set_ref_type_01(r),
                _add_line_tax_subtotal(r, 0, "9998", "100", "0"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "50"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "9998"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name", "INA"),
            ),
        ),
        (
            "3275",
            lambda r: (
                _set_ref_type_01(r),
                _add_line_tax_subtotal(r, 0, "9997", "100", "0"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "50"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "9997"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name", "EXO"),
            ),
        ),
        (
            "3276",
            lambda r: (
                _set_ref_type_01(r),
                _make_gratuita_line(r),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "0"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "9996"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name", "GRATUITA"),
            ),
        ),
        (
            "3277",
            lambda r: (
                _set_ref_type_01(r),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "50"),
            ),
        ),
        (
            "3278",
            lambda r: (
                _set_ref_type_01(r),
                _add_requested_monetary_total_child(r, "LineExtensionAmount", "50"),
            ),
        ),
        (
            "3279",
            lambda r: (
                _set_ref_type_01(r),
                _add_requested_monetary_total_child(r, "TaxInclusiveAmount", "50"),
            ),
        ),
        (
            "3280",
            lambda r: (
                _set_ref_type_01(r),
                _set_text(r, "cac:RequestedMonetaryTotal/cbc:PayableAmount", "50"),
            ),
        ),
        (
            "3291",
            lambda r: (
                _set_ref_type_01(r),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "50"),
            ),
        ),
        (
            "3294",
            lambda r: (
                _set_ref_type_01(r),
                _set_text(r, "cac:TaxTotal/cbc:TaxAmount", "50"),
            ),
        ),
        (
            "3302",
            lambda r: (
                _set_ref_type_01(r),
                _make_gratuita_line(r),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "100"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "10"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "9996"),
                _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name", "GRATUITA"),
            ),
        ),
        (
            "3303",
            lambda r: _add_requested_monetary_total_child(r, "PayableRoundingAmount", "2"),
        ),
        (
            "3306",
            lambda r: (
                _set_ref_type_01(r),
                _add_line_tax_subtotal(r, 0, "7152", None, "0.50", base_unit="1"),
                _add_global_tax_subtotal(r, "7152", None, "10"),
            ),
        ),
        (
            "3296",
            lambda r: (
                _set_ref_type_01(r),
                _add_line_tax_subtotal(r, 0, "2000", "100", "18", "18", tier="1"),
                _add_global_tax_subtotal(r, "2000", "50", "18"),
            ),
        ),
        (
            "3297",
            lambda r: (
                _set_ref_type_01(r),
                _add_line_tax_subtotal(r, 0, "9999", "100", "10", "10"),
                _add_global_tax_subtotal(r, "9999", "50", "10"),
            ),
        ),
        (
            "3298",
            lambda r: (
                _set_ref_type_01(r),
                _add_line_tax_subtotal(r, 0, "2000", "100", "18", "18", tier="1"),
                _add_global_tax_subtotal(r, "2000", "100", "10"),
            ),
        ),
        (
            "3299",
            lambda r: (
                _set_ref_type_01(r),
                _add_line_tax_subtotal(r, 0, "9999", "100", "10", "10"),
                _add_global_tax_subtotal(r, "9999", "100", "5"),
            ),
        ),
        # ------------------------------------------------------------------
        # Totales globales
        # ------------------------------------------------------------------
        (
            "2064",
            lambda r: _add_requested_monetary_total_child(r, "ChargeTotalAmount", "0"),
        ),
        (
            "3019",
            lambda r: _add_requested_monetary_total_child(r, "TaxInclusiveAmount", "0"),
        ),
        # ------------------------------------------------------------------
        # Notas
        # ------------------------------------------------------------------
        ("3006", lambda r: _set_text(r, "cbc:Note", "x" * 201)),
        # ------------------------------------------------------------------
        # Cargos / descuentos
        # ------------------------------------------------------------------
        ("3072", lambda r: _add_allowance_charge(r, "true", None, "10")),
        ("3073", lambda r: _add_line_allowance_charge(r, "true", None, "10")),
        ("3025", lambda r: _add_allowance_charge(r, "true", "45", "10", "10", factor="0")),
        ("3092", lambda r: _add_allowance_charge(r, "true", "45", "10")),
        (
            "3114",
            lambda r: _add_allowance_charge(r, "false", "45", "10"),
        ),
        ("3074", lambda r: _add_allowance_charge(r, "true", "45", "0", "10")),
        ("3016", lambda r: _add_allowance_charge(r, "true", "45", "0", "0")),
        (
            "3282",
            lambda r: _add_allowance_charge(r, "false", "04", "10", "10"),
        ),
        # ------------------------------------------------------------------
        # Términos de pago
        # ------------------------------------------------------------------
        ("3034", lambda r: _add_payment_means(r, "Detraccion")),
        ("3035", lambda r: _add_payment_terms(r, "Detraccion", "001")),
        ("3037", lambda r: _add_payment_terms(r, "Detraccion", "001", "0")),
        ("3127", lambda r: _add_payment_terms(r, "Detraccion")),
        (
            "3208",
            lambda r: _add_payment_terms(r, "Detraccion", "001", "10", "USD"),
        ),
        ("3313", lambda r: _add_payment_terms(r, "Detraccion", "001", "10")),
        ("3314", lambda r: _add_payment_means(r, "Detraccion", "000123")),
        (
            "3093",
            lambda r: (
                _add_payment_terms(r, "FormaPago", "Contado"),
            ),
        ),
        # ------------------------------------------------------------------
        # Propiedades adicionales del ítem
        # ------------------------------------------------------------------
        ("3065", lambda r: _add_item_property(r, "3059")),
        ("3243", lambda r: _add_item_property(r, "7014")),
        # ------------------------------------------------------------------
        # Combinaciones y otros
        # ------------------------------------------------------------------
        (
            "3223",
            lambda r: (
                _add_line_tax_subtotal(r, 0, "9997", "100", "0"),
            ),
        ),
        # 3030 requiere serie F + factura
        (
            "3030",
            lambda r: (
                _set_ref_type_01(r),
                _remove(
                    r,
                    "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cac:RegistrationAddress/cbc:AddressTypeCode",
                ),
            ),
        ),
        # ------------------------------------------------------------------
        # Batch 2: cabecera / discrepancia / documento modificado
        # ------------------------------------------------------------------
        ("2128", lambda r: _remove(r, "cac:DiscrepancyResponse/cbc:ResponseCode")),
        ("2135", lambda r: _set_text(r, "cac:DiscrepancyResponse/cbc:Description", "x" * 501)),
        ("2136", lambda r: _remove(r, "cac:DiscrepancyResponse/cbc:Description")),
        ("3203", lambda r: _add_child(_find(r, "cac:DiscrepancyResponse"), _CBC, "ResponseCode", "08")),
        ("2524", lambda r: _remove(r, "cac:BillingReference")),
        (
            "2594",
            lambda r: (
                _set_text(r, "cbc:ID", "0001-1"),
                _set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "02"),
            ),
        ),
        (
            "2884",
            lambda r: (
                _add_billing_reference(r, "01", "F001-2"),
            ),
        ),
        (
            "3194",
            lambda r: (
                _add_billing_reference(r, "03", "B001-2"),
            ),
        ),
        # ------------------------------------------------------------------
        # Batch 2: emisor / receptor / moneda
        # ------------------------------------------------------------------
        (
            "2511",
            lambda r: _find(
                r, "cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID"
            ).set("schemeID", "1"),
        ),
        (
            "3029",
            lambda r: _find(
                r, "cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID"
            ).attrib.pop("schemeID", None),
        ),
        (
            "2679",
            lambda r: _remove(
                r, "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID"
            ),
        ),
        ("3088", lambda r: _set_text(r, "cbc:DocumentCurrencyCode", "Catalog2.XXX")),
        # ------------------------------------------------------------------
        # Batch 2: líneas
        # ------------------------------------------------------------------
        ("2137", lambda r: _set_text(r, "cac:DebitNoteLine/cbc:ID", "0")),
        ("2139", lambda r: _set_text(r, "cac:DebitNoteLine/cbc:DebitedQuantity", "-1")),
        (
            "2410",
            lambda r: _set_text(
                r, "cac:DebitNoteLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceTypeCode", "03"
            ),
        ),
        (
            "3051",
            lambda r: _set_text(
                r, "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name", "XXX"
            ),
        ),
        (
            "3292",
            lambda r: _set_text(
                r, "cac:DebitNoteLine/cac:TaxTotal/cbc:TaxAmount", "50.00"
            ),
        ),
        (
            "3462",
            lambda r: (
                _duplicate_line(r),
                _set_text(r, "cac:DebitNoteLine[2]/cbc:ID", "2"),
                _set_text(r, "cac:DebitNoteLine[2]/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent", "10.00"),
            ),
        ),
        (
            "3230",
            lambda r: _set_text(
                r, "cac:DebitNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "17"
            ),
        ),
        (
            "3221",
            lambda r: (
                _set_resp_code(r, "12"),
                _add_line_tax_subtotal(r, 0, "9997", "100", "0", "0"),
            ),
        ),
        # ------------------------------------------------------------------
        # Batch 2: documentos relacionados
        # ------------------------------------------------------------------
        (
            "2364",
            lambda r: (
                _add_despatch_document_reference(r, "09", "T001-1"),
                _add_despatch_document_reference(r, "09", "T001-1"),
            ),
        ),
        (
            "2365",
            lambda r: (
                _add_additional_document_reference(r, "99", "DOC-1"),
                _add_additional_document_reference(r, "99", "DOC-1"),
            ),
        ),
        (
            "2426",
            lambda r: (
                _add_additional_document_reference(r, "99", "DOC-1"),
                _add_additional_document_reference(r, "99", "DOC-1"),
            ),
        ),
        # ------------------------------------------------------------------
        # Batch 2: propiedades adicionales del ítem
        # ------------------------------------------------------------------
        ("3064", lambda r: _add_item_property(r, "7000")),
        (
            "3151",
            lambda r: (
                _add_item_property_with_value(r, "7000", "1"),
                _add_item_property_with_value(r, "7002", "1"),
                _add_item_property_with_value(r, "7004", "C-123"),
                _add_item_property_with_value(r, "7005", "2024-01-01"),
                _add_item_property_with_value(r, "7006", "150101"),
                _add_item_property_with_value(r, "7007", "Av. Test"),
            ),
        ),
        (
            "3152",
            lambda r: (
                _add_item_property_with_value(r, "7000", "1"),
                _add_item_property_with_value(r, "7005", "2024-01-01"),
            ),
        ),
        (
            "3153",
            lambda r: (
                _add_item_property_with_value(r, "7000", "1"),
                _add_item_property_with_value(r, "7004", "C-123"),
            ),
        ),
        (
            "3154",
            lambda r: (
                _add_item_property_with_value(r, "7000", "1"),
                _add_item_property_with_value(r, "7002", "1"),
                _add_item_property_with_value(r, "7003", "12345"),
                _add_item_property_with_value(r, "7004", "C-123"),
                _add_item_property_with_value(r, "7005", "2024-01-01"),
                _add_item_property_with_value(r, "7007", "Av. Test"),
            ),
        ),
        (
            "3155",
            lambda r: (
                _add_item_property_with_value(r, "7000", "1"),
                _add_item_property_with_value(r, "7002", "1"),
                _add_item_property_with_value(r, "7003", "12345"),
                _add_item_property_with_value(r, "7004", "C-123"),
                _add_item_property_with_value(r, "7005", "2024-01-01"),
                _add_item_property_with_value(r, "7006", "150101"),
            ),
        ),
        (
            "3497",
            lambda r: (
                _add_item_property_with_value(r, "7013", "C-123"),
                _add_item_property_with_value(r, "7015", "3"),
                _add_item_property_with_value(r, "7016", "Contrato test"),
                _add_item_property_with_value(r, "7017", "50.00"),
            ),
        ),
        (
            "3498",
            lambda r: (
                _add_item_property_with_value(r, "7013", "C-123"),
                _add_item_property_with_value(r, "7013", "C-456"),
                _add_item_property_with_value(r, "7015", "1"),
                _add_item_property_with_value(r, "7016", "Contrato test"),
                _add_item_property_with_value(r, "7017", "50.00"),
            ),
        ),
        (
            "3499",
            lambda r: (
                _add_item_property_with_value(r, "7013", "C-123"),
            ),
        ),
        (
            "3500",
            lambda r: (
                _add_item_property_with_value(r, "7013", "C-123"),
                _add_item_property_with_value(r, "7015", "1"),
                _add_item_property_with_value(r, "7016", "Contrato test"),
                _add_item_property_with_value(r, "7017", "ABC"),
            ),
        ),
        (
            "3501",
            lambda r: (
                _add_item_property_with_value(r, "7013", "x" * 31),
                _add_item_property_with_value(r, "7015", "1"),
                _add_item_property_with_value(r, "7016", "Contrato test"),
                _add_item_property_with_value(r, "7017", "50.00"),
            ),
        ),
        (
            "3502",
            lambda r: (
                _add_item_property_with_value(r, "7013", "C-123"),
                _add_item_property_with_value(r, "7015", "1"),
                _add_item_property_with_value(r, "7016", "x" * 101),
                _add_item_property_with_value(r, "7017", "50.00"),
            ),
        ),
    ],
)
def test_debit_note_extra(code, mutator):
    root = _root()
    mutator(root)
    errors = []
    validate_debit_note_extra(root, errors)
    validate_debit_note_extra2(root, errors)
    codes = [e.code for e in errors]
    expected = code.split("_")[0]
    assert expected in codes, f"Expected error {expected} in {codes}"


def test_debit_note_extra_valid():
    root = _root()
    errors = []
    validate_debit_note_extra(root, errors)
    validate_debit_note_extra2(root, errors)
    assert errors == []
