"""Helpers, catalogues and constants shared by SUNAT validators."""

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lxml import etree


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
    **NS_COMMON,
    "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
}
NS_SUMMARY = {
    "": "urn:sunat:names:specification:ubl:peru:schema:xsd:SummaryDocuments-1",
    **NS_COMMON,
    "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
}
NS_PERCEPTION = {
    "": "urn:sunat:names:specification:ubl:peru:schema:xsd:Perception-1",
    **NS_COMMON,
    "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}
NS_RETENTION = {
    "": "urn:sunat:names:specification:ubl:peru:schema:xsd:Retention-1",
    **NS_COMMON,
    "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}
NS_SIGNATURE = {
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    **NS_COMMON,
    "ds": "http://www.w3.org/2000/09/xmldsig#",
}


# Catálogos SUNAT locales
CATALOG07 = {"10", "11", "12", "13", "14", "15", "16", "17", "20", "21", "30", "31", "32", "33", "34", "35", "36", "37"}
CATALOG05 = {"1000", "1016", "2000", "7152", "9995", "9996", "9997", "9998", "9999"}
CATALOG06 = {"0", "1", "4", "6", "7", "A", "B", "C", "D", "E", "G"}
CATALOG51 = {
    "0101", "0102", "0103", "0104", "0105", "0106", "0107", "0108",
    "0200", "0201", "0202", "0203", "0204", "0205", "0206", "0207", "0208",
    "0301", "0302", "1001", "1002", "1003", "1004", "2001", "2100", "2101", "2102", "2103", "2104",
}
CATALOG01 = {"01", "03", "07", "08", "12", "20", "40", "41"}
CATALOG03 = {"NIU", "KGM", "LTR", "MTQ", "MTR", "CMT", "GRM", "TNE", "PR", "BX", "DZN", "CEN", "ML"}
CATALOG53 = {"00", "01", "02", "03", "04", "05", "06", "07", "20", "45", "46", "47", "48", "50", "51", "52", "53", "62", "63"}
CATALOG05_NAMES = {
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


def parse_xml(xml_string: str) -> etree._Element | None:
    try:
        return etree.fromstring(xml_string.encode("utf-8"))
    except etree.XMLSyntaxError:
        return None


def text(root: etree._Element | None, xpath: str, ns: dict) -> str | None:
    if root is None:
        return None
    elem = root.find(xpath, namespaces=ns)
    if elem is None:
        return None
    return (elem.text or "").strip() or None


def attr(root: etree._Element | None, xpath: str, attr: str, ns: dict) -> str | None:
    if root is None:
        return None
    elem = root.find(xpath, namespaces=ns)
    if elem is None:
        return None
    val = elem.get(attr)
    return val.strip() if val else None


def exists(root: etree._Element | None, xpath: str, ns: dict) -> bool:
    if root is None:
        return False
    return root.find(xpath, namespaces=ns) is not None


def all_(root: etree._Element | None, xpath: str, ns: dict) -> list[etree._Element]:
    if root is None:
        return []
    return root.findall(xpath, namespaces=ns)


def is_numeric(value: str | None) -> bool:
    if value is None:
        return False
    try:
        Decimal(value)
        return True
    except InvalidOperation:
        return False


def parse_amount(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def matches(value: str | None, regex: str) -> bool:
    if value is None:
        return False
    return re.match(regex, value) is not None


def one_of(value: str | None, values: set[str]) -> bool:
    return value is not None and value in values


def add_error(errors: list[ValidationError], code: str, message: str) -> None:
    errors.append(ValidationError(code, message))


def validate_schema(xml_string: str, xsd_path: str) -> list[ValidationError]:
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
