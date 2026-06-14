"""Validaciones SUNAT adicionales para CreditNote (batch 2).

Complementa a _extra_credit_note.py con las reglas que no estaban contadas
como literales de cadena en add_error/_add o que faltaban por implementar.

Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
https://cpe.sunat.gob.pe/guias-y-manuales
"""

from __future__ import annotations

import re
from decimal import Decimal

from lxml import etree

from openubl.validators.common import (
    CATALOG05,
    CATALOG05_NAMES,
    NS_CREDIT_NOTE,
    ValidationError,
    add_error,
    all_,
    attr,
    exists,
    matches,
    parse_amount,
    text,
)

_NS = NS_CREDIT_NOTE

_CATALOG09 = {f"{i:02d}" for i in range(1, 14)}
_CATALOG16 = {"01", "02"}
_CATALOG02 = {"PEN", "USD", "EUR"}

_CATALOG02_MAP = {
    "PEN": "PEN",
    "USD": "USD",
    "EUR": "EUR",
    "Catalog2.PEN": "PEN",
    "Catalog2.USD": "USD",
    "Catalog2.EUR": "EUR",
}

_ALLOWED_F = {
    "01", "05", "06", "12", "13", "15", "16", "18", "21", "28",
    "30", "34", "37", "42", "43", "45", "55", "11", "17", "23",
    "24", "56",
}
_ALLOWED_B = {"03", "12", "16", "55"}
_ALLOWED_NUMERIC = {
    "01", "03", "05", "06", "12", "13", "15", "16", "18", "21",
    "28", "30", "34", "37", "42", "43", "45", "55", "11", "17",
    "23", "24", "56",
}

# Conceptos tributarios que requieren el tag cbc:Value (3064).
_VALUE_CONCEPTS = {
    "7001", "7002", "7003", "7004", "7005", "7006", "7007", "7008",
    "7009", "7010", "7011", "7012", "7013", "7015", "7016",
}


def _currency(value: str | None) -> str | None:
    if value is None:
        return None
    return _CATALOG02_MAP.get(value, value)


def _doc_serie(root: etree._Element) -> str:
    doc_id = text(root, "cbc:ID", _NS) or ""
    return doc_id.split("-")[0] if "-" in doc_id else doc_id


def _resp_code(root: etree._Element) -> str | None:
    return text(root, "cac:DiscrepancyResponse/cbc:ResponseCode", _NS)


def _ref_doc_type(root: etree._Element) -> str | None:
    return text(
        root,
        "cac:BillingReference/cac:InvoiceDocumentReference/cbc:DocumentTypeCode",
        _NS,
    )


def _doc_currency(root: etree._Element) -> str | None:
    return _currency(text(root, "cbc:DocumentCurrencyCode", _NS))


def _customer_type(root: etree._Element) -> str | None:
    return attr(
        root,
        "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
        "schemeID",
        _NS,
    )


def _item_property_codes(line: etree._Element) -> set[str]:
    codes: set[str] = set()
    for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", _NS):
        code = text(prop, "cbc:NameCode", _NS)
        if code is not None:
            codes.add(code)
    return codes


def _tax_code(subtotal: etree._Element) -> str | None:
    return text(subtotal, "cac:TaxCategory/cac:TaxScheme/cbc:ID", _NS)


def _tax_name(subtotal: etree._Element) -> str | None:
    return text(subtotal, "cac:TaxCategory/cac:TaxScheme/cbc:Name", _NS)


def _taxable_amount(subtotal: etree._Element) -> Decimal | None:
    return parse_amount(text(subtotal, "cbc:TaxableAmount", _NS))


def _tax_amount(subtotal: etree._Element) -> Decimal | None:
    return parse_amount(text(subtotal, "cbc:TaxAmount", _NS))


def _percent(subtotal: etree._Element) -> Decimal | None:
    return parse_amount(text(subtotal, "cac:TaxCategory/cbc:Percent", _NS))


def _exemption_code(subtotal: etree._Element) -> str | None:
    return text(subtotal, "cac:TaxCategory/cbc:TaxExemptionReasonCode", _NS)


def _within_tolerance(
    a: Decimal | None, b: Decimal | None, tol: Decimal = Decimal("1")
) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def _positive_amount(value: str | None, int_digits: int = 12, dec_digits: int = 2) -> bool:
    if value is None:
        return False
    try:
        d = Decimal(value)
    except Exception:
        return False
    if d <= 0:
        return False
    parts = value.split(".")
    if len(parts) == 2 and len(parts[1]) > dec_digits:
        return False
    if len(parts[0]) > int_digits:
        return False
    return True


