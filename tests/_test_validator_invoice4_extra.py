"""Tests parametrizados para validaciones SUNAT de Invoice - lote 4.

Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
https://cpe.sunat.gob.pe/guias-y-manuales
"""

from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest
from lxml import etree

from openubl.models import (
    Catalog2,
    Catalog6,
    Catalog51,
    Catalog7,
    Cliente,
    DocumentoVentaDetalle,
    Invoice,
    Proveedor,
)
from openubl.enricher import ContentEnricher
from openubl.renderer import render_invoice
from openubl.validators._extra_invoice4 import validate_invoice_extra4
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


def _set_attr(root: etree._Element, xpath: str, attr: str, value: str) -> None:
    elem = _find(root, xpath)
    if elem is not None:
        elem.set(attr, value)


def _remove(root: etree._Element, xpath: str) -> None:
    elem = _find(root, xpath)
    if elem is not None:
        elem.getparent().remove(elem)


def _add_child(
    parent: etree._Element,
    uri: str,
    tag: str,
    text: str | None = None,
    attrs: dict | None = None,
) -> etree._Element:
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
        proveedor=Proveedor(ruc="20000000001", razonSocial="Empresa SAC"),
        cliente=Cliente(
            nombre="Cliente",
            numeroDocumentoIdentidad="12345678",
            tipoDocumentoIdentidad=Catalog6.DNI,
        ),
        detalles=[
            DocumentoVentaDetalle(
                descripcion="Producto",
                cantidad=Decimal("2"),
                precio=Decimal("50"),
                tipoAfectacionIGV=Catalog7.GRAVADO_OPERACION_ONEROSA,
            ),
        ],
        fechaEmision=date(2026, 6, 14),
        moneda=Catalog2.PEN,
        tipoOperacion=Catalog51.VENTA_INTERNA,
    )
    ContentEnricher().enrich(doc)
    xml = render_invoice(doc)
    return etree.fromstring(xml.encode("utf-8"))


@pytest.fixture
def root():
    return _valid_invoice_root()


# ---------------------------------------------------------------------------
# Helpers para construir estructuras UBL
# ---------------------------------------------------------------------------


def _set_tipo_operacion(root: etree._Element, op: str) -> None:
    _set_text(root, "cbc:Note", op)
    _set_attr(root, "cbc:InvoiceTypeCode", "listID", op)


def _first_line(root: etree._Element) -> etree._Element | None:
    return _find(root, "cac:InvoiceLine")


def _add_additional_item_property(
    line: etree._Element, code: str, value: str | None = None
) -> etree._Element:
    prop = _add_child(line, _CAC, "AdditionalItemProperty")
    _add_child(prop, _CBC, "NameCode", code)
    if value is not None:
        _add_child(prop, _CBC, "Value", value)
    return prop


def _add_despatch_document_reference(
    root: etree._Element, ref_id: str, doc_type: str
) -> etree._Element:
    ref = _add_child(root, _CAC, "DespatchDocumentReference")
    _add_child(ref, _CBC, "ID", ref_id)
    _add_child(ref, _CBC, "DocumentTypeCode", doc_type)
    return ref


def _add_additional_document_reference(
    root: etree._Element,
    ref_id: str,
    doc_type: str,
    contract_type: str | None = None,
    description: str | None = None,
    percent: str | None = None,
) -> etree._Element:
    ref = _add_child(root, _CAC, "AdditionalDocumentReference")
    _add_child(ref, _CBC, "ID", ref_id)
    _add_child(ref, _CBC, "DocumentTypeCode", doc_type)
    if contract_type is not None:
        _add_child(ref, _CBC, "DocumentType", contract_type)
    if description is not None:
        _add_child(ref, _CBC, "DocumentDescription", description)
    if percent is not None:
        sh = _add_child(ref, _CAC, "ShareholderParty")
        _add_child(sh, _CBC, "PartecipationPercent", percent)
    return ref


def _add_additional_item_property(
    line: etree._Element, code: str, value: str | None = None
) -> etree._Element | None:
    item = _find(line, "cac:Item")
    if item is None:
        return None
    prop = _add_child(item, _CAC, "AdditionalItemProperty")
    _add_child(prop, _CBC, "NameCode", code)
    if value is not None:
        _add_child(prop, _CBC, "Value", value)
    return prop


