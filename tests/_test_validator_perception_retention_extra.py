"""Tests parametrizados para validaciones SUNAT extra de Perception y Retention.

Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
https://cpe.sunat.gob.pe/guias-y-manuales
"""

from datetime import date
from decimal import Decimal

import pytest
from lxml import etree

from openubl.models import Cliente, PercepcionRetencionOperacion, Perception, Proveedor, Retention
from openubl.models.perception import ComprobanteAfectado
from openubl.renderer import render_perception, render_retention
from openubl.validators._extra_perception_retention import (
    validate_perception_extra,
    validate_retention_extra,
)


_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
_SAC = "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"

R_NS = {
    "cac": _CAC,
    "cbc": _CBC,
    "sac": _SAC,
}

P_NS = {
    "cac": _CAC,
    "cbc": _CBC,
    "sac": _SAC,
}


def _set_text(root: etree._Element, xpath: str, value: str, ns: dict) -> None:
    elem = root.xpath(xpath, namespaces=ns)[0]
    elem.text = value


def _set_attr(root: etree._Element, xpath: str, attr: str, value: str, ns: dict) -> None:
    elem = root.xpath(xpath, namespaces=ns)[0]
    elem.set(attr, value)


def _remove_attr(root: etree._Element, xpath: str, attr: str, ns: dict) -> None:
    elem = root.xpath(xpath, namespaces=ns)[0]
    if attr in elem.attrib:
        del elem.attrib[attr]


def _add_child(parent: etree._Element, ns_uri: str, tag: str, text: str | None = None, attrs: dict | None = None) -> etree._Element:
    child = etree.SubElement(parent, f"{{{ns_uri}}}{tag}")
    if text is not None:
        child.text = text
    if attrs:
        for k, v in attrs.items():
            child.set(k, v)
    return child


def _valid_retention_xml() -> str:
    r = Retention(
        serie="R001",
        numero=1,
        fechaEmision=date(2024, 1, 1),
        proveedor=Proveedor(ruc="20100066603", razonSocial="Agente S.A.C."),
        cliente=Cliente(nombre="Cliente SAC", numeroDocumentoIdentidad="20100066604", tipoDocumentoIdentidad="6"),
        importeTotalRetenido=Decimal("30.00"),
        importeTotalPagado=Decimal("270.00"),
        tipoRegimen="01",
        tipoRegimenPorcentaje=Decimal("3"),
        operaciones=[
            PercepcionRetencionOperacion(
                numeroOperacion=1,
                fechaOperacion=date(2024, 1, 1),
                importeOperacion=Decimal("10.00"),
                comprobante=ComprobanteAfectado(
                    tipoComprobante="01",
                    serieNumero="F001-1",
                    fechaEmision=date(2024, 1, 1),
                    importeTotal=Decimal("100.00"),
                    moneda="PEN",
                ),
            ),
        ],
    )
    return render_retention(r)


def _valid_perception_xml() -> str:
    p = Perception(
        serie="P001",
        numero=1,
        fechaEmision=date(2024, 1, 1),
        proveedor=Proveedor(ruc="20100066603", razonSocial="Agente S.A.C."),
        cliente=Cliente(nombre="Cliente SAC", numeroDocumentoIdentidad="12121212121", tipoDocumentoIdentidad="6"),
        importeTotalPercibido=Decimal("30.00"),
        importeTotalCobrado=Decimal("270.00"),
        tipoRegimen="01",
        tipoRegimenPorcentaje=Decimal("1"),
        operaciones=[
            PercepcionRetencionOperacion(
                numeroOperacion=1,
                fechaOperacion=date(2024, 1, 1),
                importeOperacion=Decimal("10.00"),
                comprobante=ComprobanteAfectado(
                    tipoComprobante="01",
                    serieNumero="F001-1",
                    fechaEmision=date(2024, 1, 1),
                    importeTotal=Decimal("100.00"),
                    moneda="PEN",
                ),
            ),
        ],
    )
    return render_perception(p)


def _r_add_agent_country(root: etree._Element, country: str) -> None:
    agent = root.xpath(".//cac:AgentParty", namespaces=R_NS)[0]
    pa = _add_child(agent, _CAC, "PostalAddress")
    c = _add_child(pa, _CAC, "Country")
    _add_child(c, _CBC, "IdentificationCode", country)


