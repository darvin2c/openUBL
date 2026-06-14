"""Validaciones SUNAT adicionales para facturas (Invoice) - lote 1.

Códigos cubiertos: 1004, 2014, 2017, 2023, 2024, 2025, 2026, 2027, 2028,
2031, 2033, 2037, 2048, 2052, 2054, 2064, 2065, 2068, 2108, 2367, 2369,
2370, 2371, 2373, 2409, 2416, 2503, 2509, 2521, 2638, 2640, 2641, 2642,
2644, 2650, 2752, 2797, 2801, 2802, 2883, 2892, 2898, 2899, 2936, 2949,
2955, 2956, 2968, 2992, 2993, 2996, 2999, 3000, 3003, 3006, 3014, 3016,
3019, 3020, 3021, 3024, 3025, 3026, 3030, 3031, 3034, 3035, 3037, 3050,
3052, 3053, 3059, 3063, 3065, 3067, 3068, 3072, 3073, 3074, 3089, 3090.
"""

from lxml import etree
from decimal import Decimal

from openubl.validators.common import (
    ValidationError,
    add_error,
    all_,
    attr,
    exists,
    matches,
    parse_amount,
    text,
    NS_INVOICE,
    CATALOG03,
    CATALOG07,
)


_EXPORT_OPERATIONS = {"0200", "0201", "0202", "0203", "0204", "0205", "0206", "0207", "0208"}
_DETRACTION_OPERATIONS = {"1001", "1002", "1003", "1004"}

def validate_invoice_extra1(root: etree._Element, errors: list[ValidationError]) -> None:
    ns = NS_INVOICE

    _validate_header(root, ns, errors)
    _validate_parties(root, ns, errors)
    _validate_lines(root, ns, errors)
    _validate_global_taxes(root, ns, errors)
    _validate_monetary_total(root, ns, errors)
    _validate_global_allowance_charges(root, ns, errors)
    _validate_line_allowance_charges(root, ns, errors)
    _validate_payment_terms_and_means(root, ns, errors)
    _validate_prepaid_payments(root, ns, errors)
    _validate_notes(root, ns, errors)
    _validate_additional_item_properties(root, ns, errors)
    _validate_registration_address(root, ns, errors)