def _add_allowance_charge(
    root: etree._Element, indicator: str, reason_code: str
) -> etree._Element:
    ac = _add_child(root, _CAC, "AllowanceCharge")
    _add_child(ac, _CBC, "ChargeIndicator", indicator)
    _add_child(ac, _CBC, "AllowanceChargeReasonCode", reason_code)
    return ac


def _add_delivery_country(root: etree._Element, country_code: str) -> etree._Element:
    delivery = _add_child(root, _CAC, "Delivery")
    loc = _add_child(delivery, _CAC, "DeliveryLocation")
    addr = _add_child(loc, _CAC, "Address")
    country = _add_child(addr, _CAC, "Country")
    _add_child(country, _CBC, "IdentificationCode", country_code)
    return delivery


# ---------------------------------------------------------------------------
# Mutadores por código SUNAT
# ---------------------------------------------------------------------------


def _m1003(root: etree._Element) -> None:
    _set_text(root, "cbc:InvoiceTypeCode", "99")


def _m2364(root: etree._Element) -> None:
    _add_despatch_document_reference(root, "T001-123", "09")
    _add_despatch_document_reference(root, "T001-123", "09")


def _m2365(root: etree._Element) -> None:
    _add_additional_document_reference(root, "DOC-001", "50")
    _add_additional_document_reference(root, "DOC-001", "50")