def _r_add_receiver_country(root: etree._Element, country: str) -> None:
    receiver = root.xpath(".//cac:ReceiverParty", namespaces=R_NS)[0]
    pa = _add_child(receiver, _CAC, "PostalAddress")
    c = _add_child(pa, _CAC, "Country")
    _add_child(c, _CBC, "IdentificationCode", country)


def _r_set_doc_ref_id(root: etree._Element, value: str) -> None:
    ref = root.xpath(".//sac:SUNATRetentionDocumentReference/cbc:ID", namespaces=R_NS)[0]
    ref.text = value


def _r_set_doc_ref_type(root: etree._Element, value: str) -> None:
    ref = root.xpath(".//sac:SUNATRetentionDocumentReference/cbc:ID", namespaces=R_NS)[0]
    ref.set("schemeID", value)


class TestPerceptionExtra:
    def test_perception_extra_valid(self):
        root = etree.fromstring(_valid_perception_xml().encode("utf-8"))
        errors: list = []
        validate_perception_extra(root, errors)
        assert errors == []


class TestRetentionExtra:
    @pytest.mark.parametrize(
        "code,mutator",
        [
            ("1001", lambda r: _set_text(r, ".//cbc:ID", "INVALID", R_NS)),
            ("2111", lambda r: _set_text(r, ".//cbc:UBLVersionID", "", R_NS)),
            ("2110", lambda r: _set_text(r, ".//cbc:UBLVersionID", "2.1", R_NS)),
            ("2113", lambda r: _set_text(r, ".//cbc:CustomizationID", "", R_NS)),
            ("2112", lambda r: _set_text(r, ".//cbc:CustomizationID", "2.0", R_NS)),
            ("2678", lambda r: _remove_attr(r, ".//cac:AgentParty/cac:PartyIdentification/cbc:ID", "schemeID", R_NS)),
            ("2511", lambda r: _set_attr(r, ".//cac:AgentParty/cac:PartyIdentification/cbc:ID", "schemeID", "1", R_NS)),
            ("1037", lambda r: _set_text(r, ".//cac:AgentParty/cac:PartyLegalEntity/cbc:RegistrationName", "", R_NS)),
            ("1038", lambda r: _set_text(r, ".//cac:AgentParty/cac:PartyLegalEntity/cbc:RegistrationName", "x" * 1501, R_NS)),
            ("2548", lambda r: _r_add_agent_country(r, "US")),
            ("2516", lambda r: _remove_attr(r, ".//cac:ReceiverParty/cac:PartyIdentification/cbc:ID", "schemeID", R_NS)),
            ("2134", lambda r: _set_text(r, ".//cac:ReceiverParty/cac:PartyLegalEntity/cbc:RegistrationName", "", R_NS)),
            ("2133", lambda r: _set_text(r, ".//cac:ReceiverParty/cac:PartyLegalEntity/cbc:RegistrationName", "x" * 1501, R_NS)),
            ("2548", lambda r: _r_add_receiver_country(r, "US")),
            ("2669", lambda r: _set_text(r, ".//cbc:TotalInvoiceAmount", "0.00", R_NS)),
            ("2691", lambda r: _remove_attr(r, ".//sac:SUNATRetentionDocumentReference/cbc:ID", "schemeID", R_NS)),
            ("2692", lambda r: _set_attr(r, ".//sac:SUNATRetentionDocumentReference/cbc:ID", "schemeID", "99", R_NS)),
            ("2693", lambda r: _r_set_doc_ref_id(r, "")),
            ("2694", lambda r: _r_set_doc_ref_id(r, "INVALID")),
            ("2694", lambda r: (_r_set_doc_ref_type(r, "12"), _r_set_doc_ref_id(r, "INVALID"))[0]),
            ("2696", lambda r: _set_text(r, ".//sac:SUNATRetentionDocumentReference/cbc:TotalInvoiceAmount", "0.00", R_NS)),
        ],
    )
    def test_retention_extra_rule(self, code, mutator):
        root = etree.fromstring(_valid_retention_xml().encode("utf-8"))
        mutator(root)
        errors: list = []
        validate_retention_extra(root, errors)
        codes = [e.code for e in errors]
        assert code in codes, f"Expected error {code} in {codes}"

    def test_retention_extra_valid(self):
        root = etree.fromstring(_valid_retention_xml().encode("utf-8"))
        errors: list = []
        validate_retention_extra(root, errors)
        assert errors == []