def _positive_amount_10(value: str | None) -> bool:
    return _positive_amount(value, int_digits=12, dec_digits=10)


def _format_percent(value: str | None) -> bool:
    if value is None:
        return False
    try:
        d = Decimal(value)
    except Exception:
        return False
    if d <= 0:
        return False
    return re.match(r"^\d{1,3}(\.\d{1,5})?$", value) is not None


def validate_credit_note_extra2(
    root: etree._Element, errors: list[ValidationError] | None = None
) -> list[ValidationError]:
    """Valida reglas SUNAT adicionales para CreditNote."""
    if errors is None:
        errors = []

    _validate_header(root, errors)
    _validate_billing_reference(root, errors)
    _validate_related_documents(root, errors)
    _validate_lines(root, errors)
    _validate_payment_terms(root, errors)
    _validate_totals(root, errors)
    _validate_mortgage(root, errors)
    _validate_contracts(root, errors)
    _validate_currency(root, errors)

    return errors


def _validate_header(root: etree._Element, errors: list[ValidationError]) -> None:
    # ERROR 2128: ResponseCode obligatorio
    resp_code = _resp_code(root)
    if resp_code is None:
        add_error(
            errors,
            "2128",
            "No existe el Tag UBL cac:DiscrepancyResponse/cbc:ResponseCode o es vacío",
        )

    # ERROR 3203: ResponseCode repetido
    resp_codes = all_(root, "cac:DiscrepancyResponse/cbc:ResponseCode", _NS)
    if len(resp_codes) > 1:
        add_error(
            errors,
            "3203",
            "El tipo de nota es un dato único",
        )

    # ERROR 2136 / 2135: Description obligatorio y formato
    desc = text(root, "cac:DiscrepancyResponse/cbc:Description", _NS)
    if desc is None:
        add_error(
            errors,
            "2136",
            "No existe el Tag UBL cac:DiscrepancyResponse/cbc:Description o es vacío",
        )
    elif not matches(desc, r"^.{1,500}$"):
        add_error(
            errors,
            "2135",
            "cac:DiscrepancyResponse/cbc:Description - El dato ingresado no cumple con la estructura",
        )


def _validate_billing_reference(
    root: etree._Element, errors: list[ValidationError]
) -> None:
    refs = all_(root, "cac:BillingReference/cac:InvoiceDocumentReference", _NS)
    resp_code = _resp_code(root)
    doc_serie = _doc_serie(root)
    serie_first = doc_serie[0].upper() if doc_serie else ""

    # ERROR 2524: documento afectado obligatorio si resp_code != "10"
    if resp_code != "10" and not refs:
        add_error(
            errors,
            "2524",
            "Debe indicar el documento afectado por la nota",
        )

    # ERROR 3261: no modificar más de un comprobante
    if resp_code in _CATALOG09 and len(refs) > 1:
        add_error(
            errors,
            "3261",
            "No se puede modificar mas de un comprobante con la nota",
        )

    # ERROR 3194: solo un documento para exportación
    if resp_code == "11" and len(refs) > 1:
        add_error(
            errors,
            "3194",
            "Solo es permitido registrar un documento que modifica.",
        )

    # ERROR 2884: todos los documentos modificados del mismo tipo
    doc_types = [
        text(r, "cbc:DocumentTypeCode", _NS)
        for r in refs
        if text(r, "cbc:DocumentTypeCode", _NS) is not None
    ]
    if len(doc_types) > 1 and len(set(doc_types)) > 1:
        add_error(
            errors,
            "2884",
            "Los comprobantes modificados por la nota deben ser del mismo tipo",
        )

    # ERROR 2365: documento modificado repetido (tipo + ID)
    pairs = []
    for ref in refs:
        ref_type = text(ref, "cbc:DocumentTypeCode", _NS)
        ref_id = text(ref, "cbc:ID", _NS)
        if ref_type is not None and ref_id is not None:
            pairs.append((ref_type, ref_id))
    if len(pairs) != len(set(pairs)):
        add_error(
            errors,
            "2365",
            "El comprobante contiene un tipo y número de Documento Relacionado repetido",
        )

    for ref in refs:
        ref_type = text(ref, "cbc:DocumentTypeCode", _NS)
        ref_id = text(ref, "cbc:ID", _NS)

        # ERROR 2116 / 2399 / 2594: tipo según serie
        if serie_first in {"F", "E"}:
            allowed = set(_ALLOWED_F)
            if resp_code == "10":
                allowed |= {"", "-"}
            if ref_type is not None and ref_type not in allowed:
                add_error(
                    errors,
                    "2116",
                    "El tipo de documento modificado por la Nota de credito debe ser factura electronica o ticket",
                )
        elif serie_first == "B":
            allowed = set(_ALLOWED_B)
            if resp_code == "10":
                allowed |= {"", "-"}
            if ref_type is not None and ref_type not in allowed:
                add_error(
                    errors,
                    "2399",
                    "El tipo de documento modificado por la Nota de credito debe ser boleta electronica",
                )
        elif serie_first.isdigit():
            allowed = set(_ALLOWED_NUMERIC)
            if resp_code == "10":
                allowed |= {"", "-"}
            if ref_type is not None and ref_type not in allowed:
                add_error(
                    errors,
                    "2594",
                    "El tipo de documento modificado por la nota electronica no es valido",
                )

        # ERROR 3259: resp_code 13 -> tipo 01
        if resp_code == "13" and ref_type != "01":
            add_error(
                errors,
                "3259",
                "Para el tipo de nota de credito 13 el documento afectado debe ser Factura",
            )

        # ERROR 2117: formato del ID según tipo
        if ref_id is not None:
            if not _valid_ref_id(ref_type, ref_id):
                add_error(
                    errors,
                    "2117",
                    "La serie o numero del documento modificado por la Nota de Credito no cumple con el formato establecido",
                )


