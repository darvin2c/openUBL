"""Validaciones SUNAT adicionales para CreditNote.

Fuente de verdad:
- Excel "Reglas de validación actualizado al 24.04.2026" publicado en
  https://cpe.sunat.gob.pe/guias-y-manuales
- rules_CreditNote.txt y rules_Invoice.txt (reglas análogas aplicables a notas).

Esta función complementa las validaciones comunes de SunatValidator; se invoca
desde validate_credit_note una vez que el documento ha sido parseado.
"""

import re
from decimal import Decimal
from typing import Iterable

from lxml import etree

from openubl.validators.common import (
    ValidationError,
    add_error,
    all_,
    attr,
    exists,
    matches,
    parse_amount,
    text,
    CATALOG03,
    CATALOG05,
    CATALOG07,
    NS_CREDIT_NOTE,
)

_NS = NS_CREDIT_NOTE

_CATALOG_PREFIX = re.compile(r"^Catalog\d+\.")

# Catálogo N.° 06 - Tipo de documento de identidad (valores y nombres de miembro).
_CATALOG06_MAP = {
    "0": "0",
    "1": "1",
    "4": "4",
    "6": "6",
    "7": "7",
    "A": "A",
    "B": "B",
    "C": "C",
    "D": "D",
    "E": "E",
    "G": "G",
    "DOC_NO_DOMICILIADO": "0",
    "DNI": "1",
    "CE": "4",
    "RUC": "6",
    "PASAPORTE": "7",
}

# Catálogo N.° 07 - Tipo de afectación del IGV/IVAP.
_CATALOG07_MAP = {v: v for v in CATALOG07}
_CATALOG07_MAP.update(
    {
        "GRAVADO_OPERACION_ONEROSA": "10",
        "EXONERADO_OPERACION_ONEROSA": "20",
        "INAFECTO_OPERACION_ONEROSA": "30",
    }
)

# Catálogo N.° 02 - Moneda.
_CATALOG02_MAP = {
    "PEN": "PEN",
    "USD": "USD",
    "EUR": "EUR",
}

# Catálogo N.° 16 - Tipo de precio.
_CATALOG16_MAP = {
    "01": "01",
    "02": "02",
    "PRECIO_UNITARIO_INCLUYE_IGV": "01",
    "VALOR_REFERENCIAL_UNITARIO_EN_OPERACIONES_NO_ONEROSAS": "02",
}

# Códigos de tributo que son afectaciones al IGV/IVAP (no ISC ni otros tributos).
_IGV_LIKE_CODES = {"1000", "1016", "9995", "9996", "9997", "9998"}

# Combinaciones permitidas de tributos con monto base > 0 por línea (ERROR 3223).
_VALID_TAX_COMBINATIONS = {
    frozenset({"1000"}),
    frozenset({"1016"}),
    frozenset({"9995"}),
    frozenset({"9996"}),
    frozenset({"9997"}),
    frozenset({"9998"}),
    frozenset({"1000", "2000"}),
    frozenset({"1000", "9999"}),
    frozenset({"1000", "2000", "9999"}),
    frozenset({"1016", "9999"}),
    frozenset({"9995", "9999"}),
    frozenset({"9996", "2000"}),
    frozenset({"9996", "9999"}),
    frozenset({"9996", "2000", "9999"}),
    frozenset({"9997", "2000"}),
    frozenset({"9997", "9999"}),
    frozenset({"9997", "2000", "9999"}),
    frozenset({"9998", "2000"}),
    frozenset({"9998", "9999"}),
    frozenset({"9998", "2000", "9999"}),
    frozenset({"7152"}),
}


def _catalog_value(value: str | None, mapping: dict[str, str]) -> str | None:
    if value is None:
        return None
    bare = _CATALOG_PREFIX.sub("", value)
    return mapping.get(bare, bare)


def _catalog6(value: str | None) -> str | None:
    return _catalog_value(value, _CATALOG06_MAP)


def _catalog7(value: str | None) -> str | None:
    return _catalog_value(value, _CATALOG07_MAP)


def _currency(value: str | None) -> str | None:
    return _catalog_value(value, _CATALOG02_MAP)


def _catalog16(value: str | None) -> str | None:
    return _catalog_value(value, _CATALOG16_MAP)


def _positive_amount(value: str | None, int_digits: int = 12, dec_digits: int = 2) -> bool:
    if value is None:
        return False
    pattern = rf"^\d{{1,{int_digits}}}(\.\d{{1,{dec_digits}}})$|^\d{{1,{int_digits}}}$"
    if not re.match(pattern, value):
        return False
    amount = parse_amount(value)
    return amount is not None and amount > 0


def _non_negative_amount(value: str | None, int_digits: int = 12, dec_digits: int = 2) -> bool:
    if value is None:
        return False
    pattern = rf"^\d{{1,{int_digits}}}(\.\d{{1,{dec_digits}}})$|^\d{{1,{int_digits}}}$"
    if not re.match(pattern, value):
        return False
    amount = parse_amount(value)
    return amount is not None and amount >= 0


def _positive_amount_10(value: str | None) -> bool:
    return _positive_amount(value, int_digits=12, dec_digits=10)


def _percentage(value: str | None) -> bool:
    if value is None:
        return False
    if not re.match(r"^\d{1,3}(\.\d{1,5})?$", value):
        return False
    amount = parse_amount(value)
    return amount is not None and amount > 0


def _integer_ge_zero_le(value: str | None, max_digits: int = 5) -> bool:
    if value is None:
        return False
    if not re.match(rf"^\d{{1,{max_digits}}}$", value):
        return False
    try:
        return int(value) >= 0
    except ValueError:
        return False


def _serie(root: etree._Element) -> str:
    doc_id = text(root, "cbc:ID", _NS) or ""
    return doc_id.split("-")[0] if "-" in doc_id else doc_id


def _doc_currency(root: etree._Element) -> str | None:
    return _currency(text(root, "cbc:DocumentCurrencyCode", _NS))


def _resp_code(root: etree._Element) -> str | None:
    return text(root, "cac:DiscrepancyResponse/cbc:ResponseCode", _NS)


