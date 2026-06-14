"""Tests parametrizados para validaciones SUNAT adicionales de CreditNote.

Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
https://cpe.sunat.gob.pe/guias-y-manuales
"""

from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest
from lxml import etree

from openubl.models import CreditNote, Proveedor, Cliente, DocumentoVentaDetalle
from openubl.enricher import ContentEnricher
from openubl.renderer import render_credit_note
from openubl.validators._extra_credit_note import validate_credit_note_extra


_NS = {
    "": "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}

_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"


def _valid_credit_note_root() -> etree._Element:
    doc = CreditNote(
        serie="B001",
        numero=1,
        comprobanteAfectadoSerieNumero="B001-1",
        sustentoDescripcion="Error en precio",
        proveedor=Proveedor(ruc="20100066603", razonSocial="Test SA"),
        cliente=Cliente(nombre="Carlos", numeroDocumentoIdentidad="12345678", tipoDocumentoIdentidad="1"),
        detalles=[DocumentoVentaDetalle(descripcion="Item1", cantidad=Decimal("1"), precio=Decimal("100"))],
        fechaEmision=date(2024, 1, 1),
    )
    ContentEnricher().enrich(doc)
    xml = render_credit_note(doc)
    root = etree.fromstring(xml.encode("utf-8"))
    ref_type = root.find("cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", namespaces=_NS)
    if ref_type is not None:
        ref_type.text = "03"
    return root


# ------------------------------------------------------------------
# Helpers de mutación
# ------------------------------------------------------------------

def _find(root: etree._Element, xpath: str) -> etree._Element | None:
    return root.find(xpath, namespaces=_NS)


def _findall(root: etree._Element, xpath: str) -> list[etree._Element]:
    return root.findall(xpath, namespaces=_NS)


def _set_text(root: etree._Element, xpath: str, text: str) -> None:
    elem = _find(root, xpath)
    if elem is not None:
        elem.text = text


def _remove(root: etree._Element, xpath: str) -> None:
    elem = _find(root, xpath)
    if elem is not None:
        elem.getparent().remove(elem)


def _remove_attr(root: etree._Element, xpath: str, attr: str) -> None:
    elem = _find(root, xpath)
    if elem is not None and attr in elem.attrib:
        del elem.attrib[attr]


def _set_attr(root: etree._Element, xpath: str, attr: str, value: str) -> None:
    elem = _find(root, xpath)
    if elem is not None:
        elem.set(attr, value)


def _add_child(parent: etree._Element, ns_uri: str, tag: str, text: str | None = None, attrs: dict | None = None) -> etree._Element:
    child = etree.SubElement(parent, f"{{{ns_uri}}}{tag}")
    if text is not None:
        child.text = text
    if attrs:
        for k, v in attrs.items():
            child.set(k, v)
    return child



def _line(root: etree._Element) -> etree._Element:
    return _find(root, "cac:CreditNoteLine")


def _add_line_tax_subtotal(root: etree._Element, tax_code: str, base: str = "100.00", tax: str = "18.00", percent: str = "18.00") -> etree._Element:
    line = _line(root)
    tax_total = line.find("cac:TaxTotal", namespaces=_NS)
    if tax_total is None:
        tax_total = etree.SubElement(line, f"{{{_CAC}}}TaxTotal")
    ts = etree.SubElement(tax_total, f"{{{_CAC}}}TaxSubtotal")
    _add_child(ts, _CBC, "TaxableAmount", base, {"currencyID": "Catalog2.PEN"})
    _add_child(ts, _CBC, "TaxAmount", tax, {"currencyID": "Catalog2.PEN"})
    tc = etree.SubElement(ts, f"{{{_CAC}}}TaxCategory")
    _add_child(tc, _CBC, "Percent", percent)
    _add_child(tc, _CBC, "TaxExemptionReasonCode", "10")
    ts2 = etree.SubElement(tc, f"{{{_CAC}}}TaxScheme")
    _add_child(ts2, _CBC, "ID", tax_code)
    _add_child(ts2, _CBC, "Name", "IGV" if tax_code == "1000" else "TRIB")
    _add_child(ts2, _CBC, "TaxTypeCode", "VAT")
    return ts


def _set_line_tax_code(root: etree._Element, code: str) -> None:
    _set_text(root, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", code)


def _set_resp_code(root: etree._Element, code: str) -> None:
    _set_text(root, "cac:DiscrepancyResponse/cbc:ResponseCode", code)


def _set_serie(root: etree._Element, serie: str) -> None:
    _set_text(root, "cbc:ID", f"{serie}-1")


def _set_operation_type(root: etree._Element, op_type: str) -> None:
    custom = _find(root, "cbc:CustomizationID")
    if custom is not None:
        custom.set("listID", op_type)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

@pytest.mark.parametrize("code,mutator", [
    # ERROR 2017: cliente RUC sin 11 dígitos
    ("2017", lambda r: (
        _set_attr(r, "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID", "schemeID", "6"),
        _set_text(r, "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID", "123"),
    )),
    # ERROR 2033: TaxAmount de línea formato inválido
    ("2033", lambda r: _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0")),
    # ERROR 2037: código de tributo de línea vacío
    ("2037", lambda r: _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "")),
    # ERROR 2048: TaxAmount global formato inválido
    ("2048", lambda r: _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0")),
    # ERROR 2052: TaxTypeCode global vacío
    ("2052", lambda r: _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode", "")),
    # ERROR 2054: Name global vacío
    ("2054", lambda r: _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name", "")),
    # ERROR 2064: ChargeTotalAmount formato inválido
    ("2064", lambda r: (
        lmt := _find(r, "cac:LegalMonetaryTotal"),
        _add_child(lmt, _CBC, "ChargeTotalAmount", "0", {"currencyID": "Catalog2.PEN"}),
    )),
    # ERROR 2367: PricingReference PriceAmount inválido
    ("2367", lambda r: _set_text(r, "cac:CreditNoteLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount", "0")),
    # ERROR 2369: Price/PriceAmount inválido
    ("2369", lambda r: _set_text(r, "cac:CreditNoteLine/cac:Price/cbc:PriceAmount", "0")),
    # ERROR 2370: LineExtensionAmount inválido
    ("2370", lambda r: _set_text(r, "cac:CreditNoteLine/cbc:LineExtensionAmount", "0")),
    # ERROR 2371: falta TaxExemptionReasonCode
    ("2371", lambda r: _remove(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode")),
    # ERROR 2373: ISC sin TierRange
    ("2373", lambda r: (
        _set_line_tax_code(r, "2000"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "10.00"),
    )),
    # ERROR 2409: PriceTypeCode repetido
    ("2409", lambda r: (
        pr := _find(r, "cac:CreditNoteLine/cac:PricingReference"),
        pr.append(deepcopy(_find(r, "cac:CreditNoteLine/cac:PricingReference/cac:AlternativeConditionPrice"))),
    )),
    # ERROR 2638: línea con tributo sin total global correspondiente
    ("2638", lambda r: (
        _add_line_tax_subtotal(r, "9997", "100.00", "0.00", "0.00"),
    )),
    # ERROR 2640: gratuita con precio de venta > 0
    ("2640", lambda r: (
        _set_line_tax_code(r, "9996"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0.00"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "100.00"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "11"),
    )),
    # ERROR 2641: gratuita con precio referencial > 0 pero total global gratuita == 0
    ("2641", lambda r: (
        _set_line_tax_code(r, "9996"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0.00"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "100.00"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "11"),
        _set_text(r, "cac:CreditNoteLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceTypeCode", "02"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "0.00"),
    )),
    # ERROR 2642: exportación sin afectación 40
    ("2642", lambda r: (
        _set_resp_code(r, "11"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "10"),
    )),
    # ERROR 2644: IVAP sin afectación 17
    ("2644", lambda r: (
        _set_resp_code(r, "12"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "10"),
    )),
    # ERROR 2892: BaseUnitMeasure formato inválido
    ("2892", lambda r: (
        ts := _add_line_tax_subtotal(r, "7152", "1.00", "0.50", "0.50"),
        _add_child(ts, _CBC, "BaseUnitMeasure", "abc"),
    )),
    # ERROR 2936: unitCode fuera de catálogo
    ("2936", lambda r: _set_attr(r, "cac:CreditNoteLine/cbc:CreditedQuantity", "unitCode", "ZZZ")),
    # ERROR 2949: ICBPER antes de vigencia
    ("2949", lambda r: (
        _set_line_tax_code(r, "7152"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "7152"),
        _set_text(r, "cbc:IssueDate", "2019-07-01"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0.20"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0.20"),
    )),
    ("2956", lambda r: _remove(r, "cac:TaxTotal")),
    # ERROR 2992: falta Percent
    ("2992", lambda r: _remove(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent")),
    # ERROR 2993: Percent == 0
    ("2993", lambda r: _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent", "0.00")),
    # ERROR 2996: falta Name de tributo en línea
    ("2996", lambda r: _remove(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name")),
    # ERROR 2999: TaxableAmount global formato inválido
    ("2999", lambda r: _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "0")),
    # ERROR 3000: TaxAmount global != 0 para exonerada/inafecta/exportación
    ("3000", lambda r: (
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "9995"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "10.00"),
    )),
    # ERROR 3003: falta TaxableAmount global
    ("3003", lambda r: _remove(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount")),
    # ERROR 3006: Note demasiado largo
    ("3006", lambda r: _set_text(r, "cbc:Note", "x" * 201)),
    # ERROR 3014: languageLocaleID repetido
    ("3014", lambda r: (
        n := _find(r, "cbc:Note"),
        n.set("languageLocaleID", "1000"),
        n2 := deepcopy(n),
        r.insert(0, n2),
    )),
    # ERROR 3016: BaseAmount global formato inválido
    ("3016", lambda r: (
        ac := _add_child(r, _CAC, "AllowanceCharge"),
        _add_child(ac, _CBC, "ChargeIndicator", "true"),
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", "01"),
        _add_child(ac, _CBC, "BaseAmount", "0", {"currencyID": "Catalog2.PEN"}),
    )),
    # ERROR 3019: TaxInclusiveAmount formato inválido
    ("3019", lambda r: _set_text(r, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", "0")),
    # ERROR 3020: TaxAmount global formato inválido
    ("3020", lambda r: _set_text(r, "cac:TaxTotal/cbc:TaxAmount", "0")),
    # ERROR 3021: TaxAmount de línea formato inválido
    ("3021", lambda r: _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cbc:TaxAmount", "0")),
    # ERROR 3024: TaxTotal global duplicado
    ("3024", lambda r: r.insert(0, deepcopy(_find(r, "cac:TaxTotal")))),
    # ERROR 3025: MultiplierFactorNumeric global inválido
    ("3025", lambda r: (
        ac := _add_child(r, _CAC, "AllowanceCharge"),
        _add_child(ac, _CBC, "ChargeIndicator", "true"),
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", "01"),
        _add_child(ac, _CBC, "MultiplierFactorNumeric", "0"),
    )),
    # ERROR 3026: TaxTotal de línea duplicado
    ("3026", lambda r: _line(r).append(deepcopy(_find(r, "cac:CreditNoteLine/cac:TaxTotal")))),
    # ERROR 3030: serie F modifica factura sin AddressTypeCode
    ("3030", lambda r: (
        _set_serie(r, "F001"),
        _set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01"),
        _remove(r, "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cac:RegistrationAddress/cbc:AddressTypeCode"),
    )),
    # ERROR 3031: TaxableAmount de línea inválido
    ("3031", lambda r: _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "0")),
    # ERROR 3050: TaxExemptionReasonCode en ISC
    ("3050", lambda r: (
        _set_line_tax_code(r, "2000"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "10.00"),
    )),
    # ERROR 3052: MultiplierFactorNumeric de línea inválido
    ("3052", lambda r: (
        ac := _add_child(_line(r), _CAC, "AllowanceCharge"),
        _add_child(ac, _CBC, "ChargeIndicator", "true"),
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", "47"),
        _add_child(ac, _CBC, "MultiplierFactorNumeric", "0"),
    )),
    # ERROR 3053: BaseAmount de línea inválido
    ("3053", lambda r: (
        ac := _add_child(_line(r), _CAC, "AllowanceCharge"),
        _add_child(ac, _CBC, "ChargeIndicator", "true"),
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", "47"),
        _add_child(ac, _CBC, "BaseAmount", "0", {"currencyID": "Catalog2.PEN"}),
    )),
    # ERROR 3059: código de tributo global vacío
    ("3059", lambda r: _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "")),
    # ERROR 3065: concepto 3059 sin StartDate
    ("3065", lambda r: (
        prop := _add_child(_find(r, "cac:CreditNoteLine/cac:Item"), _CAC, "AdditionalItemProperty"),
        _add_child(prop, _CBC, "NameCode", "3059"),
    )),
    # ERROR 3067: código de tributo repetido en línea
    ("3067", lambda r: _line(r).find("cac:TaxTotal", namespaces=_NS).append(deepcopy(_find(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal")))),
    # ERROR 3068: código de tributo repetido globalmente
    ("3068", lambda r: _find(r, "cac:TaxTotal").append(deepcopy(_find(r, "cac:TaxTotal/cac:TaxSubtotal")))),
    # ERROR 3072: AllowanceCharge global sin AllowanceChargeReasonCode
    ("3072", lambda r: (
        ac := _add_child(r, _CAC, "AllowanceCharge"),
        _add_child(ac, _CBC, "ChargeIndicator", "true"),
    )),
    # ERROR 3073: AllowanceCharge de línea sin AllowanceChargeReasonCode
    ("3073", lambda r: (
        ac := _add_child(_line(r), _CAC, "AllowanceCharge"),
        _add_child(ac, _CBC, "ChargeIndicator", "true"),
    )),
    # ERROR 3074: AllowanceCharge de línea código 45 con monto 0
    ("3074", lambda r: (
        ac := _add_child(_line(r), _CAC, "AllowanceCharge"),
        _add_child(ac, _CBC, "ChargeIndicator", "true"),
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", "45"),
        _add_child(ac, _CBC, "Amount", "0", {"currencyID": "Catalog2.PEN"}),
    )),
    # ERROR 3089: PartyIdentification del emisor duplicado
    ("3089", lambda r: (
        party := _find(r, "cac:AccountingSupplierParty/cac:Party"),
        party.append(deepcopy(_find(r, "cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification"))),
    )),
    # ERROR 3090: PartyIdentification del adquiriente duplicado
    ("3090", lambda r: (
        party := _find(r, "cac:AccountingCustomerParty/cac:Party"),
        party.append(deepcopy(_find(r, "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification"))),
    )),
    # ERROR 3092: AllowanceCharge global código 45 sin BaseAmount > 0
    ("3092", lambda r: (
        ac := _add_child(r, _CAC, "AllowanceCharge"),
        _add_child(ac, _CBC, "ChargeIndicator", "true"),
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", "45"),
    )),
    # ERROR 3093: operación 2001 contado sin cargo percepción
    ("3093", lambda r: (
        _set_operation_type(r, "2001"),
        pt := _add_child(r, _CAC, "PaymentTerms"),
        _add_child(pt, _CBC, "ID", "FormaPago"),
        _add_child(pt, _CBC, "PaymentMeansID", "Contado"),
    )),
    # ERROR 3098: operación 0201 sin Delivery/Country/IdentificationCode
    ("3098", lambda r: (
        _set_operation_type(r, "0201"),
        delivery := _add_child(r, _CAC, "Delivery"),
        dl := _add_child(delivery, _CAC, "DeliveryLocation"),
        addr := _add_child(dl, _CAC, "Address"),
        country := _add_child(addr, _CAC, "Country"),
        _add_child(country, _CBC, "IdentificationCode", ""),
    )),
    # ERROR 3102: Percent formato inválido
    ("3102", lambda r: _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent", "abc")),
    # ERROR 3103: TaxAmount no cuadra con percent * base
    ("3103", lambda r: _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "5.00")),
    # ERROR 3104: Percent ISC == 0
    ("3104", lambda r: (
        _set_line_tax_code(r, "2000"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent", "0.00"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "10.00"),
    )),
    # ERROR 3105: línea sin tributo IGV-like
    ("3105", lambda r: (
        _set_line_tax_code(r, "2000"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", ""),
    )),
    # ERROR 3106: resp_code 12 con tributo 1000 global
    ("3106", lambda r: _set_resp_code(r, "12")),
    # ERROR 3107: resp_code 11 con tributo 1000 global
    ("3107", lambda r: _set_resp_code(r, "11")),
    # ERROR 3108: ISC no cuadra
    ("3108", lambda r: (
        _set_line_tax_code(r, "2000"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "5.00"),
        _add_child(_find(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory"), _CBC, "TierRange", "01"),
    )),
    # ERROR 3109: Otros tributos no cuadra
    ("3109", lambda r: (
        _set_line_tax_code(r, "9999"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "5.00"),
    )),
    # ERROR 3110: exonerada con monto != 0
    ("3110", lambda r: (
        _set_line_tax_code(r, "9997"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "10.00"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "20"),
    )),
    # ERROR 3111: gravada con monto == 0
    ("3111", lambda r: _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0.00")),
    # ERROR 3112: gratuita inafecta/exportación con monto != 0
    ("3112", lambda r: (
        _set_line_tax_code(r, "9996"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "10.00"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "100.00"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "21"),
    )),
    # ERROR 3113: gravada con monto == 0
    ("3113", lambda r: _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0.00")),
    # ERROR 3114: indicador false para código 47
    ("3114", lambda r: (
        ac := _add_child(_line(r), _CAC, "AllowanceCharge"),
        _add_child(ac, _CBC, "ChargeIndicator", "false"),
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", "47"),
    )),
    # ERROR 3115: unitCode != TNE en operación 1004
    ("3115", lambda r: (
        _set_operation_type(r, "1004"),
        _set_attr(r, "cac:CreditNoteLine/cbc:CreditedQuantity", "unitCode", "NIU"),
    )),
    # ERROR 3117: falta dirección origen en operación 1004
    ("3117", lambda r: (
        _set_operation_type(r, "1004"),
        delivery := _add_child(_line(r), _CAC, "Delivery"),
        despatch := _add_child(delivery, _CAC, "Despatch"),
        addr := _add_child(despatch, _CAC, "DespatchAddress"),
        _add_child(addr, _CAC, "AddressLine"),
    )),
    # ERROR 3118: falta ubigeo destino en operación 1004
    ("3118", lambda r: (
        _set_operation_type(r, "1004"),
        delivery := _add_child(_line(r), _CAC, "Delivery"),
        dl := _add_child(delivery, _CAC, "DeliveryLocation"),
        addr := _add_child(dl, _CAC, "Address"),
        _add_child(addr, _CBC, "ID", ""),
    )),
    # ERROR 3119: falta dirección destino en operación 1004
    ("3119", lambda r: (
        _set_operation_type(r, "1004"),
        delivery := _add_child(_line(r), _CAC, "Delivery"),
        dl := _add_child(delivery, _CAC, "DeliveryLocation"),
        addr := _add_child(dl, _CAC, "Address"),
        _add_child(addr, _CBC, "ID", "150101"),
    )),
    # ERROR 3120: falta detalle del viaje en operación 1004
    ("3120", lambda r: (
        _set_operation_type(r, "1004"),
        delivery := _add_child(_line(r), _CAC, "Delivery"),
        despatch := _add_child(delivery, _CAC, "Despatch"),
        _add_child(despatch, _CBC, "Instructions", ""),
    )),
    # ERROR 3223: combinación de tributos no permitida
    ("3223", lambda r: (
        _add_line_tax_subtotal(r, "9997", "50.00", "0.00", "0.00"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal[2]/cac:TaxCategory/cbc:TaxExemptionReasonCode", "20"),
    )),
    # ERROR 3224: price type 02 en operación no gratuita
    ("3224", lambda r: (
        pr := _find(r, "cac:CreditNoteLine/cac:PricingReference"),
        alt := _add_child(pr, _CAC, "AlternativeConditionPrice"),
        _add_child(alt, _CBC, "PriceAmount", "50.00", {"currencyID": "Catalog2.PEN"}),
        _add_child(alt, _CBC, "PriceTypeCode", "02"),
    )),
    # ERROR 3234: gratuita sin price type 02
    ("3234", lambda r: (
        _set_line_tax_code(r, "9996"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0.00"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "100.00"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", "11"),
    )),
    # ERROR 3270: precio unitario no cuadra
    ("3270", lambda r: (
        _set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01"),
        _set_text(r, "cac:CreditNoteLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount", "200.00"),
    )),
    # ERROR 3271: valor de venta no cuadra
    ("3271", lambda r: (
        _set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01"),
        _set_text(r, "cac:CreditNoteLine/cbc:LineExtensionAmount", "50.00"),
    )),
    # ERROR 3272: base imponible no cuadra
    ("3272", lambda r: (
        _set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "50.00"),
        _set_text(r, "cac:CreditNoteLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "9.00"),
    )),
    # ERROR 3273: total exportación no cuadra
    ("3273", lambda r: (
        _set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "9995"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0.00"),
    )),
    # ERROR 3274: total inafectas no cuadra
    ("3274", lambda r: (
        _set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "9998"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0.00"),
    )),
    # ERROR 3275: total exoneradas no cuadra
    ("3275", lambda r: (
        _set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "9997"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0.00"),
    )),
    # ERROR 3276: total gratuitas no cuadra
    ("3276", lambda r: (
        _set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", "9996"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "0.00"),
    )),
    # ERROR 3277: total gravadas no cuadra
    ("3277", lambda r: (
        _set_text(r, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", "01"),
        _set_text(r, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "50.00"),
    )),
    # ERROR 3278: LineExtensionAmount global no cuadra
    ("3278", lambda r: _set_text(r, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount", "50.00")),
    # ERROR 3279: TaxInclusiveAmount no cuadra
    ("3279", lambda r: _set_text(r, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", "50.00")),
    # ERROR 3282: descuento anticipo sin PrepaidAmount
    ("3282", lambda r: (
        ac := _add_child(r, _CAC, "AllowanceCharge"),
        _add_child(ac, _CBC, "ChargeIndicator", "false"),
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", "04"),
        _add_child(ac, _CBC, "Amount", "10.00", {"currencyID": "Catalog2.PEN"}),
    )),
])
def test_credit_note_extra_rule(code, mutator):
    root = _valid_credit_note_root()
    mutator(root)
    errors = validate_credit_note_extra(root, [])
    codes = [e.code for e in errors]
    assert code in codes, f"Expected error {code} in {codes}"


def test_credit_note_extra_valid():
    root = _valid_credit_note_root()
    errors = validate_credit_note_extra(root, [])
    assert errors == []