def _valid_ref_id(ref_type: str | None, ref_id: str) -> bool:
    if ref_type == "01":
        return matches(ref_id, r"^[FE][A-Z0-9]{3}-\d{1,8}$|^\d{1,4}-\d{1,8}$")
    if ref_type == "03":
        return matches(
            ref_id,
            r"^[B][A-Z0-9]{3}-\d{1,8}$|^(EB01)-\d{1,8}$|^\d{1,4}-\d{1,8}$",
        )
    if ref_type == "56":
        return matches(ref_id, r"^C[A-Z0-9]{3}-\d{1,9}$")
    if ref_type == "28":
        return matches(ref_id, r"^[A-Z0-9]{4}-\d{1,9}$")
    if ref_type in _ALLOWED_F | _ALLOWED_B | _ALLOWED_NUMERIC:
        return matches(ref_id, r"^[a-zA-Z0-9-]{1,20}-[a-zA-Z0-9-]{1,20}$")
    if ref_type in {None, "", "-"}:
        return ref_id in {"", "-"} or matches(
            ref_id, r"^[a-zA-Z0-9-]{1,20}-[a-zA-Z0-9-]{1,20}$"
        )
    return True


def _validate_related_documents(
    root: etree._Element, errors: list[ValidationError]
) -> None:
    resp_code = _resp_code(root)

    # Guías de remisión
    despatch_refs = all_(root, "cac:DespatchDocumentReference", _NS)
    pairs = []
    for ref in despatch_refs:
        ref_type = text(ref, "cbc:DocumentTypeCode", _NS)
        ref_id = text(ref, "cbc:ID", _NS)
        if ref_type is not None and ref_id is not None:
            pairs.append((ref_type, ref_id))
    if len(pairs) != len(set(pairs)):
        add_error(
            errors,
            "2364",
            "El comprobante contiene un tipo y número de Guía de Remisión repetido",
        )

    # Otros documentos relacionados
    add_refs = all_(root, "cac:AdditionalDocumentReference", _NS)
    pairs = []
    type_99_count = 0
    for ref in add_refs:
        ref_type = text(ref, "cbc:DocumentTypeCode", _NS)
        ref_id = text(ref, "cbc:ID", _NS)
        if ref_type is not None:
            if ref_type == "99":
                type_99_count += 1
            if ref_id is not None:
                pairs.append((ref_type, ref_id))

    # ERROR 2426: duplicados
    if len(pairs) != len(set(pairs)):
        add_error(
            errors,
            "2426",
            "Documentos relacionados duplicados en el comprobante.",
        )

    # ERROR 2635 / 2636 / 2637: reglas del tipo 99
    if resp_code == "10":
        if type_99_count > 1:
            add_error(
                errors,
                "2635",
                "Debe existir DocumentTypeCode de Otros documentos relacionados con valor 99 para un tipo codigo Nota Credito 10.",
            )
        if any(t != "99" for t, _ in pairs):
            add_error(
                errors,
                "2637",
                "No existe datos del DocumentType de los documentos relacionados con valor 99 para un tipo codigo Nota Credito 10.",
            )
    else:
        if type_99_count > 0:
            add_error(
                errors,
                "2636",
                "No existe datos del ID de los documentos relacionados con valor 99 para un tipo codigo Nota Credito 10.",
            )


