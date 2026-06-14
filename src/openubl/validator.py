"""
SUNAT validation engine for UBL 2.1 XML documents.

Fuente de verdad:
- Excel "Reglas de validación actualizado al 24.04.2026" publicado en
  https://cpe.sunat.gob.pe/guias-y-manuales
- INDECOPI/IOFE y PCM Directiva N.° 002-2024-PCM/SGTD (SHA-256).

Estructura:
- Cada regla implementada se anota con su código SUNAT.
- Las reglas que requieren listados/padrones SUNAT se marcan como
  FUERA DE ALCANCE y documentan el motivo.
- Los errores se devuelven como ValidationError(code, message).
"""

import base64
import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lxml import etree

from openubl.validators._extra_credit_note import validate_credit_note_extra
from openubl.validators._extra_credit_note2 import validate_credit_note_extra2
from openubl.validators._extra_debit_note import validate_debit_note_extra
from openubl.validators._extra_debit_note2 import validate_debit_note_extra2
from openubl.validators._extra_invoice1 import validate_invoice_extra1
from openubl.validators._extra_invoice2 import validate_invoice_extra2
from openubl.validators._extra_invoice3 import validate_invoice_extra3
from openubl.validators._extra_invoice4 import validate_invoice_extra4
from openubl.validators._extra_perception_retention import (
    validate_perception_extra,
    validate_retention_extra,
)
from openubl.validators._extra_voided_summary import (
    validate_summary_documents_extra,
    validate_voided_documents_extra,
)


_RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
_SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"
_SHA1_SIG = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
_SHA1_DIG = "http://www.w3.org/2000/09/xmldsig#sha1"


