"""Validaciones SUNAT adicionales para Notas de Débito (DebitNote).

Reglas implementadas desde el Excel SUNAT 2026 y rules_DebitNote.txt.
Las reglas que dependen de fechas de recepción, nombre de archivo ZIP o
contextos propios de Factura (tipo de operación, Delivery, exportación de
bienes/servicios específicos) se marcan como FUERA DE ALCANCE.
"""

from decimal import Decimal

from lxml import etree


from openubl.validators.common import (
    ValidationError,
    add_error,
    all_,
    attr,
    exists,
    parse_amount,
    text,
    CATALOG03,
    CATALOG05,
    CATALOG05_NAMES,
    CATALOG07,
    NS_DEBIT_NOTE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doc_serie(root: etree._Element) -> str:
    doc_id = text(root, "cbc:ID", NS_DEBIT_NOTE) or ""
    return doc_id.split("-")[0] if "-" in doc_id else doc_id


def _doc_numero(root: etree._Element) -> str:
    doc_id = text(root, "cbc:ID", NS_DEBIT_NOTE) or ""
    return doc_id.split("-")[1] if "-" in doc_id else ""


def _resp_code(root: etree._Element) -> str | None:
    return text(root, "cac:DiscrepancyResponse/cbc:ResponseCode", NS_DEBIT_NOTE)


def _ref_type(root: etree._Element) -> str | None:
    return text(
        root,
        "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode",
        NS_DEBIT_NOTE,
    )


def _currency(root: etree._Element) -> str | None:
    return text(root, "cbc:DocumentCurrencyCode", NS_DEBIT_NOTE)


def _issue_date(root: etree._Element) -> str | None:
    return text(root, "cbc:IssueDate", NS_DEBIT_NOTE)


def _is_decimal_12_2(value: str | None) -> bool:
    if value is None:
        return False
    import re

    if not re.match(r"^\d{1,12}(\.\d{1,2})?$", value):
        return False
    amount = parse_amount(value)
    return amount is not None and amount > 0


def _is_decimal_12_10(value: str | None) -> bool:
    if value is None:
        return False
    import re

    if not re.match(r"^\d{1,12}(\.\d{1,10})?$", value):
        return False
    amount = parse_amount(value)
    return amount is not None and amount > 0


def _is_decimal_3_5(value: str | None) -> bool:
    if value is None:
        return False
    import re

    if not re.match(r"^\d{1,3}(\.\d{1,5})?$", value):
        return False
    amount = parse_amount(value)
    return amount is not None and amount > 0


def _is_integer_up_to_5(value: str | None) -> bool:
    if value is None:
        return False
    import re

    if not re.match(r"^\d{1,5}$", value):
        return False
    return True


def _line_quantity(line: etree._Element) -> Decimal | None:
    qty_text = text(line, "cbc:DebitedQuantity", NS_DEBIT_NOTE)
    return parse_amount(qty_text)


def _line_tax_subtotals(line: etree._Element) -> list[etree._Element]:
    return all_(line, "cac:TaxTotal/cac:TaxSubtotal", NS_DEBIT_NOTE)


def _line_tax_total_amount(line: etree._Element) -> Decimal | None:
    return parse_amount(text(line, "cac:TaxTotal/cbc:TaxAmount", NS_DEBIT_NOTE))


def _line_extension(line: etree._Element) -> Decimal | None:
    return parse_amount(text(line, "cbc:LineExtensionAmount", NS_DEBIT_NOTE))


def _line_price_amount(line: etree._Element) -> Decimal | None:
    return parse_amount(text(line, "cac:Price/cbc:PriceAmount", NS_DEBIT_NOTE))


def _line_reference_price_amount(line: etree._Element, price_type: str) -> Decimal | None:
    for acp in all_(line, "cac:PricingReference/cac:AlternativeConditionPrice", NS_DEBIT_NOTE):
        if text(acp, "cbc:PriceTypeCode", NS_DEBIT_NOTE) == price_type:
            return parse_amount(text(acp, "cbc:PriceAmount", NS_DEBIT_NOTE))
    return None


def _line_reference_price_type_codes(line: etree._Element) -> list[str]:
    codes = []
    for acp in all_(line, "cac:PricingReference/cac:AlternativeConditionPrice", NS_DEBIT_NOTE):
        code = text(acp, "cbc:PriceTypeCode", NS_DEBIT_NOTE)
        if code is not None:
            codes.append(code)
    return codes


def _global_tax_subtotals(root: etree._Element) -> list[etree._Element]:
    return all_(root, "cac:TaxTotal/cac:TaxSubtotal", NS_DEBIT_NOTE)


def _global_tax_total_amount(root: etree._Element) -> Decimal | None:
    return parse_amount(text(root, "cac:TaxTotal/cbc:TaxAmount", NS_DEBIT_NOTE))


def _find_global_tax_subtotal(root: etree._Element, tax_code: str) -> etree._Element | None:
    for ts in _global_tax_subtotals(root):
        if text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE) == tax_code:
            return ts
    return None


def _has_line_with_tax(root: etree._Element, tax_code: str) -> bool:
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        for ts in _line_tax_subtotals(line):
            code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
            base = parse_amount(text(ts, "cbc:TaxableAmount", NS_DEBIT_NOTE))
            if code == tax_code and base is not None and base > 0:
                return True
    return False


def _sum_line_extensions_by_tax(root: etree._Element, tax_code: str) -> Decimal:
    total = Decimal("0")
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        line_ext = _line_extension(line)
        if line_ext is None:
            continue
        for ts in _line_tax_subtotals(line):
            code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
            base = parse_amount(text(ts, "cbc:TaxableAmount", NS_DEBIT_NOTE))
            if code == tax_code and base is not None and base > 0:
                total += line_ext
                break
    return total


def _sum_line_tax_amounts(root: etree._Element, tax_code: str) -> Decimal:
    total = Decimal("0")
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        for ts in _line_tax_subtotals(line):
            code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
            if code == tax_code:
                amount = parse_amount(text(ts, "cbc:TaxAmount", NS_DEBIT_NOTE))
                if amount is not None:
                    total += amount
    return total


def _sum_line_tax_bases(root: etree._Element, tax_code: str) -> Decimal:
    total = Decimal("0")
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        for ts in _line_tax_subtotals(line):
            code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
            if code == tax_code:
                base = parse_amount(text(ts, "cbc:TaxableAmount", NS_DEBIT_NOTE))
                if base is not None:
                    total += base
    return total


def _global_charge_total(root: etree._Element) -> Decimal | None:
    return parse_amount(
        text(root, "cac:RequestedMonetaryTotal/cbc:ChargeTotalAmount", NS_DEBIT_NOTE)
    )


def _global_prepaid(root: etree._Element) -> Decimal | None:
    return parse_amount(
        text(root, "cac:RequestedMonetaryTotal/cbc:PrepaidAmount", NS_DEBIT_NOTE)
    )


def _global_rounding(root: etree._Element) -> Decimal | None:
    return parse_amount(
        text(root, "cac:RequestedMonetaryTotal/cbc:PayableRoundingAmount", NS_DEBIT_NOTE)
    )


def _within_tolerance(a: Decimal, b: Decimal, tol: Decimal = Decimal("1")) -> bool:
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
# Validación principal
# ---------------------------------------------------------------------------