def _validate_lines(root: etree._Element, errors: list[ValidationError]) -> None:
    lines = all_(root, "cac:CreditNoteLine", _NS)
    resp_code = _resp_code(root)
    seen_ids: set[str] = set()

    for line in lines:
        line_id = text(line, "cbc:ID", _NS)

        # ERROR 2137: formato del ID
        if line_id is None or not matches(line_id, r"^\d{1,3}$") or line_id == "0":
            add_error(
                errors,
                "2137",
                "El Numero de orden del item no cumple con el formato establecido",
            )
        else:
            if line_id in seen_ids:
                add_error(
                    errors,
                    "2752",
                    "El número de ítem no puede estar duplicado.",
                )
            seen_ids.add(line_id)

        # ERROR 2138: CreditedQuantity@unitCode obligatorio
        qty = line.find("cbc:CreditedQuantity", namespaces=_NS)
        if qty is not None:
            unit_code = qty.get("unitCode")
            if unit_code is None or unit_code == "":
                add_error(
                    errors,
                    "2138",
                    "CreditedQuantity/@unitCode - El dato ingresado no cumple con el estandar",
                )

        # ERROR 2139: CreditedQuantity formato
        qty_text = text(line, "cbc:CreditedQuantity", _NS)
        if qty_text is not None and not matches(
            qty_text, r"^\d{1,12}(\.\d{1,10})?$"
        ):
            add_error(
                errors,
                "2139",
                "CreditedQuantity - El dato ingresado no cumple con el estandar",
            )

        # ERROR 3230: afectación 17 solo con tipo de nota 12
        tax_exempt = text(
            line,
            "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:TaxExemptionReasonCode",
            _NS,
        )
        if tax_exempt == "17" and resp_code != "12":
            add_error(
                errors,
                "3230",
                "Tipo de nota debe ser 'Ajustes afectos al IVAP'",
            )

        # ERROR 3221: tipo 12 no admite tributos 9995/9997/9998
        if resp_code == "12":
            tax_codes = {
                text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", _NS)
                for ts in all_(line, "cac:TaxTotal/cac:TaxSubtotal", _NS)
            }
            if tax_codes.intersection({"9995", "9997", "9998"}):
                add_error(
                    errors,
                    "3221",
                    "El dato ingresado como codigo de tributo global es invalido para tipo de nota",
                )

        # ERROR 3315: tipo 13 -> Percent = 0
        if resp_code == "13":
            percent = text(
                line,
                "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent",
                _NS,
            )
            if percent is not None and parse_amount(percent) != Decimal("0"):
                add_error(
                    errors,
                    "3315",
                    "Si el tipo de nota de credito es 13, el Importe total debe ser cero",
                )

        # ERROR 2410: PriceTypeCode catálogo 16
        alt_prices = all_(
            line,
            "cac:PricingReference/cac:AlternativeConditionPrice",
            _NS,
        )
        for alt in alt_prices:
            ptc = text(alt, "cbc:PriceTypeCode", _NS)
            if ptc is None:
                add_error(
                    errors,
                    "2410",
                    "Se ha consignado un valor invalido en el campo cbc:PriceTypeCode",
                )
            elif ptc not in _CATALOG16:
                add_error(
                    errors,
                    "2410",
                    "Se ha consignado un valor invalido en el campo cbc:PriceTypeCode",
                )

        # ERROR 3051: nombre de tributo vs código
        for ts in all_(line, "cac:TaxTotal/cac:TaxSubtotal", _NS):
            code = _tax_code(ts)
            name = _tax_name(ts)
            if code in CATALOG05_NAMES:
                expected = CATALOG05_NAMES[code]
                if name != expected:
                    add_error(
                        errors,
                        "3051",
                        "Nombre de tributo no corresponde al código de tributo de la linea.",
                    )

        # ERROR 3064: valor del concepto por línea
        for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", _NS):
            code = text(prop, "cbc:NameCode", _NS)
            if code in _VALUE_CONCEPTS:
                value = text(prop, "cbc:Value", _NS)
                if value is None or value == "":
                    add_error(
                        errors,
                        "3064",
                        "El XML no contiene tag o no existe información del valor del concepto por linea.",
                    )

        # ERROR 3243: fecha del concepto por línea (concepto 7014)
        for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", _NS):
            code = text(prop, "cbc:NameCode", _NS)
            if code == "7014":
                start_date = text(
                    prop, "cac:UsabilityPeriod/cbc:StartDate", _NS
                )
                if start_date is None:
                    add_error(
                        errors,
                        "3243",
                        "El XML no contiene tag o no existe información de la fecha del concepto por linea",
                    )