def _ref_doc_type(root: etree._Element) -> str | None:
    return text(root, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode", _NS)


def _customer_type(root: etree._Element) -> str | None:
    return _catalog6(attr(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID", "schemeID", _NS))


def _issue_date(root: etree._Element) -> str | None:
    return text(root, "cbc:IssueDate", _NS)


def _line_tax_subtotals(line: etree._Element) -> list[etree._Element]:
    return line.findall("cac:TaxTotal/cac:TaxSubtotal", namespaces=_NS)


def _line_tax_codes(line: etree._Element) -> set[str]:
    return {
        t.text.strip()
        for t in line.findall("cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID", namespaces=_NS)
        if t.text
    }


def _tax_code(subtotal: etree._Element) -> str | None:
    return text(subtotal, "cac:TaxCategory/cac:TaxScheme/cbc:ID", _NS)


def _tax_amount(subtotal: etree._Element) -> Decimal | None:
    return parse_amount(text(subtotal, "cbc:TaxAmount", _NS))


def _taxable_amount(subtotal: etree._Element) -> Decimal | None:
    return parse_amount(text(subtotal, "cbc:TaxableAmount", _NS))


def _percent(subtotal: etree._Element) -> Decimal | None:
    return parse_amount(text(subtotal, "cac:TaxCategory/cbc:Percent", _NS))


def _exemption_code(subtotal: etree._Element) -> str | None:
    return _catalog7(text(subtotal, "cac:TaxCategory/cbc:TaxExemptionReasonCode", _NS))


def _within_tolerance(a: Decimal | None, b: Decimal | None, tol: Decimal = Decimal("1")) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def validate_credit_note_extra(root: etree._Element, errors: list[ValidationError] | None = None) -> list[ValidationError]:
    """Valida reglas SUNAT adicionales para un CreditNote ya parseado."""
    if errors is None:
        errors = []

    # ------------------------------------------------------------------
    # FUERA DE ALCANCE documentadas
    # ------------------------------------------------------------------
    # ERROR 1079: requiere fecha de recepción del XML por SUNAT.
    # ERROR 2108: requiere fecha de recepción del XML por SUNAT.
    # ERROR 3116 / 3121: texto de la regla no disponible en rules_CreditNote.txt
    #                    ni en rules_Invoice.txt para CreditNote.
    # ------------------------------------------------------------------

    _validate_parties(root, errors)
    _validate_lines(root, errors)
    _validate_global_taxes(root, errors)
    _validate_monetary_total(root, errors)
    _validate_allowance_charges(root, errors)
    _validate_notes(root, errors)
    _validate_delivery(root, errors)

    return errors


def _validate_parties(root: etree._Element, errors: list[ValidationError]) -> None:
    # ERROR 3089: más de un PartyIdentification del emisor
    supplier_ids = all_(
        root,
        "cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification",
        _NS,
    )
    if len(supplier_ids) > 1:
        add_error(errors, "3089", "Existe más de un tag cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification")

    # ERROR 3090: más de un PartyIdentification del adquiriente
    customer_ids = all_(
        root,
        "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification",
        _NS,
    )
    if len(customer_ids) > 1:
        add_error(errors, "3090", "Existe más de un tag cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification")

    # ERROR 2017: si el tipo de documento del adquiriente es RUC (6), debe tener 11 dígitos
    customer_id_elem = root.find(
        "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
        namespaces=_NS,
    )
    if customer_id_elem is not None:
        cust_type = _catalog6(customer_id_elem.get("schemeID"))
        cust_id = (customer_id_elem.text or "").strip()
        if cust_type == "6" and not matches(cust_id, r"^\d{11}$"):
            add_error(
                errors,
                "2017",
                "Si 'Tipo de documento de identidad del adquiriente' es RUC (6), el formato del Tag UBL es diferente a numérico de 11 dígitos",
            )

    # ERROR 3030: serie F y modifica factura (01) → AddressTypeCode obligatorio
    serie = _serie(root)
    ref_type = _ref_doc_type(root)
    if serie and serie.upper().startswith("F") and ref_type == "01":
        address_type = text(
            root,
            "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cac:RegistrationAddress/cbc:AddressTypeCode",
            _NS,
        )
        if address_type is None or address_type == "":
            add_error(
                errors,
                "3030",
                "Si 'Serie del comprobante' inicia con 'F' y 'Tipo de documento que modifica' es '01', no existe el tag cbc:AddressTypeCode o es vacío",
            )

    # ERROR 3098: tipo de operación 0201/0208 → Delivery/Country/IdentificationCode obligatorio
    # En CreditNote no hay InvoiceTypeCode; usamos el atributo listID de CustomizationID como proxy
    # de tipo de operación cuando se informa. Si no se informa, la regla no aplica.
    op_type = _operation_type(root)
    if op_type in {"0201", "0208"}:
        country_id = text(
            root,
            "cac:Delivery/cac:DeliveryLocation/cac:Address/cac:Country/cbc:IdentificationCode",
            _NS,
        )
        if country_id is None or country_id == "":
            add_error(
                errors,
                "3098",
                "Si 'Tipo de operación' es '0201' o '0208', no existe el tag cac:Delivery/.../cbc:IdentificationCode o es vacío",
            )


def _operation_type(root: etree._Element) -> str | None:
    """Devuelve el tipo de operación si se informa; en CreditNote no es estándar."""
    custom = root.find("cbc:CustomizationID", namespaces=_NS)
    if custom is not None:
        val = (custom.get("listID") or "").strip()
        if val:
            return val
    note = root.find("cbc:Note", namespaces=_NS)
    if note is not None:
        val = (note.get("languageLocaleID") or "").strip()
        if val:
            return val
    return None


def _validate_lines(root: etree._Element, errors: list[ValidationError]) -> None:
    currency = _doc_currency(root)
    resp_code = _resp_code(root)
    ref_type = _ref_doc_type(root)
    modifies_invoice = ref_type == "01"

    lines = all_(root, "cac:CreditNoteLine", _NS)
    for line in lines:
        _validate_line_quantity(root, line, errors)
        _validate_line_prices(root, line, errors, modifies_invoice)
        _validate_line_taxes(root, line, errors, resp_code, modifies_invoice)
        _validate_line_allowance_charge(root, line, errors)

        _validate_line_additional_item_properties(root, line, errors)

def _validate_line_quantity(
    root: etree._Element, line: etree._Element, errors: list[ValidationError]
) -> None:
    qty_elem = line.find("cbc:CreditedQuantity", namespaces=_NS)
    op_type = _operation_type(root)
    if qty_elem is not None:
        unit_code = qty_elem.get("unitCode")
        # ERROR 2936: unitCode en Catálogo N.° 03
        if unit_code is not None and unit_code not in CATALOG03:
            add_error(
                errors,
                "2936",
                "El valor del atributo cbc:CreditedQuantity@unitCode no corresponde al Catálogo N.° 03",
            )
        # ERROR 3115: operación 1004 requiere unitCode TNE
        if op_type == "1004" and unit_code is not None and unit_code != "TNE":
            add_error(
                errors,
                "3115",
                "El dato ingresado como unidad de medida de cantidad de especie vendidas no corresponde al valor esperado",
            )


def _validate_line_prices(
    root: etree._Element,
    line: etree._Element,
    errors: list[ValidationError],
    modifies_invoice: bool,
) -> None:
    # ERROR 2369: Price/PriceAmount formato
    price_amount = text(line, "cac:Price/cbc:PriceAmount", _NS)
    if price_amount is not None and not _positive_amount_10(price_amount):
        add_error(
            errors,
            "2369",
            "El formato del Tag UBL cac:Price/cbc:PriceAmount es diferente de decimal positivo de 12 enteros y hasta 10 decimales y diferente de cero",
        )

    # ERROR 2370: LineExtensionAmount formato
    line_ext = text(line, "cbc:LineExtensionAmount", _NS)
    if line_ext is not None and not _positive_amount(line_ext):
        add_error(
            errors,
            "2370",
            "El formato del Tag UBL cbc:LineExtensionAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
        )

    # ERROR 2367: PricingReference/AlternativeConditionPrice/PriceAmount formato
    alt_prices = line.findall("cac:PricingReference/cac:AlternativeConditionPrice", namespaces=_NS)
    price_type_codes: list[str] = []
    has_price_type_02 = False
    for alt in alt_prices:
        pa = text(alt, "cbc:PriceAmount", _NS)
        if pa is not None and not _positive_amount_10(pa):
            add_error(
                errors,
                "2367",
                "El formato del Tag UBL cac:PricingReference/.../cbc:PriceAmount es diferente de decimal positivo de 12 enteros y hasta 10 decimales y diferente de cero",
            )
        ptc = text(alt, "cbc:PriceTypeCode", _NS)
        if ptc is not None:
            price_type_codes.append(ptc)
            if _catalog16(ptc) == "02":
                has_price_type_02 = True

    # ERROR 2409: PriceTypeCode repetido en la línea
    if len(price_type_codes) != len(set(price_type_codes)):
        add_error(
            errors,
            "2409",
            "Existe en el mismo ítem otro cac:AlternativeConditionPrice con el mismo valor del Tag UBL cbc:PriceTypeCode",
        )

    gratuita = _line_is_gratuita(line)

    # ERROR 2640: operación gratuita → PriceAmount debe ser > 0
    if gratuita:
        for alt in alt_prices:
            pa = parse_amount(text(alt, "cbc:PriceAmount", _NS))
            ptc = _catalog16(text(alt, "cbc:PriceTypeCode", _NS))
            if ptc == "01" and pa is not None and pa > 0:
                add_error(
                    errors,
                    "2640",
                    "Operación gratuita, solo debe consignar un monto referencial",
                )

    # ERROR 3224: no es gratuita y price type 02 con monto > 0
    if not gratuita and has_price_type_02:
        for alt in alt_prices:
            pa = parse_amount(text(alt, "cbc:PriceAmount", _NS))
            ptc = _catalog16(text(alt, "cbc:PriceTypeCode", _NS))
            if ptc == "02" and pa is not None and pa > 0:
                add_error(
                    errors,
                    "3224",
                    "Si existe 'Valor referencial unitario en operac. no onerosas' con monto mayor a cero, la operación debe ser gratuita",
                )

    # ERROR 3234: gratuita y price type diferente de 02
    if gratuita and has_price_type_02:
        for alt in alt_prices:
            ptc = _catalog16(text(alt, "cbc:PriceTypeCode", _NS))
            if ptc != "02":
                add_error(
                    errors,
                    "3234",
                    "El código de precio '02' es sólo para operaciones gratuitas",
                )

    # ERROR 3270: precio unitario debe cuadrar con valor venta + impuestos - descuentos + cargos
    if modifies_invoice:
        _check_line_unit_price(root, line, errors)

    # ERROR 3271: LineExtensionAmount debe cuadrar
    if modifies_invoice:
        _check_line_extension_amount(root, line, errors)


def _line_is_gratuita(line: etree._Element) -> bool:
    for sub in _line_tax_subtotals(line):
        if _tax_code(sub) == "9996" and (_taxable_amount(sub) or Decimal("0")) > 0:
            return True
    return False


def _check_line_unit_price(
    root: etree._Element, line: etree._Element, errors: list[ValidationError]
) -> None:
    """ERROR 3270: verifica precio unitario incluyendo IGV."""
    qty_text = text(line, "cbc:CreditedQuantity", _NS)
    price_alt = line.find("cac:PricingReference/cac:AlternativeConditionPrice[cbc:PriceTypeCode='01']", namespaces=_NS)
    if price_alt is None:
        price_alt = line.find("cac:PricingReference/cac:AlternativeConditionPrice", namespaces=_NS)
    if qty_text is None or price_alt is None:
        return
    qty = parse_amount(qty_text)
    price = parse_amount(text(price_alt, "cbc:PriceAmount", _NS))
    if qty is None or qty == 0 or price is None:
        return
    line_ext = parse_amount(text(line, "cbc:LineExtensionAmount", _NS)) or Decimal("0")
    line_tax = parse_amount(text(line, "cac:TaxTotal/cbc:TaxAmount", _NS)) or Decimal("0")
    expected_price = (line_ext + line_tax) / qty
    if not _within_tolerance(price, expected_price, Decimal("1")):
        add_error(
            errors,
            "3270",
            "El precio unitario de la operación difiere de los cálculos realizados en base a la información remitida",
        )


def _check_line_extension_amount(
    root: etree._Element, line: etree._Element, errors: list[ValidationError]
) -> None:
    """ERROR 3271: verifica valor de venta por ítem."""
    qty_text = text(line, "cbc:CreditedQuantity", _NS)
    price_text = text(line, "cac:Price/cbc:PriceAmount", _NS)
    line_ext_text = text(line, "cbc:LineExtensionAmount", _NS)
    if qty_text is None or price_text is None or line_ext_text is None:
        return
    qty = parse_amount(qty_text)
    price = parse_amount(price_text)
    line_ext = parse_amount(line_ext_text)
    if qty is None or price is None or line_ext is None:
        return

    gratuita = _line_is_gratuita(line)
    ref_price = None
    if gratuita:
        ref_alt = line.find(
            "cac:PricingReference/cac:AlternativeConditionPrice[cbc:PriceTypeCode='02']",
            namespaces=_NS,
        )
        if ref_alt is not None:
            ref_price = parse_amount(text(ref_alt, "cbc:PriceAmount", _NS))

    if ref_price is not None:
        expected = qty * ref_price
    else:
        expected = qty * price
    if not _within_tolerance(line_ext, expected, Decimal("1")):
        add_error(
            errors,
            "3271",
            "El valor de venta por ítem difiere de los importes consignados",
        )


def _validate_line_additional_item_properties(
    root: etree._Element, line: etree._Element, errors: list[ValidationError]
) -> None:
    """ERROR 3065: UsabilityPeriod/StartDate cuando ciertos códigos de concepto existen."""
    concept_codes: set[str] = set()
    for prop in line.findall("cac:Item/cac:AdditionalItemProperty", namespaces=_NS):
        code = text(prop, "cbc:NameCode", _NS)
        if code is not None:
            concept_codes.add(code)

    required = False
    if "3059" in concept_codes or "3005" in concept_codes:
        required = True

    if required:
        start_date = text(line, "cac:Item/cac:AdditionalItemProperty/cac:UsabilityPeriod/cbc:StartDate", _NS)
        if start_date is None:
            add_error(
                errors,
                "3065",
                "De existir 'Código del concepto' igual a '3059' o '3005', no existe el tag cac:UsabilityPeriod/cbc:StartDate",
            )
def _validate_line_taxes(
    root: etree._Element,
    line: etree._Element,
    errors: list[ValidationError],
    resp_code: str | None,
    modifies_invoice: bool,
) -> None:
    gratuita = _line_is_gratuita(line)
    alt_prices = line.findall("cac:PricingReference/cac:AlternativeConditionPrice", namespaces=_NS)
    tax_totals = line.findall("cac:TaxTotal", namespaces=_NS)

    # ERROR 3195: debe existir al menos un TaxTotal en la línea
    if not tax_totals:
        add_error(errors, "3195", "No existe el tag cac:CreditNoteLine/cac:TaxTotal")
        return

    # ERROR 3026: más de un TaxTotal por línea
    if len(tax_totals) > 1:
        add_error(errors, "3026", "El tag cac:TaxTotal no debe repetirse a nivel de ítem")

    # ERROR 3021: formato del total de impuestos de línea
    total_tax_text = text(line, "cac:TaxTotal/cbc:TaxAmount", _NS)
    if total_tax_text is not None and not _positive_amount(total_tax_text):
        add_error(
            errors,
            "3021",
            "El formato del Tag UBL cac:TaxTotal/cbc:TaxAmount de la línea no cumple con el formato establecido",
        )

    tax_codes_with_base: set[str] = set()
    seen_tax_codes: set[str] = set()

    for sub in _line_tax_subtotals(line):
        code = _tax_code(sub)
        base = _taxable_amount(sub) or Decimal("0")
        tax = _tax_amount(sub)
        pct = _percent(sub)
        exempt = _exemption_code(sub)

        if code is not None:
            # ERROR 3067: código de tributo repetido en la línea
            if code in seen_tax_codes:
                add_error(
                    errors,
                    "3067",
                    "Existe en el mismo ítem más de un cac:TaxSubtotal con el mismo valor del Tag UBL cbc:ID",
                )
            seen_tax_codes.add(code)
            if base > 0:
                tax_codes_with_base.add(code)

        # ERROR 2037: código de tributo obligatorio
        if code is None or code == "":
            add_error(
                errors,
                "2037",
                "No existe el Tag UBL cac:TaxCategory/cac:TaxScheme/cbc:ID del ítem o es vacío",
            )

        # ERROR 2996: nombre de tributo obligatorio
        name = text(sub, "cac:TaxCategory/cac:TaxScheme/cbc:Name", _NS)
        if name is None or name == "":
            add_error(
                errors,
                "2996",
                "No existe el Tag UBL cac:TaxCategory/cac:TaxScheme/cbc:Name del ítem o es vacío",
            )

        # ERROR 3031: TaxableAmount formato
        taxable_text = text(sub, "cbc:TaxableAmount", _NS)
        if taxable_text is not None and not _positive_amount(taxable_text):
            add_error(
                errors,
                "3031",
                "El formato del Tag UBL cbc:TaxableAmount de la línea no cumple con el formato establecido",
            )

        # ERROR 2033: TaxAmount formato
        if tax is not None:
            tax_text = text(sub, "cbc:TaxAmount", _NS)
            if tax_text is not None and not _positive_amount(tax_text):
                add_error(
                    errors,
                    "2033",
                    "El formato del Tag UBL cbc:TaxAmount de la línea no cumple con el formato establecido",
                )

        # ERROR 2992: Percent obligatorio excepto para 7152
        if code != "7152" and pct is None:
            add_error(
                errors,
                "2992",
                "El XML no contiene el tag de la tasa del tributo de la línea",
            )

        # ERROR 3102: Percent formato
        pct_text = text(sub, "cac:TaxCategory/cbc:Percent", _NS)
        if pct_text is not None and not _percentage(pct_text):
            add_error(
                errors,
                "3102",
                "El formato del Tag UBL cac:TaxCategory/cbc:Percent es diferente de decimal positivo de 3 enteros y hasta 5 decimales y diferente de cero",
            )

        # ERROR 2371: TaxExemptionReasonCode obligatorio para tributos IGV-like con base > 0
        if code in _IGV_LIKE_CODES and base > 0 and exempt is None:
            add_error(
                errors,
                "2371",
                "El XML no contiene el tag cbc:TaxExemptionReasonCode de Afectación al IGV",
            )

        # ERROR 3050: TaxExemptionReasonCode no debe existir para ISC/9999
        if code in {"2000", "9999"} and exempt is not None:
            add_error(
                errors,
                "3050",
                "Afectación de IGV no corresponde al código de tributo de la línea",
            )

        # ERROR 2373: TierRange obligatorio para ISC con base > 0
        if code == "2000" and base > 0:
            tier = text(sub, "cac:TaxCategory/cbc:TierRange", _NS)
            if tier is None or tier == "":
                add_error(
                    errors,
                    "2373",
                    "Si existe monto de ISC en el ítem debe especificar el sistema de cálculo",
                )

        # ERROR 3210: TierRange no debe existir si no es ISC
        if code != "2000" and text(sub, "cac:TaxCategory/cbc:TierRange", _NS) is not None:
            add_error(
                errors,
                "3210",
                "Solo debe consignar sistema de cálculo si el tributo es ISC",
            )

        # ERROR 3104: Percent != 0 para ISC con base > 0
        if code == "2000" and base > 0 and pct is not None and pct == 0:
            add_error(
                errors,
                "3104",
                "El factor de afectación de ISC por línea debe ser diferente a 0.00",
            )

        # ERROR 3103: TaxAmount == Percent * TaxableAmount (tolerancia 1)
        if code in {"1000", "1016"} and base > 0 and pct is not None and tax is not None:
            expected = (base * pct) / Decimal("100")
            if not _within_tolerance(tax, expected):
                add_error(
                    errors,
                    "3103",
                    "El producto del factor y monto base de la afectación del IGV/IVAP no corresponde al monto de afectación de línea",
                )

        # ERROR 3108 / 3109: ISC / Otros tributos
        if code == "2000" and base > 0 and pct is not None and tax is not None:
            expected = (base * pct) / Decimal("100")
            if not _within_tolerance(tax, expected):
                add_error(
                    errors,
                    "3108",
                    "El producto del factor y monto base de la afectación del ISC no corresponde al monto de afectación de línea",
                )
        if code == "9999" and base > 0 and pct is not None and tax is not None:
            expected = (base * pct) / Decimal("100")
            if not _within_tolerance(tax, expected):
                add_error(
                    errors,
                    "3109",
                    "El producto del factor y monto base de la afectación de otros tributos no corresponde al monto de afectación de línea",
                )

        # ERROR 3110: TaxAmount == 0 para exoneradas/inafectas/exportación
        if code in {"9995", "9997", "9998"} and tax is not None and tax != 0:
            add_error(
                errors,
                "3110",
                "El monto de afectación de IGV por línea debe ser igual a 0.00 para Exoneradas, Inafectas, Exportación",
            )
        if code == "9996" and base > 0 and exempt in {"11", "12", "13", "14", "15", "16", "17"} and tax is not None and tax != 0:
            add_error(
                errors,
                "3110",
                "El monto de afectación de IGV por línea debe ser igual a 0.00 para operaciones gratuitas de exoneradas/inafectas",
            )

        # ERROR 3111: TaxAmount != 0 para gravadas (1000/1016) con base > 0.06
        if code in {"1000", "1016"} and base > Decimal("0.06") and tax is not None and tax == 0:
            add_error(
                errors,
                "3111",
                "El monto de afectación de IGV por línea debe ser diferente a 0.00",
            )
        if code == "9996" and base > Decimal("0.06") and exempt in {"11", "12", "13", "14", "15", "16", "17"} and tax is not None and tax == 0:
            add_error(
                errors,
                "3111",
                "El monto de afectación de IGV por línea debe ser diferente a 0.00",
            )

        # ERROR 2993: Percent != 0 para gravadas con base > 0
        if code in {"1000", "1016"} and base > 0 and pct is not None and pct == 0:
            add_error(
                errors,
                "2993",
                "El factor de afectación de IGV por línea debe ser diferente a 0.00",
            )
        if code == "9996" and base > 0 and exempt in {"11", "12", "13", "14", "15", "16", "17"} and pct is not None and pct == 0:
            add_error(
                errors,
                "2993",
                "El factor de afectación de IGV por línea debe ser diferente a 0.00",
            )

        # ERROR 3112: TaxAmount != 0 para 9996 gratuitas de inafectas/exportación con base > 0
        if code == "9996" and base > 0 and exempt in {"21", "31", "32", "33", "34", "35", "36", "37", "40"} and tax is not None and tax != 0:
            add_error(
                errors,
                "3112",
                "El monto de afectación de IGV por línea debe ser igual a 0.00 para operaciones gratuitas de inafectas/exportación",
            )

        # ERROR 3113: TaxAmount == 0 para gravadas (1000/1016) con base > 0
        if code in {"1000", "1016"} and base > 0 and tax is not None and tax == 0:
            add_error(
                errors,
                "3113",
                "El monto de afectación de IGV por línea debe ser diferente a 0.00",
            )

    # ERROR 2641: gratuita con precio referencial > 0 debe tener total global gratuita > 0
    if gratuita:
        has_ref_price_02 = False
        for alt in alt_prices:
            if _catalog16(text(alt, "cbc:PriceTypeCode", _NS)) == "02":
                pa = parse_amount(text(alt, "cbc:PriceAmount", _NS))
                if pa is not None and pa > 0:
                    has_ref_price_02 = True
                    break
        if has_ref_price_02:
            global_gratuita_val = Decimal("0")
            for ts in root.findall("cac:TaxTotal/cac:TaxSubtotal", namespaces=_NS):
                if _tax_code(ts) == "9996":
                    global_gratuita_val = parse_amount(text(ts, "cbc:TaxableAmount", _NS)) or Decimal("0")
                    break
            if global_gratuita_val <= 0:
                add_error(
                    errors,
                    "2641",
                    "Operación gratuita, debe consignar Total valor venta - operaciones gratuitas mayor a cero",
                )

    # ERROR 3224: no es gratuita y price type 02 con monto > 0
    if not gratuita:
        for alt in alt_prices:
            pa = parse_amount(text(alt, "cbc:PriceAmount", _NS))
            ptc = _catalog16(text(alt, "cbc:PriceTypeCode", _NS))
            if ptc == "02" and pa is not None and pa > 0:
                add_error(
                    errors,
                    "3224",
                    "Si existe 'Valor referencial unitario en operac. no onerosas' con monto mayor a cero, la operación debe ser gratuita",
                )

    # ERROR 3234: gratuita y price type diferente de 02 (o sin 02)
    if gratuita:
        has_02 = any(_catalog16(text(alt, "cbc:PriceTypeCode", _NS)) == "02" for alt in alt_prices)
        if not has_02:
            add_error(
                errors,
                "3234",
                "El código de precio '02' es sólo para operaciones gratuitas",
            )

    # ERROR 2640: operación gratuita → PriceAmount tipo 01 debe ser 0
    if gratuita:
        for alt in alt_prices:
            pa = parse_amount(text(alt, "cbc:PriceAmount", _NS))
            ptc = _catalog16(text(alt, "cbc:PriceTypeCode", _NS))
            if ptc == "01" and pa is not None and pa > 0:
                add_error(
                    errors,
                    "2640",
                    "Operación gratuita, solo debe consignar un monto referencial",
                )

    # ERROR 2892 / 3237 / 3236 / 3238: ICBPER
    if code == "7152":
        base_measure = text(sub, "cbc:BaseUnitMeasure", _NS)
        if base_measure is None:
            add_error(
                errors,
                "3237",
                "Debe consignar el campo cac:TaxSubtotal/cbc:BaseUnitMeasure a nivel de ítem",
            )
        elif not _integer_ge_zero_le(base_measure, 5):
            add_error(
                errors,
                "2892",
                "El formato del Tag UBL cbc:BaseUnitMeasure es diferente de entero mayor o igual a cero y de hasta 5 dígitos",
            )
        else:
            bm = parse_amount(base_measure) or Decimal("0")
            qty_text = text(line, "cbc:CreditedQuantity", _NS)
            qty = parse_amount(qty_text) if qty_text else Decimal("0")
            if bm > 0 and bm != qty:
                add_error(
                    errors,
                    "3236",
                    "El valor de cbc:BaseUnitMeasure no corresponde a la cantidad de unidades por ítem",
                )
        per_unit = text(sub, "cac:TaxCategory/cbc:PerUnitAmount", _NS)
        if per_unit is not None and not _percentage(per_unit):
            add_error(
                errors,
                "2892",
                "El formato del Tag UBL cbc:PerUnitAmount es diferente de decimal positivo de 3 enteros y hasta 5 decimales y diferente de cero",
            )
        if base_measure is not None:
            bm = parse_amount(base_measure) or Decimal("0")
            pu = parse_amount(per_unit) if per_unit else Decimal("0")
            if bm > 0 and pu == 0:
                add_error(
                    errors,
                    "3238",
                    "El valor de cbc:PerUnitAmount no corresponde al valor esperado",
                )

    # ERROR 3272: TaxableAmount cuadre
    if modifies_invoice:
        price = parse_amount(text(line, "cac:Price/cbc:PriceAmount", _NS)) or Decimal("0")
        isc_tax = Decimal("0")
        for s2 in _line_tax_subtotals(line):
            if _tax_code(s2) == "2000":
                isc_tax = _tax_amount(s2) or Decimal("0")
        if code == "2000" and base > 0:
            expected = price + isc_tax
        else:
            expected = price
        if not _within_tolerance(base, expected):
            add_error(
                errors,
                "3272",
                "La base imponible a nivel de línea difiere de la información consignada en el comprobante",
            )

    # ERROR 3105: al menos un tributo IGV-like por línea
    if not tax_codes_with_base.intersection(_IGV_LIKE_CODES):
        add_error(
            errors,
            "3105",
            "El XML debe contener al menos un tributo por línea de afectación por IGV",
        )

    # ERROR 3223: combinación de tributos permitida
    if tax_codes_with_base and tax_codes_with_base not in _VALID_TAX_COMBINATIONS:
        add_error(
            errors,
            "3223",
            "La combinación de tributos no es permitida",
        )

    # ERROR 2642 / 2644: resp_code 11 → 40, resp_code 12 → 17
    if resp_code == "11":
        for sub in _line_tax_subtotals(line):
            if _tax_code(sub) in _IGV_LIKE_CODES and (_taxable_amount(sub) or Decimal("0")) > 0:
                exempt = _exemption_code(sub)
                if exempt != "40":
                    add_error(
                        errors,
                        "2642",
                        "Operaciones de exportación, deben consignar Tipo Afectación igual a 40",
                    )
    if resp_code == "12":
        for sub in _line_tax_subtotals(line):
            if _tax_code(sub) in _IGV_LIKE_CODES and (_taxable_amount(sub) or Decimal("0")) > 0:
                exempt = _exemption_code(sub)
                if exempt != "17":
                    add_error(
                        errors,
                        "2644",
                        "Comprobante operación sujeta IVAP solo debe tener ítems con código de afectación del IGV igual a 17",
                    )


def _validate_line_allowance_charge(
    root: etree._Element, line: etree._Element, errors: list[ValidationError]
) -> None:
    for ac in line.findall("cac:AllowanceCharge", namespaces=_NS):
        indicator = text(ac, "cbc:ChargeIndicator", _NS)
        reason_code = text(ac, "cbc:AllowanceChargeReasonCode", _NS)
        factor = text(ac, "cbc:MultiplierFactorNumeric", _NS)
        amount = text(ac, "cbc:Amount", _NS)
        base_amount = text(ac, "cbc:BaseAmount", _NS)

        # ERROR 3073: código de motivo obligatorio
        if reason_code is None or reason_code == "":
            add_error(
                errors,
                "3073",
                "No existe el Tag UBL cbc:AllowanceChargeReasonCode o es vacío",
            )

        # ERROR 3114: indicador para códigos 47/48
        if reason_code in {"47", "48"} and indicator != "true":
            add_error(
                errors,
                "3114",
                "El indicador de cargo/descuento debe ser 'true' para códigos de motivo 47 y 48",
            )

        # ERROR 3052: factor formato
        if factor is not None and not _percentage(factor):
            add_error(
                errors,
                "3052",
                "El formato del Tag UBL cbc:MultiplierFactorNumeric es diferente de decimal positivo de 3 enteros y hasta 5 decimales y diferente de cero",
            )

        # ERROR 3053: base amount formato
        if base_amount is not None and not _positive_amount(base_amount):
            add_error(
                errors,
                "3053",
                "El formato del Tag UBL cbc:BaseAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 3074: amount == 0 cuando código 45
        if reason_code == "45" and amount is not None:
            amt = parse_amount(amount)
            if amt is not None and amt == 0:
                add_error(
                    errors,
                    "3074",
                    "El monto del cargo/descuento debe ser mayor a 0 cuando el código de motivo es 45",
                )


def _validate_global_taxes(root: etree._Element, errors: list[ValidationError]) -> None:
    tax_totals = root.findall("cac:TaxTotal", namespaces=_NS)

    # ERROR 2956: debe existir TaxTotal global
    if not tax_totals:
        add_error(errors, "2956", "No existe el tag /CreditNote/cac:TaxTotal")
        return

    # ERROR 3024: más de un TaxTotal global
    if len(tax_totals) > 1:
        add_error(errors, "3024", "El tag cac:TaxTotal no debe repetirse a nivel de totales")

    global_total_text = text(root, "cac:TaxTotal/cbc:TaxAmount", _NS)
    global_total = parse_amount(global_total_text)

    # ERROR 3020: formato del total global
    if global_total_text is not None and not _positive_amount(global_total_text):
        add_error(
            errors,
            "3020",
            "El formato del Tag UBL cac:TaxTotal/cbc:TaxAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
        )

    resp_code = _resp_code(root)
    modifies_invoice = _ref_doc_type(root) == "01"

    # Recolectar subtotales globales y líneas
    global_subtotals = root.findall("cac:TaxTotal/cac:TaxSubtotal", namespaces=_NS)
    seen_global_codes: set[str] = set()
    global_bases: dict[str, Decimal] = {}
    global_taxes: dict[str, Decimal] = {}

    line_bases: dict[str, Decimal] = {}
    line_taxes: dict[str, Decimal] = {}
    line_exts_by_tax: dict[str, Decimal] = {}

    for line in all_(root, "cac:CreditNoteLine", _NS):
        line_ext = parse_amount(text(line, "cbc:LineExtensionAmount", _NS)) or Decimal("0")
        for sub in _line_tax_subtotals(line):
            code = _tax_code(sub)
            if code is None:
                continue
            base = _taxable_amount(sub) or Decimal("0")
            tax = _tax_amount(sub) or Decimal("0")
            line_bases[code] = line_bases.get(code, Decimal("0")) + base
            line_taxes[code] = line_taxes.get(code, Decimal("0")) + tax
            if base > 0:
                line_exts_by_tax[code] = line_exts_by_tax.get(code, Decimal("0")) + line_ext

    for sub in global_subtotals:
        code = _tax_code(sub)
        base = _taxable_amount(sub)
        tax = _tax_amount(sub)
        base_text = text(sub, "cbc:TaxableAmount", _NS)
        tax_text = text(sub, "cbc:TaxAmount", _NS)

        # ERROR 3059: código de tributo obligatorio
        if code is None or code == "":
            add_error(
                errors,
                "3059",
                "No existe el Tag UBL cac:TaxCategory/cac:TaxScheme/cbc:ID o es vacío",
            )
            continue

        # ERROR 3068: código de tributo repetido globalmente
        if code in seen_global_codes:
            add_error(
                errors,
                "3068",
                "Existe a nivel global más de un cac:TaxSubtotal con el mismo valor del Tag UBL cbc:ID",
            )
        seen_global_codes.add(code)

        if base is not None:
            global_bases[code] = base
        if tax is not None:
            global_taxes[code] = tax

        # ERROR 3003: TaxableAmount obligatorio cuando código != 7152
        if code != "7152" and base_text is None:
            add_error(
                errors,
                "3003",
                "No existe el Tag UBL cac:TaxSubtotal/cbc:TaxableAmount o no existe información de total valor de venta globales",
            )

        # ERROR 2999: TaxableAmount formato
        if base_text is not None and not _positive_amount(base_text):
            add_error(
                errors,
                "2999",
                "El formato del Tag UBL cac:TaxSubtotal/cbc:TaxableAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 2048: TaxAmount formato
        if tax_text is not None and not _positive_amount(tax_text):
            add_error(
                errors,
                "2048",
                "El formato del Tag UBL cac:TaxSubtotal/cbc:TaxAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 3000: TaxAmount == 0 para 9995/9997/9998
        if code in {"9995", "9997", "9998"} and tax is not None and tax != 0:
            add_error(
                errors,
                "3000",
                "El monto total del impuesto sobre el valor de venta de operaciones gratuitas/inafectas/exoneradas debe ser igual a 0.00",
            )

        # ERROR 2054: Name obligatorio
        name = text(sub, "cac:TaxCategory/cac:TaxScheme/cbc:Name", _NS)
        if name is None or name == "":
            add_error(
                errors,
                "2054",
                "No existe el Tag UBL cac:TaxCategory/cac:TaxScheme/cbc:Name de impuestos globales",
            )

        # ERROR 2052: TaxTypeCode obligatorio
        ttc = text(sub, "cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode", _NS)
        if ttc is None or ttc == "":
            add_error(
                errors,
                "2052",
                "No existe el Tag UBL cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode de impuestos globales",
            )

        # ERROR 2949: ICBPER antes de 2019-08-01
        if code == "7152" and tax is not None and tax > 0:
            issue = _issue_date(root)
            if issue is not None and issue < "2019-08-01":
                add_error(
                    errors,
                    "2949",
                    "El impuesto ICBPER no se encuentra vigente",
                )

    # ERROR 2638: si existe tributo en línea, debe existir su total global
    for code in line_bases:
        if line_bases[code] > 0 and code not in global_bases:
            add_error(
                errors,
                "2638",
                "Si tiene operaciones de un tributo en alguna línea, debe consignar el tag del total del tributo",
            )

    # ERROR 3106 / 3107: códigos inválidos según tipo de nota de crédito
    if resp_code == "12":
        if "1000" in global_bases and global_bases["1000"] > 0:
            add_error(
                errors,
                "3106",
                "El dato ingresado como código de tributo global es inválido para tipo de operación IVAP",
            )
    if resp_code == "11":
        for code in {"1000", "1016", "2000", "9999"}:
            if code in global_bases and global_bases[code] > 0:
                add_error(
                    errors,
                    "3107",
                    "El dato ingresado como código de tributo global es inválido para tipo de operación exportación",
                )
                break

    # Cuadres globales (solo cuando modifica factura 01)
    if modifies_invoice:
        _check_global_tax_sums(root, errors, global_bases, global_taxes, line_bases, line_taxes, line_exts_by_tax)


def _check_global_tax_sums(
    root: etree._Element,
    errors: list[ValidationError],
    global_bases: dict[str, Decimal],
    global_taxes: dict[str, Decimal],
    line_bases: dict[str, Decimal],
    line_taxes: dict[str, Decimal],
    line_exts_by_tax: dict[str, Decimal],
) -> None:
    # ERROR 3277: base 1000 == suma line_exts de líneas con 1000 base > 0
    if "1000" in global_bases:
        expected = line_exts_by_tax.get("1000", Decimal("0"))
        if not _within_tolerance(global_bases["1000"], expected):
            add_error(
                errors,
                "3277",
                "La sumatoria del total valor de venta - operaciones gravadas de línea no corresponden al total",
            )

    # ERROR 3293: base 1016
    if "1016" in global_bases:
        expected = line_exts_by_tax.get("1016", Decimal("0"))
        if not _within_tolerance(global_bases["1016"], expected):
            add_error(
                errors,
                "3293",
                "La sumatoria del total valor de venta - IVAP de línea no corresponden al total",
            )

    # ERROR 3273 / 3274 / 3275 / 3276
    for code, err in [("9995", "3273"), ("9998", "3274"), ("9997", "3275"), ("9996", "3276")]:
        if code in global_bases:
            expected = line_exts_by_tax.get(code, Decimal("0"))
            if not _within_tolerance(global_bases[code], expected):
                add_error(
                    errors,
                    err,
                    f"La sumatoria del total valor de venta - {code} de línea no corresponden al total",
                )

    # ERROR 3291 / 3295: TaxAmount 1000 / 1016 == base * tasa
    for code, err in [("1000", "3291"), ("1016", "3295")]:
        if code in global_bases and code in global_taxes:
            # Tomar la tasa de la primera línea con ese tributo
            pct = None
            for line in all_(root, "cac:CreditNoteLine", _NS):
                for sub in _line_tax_subtotals(line):
                    if _tax_code(sub) == code:
                        pct = _percent(sub)
                        break
                if pct is not None:
                    break
            if pct is not None:
                expected = (global_bases[code] * pct) / Decimal("100")
                if not _within_tolerance(global_taxes[code], expected):
                    add_error(
                        errors,
                        err,
                        f"El cálculo del tributo {code} es incorrecto",
                    )

    # ERROR 3296 / 3297: base ISC / Otros
    for code, err in [("2000", "3296"), ("9999", "3297")]:
        if code in global_bases:
            expected = line_bases.get(code, Decimal("0"))
            if not _within_tolerance(global_bases[code], expected):
                add_error(
                    errors,
                    err,
                    f"La sumatoria del monto base - {code} de línea no corresponden al total",
                )

    # ERROR 3298 / 3299: tax ISC / Otros
    for code, err in [("2000", "3298"), ("9999", "3299")]:
        if code in global_taxes:
            expected = line_taxes.get(code, Decimal("0"))
            if not _within_tolerance(global_taxes[code], expected):
                add_error(
                    errors,
                    err,
                    f"La sumatoria del total del importe del tributo {code} de línea no corresponden al total",
                )

    # ERROR 3306: tax 7152 == suma líneas
    if "7152" in global_taxes:
        expected = line_taxes.get("7152", Decimal("0"))
        if not _within_tolerance(global_taxes["7152"], expected):
            add_error(
                errors,
                "3306",
                "La sumatoria del total del importe del tributo ICBPER de línea no corresponden al total",
            )


def _validate_monetary_total(root: etree._Element, errors: list[ValidationError]) -> None:
    # ERROR 2064: ChargeTotalAmount formato
    charge_total_text = text(root, "cac:LegalMonetaryTotal/cbc:ChargeTotalAmount", _NS)
    if charge_total_text is not None and not _positive_amount(charge_total_text):
        add_error(
            errors,
            "2064",
            "El formato del Tag UBL cac:LegalMonetaryTotal/cbc:ChargeTotalAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
        )

    # ERROR 3019: TaxInclusiveAmount formato
    tax_incl_text = text(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", _NS)
    if tax_incl_text is not None and not _positive_amount(tax_incl_text):
        add_error(
            errors,
            "3019",
            "El formato del Tag UBL cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
        )

    # ERROR 3278: LineExtensionAmount == suma de líneas
    line_ext_total_text = text(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount", _NS)
    if line_ext_total_text is not None:
        line_ext_total = parse_amount(line_ext_total_text)
        sum_lines = sum(
            parse_amount(text(line, "cbc:LineExtensionAmount", _NS)) or Decimal("0")
            for line in all_(root, "cac:CreditNoteLine", _NS)
        )
        if line_ext_total is not None and not _within_tolerance(line_ext_total, sum_lines):
            add_error(
                errors,
                "3278",
                "El valor del tag cac:LegalMonetaryTotal/cbc:LineExtensionAmount es diferente de la sumatoria del 'Valor de venta por ítem'",
            )

    # ERROR 3279: TaxInclusiveAmount == suma de totales + impuestos
    if tax_incl_text is not None:
        tax_incl = parse_amount(tax_incl_text)
        if tax_incl is not None:
            total = Decimal("0")
            for sub in root.findall("cac:TaxTotal/cac:TaxSubtotal", namespaces=_NS):
                code = _tax_code(sub)
                tax = _tax_amount(sub) or Decimal("0")
                base = _taxable_amount(sub) or Decimal("0")
                if code == "7152":
                    total += tax
                else:
                    total += base + tax
            # Añadir cargos globales que no afectan la base
            for ac in root.findall("cac:AllowanceCharge", namespaces=_NS):
                indicator = text(ac, "cbc:ChargeIndicator", _NS)
                amount = parse_amount(text(ac, "cbc:Amount", _NS)) or Decimal("0")
                if indicator == "true":
                    total += amount
                elif indicator == "false":
                    total -= amount
            if not _within_tolerance(tax_incl, total):
                add_error(
                    errors,
                    "3279",
                    "La sumatoria del Total del valor de venta más los impuestos no concuerda con la base imponible",
                )

    # ERROR 3303: PayableRoundingAmount absoluto <= 1
    rounding_text = text(root, "cac:LegalMonetaryTotal/cbc:PayableRoundingAmount", _NS)
    if rounding_text is not None:
        rounding = parse_amount(rounding_text)
        if rounding is not None and abs(rounding) > Decimal("1"):
            add_error(
                errors,
                "3303",
                "El monto para el redondeo del Importe Total excede el valor permitido",
            )


def _validate_allowance_charges(root: etree._Element, errors: list[ValidationError]) -> None:
    global_ac = root.findall("cac:AllowanceCharge", namespaces=_NS)

    # ERROR 3093: operación 2001 + contado → debe existir código 51/52/53
    op_type = _operation_type(root)
    payment_terms = all_(root, "cac:PaymentTerms", _NS)
    is_contado = any(
        text(pt, "cbc:ID", _NS) == "FormaPago"
        and text(pt, "cbc:PaymentMeansID", _NS) == "Contado"
        for pt in payment_terms
    )
    if op_type == "2001" and is_contado:
        reason_codes = {text(ac, "cbc:AllowanceChargeReasonCode", _NS) for ac in global_ac}
        if not reason_codes.intersection({"51", "52", "53"}):
            add_error(
                errors,
                "3093",
                "Si operación es sujeta a percepción y la forma de pago es Contado, debe ingresar cargo para Percepción",
            )

    for ac in global_ac:
        indicator = text(ac, "cbc:ChargeIndicator", _NS)
        reason_code = text(ac, "cbc:AllowanceChargeReasonCode", _NS)
        factor = text(ac, "cbc:MultiplierFactorNumeric", _NS)
        amount = text(ac, "cbc:Amount", _NS)
        base_amount = text(ac, "cbc:BaseAmount", _NS)

        # ERROR 3072: código de motivo obligatorio si existe indicador
        if indicator is not None and (reason_code is None or reason_code == ""):
            add_error(
                errors,
                "3072",
                "No existe el Tag UBL cac:AllowanceCharge/cbc:AllowanceChargeReasonCode o es vacío",
            )

        # ERROR 3025: factor formato
        if factor is not None and not _percentage(factor):
            add_error(
                errors,
                "3025",
                "El formato del Tag UBL cac:AllowanceCharge/cbc:MultiplierFactorNumeric es diferente de decimal positivo de 3 enteros y hasta 5 decimales y diferente de cero",
            )

        # ERROR 3016: base amount formato
        if base_amount is not None and not _positive_amount(base_amount):
            add_error(
                errors,
                "3016",
                "El formato del Tag UBL cac:AllowanceCharge/cbc:BaseAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 3092: base amount > 0 cuando código 45
        if reason_code == "45" and (base_amount is None or parse_amount(base_amount) is None or parse_amount(base_amount) <= 0):
            add_error(
                errors,
                "3092",
                "Para cargo/descuento FISE, debe ingresar monto base y debe ser mayor a 0.00",
            )

    # ERROR 3282: descuentos por anticipo requieren PrepaidAmount > 0
    anticipo_codes = {"04", "05", "06", "20"}
    has_anticipo_discount = any(
        text(ac, "cbc:AllowanceChargeReasonCode", _NS) in anticipo_codes
        and parse_amount(text(ac, "cbc:Amount", _NS) or "0") > 0
        for ac in global_ac
    )
    if has_anticipo_discount:
        prepaid_text = text(root, "cac:LegalMonetaryTotal/cbc:PrepaidAmount", _NS)
        prepaid = parse_amount(prepaid_text) if prepaid_text is not None else None
        if prepaid is None or prepaid <= 0:
            add_error(
                errors,
                "3282",
                "Si se informa descuentos globales por anticipo debe existir 'Total de anticipos' con monto mayor a cero",
            )


def _validate_notes(root: etree._Element, errors: list[ValidationError]) -> None:
    notes = root.findall("cbc:Note", namespaces=_NS)

    # ERROR 3006: formato 1-200 caracteres
    for note in notes:
        content = (note.text or "").strip()
        if not re.match(r"^.{1,200}$", content):
            add_error(
                errors,
                "3006",
                "El formato del Tag UBL cbc:Note no cumple con el formato de 1 a 200 caracteres",
            )

    # ERROR 3014: languageLocaleID (código de leyenda) no debe repetirse
    locale_ids = [node.get("languageLocaleID") for node in notes if node.get("languageLocaleID")]
    if len(locale_ids) != len(set(locale_ids)):
        add_error(
            errors,
            "3014",
            "El código de leyenda no debe repetirse en el comprobante",
        )


def _validate_delivery(root: etree._Element, errors: list[ValidationError]) -> None:
    op_type = _operation_type(root)
    if op_type != "1004":
        return

    for line in all_(root, "cac:CreditNoteLine", _NS):
        delivery = line.find("cac:Delivery", namespaces=_NS)
        if delivery is None:
            continue

        # ERROR 3117: dirección punto de origen
        origin = text(
            delivery,
            "cac:Despatch/cac:DespatchAddress/cac:AddressLine/cbc:Line",
            _NS,
        )
        if origin is None or origin == "":
            add_error(
                errors,
                "3117",
                "No existe el tag de dirección del punto de origen en Detracciones - Servicio de transporte de carga",
            )

        # ERROR 3118: ubigeo punto de destino
        dest_id = text(
            delivery,
            "cac:DeliveryLocation/cac:Address/cbc:ID",
            _NS,
        )
        if dest_id is None or dest_id == "":
            add_error(
                errors,
                "3118",
                "No existe el tag de ubigeo del punto de destino en Detracciones - Servicio de transporte de carga",
            )

        # ERROR 3119: dirección punto de destino
        dest_line = text(
            delivery,
            "cac:DeliveryLocation/cac:Address/cac:AddressLine/cbc:Line",
            _NS,
        )
        if dest_line is None:
            add_error(
                errors,
                "3119",
                "No existe el tag de dirección del punto de destino en Detracciones - Servicio de transporte de carga",
            )

        # ERROR 3120: detalle del viaje
        instructions = text(delivery, "cac:Despatch/cbc:Instructions", _NS)
        if instructions is None or instructions == "":
            add_error(
                errors,
                "3120",
                "No existe el tag de detalle del viaje en Detracciones - Servicio de transporte de carga",
            )