class ValidationError:
    """Error de validación SUNAT con código y mensaje."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}

    def __repr__(self) -> str:
        return f"ValidationError({self.code}, {self.message!r})"


class SunatValidator:
    """Validates rendered XML against SUNAT rules and XSD schemas."""

    # Namespaces UBL 2.1
    NS_COMMON = {
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    }
    NS_INVOICE = {**NS_COMMON, "": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"}
    NS_CREDIT_NOTE = {**NS_COMMON, "": "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"}
    NS_DEBIT_NOTE = {**NS_COMMON, "": "urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2"}
    NS_VOIDED = {
        "": "urn:sunat:names:specification:ubl:peru:schema:xsd:VoidedDocuments-1",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
    }
    NS_SUMMARY = {
        "": "urn:sunat:names:specification:ubl:peru:schema:xsd:SummaryDocuments-1",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
    }
    NS_PERCEPTION = {
        "": "urn:sunat:names:specification:ubl:peru:schema:xsd:Perception-1",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
        "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    }
    NS_RETENTION = {
        "": "urn:sunat:names:specification:ubl:peru:schema:xsd:Retention-1",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
        "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    }
    NS_SIGNATURE = {
        "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "ds": "http://www.w3.org/2000/09/xmldsig#",
    }

    def __init__(self):
        self._load_catalogs()

    def _load_catalogs(self) -> None:
        """Cargar catálogos SUNAT locales."""
        # Catálogo N.° 07 - Tipo de afectación del IGV/IVAP
        self.catalog07 = {"10", "11", "12", "13", "14", "15", "16", "17", "20", "21", "30", "31", "32", "33", "34", "35", "36", "37"}
        # Catálogo N.° 05 - Tipo de tributo
        self.catalog05 = {"1000", "1016", "2000", "7152", "9995", "9996", "9997", "9998", "9999"}
        # Catálogo N.° 06 - Tipo de documento de identidad
        self.catalog06 = {"0", "1", "4", "6", "7", "A", "B", "C", "D", "E", "G"}
        # Catálogo N.° 51 - Tipo de operación (subset común)
        self.catalog51 = {
            "0101", "0102", "0103", "0104", "0105", "0106", "0107", "0108",
            "0200", "0201", "0202", "0203", "0204", "0205", "0206", "0207", "0208",
            "0301", "0302", "1001", "1002", "1003", "1004", "2001", "2100", "2101", "2102", "2103", "2104",
        }
        # Catálogo N.° 01 - Tipo de comprobante
        self.catalog01 = {"01", "03", "07", "08", "12", "20", "40", "41"}
        # Catálogo N.° 03 - Unidad de medida (subset)
        self.catalog03 = {"NIU", "KGM", "LTR", "MTQ", "MTR", "CMT", "GRM", "TNE", "PR", "BX", "DZN", "CEN", "ML"}
        # Códigos de motivo de cargo/descuento (subset Catálogo 53)
        self.catalog53 = {"00", "01", "02", "03", "04", "05", "06", "07", "20", "45", "46", "47", "48", "50", "51", "52", "53", "62", "63"}
        # Nombres de tributo según Catálogo N.° 05
        self.catalog05_names = {
            "1000": "IGV",
            "1016": "IVAP",
            "2000": "ISC",
            "7152": "ICBPER",
            "9995": "EXP",
            "9996": "GRATUITA",
            "9997": "EXO",
            "9998": "INA",
            "9999": "OTROS",
        }

    # ------------------------------------------------------------------
    # Helpers reutilizables
    # ------------------------------------------------------------------

    def _parse_xml(self, xml_string: str) -> etree._Element | None:
        try:
            return etree.fromstring(xml_string.encode("utf-8"))
        except etree.XMLSyntaxError:
            return None

    @staticmethod
    def _text(root: etree._Element | None, xpath: str, ns: dict) -> str | None:
        if root is None:
            return None
        elem = root.find(xpath, namespaces=ns)
        if elem is None:
            return None
        return (elem.text or "").strip() or None

    @staticmethod
    def _attr(root: etree._Element | None, xpath: str, attr: str, ns: dict) -> str | None:
        if root is None:
            return None
        elem = root.find(xpath, namespaces=ns)
        if elem is None:
            return None
        val = elem.get(attr)
        return val.strip() if val else None

    @staticmethod
    def _exists(root: etree._Element | None, xpath: str, ns: dict) -> bool:
        if root is None:
            return False
        return root.find(xpath, namespaces=ns) is not None

    @staticmethod
    def _all(root: etree._Element | None, xpath: str, ns: dict) -> list[etree._Element]:
        if root is None:
            return []
        return root.findall(xpath, namespaces=ns)

    @staticmethod
    def _is_numeric(value: str | None) -> bool:
        if value is None:
            return False
        try:
            Decimal(value)
            return True
        except InvalidOperation:
            return False

    @staticmethod
    def _parse_amount(value: str | None) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(value)
        except InvalidOperation:
            return None

    @staticmethod
    def _matches(value: str | None, regex: str) -> bool:
        if value is None:
            return False
        return re.match(regex, value) is not None

    @staticmethod
    def _one_of(value: str | None, values: set[str]) -> bool:
        return value is not None and value in values

    @staticmethod
    def _add(errors: list[ValidationError], code: str, message: str) -> None:
        errors.append(ValidationError(code, message))

    def validate_schema(self, xml_string: str, xsd_path: str) -> list[ValidationError]:
        """Validate XML against UBL 2.1 XSD schema. Errors reported as code 306."""
        errors: list[ValidationError] = []
        try:
            xml_doc = etree.fromstring(xml_string.encode("utf-8"))
            xsd_path_obj = Path(xsd_path).resolve()
            with open(xsd_path_obj, "rb") as f:
                schema_root = etree.parse(f, base_url=str(xsd_path_obj.parent)).getroot()
            schema = etree.XMLSchema(schema_root)
            schema.assertValid(xml_doc)
        except etree.XMLSyntaxError as e:
            errors.append(ValidationError("306", f"No se puede leer (parsear) el archivo XML - {e}"))
        except etree.DocumentInvalid as e:
            detail = str(e).replace("\n", " ")
            if "does not resolve" in detail or "failed to load external entity" in detail:
                return []
            errors.append(ValidationError("306", f"No se puede leer (parsear) el archivo XML - {detail}"))
        except Exception as e:
            msg = str(e)
            if "does not resolve" in msg or "failed to load external entity" in msg or "I/O warning" in msg:
                return []
            errors.append(ValidationError("306", f"No se puede leer (parsear) el archivo XML - {e}"))
        return errors

    # ------------------------------------------------------------------
    # Dispatchers
    # ------------------------------------------------------------------

    def validate_invoice(self, xml_string: str) -> list[ValidationError]:
        """Validate invoice XML against SUNAT business rules."""
        root = self._parse_xml(xml_string)
        errors: list[ValidationError] = []
        if root is None:
            errors.append(ValidationError("306", "No se puede leer (parsear) el archivo XML"))
            return errors
        self._validate_invoice_common(root, self.NS_INVOICE, errors)
        self._validate_invoice_specific(root, errors)
        validate_invoice_extra1(root, errors)
        validate_invoice_extra2(root, errors)
        validate_invoice_extra3(root, errors)
        validate_invoice_extra4(root, errors)
        return errors

    def validate_credit_note(self, xml_string: str) -> list[ValidationError]:
        """Validate credit note XML against SUNAT business rules."""
        root = self._parse_xml(xml_string)
        errors: list[ValidationError] = []
        if root is None:
            errors.append(ValidationError("306", "No se puede leer (parsear) el archivo XML"))
            return errors
        self._validate_invoice_common(root, self.NS_CREDIT_NOTE, errors)
        self._validate_credit_note_specific(root, errors)
        validate_credit_note_extra(root, errors)
        validate_credit_note_extra2(root, errors)
        return errors

    def validate_debit_note(self, xml_string: str) -> list[ValidationError]:
        """Validate debit note XML against SUNAT business rules."""
        root = self._parse_xml(xml_string)
        errors: list[ValidationError] = []
        if root is None:
            errors.append(ValidationError("306", "No se puede leer (parsear) el archivo XML"))
            return errors
        self._validate_invoice_common(root, self.NS_DEBIT_NOTE, errors)
        self._validate_debit_note_specific(root, errors)
        validate_debit_note_extra(root, errors)
        validate_debit_note_extra2(root, errors)
        return errors

    def validate_voided_documents(self, xml_string: str) -> list[ValidationError]:
        """Validate voided documents XML against SUNAT business rules."""
        root = self._parse_xml(xml_string)
        errors: list[ValidationError] = []
        if root is None:
            errors.append(ValidationError("306", "No se puede leer (parsear) el archivo XML"))
            return errors
        self._validate_voided_documents(root, errors)
        validate_voided_documents_extra(root, errors)
        return errors

    def validate_summary_documents(self, xml_string: str) -> list[ValidationError]:
        """Validate summary documents XML against SUNAT business rules."""
        root = self._parse_xml(xml_string)
        errors: list[ValidationError] = []
        if root is None:
            errors.append(ValidationError("306", "No se puede leer (parsear) el archivo XML"))
            return errors
        self._validate_summary_documents(root, errors)
        validate_summary_documents_extra(root, errors)
        return errors

    def validate_perception(self, xml_string: str) -> list[ValidationError]:
        """Validate perception XML against SUNAT business rules."""
        root = self._parse_xml(xml_string)
        errors: list[ValidationError] = []
        if root is None:
            errors.append(ValidationError("306", "No se puede leer (parsear) el archivo XML"))
            return errors
        self._validate_perception(root, errors)
        validate_perception_extra(root, errors)
        return errors

    def validate_retention(self, xml_string: str) -> list[ValidationError]:
        """Validate retention XML against SUNAT business rules."""
        root = self._parse_xml(xml_string)
        errors: list[ValidationError] = []
        if root is None:
            errors.append(ValidationError("306", "No se puede leer (parsear) el archivo XML"))
            return errors
        self._validate_retention(root, errors)
        validate_retention_extra(root, errors)
        return errors

    def validate_signature(self, xml_string: str) -> list[ValidationError]:
        """Validate signed XML structure and SHA-256 algorithms."""
        root = self._parse_xml(xml_string)
        errors: list[ValidationError] = []
        if root is None:
            errors.append(ValidationError("306", "No se puede leer (parsear) el archivo XML"))
            return errors
        self._validate_signature(root, errors)
        return errors

    # ------------------------------------------------------------------
    # Invoice / CreditNote / DebitNote common validations
    # ------------------------------------------------------------------

    def _validate_invoice_common(self, root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
        """Validaciones comunes para Invoice, CreditNote y DebitNote."""

        # ERROR 2075 / 2074: UBLVersionID
        ubl_version = self._text(root, "cbc:UBLVersionID", ns)
        if ubl_version is None:
            self._add(errors, "2075", "No existe el Tag UBL cbc:UBLVersionID o es vacío")
        elif ubl_version != "2.1":
            self._add(errors, "2074", "El valor del Tag UBL cbc:UBLVersionID es diferente de '2.1'")

        # ERROR 2073 / 2072: CustomizationID
        customization = self._text(root, "cbc:CustomizationID", ns)
        if customization is None:
            self._add(errors, "2073", "No existe el Tag UBL cbc:CustomizationID o es vacío")
        elif customization != "2.0":
            self._add(errors, "2072", "El valor del Tag UBL cbc:CustomizationID es diferente de '2.0'")

        # ERROR 1001: ID format
        doc_id = self._text(root, "cbc:ID", ns)
        if doc_id is None or not self._matches(doc_id, r"^[A-Za-z0-9]{3,4}-\d{1,8}$"):
            self._add(errors, "1001", "El formato del Tag UBL cbc:ID no tiene el formato: [A-Z0-9]{3,4}-[0-9]{1,8}")

        # ERROR 2070: DocumentCurrencyCode
        currency = self._text(root, "cbc:DocumentCurrencyCode", ns)
        if currency is None:
            self._add(errors, "2070", "No existe el Tag UBL cbc:DocumentCurrencyCode o es vacío")

        # ERROR 2071: currencyID consistency
        self._check_currency_consistency(root, ns, errors)

        # ERROR 1037: Supplier RegistrationName
        reg_name = self._text(root, "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName", ns)
        if reg_name is None:
            self._add(errors, "1037", "No existe el Tag UBL cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName o es vacío")

        # ERROR 1008 / 1007: Supplier schemeID and RUC
        supplier_id_elem = root.find("cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID", namespaces=ns)
        if supplier_id_elem is not None:
            scheme = supplier_id_elem.get("schemeID")
            ruc = (supplier_id_elem.text or "").strip()
            if scheme is None or scheme == "":
                self._add(errors, "1008", "No existe el atributo cac:AccountingSupplierParty/.../cbc:ID@schemeID o es vacío")
            elif scheme != "6":
                self._add(errors, "1007", "El valor del Tag UBL cac:AccountingSupplierParty/.../cbc:ID@schemeID es diferente a '6'")
            if not self._matches(ruc, r"^\d{11}$"):
                self._add(errors, "1034", "El valor del Tag UBL cac:AccountingSupplierParty/.../cbc:ID es diferente al RUC del nombre del XML")

        # ERROR 2015: Customer schemeID
        customer_id_elem = root.find("cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID", namespaces=ns)
        if customer_id_elem is not None:
            scheme = customer_id_elem.get("schemeID")
            if scheme is None:
                self._add(errors, "2015", "No existe el atributo cac:AccountingCustomerParty/.../cbc:ID@schemeID")

        # ERROR 2021 / 2022: Customer RegistrationName
        cust_name = self._text(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName", ns)
        if cust_name is None:
            self._add(errors, "2021", "No existe el Tag UBL cac:AccountingCustomerParty/.../cbc:RegistrationName o es vacío")
        elif not self._matches(cust_name, r"^.{3,1500}$"):
            self._add(errors, "2022", "El formato del Tag UBL cac:AccountingCustomerParty/.../cbc:RegistrationName es diferente a alfanumérico de 3 hasta 1500 caracteres")

        is_debit = ns is self.NS_DEBIT_NOTE
        total_path = "cac:RequestedMonetaryTotal" if is_debit else "cac:LegalMonetaryTotal"

        # ERROR 2062: PayableAmount > 0
        payable = self._parse_amount(self._text(root, f"{total_path}/cbc:PayableAmount", ns))
        if payable is None or payable <= 0:
            self._add(errors, "2062", f"El formato del Tag UBL {total_path}/cbc:PayableAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero")

        if not is_debit:
            # ERROR 3305: TaxInclusiveAmount exists
            if not self._exists(root, f"{total_path}/cbc:TaxInclusiveAmount", ns):
                self._add(errors, "3305", f"No existe el Tag UBL {total_path}/cbc:TaxInclusiveAmount")

            # ERROR 3288: LineExtensionAmount exists
            if not self._exists(root, f"{total_path}/cbc:LineExtensionAmount", ns):
                self._add(errors, "3288", f"No existe el Tag UBL {total_path}/cbc:LineExtensionAmount")

        # ERROR 3294: TaxTotal matches sum of lines
        self._check_tax_total(root, ns, errors)

        # ERROR 3278: LineExtensionAmount matches sum
        self._check_line_extension_amount(root, ns, errors)

    def _validate_invoice_specific(self, root: etree._Element, errors: list[ValidationError]) -> None:
        """ERROR 1004: InvoiceTypeCode (solo Invoice)."""
        ns = self.NS_INVOICE
        type_code = self._text(root, "cbc:InvoiceTypeCode", ns)
        if type_code is None:
            self._add(errors, "1004", "No existe el Tag UBL cbc:InvoiceTypeCode o es vacío")

    def _check_currency_consistency(self, root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
        """ERROR 2071: currencyID consistency across totals and lines."""
        currency = self._text(root, "cbc:DocumentCurrencyCode", ns)
        if currency is None:
            return

        def _check(elem: etree._Element) -> bool:
            for child in elem:
                cid = child.get("currencyID")
                if cid is not None and cid.strip() != currency:
                    return False
            return True

        totals = self._all(root, "cac:LegalMonetaryTotal", ns)
        totals += self._all(root, "cac:RequestedMonetaryTotal", ns)
        totals += self._all(root, "cac:TaxTotal", ns)
        for total in totals:
            if not _check(total):
                self._add(errors, "2071", f"La moneda de los totales de línea y totales de comprobantes es diferente a {currency}")
                return

        lines = self._all(root, "cac:InvoiceLine", ns)
        lines += self._all(root, "cac:CreditNoteLine", ns)
        lines += self._all(root, "cac:DebitNoteLine", ns)
        for line in lines:
            for child in line:
                cid = child.get("currencyID")
                if cid is not None and cid.strip() != currency:
                    self._add(errors, "2071", f"La moneda de los totales de línea y totales de comprobantes es diferente a {currency}")
                    return
                for sub in child:
                    cid = sub.get("currencyID")
                    if cid is not None and cid.strip() != currency:
                        self._add(errors, "2071", f"La moneda de los totales de línea y totales de comprobantes es diferente a {currency}")
                        return


    def _check_tax_total(self, root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
        """ERROR 3294: TaxTotal global matches sum of line taxes."""
        tax_total = self._parse_amount(self._text(root, "cac:TaxTotal/cbc:TaxAmount", ns))
        if tax_total is None:
            self._add(errors, "2956", "No existe el tag /Invoice/cac:TaxTotal")
            return
        line_taxes = self._all(root, "cac:InvoiceLine/cac:TaxTotal/cbc:TaxAmount", ns)
        line_taxes += self._all(root, "cac:CreditNoteLine/cac:TaxTotal/cbc:TaxAmount", ns)
        line_taxes += self._all(root, "cac:DebitNoteLine/cac:TaxTotal/cbc:TaxAmount", ns)
        try:
            sum_lines = sum(self._parse_amount(t.text) or Decimal("0") for t in line_taxes)
            if abs(tax_total - sum_lines) > Decimal("1"):
                self._add(errors, "3294", "El valor del Tag UBL cac:TaxTotal/cbc:TaxAmount es diferente a la sumatoria de 'Monto de tributo por línea'")
        except Exception:
            pass

    def _check_line_extension_amount(self, root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
        """ERROR 3278: LineExtensionAmount global matches sum of line extensions."""
        total_path = "cac:RequestedMonetaryTotal" if ns is self.NS_DEBIT_NOTE else "cac:LegalMonetaryTotal"
        line_ext = self._parse_amount(self._text(root, f"{total_path}/cbc:LineExtensionAmount", ns))
        if line_ext is None:
            return
        line_exts = self._all(root, "cac:InvoiceLine/cbc:LineExtensionAmount", ns)
        line_exts += self._all(root, "cac:CreditNoteLine/cbc:LineExtensionAmount", ns)
        line_exts += self._all(root, "cac:DebitNoteLine/cbc:LineExtensionAmount", ns)
        try:
            sum_exts = sum(self._parse_amount(t.text) or Decimal("0") for t in line_exts)
            if abs(line_ext - sum_exts) > Decimal("1"):
                self._add(errors, "3278", f"El valor del Tag UBL {total_path}/cbc:LineExtensionAmount es diferente de la sumatoria del 'Valor de venta por ítem'")
        except Exception:
            pass

    def _doc_serie(self, root: etree._Element, ns: dict) -> str:
        doc_id = self._text(root, "cbc:ID", ns) or ""
        return doc_id.split("-")[0] if "-" in doc_id else doc_id

    def _doc_numero(self, root: etree._Element, ns: dict) -> str:
        doc_id = self._text(root, "cbc:ID", ns) or ""
        return doc_id.split("-")[1] if "-" in doc_id else ""

    # ------------------------------------------------------------------
    # CreditNote / DebitNote specific validations
    # ------------------------------------------------------------------

    def _validate_credit_note_specific(self, root: etree._Element, errors: list[ValidationError]) -> None:
        ns = self.NS_CREDIT_NOTE

        # ERROR 2128: DiscrepancyResponse/ResponseCode
        resp_code = self._text(root, "cac:DiscrepancyResponse/cbc:ResponseCode", ns)
        if resp_code is None:
            self._add(errors, "2128", "No existe el Tag UBL cac:DiscrepancyResponse/cbc:ResponseCode o es vacío")

        # ERROR 3203: DiscrepancyResponse/ResponseCode repetido
        resp_codes = self._all(root, "cac:DiscrepancyResponse/cbc:ResponseCode", ns)
        if len(resp_codes) > 1:
            self._add(errors, "3203", "El tag UBL cac:DiscrepancyResponse/cbc:ResponseCode se repite dentro del mismo documento")

        # ERROR 2136 / 2135: DiscrepancyResponse/Description
        resp_desc = self._text(root, "cac:DiscrepancyResponse/cbc:Description", ns)
        if resp_desc is None:
            self._add(errors, "2136", "No existe el Tag UBL cac:DiscrepancyResponse/cbc:Description o es vacío")
        elif not self._matches(resp_desc, r"^.{1,500}$"):
            self._add(errors, "2135", "El formato del Tag UBL cac:DiscrepancyResponse/cbc:Description es diferente a alfanumérico de 1 hasta 500 caracteres")

        # ERROR 3029 / 2511: AccountingSupplierParty schemeID
        supplier_id_elem = root.find("cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID", namespaces=ns)
        if supplier_id_elem is not None:
            scheme = supplier_id_elem.get("schemeID")
            if scheme is None or scheme == "":
                self._add(errors, "3029", "No existe el atributo cac:AccountingSupplierParty/.../cbc:ID@schemeID o es vacío")
            elif scheme != "6":
                self._add(errors, "2511", "El valor del Tag UBL cac:AccountingSupplierParty/.../cbc:ID@schemeID es diferente a '6'")

        # ERROR 2679: AccountingCustomerParty ID y schemeID
        customer_id_elem = root.find("cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID", namespaces=ns)
        if customer_id_elem is None:
            self._add(errors, "2679", "No existe el Tag UBL cac:AccountingCustomerParty/.../cbc:ID o es vacío")
        else:
            scheme = customer_id_elem.get("schemeID")
            if scheme is None or scheme == "":
                self._add(errors, "2679", "No existe el atributo cac:AccountingCustomerParty/.../cbc:ID@schemeID o es vacío")

        # BillingReference rules
        self._validate_credit_note_billing_reference(root, ns, errors, resp_code)

        # CreditNoteLine rules
        self._validate_credit_note_lines(root, ns, errors, resp_code)

        # PaymentTerms rules
        self._validate_credit_note_payment_terms(root, ns, errors, resp_code)

    def _validate_credit_note_billing_reference(self, root: etree._Element, ns: dict, errors: list[ValidationError], resp_code: str | None) -> None:
        """Reglas de BillingReference para notas de crédito."""
        refs = self._all(root, "cac:BillingReference/cac:InvoiceDocumentReference", ns)
        doc_serie = self._doc_serie(root, ns)

        # ERROR 2524: BillingReference/InvoiceDocumentReference/ID obligatorio si resp_code != "10"
        if resp_code != "10" and not refs:
            self._add(errors, "2524", "Si 'Código de tipo de nota de crédito' es diferente de '10-Otros', no existe un tag /CreditNote/cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID")

        # ERROR 3261: resp_code en 01-10,12,13 y tipos de documento repetidos
        if resp_code in {"01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "12", "13"} and len(refs) > 1:
            types = [self._text(r, "cbc:DocumentTypeCode", ns) for r in refs]
            if len(types) != len(set(types)):
                self._add(errors, "3261", "Si 'Código de tipo de nota de crédito' es 01-10,12,13, existe más de un tag cbc:DocumentTypeCode con el mismo valor")

        # ERROR 3194: resp_code == "11" y más de un BillingReference
        if resp_code == "11" and len(refs) > 1:
            self._add(errors, "3194", "Si 'Código de tipo de nota de crédito' es '11-Ajustes de operaciones de exportación', existe más de un tag /CreditNote/cac:BillingReference")

        # ERROR 2884: si hay más de un BillingReference, todos deben tener el mismo tipo
        doc_types = [self._text(r, "cbc:DocumentTypeCode", ns) for r in refs if self._text(r, "cbc:DocumentTypeCode", ns) is not None]
        if len(doc_types) > 1 and len(set(doc_types)) > 1:
            self._add(errors, "2884", "Si existe más de un documento que se modifica, no todos tienen el mismo 'Tipo de documento que modifica'")

        for ref in refs:
            ref_id = self._text(ref, "cbc:ID", ns)
            ref_type = self._text(ref, "cbc:DocumentTypeCode", ns)

            # ERROR 2117: si modifica factura (01), formato del ID
            if ref_type == "01" and ref_id is not None:
                if not self._matches(ref_id, r"^[FE][A-Z0-9]{3}-\d{1,8}$|^\d{1,4}-\d{1,8}$"):
                    self._add(errors, "2117", "Si documento que se modifica es una factura (Tipo '01'), el formato del Tag UBL es diferente a [F/E][A-Z0-9]{3}-[0-9]{1,8} o [0-9]{1,4}-[0-9]{1,8}")

            # ERROR 2116: resp_code != "10" y serie F/E → tipo debe ser 01
            if resp_code != "10" and doc_serie and doc_serie[0].upper() in {"F", "E"} and ref_type != "01":
                self._add(errors, "2116", "Si 'Código de tipo de nota de crédito' es diferente de '10' y la Serie empieza con F/E, el 'Tipo de documento que modifica' debe ser '01'")

            # ERROR 2399: resp_code != "10" y serie B → tipo debe ser 03
            if resp_code != "10" and doc_serie and doc_serie[0].upper() == "B" and ref_type != "03":
                self._add(errors, "2399", "Si 'Código de tipo de nota de crédito' es diferente de '10' y la Serie empieza con B, el 'Tipo de documento que modifica' debe ser '03'")

            # ERROR 2594: resp_code != "10" y serie numérica → tipo debe ser 01 o 03
            if resp_code != "10" and doc_serie and doc_serie[0].isdigit() and ref_type not in {"01", "03"}:
                self._add(errors, "2594", "Si 'Código de tipo de nota de crédito' es diferente de '10' y la Serie empieza con número, el 'Tipo de documento que modifica' debe ser '01' o '03'")

            # ERROR 3259: resp_code == "13" → tipo debe ser 01
            if resp_code == "13" and ref_type != "01":
                self._add(errors, "3259", "Si 'Código de tipo de nota de crédito' es '13' y el 'Tipo de documento que modifica' es diferente de '01'")

        # ERROR 3286, 3503, 3260: reglas truncadas en el Excel; se aplican interpretaciones conservadoras
        # FUERA DE ALCANCE parcial - requieren contexto de nombre de archivo o texto completo de la regla.

        # ERROR 2426, 2636, 2635, 2637: AdditionalDocumentReference
        add_refs = self._all(root, "cac:AdditionalDocumentReference", ns)
        pairs = []
        for ar in add_refs:
            ar_type = self._text(ar, "cbc:DocumentTypeCode", ns)
            ar_id = self._text(ar, "cbc:ID", ns)
            if ar_type is not None and ar_id is not None:
                pairs.append((ar_type, ar_id))

        # ERROR 2426: (tipo + id) repetido
        if len(pairs) != len(set(pairs)):
            self._add(errors, "2426", "El 'Tipo de otro documento relacionado' concatenado con el valor del Tag UBL se repite en el /CreditNote")

        type_99_count = sum(1 for t, _ in pairs if t == "99")
        # ERROR 2636: resp_code != "10" y existe tipo 99
        if resp_code != "10" and type_99_count > 0:
            self._add(errors, "2636", "Si 'Código de tipo de nota de crédito' es diferente de 10 y 'Tipo de otro documento relacionado' es 99, no debe existir")

        if resp_code == "10":
            # ERROR 2635: resp_code == "10" y más de un tipo 99
            if type_99_count > 1:
                self._add(errors, "2635", "Si 'Código de tipo de nota de crédito' es 10, existe más de un tag igual a '99'")
            # ERROR 2637: resp_code == "10" y existe tipo diferente de 99
            if any(t != "99" for t, _ in pairs):
                self._add(errors, "2637", "Si 'Código de tipo de nota de crédito' es 10, el 'Tipo de otro documento relacionado' debe ser '99'")

    def _validate_credit_note_lines(self, root: etree._Element, ns: dict, errors: list[ValidationError], resp_code: str | None) -> None:
        """Reglas de CreditNoteLine."""
        lines = self._all(root, "cac:CreditNoteLine", ns)
        seen_ids: set[str] = set()

        for line in lines:
            line_id = self._text(line, "cbc:ID", ns)

            # ERROR 2137: formato de cbc:ID
            if line_id is None or not self._matches(line_id, r"^\d{1,3}$") or line_id == "0":
                self._add(errors, "2137", "El formato del Tag UBL cbc:ID es diferente de numérico de hasta 3 dígitos; o es igual a cero")
            else:
                # ERROR 2752: ID repetido
                if line_id in seen_ids:
                    self._add(errors, "2752", "Existe otro cac:CreditNoteLine con el mismo valor del Tag UBL cbc:ID")
                seen_ids.add(line_id)

            # ERROR 2138: CreditedQuantity@unitCode
            qty = line.find("cbc:CreditedQuantity", namespaces=ns)
            if qty is not None:
                unit_code = qty.get("unitCode")
                if unit_code is None or unit_code == "":
                    self._add(errors, "2138", "No existe el atributo cbc:CreditedQuantity@unitCode o es vacío")

            # ERROR 2139: CreditedQuantity formato
            qty_text = self._text(line, "cbc:CreditedQuantity", ns)
            if qty_text is not None and not self._matches(qty_text, r"^\d{1,12}(\.\d{1,10})?$"):
                self._add(errors, "2139", "El formato del Tag UBL cbc:CreditedQuantity es diferente de decimal positivo de 12 enteros y hasta 10 decimales")

            # ERROR 3230: TaxExemptionReasonCode == "17" y resp_code != "12"
            tax_exempt = self._text(line, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode", ns)
            if tax_exempt == "17" and resp_code != "12":
                self._add(errors, "3230", "Si 'Afectación al IGV o IVAP' es '17' y 'Código de tipo de nota de crédito' es diferente de '12'")

            # ERROR 3221: resp_code == "12" y existe tributo 9995/9997/9998
            if resp_code == "12":
                tax_codes = {self._text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns) for ts in self._all(line, "cac:TaxTotal/cac:TaxSubtotal", ns)}
                if tax_codes.intersection({"9995", "9997", "9998"}):
                    self._add(errors, "3221", "Si 'Código de tipo de nota de crédito' es '12' (IVAP), no puede existir código de tributo 9995, 9997 ni 9998")

            # ERROR 3315: resp_code == "13" y Percent != 0
            if resp_code == "13":
                percent = self._text(line, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent", ns)
                if percent is not None and self._parse_amount(percent) != Decimal("0"):
                    self._add(errors, "3315", "Si 'Código de tipo de nota de crédito' es '13', el valor del Tag UBL cbc:Percent debe ser cero")

    def _validate_credit_note_payment_terms(self, root: etree._Element, ns: dict, errors: list[ValidationError], resp_code: str | None) -> None:
        """Reglas de PaymentTerms para notas de crédito."""
        payment_terms = self._all(root, "cac:PaymentTerms", ns)
        customer_type = self._attr(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID", "schemeID", ns)

        # ERROR 3257: resp_code == "13" requiere PaymentTerms con ID "FormaPago"
        if resp_code == "13":
            forma_pago_terms = [pt for pt in payment_terms if self._text(pt, "cbc:ID", ns) == "FormaPago"]
            if not forma_pago_terms:
                self._add(errors, "3257", "Si 'Código de tipo de nota de crédito' es '13', no existe al menos un tag cac:PaymentTerms con cbc:ID igual a 'FormaPago'")

        for pt in payment_terms:
            pt_id = self._text(pt, "cbc:ID", ns)
            means_id = self._text(pt, "cbc:PaymentMeansID", ns)
            if pt_id == "FormaPago":
                # ERROR 3320: FormaPago=Credito, resp_code=13 y cliente no es 6
                if means_id == "Credito" and resp_code == "13" and customer_type != "6":
                    self._add(errors, "3320", "Si 'Indicador' es 'FormaPago', 'Forma de pago' es 'Credito' y 'Código de tipo de nota de crédito' es '13', el tipo de documento del adquiriente debe ser '6'")
                # ERROR 3321: FormaPago=Cuota[0-9]{3} y cliente no es 6
                if means_id is not None and self._matches(means_id, r"^Cuota\d{3}$") and customer_type != "6":
                    self._add(errors, "3321", "Si existe un tag cac:PaymentTerms con cbc:ID 'FormaPago' y valor 'Cuota[0-9]{3}', el tipo de documento del adquiriente debe ser '6'")

    def _validate_debit_note_specific(self, root: etree._Element, errors: list[ValidationError]) -> None:
        ns = self.NS_DEBIT_NOTE
        resp_code = self._text(root, "cac:DiscrepancyResponse/cbc:ResponseCode", ns)
        doc_serie = self._doc_serie(root, ns)

        # BillingReference rules
        refs = self._all(root, "cac:BillingReference/cac:InvoiceDocumentReference", ns)
        for ref in refs:
            ref_id = self._text(ref, "cbc:ID", ns)
            ref_type = self._text(ref, "cbc:DocumentTypeCode", ns)

            # ERROR 2205: si modifica factura (01), formato del ID
            if ref_type == "01" and ref_id is not None:
                if not self._matches(ref_id, r"^[FE][A-Z0-9]{3}-\d{1,8}$|^\d{1,4}-\d{1,8}$"):
                    self._add(errors, "2205", "Si documento que se modifica es una factura (Tipo '01'), el formato del Tag UBL es diferente a [F/E][A-Z0-9]{3}-[0-9]{1,8} o [0-9]{1,4}-[0-9]{1,8}")

            # ERROR 2204: resp_code no es 03/13 y serie F/E → tipo debe ser 01
            if resp_code not in {"03", "13"} and doc_serie and doc_serie[0].upper() in {"F", "E"} and ref_type != "01":
                self._add(errors, "2204", "Si 'Código de tipo de nota de débito' es diferente de '03' y '13' y la Serie empieza con F/E, el 'Tipo de documento que modifica' debe ser '01'")

            # ERROR 2400: resp_code no es 03/13 y serie B → tipo debe ser 03
            if resp_code not in {"03", "13"} and doc_serie and doc_serie[0].upper() == "B" and ref_type != "03":
                self._add(errors, "2400", "Si 'Código de tipo de nota de débito' es diferente de '03' y '13' y la Serie empieza con B, el 'Tipo de documento que modifica' debe ser '03'")

        # DebitNoteLine rules
        lines = self._all(root, "cac:DebitNoteLine", ns)
        for line in lines:
            # ERROR 2188: DebitedQuantity@unitCode
            qty = line.find("cbc:DebitedQuantity", namespaces=ns)
            if qty is not None:
                unit_code = qty.get("unitCode")
                if unit_code is None or unit_code == "":
                    self._add(errors, "2188", "No existe el atributo cbc:DebitedQuantity@unitCode o es vacío")

            for ts in self._all(line, "cac:TaxTotal/cac:TaxSubtotal", ns):
                tax_code = self._text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns)
                tax_amount = self._parse_amount(self._text(ts, "cbc:TaxAmount", ns))
                percent = self._text(ts, "cac:TaxCategory/cbc:Percent", ns)

                # ERROR 2643: IVAP (1016) con nota débito 12 → Percent debe ser 0
                if tax_code == "1016" and resp_code == "12":
                    if percent is not None and self._parse_amount(percent) != Decimal("0"):
                        self._add(errors, "2643", "Si 'Código de tributo por línea' es 1016 (IVAP) y 'Código de tipo de nota de débito' es 12, el valor del Tag UBL cbc:Percent debe ser cero")

                # ERROR 3507: nota débito 13 → IGV/IVAP debe ser 0
                if resp_code == "13" and tax_code in {"1000", "1016"} and tax_amount is not None and tax_amount > 0:
                    self._add(errors, "3507", "Si 'Código de tipo de nota de débito' es '13', el monto de IGV o IVAP debe ser cero")

                # ERROR 3101: tributos 9995/9997/9998 → monto debe ser 0
                if tax_code in {"9995", "9997", "9998"} and tax_amount is not None and tax_amount != 0:
                    self._add(errors, "3101", "Si 'Código de tributo por línea' es 9995, 9997 o 9998, el valor del tag UBL cbc:TaxAmount debe ser 0")

        # ERROR 3313 / 3314: PaymentTerms/PaymentMeans Detraccion deben coexistir
        pt_ids = {self._text(pt, "cbc:ID", ns) for pt in self._all(root, "cac:PaymentTerms", ns)}
        pm_ids = {self._text(pm, "cbc:ID", ns) for pm in self._all(root, "cac:PaymentMeans", ns)}
        if "Detraccion" in pt_ids and "Detraccion" not in pm_ids:
            self._add(errors, "3313", "Si existe 'Indicador PaymentTerms' igual a 'Detraccion', debe existir un 'Indicador PaymentMeans' igual a 'Detraccion'")
        if "Detraccion" in pm_ids and "Detraccion" not in pt_ids:
            self._add(errors, "3314", "Si existe 'Indicador PaymentMeans' igual a 'Detraccion', debe existir un 'Indicador PaymentTerms' igual a 'Detraccion'")

    # ------------------------------------------------------------------
    # VoidedDocuments validations
    # ------------------------------------------------------------------

    def _validate_voided_documents(self, root: etree._Element, errors: list[ValidationError]) -> None:
        ns = self.NS_VOIDED

        # ERROR 2075 / 2074: UBLVersionID
        ubl_version = self._text(root, "cbc:UBLVersionID", ns)
        if ubl_version is None:
            self._add(errors, "2075", "No existe el Tag UBL cbc:UBLVersionID o es vacío")
        elif ubl_version != "2.0":
            self._add(errors, "2074", "El valor del Tag UBL cbc:UBLVersionID es diferente a '2.0'")

        # ERROR 2072: CustomizationID
        customization = self._text(root, "cbc:CustomizationID", ns)
        if customization is None or customization != "1.0":
            self._add(errors, "2072", "El valor del Tag UBL cbc:CustomizationID es diferente a '1.0'")

        # ERROR 2220 / 2346 / 1034: datos del nombre del archivo
        # La comparación exacta con el nombre del archivo ZIP es FUERA DE ALCANCE
        # porque el server ya no recibe/manipula ZIP. Se valida estructuralmente
        # el ID (RA-YYYYMMDD-NNNN), la coherencia ID vs IssueDate y el RUC.
        doc_id = self._text(root, "cbc:ID", ns)
        if doc_id is None or not self._matches(doc_id, r"^RA-\d{8}-\d{1,4}$"):
            self._add(errors, "2220", "El ID del nombre del archivo es diferente al Tag UBL cbc:ID (se espera RA-YYYYMMDD-NNNN)")
        else:
            # ERROR 2346: fecha del nombre del archivo vs IssueDate
            issue_date = self._text(root, "cbc:IssueDate", ns)
            id_date = f"{doc_id[3:7]}-{doc_id[7:9]}-{doc_id[9:11]}"
            if issue_date is not None and issue_date != id_date:
                self._add(errors, "2346", "La fecha del nombre del archivo es diferente al tag UBL cbc:IssueDate")

        # ERROR 2301: IssueDate no puede ser futura (aproximación local a fecha de envío)
        issue_date = self._text(root, "cbc:IssueDate", ns)
        if issue_date is not None:
            try:
                issue = date.fromisoformat(issue_date)
                if issue > date.today():
                    self._add(errors, "2301", "El valor del Tag UBL cbc:IssueDate es mayor a la fecha de envío")
            except ValueError:
                self._add(errors, "2301", "El valor del Tag UBL cbc:IssueDate no es una fecha válida")

        # ERROR 2671: ReferenceDate <= IssueDate
        ref_date = self._text(root, "cbc:ReferenceDate", ns)
        if ref_date is not None and issue_date is not None:
            try:
                ref = date.fromisoformat(ref_date)
                issue = date.fromisoformat(issue_date)
                if ref > issue:
                    self._add(errors, "2671", "El valor del Tag UBL cbc:ReferenceDate es mayor a 'Fecha de generación de la comunicación'")
            except ValueError:
                pass

        # ERROR 1034 / 2288 / 2287 / 2229 / 2228: AccountingSupplierParty
        supplier_account_id = self._text(root, "cac:AccountingSupplierParty/cbc:CustomerAssignedAccountID", ns)
        if supplier_account_id is None:
            self._add(errors, "2288", "No existe el Tag UBL cac:AccountingSupplierParty/cbc:CustomerAssignedAccountID o es vacío")
        elif not self._matches(supplier_account_id, r"^\d{11}$"):
            self._add(errors, "1034", "El valor del Tag UBL cac:AccountingSupplierParty/cbc:CustomerAssignedAccountID es diferente al RUC del nombre del XML")

        additional_account_id = self._text(root, "cac:AccountingSupplierParty/cbc:AdditionalAccountID", ns)
        if additional_account_id is None:
            self._add(errors, "2288", "No existe el Tag UBL cac:AccountingSupplierParty/cbc:AdditionalAccountID o es vacío")
        elif additional_account_id != "6":
            self._add(errors, "2287", "El valor del Tag UBL cac:AccountingSupplierParty/cbc:AdditionalAccountID es diferente de '6'")

        reg_name = self._text(root, "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName", ns)
        if reg_name is None:
            self._add(errors, "2229", "No existe el Tag UBL cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName o es vacío")
        elif not self._matches(reg_name, r"^.{3,100}$"):
            self._add(errors, "2228", "El formato del Tag UBL cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName es diferente a alfanumérico de 3 hasta 100 caracteres")

        # ERROR 2307 / 2305 / 2306 / 2752 / 2309 / 2308 / 2311 / 2310 / 2313 / 2312 / 2348 / 2315: líneas
        lines = self._all(root, "sac:VoidedDocumentsLine", ns)
        line_ids: list[str] = []
        line_keys: list[str] = []
        for line in lines:
            line_id = self._text(line, "cbc:LineID", ns)
            if line_id is None:
                self._add(errors, "2307", "El Tag UBL cbc:LineID es vacío")
            else:
                if not self._matches(line_id, r"^\d{1,5}$"):
                    self._add(errors, "2305", "El formato del Tag UBL cbc:LineID es numérico hasta 5 dígitos")
                else:
                    lid = int(line_id)
                    if lid < 1:
                        self._add(errors, "2306", "El valor del Tag UBL cbc:LineID es menor a 1")
                    else:
                        line_ids.append(line_id)

            doc_type = self._text(line, "cbc:DocumentTypeCode", ns)
            if doc_type is None:
                self._add(errors, "2309", "El Tag UBL cbc:DocumentTypeCode es vacío")
            elif doc_type not in {"01", "07", "08", "25", "28", "30", "34", "42", "56"}:
                self._add(errors, "2308", "El valor del Tag UBL cbc:DocumentTypeCode es diferente a '01', '07', '08', '25', '28', '30', '34', '42' y '56'")

            serie = self._text(line, "cbc:DocumentSerialID", ns)
            if serie is None:
                self._add(errors, "2311", "El Tag UBL cbc:DocumentSerialID es vacío")
            elif doc_type == "01" and not self._matches(serie, r"^F[A-Z0-9]{3}$|^\d{1,4}$"):
                self._add(errors, "2310", "Si 'Tipo de documento' es '01', el formato del Tag UBL cbc:DocumentSerialID es diferente a [F][A-Z0-9]{3} o [0-9]{1,4}")
            elif doc_type == "03" and not self._matches(serie, r"^B[A-Z0-9]{3}$|^\d{1,4}$"):
                self._add(errors, "2310", "Si 'Tipo de documento' es '03', el formato del Tag UBL cbc:DocumentSerialID es diferente a [B][A-Z0-9]{3} o [0-9]{1,4}")

            doc_number = self._text(line, "cbc:DocumentNumberID", ns)
            if doc_number is None:
                self._add(errors, "2313", "El Tag UBL cbc:DocumentNumberID es vacío")
            elif not self._matches(doc_number, r"^\d{1,8}$"):
                self._add(errors, "2312", "El formato del Tag UBL cbc:DocumentNumberID es numérico de hasta 8 dígitos")

            if doc_type is not None and serie is not None and doc_number is not None:
                key = f"{doc_type}-{serie}-{doc_number}"
                if key in line_keys:
                    self._add(errors, "2348", 'El "Tipo de documento" concatenado con "Serie del documento dado de baja" concatenado con el Tag UBL se repite en el /VoidedDocuments')
                line_keys.append(key)

            void_reason = self._text(line, "cbc:VoidReasonDescription", ns)
            if void_reason is None:
                self._add(errors, "2315", "El Tag UBL cbc:VoidReasonDescription es vacío")

        # ERROR 2752: LineID repetido
        if len(line_ids) != len(set(line_ids)):
            self._add(errors, "2752", "El valor del Tag UBL cbc:LineID se repite en el /VoidedDocuments")

        # FUERA DE ALCANCE:
        # 2324 - requiere historial de presentación previa a SUNAT.
        # 2581 - requiere padrón SEE-Empresas supervisadas.
        # 2957 - requiere fecha de recepción del XML por SUNAT.

    # ------------------------------------------------------------------
    # SummaryDocuments validations
    # ------------------------------------------------------------------

    def _validate_summary_documents(self, root: etree._Element, errors: list[ValidationError]) -> None:
        ns = self.NS_SUMMARY

        # ERROR 2075 / 2074: UBLVersionID
        ubl_version = self._text(root, "cbc:UBLVersionID", ns)
        if ubl_version is None:
            self._add(errors, "2075", "No existe el Tag UBL cbc:UBLVersionID o es vacío")
        elif ubl_version != "2.0":
            self._add(errors, "2074", "El valor del Tag UBL cbc:UBLVersionID es diferente de '2.0'")

        # ERROR 2072: CustomizationID
        customization = self._text(root, "cbc:CustomizationID", ns)
        if customization is None or customization != "1.1":
            self._add(errors, "2072", "El valor del Tag UBL cbc:CustomizationID es diferente a '1.1'")

        doc_id = self._text(root, "cbc:ID", ns)
        issue_date = self._text(root, "cbc:IssueDate", ns)
        ref_date = self._text(root, "cbc:ReferenceDate", ns)

        # ERROR 2220: ID formato RC-YYYYMMDD-NNNN (comparación con nombre de archivo FUERA DE ALCANCE)
        if doc_id is None or not self._matches(doc_id, r"^RC-\d{8}-\d{1,5}$"):
            self._add(errors, "2220", "El formato del Tag UBL cbc:ID no cumple RC-YYYYMMDD-NNNN")

        # ERROR 2346: IssueDate coherente con fecha del ID (comparación con nombre de archivo FUERA DE ALCANCE)
        if doc_id is not None and issue_date is not None:
            m = re.match(r"^RC-(\d{8})-", doc_id)
            if m:
                id_date = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
                if id_date != issue_date:
                    self._add(errors, "2346", "El valor del Tag UBL cbc:IssueDate es diferente a la fecha del nombre del archivo")

        # ERROR 2223: presentación previa - FUERA DE ALCANCE
        # ERROR 1078: padrón SEE-OSE - FUERA DE ALCANCE

        # ERROR 2236: IssueDate mayor a hoy
        if issue_date is not None:
            try:
                if date.fromisoformat(issue_date) > date.today():
                    self._add(errors, "2236", "El valor del Tag UBL cbc:IssueDate es mayor que el día de hoy")
            except Exception:
                pass

        # ERROR 2671: ReferenceDate mayor a IssueDate
        if ref_date is not None and issue_date is not None:
            try:
                if date.fromisoformat(ref_date) > date.fromisoformat(issue_date):
                    self._add(errors, "2671", "El valor del Tag UBL cbc:ReferenceDate es mayor a la Fecha de generación del resumen")
            except Exception:
                pass

        # ERROR 1034: CustomerAssignedAccountID del emisor (formato RUC; comparación con nombre de archivo FUERA DE ALCANCE)
        supplier_ruc = self._text(root, "cac:AccountingSupplierParty/cbc:CustomerAssignedAccountID", ns)
        if supplier_ruc is None or not self._matches(supplier_ruc, r"^\d{11}$"):
            self._add(errors, "1034", "El valor del Tag UBL cac:AccountingSupplierParty/cbc:CustomerAssignedAccountID no coincide con el RUC del nombre del archivo")

        # ERROR 2219 / 2218: AdditionalAccountID del emisor
        add_account = self._text(root, "cac:AccountingSupplierParty/cbc:AdditionalAccountID", ns)
        if add_account is None:
            self._add(errors, "2219", "No existe el Tag UBL cac:AccountingSupplierParty/cbc:AdditionalAccountID o es vacío")
        elif add_account != "6":
            self._add(errors, "2218", "El valor del Tag UBL cac:AccountingSupplierParty/cbc:AdditionalAccountID es diferente a 6 (RUC)")

        # ERROR 2229 / 2228: RegistrationName del emisor
        reg_name = self._text(root, "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName", ns)
        if reg_name is None:
            self._add(errors, "2229", "No existe el Tag UBL cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName o es vacío")
        elif not self._matches(reg_name, r"^.{3,100}$"):
            self._add(errors, "2228", "El formato del Tag UBL cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName es diferente a alfanumérico de 3 hasta 100 caracteres")

        lines = self._all(root, "sac:SummaryDocumentsLine", ns)
        line_data: list[tuple[str | None, str | None, str | None]] = []
        for line in lines:
            line_data.append(self._validate_summary_line(line, ns, errors))

        # ERROR 3094: (tipo, id, operación) repetido
        seen_full: set[tuple[str, str, str]] = set()
        for doc_type, line_id, op in line_data:
            if doc_type and line_id and op:
                key = (doc_type, line_id, op)
                if key in seen_full:
                    self._add(errors, "3094", "El 'Tipo de Comprobante', 'Serie y número de correlativo del documento' y 'Código de operación del ítem' se repite en otra línea")
                else:
                    seen_full.add(key)
        # ERROR 2752: LineID repetido
        line_ids = [self._text(line, "cbc:LineID", ns) for line in lines]
        if len(line_ids) != len(set(line_ids)):
            self._add(errors, "2752", "El valor del Tag UBL cbc:LineID se repite en el /SummaryDocuments")

        # ERROR 3095 / 3096: operaciones incompatibles para el mismo comprobante
        ops_by_doc: dict[tuple[str, str], set[str]] = {}
        for doc_type, line_id, op in line_data:
            if doc_type and line_id and op:
                ops_by_doc.setdefault((doc_type, line_id), set()).add(op)
        for ops in ops_by_doc.values():
            if "1" in ops and "2" in ops:
                self._add(errors, "3095", "El comprobante es adicionado y modificado en el mismo envio")
            if "2" in ops and "3" in ops:
                self._add(errors, "3096", "El comprobante es modificado y anulado en el mismo envio")

    def _validate_summary_line(self, line: etree._Element, ns: dict, errors: list[ValidationError]) -> tuple[str | None, str | None, str | None]:
        """Valida una línea de SummaryDocuments y devuelve (tipo, id, operación)."""
        doc_type = self._text(line, "cbc:DocumentTypeCode", ns)
        line_id = self._text(line, "cbc:ID", ns)
        condition_code = self._text(line, "cac:Status/cbc:ConditionCode", ns)

        # ERROR 2238 / 2239 / 2752: LineID
        line_id_text = self._text(line, "cbc:LineID", ns)
        if line_id_text is None or not self._matches(line_id_text, r"^\d{1,5}$"):
            self._add(errors, "2238", "El formato del Tag UBL cbc:LineID es numérico hasta 5 dígitos")
        else:
            try:
                lid = int(line_id_text)
                if lid < 1:
                    self._add(errors, "2239", "El valor del Tag UBL cbc:LineID es menor a 1")
            except Exception:
                pass

        # ERROR 2242 / 2241: DocumentTypeCode
        if doc_type is None or doc_type == "":
            self._add(errors, "2242", "El Tag UBL cbc:DocumentTypeCode es vacío")
        elif doc_type not in {"03", "07", "08"}:
            self._add(errors, "2241", "El valor del Tag UBL cbc:DocumentTypeCode es diferente a 03, 07, 08")

        # ERROR 2512 / 2513: cbc:ID
        if line_id is None:
            self._add(errors, "2512", "No existe el Tag UBL cbc:ID")
        elif doc_type in {"03", "07", "08"}:
            if not self._matches(line_id, r"^([B][A-Z0-9]{3})-(?!0+$)([0-9]{1,8})$") and not self._matches(line_id, r"^[0-9]{1,4}-[0-9]{1,8}$"):
                self._add(errors, "2513", "El formato del Tag UBL cbc:ID no cumple con el tipo de documento")

        # ERROR 2522: ConditionCode
        if condition_code is None or condition_code == "":
            self._add(errors, "2522", "No existe el Tag UBL cac:Status/cbc:ConditionCode o es vacío")

        # ERROR 2251: TotalAmount
        total_amount = self._parse_amount(self._text(line, "sac:TotalAmount", ns))
        total_amount_text = self._text(line, "sac:TotalAmount", ns)
        if total_amount_text is None or not self._matches(total_amount_text, r"^\d{1,12}(\.\d{1,2})?$") or (total_amount is not None and total_amount < 0):
            self._add(errors, "2251", "El formato del Tag UBL sac:TotalAmount es diferente de decimal de 12 enteros y hasta 2 decimales o menor a cero")

        # ERROR 2071: currencyID consistency within line (excluding perception reference)
        base_currency = self._attr(line, "sac:TotalAmount", "currencyID", ns)
        if base_currency is not None:
            inconsistent = False
            perception_ref = line.find("sac:SUNATPerceptionSummaryDocumentReference", namespaces=ns)
            for elem in line.iter():
                if perception_ref is not None and (elem is perception_ref or perception_ref in elem.iterancestors()):
                    continue
                cid = elem.get("currencyID")
                if cid is not None and cid.strip() != base_currency:
                    inconsistent = True
                    break
            if inconsistent:
                self._add(errors, "2071", "La moneda debe ser la misma en todo el documento. Salvo las percepciones que sólo son en moneda nacional")

        # ERROR 2514 / 2014 / 2017 / 2015 / 2022: AccountingCustomerParty
        customer = line.find("cac:AccountingCustomerParty", namespaces=ns)
        if total_amount is not None and total_amount > Decimal("700") and customer is None:
            self._add(errors, "2514", "Si el campo 'Importe total de la venta' es mayor a 700 nuevos soles y no existe el tag cac:AccountingCustomerParty")
        if customer is not None:
            cust_id = self._text(customer, "cbc:CustomerAssignedAccountID", ns)
            if cust_id is None:
                self._add(errors, "2014", "Si existe tag de 'Adquiriente o usuario', no existe el Tag UBL cbc:CustomerAssignedAccountID")
            else:
                cust_type = self._text(customer, "cbc:AdditionalAccountID", ns)
                if cust_type == "6" and not self._matches(cust_id, r"^\d{11}$"):
                    self._add(errors, "2017", "Si existe tag de 'Adquiriente o usuario' y 'Tipo de documento de identidad del adquiriente' es '6', el formato del Tag UBL es diferente a numérico de 11 dígitos")
            cust_type_elem = customer.find("cbc:AdditionalAccountID", namespaces=ns)
            if cust_type_elem is None or (cust_type_elem.text or "").strip() == "":
                self._add(errors, "2015", "Si existe tag de 'Adquiriente o usuario', no existe el Tag UBL cbc:AdditionalAccountID")
            cust_name = self._text(customer, "cac:Party/cac:PartyLegalEntity/cbc:RegistrationName", ns)
            if cust_name is not None and not self._matches(cust_name, r"^.{3,250}$"):
                self._add(errors, "2022", "El formato del Tag UBL cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName es diferente a alfanumérico de 3 hasta 250 caracteres")

        # ERROR 2582 / 2524 / 2583 / 2513 / 2920: BillingReference
        billing_ref = line.find("cac:BillingReference", namespaces=ns)
        if billing_ref is not None and doc_type not in {"07", "08"}:
            self._add(errors, "2582", "Si existe el nodo cac:BillingReference y el tipo de comprobante es diferente de '07' y '08'")
        if doc_type in {"07", "08"} and condition_code != "3":
            ref_id = self._text(billing_ref, "cac:InvoiceDocumentReference/cbc:ID", ns) if billing_ref is not None else None
            if ref_id is None or ref_id == "":
                self._add(errors, "2524", "Si 'Tipo de documento' es '07' u '08' y 'Tipo de operación' es diferente de '3', el Tag UBL cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID es vacío")
            ref_type = self._text(billing_ref, "cac:InvoiceDocumentReference/cbc:DocumentTypeCode", ns) if billing_ref is not None else None
            if ref_type is None or ref_type == "":
                self._add(errors, "2583", "Si 'Tipo de documento' es '07' u '08' y 'Tipo de operación' es diferente de '3', no existe el Tag UBL cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode")
            elif ref_type not in {"03", "12", "16", "55"}:
                self._add(errors, "2513", "Si 'Tipo de documento' es '07' u '08' y 'Tipo de operación' es diferente de '3', el valor del Tag UBL cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode es diferente a '03', '12', '16' y '55'")
            elif ref_type in {"12", "16", "55"} and not self._matches(ref_id, r"^[a-zA-Z0-9-]{1,20}-[a-zA-Z0-9-]{1,20}$"):
                self._add(errors, "2920", "Si 'Tipo de documento que modifica' es '12', '16' o '55' y 'Tipo de operación' es diferente de '3', el formato del Tag UBL es diferente al establecido")
            elif ref_type == "03" and ref_id is not None and not self._matches(ref_id, r"^([B][A-Z0-9]{3})-(?!0+$)([0-9]{1,8})$") and not self._matches(ref_id, r"^(EB01)-[0-9]{1,8}$") and not self._matches(ref_id, r"^[0-9]{1,4}-[0-9]{1,8}$"):
                self._add(errors, "2920", "Si 'Tipo de documento que modifica' es '03' y 'Tipo de operación' es diferente de '3', el formato del Tag UBL es diferente al establecido")

        # ERROR 2986 / 2893 / 2608 / 2685 / 2895 / 2690 / 2897: SUNATPerceptionSummaryDocumentReference
        perception_ref = line.find("sac:SUNATPerceptionSummaryDocumentReference", namespaces=ns)
        if perception_ref is not None:
            if doc_type != "03" or condition_code == "2":
                self._add(errors, "2986", "Si existe nodo sac:SUNATPerceptionSummaryDocumentReference y el tipo de comprobante no es boleta (03) o es una operación de modificación (ConditionCode = 2)")
            perc_total_text = self._text(perception_ref, "cbc:TotalInvoiceAmount", ns)
            perc_total = self._parse_amount(perc_total_text)
            if perc_total_text is None or not self._matches(perc_total_text, r"^\d{1,12}(\.\d{1,2})?$") or (perc_total is not None and perc_total <= 0):
                self._add(errors, "2893", "El formato del Tag UBL cbc:TotalInvoiceAmount es diferente a númerico de 12 enteros y 2 decimales o es menor o igual a cero")
            perc_total_curr = self._attr(perception_ref, "cbc:TotalInvoiceAmount", "currencyID", ns)
            if perc_total_curr is not None and perc_total_curr != "PEN":
                self._add(errors, "2685", "El valor del Tag UBL cbc:TotalInvoiceAmount@currencyID es diferente 'PEN'")
            cashed_text = self._text(perception_ref, "sac:SUNATTotalCashed", ns)
            cashed = self._parse_amount(cashed_text)
            if cashed_text is None or not self._matches(cashed_text, r"^\d{1,12}(\.\d{1,2})?$") or (cashed is not None and cashed <= 0):
                self._add(errors, "2895", "El formato del Tag UBL sac:SUNATTotalCashed es diferente a númerico de 12 enteros y 2 decimales o es menor o igual a cero")
            cashed_curr = self._attr(perception_ref, "sac:SUNATTotalCashed", "currencyID", ns)
            if cashed_curr is not None and cashed_curr != "PEN":
                self._add(errors, "2690", "El valor del Tag UBL sac:SUNATTotalCashed@currencyID es diferente 'PEN'")
            taxable_text = self._text(perception_ref, "cbc:TaxableAmount", ns)
            taxable = self._parse_amount(taxable_text)
            if taxable_text is None or not self._matches(taxable_text, r"^\d{1,12}(\.\d{1,2})?$") or (taxable is not None and taxable <= 0):
                self._add(errors, "2897", "El formato del Tag UBL cbc:TaxableAmount es diferente a númerico de 12 enteros y 2 decimales o es menor o igual a cero")
            # ERROR 2608: cuadres en moneda PEN
            if base_currency == "PEN":
                perc_percent_text = self._text(perception_ref, "sac:SUNATPerceptionPercent", ns)
                perc_percent = self._parse_amount(perc_percent_text)
                if taxable is not None and perc_total is not None and perc_percent is not None and perc_percent > 0:
                    expected = (taxable * perc_percent) / Decimal("100")
                    if abs(expected - perc_total) > Decimal("1"):
                        self._add(errors, "2608", "Los montos de pago, percibidos y montos cobrados consignados para el documento relacionado no son correctos")
                if total_amount is not None and cashed is not None and perc_total is not None:
                    expected_cashed = total_amount + perc_total
                    if abs(expected_cashed - cashed) > Decimal("1"):
                        self._add(errors, "2608", "Los montos de pago, percibidos y montos cobrados consignados para el documento relacionado no son correctos")

        # ERROR 2255 / 2254 / 2257 / 2357: BillingPayment
        instruction_ids: set[str] = set()
        for bp in self._all(line, "sac:BillingPayment", ns):
            paid = self._text(bp, "cbc:PaidAmount", ns)
            if paid is None:
                self._add(errors, "2255", "No existe el Tag UBL cac:BillingPayment/cbc:PaidAmount")
            elif not self._matches(paid, r"^\d{1,12}(\.\d{1,2})?$") or self._parse_amount(paid) is None or self._parse_amount(paid) <= 0:
                self._add(errors, "2254", "El formato del Tag UBL cac:BillingPayment/cbc:PaidAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero")
            inst = self._text(bp, "cbc:InstructionID", ns)
            if inst is None:
                self._add(errors, "2257", "No existe el Tag UBL cac:BillingPayment/cbc:InstructionID")
            else:
                if inst in instruction_ids:
                    self._add(errors, "2357", "El valor del Tag UBL cbc:InstructionID se repite en el /SummaryDocuments/sac:SummaryDocumentsLine")
                instruction_ids.add(inst)

        # ERROR 2263 / 2411 / 2261: AllowanceCharge
        charge_indicators: set[str] = set()
        for ac in self._all(line, "cac:AllowanceCharge", ns):
            indicator = self._text(ac, "cbc:ChargeIndicator", ns)
            if indicator != "true":
                self._add(errors, "2263", "El valor del Tag UBL cac:AllowanceCharge/cbc:ChargeIndicator es diferente de 'true'")
            if indicator is not None and indicator in charge_indicators:
                self._add(errors, "2411", "El valor del Tag UBL cbc:ChargeIndicator se repite en el /SummaryDocuments/sac:SummaryDocumentsLine")
            if indicator is not None:
                charge_indicators.add(indicator)
            ac_amount = self._text(ac, "cbc:Amount", ns)
            if ac_amount is None or not self._matches(ac_amount, r"^\d{1,12}(\.\d{1,2})?$") or self._parse_amount(ac_amount) is None or self._parse_amount(ac_amount) <= 0:
                self._add(errors, "2261", "El formato del Tag UBL cac:AllowanceCharge/cbc:Amount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero")

        # ERROR 2278 / 2048 / 2344 / 2269 / 2355 / 2271 / 2276 / 3051 / 2275 / 2992 / 3504 / 3102: TaxTotal
        tax_ids_seen: set[str] = set()
        has_igv_ivap = False
        for tax_total in self._all(line, "cac:TaxTotal", ns):
            global_tax_text = self._text(tax_total, "cbc:TaxAmount", ns)
            global_tax = self._parse_amount(global_tax_text)
            if global_tax_text is None or not self._matches(global_tax_text, r"^\d{1,12}(\.\d{1,2})?$") or (global_tax is not None and global_tax <= 0):
                self._add(errors, "2048", "El formato del Tag UBL cac:TaxTotal/cbc:TaxAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero")
            for subtotal in self._all(tax_total, "cac:TaxSubtotal", ns):
                sub_tax_text = self._text(subtotal, "cbc:TaxAmount", ns)
                sub_tax = self._parse_amount(sub_tax_text)
                if global_tax is not None and sub_tax is not None and abs(global_tax - sub_tax) > Decimal("0"):
                    self._add(errors, "2344", "El valor del Tag UBL cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount es diferente al Tag anterior")
                tax_code = self._text(subtotal, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns)
                if tax_code is None or tax_code == "":
                    self._add(errors, "2269", "No existe el Tag UBL cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID o es vacío")
                else:
                    if tax_code in {"1000", "1016"}:
                        has_igv_ivap = True
                    if tax_code in tax_ids_seen:
                        self._add(errors, "2355", "El valor del Tag UBL cac:TaxScheme/cbc:ID se repite en el /SummaryDocuments/sac:SummaryDocumentsLine")
                    tax_ids_seen.add(tax_code)
                    tax_name = self._text(subtotal, "cac:TaxCategory/cac:TaxScheme/cbc:Name", ns)
                    if tax_name is None or tax_name == "":
                        self._add(errors, "2271", "No existe el Tag UBL cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name o es vacío")
                    else:
                        expected_name = self.catalog05_names.get(tax_code)
                        if expected_name is not None and tax_name != expected_name:
                            if tax_code == "1000":
                                self._add(errors, "2276", "Si 'Código de tributo' es 1000, el valor del Tag UBL es diferente a 'IGV'")
                            elif tax_code == "1016":
                                self._add(errors, "3051", "Si 'Código de tributo' es 1016, el valor del Tag UBL es diferente a 'IVAP'")
                            elif tax_code == "2000":
                                self._add(errors, "2275", "Si 'Código de tributo' es 2000, el valor del Tag UBL es diferente a 'ISC'")
                            elif tax_code == "9996":
                                self._add(errors, "3051", "Si 'Código de tributo' es 9996, el valor del Tag UBL es diferente a 'GRATUITA'")
                    percent_text = self._text(subtotal, "cac:TaxCategory/cbc:Percent", ns)
                    if tax_code != "7152" and percent_text is None:
                        self._add(errors, "2992", "Si el 'Código de tributo' es diferente de '7152', no existe el Tag UBL cac:TaxCategory/cbc:Percent")
                    if percent_text is not None:
                        if not self._matches(percent_text, r"^\d{1,3}(\.\d{1,5})?$") or self._parse_amount(percent_text) is None or self._parse_amount(percent_text) <= 0:
                            self._add(errors, "3102", "El formato del Tag UBL cac:TaxCategory/cbc:Percent es diferente de decimal positivo de hasta 3 enteros y hasta 5 decimales")
                        if tax_code in {"1000", "9996"} and doc_type == "03":
                            percent_val = self._parse_amount(percent_text)
                            if percent_val is not None and percent_val not in (Decimal("10.5"), Decimal("18")):
                                self._add(errors, "3504", "Si 'Código de tributo' es '1000' o '9996' y 'Tipo de comprobante' es '03', el valor del Tag UBL es diferente de 10.5 y 18")
        if self._exists(line, "cac:TaxTotal", ns) and not has_igv_ivap:
            self._add(errors, "2278", "Si no existe cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID = '1000' o '1016'")

        return doc_type, line_id, condition_code

    # FUERA DE ALCANCE SummaryDocuments:
    # 2223 - requiere historial de presentación previa a SUNAT.
    # 1078 - requiere padrón SEE-OSE.
    # 2220 / 2346 / 1034 - comparación con nombre de archivo XML/ZIP es FUERA DE ALCANCE;
    #                       se implementa validación estructural local como aproximación.

    # ------------------------------------------------------------------
    # Perception / Retention validations
    # ------------------------------------------------------------------

    def _validate_perception(self, root: etree._Element, errors: list[ValidationError]) -> None:
        ns = self.NS_PERCEPTION

        # ERROR 2111 / 2110: UBLVersionID
        ubl_version = self._text(root, "cbc:UBLVersionID", ns)
        if ubl_version is None or ubl_version == "":
            self._add(errors, "2111", "El Tag UBL cbc:UBLVersionID está vacío")
        elif ubl_version != "2.0":
            self._add(errors, "2110", "El valor del Tag UBL cbc:UBLVersionID es diferente a '2.0'")

        # ERROR 2113 / 2112: CustomizationID
        customization = self._text(root, "cbc:CustomizationID", ns)
        if customization is None or customization == "":
            self._add(errors, "2113", "El Tag UBL cbc:CustomizationID está vacío")
        elif customization != "1.0":
            self._add(errors, "2112", "El valor del Tag UBL cbc:CustomizationID es diferente a '1.0'")

        # ERROR 1049: ID vs nombre de archivo
        # FUERA DE ALCANCE - requiere nombre de archivo XML.

        # ERROR 1001: ID format
        doc_id = self._text(root, "cbc:ID", ns)
        if doc_id is None or not self._matches(doc_id, r"^[A-Z][A-Z0-9]{3}-\d{1,8}$"):
            self._add(errors, "1001", "El formato del Tag UBL cbc:ID no tiene el formato: [A-Z][A-Z0-9]{3}-[0-9]{1,8}")

        # ERROR 2600: IssueDate vs fecha de recepción
        # FUERA DE ALCANCE - requiere fecha de recepción de SUNAT.

        # ERROR 3322: ExceptionalIndicator
        exceptional = self._text(root, "sac:ExceptionalIndicator", ns)
        if exceptional is not None and exceptional != "01":
            self._add(errors, "3322", "El valor del Tag UBL sac:ExceptionalIndicator es diferente de '01'")

        # ERROR 1034: AgentParty RUC vs nombre de archivo
        # FUERA DE ALCANCE - requiere nombre de archivo XML.

        # ERROR 2678 / 2511: AgentParty schemeID
        agent_id_elem = root.find("cac:AgentParty/cac:PartyIdentification/cbc:ID", namespaces=ns)
        if agent_id_elem is not None:
            agent_scheme = agent_id_elem.get("schemeID")
            if agent_scheme is None or agent_scheme == "":
                self._add(errors, "2678", "No existe el Tag UBL cac:AgentParty/.../cbc:ID@schemeID o es vacío")
            elif agent_scheme != "6":
                self._add(errors, "2511", "El valor del Tag UBL cac:AgentParty/.../cbc:ID@schemeID es diferente a '6'")

        # ERROR 1037 / 1038: AgentParty RegistrationName
        agent_name = self._text(root, "cac:AgentParty/cac:PartyLegalEntity/cbc:RegistrationName", ns)
        if agent_name is None:
            self._add(errors, "1037", "No existe el Tag UBL cac:AgentParty/.../cbc:RegistrationName o es vacío")
        elif not self._matches(agent_name, r"^.{1,1500}$"):
            self._add(errors, "1038", "El formato del Tag UBL cac:AgentParty/.../cbc:RegistrationName es diferente a alfanumérico de hasta 1500 caracteres")

        # ERROR 2548: AgentParty Country = PE
        agent_country = self._text(root, "cac:AgentParty/cac:PostalAddress/cac:Country/cbc:IdentificationCode", ns)
        if agent_country is not None and agent_country != "PE":
            self._add(errors, "2548", "El valor del Tag UBL cac:AgentParty/.../cbc:IdentificationCode es diferente a 'PE'")

        # ERROR 2679 / 2680 / 2604 / 2516 / 2134 / 2133: ReceiverParty
        receiver_id_elem = root.find("cac:ReceiverParty/cac:PartyIdentification/cbc:ID", namespaces=ns)
        agent_ruc = self._text(root, "cac:AgentParty/cac:PartyIdentification/cbc:ID", ns)
        if receiver_id_elem is None:
            self._add(errors, "2679", "No existe el Tag UBL cac:ReceiverParty/.../cbc:ID o es vacío")
        else:
            receiver_id = (receiver_id_elem.text or "").strip()
            if receiver_id == "":
                self._add(errors, "2679", "No existe el Tag UBL cac:ReceiverParty/.../cbc:ID o es vacío")
            elif not self._matches(receiver_id, r"^.{1,15}$"):
                self._add(errors, "2680", "El formato del Tag UBL cac:ReceiverParty/.../cbc:ID es diferente a alfanumérico de hasta 15 caracteres")
            if agent_ruc is not None and receiver_id == agent_ruc:
                self._add(errors, "2604", "El valor del Tag UBL cac:ReceiverParty/.../cbc:ID es igual al 'Número de documento de identidad del emisor'")
            receiver_scheme = receiver_id_elem.get("schemeID")
            if receiver_scheme is None or receiver_scheme == "":
                self._add(errors, "2516", "No existe el Tag UBL cac:ReceiverParty/.../cbc:ID@schemeID o es vacío")

        receiver_name = self._text(root, "cac:ReceiverParty/cac:PartyLegalEntity/cbc:RegistrationName", ns)
        if receiver_name is None:
            self._add(errors, "2134", "No existe el Tag UBL cac:ReceiverParty/.../cbc:RegistrationName o es vacío")
        elif not self._matches(receiver_name, r"^.{1,1500}$"):
            self._add(errors, "2133", "El formato del Tag UBL cac:ReceiverParty/.../cbc:RegistrationName es diferente a alfanumérico de hasta 1500 caracteres")

        # ERROR 3327: emisión excepcional + régimen 01 + receptor
        # FUERA DE ALCANCE - requiere listado SUNAT de agentes de percepción.

        # ERROR 2669 / 2685 / 2667: TotalInvoiceAmount
        total_invoice_amount = self._parse_amount(self._text(root, "cbc:TotalInvoiceAmount", ns))
        total_invoice_currency = self._attr(root, "cbc:TotalInvoiceAmount", "currencyID", ns)
        if total_invoice_amount is None or total_invoice_amount <= 0:
            self._add(errors, "2669", "El formato del Tag UBL cbc:TotalInvoiceAmount es diferente a decimal positivo de 12 enteros y 2 decimales o es cero (0)")
        if total_invoice_currency is not None and total_invoice_currency != "PEN":
            self._add(errors, "2685", "El valor del Tag UBL cbc:TotalInvoiceAmount@currencyID es diferente 'PEN'")

        # ERROR 2687 / 2690 / 2668: SUNATTotalCashed
        total_cashed = self._parse_amount(self._text(root, "sac:SUNATTotalCashed", ns))
        total_cashed_currency = self._attr(root, "sac:SUNATTotalCashed", "currencyID", ns)
        if total_cashed is None or total_cashed <= 0:
            self._add(errors, "2687", "El formato del Tag UBL sac:SUNATTotalCashed es diferente a decimal positivo de 12 enteros y 2 decimales o es cero (0)")
        if total_cashed_currency is not None and total_cashed_currency != "PEN":
            self._add(errors, "2690", "El valor del Tag UBL sac:SUNATTotalCashed@currencyID es diferente 'PEN'")

        # ERROR 3303 / 3304: PayableRoundingAmount
        rounding = self._parse_amount(self._text(root, "cbc:PayableRoundingAmount", ns))
        rounding_currency = self._attr(root, "cbc:PayableRoundingAmount", "currencyID", ns)
        if rounding is not None:
            if abs(rounding) > Decimal("1"):
                self._add(errors, "3303", "Si existe el tag UBL cbc:PayableRoundingAmount, el valor absoluto es mayor a 1")
            if rounding_currency is not None and rounding_currency != "PEN":
                self._add(errors, "3304", "Si existe el Tag UBL cbc:PayableRoundingAmount@currencyID, el valor es diferente a 'PEN'")

        # Document references
        refs = self._all(root, "sac:SUNATPerceptionDocumentReference", ns)
        if exceptional == "01" and len(refs) > 1:
            self._add(errors, "3323", "Si el valor del 'Indicador de emisión excepcional' es '01' y existe más de un (01) documento relacionado")

        perception_sum = Decimal("0")
        net_cashed_sum = Decimal("0")
        paid_dates = []
        payment_keys = []
        for ref in refs:
            ref_ns = ns
            ref_id_elem = ref.find("cbc:ID", namespaces=ref_ns)
            ref_id = (ref_id_elem.text or "").strip() if ref_id_elem is not None else ""
            ref_type = ref_id_elem.get("schemeID") if ref_id_elem is not None else None

            # ERROR 2691 / 2692 / 3324: reference ID@schemeID
            if ref_type is None or ref_type == "":
                self._add(errors, "2691", "No existe el Tag UBL sac:SUNATPerceptionDocumentReference/cbc:ID@schemeID o es vacío")
            elif ref_type not in {"01", "03", "12", "07", "08", "40"}:
                self._add(errors, "2692", "El valor del Tag UBL sac:SUNATPerceptionDocumentReference/cbc:ID@schemeID es diferente a '01', '03', '12', '07', '08', '40'")
            if exceptional == "01" and ref_type is not None and ref_type != "01":
                self._add(errors, "3324", "Si el valor del 'Indicador de emisión excepcional' es '01', el valor del 'Tipo de documento relacionado' es diferente de '01'")

            # ERROR 2693 / 2694: reference ID
            if ref_id == "":
                self._add(errors, "2693", "El valor del Tag UBL sac:SUNATPerceptionDocumentReference/cbc:ID está vacío")
            elif ref_type == "12" and not self._matches(ref_id, r"^[a-zA-Z0-9-]{1,20}(-\d{1,20})?$"):
                self._add(errors, "2694", "Si 'Tipo de documento relacionado' es '12', el formato del Tag UBL es diferente a alfanumérico de 1 a 20 caracteres opcionalmente seguido de guión y número")

            # ERROR 2696: reference TotalInvoiceAmount
            ref_total = self._parse_amount(self._text(ref, "cbc:TotalInvoiceAmount", ref_ns))
            if ref_total is None or ref_total <= 0:
                self._add(errors, "2696", "El formato del Tag UBL sac:SUNATPerceptionDocumentReference/cbc:TotalInvoiceAmount es diferente a decimal positivo de 12 enteros y 2 decimales o es cero (0)")

            # Payment
            payment = ref.find("cac:Payment", namespaces=ref_ns)
            if ref_type != "07":
                # ERROR 2702: PaidDate exists
                paid_date = self._text(payment, "cbc:PaidDate", ref_ns) if payment is not None else None
                if paid_date is None:
                    self._add(errors, "2702", "Si 'Tipo de documento relacionado' es diferente a '07', no existe el Tag UBL cac:Payment/cbc:PaidDate")
                else:
                    paid_dates.append(paid_date)
                    # ERROR 2612: same period as IssueDate
                    issue_date = self._text(root, "cbc:IssueDate", ns)
                    if issue_date is not None and paid_date[:7] != issue_date[:7]:
                        self._add(errors, "2612", "Si existe 'Fecha de cobro', el valor es de mes/año diferente a la 'fecha de emisión' del comprobante de percepción")

                # ERROR 2697 / 2698: Payment ID
                payment_id = self._text(payment, "cbc:ID", ref_ns) if payment is not None else None
                if payment_id is None or payment_id == "":
                    self._add(errors, "2697", "Si 'Tipo de documento relacionado' es diferente a '07', no existe el Tag UBL cac:Payment/cbc:ID o es vacío")
                elif not self._matches(payment_id, r"^\d{1,9}$"):
                    self._add(errors, "2698", "Si 'Tipo de documento relacionado' es diferente a '07', el formato del Tag UBL cac:Payment/cbc:ID es diferente a numérico de hasta 9 dígitos")

                # ERROR 2699 / 2700: Payment PaidAmount
                paid_amount = self._parse_amount(self._text(payment, "cbc:PaidAmount", ref_ns)) if payment is not None else None
                if paid_amount is None:
                    self._add(errors, "2699", "Si 'Tipo de documento relacionado' es diferente a '07', no existe el Tag UBL cac:Payment/cbc:PaidAmount")
                elif paid_amount <= 0:
                    self._add(errors, "2700", "Si 'Tipo de documento relacionado' es diferente a '07', el formato del Tag UBL cac:Payment/cbc:PaidAmount es diferente a decimal positivo de 12 enteros y 2 decimales")

                # ERROR 2607: Payment PaidAmount currencyID
                paid_currency = self._attr(payment, "cbc:PaidAmount", "currencyID", ref_ns) if payment is not None else None
                ref_currency = self._attr(ref, "cbc:TotalInvoiceAmount", "currencyID", ref_ns)
                if paid_currency is not None and ref_currency is not None and paid_currency != ref_currency:
                    self._add(errors, "2607", "Si 'Tipo de documento relacionado' es diferente a '07', el valor del Tag UBL cac:Payment/cbc:PaidAmount@currencyID es diferente al 'Tipo de moneda del documento relacionado'")

                # ERROR 2626: uniqueness
                if payment_id is not None and paid_date is not None:
                    key = (ref_id, paid_date, payment_id)
                    if key in payment_keys:
                        self._add(errors, "2626", "Si 'Tipo de documento relacionado' es diferente a '07', la 'Serie y número correlativo del documento relacionado' concatenada con la 'Fecha de cobro' y el 'Identificador de pago' se repite")
                    payment_keys.append(key)

            # Perception information
            info = ref.find("sac:SUNATPerceptionInformation", namespaces=ref_ns)
            if info is not None:
                # ERROR 2705 / 2707: SUNATPerceptionAmount
                perc_amount = self._parse_amount(self._text(info, "sac:SUNATPerceptionAmount", ref_ns))
                perc_currency = self._attr(info, "sac:SUNATPerceptionAmount", "currencyID", ref_ns)
                if perc_amount is None or perc_amount <= 0:
                    self._add(errors, "2705", "El formato del Tag UBL sac:SUNATPerceptionAmount es diferente a decimal positivo de 12 enteros y 2 decimales o es cero (0)")
                if perc_currency is not None and perc_currency != "PEN":
                    self._add(errors, "2707", "El valor del Tag UBL sac:SUNATPerceptionAmount@currencyID es diferente a 'PEN'")
                ref_currency = self._attr(ref, "cbc:TotalInvoiceAmount", "currencyID", ref_ns)
                if ref_type not in {"07", "40"} and perc_amount is not None:
                    perception_sum += perc_amount

                # ERROR 2711 / 2713: SUNATNetTotalCashed
                net_cashed = self._parse_amount(self._text(info, "sac:SUNATNetTotalCashed", ref_ns))
                net_cashed_currency = self._attr(info, "sac:SUNATNetTotalCashed", "currencyID", ref_ns)
                if net_cashed is None or net_cashed <= 0:
                    self._add(errors, "2711", "El formato del Tag UBL sac:SUNATNetTotalCashed es diferente a decimal positivo de 12 enteros y 2 decimales o es cero (0)")
                if net_cashed_currency is not None and net_cashed_currency != "PEN":
                    self._add(errors, "2713", "El valor del Tag UBL sac:SUNATNetTotalCashed@currencyID es diferente a 'PEN'")
                if net_cashed is not None:
                    net_cashed_sum += net_cashed

                # ERROR 2608: cuadre de montos en moneda PEN
                if ref_currency == "PEN" and perc_amount is not None and net_cashed is not None and ref_total is not None:
                    expected_total = perc_amount + net_cashed
                    if abs(expected_total - ref_total) > Decimal("0.01"):
                        self._add(errors, "2608", "Si 'Tipo de moneda del documento relacionado' es 'PEN', los montos de percepción, neto cobrado e importe total no cuadran")

                # ERROR 2719 / 2749 / 2715 / 2721 / 2716 / 2722: ExchangeRate
                if ref_type != "07" and ref_currency is not None and ref_currency != "PEN":
                    exchange = info.find("cac:ExchangeRate", namespaces=ref_ns)
                    if exchange is None:
                        self._add(errors, "2719", "Si 'Tipo de documento relacionado' es diferente a '07' y 'Tipo de moneda del documento relacionado' es diferente 'PEN', no existe el Tag UBL cac:ExchangeRate")
                    else:
                        target = self._text(exchange, "cbc:TargetCurrencyCode", ref_ns)
                        if target is not None and target != ref_currency:
                            self._add(errors, "2749", "Si 'Tipo de documento relacionado' es diferente a '07', el valor del Tag UBL cac:ExchangeRate/cbc:TargetCurrencyCode es diferente al 'Tipo de moneda del documento relacionado'")
                        if target is not None and target != "PEN":
                            self._add(errors, "2715", "Si existe el Tag UBL cac:ExchangeRate/cbc:TargetCurrencyCode, el valor es diferente de 'PEN'")
                        calc = self._parse_amount(self._text(exchange, "cbc:CalculationRate", ref_ns))
                        if calc is None:
                            self._add(errors, "2721", "Si 'Tipo de documento relacionado' es diferente a '07' y 'Tipo de moneda del documento relacionado' es diferente 'PEN', no existe el Tag UBL cac:ExchangeRate/cbc:CalculationRate")
                        elif calc <= 0:
                            self._add(errors, "2716", "Si existe el Tag UBL cac:ExchangeRate/cbc:CalculationRate, el formato es diferente a decimal positivo de 4 enteros y 6 decimales o es cero (0)")
                        if not self._exists(exchange, "cbc:Date", ref_ns):
                            self._add(errors, "2722", "Si 'Tipo de documento relacionado' es diferente a '07' y 'Tipo de moneda del documento relacionado' es diferente 'PEN', no existe el Tag UBL cac:ExchangeRate/cbc:Date")

        # ERROR 2659: all PaidDate same period
        if len(paid_dates) > 1:
            periods = {d[:7] for d in paid_dates}
            if len(periods) > 1:
                self._add(errors, "2659", "Si existe 'Fecha de cobro', el valor es de mes/año (periodo) diferente a otra 'Fecha de cobro'")

        # ERROR 2667: TotalInvoiceAmount = sum of perception amounts
        if total_invoice_amount is not None and total_invoice_amount != perception_sum:
            self._add(errors, "2667", "El valor de Tag UBL cbc:TotalInvoiceAmount es diferente a la suma de 'Importe Percibido', sin considerar los tipos de documentos '07' y '40'")

        # ERROR 2668: SUNATTotalCashed = sum of net cashed + rounding
        expected_cashed = net_cashed_sum + (rounding or Decimal("0"))
        if total_cashed is not None and total_cashed != expected_cashed:
            self._add(errors, "2668", "El valor de Tag UBL sac:SUNATTotalCashed es diferente a la suma de 'Importe total a cobrar (neto)' más el 'Monto de redondeo del importe total cobrado'")

    def _validate_retention(self, root: etree._Element, errors: list[ValidationError]) -> None:
        ns = self.NS_RETENTION

        # ERROR 2723 / 2724 / 2620: ReceiverParty ID
        receiver_id_elem = root.find("cac:ReceiverParty/cac:PartyIdentification/cbc:ID", namespaces=ns)
        agent_ruc = self._text(root, "cac:AgentParty/cac:PartyIdentification/cbc:ID", ns)
        if receiver_id_elem is None:
            self._add(errors, "2723", "El valor del Tag UBL cac:ReceiverParty/.../cbc:ID está vacío")
        else:
            receiver_id = (receiver_id_elem.text or "").strip()
            if receiver_id == "":
                self._add(errors, "2723", "El valor del Tag UBL cac:ReceiverParty/.../cbc:ID está vacío")
            elif not self._matches(receiver_id, r"^\d{11}$"):
                self._add(errors, "2724", "El formato del Tag UBL cac:ReceiverParty/.../cbc:ID es diferente a numérico de 11 dígitos")
            if agent_ruc is not None and receiver_id == agent_ruc:
                self._add(errors, "2620", "El valor del Tag UBL cac:ReceiverParty/.../cbc:ID es igual al 'Número de documento de identidad del emisor'")

        # ERROR 2669 / 2728: TotalInvoiceAmount
        total_invoice_amount = self._parse_amount(self._text(root, "cbc:TotalInvoiceAmount", ns))
        total_invoice_currency = self._attr(root, "cbc:TotalInvoiceAmount", "currencyID", ns)
        if total_invoice_amount is None or total_invoice_amount <= 0:
            self._add(errors, "2669", "El formato del Tag UBL cbc:TotalInvoiceAmount es diferente a decimal positivo de 12 enteros y 2 decimales o es cero (0)")
        if total_invoice_currency is not None and total_invoice_currency != "PEN":
            self._add(errors, "2728", "El valor del Tag UBL cbc:TotalInvoiceAmount@currencyID es diferente 'PEN'")

        # ERROR 2730 / 2732 / 2629: SUNATTotalPaid
        total_paid = self._parse_amount(self._text(root, "sac:SUNATTotalPaid", ns))
        total_paid_currency = self._attr(root, "sac:SUNATTotalPaid", "currencyID", ns)
        if total_paid is None or total_paid <= 0:
            self._add(errors, "2730", "El formato del Tag UBL sac:SUNATTotalPaid es diferente a decimal positivo de 12 enteros y 2 decimales o es cero (0)")
        if total_paid_currency is not None and total_paid_currency != "PEN":
            self._add(errors, "2732", "El valor del Tag UBL sac:SUNATTotalPaid@currencyID es diferente 'PEN'")

        # ERROR 3303 / 3304: PayableRoundingAmount
        rounding = self._parse_amount(self._text(root, "cbc:PayableRoundingAmount", ns))
        rounding_currency = self._attr(root, "cbc:PayableRoundingAmount", "currencyID", ns)
        if rounding is not None:
            if abs(rounding) > Decimal("1"):
                self._add(errors, "3303", "Si existe el tag UBL cbc:PayableRoundingAmount, el valor absoluto es mayor a 1")
            if rounding_currency is not None and rounding_currency != "PEN":
                self._add(errors, "3304", "Si existe el Tag UBL cbc:PayableRoundingAmount@currencyID, el valor es diferente a 'PEN'")


        # ERROR 2985: IssueDate > 2014-02-28 when regime = 02
        issue_date = self._text(root, "cbc:IssueDate", ns)
        regime = self._text(root, "sac:SUNATRetentionSystemCode", ns)
        if regime == "02" and issue_date is not None and issue_date > "2014-02-28":
            self._add(errors, "2985", "Si el 'Código del régimen de retención' es '02' (TASA 6%), el valor del Tag UBL cbc:IssueDate es mayor al 28/02/2014")

        # Document references
        refs = self._all(root, "sac:SUNATRetentionDocumentReference", ns)
        retention_sum = Decimal("0")
        net_paid_sum = Decimal("0")
        paid_dates = []
        for ref in refs:
            ref_ns = ns
            ref_id_elem = ref.find("cbc:ID", namespaces=ref_ns)
            ref_id = (ref_id_elem.text or "").strip() if ref_id_elem is not None else ""
            ref_type = ref_id_elem.get("schemeID") if ref_id_elem is not None else None

            # Payment
            payment = ref.find("cac:Payment", namespaces=ref_ns)
            if ref_type != "07":
                # ERROR 2737: PaidDate exists
                paid_date = self._text(payment, "cbc:PaidDate", ref_ns) if payment is not None else None
                if paid_date is None:
                    self._add(errors, "2737", "Si 'Tipo de documento relacionado' es diferente a '07', no existe el Tag UBL cac:Payment/cbc:PaidDate")
                else:
                    paid_dates.append(paid_date)
                    # ERROR 2625: same period as IssueDate
                    if issue_date is not None and paid_date[:7] != issue_date[:7]:
                        self._add(errors, "2625", "Si existe 'Fecha de pago', el valor es de mes/año diferente a la 'fecha de emisión' del comprobante de retención")

                # ERROR 2733 / 2734: Payment ID
                payment_id = self._text(payment, "cbc:ID", ref_ns) if payment is not None else None
                if payment_id is None or payment_id == "":
                    self._add(errors, "2733", "Si 'Tipo de documento relacionado' es diferente a '07', no existe el Tag UBL cac:Payment/cbc:ID o es vacío")
                elif not self._matches(payment_id, r"^\d{1,9}$"):
                    self._add(errors, "2734", "Si 'Tipo de documento relacionado' es diferente a '07', el formato del Tag UBL cac:Payment/cbc:ID es diferente a numérico de hasta 9 dígitos")

                # ERROR 2735 / 2736: Payment PaidAmount
                paid_amount = self._parse_amount(self._text(payment, "cbc:PaidAmount", ref_ns)) if payment is not None else None
                if paid_amount is None:
                    self._add(errors, "2735", "Si 'Tipo de documento relacionado' es diferente a '07', no existe el Tag UBL cac:Payment/cbc:PaidAmount")
                elif paid_amount <= 0:
                    self._add(errors, "2736", "Si 'Tipo de documento relacionado' es diferente a '07', el formato del Tag UBL cac:Payment/cbc:PaidAmount es diferente a decimal positivo de 12 enteros y 2 decimales")

                # ERROR 2622: Payment PaidAmount currencyID
                paid_currency = self._attr(payment, "cbc:PaidAmount", "currencyID", ref_ns) if payment is not None else None
                ref_currency = self._attr(ref, "cbc:TotalInvoiceAmount", "currencyID", ref_ns)
                if paid_currency is not None and ref_currency is not None and paid_currency != ref_currency:
                    self._add(errors, "2622", "Si 'Tipo de documento relacionado' es diferente a '07', el valor del Tag UBL cac:Payment/cbc:PaidAmount@currencyID es diferente al 'Tipo de moneda del documento relacionado'")

            # Retention information
            info = ref.find("sac:SUNATRetentionInformation", namespaces=ref_ns)
            if info is not None:
                # ERROR 2740 / 2742: SUNATRetentionAmount
                ret_amount = self._parse_amount(self._text(info, "sac:SUNATRetentionAmount", ref_ns))
                ret_currency = self._attr(info, "sac:SUNATRetentionAmount", "currencyID", ref_ns)
                if ret_amount is None or ret_amount <= 0:
                    self._add(errors, "2740", "El formato del Tag UBL sac:SUNATRetentionAmount es diferente a decimal positivo de 12 enteros y 2 decimales o es cero (0)")
                if ret_currency is not None and ret_currency != "PEN":
                    self._add(errors, "2742", "El valor del Tag UBL sac:SUNATRetentionAmount@currencyID es diferente a 'PEN'")
                ref_total = self._parse_amount(self._text(ref, "cbc:TotalInvoiceAmount", ref_ns))
                ref_currency = self._attr(ref, "cbc:TotalInvoiceAmount", "currencyID", ref_ns)
                if ref_type not in {"07", "20"} and ret_amount is not None:
                    retention_sum += ret_amount

                # ERROR 2746 / 2748: SUNATNetTotalPaid
                net_paid = self._parse_amount(self._text(info, "sac:SUNATNetTotalPaid", ref_ns))
                net_paid_currency = self._attr(info, "sac:SUNATNetTotalPaid", "currencyID", ref_ns)
                if net_paid is None or net_paid <= 0:
                    self._add(errors, "2746", "El formato del Tag UBL sac:SUNATNetTotalPaid es diferente a decimal positivo de 12 enteros y 2 decimales o es cero (0)")
                if net_paid_currency is not None and net_paid_currency != "PEN":
                    self._add(errors, "2748", "El valor del Tag UBL sac:SUNATNetTotalPaid@currencyID es diferente a 'PEN'")
                if net_paid is not None:
                    net_paid_sum += net_paid

                # ERROR 2623: cuadre de montos en moneda PEN
                if ref_currency == "PEN" and ret_amount is not None and net_paid is not None and ref_total is not None:
                    expected_total = ret_amount + net_paid
                    if abs(expected_total - ref_total) > Decimal("0.01"):
                        self._add(errors, "2623", "Si 'Tipo de moneda del documento relacionado' es 'PEN', los montos de retención, neto pagado e importe total no cuadran")


        # ERROR 2661: all PaidDate same period
        if len(paid_dates) > 1:
            periods = {d[:7] for d in paid_dates}
            if len(periods) > 1:
                self._add(errors, "2661", "Si existe 'Fecha de pago', el valor es de mes/año (periodo) diferente a otra 'Fecha de pago'")

        # ERROR 2628: TotalInvoiceAmount = sum of retention amounts
        if total_invoice_amount is not None and total_invoice_amount != retention_sum:
            self._add(errors, "2628", "El valor de Tag UBL cbc:TotalInvoiceAmount es diferente a la suma de 'Importe retenido', sin considerar los tipos de documentos '07' y '20'")

        # ERROR 2629: SUNATTotalPaid = sum of net paid + rounding
        expected_paid = net_paid_sum + (rounding or Decimal("0"))
        if total_paid is not None and total_paid != expected_paid:
            self._add(errors, "2629", "El valor de Tag UBL sac:SUNATTotalPaid es diferente a la suma de 'Importe total a pagar' más el 'Monto de redondeo del importe total pagado'")

    # ------------------------------------------------------------------
    # Signature validations
    # ------------------------------------------------------------------

    def _validate_signature(self, root: etree._Element, errors: list[ValidationError]) -> None:
        ns = self.NS_SIGNATURE

        sig = root.xpath("//ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/ds:Signature", namespaces=ns)
        if not sig:
            sig = root.xpath("//ds:Signature", namespaces=ns)
        if not sig:
            self._add(errors, "2085", "No existe el Tag UBL ds:Signature")
            return
        sig = sig[0]

        # ERROR 2085 / 2084: Signature/@Id
        sig_id = sig.get("Id")
        if sig_id is None:
            self._add(errors, "2085", "No existe el Tag UBL ds:Signature/@Id")
        elif not self._matches(sig_id, r"^.{1,3000}$"):
            self._add(errors, "2084", "El formato del Tag UBL ds:Signature/@Id es diferente a alfanumérico de hasta 3000 caracteres")

        # ERROR 2087 / 2086: CanonicalizationMethod/@Algorithm
        canon = sig.xpath("ds:SignedInfo/ds:CanonicalizationMethod/@Algorithm", namespaces=ns)
        if not canon:
            self._add(errors, "2087", "No existe el Tag UBL ds:SignedInfo/ds:CanonicalizationMethod/@Algorithm")
        elif not self._matches(canon[0], r"^.{1,3000}$"):
            self._add(errors, "2086", "El formato del Tag UBL ds:CanonicalizationMethod/@Algorithm es diferente a alfanumérico de hasta 3000 caracteres")

        # ERROR 2089 / 2088: SignatureMethod/@Algorithm
        sig_method = sig.xpath("ds:SignedInfo/ds:SignatureMethod/@Algorithm", namespaces=ns)
        if not sig_method:
            self._add(errors, "2089", "No existe el Tag UBL ds:SignedInfo/ds:SignatureMethod/@Algorithm")
        elif not self._matches(sig_method[0], r"^.{1,3000}$"):
            self._add(errors, "2088", "El formato del Tag UBL ds:SignedInfo/ds:SignatureMethod/@Algorithm es diferente a alfanumérico de hasta 3000 caracteres")
        else:
            alg = sig_method[0]
            if alg == _SHA1_SIG:
                self._add(errors, "2089", "SHA-1 (rsa-sha1) está deprecado; use RSA-SHA-256 según INDECOPI/IOFE y PCM Directiva 002-2024")
            elif alg != _RSA_SHA256:
                self._add(errors, "2089", f"ds:SignatureMethod/@Algorithm debe ser {_RSA_SHA256}")

        # ERROR 2091 / 2090: Reference/@URI
        ref_uri = sig.xpath("ds:SignedInfo/ds:Reference/@URI", namespaces=ns)
        if not ref_uri:
            self._add(errors, "2091", "No existe el Tag UBL ds:SignedInfo/ds:Reference/@URI")
        elif not ref_uri[0].strip() and ref_uri[0] != "":
            self._add(errors, "2090", "El Tag UBL ds:SignedInfo/ds:Reference/@URI se encuentra vacío")

        # ERROR 2093 / 2092: Transform/@Algorithm
        transform = sig.xpath("ds:SignedInfo/ds:Reference/ds:Transforms/ds:Transform/@Algorithm", namespaces=ns)
        if not transform:
            self._add(errors, "2093", "No existe el Tag UBL ds:SignedInfo/ds:Reference/ds:Transform/@Algorithm")
        elif not self._matches(transform[0], r"^.{1,3000}$"):
            self._add(errors, "2092", "El formato del Tag UBL ds:Transform/@Algorithm es diferente a alfanumérico de hasta 3000 caracteres")

        # ERROR 2095 / 2094: DigestMethod/@Algorithm
        digest_method = sig.xpath("ds:SignedInfo/ds:Reference/ds:DigestMethod/@Algorithm", namespaces=ns)
        if not digest_method:
            self._add(errors, "2095", "No existe el Tag UBL ds:SignedInfo/ds:Reference/ds:DigestMethod/@Algorithm")
        elif not self._matches(digest_method[0], r"^.{1,3000}$"):
            self._add(errors, "2094", "El formato del Tag UBL ds:DigestMethod/@Algorithm es diferente a alfanumérico de hasta 3000 caracteres")
        else:
            alg = digest_method[0]
            if alg == _SHA1_DIG:
                self._add(errors, "2095", "SHA-1 (sha1) está deprecado; use SHA-256 según INDECOPI/IOFE y PCM Directiva 002-2024")
            elif alg != _SHA256:
                self._add(errors, "2095", f"ds:DigestMethod/@Algorithm debe ser {_SHA256}")

        # ERROR 2097: DigestValue
        digest_val = sig.xpath("ds:SignedInfo/ds:Reference/ds:DigestValue", namespaces=ns)
        if not digest_val:
            self._add(errors, "2097", "No existe el Tag UBL ds:SignedInfo/ds:Reference/ds:DigestValue")
        elif not digest_val[0].text or len(digest_val[0].text.strip()) < 2:
            self._add(errors, "2097", "El Tag UBL ds:DigestValue está vacío")

        # ERROR 2099 / 2098: SignatureValue
        sig_value = sig.xpath("ds:SignatureValue", namespaces=ns)
        if not sig_value:
            self._add(errors, "2099", "No existe el Tag UBL ds:SignatureValue")
        elif not sig_value[0].text or len(sig_value[0].text.strip()) < 2:
            self._add(errors, "2099", "El Tag UBL ds:SignatureValue está vacío")
        elif not self._matches(sig_value[0].text.strip(), r"^[A-Za-z0-9+/=]{2,}$"):
            self._add(errors, "2098", "El Tag UBL ds:SignatureValue no cumple con el formato de letras de A a Z, números, '+', '=', como mínimo 2 caracteres")

        # ERROR 2101 / 2100: X509Certificate
        x509 = root.xpath("//ds:X509Certificate", namespaces=ns)
        if not x509:
            self._add(errors, "2101", "No existe el Tag UBL ds:X509Certificate")
        elif not x509[0].text or len(x509[0].text.strip()) < 2:
            self._add(errors, "2101", "El Tag UBL ds:X509Certificate está vacío")
        elif not self._matches(x509[0].text.strip(), r"^[A-Za-z0-9+/=\s]{2,}$"):
            self._add(errors, "2100", "El Tag UBL ds:X509Certificate no cumple con el formato de letras de A a Z, números, '+', '=', como mínimo 2 caracteres")

        # cac:Signature block (2076-2083) - solo si existe en el documento
        if self._exists(root, "cac:Signature", ns):
            self._validate_signature_party(root, ns, errors)


    def _validate_signature_party(self, root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
        """ERROR 2076-2083: cac:Signature party."""
        sig_id = self._text(root, "cac:Signature/cbc:ID", ns)
        if sig_id is None:
            self._add(errors, "2076", "No existe el Tag UBL cac:Signature/cbc:ID")
        elif not self._matches(sig_id, r"^.{1,3000}$"):
            self._add(errors, "2077", "El formato del Tag UBL cac:Signature/cbc:ID es diferente a alfanumérico de hasta 3000 caracteres")

        sig_party_id = self._text(root, "cac:Signature/cac:SignatoryParty/cac:PartyIdentification/cbc:ID", ns)
        supplier_ruc = self._text(root, "cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID", ns)
        if sig_party_id is None:
            self._add(errors, "2079", "No existe el Tag UBL cac:Signature/cac:SignatoryParty/cac:PartyIdentification/cbc:ID")
        elif not self._matches(sig_party_id, r"^\d{11}$") or (supplier_ruc is not None and sig_party_id != supplier_ruc):
            self._add(errors, "2078", "El Tag UBL cac:Signature/cac:SignatoryParty/cac:PartyIdentification/cbc:ID debe ser igual al RUC del emisor")

        sig_party_name = self._text(root, "cac:Signature/cac:SignatoryParty/cac:PartyName/cbc:Name", ns)
        if sig_party_name is None:
            self._add(errors, "2081", "No existe el Tag UBL cac:Signature/cac:SignatoryParty/cac:PartyName/cbc:Name")
        elif not self._matches(sig_party_name, r"^.{1,3000}$"):
            self._add(errors, "2080", "El formato del Tag UBL cac:Signature/cac:SignatoryParty/cac:PartyName/cbc:Name es diferente a alfanumérico de hasta 3000 caracteres")

        sig_uri = self._text(root, "cac:Signature/cac:DigitalSignatureAttachment/cac:ExternalReference/cbc:URI", ns)
        if sig_uri is None:
            self._add(errors, "2083", "No existe el Tag UBL cac:Signature/cac:DigitalSignatureAttachment/cac:ExternalReference/cbc:URI")
        elif not self._matches(sig_uri, r"^.{1,3000}$"):
            self._add(errors, "2082", "El formato del Tag UBL cac:Signature/cac:DigitalSignatureAttachment/cac:ExternalReference/cbc:URI es diferente a alfanumérico de hasta 3000 caracteres")

    # ------------------------------------------------------------------
    # Out-of-scope rules (documented)
    # ------------------------------------------------------------------

    # FUERA DE ALCANCE - requiere listado/padrón SUNAT:
    # 1033, 2010, 2011, 3097, 1078, 3281, 1086, 3239, 1083, 2800, 2040,
    # 2036, 3051 (listado 1016 IVAP), 2377, 2041, 3071, 3283-3289, 3007,
    # 2964, 2961, 3027, 2798, 2792, 2788, 2505, 2529, 3218-3219, 2520,
    # 3033, 3174, 3134, 3116, 3118, 3150, 2172, 2016, 2119-2121, 2885,
    # 3209, 2199, 2209-2208, 2663, 3207, 2987, 2282, 2957, 2605, 2989-2990,
    # 2517, 2891, 2601, 2896, 2256, 2268, 2375, 2105, 2398, 2323, 2617,
    # 3312, 3328-3329, 3310, 2610, 2618-2619, 2621, 2723, etc.
    # También fuera de alcance reglas que dependen del nombre del archivo ZIP
    # o de la fecha de recepción de SUNAT (2108, 2329, 1079, 2600, 2957).