def _validate_payment_terms(
    root: etree._Element, errors: list[ValidationError]
) -> None:
    resp_code = _resp_code(root)
    terms = all_(root, "cac:PaymentTerms", _NS)
    customer_type = _customer_type(root)
    forma_pago_terms = [pt for pt in terms if text(pt, "cbc:ID", _NS) == "FormaPago"]

    # ERROR 3257: tipo 13 requiere FormaPago
    if resp_code == "13" and not forma_pago_terms:
        add_error(
            errors,
            "3257",
            "Para el tipo de nota de credito 13 debe consignar información de la operación al credito",
        )

    means_ids: list[str | None] = []
    has_credito = False
    has_contado = False
    for pt in forma_pago_terms:
        means_id = text(pt, "cbc:PaymentMeansID", _NS)
        means_ids.append(means_id)

        # ERROR 3245: PaymentMeansID obligatorio
        if means_id is None:
            add_error(
                errors,
                "3245",
                "Debe informar si el tipo de transaccion es al Contado o al Credito",
            )
            continue

        if means_id == "Credito":
            has_credito = True
        if means_id == "Contado":
            has_contado = True

        # ERROR 3246: valores permitidos
        if means_id not in {"Contado", "Credito"} and not matches(
            means_id, r"^Cuota\d{3}$"
        ):
            add_error(
                errors,
                "3246",
                "El tipo de transaccion o el identificador de la cuota no cumple con el formato esperado",
            )

        # ERROR 3320: cliente RUC para crédito tipo 13
        if (
            means_id == "Credito"
            and resp_code == "13"
            and customer_type != "6"
        ):
            add_error(
                errors,
                "3320",
                "El monto neto pendiente de pago debe ser menor o igual al monto de la factura",
            )

    # ERROR 3248: PaymentMeansID repetido
    non_none = [m for m in means_ids if m is not None]
    if len(non_none) != len(set(non_none)):
        add_error(
            errors,
            "3248",
            "El tipo de transaccion o el identificador de la cuota no debe repetirse en el comprobante",
        )

    cuotas = [
        pt
        for pt in forma_pago_terms
        if matches(text(pt, "cbc:PaymentMeansID", _NS) or "", r"^Cuota\d{3}$")
    ]

    # ERROR 3252: si existe cuota debe existir Crédito
    if cuotas and not has_credito:
        add_error(
            errors,
            "3252",
            "Si existe información de cuota de pago, el tipo de transaccion debe ser al credito",
        )

    if has_credito and customer_type == "6":
        # ERROR 3249: al menos una cuota
        if not cuotas:
            add_error(
                errors,
                "3249",
                "Si el tipo de transaccion es al Credito debe existir al menos información de una cuota de pago",
            )

        # ERROR 3251 / 3250: monto neto pendiente
        net_term = next(
            (
                pt
                for pt in forma_pago_terms
                if text(pt, "cbc:PaymentMeansID", _NS) == "Credito"
            ),
            None,
        )
        net_amount: Decimal | None = None
        if net_term is not None:
            net_text = text(net_term, "cbc:Amount", _NS)
            if net_text is None:
                add_error(
                    errors,
                    "3251",
                    "Si el tipo de transaccion es al Credito debe consignarse el Monto neto pendiente de pago",
                )
            elif not _positive_amount(net_text):
                add_error(
                    errors,
                    "3250",
                    "El Monto neto pendiente de pago no cumple el formato definido",
                )
            else:
                net_amount = parse_amount(net_text)

        # ERROR 3319: suma de cuotas = monto neto
        if net_amount is not None:
            sum_cuotas = sum(
                parse_amount(text(c, "cbc:Amount", _NS)) or Decimal("0")
                for c in cuotas
            )
            if sum_cuotas != net_amount:
                add_error(
                    errors,
                    "3319",
                    "La suma de las cuotas debe ser igual al Monto neto pendiente de pago.",
                )

        for c in cuotas:
            # ERROR 3254 / 3253: monto de cuota
            cuota_amount_text = text(c, "cbc:Amount", _NS)
            if cuota_amount_text is None:
                add_error(
                    errors,
                    "3254",
                    "Si se consigna información de la cuota de pago, debe indicarse el monto de la cuota",
                )
            elif not _positive_amount(cuota_amount_text):
                add_error(
                    errors,
                    "3253",
                    "El Monto del pago único o de las cuotas no cumple el formato definido",
                )

            # ERROR 3256 / 3255: fecha de cuota
            due_date = text(c, "cbc:PaymentDueDate", _NS)
            if due_date is None:
                add_error(
                    errors,
                    "3256",
                    "Si se consigna información de la cuota de pago, debe indicarse la fecha del pago único o de las cuotas",
                )
            elif not matches(due_date, r"^\d{4}-\d{2}-\d{2}$"):
                add_error(
                    errors,
                    "3255",
                    "Fecha del pago único o de las cuotas no cumple el formato definido",
                )
            else:
                # ERROR 3321: fecha de cuota > fecha de emisión
                issue = text(root, "cbc:IssueDate", _NS)
                if issue is not None and due_date <= issue:
                    add_error(
                        errors,
                        "3321",
                        "La fecha de la cuota debe ser mayor a la fecha de emisión de la factura",
                    )


