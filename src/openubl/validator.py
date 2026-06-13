"""
SUNAT validation engine for UBL 2.1 XML documents.

Based on "Reglas de validación actualizado al 24.04.2026" from SUNAT,
plus SHA-256 algorithm requirements from INDECOPI/IOFE and PCM
Directiva N.° 002-2024-PCM/SGTD.
"""
import re
from lxml import etree


_RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
_SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"
_SHA1_SIG = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
_SHA1_DIG = "http://www.w3.org/2000/09/xmldsig#sha1"


class SunatValidator:
    """Validates rendered XML against SUNAT rules and XSD schemas."""

    def validate_schema(self, xml_string: str, xsd_path: str) -> list[str]:
        """Validate XML against UBL 2.1 XSD schema."""
        try:
            xml_doc = etree.fromstring(xml_string.encode("utf-8"))
            with open(xsd_path, "rb") as f:
                schema_root = etree.XML(f.read())
            schema = etree.XMLSchema(schema_root)
            schema.assertValid(xml_doc)
            return []
        except etree.XMLSyntaxError as e:
            return [f"XML malformed: {e}"]
        except etree.DocumentInvalid as e:
            return [f"XSD validation error: {e}"]
        except Exception as e:
            return [f"Schema validation error: {e}"]

    def validate_invoice(self, xml_string: str) -> list[str]:
        """Validate invoice XML against SUNAT business rules."""
        errors = []
        try:
            root = etree.fromstring(xml_string.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            return [f"XML malformed: {e}"]

        ns = {"": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
              "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}

        # ERROR 2074: UBLVersionID must be 2.1
        ubl_version = root.findtext("cbc:UBLVersionID", namespaces=ns)
        if ubl_version != "2.1":
            errors.append("ERROR 2074: UBLVersionID debe ser '2.1'")

        # ERROR 2072: CustomizationID must be 2.0
        customization = root.findtext("cbc:CustomizationID", namespaces=ns)
        if customization != "2.0":
            errors.append("ERROR 2072: CustomizationID debe ser '2.0'")

        # ERROR 1001: ID format
        doc_id = root.findtext("cbc:ID", namespaces=ns)
        if doc_id and not re.match(r"^[A-Za-z0-9]{3,4}-\d{1,8}$", doc_id):
            errors.append("ERROR 1001: Formato de ID inválido")

        # ERROR 2070: DocumentCurrencyCode
        currency = root.findtext("cbc:DocumentCurrencyCode", namespaces=ns)
        if not currency:
            errors.append("ERROR 2070: DocumentCurrencyCode es obligatorio")

        # ERROR 1008/1007: Supplier RUC
        supplier_id = root.find("cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID", namespaces=ns)
        if supplier_id is not None:
            scheme = supplier_id.get("schemeID")
            ruc = supplier_id.text
            if scheme != "6":
                errors.append("ERROR 1007: schemeID del emisor debe ser '6'")
            if not ruc or not re.match(r"^\d{11}$", ruc):
                errors.append("ERROR 1008: RUC del emisor debe tener 11 dígitos")

        # ERROR 1037: RegistrationName
        reg_name = root.findtext("cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName", namespaces=ns)
        if not reg_name:
            errors.append("ERROR 1037: RegistrationName del emisor es obligatorio")

        # ERROR 2015: Customer schemeID
        customer_id = root.find("cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID", namespaces=ns)
        if customer_id is not None:
            scheme = customer_id.get("schemeID")
            if not scheme:
                errors.append("ERROR 2015: schemeID del cliente es obligatorio")

        # ERROR 2062: PayableAmount > 0
        payable = root.find("cac:LegalMonetaryTotal/cbc:PayableAmount", namespaces=ns)
        if payable is not None:
            try:
                val = float(payable.text or "0")
                if val <= 0:
                    errors.append("ERROR 2062: PayableAmount debe ser mayor a 0")
            except ValueError:
                errors.append("ERROR 2062: PayableAmount no es numérico")

        # ERROR 3305: TaxInclusiveAmount exists
        tax_inclusive = root.find("cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", namespaces=ns)
        if tax_inclusive is None:
            errors.append("ERROR 3305: TaxInclusiveAmount es obligatorio")

        # ERROR 3294: TaxTotal matches sum of lines (Invoice, CreditNote, DebitNote)
        tax_total = root.find("cac:TaxTotal/cbc:TaxAmount", namespaces=ns)
        if tax_total is not None:
            try:
                total_tax = float(tax_total.text or "0")
                line_taxes = root.findall("cac:InvoiceLine/cac:TaxTotal/cbc:TaxAmount", namespaces=ns)
                line_taxes += root.findall("cac:CreditNoteLine/cac:TaxTotal/cbc:TaxAmount", namespaces=ns)
                line_taxes += root.findall("cac:DebitNoteLine/cac:TaxTotal/cbc:TaxAmount", namespaces=ns)
                sum_lines = sum(float(t.text or "0") for t in line_taxes)
                if abs(total_tax - sum_lines) > 1:
                    errors.append("ERROR 3294: TaxTotal no cuadra con sumatoria de líneas")
            except ValueError:
                pass

        # ERROR 3278: LineExtensionAmount matches sum
        line_ext = root.find("cac:LegalMonetaryTotal/cbc:LineExtensionAmount", namespaces=ns)
        if line_ext is not None:
            try:
                total_ext = float(line_ext.text or "0")
                line_exts = root.findall("cac:InvoiceLine/cbc:LineExtensionAmount", namespaces=ns)
                line_exts += root.findall("cac:CreditNoteLine/cbc:LineExtensionAmount", namespaces=ns)
                line_exts += root.findall("cac:DebitNoteLine/cbc:LineExtensionAmount", namespaces=ns)
                sum_exts = sum(float(t.text or "0") for t in line_exts)
                if abs(total_ext - sum_exts) > 1:
                    errors.append("ERROR 3278: LineExtensionAmount no cuadra con sumatoria de líneas")
            except ValueError:
                pass

        return errors

    def validate_credit_note(self, xml_string: str) -> list[str]:
        """Validate credit note XML."""
        errors = self.validate_invoice(xml_string)
        # Additional credit note specific validations would go here
        return errors

    def validate_voided_documents(self, xml_string: str) -> list[str]:
        """Validate voided documents XML."""
        errors = []
        try:
            root = etree.fromstring(xml_string.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            return [f"XML malformed: {e}"]

        ns = {"": "urn:sunat:names:specification:ubl:peru:schema:xsd:VoidedDocuments-1",
              "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}

        ubl_version = root.findtext("cbc:UBLVersionID", namespaces=ns)
        if ubl_version != "2.0":
            errors.append("ERROR 2074 (Voided): UBLVersionID debe ser '2.0'")

        customization = root.findtext("cbc:CustomizationID", namespaces=ns)
        if customization != "1.0":
            errors.append("ERROR 2072 (Voided): CustomizationID debe ser '1.0'")

        return errors

    def validate_signed_xml(self, xml_string: str) -> list[str]:
        """Validate signed XML structure and SHA-256 algorithms."""
        errors = []
        try:
            root = etree.fromstring(xml_string.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            return [f"XML malformed: {e}"]

        ns = {"ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
              "ds": "http://www.w3.org/2000/09/xmldsig#"}

        # ERROR 2085: Signature ID
        sig = root.xpath("//ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/ds:Signature", namespaces=ns)
        if not sig:
            errors.append("ERROR 2085: ds:Signature no encontrado en ExtensionContent")
        elif not sig[0].get("Id"):
            errors.append("ERROR 2085: ds:Signature/@Id es obligatorio")

        # ERROR 2101: X509Certificate
        x509 = root.xpath("//ds:X509Certificate", namespaces=ns)
        if not x509:
            errors.append("ERROR 2101: ds:X509Certificate es obligatorio")
        elif not x509[0].text or len(x509[0].text.strip()) < 2:
            errors.append("ERROR 2101: ds:X509Certificate vacío")

        # ERROR 2099: SignatureValue
        sig_val = root.xpath("//ds:SignatureValue", namespaces=ns)
        if not sig_val:
            errors.append("ERROR 2099: ds:SignatureValue es obligatorio")
        elif not sig_val[0].text or len(sig_val[0].text.strip()) < 2:
            errors.append("ERROR 2099: ds:SignatureValue vacío")

        # ERROR 2087: CanonicalizationMethod
        canon = root.xpath("//ds:SignedInfo/ds:CanonicalizationMethod/@Algorithm", namespaces=ns)
        if not canon:
            errors.append("ERROR 2087: ds:CanonicalizationMethod/@Algorithm es obligatorio")

        # ERROR 2089: SignatureMethod
        sig_method = root.xpath("//ds:SignedInfo/ds:SignatureMethod/@Algorithm", namespaces=ns)
        if not sig_method:
            errors.append("ERROR 2089: ds:SignatureMethod/@Algorithm es obligatorio")
        else:
            alg = sig_method[0]
            if alg == _SHA1_SIG:
                errors.append(
                    "ERROR 2089: SHA-1 (rsa-sha1) está deprecado; "
                    "use RSA-SHA-256 según INDECOPI/IOFE y PCM Directiva 002-2024"
                )
            elif alg != _RSA_SHA256:
                errors.append(
                    f"ERROR 2089: ds:SignatureMethod/@Algorithm debe ser {_RSA_SHA256}"
                )

        # ERROR 2091: Reference URI
        ref_uri = root.xpath("//ds:SignedInfo/ds:Reference/@URI", namespaces=ns)
        if not ref_uri:
            errors.append("ERROR 2091: ds:Reference/@URI es obligatorio")

        # ERROR 2093: Transform Algorithm
        transform = root.xpath("//ds:SignedInfo/ds:Reference/ds:Transforms/ds:Transform/@Algorithm", namespaces=ns)
        if not transform:
            errors.append("ERROR 2093: ds:Transform/@Algorithm es obligatorio")

        # ERROR 2095: DigestMethod Algorithm
        digest_method = root.xpath("//ds:SignedInfo/ds:Reference/ds:DigestMethod/@Algorithm", namespaces=ns)
        if not digest_method:
            errors.append("ERROR 2095: ds:DigestMethod/@Algorithm es obligatorio")
        else:
            alg = digest_method[0]
            if alg == _SHA1_DIG:
                errors.append(
                    "ERROR 2095: SHA-1 (sha1) está deprecado; "
                    "use SHA-256 según INDECOPI/IOFE y PCM Directiva 002-2024"
                )
            elif alg != _SHA256:
                errors.append(
                    f"ERROR 2095: ds:DigestMethod/@Algorithm debe ser {_SHA256}"
                )

        # ERROR 2097: DigestValue
        digest_val = root.xpath("//ds:SignedInfo/ds:Reference/ds:DigestValue", namespaces=ns)
        if not digest_val:
            errors.append("ERROR 2097: ds:DigestValue es obligatorio")
        elif not digest_val[0].text or len(digest_val[0].text.strip()) < 2:
            errors.append("ERROR 2097: ds:DigestValue vacío")

        return errors