def _m2410(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceTypeCode", "03")


def _m2595(root: etree._Element) -> None:
    line = _first_line(root)
    if line is not None:
        _add_additional_item_property(line, "7010")


def _m2596(root: etree._Element) -> None:
    line = _first_line(root)
    if line is not None:
        _add_additional_item_property(line, "7011")


def _m2597(root: etree._Element) -> None:
    line = _first_line(root)
    if line is not None:
        _add_additional_item_property(line, "7013")


def _m2954(root: etree._Element) -> None:
    line = _first_line(root)
    if line is not None:
        ac = _add_child(line, _CAC, "AllowanceCharge")
        _add_child(ac, _CBC, "AllowanceChargeReasonCode", "99")


def _m3051(root: etree._Element) -> None:
    _set_text(root, "cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name", "IVA")


def _m3064(root: etree._Element) -> None:
    line = _first_line(root)
    if line is not None:
        _add_additional_item_property(line, "4000")


def _m3088(root: etree._Element) -> None:
    _set_text(root, "cbc:DocumentCurrencyCode", "ZZZ")


def _m3099(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0201")
    _add_delivery_country(root, "ZZ")


def _m3136(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0202")
    line = _first_line(root)
    if line is not None:
        for code in ("4008", "4000", "4007", "4001", "4002", "4003", "4004", "4006", "4005"):
            _add_additional_item_property(line, code, "x")


def _m3137(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0202")
    line = _first_line(root)
    if line is not None:
        for code in ("4009", "4000", "4007", "4001", "4002", "4003", "4004", "4006", "4005"):
            _add_additional_item_property(line, code, "x")


def _m3138(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0202")
    line = _first_line(root)
    if line is not None:
        for code in ("4009", "4008", "4007", "4001", "4002", "4003", "4004", "4006", "4005"):
            _add_additional_item_property(line, code, "x")


def _m3139(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0202")
    line = _first_line(root)
    if line is not None:
        for code in ("4009", "4008", "4000", "4001", "4002", "4003", "4004", "4006", "4005"):
            _add_additional_item_property(line, code, "x")


def _m3140(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0202")
    line = _first_line(root)
    if line is not None:
        for code in ("4009", "4008", "4000", "4007", "4002", "4003", "4004", "4006", "4005"):
            _add_additional_item_property(line, code, "x")


def _m3141(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0202")
    line = _first_line(root)
    if line is not None:
        for code in ("4009", "4008", "4000", "4007", "4001", "4003", "4004", "4006", "4005"):
            _add_additional_item_property(line, code, "x")


def _m3142(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0202")
    line = _first_line(root)
    if line is not None:
        for code in ("4009", "4008", "4000", "4007", "4001", "4002", "4004", "4006", "4005"):
            _add_additional_item_property(line, code, "x")


def _m3143(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0202")
    line = _first_line(root)
    if line is not None:
        for code in ("4009", "4008", "4000", "4007", "4001", "4002", "4003", "4006", "4005"):
            _add_additional_item_property(line, code, "x")


def _m3144(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0202")
    line = _first_line(root)
    if line is not None:
        for code in ("4009", "4008", "4000", "4007", "4001", "4002", "4003", "4004", "4005"):
            _add_additional_item_property(line, code, "x")


def _m3145(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0202")
    line = _first_line(root)
    if line is not None:
        for code in ("4009", "4008", "4000", "4007", "4001", "4002", "4003", "4004", "4006"):
            _add_additional_item_property(line, code, "x")


def _m3157(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0302")
    party = _find(root, "cac:AccountingSupplierParty/cac:Party")
    if party is not None:
        agent = _add_child(party, _CAC, "AgentParty")
        pi = _add_child(agent, _CAC, "PartyIdentification")
        _add_child(pi, _CBC, "ID", "12345678")
    line = _first_line(root)
    if line is not None:
        for code in _BVME_CODES:
            _add_additional_item_property(line, code, "x")


_BVME_CODES = ["4040", "4041", "4049", "4042", "4043", "4044", "4045", "4046", "4047", "4048"]


def _m3159(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0302")
    line = _first_line(root)
    if line is not None:
        for code in [c for c in _BVME_CODES if c != "4040"]:
            _add_additional_item_property(line, code, "x")


def _m3160(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0302")
    line = _first_line(root)
    if line is not None:
        for code in [c for c in _BVME_CODES if c != "4041"]:
            _add_additional_item_property(line, code, "x")


def _m3161(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0302")
    line = _first_line(root)
    if line is not None:
        for code in [c for c in _BVME_CODES if c != "4042"]:
            _add_additional_item_property(line, code, "x")


def _m3162(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0302")
    line = _first_line(root)
    if line is not None:
        for code in [c for c in _BVME_CODES if c != "4043"]:
            _add_additional_item_property(line, code, "x")


def _m3163(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0302")
    line = _first_line(root)
    if line is not None:
        for code in [c for c in _BVME_CODES if c != "4044"]:
            _add_additional_item_property(line, code, "x")


def _m3164(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0302")
    line = _first_line(root)
    if line is not None:
        for code in [c for c in _BVME_CODES if c != "4045"]:
            _add_additional_item_property(line, code, "x")


def _m3165(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0302")
    line = _first_line(root)
    if line is not None:
        for code in [c for c in _BVME_CODES if c != "4046"]:
            _add_additional_item_property(line, code, "x")


def _m3166(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0302")
    line = _first_line(root)
    if line is not None:
        for code in [c for c in _BVME_CODES if c != "4047"]:
            _add_additional_item_property(line, code, "x")


def _m3167(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0302")
    line = _first_line(root)
    if line is not None:
        for code in [c for c in _BVME_CODES if c != "4048"]:
            _add_additional_item_property(line, code, "x")


def _m3204(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0302")
    line = _first_line(root)
    if line is not None:
        for code in [c for c in _BVME_CODES if c != "4049"]:
            _add_additional_item_property(line, code, "x")


def _m3168(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0301")
    line = _first_line(root)
    if line is not None:
        for code in ("4031", "4032", "4033"):
            _add_additional_item_property(line, code, "x")


def _m3169(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0301")
    line = _first_line(root)
    if line is not None:
        for code in ("4030", "4032", "4033"):
            _add_additional_item_property(line, code, "x")


def _m3170(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0301")
    line = _first_line(root)
    if line is not None:
        for code in ("4030", "4031", "4033"):
            _add_additional_item_property(line, code, "x")


def _m3171(root: etree._Element) -> None:
    _set_tipo_operacion(root, "0301")
    line = _first_line(root)
    if line is not None:
        for code in ("4030", "4031", "4032"):
            _add_additional_item_property(line, code, "x")


def _m3206(root: etree._Element) -> None:
    _set_tipo_operacion(root, "9999")


def _m3236(root: etree._Element) -> None:
    line = _first_line(root)
    if line is not None:
        ts = _add_child(line, _CAC, "TaxTotal")
        st = _add_child(ts, _CAC, "TaxSubtotal")
        _add_child(st, _CBC, "BaseUnitMeasure", "KGM")
        tc = _add_child(st, _CAC, "TaxCategory")
        tsc = _add_child(tc, _CAC, "TaxScheme")
        _add_child(tsc, _CBC, "ID", "7152")


def _m3237(root: etree._Element) -> None:
    line = _first_line(root)
    if line is not None:
        ts = _add_child(line, _CAC, "TaxTotal")
        st = _add_child(ts, _CAC, "TaxSubtotal")
        tc = _add_child(st, _CAC, "TaxCategory")
        tsc = _add_child(tc, _CAC, "TaxScheme")
        _add_child(tsc, _CBC, "ID", "7152")


def _m3238(root: etree._Element) -> None:
    line = _first_line(root)
    if line is not None:
        ts = _add_child(line, _CAC, "TaxTotal")
        st = _add_child(ts, _CAC, "TaxSubtotal")
        _add_child(st, _CBC, "BaseUnitMeasure", "NIU")
        _add_child(st, _CBC, "PerUnitAmount", "0.00")
        tc = _add_child(st, _CAC, "TaxCategory")
        tsc = _add_child(tc, _CAC, "TaxScheme")
        _add_child(tsc, _CBC, "ID", "7152")


def _m3316(root: etree._Element) -> None:
    _set_tipo_operacion(root, "2002")


def _m3317(root: etree._Element) -> None:
    _add_allowance_charge(root, "false", "63")


def _m3497(root: etree._Element) -> None:
    _add_additional_document_reference(
        root,
        ref_id="C-001",
        doc_type="07",
        contract_type="3",
        description="Contrato",
        percent="50.00",
    )


def _m3498(root: etree._Element) -> None:
    _add_additional_document_reference(
        root,
        ref_id="C-001",
        doc_type="07",
        contract_type="1",
        description="Contrato",
        percent="50.00",
    )
    _add_additional_document_reference(
        root,
        ref_id="C-002",
        doc_type="07",
        contract_type="1",
        description="Contrato",
        percent="50.00",
    )


def _m3499(root: etree._Element) -> None:
    ref = _add_child(root, _CAC, "AdditionalDocumentReference")
    _add_child(ref, _CBC, "ID", "C-001")
    _add_child(ref, _CBC, "DocumentTypeCode", "07")


def _m3500(root: etree._Element) -> None:
    _add_additional_document_reference(
        root,
        ref_id="C-001",
        doc_type="07",
        contract_type="1",
        description="Contrato",
        percent="1234",
    )


def _m3501(root: etree._Element) -> None:
    _add_additional_document_reference(
        root,
        ref_id="C-001-C-001-C-001-C-001-C-001",
        doc_type="07",
        contract_type="1",
        description="Contrato",
        percent="50.00",
    )


def _m3502(root: etree._Element) -> None:
    _add_additional_document_reference(
        root,
        ref_id="C-001",
        doc_type="07",
        contract_type="1",
        description="x" * 101,
        percent="50.00",
    )


MUTATORS = [
    ("1003", _m1003),
    ("2364", _m2364),
    ("2365", _m2365),
    ("2410", _m2410),
    ("2595", _m2595),
    ("2596", _m2596),
    ("2597", _m2597),
    ("2954", _m2954),
    ("3051", _m3051),
    ("3064", _m3064),
    ("3088", _m3088),
    ("3099", _m3099),
    ("3136", _m3136),
    ("3137", _m3137),
    ("3138", _m3138),
    ("3139", _m3139),
    ("3140", _m3140),
    ("3141", _m3141),
    ("3142", _m3142),
    ("3143", _m3143),
    ("3144", _m3144),
    ("3145", _m3145),
    ("3157", _m3157),
    ("3159", _m3159),
    ("3160", _m3160),
    ("3161", _m3161),
    ("3162", _m3162),
    ("3163", _m3163),
    ("3164", _m3164),
    ("3165", _m3165),
    ("3166", _m3166),
    ("3167", _m3167),
    ("3168", _m3168),
    ("3169", _m3169),
    ("3170", _m3170),
    ("3171", _m3171),
    ("3204", _m3204),
    ("3206", _m3206),
    ("3236", _m3236),
    ("3237", _m3237),
    ("3238", _m3238),
    ("3316", _m3316),
    ("3317", _m3317),
    ("3497", _m3497),
    ("3498", _m3498),
    ("3499", _m3499),
    ("3500", _m3500),
    ("3501", _m3501),
    ("3502", _m3502),
]


@pytest.mark.parametrize("code,mutator", MUTATORS)
def test_invoice_extra4(code: str, mutator, root: etree._Element) -> None:
    mutator(root)
    errs: list = []
    validate_invoice_extra4(root, errs)
    codes = [e.code for e in errs]
    assert code in codes, f"Expected error {code} in {codes}"