def _validate_totals(root: etree._Element, errors: list[ValidationError]) -> None:
    ref_type = _ref_doc_type(root)
    if ref_type != "01":
        return

    lines = all_(root, "cac:CreditNoteLine", _NS)

    line_bases: dict[str, Decimal] = {}
    line_taxes: dict[str, Decimal] = {}
    line_exts_by_tax: dict[str, Decimal] = {}
    line_percents: dict[str, Decimal] = {}
    igv_percents: list[Decimal] = []

    for line in lines:
        line_ext = parse_amount(text(line, "cbc:LineExtensionAmount", _NS)) or Decimal("0")
        gratuita = False
        for ts in all_(line, "cac:TaxTotal/cac:TaxSubtotal", _NS):
            code = _tax_code(ts)
            base = _taxable_amount(ts) or Decimal("0")
            tax = _tax_amount(ts) or Decimal("0")
            if code is None:
                continue
            line_bases[code] = line_bases.get(code, Decimal("0")) + base
            line_taxes[code] = line_taxes.get(code, Decimal("0")) + tax
            if base > 0:
                line_exts_by_tax[code] = line_exts_by_tax.get(code, Decimal("0")) + line_ext
            if code in {"1000", "1016"}:
                pct = _percent(ts)
                if pct is not None:
                    line_percents[code] = pct
            if code == "1000" and base > 0:
                pct = _percent(ts)
                if pct is not None:
                    igv_percents.append(pct)
            if code == "9996" and base > 0:
                exempt = _exemption_code(ts)
                if exempt in {"11", "12", "13", "14", "15", "16"}:
                    pct = _percent(ts)
                    if pct is not None:
                        igv_percents.append(pct)
            if code == "9996" and base > 0:
                gratuita = True

    global_subtotals = all_(root, "cac:TaxTotal/cac:TaxSubtotal", _NS)
    global_bases: dict[str, Decimal] = {}
    global_taxes: dict[str, Decimal] = {}
    global_total_tax = parse_amount(text(root, "cac:TaxTotal/cbc:TaxAmount", _NS))

    for sub in global_subtotals:
        code = _tax_code(sub)
        base = _taxable_amount(sub)
        tax = _tax_amount(sub)
        if code is None:
            continue
        if base is not None:
            global_bases[code] = base
        if tax is not None:
            global_taxes[code] = tax

    # ERROR 3273 / 3274 / 3275 / 3276
    if "9995" in global_bases:
        expected = line_exts_by_tax.get("9995", Decimal("0"))
        if not _within_tolerance(global_bases["9995"], expected):
            add_error(
                errors,
                "3273",
                "La sumatoria del total valor de venta - Exportaciones de línea no corresponden al total",
            )
    if "9998" in global_bases:
        expected = line_exts_by_tax.get("9998", Decimal("0"))
        if not _within_tolerance(global_bases["9998"], expected):
            add_error(
                errors,
                "3274",
                "La sumatoria del total valor de venta - operaciones inafectas de línea no corresponden al total",
            )
    if "9997" in global_bases:
        expected = line_exts_by_tax.get("9997", Decimal("0"))
        if not _within_tolerance(global_bases["9997"], expected):
            add_error(
                errors,
                "3275",
                "La sumatoria del total valor de venta - operaciones exoneradas de línea no corresponden al total",
            )
    if "9996" in global_bases:
        expected = line_exts_by_tax.get("9996", Decimal("0"))
        if not _within_tolerance(global_bases["9996"], expected):
            add_error(
                errors,
                "3276",
                "La sumatoria del total valor de venta - operaciones gratuitas de línea no corresponden al total",
            )

    # ERROR 3291 / 3295
    if "1000" in global_bases and "1000" in global_taxes:
        pct = line_percents.get("1000")
        if pct is not None:
            expected = (global_bases["1000"] * pct) / Decimal("100")
            if not _within_tolerance(global_taxes["1000"], expected):
                add_error(
                    errors,
                    "3291",
                    "El cálculo del IGV es Incorrecto",
                )
    if "1016" in global_bases and "1016" in global_taxes:
        pct = line_percents.get("1016")
        if pct is not None:
            expected = (global_bases["1016"] * pct) / Decimal("100")
            if not _within_tolerance(global_taxes["1016"], expected):
                add_error(
                    errors,
                    "3295",
                    "El importe del IVAP no corresponden al determinado por la informacion consignada.",
                )

    # ERROR 3296 / 3297: base ISC / Otros
    if "2000" in global_bases:
        expected = line_bases.get("2000", Decimal("0"))
        if not _within_tolerance(global_bases["2000"], expected):
            add_error(
                errors,
                "3296",
                "La sumatoria del monto base - ISC de línea no corresponden al total",
            )
    if "9999" in global_bases:
        expected = line_bases.get("9999", Decimal("0"))
        if not _within_tolerance(global_bases["9999"], expected):
            add_error(
                errors,
                "3297",
                "La sumatoria del monto base - Otros tributos de línea no corresponden al total",
            )

    # ERROR 3298 / 3299: tax ISC / Otros
    if "2000" in global_taxes:
        expected = line_taxes.get("2000", Decimal("0"))
        if not _within_tolerance(global_taxes["2000"], expected):
            add_error(
                errors,
                "3298",
                "La sumatoria del total del importe del tributo ISC de línea no corresponden al total",
            )
    if "9999" in global_taxes:
        expected = line_taxes.get("9999", Decimal("0"))
        if not _within_tolerance(global_taxes["9999"], expected):
            add_error(
                errors,
                "3299",
                "La sumatoria del total del importe del tributo Otros tributos de línea no corresponden al total",
            )

    # ERROR 3292: TaxTotal global vs suma de impuestos por línea
    if global_total_tax is not None:
        expected_tax = sum(
            line_taxes.get(code, Decimal("0"))
            for code in ("1000", "1016", "2000", "7152", "9999")
        )
        if not _within_tolerance(global_total_tax, expected_tax):
            add_error(
                errors,
                "3292",
                "El importe total de impuestos por línea no coincide con la sumatoria de los impuestos por línea.",
            )

    # ERROR 3462: tasa IGV única y vigente
    if len(set(igv_percents)) > 1:
        add_error(
            errors,
            "3462",
            "La tasa del IGV debe ser la misma en todas las líneas o ítems del documento y debe corresponder con una tasa vigente.",
        )
    for pct in igv_percents:
        if pct not in {Decimal("18.00"), Decimal("10.50"), Decimal("10.00")}:
            add_error(
                errors,
                "3462",
                "La tasa del IGV debe ser la misma en todas las líneas o ítems del documento y debe corresponder con una tasa vigente.",
            )

    # ERROR 3280: importe total calculado
    _validate_payable_amount(root, errors, line_bases, line_taxes)


