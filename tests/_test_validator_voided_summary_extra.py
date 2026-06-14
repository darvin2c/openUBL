"""
Tests parametrizados para las reglas extra de VoidedDocuments y SummaryDocuments.

Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
https://cpe.sunat.gob.pe/guias-y-manuales
"""

from copy import deepcopy

import pytest
from lxml import etree

from openubl.validators._extra_voided_summary import (
    validate_summary_documents_extra,
    validate_voided_documents_extra,
)


NS_VOIDED = {
    "": "urn:sunat:names:specification:ubl:peru:schema:xsd:VoidedDocuments-1",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
}

NS_SUMMARY = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
}

_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
_SAC = "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"


def _valid_voided_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<VoidedDocuments xmlns="urn:sunat:names:specification:ubl:peru:schema:xsd:VoidedDocuments-1"'
        ' xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"'
        ' xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"'
        ' xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1">'
        '<cbc:UBLVersionID>2.0</cbc:UBLVersionID>'
        '<cbc:CustomizationID>1.0</cbc:CustomizationID>'
        '<cbc:ID>RA-20240101-1</cbc:ID>'
        '<cbc:ReferenceDate>2024-01-01</cbc:ReferenceDate>'
        '<cbc:IssueDate>2024-01-01</cbc:IssueDate>'
        '<cac:AccountingSupplierParty>'
        '<cbc:CustomerAssignedAccountID>20100066603</cbc:CustomerAssignedAccountID>'
        '<cbc:AdditionalAccountID>6</cbc:AdditionalAccountID>'
        '<cac:Party><cac:PartyLegalEntity><cbc:RegistrationName>Test SA</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party>'
        '</cac:AccountingSupplierParty>'
        '<sac:VoidedDocumentsLine>'
        '<cbc:LineID>1</cbc:LineID>'
        '<cbc:DocumentTypeCode>01</cbc:DocumentTypeCode>'
        '<cbc:DocumentSerialID>F001</cbc:DocumentSerialID>'
        '<cbc:DocumentNumberID>1</cbc:DocumentNumberID>'
        '<cbc:VoidReasonDescription>Error</cbc:VoidReasonDescription>'
        '</sac:VoidedDocumentsLine>'
        '</VoidedDocuments>'
    )


def _valid_summary_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8"?>
<SummaryDocuments xmlns="urn:sunat:names:specification:ubl:peru:schema:xsd:SummaryDocuments-1"
                  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
                  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
                  xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1">
  <cbc:UBLVersionID>2.0</cbc:UBLVersionID>
  <cbc:CustomizationID>1.1</cbc:CustomizationID>
  <cbc:ID>RC-20240101-1</cbc:ID>
  <cbc:ReferenceDate>2024-01-01</cbc:ReferenceDate>
  <cbc:IssueDate>2024-01-01</cbc:IssueDate>
  <cac:AccountingSupplierParty>
    <cbc:CustomerAssignedAccountID>20100066603</cbc:CustomerAssignedAccountID>
    <cbc:AdditionalAccountID>6</cbc:AdditionalAccountID>
    <cac:Party>
      <cac:PartyLegalEntity>
        <cbc:RegistrationName>Test SA</cbc:RegistrationName>
      </cac:PartyLegalEntity>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <sac:SummaryDocumentsLine>
    <cbc:LineID>1</cbc:LineID>
    <cbc:DocumentTypeCode>03</cbc:DocumentTypeCode>
    <cbc:ID>B001-1</cbc:ID>
    <cac:AccountingCustomerParty>
      <cbc:CustomerAssignedAccountID>12345678</cbc:CustomerAssignedAccountID>
      <cbc:AdditionalAccountID>1</cbc:AdditionalAccountID>
      <cac:Party>
        <cac:PartyLegalEntity>
          <cbc:RegistrationName>Carlos Feria</cbc:RegistrationName>
        </cac:PartyLegalEntity>
      </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:Status>
      <cbc:ConditionCode>1</cbc:ConditionCode>
    </cac:Status>
    <sac:TotalAmount currencyID="PEN">1000.00</sac:TotalAmount>
    <sac:BillingPayment>
      <cbc:PaidAmount currencyID="PEN">847.46</cbc:PaidAmount>
      <cbc:InstructionID>01</cbc:InstructionID>
    </sac:BillingPayment>
    <cac:TaxTotal>
      <cbc:TaxAmount currencyID="PEN">152.54</cbc:TaxAmount>
      <cac:TaxSubtotal>
        <cbc:TaxAmount currencyID="PEN">152.54</cbc:TaxAmount>
        <cac:TaxCategory>
          <cbc:Percent>18.00</cbc:Percent>
          <cac:TaxScheme>
            <cbc:ID>1000</cbc:ID>
            <cbc:Name>IGV</cbc:Name>
            <cbc:TaxTypeCode>VAT</cbc:TaxTypeCode>
          </cac:TaxScheme>
        </cac:TaxCategory>
      </cac:TaxSubtotal>
    </cac:TaxTotal>
  </sac:SummaryDocumentsLine>