def validate_debit_note_extra(root: etree._Element, errors: list[ValidationError]) -> None:
    ns = NS_DEBIT_NOTE
    serie = _doc_serie(root)
    ref_type = _ref_type(root)
    resp_code = _resp_code(root)
    issue_date = _issue_date(root)

    _validate_header(root, errors, serie, ref_type, issue_date)
    _validate_parties(root, errors)
    _validate_lines(root, errors, ref_type, resp_code)
    _validate_global_taxes(root, errors, ref_type, resp_code)
    _validate_totals(root, errors, ref_type)
    _validate_notes(root, errors)
    _validate_payment_terms(root, errors)
    _validate_allowance_charges(root, errors)
    _validate_additional_item_properties(root, errors)


# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------

def _validate_header(
    root: etree._Element,
    errors: list[ValidationError],
    serie: str,
    ref_type: str | None,
    issue_date: str | None,
) -> None:
    # ERROR 1079 / 2108: fechas de recepción - FUERA DE ALCANCE
    # Se documenta abajo como fuera de alcance por requerir fecha de recepción SUNAT.
    pass


# ---------------------------------------------------------------------------
# Emisor / Receptor
# ---------------------------------------------------------------------------

def _validate_parties(root: etree._Element, errors: list[ValidationError]) -> None:
    # ERROR 3089: más de un PartyIdentification del emisor
    supplier_ids = all_(
        root,
        "cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification",
        NS_DEBIT_NOTE,
    )
    if len(supplier_ids) > 1:
        add_error(
            errors,
            "3089",
            "Existe más de un Tag UBL cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification",
        )

    # ERROR 3090: más de un PartyIdentification del receptor
    customer_ids = all_(
        root,
        "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification",
        NS_DEBIT_NOTE,
    )
    if len(customer_ids) > 1:
        add_error(
            errors,
            "3090",
            "Existe más de un Tag UBL en el XML cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification",
        )

    # ERROR 2017: si el tipo de documento del receptor es RUC (6), debe tener 11 dígitos
    customer_id_elem = root.find(
        "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
        namespaces=NS_DEBIT_NOTE,
    )
    if customer_id_elem is not None:
        scheme = customer_id_elem.get("schemeID")
        customer_id = (customer_id_elem.text or "").strip()
        if scheme == "6" and not _matches(customer_id, r"^\d{11}$"):
            add_error(
                errors,
                "2017",
                "Si 'Tipo de documento de identidad del adquiriente' es RUC (6), el formato del Tag UBL es diferente a numérico de 11 dígitos",
            )

    # ERROR 3030: código de local anexo si serie inicia con 'F' y modifica factura '01'
    serie = _doc_serie(root)
    ref_type = _ref_type(root)
    if serie.startswith("F") and ref_type == "01":
        address_type = text(
            root,
            "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cac:RegistrationAddress/cbc:AddressTypeCode",
            NS_DEBIT_NOTE,
        )
        if address_type is None:
            add_error(
                errors,
                "3030",
                "Si 'Serie del comprobante' inicia con 'F' y 'Tipo de documento que modifica' es '01', no existe el Tag UBL o es vacío",
            )


def _matches(value: str | None, pattern: str) -> bool:
    if value is None:
        return False
    import re

    return re.match(pattern, value) is not None


# ---------------------------------------------------------------------------
# Líneas
# ---------------------------------------------------------------------------