def _validate_payable_amount(
    root: etree._Element,
    errors: list[ValidationError],
    line_bases: dict[str, Decimal],
    line_taxes: dict[str, Decimal],
) -> None:
    payable_text = text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount", _NS)
    if payable_text is None:
        return
    payable = parse_amount(payable_text)
    if payable is None:
        return

    line_ext_total = sum(
        parse_amount(text(line, "cbc:LineExtensionAmount", _NS)) or Decimal("0")
        for line in all_(root, "cac:CreditNoteLine", _NS)
    )

    tax_total = parse_amount(text(root, "cac:TaxTotal/cbc:TaxAmount", _NS)) or Decimal("0")

    charges = Decimal("0")
    allowances = Decimal("0")
    for ac in all_(root, "cac:AllowanceCharge", _NS):
        indicator = text(ac, "cbc:ChargeIndicator", _NS)
        amount = parse_amount(text(ac, "cbc:Amount", _NS)) or Decimal("0")
        if indicator == "true":
            charges += amount
        elif indicator == "false":
            allowances += amount

    rounding = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:PayableRoundingAmount", _NS)
    ) or Decimal("0")

    expected = line_ext_total + tax_total + charges - allowances + rounding
    if not _within_tolerance(payable, expected):
        add_error(
            errors,
            "3280",
            "El importe total del comprobante no coincide con el valor calculado",
        )