</SummaryDocuments>'''


def _set_text(root: etree._Element, xpath: str, value: str, ns: dict) -> None:
    elem = root.find(xpath, namespaces=ns)
    if elem is None:
        raise ValueError(f"Element not found: {xpath}")
    elem.text = value


def _voided_line(root: etree._Element) -> etree._Element:
    elem = root.find(".//sac:VoidedDocumentsLine", namespaces=NS_VOIDED)
    if elem is None:
        raise ValueError("VoidedDocumentsLine not found")
    return elem


def _summary_line(root: etree._Element, index: int = 0) -> etree._Element:
    elems = root.findall(".//sac:SummaryDocumentsLine", namespaces=NS_SUMMARY)
    if not elems:
        raise ValueError("SummaryDocumentsLine not found")
    return elems[index]




def _add_voided_line(root: etree._Element) -> None:
    line = _voided_line(root)
    new_line = deepcopy(line)
    # Duplica el mismo documento (tipo, serie y número) para simular que ya
    # fue informado anteriormente.
    new_line.find("cbc:LineID", namespaces=NS_VOIDED).text = "2"
    root.append(new_line)


def _add_perception_with_bad_ruc(root: etree._Element) -> None:
    line = _summary_line(root)
    # Cambia adquiriente a RUC con dígito de control inválido.
    cust_type = line.find("cac:AccountingCustomerParty/cbc:AdditionalAccountID", namespaces=NS_SUMMARY)
    if cust_type is not None:
        cust_type.text = "6"
    cust_id = line.find("cac:AccountingCustomerParty/cbc:CustomerAssignedAccountID", namespaces=NS_SUMMARY)
    if cust_id is not None:
        cust_id.text = "20100066604"
    # Agrega información de percepción cuadrada en PEN.
    ref = etree.SubElement(line, f"{{{_SAC}}}SUNATPerceptionSummaryDocumentReference")
    etree.SubElement(ref, f"{{{_SAC}}}SUNATPerceptionSystemCode").text = "01"
    etree.SubElement(ref, f"{{{_SAC}}}SUNATPerceptionPercent").text = "1.80"
    total = etree.SubElement(ref, f"{{{_CBC}}}TotalInvoiceAmount")
    total.set("currencyID", "PEN")
    total.text = "18.00"
    cashed = etree.SubElement(ref, f"{{{_SAC}}}SUNATTotalCashed")
    cashed.set("currencyID", "PEN")
    cashed.text = "1018.00"
    taxable = etree.SubElement(ref, f"{{{_CBC}}}TaxableAmount")
    taxable.set("currencyID", "PEN")
    taxable.text = "1000.00"


def _clone_summary_line(root: etree._Element) -> etree._Element:
    line = _summary_line(root)
    new_line = deepcopy(line)
    root.append(new_line)
    return new_line


def _add_modification_line_no_base(root: etree._Element) -> None:
    new_line = _clone_summary_line(root)
    new_line.find("cbc:LineID", namespaces=NS_SUMMARY).text = "2"
    new_line.find("cbc:DocumentTypeCode", namespaces=NS_SUMMARY).text = "07"
    new_line.find("cbc:ID", namespaces=NS_SUMMARY).text = "B002-5"
    new_line.find("cac:Status/cbc:ConditionCode", namespaces=NS_SUMMARY).text = "2"
    # Agrega referencia a boleta no informada en el resumen.
    billing = etree.SubElement(new_line, f"{{{_CAC}}}BillingReference")
    idr = etree.SubElement(billing, f"{{{_CAC}}}InvoiceDocumentReference")
    id_el = etree.SubElement(idr, f"{{{_CBC}}}ID")
    id_el.text = "B001-10"
    type_el = etree.SubElement(idr, f"{{{_CBC}}}DocumentTypeCode")
    type_el.text = "03"


def _add_modification_line_referencing_anulado(root: etree._Element) -> None:
    # Línea base anulada.
    base = _clone_summary_line(root)
    base.find("cbc:LineID", namespaces=NS_SUMMARY).text = "2"
    base.find("cbc:ID", namespaces=NS_SUMMARY).text = "B001-10"
    base.find("cac:Status/cbc:ConditionCode", namespaces=NS_SUMMARY).text = "3"
    # Línea de modificación que referencia a la anulada.
    mod = _clone_summary_line(root)
    mod.find("cbc:LineID", namespaces=NS_SUMMARY).text = "3"
    mod.find("cbc:DocumentTypeCode", namespaces=NS_SUMMARY).text = "07"
    mod.find("cbc:ID", namespaces=NS_SUMMARY).text = "B002-5"
    mod.find("cac:Status/cbc:ConditionCode", namespaces=NS_SUMMARY).text = "2"
    billing = etree.SubElement(mod, f"{{{_CAC}}}BillingReference")
    idr = etree.SubElement(billing, f"{{{_CAC}}}InvoiceDocumentReference")
    id_el = etree.SubElement(idr, f"{{{_CBC}}}ID")
    id_el.text = "B001-10"
    type_el = etree.SubElement(idr, f"{{{_CBC}}}DocumentTypeCode")
    type_el.text = "03"


class TestVoidedDocumentsExtra:
    def test_voided_documents_extra_valid(self):
        root = etree.fromstring(_valid_voided_xml().encode("utf-8"))
        errors: list = []
        validate_voided_documents_extra(root, errors)
        assert errors == []

    @pytest.mark.parametrize(
        "code,mutator",
        [
            (
                "0127",
                lambda r: _set_text(r, ".//cbc:ID", "RA-20240101-0", NS_VOIDED),
            ),
            (
                "2105",
                lambda r: (
                    _set_text(r, ".//cbc:DocumentTypeCode", "30", NS_VOIDED),
                    _set_text(r, ".//cbc:DocumentSerialID", "B001", NS_VOIDED),
                ),
            ),
            (
                "2323",
                lambda r: _add_voided_line(r),
            ),
            (
                "2375",
                lambda r: (
                    _set_text(r, ".//cbc:ReferenceDate", "2023-12-31", NS_VOIDED),
                    _set_text(r, ".//cbc:DocumentTypeCode", "30", NS_VOIDED),
                ),
            ),
            (
                "2398",
                lambda r: _set_text(
                    r, ".//cbc:DocumentNumberID", "00000000", NS_VOIDED
                ),
            ),
            (
                "2581",
                lambda r: (
                    _set_text(r, ".//cbc:DocumentTypeCode", "42", NS_VOIDED),
                    _set_text(r, ".//cbc:DocumentSerialID", "S001", NS_VOIDED),
                ),
            ),
        ],
    )
    def test_voided_documents_extra_rule(self, code: str, mutator) -> None:
        root = etree.fromstring(_valid_voided_xml().encode("utf-8"))
        mutator(root)
        errors: list = []
        validate_voided_documents_extra(root, errors)
        codes = [e.code for e in errors]
        assert code in codes, f"Expected error {code} in {codes}"


class TestSummaryDocumentsExtra:
    def test_summary_documents_extra_valid(self):
        root = etree.fromstring(_valid_summary_xml().encode("utf-8"))
        errors: list = []
        validate_summary_documents_extra(root, errors)
        assert errors == []

    @pytest.mark.parametrize(
        "code,mutator",
        [
            (
                "2605",
                lambda r: _add_perception_with_bad_ruc(r),
            ),
            (
                "2957",
                lambda r: (
                    _set_text(r, ".//cbc:ReferenceDate", "2023-12-24", NS_SUMMARY),
                    _set_text(
                        r, ".//cac:Status/cbc:ConditionCode", "3", NS_SUMMARY
                    ),
                ),
            ),
            (
                "2989",
                lambda r: _add_modification_line_no_base(r),
            ),
            (
                "2990",
                lambda r: _add_modification_line_referencing_anulado(r),
            ),
        ],
    )
    def test_summary_documents_extra_rule(self, code: str, mutator) -> None:
        root = etree.fromstring(_valid_summary_xml().encode("utf-8"))
        mutator(root)
        errors: list = []
        validate_summary_documents_extra(root, errors)
        codes = [e.code for e in errors]
        assert code in codes, f"Expected error {code} in {codes}"