def _validate_lines(
    root: etree._Element,
    errors: list[ValidationError],
    ref_type: str | None,
    resp_code: str | None,
) -> None:
    lines = all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE)
    seen_line_ids: set[str] = set()

    for line in lines:
        line_id = text(line, "cbc:ID", NS_DEBIT_NOTE)
        if line_id is not None:
            if line_id in seen_line_ids:
                add_error(
                    errors,
                    "2752",
                    "Existe otro cac:DebitNoteLine con el mismo valor del Tag UBL cbc:ID",
                )
            seen_line_ids.add(line_id)

        # ERROR 2936: unidad de medida del catálogo 03
        qty_elem = line.find("cbc:DebitedQuantity", namespaces=NS_DEBIT_NOTE)
        if qty_elem is not None:
            unit_code = qty_elem.get("unitCode")
            if unit_code is not None and unit_code not in CATALOG03:
                add_error(
                    errors,
                    "2936",
                    "El dato ingresado como unidad de medida no corresponde al valor esperado",
                )

        # ERROR 2369: formato del valor unitario (PriceAmount)
        price_amount = text(line, "cac:Price/cbc:PriceAmount", NS_DEBIT_NOTE)
        if price_amount is not None and not _is_decimal_12_10(price_amount):
            add_error(
                errors,
                "2369",
                "El formato del Tag UBL cac:Price/cbc:PriceAmount es diferente de decimal positivo de 12 enteros y hasta 10 decimales y diferente de cero",
            )

        # ERROR 2370: formato del valor de venta por ítem
        line_ext_text = text(line, "cbc:LineExtensionAmount", NS_DEBIT_NOTE)
        line_ext = parse_amount(line_ext_text)
        if line_ext_text is not None and (line_ext is None or line_ext <= 0):
            add_error(
                errors,
                "2370",
                "El formato del Tag UBL cbc:LineExtensionAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 2367: formato del precio de venta unitario / valor referencial
        for acp in all_(line, "cac:PricingReference/cac:AlternativeConditionPrice", NS_DEBIT_NOTE):
            price_amt = text(acp, "cbc:PriceAmount", NS_DEBIT_NOTE)
            if price_amt is not None and not _is_decimal_12_10(price_amt):
                add_error(
                    errors,
                    "2367",
                    "El formato del Tag UBL cbc:PriceAmount es diferente de decimal positivo de 12 enteros y hasta 10 decimales y diferente de cero",
                )

        # ERROR 2409: PriceTypeCode repetido en el ítem
        price_type_codes = _line_reference_price_type_codes(line)
        if len(price_type_codes) != len(set(price_type_codes)):
            add_error(
                errors,
                "2409",
                "Existe en el mismo ítem otro cac:AlternativeConditionPrice con el mismo valor del Tag UBL cbc:PriceTypeCode",
            )

        # ERROR 2640: operación gratuita debe tener precio referencial > 0
        has_gratuita = False
        gratuita_base = Decimal("0")
        for ts in _line_tax_subtotals(line):
            code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
            base = parse_amount(text(ts, "cbc:TaxableAmount", NS_DEBIT_NOTE))
            if code == "9996" and base is not None and base > 0:
                has_gratuita = True
                gratuita_base = base
                break

        if has_gratuita:
            ref_price = _line_reference_price_amount(line, "02")
            if ref_price is None or ref_price <= 0:
                add_error(
                    errors,
                    "2640",
                    "Operacion gratuita, solo debe consignar un monto referencial",
                )
            # ERROR 3224: si no es gratuita y PriceTypeCode 02 > 0 -> error (lo contrario se maneja abajo)
            # ERROR 3234: si es gratuita, el código de precio debe ser '02'
            price_types = _line_reference_price_type_codes(line)
            if price_types and "02" not in price_types:
                add_error(
                    errors,
                    "3234",
                    "Si existe en la misma línea un tributo 9996 con monto base mayor a cero, el 'Código de precio' debe ser '02'",
                )
        else:
            ref_price = _line_reference_price_amount(line, "02")
            if ref_price is not None and ref_price > 0:
                add_error(
                    errors,
                    "3224",
                    "Si no existe operación gratuita y 'Código de precio' es '02', el Tag UBL debe ser cero",
                )

        # ERROR 3270: precio de venta unitario = (valor venta + tributos) / cantidad
        if ref_type == "01" and not has_gratuita:
            price_01 = _line_reference_price_amount(line, "01")
            qty = _line_quantity(line)
            line_tax = _line_tax_total_amount(line)
            line_ext = _line_extension(line)
            if (
                price_01 is not None
                and qty is not None
                and qty > 0
                and line_ext is not None
                and line_tax is not None
            ):
                expected = (line_ext + line_tax) / qty
                if not _within_tolerance(price_01, expected):
                    add_error(
                        errors,
                        "3270",
                        "El precio unitario de la operación difiere de los cálculos realizados en base a la información remitida",
                    )

        # ERROR 3271: valor de venta por ítem = valor unitario * cantidad (ajuste simple)
        if ref_type == "01":
            qty = _line_quantity(line)
            unit_price = _line_price_amount(line)
            line_ext = _line_extension(line)
            if has_gratuita:
                ref_price = _line_reference_price_amount(line, "02")
                if (
                    ref_price is not None
                    and qty is not None
                    and qty > 0
                    and line_ext is not None
                ):
                    expected = ref_price * qty
                    if not _within_tolerance(line_ext, expected):
                        add_error(
                            errors,
                            "3271",
                            "El valor de venta por ítem difiere de los importes consignados",
                        )
            else:
                if (
                    unit_price is not None
                    and qty is not None
                    and qty > 0
                    and line_ext is not None
                ):
                    expected = unit_price * qty
                    if not _within_tolerance(line_ext, expected):
                        add_error(
                            errors,
                            "3271",
                            "El valor de venta por ítem difiere de los importes consignados",
                        )

        # Validaciones por subtotal de impuestos de la línea
        _validate_line_tax_subtotals(root, line, errors, has_gratuita, gratuita_base, resp_code)


# ---------------------------------------------------------------------------
# Impuestos por línea
# ---------------------------------------------------------------------------

def _validate_line_tax_subtotals(
    root: etree._Element,
    line: etree._Element,
    errors: list[ValidationError],
    has_gratuita: bool,
    gratuita_base: Decimal,
    resp_code: str | None,
) -> None:
    tax_subtotals = _line_tax_subtotals(line)

    # ERROR 3026: más de un TaxTotal por ítem
    tax_totals = all_(line, "cac:TaxTotal", NS_DEBIT_NOTE)
    if len(tax_totals) > 1:
        add_error(
            errors,
            "3026",
            "Existe en el mismo ítem más de un tag cac:TaxTotal",
        )

    # ERROR 3195 / 3021: TaxTotal/TaxAmount de la línea
    line_tax_amount_text = text(line, "cac:TaxTotal/cbc:TaxAmount", NS_DEBIT_NOTE)
    if line_tax_amount_text is None:
        add_error(
            errors,
            "3195",
            "No existe el tag cac:DebitNoteLine/cac:TaxTotal",
        )
    elif not _is_decimal_12_2(line_tax_amount_text):
        add_error(
            errors,
            "3021",
            "El formato del Tag UBL cac:TaxTotal/cbc:TaxAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
        )

    seen_tax_codes: set[str] = set()
    has_base_igv_ivap = False
    line_ext = _line_extension(line)

    for ts in tax_subtotals:
        tax_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
        tax_name = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name", NS_DEBIT_NOTE)
        tax_type_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode", NS_DEBIT_NOTE)
        taxable_text = text(ts, "cbc:TaxableAmount", NS_DEBIT_NOTE)
        taxable = parse_amount(taxable_text)
        tax_amount_text = text(ts, "cbc:TaxAmount", NS_DEBIT_NOTE)
        tax_amount = parse_amount(tax_amount_text)
        percent_text = text(ts, "cac:TaxCategory/cbc:Percent", NS_DEBIT_NOTE)
        percent = parse_amount(percent_text)
        exemption = text(ts, "cac:TaxCategory/cbc:TaxExemptionReasonCode", NS_DEBIT_NOTE)
        tier_range = text(ts, "cac:TaxCategory/cbc:TierRange", NS_DEBIT_NOTE)
        base_unit = text(ts, "cbc:BaseUnitMeasure", NS_DEBIT_NOTE)
        per_unit = text(ts, "cac:TaxCategory/cbc:PerUnitAmount", NS_DEBIT_NOTE)

        # ERROR 2037: código de tributo no vacío
        if tax_code is None or tax_code == "":
            add_error(
                errors,
                "2037",
                "No existe el Tag UBL cac:TaxCategory/cac:TaxScheme/cbc:ID del Item",
            )

        # ERROR 2996: nombre de tributo no vacío
        if tax_name is None or tax_name == "":
            add_error(
                errors,
                "2996",
                "No existe el Tag UBL cac:TaxCategory/cac:TaxScheme/cbc:Name del Item",
            )

        # ERROR 3067: código de tributo repetido en el ítem
        if tax_code is not None:
            if tax_code in seen_tax_codes:
                add_error(
                    errors,
                    "3067",
                    "Existe en el mismo ítem más de un cac:TaxSubtotal con el mismo valor del Tag UBL cbc:ID",
                )
            seen_tax_codes.add(tax_code)

        # ERROR 3031: formato del monto base
        if taxable_text is not None and (taxable is None or taxable <= 0):
            add_error(
                errors,
                "3031",
                "El formato del Tag UBL cbc:TaxableAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 2033: formato del monto de tributo
        if tax_amount_text is not None and (tax_amount is None or tax_amount <= 0):
            add_error(
                errors,
                "2033",
                "El formato del Tag UBL cbc:TaxAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 2992: tasa del tributo (excepto 7152)
        if tax_code != "7152" and percent_text is None:
            add_error(
                errors,
                "2992",
                "No existe el Tag UBL cac:TaxCategory/cbc:Percent",
            )

        # ERROR 3102: formato de la tasa
        if percent_text is not None and not _is_decimal_3_5(percent_text):
            add_error(
                errors,
                "3102",
                "El formato del Tag UBL cbc:Percent es diferente de decimal positivo de 3 enteros y hasta 5 decimales y diferente de cero",
            )

        # ERROR 2371 / 3050: TaxExemptionReasonCode
        if tax_code not in {"2000", "9999"} and taxable is not None and taxable > 0:
            if exemption is None:
                add_error(
                    errors,
                    "2371",
                    "No existe el Tag UBL cbc:TaxExemptionReasonCode",
                )
        if tax_code in {"2000", "9999"} and exemption is not None:
            add_error(
                errors,
                "3050",
                "Afectación de IGV no corresponde al código de tributo de la linea",
            )

        # ERROR 2642: nota débito tipo 11 (exportación) requiere afectación 40
        if resp_code == "11" and taxable is not None and taxable > 0:
            if exemption != "40":
                add_error(
                    errors,
                    "2642",
                    "Operaciones de exportacion, deben consignar Tipo Afectacion igual a 40",
                )

        # ERROR 2644: nota débito tipo 12 (IVAP) requiere afectación 17
        if resp_code == "12" and taxable is not None and taxable > 0:
            if exemption != "17":
                add_error(
                    errors,
                    "2644",
                    "Comprobante operacion sujeta IVAP solo debe tener ítems con código de afectación del IGV igual a 17",
                )

        # ERROR 3110 / 3111: montos de tributo según tipo de operación
        if tax_code in {"9995", "9997", "9998"} and tax_amount is not None and tax_amount != 0:
            add_error(
                errors,
                "3110",
                "El monto de afectacion de IGV por linea debe ser igual a 0.00 para Exoneradas, Inafectas, Exportación",
            )
        if tax_code == "9996" and taxable is not None and taxable > Decimal("0.06"):
            if exemption in {"11", "12", "13", "14", "15", "16", "17"} and tax_amount == 0:
                add_error(
                    errors,
                    "3111",
                    "El monto de afectación de IGV por linea debe ser diferente a 0.00",
                )
        if tax_code in {"1000", "1016"} and taxable is not None and taxable > Decimal("0.06"):
            if tax_amount == 0:
                add_error(
                    errors,
                    "3111",
                    "El monto de afectación de IGV por linea debe ser diferente a 0.00",
                )

        # ERROR 3103: IGV/IVAP = percent * base / 100 (tolerancia 1)
        if tax_code in {"1000", "1016"} and taxable is not None and tax_amount is not None and percent is not None:
            expected = (taxable * percent) / Decimal("100")
            if not _within_tolerance(tax_amount, expected):
                add_error(
                    errors,
                    "3103",
                    "El producto del factor y monto base de la afectación del IGV/IVAP no corresponde al monto de afectacion de linea",
                )

        # ERROR 3108: ISC = percent * base / 100
        if tax_code == "2000" and taxable is not None and tax_amount is not None and percent is not None:
            expected = (taxable * percent) / Decimal("100")
            if not _within_tolerance(tax_amount, expected):
                add_error(
                    errors,
                    "3108",
                    "El producto del factor y monto base de la afectación del ISC no corresponde al monto de afectacion de linea",
                )

        # ERROR 3109: Otros tributos = percent * base / 100
        if tax_code == "9999" and taxable is not None and tax_amount is not None and percent is not None:
            expected = (taxable * percent) / Decimal("100")
            if not _within_tolerance(tax_amount, expected):
                add_error(
                    errors,
                    "3109",
                    "El producto del factor y monto base de la afectación de otros tributos no corresponde al monto de afectacion de linea",
                )

        # ERROR 3104: ISC percent no debe ser 0
        if tax_code == "2000" and taxable is not None and taxable > 0:
            if percent is not None and percent == 0:
                add_error(
                    errors,
                    "3104",
                    "El factor de afectación de ISC por linea debe ser diferente a 0.00",
                )

        # ERROR 2373 / 3210: TierRange solo para ISC
        if tax_code == "2000" and taxable is not None and taxable > 0:
            if tier_range is None:
                add_error(
                    errors,
                    "2373",
                    "Si existe monto de ISC en el ITEM debe especificar el sistema de calculo",
                )
        if tax_code != "2000" and tier_range is not None:
            add_error(
                errors,
                "3210",
                "Solo debe consignar sistema de calculo si el tributo es ISC",
            )

        # ERROR 2892 / 3237 / 3236 / 3238: ICBPER
        if tax_code == "7152":
            if base_unit is None:
                add_error(
                    errors,
                    "3237",
                    "Debe consignar el campo cac:TaxSubtotal/cbc:BaseUnitMeasure a nivel de ítem",
                )
            elif not _is_integer_up_to_5(base_unit):
                add_error(
                    errors,
                    "2892",
                    "El formato del Tag UBL cbc:BaseUnitMeasure es diferente de entero mayor o igual a cero, y de hasta 5 dígitos",
                )
            else:
                qty = _line_quantity(line)
                base_unit_val = parse_amount(base_unit) or Decimal("0")
                if base_unit_val > 0 and qty is not None and not _within_tolerance(base_unit_val, qty):
                    add_error(
                        errors,
                        "3236",
                        "El valor ingresado en el campo cac:TaxSubtotal/cbc:BaseUnitMeasure no corresponde al valor esperado",
                    )
            if per_unit is not None:
                if not _is_decimal_3_5(per_unit):
                    add_error(
                        errors,
                        "2892",
                        "El formato del Tag UBL cbc:PerUnitAmount es diferente de decimal positivo de 3 enteros y hasta 5 decimales y diferente de cero",
                    )
                base_unit_val = parse_amount(base_unit) or Decimal("0")
                per_unit_val = parse_amount(per_unit) or Decimal("0")
                if base_unit_val > 0 and per_unit_val == 0:
                    add_error(
                        errors,
                        "3238",
                        "El valor ingresado en el campo cac:TaxSubtotal/cbc:PerUnitAmount del ítem no corresponde al valor esperado",
                    )

        # ERROR 3272: monto base vs valor de venta por ítem
        if _ref_type(root) == "01" and taxable is not None:
            if tax_code == "2000" and taxable > 0:
                if line_ext is not None and tax_amount is not None:
                    expected = line_ext + tax_amount
                    if not _within_tolerance(taxable, expected):
                        add_error(
                            errors,
                            "3272",
                            "La base imponible a nivel de línea difiere de la información consignada en el comprobante",
                        )
            elif tax_code in {"1000", "1016", "9995", "9996", "9997", "9998"} and taxable > 0:
                if line_ext is not None and not _within_tolerance(taxable, line_ext):
                    add_error(
                        errors,
                        "3272",
                        "La base imponible a nivel de línea difiere de la información consignada en el comprobante",
                    )

        # ERROR 2993: tasa 0 para gratuitas y gravadas
        if tax_code == "9996" and taxable is not None and taxable > 0:
            if exemption in {"11", "12", "13", "14", "15", "16", "17"} and percent is not None and percent == 0:
                add_error(
                    errors,
                    "2993",
                    "El factor de afectación de IGV por linea debe ser diferente a 0.00",
                )
        if tax_code in {"1000", "1016"} and taxable is not None and taxable > 0:
            if percent is not None and percent == 0:
                add_error(
                    errors,
                    "2993",
                    "El factor de afectación de IGV por linea debe ser diferente a 0.00",
                )

        # ERROR 3105: al menos un tributo de afectación IGV/IVAP con base > 0
        if tax_code in {"1000", "1016", "9995", "9996", "9997", "9998"} and taxable is not None and taxable > 0:
            has_base_igv_ivap = True

    # ERROR 3105
    if not has_base_igv_ivap:
        add_error(
            errors,
            "3105",
            "El XML debe contener al menos un tributo por linea de afectacion por IGV",
        )

    # ERROR 3223: combinaciones permitidas de tributos con base > 0
    codes_with_base = set()
    for ts in tax_subtotals:
        code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
        base = parse_amount(text(ts, "cbc:TaxableAmount", NS_DEBIT_NOTE))
        if base is not None and base > 0 and code is not None:
            codes_with_base.add(code)
    if codes_with_base:
        allowed = [
            {"1000", "2000", "9999"},
            {"1016", "9999"},
            {"9995", "9999"},
            {"9996", "2000", "9999"},
            {"9997", "2000", "9999"},
            {"9998", "2000", "9999"},
        ]
        if not any(codes_with_base <= combo for combo in allowed):
            add_error(
                errors,
                "3223",
                "La combinación de tributos no es permitida",
            )


# ---------------------------------------------------------------------------
# Impuestos globales
# ---------------------------------------------------------------------------

def _validate_global_taxes(
    root: etree._Element,
    errors: list[ValidationError],
    ref_type: str | None,
    resp_code: str | None,
) -> None:
    tax_totals = all_(root, "cac:TaxTotal", NS_DEBIT_NOTE)

    # ERROR 2956 / 3020: TaxTotal global
    if not tax_totals:
        add_error(
            errors,
            "2956",
            "No existe el tag /DebitNote/cac:TaxTotal",
        )
    else:
        global_tax_text = text(root, "cac:TaxTotal/cbc:TaxAmount", NS_DEBIT_NOTE)
        global_tax = parse_amount(global_tax_text)
        if global_tax_text is not None and (global_tax is None or global_tax <= 0):
            add_error(
                errors,
                "3020",
                "El formato del Tag UBL cac:TaxTotal/cbc:TaxAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

    # ERROR 3024: más de un TaxTotal global
    if len(tax_totals) > 1:
        add_error(
            errors,
            "3024",
            "Existe a nivel global más de un tag cac:TaxTotal",
        )

    seen_global_codes: set[str] = set()

    for ts in _global_tax_subtotals(root):
        tax_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
        tax_name = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name", NS_DEBIT_NOTE)
        tax_type_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode", NS_DEBIT_NOTE)
        taxable_text = text(ts, "cbc:TaxableAmount", NS_DEBIT_NOTE)
        taxable = parse_amount(taxable_text)
        tax_amount_text = text(ts, "cbc:TaxAmount", NS_DEBIT_NOTE)
        tax_amount = parse_amount(tax_amount_text)

        # ERROR 3059: código de tributo global
        if tax_code is None or tax_code == "":
            add_error(
                errors,
                "3059",
                "No existe el Tag UBL cac:TaxCategory/cac:TaxScheme/cbc:ID",
            )

        # ERROR 2054: nombre de tributo global
        if tax_name is None or tax_name == "":
            add_error(
                errors,
                "2054",
                "No existe el Tag UBL TaxScheme Name de impuestos globales",
            )

        # ERROR 2052: código internacional de tributo global
        if tax_type_code is None or tax_type_code == "":
            add_error(
                errors,
                "2052",
                "No existe el Tag UBL código de tributo internacional de impuestos globales",
            )

        # ERROR 3068: código de tributo global repetido
        if tax_code is not None:
            if tax_code in seen_global_codes:
                add_error(
                    errors,
                    "3068",
                    "Existe a nivel global más de un cac:TaxSubtotal con el mismo valor del Tag UBL cbc:ID",
                )
            seen_global_codes.add(tax_code)

        # ERROR 3003 / 2999: TaxableAmount global
        if tax_code != "7152":
            if taxable_text is None:
                add_error(
                    errors,
                    "3003",
                    "No existe el Tag UBL cbc:TaxableAmount de total valor de venta globales",
                )
            elif taxable is None or taxable <= 0:
                add_error(
                    errors,
                    "2999",
                    "El formato del Tag UBL cbc:TaxableAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
                )

        # ERROR 2048: TaxAmount global
        if tax_amount_text is not None and (tax_amount is None or tax_amount <= 0):
            add_error(
                errors,
                "2048",
                "El formato del Tag UBL cac:TaxSubtotal/cbc:TaxAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 3000: TaxAmount debe ser 0 para exoneradas/inafectas/exportación
        if tax_code in {"9995", "9997", "9998"} and tax_amount is not None and tax_amount != 0:
            add_error(
                errors,
                "3000",
                "El monto total del impuestos sobre el valor de venta de operaciones gratuitas/inafectas/exoneradas debe ser igual a 0.00",
            )

        # ERROR 2949: ICBPER antes de 2019-08-01
        if tax_code == "7152" and tax_amount is not None and tax_amount > 0:
            issue_date = _issue_date(root)
            if issue_date is not None and issue_date < "2019-08-01":
                add_error(
                    errors,
                    "2949",
                    "El impuesto ICBPER no se encuentra vigente",
                )

        # ERROR 3107: exportación / IVAP no debe tener ciertos tributos globales
        if resp_code == "12" and tax_code == "1000" and taxable is not None and taxable > 0:
            add_error(
                errors,
                "3107",
                "El dato ingresado como codigo de tributo global es invalido para tipo de operación",
            )
        if resp_code == "11" and tax_code in {"1000", "1016"} and taxable is not None and taxable > 0:
            add_error(
                errors,
                "3107",
                "El dato ingresado como codigo de tributo global es invalido para tipo de operación",
            )
        if resp_code == "11" and tax_code in {"2000", "9999"}:
            add_error(
                errors,
                "3107",
                "El dato ingresado como codigo de tributo global es invalido para tipo de operación",
            )

        # Cuadres globales solo para notas de débito que modifican facturas (01)
        if ref_type == "01" and tax_code is not None:
            # ERROR 3273 / 3274 / 3275 / 3276: total valor de venta por tipo
            if tax_code == "9995":
                expected = _sum_line_extensions_by_tax(root, "9995")
                if taxable is not None and not _within_tolerance(taxable, expected):
                    add_error(
                        errors,
                        "3273",
                        "La sumatoria del total valor de venta - Exportaciones de línea no corresponden al total",
                    )
            elif tax_code == "9997":
                expected = _sum_line_extensions_by_tax(root, "9997")
                if taxable is not None and not _within_tolerance(taxable, expected):
                    add_error(
                        errors,
                        "3275",
                        "La sumatoria del total valor de venta - operaciones exoneradas de línea no corresponden al total",
                    )
            elif tax_code == "9998":
                expected = _sum_line_extensions_by_tax(root, "9998")
                if taxable is not None and not _within_tolerance(taxable, expected):
                    add_error(
                        errors,
                        "3274",
                        "La sumatoria del total valor de venta - operaciones inafectas de línea no corresponden al total",
                    )
            elif tax_code == "9996":
                expected = _sum_line_extensions_by_tax(root, "9996")
                if taxable is not None and not _within_tolerance(taxable, expected):
                    add_error(
                        errors,
                        "3276",
                        "La sumatoria del total valor de venta - operaciones gratuitas de línea no corresponden al total",
                    )
                # ERROR 2641: si hay línea gratuita con precio referencial > 0, el total debe ser > 0
                if expected == 0 and _has_gratuita_reference_price(root):
                    add_error(
                        errors,
                        "2641",
                        "Operacion gratuita, debe consignar Total valor venta - operaciones gratuitas mayor a cero",
                    )
                # ERROR 3302: TaxAmount global 9996 = suma de IGV de líneas gratuitas
                expected_tax = _sum_gratuita_igv(root)
                if tax_amount is not None and not _within_tolerance(tax_amount, expected_tax):
                    add_error(
                        errors,
                        "3302",
                        "La sumatoria de los IGV de operaciones gratuitas de la línea no corresponden al total",
                    )
            elif tax_code == "1000":
                # ERROR 3277: total valor venta gravadas
                expected = _sum_line_extensions_by_tax(root, "1000")
                if taxable is not None and not _within_tolerance(taxable, expected):
                    add_error(
                        errors,
                        "3277",
                        "La sumatoria del total valor de venta - operaciones gravadas de línea no corresponden al total",
                    )
                # ERROR 3291: IGV global = sum(base)*percent
                igv_bases = _sum_line_tax_bases(root, "1000")
                line_percent = _first_line_percent(root, "1000")
                if line_percent is not None and tax_amount is not None:
                    expected_tax = (igv_bases * line_percent) / Decimal("100")
                    if not _within_tolerance(tax_amount, expected_tax):
                        add_error(
                            errors,
                            "3291",
                            "El cálculo del IGV es Incorrecto",
                        )
            elif tax_code == "1016":
                # ERROR 3293: total valor venta IVAP
                expected = _sum_line_extensions_by_tax(root, "1016")
                if taxable is not None and not _within_tolerance(taxable, expected):
                    add_error(
                        errors,
                        "3293",
                        "La sumatoria del total valor de venta - IVAP de línea no corresponden al total",
                    )
                # ERROR 3295: IVAP global = sum(base)*percent
                ivap_bases = _sum_line_tax_bases(root, "1016")
                line_percent = _first_line_percent(root, "1016")
                if line_percent is not None and tax_amount is not None:
                    expected_tax = (ivap_bases * line_percent) / Decimal("100")
                    if not _within_tolerance(tax_amount, expected_tax):
                        add_error(
                            errors,
                            "3295",
                            "El importe del IVAP no corresponden al determinado por la informacion consignada",
                        )
            elif tax_code == "2000":
                # ERROR 3296: base ISC global
                expected_base = _sum_line_tax_bases(root, "2000")
                if taxable is not None and not _within_tolerance(taxable, expected_base):
                    add_error(
                        errors,
                        "3296",
                        "La sumatoria del monto base - ISC de línea no corresponden al total",
                    )
                # ERROR 3298: ISC global
                expected_tax = _sum_line_tax_amounts(root, "2000")
                if tax_amount is not None and not _within_tolerance(tax_amount, expected_tax):
                    add_error(
                        errors,
                        "3298",
                        "La sumatoria del total del importe del tributo ISC de línea no corresponden al total",
                    )
            elif tax_code == "9999":
                # ERROR 3297: base otros tributos global
                expected_base = _sum_line_tax_bases(root, "9999")
                if taxable is not None and not _within_tolerance(taxable, expected_base):
                    add_error(
                        errors,
                        "3297",
                        "La sumatoria del monto base - Otros tributos de línea no corresponden al total",
                    )
                # ERROR 3299: otros tributos global
                expected_tax = _sum_line_tax_amounts(root, "9999")
                if tax_amount is not None and not _within_tolerance(tax_amount, expected_tax):
                    add_error(
                        errors,
                        "3299",
                        "La sumatoria del total del importe del tributo Otros tributos de línea no corresponden al total",
                    )
            # 3306 se valida fuera del bloque ref_type

        # ERROR 3294: TaxTotal global = sumatoria de tributos por línea
        if ref_type == "01" and tax_code in {"1000", "1016", "2000", "7152", "9999"}:
            expected = _sum_line_tax_amounts(root, tax_code)
            if tax_amount is not None and not _within_tolerance(tax_amount, expected):
                add_error(
                    errors,
                    "3294",
                    "La sumatoria de impuestos globales no corresponde al monto total de impuestos",
                )

    # ERROR 3294 (global TaxTotal/cbc:TaxAmount vs líneas)
    if ref_type == "01":
        global_tax_total = _global_tax_total_amount(root)
        line_tax_sum = Decimal("0")
        for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
            line_tax = _line_tax_total_amount(line)
            if line_tax is not None:
                line_tax_sum += line_tax
        if global_tax_total is not None and not _within_tolerance(global_tax_total, line_tax_sum):
            add_error(
                errors,
                "3294",
                "El valor del Tag UBL cac:TaxTotal/cbc:TaxAmount es diferente a la sumatoria de 'Monto de tributo por línea'",
            )

    # ERROR 3306: ICBPER global vs líneas
    icbper_global = None
    for ts in _global_tax_subtotals(root):
        if text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE) == "7152":
            icbper_global = parse_amount(text(ts, "cbc:TaxAmount", NS_DEBIT_NOTE))
            break
    if icbper_global is not None:
        expected_tax = _sum_line_tax_amounts(root, "7152")
        if not _within_tolerance(icbper_global, expected_tax):
            add_error(
                errors,
                "3306",
                "La sumatoria del total del importe del tributo ICBPER de línea no corresponden al total",
            )

        # ERROR 3294: TaxTotal global = sumatoria de tributos por línea
        if ref_type == "01" and tax_code in {"1000", "1016", "2000", "7152", "9999"}:
            expected = _sum_line_tax_amounts(root, tax_code)
            if tax_amount is not None and not _within_tolerance(tax_amount, expected):
                add_error(
                    errors,
                    "3294",
                    "La sumatoria de impuestos globales no corresponde al monto total de impuestos",
                )

    # ERROR 2638: si existe línea con base > 0 de ciertos tributos, debe existir total global
    for tax_code in {"1000", "1016", "9995", "9996", "9997", "9998"}:
        if _has_line_with_tax(root, tax_code) and _find_global_tax_subtotal(root, tax_code) is None:
            add_error(
                errors,
                "2638",
                "Si tiene operaciones de un tributo en alguna línea, debe consignar el tag del total del tributo",
            )


# ---------------------------------------------------------------------------
# Totales globales
# ---------------------------------------------------------------------------

def _validate_totals(root: etree._Element, errors: list[ValidationError], ref_type: str | None) -> None:
    # ERROR 2064: ChargeTotalAmount formato
    charge_total_text = text(root, "cac:RequestedMonetaryTotal/cbc:ChargeTotalAmount", NS_DEBIT_NOTE)
    if charge_total_text is not None:
        charge_total = parse_amount(charge_total_text)
        if charge_total is None or charge_total <= 0:
            add_error(
                errors,
                "2064",
                "El formato del Tag UBL cbc:ChargeTotalAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

    # ERROR 3019: TaxInclusiveAmount formato
    tax_inclusive_text = text(root, "cac:RequestedMonetaryTotal/cbc:TaxInclusiveAmount", NS_DEBIT_NOTE)
    if tax_inclusive_text is not None:
        tax_inclusive = parse_amount(tax_inclusive_text)
        if tax_inclusive is None or tax_inclusive <= 0:
            add_error(
                errors,
                "3019",
                "El formato del Tag UBL cbc:TaxInclusiveAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )
        # ERROR 3279: TaxInclusiveAmount cuadre (simplificado)
        if ref_type == "01" and tax_inclusive is not None:
            expected = _calculate_tax_inclusive(root)
            if not _within_tolerance(tax_inclusive, expected):
                add_error(
                    errors,
                    "3279",
                    "El valor del Tag UBL cbc:TaxInclusiveAmount difiere de la sumatoria de totales",
                )

    # ERROR 3278: LineExtensionAmount cuadre
    line_ext_text = text(root, "cac:RequestedMonetaryTotal/cbc:LineExtensionAmount", NS_DEBIT_NOTE)
    if line_ext_text is not None:
        line_ext = parse_amount(line_ext_text)
        if line_ext is None or line_ext <= 0:
            add_error(
                errors,
                "2370",  # código de formato similar
                "El formato del Tag UBL cbc:LineExtensionAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )
        elif ref_type == "01":
            expected = _sum_line_extensions_by_tax(root, "1000")
            expected += _sum_line_extensions_by_tax(root, "1016")
            expected += _sum_line_extensions_by_tax(root, "9995")
            expected += _sum_line_extensions_by_tax(root, "9997")
            expected += _sum_line_extensions_by_tax(root, "9998")
            if not _within_tolerance(line_ext, expected):
                add_error(
                    errors,
                    "3278",
                    "El valor del Tag UBL cbc:LineExtensionAmount es diferente de la sumatoria del 'Valor de venta por ítem'",
                )

    # ERROR 3280: PayableAmount cuadre
    payable_text = text(root, "cac:RequestedMonetaryTotal/cbc:PayableAmount", NS_DEBIT_NOTE)
    payable = parse_amount(payable_text)
    if payable_text is not None and (payable is None or payable <= 0):
        add_error(
            errors,
            "2062",
            "El formato del Tag UBL cbc:PayableAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
        )
    if ref_type == "01" and payable is not None:
        expected = _calculate_payable(root)
        if not _within_tolerance(payable, expected):
            add_error(
                errors,
                "3280",
                "El importe total del comprobante no coincide con el valor calculado",
            )

    # ERROR 3303: PayableRoundingAmount absoluto mayor a 1
    rounding = _global_rounding(root)
    if rounding is not None and abs(rounding) > 1:
        add_error(
            errors,
            "3303",
            "El monto para el redondeo del Importe Total excede el valor permitido",
        )


def _calculate_tax_inclusive(root: etree._Element) -> Decimal:
    total = Decimal("0")
    for tax_code in {"1000", "1016", "9995", "9996", "9997", "9998"}:
        ts = _find_global_tax_subtotal(root, tax_code)
        if ts is not None:
            total += parse_amount(text(ts, "cbc:TaxableAmount", NS_DEBIT_NOTE)) or Decimal("0")
    for tax_code in {"2000", "9999", "7152"}:
        ts = _find_global_tax_subtotal(root, tax_code)
        if ts is not None:
            total += parse_amount(text(ts, "cbc:TaxAmount", NS_DEBIT_NOTE)) or Decimal("0")
    return total


def _calculate_payable(root: etree._Element) -> Decimal:
    total = Decimal("0")
    for tax_code in {"1000", "1016", "9995", "9996", "9997", "9998"}:
        ts = _find_global_tax_subtotal(root, tax_code)
        if ts is not None:
            total += parse_amount(text(ts, "cbc:TaxableAmount", NS_DEBIT_NOTE)) or Decimal("0")
    for tax_code in {"1000", "1016", "2000", "9999", "7152"}:
        ts = _find_global_tax_subtotal(root, tax_code)
        if ts is not None:
            total += parse_amount(text(ts, "cbc:TaxAmount", NS_DEBIT_NOTE)) or Decimal("0")
    charge = _global_charge_total(root)
    if charge is not None:
        total += charge
    rounding = _global_rounding(root)
    if rounding is not None:
        total += rounding
    return total


def _first_line_percent(root: etree._Element, tax_code: str) -> Decimal | None:
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        for ts in _line_tax_subtotals(line):
            code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
            if code == tax_code:
                return parse_amount(text(ts, "cac:TaxCategory/cbc:Percent", NS_DEBIT_NOTE))
    return None


def _has_gratuita_reference_price(root: etree._Element) -> bool:
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        for ts in _line_tax_subtotals(line):
            code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
            base = parse_amount(text(ts, "cbc:TaxableAmount", NS_DEBIT_NOTE))
            if code == "9996" and base is not None and base > 0:
                ref = _line_reference_price_amount(line, "02")
                if ref is not None and ref > 0:
                    return True
    return False


def _sum_gratuita_igv(root: etree._Element) -> Decimal:
    total = Decimal("0")
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        has_gratuita = False
        for ts in _line_tax_subtotals(line):
            code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
            base = parse_amount(text(ts, "cbc:TaxableAmount", NS_DEBIT_NOTE))
            if code == "9996" and base is not None and base > 0:
                has_gratuita = True
                break
        if has_gratuita:
            for ts in _line_tax_subtotals(line):
                code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
                if code in {"1000", "1016"}:
                    amount = parse_amount(text(ts, "cbc:TaxAmount", NS_DEBIT_NOTE))
                    if amount is not None:
                        total += amount
    return total


# ---------------------------------------------------------------------------
# Notas / leyendas
# ---------------------------------------------------------------------------

def _validate_notes(root: etree._Element, errors: list[ValidationError]) -> None:
    # ERROR 3006: formato de la descripción de la leyenda
    for note in all_(root, "cbc:Note", NS_DEBIT_NOTE):
        note_text = (note.text or "").strip()
        if note_text and len(note_text) > 200:
            add_error(
                errors,
                "3006",
                "El formato del Tag UBL cbc:Note es diferente a alfanumérico de 1 a 200 caracteres",
            )


# ---------------------------------------------------------------------------
# Términos de pago (detracción)
# ---------------------------------------------------------------------------

def _validate_payment_terms(root: etree._Element, errors: list[ValidationError]) -> None:
    payment_terms = all_(root, "cac:PaymentTerms", NS_DEBIT_NOTE)
    payment_means = all_(root, "cac:PaymentMeans", NS_DEBIT_NOTE)
    pt_ids = {text(pt, "cbc:ID", NS_DEBIT_NOTE) for pt in payment_terms}
    pm_ids = {text(pm, "cbc:ID", NS_DEBIT_NOTE) for pm in payment_means}

    # 3313 / 3314 ya se validan en validator.py; se mantienen aquí por completitud
    if "Detraccion" in pt_ids and "Detraccion" not in pm_ids:
        add_error(
            errors,
            "3313",
            "Si existe 'Indicador PaymentTerms' igual a 'Detraccion', debe existir un 'Indicador PaymentMeans' igual a 'Detraccion'",
        )
    if "Detraccion" in pm_ids and "Detraccion" not in pt_ids:
        add_error(
            errors,
            "3314",
            "Si existe 'Indicador PaymentMeans' igual a 'Detraccion', debe existir un 'Indicador PaymentTerms' igual a 'Detraccion'",
        )

    for pt in payment_terms:
        pt_id = text(pt, "cbc:ID", NS_DEBIT_NOTE)
        if pt_id != "Detraccion":
            continue

        # ERROR 3127: código de bien o servicio
        means_id = text(pt, "cbc:PaymentMeansID", NS_DEBIT_NOTE)
        if means_id is None or means_id == "":
            add_error(
                errors,
                "3127",
                "Si 'Indicador PaymentTerms' es igual a 'Detraccion', no existe el tag o es vacío",
            )

        # ERROR 3035 / 3037: monto de detracción
        amount_text = text(pt, "cbc:Amount", NS_DEBIT_NOTE)
        if amount_text is None:
            add_error(
                errors,
                "3035",
                "Si 'Indicador PaymentTerms' es igual a 'Detraccion', no existe el Tag UBL",
            )
        else:
            amount = parse_amount(amount_text)
            if amount is None or amount <= 0:
                add_error(
                    errors,
                    "3037",
                    "El formato del Tag UBL cbc:Amount es diferente de decimal positivo de 12 enteros y hasta 2 decimales",
                )

        # ERROR 3208: currencyID de la detracción debe ser PEN
        amount_elem = pt.find("cbc:Amount", namespaces=NS_DEBIT_NOTE)
        if amount_elem is not None:
            curr = amount_elem.get("currencyID")
            if curr is not None and curr != "PEN":
                add_error(
                    errors,
                    "3208",
                    "La moneda del monto de la detracción debe ser PEN",
                )

    for pm in payment_means:
        pm_id = text(pm, "cbc:ID", NS_DEBIT_NOTE)
        if pm_id != "Detraccion":
            continue

        # ERROR 3034: número de cuenta
        account = text(pm, "cac:PayeeFinancialAccount/cbc:ID", NS_DEBIT_NOTE)
        if account is None or account == "":
            add_error(
                errors,
                "3034",
                "Si 'Indicador PaymentMeans' es igual a 'Detraccion', no existe el Tag UBL o es vacío",
            )

    # ERROR 3093: si forma de pago es Contado debe existir cargo 51/52/53
    for pt in payment_terms:
        pt_id = text(pt, "cbc:ID", NS_DEBIT_NOTE)
        means_id = text(pt, "cbc:PaymentMeansID", NS_DEBIT_NOTE)
        if pt_id == "FormaPago" and means_id == "Contado":
            has_perception = any(
                text(ac, "cbc:AllowanceChargeReasonCode", NS_DEBIT_NOTE) in {"51", "52", "53"}
                for ac in all_(root, "cac:AllowanceCharge", NS_DEBIT_NOTE)
            )
            if not has_perception:
                add_error(
                    errors,
                    "3093",
                    "Si 'Forma de pago' es 'Contado', no existe un 'Código de motivo de cargo/descuento' igual a '51', '52' o '53'",
                )


# ---------------------------------------------------------------------------
# Cargos / descuentos globales y por ítem
# ---------------------------------------------------------------------------

def _validate_allowance_charges(root: etree._Element, errors: list[ValidationError]) -> None:
    # Globales
    for ac in all_(root, "cac:AllowanceCharge", NS_DEBIT_NOTE):
        _validate_allowance_charge(ac, errors, global_level=True)

    # Por ítem
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        for ac in all_(line, "cac:AllowanceCharge", NS_DEBIT_NOTE):
            _validate_allowance_charge(ac, errors, global_level=False)


def _validate_allowance_charge(
    ac: etree._Element, errors: list[ValidationError], global_level: bool
) -> None:
    indicator = text(ac, "cbc:ChargeIndicator", NS_DEBIT_NOTE)
    reason_code = text(ac, "cbc:AllowanceChargeReasonCode", NS_DEBIT_NOTE)
    factor_text = text(ac, "cbc:MultiplierFactorNumeric", NS_DEBIT_NOTE)
    amount_text = text(ac, "cbc:Amount", NS_DEBIT_NOTE)
    base_text = text(ac, "cbc:BaseAmount", NS_DEBIT_NOTE)
    amount: Decimal | None = None

    # ERROR 3072 / 3073: código de motivo obligatorio si existe indicador
    if indicator is not None and (reason_code is None or reason_code == ""):
        code = "3073" if not global_level else "3072"
        add_error(
            errors,
            code,
            "Si existe 'Indicador de cargo/descuento', no existe el Tag UBL cbc:AllowanceChargeReasonCode o es vacío",
        )

    # ERROR 3114: indicador correcto según código de motivo
    if reason_code is not None and indicator is not None:
        cargo_codes = {"45", "46", "49", "50", "51", "52", "53"}
        descuento_codes = {"00", "01", "02", "03", "04", "05", "06", "20"}
        if reason_code in cargo_codes and indicator != "true":
            add_error(
                errors,
                "3114",
                "El indicador de cargo debe ser 'true'",
            )
        if reason_code in descuento_codes and indicator != "false":
            add_error(
                errors,
                "3114",
                "El indicador de descuento debe ser 'false'",
            )

    # ERROR 3025 / 3052: formato del factor
    if factor_text is not None and not _is_decimal_3_5(factor_text):
        code = "3052" if not global_level else "3025"
        add_error(
            errors,
            code,
            "El formato del Tag UBL cbc:MultiplierFactorNumeric es diferente de decimal positivo de 3 enteros y hasta 5 decimales y diferente de cero",
        )

    # ERROR 3016 / 3053 / 3092 / 3074: monto y base
    if amount_text is not None:
        amount = parse_amount(amount_text)
        if (global_level and (amount is None or amount <= 0)) or (not global_level and amount is not None and amount <= 0):
            add_error(
                errors,
                "3016",
                "El formato del Tag UBL cbc:Amount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )
        if reason_code == "45" and amount is not None and amount == 0:
            add_error(
                errors,
                "3074",
                "El monto del cargo para FISE debe ser mayor a 0.00",
            )
    if reason_code == "45" and (base_text is None or parse_amount(base_text) is None or parse_amount(base_text) <= 0):
        add_error(
            errors,
            "3092",
            "Para cargo/descuento FISE, debe ingresar monto base y debe ser mayor a 0.00",
        )
    if base_text is not None:
        base = parse_amount(base_text)
        if base is None or base <= 0:
            code = "3053" if not global_level else "3016"
            add_error(
                errors,
                code,
                "El formato del Tag UBL cbc:BaseAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

    # ERROR 3282: descuentos por anticipos (04,05,06,20) requieren PrepaidAmount > 0
    if reason_code in {"04", "05", "06", "20"} and amount is not None and amount > 0:
        prepaid = _global_prepaid(root_of(ac))
        if prepaid is None or prepaid <= 0:
            add_error(
                errors,
                "3282",
                "Si existe descuento por anticipo, el 'Total de anticipos' debe ser mayor a cero",
            )


def root_of(elem: etree._Element) -> etree._Element:
    while elem.getparent() is not None:
        elem = elem.getparent()
    return elem


def _validate_additional_item_properties(root: etree._Element, errors: list[ValidationError]) -> None:
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", NS_DEBIT_NOTE):
            code = text(prop, "cbc:NameCode", NS_DEBIT_NOTE)
            value = text(prop, "cbc:Value", NS_DEBIT_NOTE)

            # ERROR 3065: fechas de vigencia según concepto
            if code in {"3059", "3005", "4002", "4003", "4004", "4006", "4048"}:
                if not exists(prop, "cac:UsabilityPeriod/cbc:StartDate", NS_DEBIT_NOTE):
                    add_error(
                        errors,
                        "3065",
                        f"De existir 'Código del concepto' igual a '{code}', no existe el tag cac:UsabilityPeriod/cbc:StartDate",
                    )

            # ERROR 3243: fecha de inicio para concepto 7014
            if code == "7014":
                if not exists(prop, "cac:UsabilityPeriod/cbc:StartDate", NS_DEBIT_NOTE):
                    add_error(
                        errors,
                        "3243",
                        "De existir 'Código del concepto' igual a '7014', no existe el tag cac:UsabilityPeriod/cbc:StartDate",
                    )


# ---------------------------------------------------------------------------
# Reglas documentadas como fuera de alcance para DebitNote
# ---------------------------------------------------------------------------

# FUERA DE ALCANCE:
# 1079, 2108 - requieren la fecha de recepción del XML por SUNAT.
# 3014 - texto de la regla incompleto ("El valor del atributo se repite"); no
#        se dispone del atributo evaluado en rules_DebitNote.txt.
# 3098 - depende de 'Tipo de operación' 0201/0208 y tag Delivery que no están
#        en el esquema de DebitNote generado por openUBL.
# 3106 - código no encontrado en rules_DebitNote.txt ni en rules_Invoice.txt;
#        sin definición aplicable.
# 3112, 3113, 3115, 3116, 3117, 3118, 3119, 3120, 3121 - detalles de
#        exportación / minería / carta de porte / viajes, propios de Invoice y
#        no aplicables a DebitNote en este contexto.