def _validate_mortgage(root: etree._Element, errors: list[ValidationError]) -> None:
    for line in all_(root, "cac:CreditNoteLine", _NS):
        codes = _item_property_codes(line)
        producto = "7000" in codes
        indicador_3 = "7002" in codes
        if producto:
            if "7004" not in codes:
                add_error(
                    errors,
                    "3152",
                    "El XML no contiene el tag de Créditos Hipotecarios: Número de contrato",
                )
            if "7005" not in codes:
                add_error(
                    errors,
                    "3153",
                    "El XML no contiene el tag de Créditos Hipotecarios: Fecha de otorgamiento del crédito",
                )
            if indicador_3:
                if "7003" not in codes:
                    add_error(
                        errors,
                        "3151",
                        "El XML no contiene el tag de Créditos Hipotecarios: Partida Registral",
                    )
                if "7006" not in codes:
                    add_error(
                        errors,
                        "3154",
                        "El XML no contiene el tag de Créditos Hipotecarios: Dirección del predio - Código de ubigeo",
                    )
                if "7007" not in codes:
                    add_error(
                        errors,
                        "3155",
                        "El XML no contiene el tag de Créditos Hipotecarios: Dirección del predio - Dirección completa",
                    )


def _validate_contracts(root: etree._Element, errors: list[ValidationError]) -> None:
    contracts = all_(root, "cac:ContractDocumentReference", _NS)
    ids = [text(c, "cbc:ID", _NS) for c in contracts if text(c, "cbc:ID", _NS) is not None]

    # ERROR 3498: más de un número de contrato
    if len(ids) > 1:
        add_error(
            errors,
            "3498",
            "No se permite mas de un numero de contrato de colaboracion empresarial",
        )

    for contract in contracts:
        doc_type = text(contract, "cbc:DocumentTypeCode", _NS)
        doc_id = text(contract, "cbc:ID", _NS)
        doc_desc = text(contract, "cbc:DocumentDescription", _NS)
        percent = text(
            contract,
            "cac:IssuerParty/cac:PartyLegalEntity/cac:ShareholderParty/cbc:PartecipationPercent",
            _NS,
        )

        # ERROR 3497: tipo de contrato 1 o 2
        if doc_type is not None and doc_type not in {"1", "2"}:
            add_error(
                errors,
                "3497",
                "El tipo de contrato debe ser 1-ventas o 2-adquisiciones",
            )

        # ERROR 3501: número de contrato formato
        if doc_id is not None:
            if not matches(doc_id, r"^.{1,50}$") or doc_id.strip() == "":
                add_error(
                    errors,
                    "3501",
                    "El Numero del contrato de colaboracion empresarial no cumple el formato o longitud establecida",
                )

        # ERROR 3502: descripción formato
        if doc_desc is not None:
            if not matches(doc_desc, r"^.{1,250}$") or doc_desc.strip() == "":
                add_error(
                    errors,
                    "3502",
                    "La Descripcion del contrato de colaboracion empresarial no cumple el formato o longitud especificada",
                )

        # ERROR 3500: porcentaje formato
        if percent is not None:
            if not _format_percent(percent):
                add_error(
                    errors,
                    "3500",
                    "El Porcentaje de participacion no cumple con el formato o longitud especificada",
                )

        # ERROR 3499: completitud
        if doc_id is not None and (
            doc_type is None or doc_desc is None or percent is None
        ):
            add_error(
                errors,
                "3499",
                "Si informa Numero de contrato, debe consignar el Tipo de contrato, la Descripcion de contrato y el Porcentaje de participacion",
            )


def _validate_currency(root: etree._Element, errors: list[ValidationError]) -> None:
    currency = _doc_currency(root)
    if currency is not None and currency not in _CATALOG02:
        add_error(
            errors,
            "3088",
            "El valor ingresado como moneda del comprobante no es valido (catalogo nro 02).",
        )