def _validate_header(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    # ERROR 1004: InvoiceTypeCode obligatorio
    invoice_type_code = text(root, "cbc:InvoiceTypeCode", ns)
    if invoice_type_code is None:
        add_error(errors, "1004", "No existe el Tag UBL cbc:InvoiceTypeCode o es vacío")

    # ERROR 2108: fuera de alcance - requiere fecha de recepción del XML por SUNAT.
    # FUERA DE ALCANCE - requiere fecha de recepción del XML.


def _validate_parties(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    # ERROR 3089: más de un PartyIdentification del emisor
    supplier_ids = all_(
        root,
        "cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification",
        ns,
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
        ns,
    )
    if len(customer_ids) > 1:
        add_error(
            errors,
            "3090",
            "Existe más de un Tag UBL cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification",
        )

    # ERROR 2014: número de documento del receptor existe
    customer_id_elem = root.find(
        "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID", namespaces=ns
    )
    if customer_id_elem is None:
        add_error(
            errors,
            "2014",
            "No existe el Tag UBL cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
        )
        return

    customer_id = (customer_id_elem.text or "").strip() or None
    scheme = customer_id_elem.get("schemeID")

    # ERROR 2017: si tipo documento es 6, debe ser numérico de 11 dígitos
    if scheme == "6" and not matches(customer_id, r"^\d{11}$"):
        add_error(
            errors,
            "2017",
            "Si 'Tipo de documento del adquiriente o usuario' es '6', el formato del Tag UBL es diferente a numérico de 11 dígitos",
        )

    # ERROR 2801: si tipo documento es 1, debe ser numérico de 8 dígitos
    if scheme == "1" and not matches(customer_id, r"^\d{8}$"):
        add_error(
            errors,
            "2801",
            "Si el 'Tipo de documento de identidad del adquiriente o usuario' es '1', el formato del Tag UBL es diferente de numérico de 8 dígitos",
        )

    # ERROR 2802: si tipo documento es 4/7/0/A/B/C/D/E/G, alfanumérico hasta 15 sin espacios
    if scheme in {"4", "7", "0", "A", "B", "C", "D", "E", "G"}:
        if not matches(customer_id, r"^[A-Za-z0-9]{1,15}$"):
            add_error(
                errors,
                "2802",
                "Si 'Tipo de documento del adquiriente o usuario' es '4', '7', '0', 'A', 'B', 'C', 'D', 'E' o 'G', el formato del Tag UBL es diferente a alfanumérico de hasta 15 caracteres",
            )


def _validate_lines(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    lines = all_(root, "cac:InvoiceLine", ns)
    seen_line_ids: set[str] = set()

    for line in lines:
        line_id = text(line, "cbc:ID", ns)

        # ERROR 2023: formato de ID de línea
        if line_id is None or not matches(line_id, r"^\d{1,3}$") or line_id == "0":
            add_error(
                errors,
                "2023",
                "El formato del Tag UBL cac:InvoiceLine/cbc:ID es diferente de numérico de hasta 3 dígitos; o es igual cero",
            )
        else:
            # ERROR 2752: ID de línea repetido
            if line_id in seen_line_ids:
                add_error(
                    errors,
                    "2752",
                    "Existe otro cac:InvoiceLine con el mismo valor del Tag UBL cbc:ID",
                )
            seen_line_ids.add(line_id)

        # ERROR 2883: InvoicedQuantity@unitCode existe
        qty_elem = line.find("cbc:InvoicedQuantity", namespaces=ns)
        if qty_elem is not None:
            unit_code = qty_elem.get("unitCode")
            if unit_code is None or unit_code == "":
                add_error(
                    errors,
                    "2883",
                    "No existe el atributo cbc:InvoicedQuantity@unitCode o es vacío",
                )
            else:
                # ERROR 2936: unitCode en catálogo 03
                if unit_code not in CATALOG03:
                    add_error(
                        errors,
                        "2936",
                        "El valor del atributo cbc:InvoicedQuantity@unitCode es diferente al Catálogo N.° 03",
                    )

        # ERROR 2024: InvoicedQuantity existe y no es cero
        qty_text = text(line, "cbc:InvoicedQuantity", ns)
        if qty_text is None:
            add_error(
                errors,
                "2024",
                "No existe el Tag UBL cac:InvoiceLine/cbc:InvoicedQuantity o es cero (0)",
            )
        else:
            qty_val = parse_amount(qty_text)
            if qty_val is None or qty_val == 0:
                add_error(
                    errors,
                    "2024",
                    "No existe el Tag UBL cac:InvoiceLine/cbc:InvoicedQuantity o es cero (0)",
                )
            # ERROR 2025: formato decimal positivo 12 enteros y 10 decimales
            elif not matches(qty_text, r"^\d{1,12}(\.\d{1,10})?$"):
                add_error(
                    errors,
                    "2025",
                    "El formato del Tag UBL cac:InvoiceLine/cbc:InvoicedQuantity es diferente de decimal positivo de 12 enteros y hasta 10 decimales",
                )

        # ERROR 2026: Description existe
        desc = text(line, "cac:Item/cbc:Description", ns)
        if desc is None:
            add_error(
                errors,
                "2026",
                "No existe el Tag UBL cac:InvoiceLine/cac:Item/cbc:Description o es vacío",
            )
        else:
            # ERROR 2027: formato 1-500 caracteres
            if not matches(desc, r"^.{1,500}$"):
                add_error(
                    errors,
                    "2027",
                    "El formato del Tag UBL cac:InvoiceLine/cac:Item/cbc:Description es diferente a alfanumérico de 1 hasta 500 caracteres",
                )

        # ERROR 2068: PriceAmount existe
        price_amount = text(line, "cac:Price/cbc:PriceAmount", ns)
        if price_amount is None:
            add_error(
                errors,
                "2068",
                "No existe el Tag UBL cac:InvoiceLine/cac:Price/cbc:PriceAmount",
            )
        else:
            # ERROR 2369: formato decimal positivo 12 enteros y 10 decimales y diferente de cero
            if not matches(price_amount, r"^\d{1,12}(\.\d{1,10})?$") or parse_amount(price_amount) == 0:
                add_error(
                    errors,
                    "2369",
                    "El formato del Tag UBL cac:InvoiceLine/cac:Price/cbc:PriceAmount es diferente de decimal positivo de 12 enteros y hasta 10 decimales y diferente de cero",
                )

        # ERROR 2028: PricingReference/AlternativeConditionPrice/PriceAmount existe
        alt_price = text(line, "cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount", ns)
        if alt_price is None:
            add_error(
                errors,
                "2028",
                "No existe el Tag UBL cac:InvoiceLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount",
            )
        else:
            # ERROR 2367: formato decimal positivo 12 enteros y 10 decimales y diferente de cero
            if not matches(alt_price, r"^\d{1,12}(\.\d{1,10})?$") or parse_amount(alt_price) == 0:
                add_error(
                    errors,
                    "2367",
                    "El formato del Tag UBL cac:InvoiceLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount es diferente de decimal positivo de 12 enteros y hasta 10 decimales y diferente de cero",
                )

        # ERROR 2409: PriceTypeCode repetido en mismo ítem
        price_type_codes = [
            (pt.text or "").strip()
            for pt in all_(line, "cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceTypeCode", ns)
        ]
        if len(price_type_codes) != len(set(price_type_codes)):
            add_error(
                errors,
                "2409",
                "Existe en el mismo ítem otro cac:AlternativeConditionPrice con el mismo valor del Tag UBL cbc:PriceTypeCode",
            )

        # ERROR 2370: LineExtensionAmount formato
        line_ext = text(line, "cbc:LineExtensionAmount", ns)
        if line_ext is None or not _positive_decimal_12_2(line_ext):
            add_error(
                errors,
                "2370",
                "El formato del Tag UBL cac:InvoiceLine/cbc:LineExtensionAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )
        _validate_line_tax_subtotals(line, ns, errors)
        _validate_line_allowance_charges(line, ns, errors)


def _validate_line_tax_subtotals(
    line: etree._Element, ns: dict, errors: list[ValidationError]
) -> None:
    tax_totals = all_(line, "cac:TaxTotal", ns)

    # ERROR 3026: TaxTotal línea repetido
    if len(tax_totals) > 1:
        add_error(
            errors,
            "3026",
            "Existe en el mismo ítem más de un tag cac:TaxTotal",
        )

    for tax_total in tax_totals:
        # ERROR 3021: TaxTotal línea TaxAmount formato
        tax_amount_text = text(tax_total, "cbc:TaxAmount", ns)
        if tax_amount_text is not None and not _positive_decimal_12_2(tax_amount_text):
            add_error(
                errors,
                "3021",
                "Si el Tag UBL existe, el formato del Tag UBL cac:InvoiceLine/cac:TaxTotal/cbc:TaxAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

    subtotals = all_(line, "cac:TaxTotal/cac:TaxSubtotal", ns)
    seen_tax_ids: set[str] = set()
    has_free = False
    tax_code_17_line = False

    for ts in subtotals:
        tax_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns)
        tax_name = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name", ns)
        tax_type_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode", ns)
        taxable = text(ts, "cbc:TaxableAmount", ns)
        tax_amount = text(ts, "cbc:TaxAmount", ns)
        percent = text(ts, "cac:TaxCategory/cbc:Percent", ns)
        exemption = text(ts, "cac:TaxCategory/cbc:TaxExemptionReasonCode", ns)
        taxable_val = parse_amount(taxable) if taxable else None
        tax_amount_val = parse_amount(tax_amount) if tax_amount else None

        # ERROR 2037: TaxScheme/ID existe
        if tax_code is None:
            add_error(
                errors,
                "2037",
                "No existe el Tag UBL cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID del Item",
            )
        else:
            # ERROR 3067: TaxSubtotal ID repetido en misma línea
            if tax_code in seen_tax_ids:
                add_error(
                    errors,
                    "3067",
                    "Existe en el mismo ítem más de un cac:TaxSubtotal con el mismo valor del Tag UBL cbc:ID",
                )
            seen_tax_ids.add(tax_code)

        # ERROR 2996: TaxScheme/Name existe
        if tax_name is None:
            add_error(
                errors,
                "2996",
                "No existe el Tag UBL cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name del Item",
            )

        # ERROR 2052: TaxScheme/TaxTypeCode existe (reutilizado a nivel línea)
        if tax_type_code is None:
            add_error(
                errors,
                "2052",
                "No existe el Tag UBL cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode del Item",
            )

        # ERROR 3031: TaxableAmount formato
        if taxable is not None and not _positive_decimal_12_2(taxable):
            add_error(
                errors,
                "3031",
                "Si el Tag UBL existe, el formato del Tag UBL cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 2033: TaxAmount formato
        if tax_amount is None or not _positive_decimal_12_2(tax_amount):
            add_error(
                errors,
                "2033",
                "El formato del Tag UBL cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 2992: Percent existe si tributo != 7152
        if tax_code != "7152" and percent is None:
            add_error(
                errors,
                "2992",
                "Si el 'Código de tributo' es diferente de '7152', no existe el Tag UBL cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent",
            )

        # ERROR 3102: Percent formato si existe
        if percent is not None and not matches(percent, r"^\d{1,3}(\.\d{1,5})?$"):
            add_error(
                errors,
                "3102",
                "Si el Tag UBL existe, el formato del Tag UBL cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent es diferente de decimal positivo de 3 enteros y hasta 5 decimales",
            )

        # ERROR 2993: Percent debe ser diferente de 0 para 1000/1016/9996 con base > 0
        if tax_code in {"1000", "1016", "9996"} and taxable_val is not None and taxable_val > 0:
            if percent is not None and parse_amount(percent) == 0:
                add_error(
                    errors,
                    "2993",
                    "Si 'Código de tributo por línea' es igual a '9996' cuyo 'Monto base' es mayor a cero y la 'Afectación al IGV o IVAP' es '11', '12', '13', '14', '15', '16' o '17', el valor del tag UBL es igual a 0",
                )


        # ERROR 3000: TaxAmount = 0 para 9995/9997/9998
        if tax_code in {"9995", "9997", "9998"} and tax_amount_val is not None and tax_amount_val != 0:
            add_error(
                errors,
                "3000",
                "Si 'Código de tributo por línea' es '9995', '9997' o '9998', el valor del tag UBL cbc:TaxAmount es diferente de 0",
            )

        # ERROR 2371: TaxExemptionReasonCode existe si tributo != 2000/9999 y base > 0
        if tax_code not in {"2000", "9999"} and taxable_val is not None and taxable_val > 0 and exemption is None:
            add_error(
                errors,
                "2371",
                "Si 'Código de tributo por línea' es diferente a '2000' (ISC) o '9999' (Otros tributos), cuyo 'Monto base' es mayor a cero, no existe el Tag UBL cbc:TaxExemptionReasonCode",
            )

        # ERROR 3050: TaxExemptionReasonCode no existe si tributo = 2000/9999
        if tax_code in {"2000", "9999"} and exemption is not None:
            add_error(
                errors,
                "3050",
                "Si 'Código de tributo por línea' es igual a '2000' (ISC) o '9999' (Otros tributos), existe el tag UBL cbc:TaxExemptionReasonCode",
            )

        # ERROR 2373: TierRange existe si tributo = 2000 y base > 0
        if tax_code == "2000" and taxable_val is not None and taxable_val > 0:
            tier = text(ts, "cac:TaxCategory/cbc:TierRange", ns)
            if tier is None:
                add_error(
                    errors,
                    "2373",
                    "Si 'Código de tributo por línea' es '2000' (ISC) cuyo 'Monto base' es mayor a cero, no existe el Tag UBL cbc:TierRange",
                )

        # ERROR 2892: BaseUnitMeasure formato (ICBPER)
        base_unit = text(ts, "cbc:BaseUnitMeasure", ns)
        if base_unit is not None:
            if not matches(base_unit, r"^\d{1,5}$"):
                add_error(
                    errors,
                    "2892",
                    "El formato del Tag UBL cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal/cbc:BaseUnitMeasure es diferente de entero mayor o igual a cero, y de hasta 5 dígitos",
                )

        # Detección para 2640/2641
        if tax_code == "9996" and taxable_val is not None and taxable_val > 0:
            has_free = True

        if exemption == "17" and taxable_val is not None and taxable_val > 0:
            tax_code_17_line = True

    # ERROR 2640: si línea tiene tributo 9996 con base > 0, PriceAmount > 0
    if has_free:
        for price in all_(line, "cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount", ns):
            if parse_amount(price.text) is not None and parse_amount(price.text) <= 0:
                add_error(
                    errors,
                    "2640",
                    "Si existe en la línea un cac:TaxSubtotal con 'Código de tributo por línea' igual a '9996' cuyo 'Monto base' es mayor a cero, el valor del Tag UBL es mayor a 0",
                )
                break

    # ERROR 2644: si TaxExemptionReasonCode=17 y base>0, todas las líneas con base>0 deben ser 17
    # Se evalúa globalmente en _validate_global_taxes


def _validate_global_taxes(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    tax_totals = all_(root, "cac:TaxTotal", ns)

    # ERROR 2956: TaxTotal global existe
    if not tax_totals:
        add_error(
            errors,
            "2956",
            "No existe el tag /Invoice/cac:TaxTotal",
        )
        return

    # ERROR 3024: TaxTotal global repetido
    if len(tax_totals) > 1:
        add_error(
            errors,
            "3024",
            "Existe a nivel global más de un tag cac:TaxTotal",
        )
        return

    tax_total = tax_totals[0]

    # ERROR 3020: TaxTotal global TaxAmount formato
    tax_amount_text = text(tax_total, "cbc:TaxAmount", ns)
    if tax_amount_text is None or not _positive_decimal_12_2(tax_amount_text):
        add_error(
            errors,
            "3020",
            "Si el Tag UBL existe, el formato del Tag UBL cac:TaxTotal/cbc:TaxAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
        )

    subtotals = all_(tax_total, "cac:TaxSubtotal", ns)
    seen_tax_ids: set[str] = set()
    invoice_type_code = text(root, "cbc:InvoiceTypeCode", ns)

    # Recopilar IDs de tributos a nivel línea con base > 0
    line_tax_ids_with_base: set[str] = set()
    lines = all_(root, "cac:InvoiceLine", ns)
    any_line_17 = False
    any_line_2000 = False
    for line in lines:
        for ts in all_(line, "cac:TaxTotal/cac:TaxSubtotal", ns):
            tax_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns)
            taxable = parse_amount(text(ts, "cbc:TaxableAmount", ns))
            exemption = text(ts, "cac:TaxCategory/cbc:TaxExemptionReasonCode", ns)
            if tax_code in {"1000", "1016", "9995", "9996", "9997", "9998"} and taxable is not None and taxable > 0:
                line_tax_ids_with_base.add(tax_code)
            if exemption == "17" and taxable is not None and taxable > 0:
                any_line_17 = True
            if tax_code == "2000" and taxable is not None and taxable > 0:
                any_line_2000 = True

    # ERROR 2644: línea IVAP (17) con base > 0 y otra línea diferente
    if any_line_17:
        for line in lines:
            for ts in all_(line, "cac:TaxTotal/cac:TaxSubtotal", ns):
                tax_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns)
                exemption = text(ts, "cac:TaxCategory/cbc:TaxExemptionReasonCode", ns)
                taxable = parse_amount(text(ts, "cbc:TaxableAmount", ns))
                if taxable is not None and taxable > 0 and exemption != "17" and tax_code in {"1000", "9995", "9996", "9997", "9998"}:
                    add_error(
                        errors,
                        "2644",
                        "Si 'Afectación al IGV o IVAP' es '17' y 'Monto base' es mayor a cero, y existe otra línea con 'Afectación al IGV o IVAP por ítem' diferente de '17' y 'Monto base' mayor a cero",
                    )
                    break
            else:
                continue
            break

    # ERROR 2650: ISC + IVAP coexistencia
    if any_line_17 and any_line_2000:
        add_error(
            errors,
            "2650",
            "Si 'Código de tributo' es '2000' y 'Monto base' es mayor a cero, y existe un ítem con código de 'Afectación al IGV o IVAP' con valor '17' (IVAP) cuyo 'Monto base' es mayor a cero",
        )

    for ts in subtotals:
        tax_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns)
        tax_name = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name", ns)
        tax_type_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode", ns)
        taxable = text(ts, "cbc:TaxableAmount", ns)
        tax_amount = text(ts, "cbc:TaxAmount", ns)

        # ERROR 3059: TaxScheme/ID existe
        if tax_code is None:
            add_error(
                errors,
                "3059",
                "No existe el Tag UBL cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID",
            )
        else:
            # ERROR 3068: TaxSubtotal global ID repetido
            if tax_code in seen_tax_ids:
                add_error(
                    errors,
                    "3068",
                    "Existe a nivel global más de un cac:TaxSubtotal con el mismo valor del Tag UBL cbc:ID",
                )
            seen_tax_ids.add(tax_code)

        # ERROR 2054: TaxScheme/Name existe
        if tax_name is None:
            add_error(
                errors,
                "2054",
                "No existe el Tag UBL cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:Name",
            )

        # ERROR 2052: TaxScheme/TaxTypeCode existe
        if tax_type_code is None:
            add_error(
                errors,
                "2052",
                "No existe el Tag UBL cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:TaxTypeCode",
            )

        # ERROR 3003: TaxableAmount existe si tributo != 7152
        if tax_code != "7152" and taxable is None:
            add_error(
                errors,
                "3003",
                "Si el 'Código de tributo' es diferente de '7152', no existe el Tag UBL cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount",
            )

        # ERROR 2999: TaxableAmount formato
        if taxable is not None and not _positive_decimal_12_2(taxable):
            add_error(
                errors,
                "2999",
                "El formato del Tag UBL cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 2048: TaxAmount formato
        if tax_amount is None or not _positive_decimal_12_2(tax_amount):
            add_error(
                errors,
                "2048",
                "El formato del Tag UBL cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 3107: exportación no debe tener ciertos tributos globales
        if invoice_type_code in _EXPORT_OPERATIONS:
            if tax_code in {"9997", "9998"}:
                add_error(
                    errors,
                    "3107",
                    "Si 'Tipo de operación' es de exportación y existe un ID '9997' o '9998' a nivel global",
                )
            if tax_code in {"1000", "1016"}:
                add_error(
                    errors,
                    "3107",
                    "Si 'Tipo de operación' es de exportación y existe un ID '1000' o '1016' a nivel global",
                )
            if tax_code in {"2000", "9999"}:
                add_error(
                    errors,
                    "3107",
                    "Si 'Tipo de operación' es de exportación y existe un ID '2000' o '9999' a nivel global",
                )

        # ERROR 2642: exportación → TaxExemptionReasonCode = 40
        if invoice_type_code in _EXPORT_OPERATIONS:
            exemption = text(ts, "cac:TaxCategory/cbc:TaxExemptionReasonCode", ns)
            if exemption != "40":
                add_error(
                    errors,
                    "2642",
                    "Si 'Tipo de operación' es exportación, el valor del tag UBL cbc:TaxExemptionReasonCode es diferente a '40'",
                )

        # ERROR 2638: si línea tiene tributo con base>0, debe existir global
        if tax_code in line_tax_ids_with_base:
            line_tax_ids_with_base.discard(tax_code)

    # ERROR 2638: tributos de línea sin total global
    for missing in line_tax_ids_with_base:
        add_error(
            errors,
            "2638",
            f"Si existe alguna línea con 'Monto base' mayor a cero para el tributo '{missing}', y no existe su respectivo tag de totales del tributo",
        )

    # ERROR 2641: gratuita + precio 02 > 0 → total gratuito > 0
    free_global = None
    for ts in subtotals:
        if text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns) == "9996":
            free_global = parse_amount(text(ts, "cbc:TaxableAmount", ns))
            break

    if free_global is not None and free_global == 0:
        for line in lines:
            for alt in all_(line, "cac:PricingReference/cac:AlternativeConditionPrice", ns):
                price_type = text(alt, "cbc:PriceTypeCode", ns)
                price = parse_amount(text(alt, "cbc:PriceAmount", ns))
                if price_type == "02" and price is not None and price > 0:
                    add_error(
                        errors,
                        "2641",
                        "Si 'Código de tributo' es '9996' (Gratuita) y existe una línea con 'Valor referencial unitario por ítem en operaciones gratuitas' con monto mayor a cero, el valor del Tag UBL es igual a 0",
                    )
                    break
            else:
                continue
            break

    # ERROR 2416: gratuita + leyenda 1002 → total gratuito = 0
    notes = all_(root, "cbc:Note", ns)
    has_legend_1002 = any(
        note.get("languageLocaleID") == "1002" for note in notes
    )
    if has_legend_1002 and free_global is not None and free_global == 0:
        add_error(
            errors,
            "2416",
            "Si 'Código de tributo' es '9996' (Gratuita) y 'Código de leyenda' es '1002', el valor del Tag UBL es igual a 0",
        )

    # ERROR 2949: ICBPER + fecha emisión < 2019-08-01
    issue_date = text(root, "cbc:IssueDate", ns)
    for ts in subtotals:
        if text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns) == "7152":
            tax_amount = parse_amount(text(ts, "cbc:TaxAmount", ns))
            if tax_amount is not None and tax_amount > 0 and issue_date is not None and issue_date < "2019-08-01":
                add_error(
                    errors,
                    "2949",
                    "Si 'Código de tributo' es '7152' y la 'Fecha de emisión' es menor a '2019-08-01', el valor del Tag Ubl es mayor a cero",
                )


def _validate_global_allowance_charges(
    root: etree._Element, ns: dict, errors: list[ValidationError]
) -> None:
    allowance_charges = all_(root, "cac:AllowanceCharge", ns)

    # ERROR 2065: AllowanceTotalAmount formato
    allowance_total = text(root, "cac:LegalMonetaryTotal/cbc:AllowanceTotalAmount", ns)
    if allowance_total is not None and not _positive_decimal_12_2(allowance_total):
        add_error(
            errors,
            "2065",
            "El formato del Tag UBL cac:LegalMonetaryTotal/cbc:AllowanceTotalAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
        )

    # ERROR 2064: ChargeTotalAmount formato
    charge_total = text(root, "cac:LegalMonetaryTotal/cbc:ChargeTotalAmount", ns)
    if charge_total is not None and not _positive_decimal_12_2(charge_total):
        add_error(
            errors,
            "2064",
            "El formato del Tag UBL cac:LegalMonetaryTotal/cbc:ChargeTotalAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
        )

    for ac in allowance_charges:
        indicator = text(ac, "cbc:ChargeIndicator", ns)
        reason_code = text(ac, "cbc:AllowanceChargeReasonCode", ns)
        amount = text(ac, "cbc:Amount", ns)
        base_amount = text(ac, "cbc:BaseAmount", ns)
        factor = text(ac, "cbc:MultiplierFactorNumeric", ns)
        amount_val = parse_amount(amount) if amount else None
        base_val = parse_amount(base_amount) if base_amount else None
        factor_val = parse_amount(factor) if factor else None

        # ERROR 3072: AllowanceChargeReasonCode existe
        if reason_code is None:
            add_error(
                errors,
                "3072",
                "Si existe 'Indicador de cargo/descuento', no existe el Tag UBL cac:AllowanceCharge/cbc:AllowanceChargeReasonCode o es vacío",
            )

        # ERROR 2968: Amount formato
        if amount is None or not _positive_decimal_12_2(amount):
            add_error(
                errors,
                "2968",
                "El formato del Tag UBL cac:AllowanceCharge/cbc:Amount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 3016: BaseAmount formato si existe
        if base_amount is not None and not _positive_decimal_12_2(base_amount):
            add_error(
                errors,
                "3016",
                "El formato del Tag UBL cac:AllowanceCharge/cbc:BaseAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 3025: MultiplierFactorNumeric formato si existe
        if factor is not None and not matches(factor, r"^\d{1,3}(\.\d{1,5})?$"):
            add_error(
                errors,
                "3025",
                "Si el Tag UBL existe, el formato del Tag UBL cac:AllowanceCharge/cbc:MultiplierFactorNumeric es diferente de decimal positivo de 3 enteros y hasta 5 decimales",
            )

        # ERROR 3114: ChargeIndicator según código
        if reason_code in {"45", "46", "49", "50", "51", "52", "53"}:
            if indicator != "true":
                add_error(
                    errors,
                    "3114",
                    "Si valor del tag es diferente de 'true' para 'código de motivo de cargo' igual a '45', '46', '49', '50', '51', '52' y '53'",
                )
        if reason_code in {"02", "03", "04", "05", "06", "20"}:
            if indicator != "false":
                add_error(
                    errors,
                    "3114",
                    "Si valor del tag es diferente de 'false' para 'Código de motivo de descuento' igual a '02', '03', '04', '05', '06' y '20'",
                )

        # ERROR 3074: Amount = 0 con código 45
        if reason_code == "45" and amount_val is not None and amount_val == 0:
            add_error(
                errors,
                "3074",
                "Si el Tag UBL existe, el valor del Tag Ubl es 0 (cero), cuando el código de motivo de cargo igual a '45'",
            )

        # ERROR 3307: Amount = BaseAmount * factor ±1
        if reason_code is not None and base_val is not None and factor_val is not None and factor_val > 0:
            expected = (base_val * factor_val).quantize(Decimal("0.01"))
            if amount_val is None or abs(amount_val - expected) > Decimal("1"):
                add_error(
                    errors,
                    "3307",
                    "Si existe el tag 'Código de motivo de cargo/descuento' y existe 'Factor de cargo/descuento' con monto mayor a cero, el importe difiere del resultado de multiplicar 'Monto base' por el 'Factor'",
                )

    # ERROR 3282: descuentos por anticipo requieren PrepaidAmount > 0
    has_anticipo_discount = any(
        text(ac, "cbc:AllowanceChargeReasonCode", ns) in {"04", "05", "06", "20"}
        and parse_amount(text(ac, "cbc:Amount", ns)) is not None
        and parse_amount(text(ac, "cbc:Amount", ns)) > 0
        for ac in allowance_charges
    )
    prepaid = parse_amount(text(root, "cac:LegalMonetaryTotal/cbc:PrepaidAmount", ns))
    if has_anticipo_discount and (prepaid is None or prepaid <= 0):
        add_error(
            errors,
            "3282",
            "Si existe el tag 'Código de motivo de cargo/descuento' con valor igual a '04', '05', '06' o '20', el valor del tag UBL es mayor a cero, y el 'Total de anticipos' no existe o es cero",
        )


def _validate_line_allowance_charges(
    line: etree._Element, ns: dict, errors: list[ValidationError]
) -> None:
    allowance_charges = all_(line, "cac:AllowanceCharge", ns)

    for ac in allowance_charges:
        indicator = text(ac, "cbc:ChargeIndicator", ns)
        reason_code = text(ac, "cbc:AllowanceChargeReasonCode", ns)
        amount = text(ac, "cbc:Amount", ns)
        base_amount = text(ac, "cbc:BaseAmount", ns)
        factor = text(ac, "cbc:MultiplierFactorNumeric", ns)
        amount_val = parse_amount(amount) if amount else None
        base_val = parse_amount(base_amount) if base_amount else None
        factor_val = parse_amount(factor) if factor else None

        # ERROR 3073: AllowanceChargeReasonCode existe
        if reason_code is None:
            add_error(
                errors,
                "3073",
                "No existe el Tag UBL cac:InvoiceLine/cac:AllowanceCharge/cbc:AllowanceChargeReasonCode o es vacío",
            )

        # ERROR 2955: Amount formato
        if amount is None or not _positive_decimal_12_2(amount):
            add_error(
                errors,
                "2955",
                "El formato del Tag UBL cac:InvoiceLine/cac:AllowanceCharge/cbc:Amount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 3053: BaseAmount formato si existe
        if base_amount is not None and not _positive_decimal_12_2(base_amount):
            add_error(
                errors,
                "3053",
                "Si el Tag UBL existe, el formato del Tag UBL cac:InvoiceLine/cac:AllowanceCharge/cbc:BaseAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
            )

        # ERROR 3052: MultiplierFactorNumeric formato si existe
        if factor is not None and not matches(factor, r"^\d{1,3}(\.\d{1,5})?$"):
            add_error(
                errors,
                "3052",
                "Si el Tag UBL existe, el formato del Tag UBL cac:InvoiceLine/cac:AllowanceCharge/cbc:MultiplierFactorNumeric es diferente de decimal positivo de 3 enteros y hasta 5 decimales",
            )

        # ERROR 3114: ChargeIndicator según código
        if reason_code in {"47", "48"}:
            if indicator != "true":
                add_error(
                    errors,
                    "3114",
                    "Si valor del tag es diferente de 'true' para 'código de motivo de cargo' igual a '47' y '48'",
                )
        if reason_code in {"00", "01"}:
            if indicator != "false":
                add_error(
                    errors,
                    "3114",
                    "Si valor del tag es diferente 'false' para 'Código de motivo de descuento' igual a '00' y '01'",
                )

        # ERROR 3290: Amount = BaseAmount * factor ±1
        if reason_code is not None and base_val is not None and factor_val is not None and factor_val > 0:
            expected = (base_val * factor_val).quantize(Decimal("0.01"))
            if amount_val is None or abs(amount_val - expected) > Decimal("1"):
                add_error(
                    errors,
                    "3290",
                    "Si existe el tag 'Código de motivo de cargo/descuento' y existe 'Factor de cargo/descuento' con monto mayor a cero, el importe difiere del resultado de multiplicar 'Monto base' por el 'Factor'",
                )


def _validate_payment_terms_and_means(
    root: etree._Element, ns: dict, errors: list[ValidationError]
) -> None:
    invoice_type_code = text(root, "cbc:InvoiceTypeCode", ns)

    payment_terms = all_(root, "cac:PaymentTerms", ns)
    payment_means = all_(root, "cac:PaymentMeans", ns)

    pt_ids = {text(pt, "cbc:ID", ns) for pt in payment_terms}
    pm_ids = {text(pm, "cbc:ID", ns) for pm in payment_means}

    # ERROR 3034: PaymentMeans/ID=Detraccion para tipo op 1001-1004
    if invoice_type_code in _DETRACTION_OPERATIONS:
        if "Detraccion" not in pm_ids:
            add_error(
                errors,
                "3034",
                "Si 'Tipo de operación' es '1001', '1002', '1003' o '1004', no existe al menos un cac:PaymentMeans con cbc:ID con valor igual a 'Detraccion'",
            )

    for pt in payment_terms:
        pt_id = text(pt, "cbc:ID", ns)
        amount = text(pt, "cbc:Amount", ns)

        # ERROR 3035: PaymentTerms/Amount existe si ID=Detraccion
        if pt_id == "Detraccion" and amount is None:
            add_error(
                errors,
                "3035",
                "Si 'Indicador PaymentTerms' es igual a 'Detraccion', no existe el Tag UBL cac:PaymentTerms/cbc:Amount",
            )

        # ERROR 3037: PaymentTerms/Amount formato
        if amount is not None and not _positive_decimal_12_2(amount):
            add_error(
                errors,
                "3037",
                "El formato del Tag UBL cac:PaymentTerms/cbc:Amount es diferente de decimal (positivo mayor a cero) de 12 enteros y hasta 2 decimales",
            )

    # ERROR 2797: percepción Amount > Importe total
    for ac in all_(root, "cac:AllowanceCharge", ns):
        reason = text(ac, "cbc:AllowanceChargeReasonCode", ns)
        if reason in {"51", "52", "53"}:
            amount = parse_amount(text(ac, "cbc:Amount", ns))
            payable = parse_amount(text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount", ns))
            currency = text(root, "cbc:DocumentCurrencyCode", ns)
            if currency == "PEN" and amount is not None and payable is not None and amount > payable:
                add_error(
                    errors,
                    "2797",
                    "Si 'Código de motivo de cargo/descuento' es '51', '52' o '53' (Percepción) y 'Tipo de moneda' del comprobante es 'PEN', el valor del Tag UBL es mayor a 'Importe total'",
                )


def _validate_prepaid_payments(
    root: etree._Element, ns: dict, errors: list[ValidationError]
) -> None:
    prepaids = all_(root, "cac:PrepaidPayment", ns)

    total_prepaid = Decimal("0")
    for pp in prepaids:
        paid_amount = text(pp, "cbc:PaidAmount", ns)

        # ERROR 2503: PaidAmount <= 0
        if paid_amount is not None:
            val = parse_amount(paid_amount)
            if val is None or val <= 0:
                add_error(
                    errors,
                    "2503",
                    "Si el Tag UBL existe, cac:PrepaidPayment/cbc:PaidAmount es menor o igual a 0",
                )
            else:
                total_prepaid += val

        # ERROR 2521: AdditionalDocumentReference/ID formato si tipo 02/03
        # Simplificación: validamos formato cuando existe el nodo
        ref_id = text(pp, "cbc:ID", ns)
        # No se puede determinar el tipo sin contexto adicional; se deja FUERA parcial
        # FUERA DE ALCANCE parcial - requiere contexto de tipo de comprobante de anticipo.

    # ERROR 2509: PrepaidAmount = suma de anticipos
    prepaid_total_text = text(root, "cac:LegalMonetaryTotal/cbc:PrepaidAmount", ns)
    if prepaid_total_text is not None:
        prepaid_total = parse_amount(prepaid_total_text)
        if prepaid_total is not None and prepaid_total > 0 and abs(prepaid_total - total_prepaid) > Decimal("0.01"):
            add_error(
                errors,
                "2509",
                "Si existe Tag UBL con valor mayor a cero, la suma de los 'Importe del anticipo' es diferente al valor del tag UBL",
            )


def _validate_notes(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    notes = all_(root, "cbc:Note", ns)

    # ERROR 3014: languageLocaleID repetido
    locales = [note.get("languageLocaleID") for note in notes if note.get("languageLocaleID")]
    if len(locales) != len(set(locales)):
        add_error(
            errors,
            "3014",
            "El valor del atributo se repite en el comprobante",
        )

    # ERROR 3006: Note formato 1-200 caracteres
    for note in notes:
        content = (note.text or "").strip()
        if content and not matches(content, r"^.{1,200}$"):
            add_error(
                errors,
                "3006",
                "Si el formato del Tag UBL cbc:Note es diferente a alfanumérico de 1 a 200 caractéres",
            )


def _validate_additional_item_properties(
    root: etree._Element, ns: dict, errors: list[ValidationError]
) -> None:
    invoice_type_code = text(root, "cbc:InvoiceTypeCode", ns)

    for line in all_(root, "cac:InvoiceLine", ns):
        properties = all_(line, "cac:Item/cac:AdditionalItemProperty", ns)
        codes = set()
        for prop in properties:
            name_code = text(prop, "cbc:NameCode", ns)
            if name_code:
                codes.add(name_code)

            # ERROR 3065: StartDate si NameCode = 3059
            if name_code == "3059":
                if not exists(prop, "cac:UsabilityPeriod/cbc:StartDate", ns):
                    add_error(
                        errors,
                        "3065",
                        "De existir 'Código del concepto' igual a '3059' y no existe el tag cac:UsabilityPeriod/cbc:StartDate",
                    )

        # ERROR 3063: NameCode 3001 si tipo operación 1002
        if invoice_type_code == "1002" and "3001" not in codes:
            add_error(
                errors,
                "3063",
                "Si 'Tipo de operación' es igual a '1002', y no existe el tag con valor '3001'",
            )

        # ERROR 2898/2899: tipo operación 2104 y concepto 7015
        if invoice_type_code == "2104":
            if "7015" not in codes:
                add_error(
                    errors,
                    "2898",
                    "Si 'Tipo de operación' es '2104' y el 'Código del concepto' es '7015' y el valor del tag es igual a '1' o '2', no existe el concepto 7015",
                )
                add_error(
                    errors,
                    "2899",
                    "Si 'Tipo de operación' es '2104' y el 'Código del concepto' es '7015' y el valor del tag es igual a '3', no existe el concepto 7015",
                )
def _validate_monetary_total(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    """ERROR 2031 / 3019: formatos de LineExtensionAmount y TaxInclusiveAmount."""
    line_ext = text(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount", ns)
    if line_ext is not None and not _positive_decimal_12_2(line_ext):
        add_error(
            errors,
            "2031",
            "Si existe el tag, el formato del Tag UBL cac:LegalMonetaryTotal/cbc:LineExtensionAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
        )

    tax_inclusive = text(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", ns)
    if tax_inclusive is not None and not _positive_decimal_12_2(tax_inclusive):
        add_error(
            errors,
            "3019",
            "Si existe el tag, el formato del Tag UBL cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount es diferente de decimal positivo de 12 enteros y hasta 2 decimales y diferente de cero",
        )


def _validate_registration_address(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    """ERROR 3030: AddressTypeCode obligatorio si serie no inicia con número."""
    doc_id = text(root, "cbc:ID", ns) or ""
    serie = doc_id.split("-")[0] if "-" in doc_id else doc_id
    if serie and not serie[0].isdigit():
        if not exists(root, "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cac:RegistrationAddress/cbc:AddressTypeCode", ns):
            add_error(
                errors,
                "3030",
                "Si Serie del documento no inicia con número, no existe el Tag UBL cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cac:RegistrationAddress/cbc:AddressTypeCode o es vacío",
            )



def _positive_decimal_12_2(value: str) -> bool:
    """Decimal positivo de hasta 12 enteros y 2 decimales, diferente de cero."""
    if not matches(value, r"^\d{1,12}(\.\d{1,2})?$"):
        return False
    val = parse_amount(value)
    if val is None or val <= 0:
        return False
    return True


# FUERA DE ALCANCE documentado:
# ERROR 2108: requiere fecha de recepción del XML por SUNAT.
# ERROR 2521: requiere contexto del tipo de comprobante de anticipo para validar formato exacto.
