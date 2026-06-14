"""Validaciones SUNAT adicionales para Invoice (batch 3).

Códigos implementados: 3220, 3223, 3224, 3233, 3234, 3241, 3242, 3243, 3244,
3245, 3246, 3247, 3248, 3249, 3250, 3251, 3252, 3253, 3254, 3255, 3256, 3262,
3263, 3264, 3265, 3266, 3267, 3270, 3271, 3272, 3273, 3274, 3275, 3276, 3277,
3278, 3279, 3280, 3282, 3286, 3287, 3288, 3290, 3291, 3292, 3293, 3294, 3295,
3296, 3297, 3298, 3299, 3300, 3301, 3302, 3303, 3305, 3306, 3307, 3308, 3309,
3310, 3311, 3318, 3319, 3330, 3461.

Fuente de verdad:
- Excel "Reglas de validación actualizado al 24.04.2026" publicado en
  https://cpe.sunat.gob.pe/guias-y-manuales
- rules_Invoice.txt
"""

from decimal import Decimal
from lxml import etree

from openubl.models.catalog import Catalog6, Catalog7, Catalog51
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
)


_TOLERANCE = Decimal("1")
_NSMAP = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}


def _norm_catalog(value: str | None, enum_cls) -> str | None:
    """Normaliza valores tipo 'Catalog7.GRAVADO...' al código numérico SUNAT."""
    if value is None:
        return None
    if "." in value:
        name = value.split(".")[-1]
        try:
            return enum_cls[name].value
        except KeyError:
            pass
    return value


def _tipo_operacion(root: etree._Element) -> str | None:
    """Devuelve el código numérico del tipo de operación (Catálogo 51)."""
    val = attr(root, "cbc:InvoiceTypeCode", "listID", NS_INVOICE)
    if val is None:
        val = text(root, "cbc:Note", NS_INVOICE)
    return _norm_catalog(val, Catalog51)


def _customer_type(root: etree._Element) -> str | None:
    val = attr(
        root,
        "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
        "schemeID",
        NS_INVOICE,
    )
    return _norm_catalog(val, Catalog6)


def _line_tax_subtotals(line: etree._Element):
    for ts in all_(line, "cac:TaxTotal/cac:TaxSubtotal", NS_INVOICE):
        code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_INVOICE)
        taxable = parse_amount(text(ts, "cbc:TaxableAmount", NS_INVOICE))
        tax = parse_amount(text(ts, "cbc:TaxAmount", NS_INVOICE))
        percent = parse_amount(text(ts, "cac:TaxCategory/cbc:Percent", NS_INVOICE))
        af = _norm_catalog(
            text(ts, "cac:TaxCategory/cbc:TaxExemptionReasonCode", NS_INVOICE),
            Catalog7,
        )
        yield {
            "code": code,
            "taxable": taxable,
            "tax": tax,
            "percent": percent,
            "afectacion": af,
        }


def _global_tax_subtotals(root: etree._Element):
    for ts in all_(root, "cac:TaxTotal/cac:TaxSubtotal", NS_INVOICE):
        code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_INVOICE)
        taxable = parse_amount(text(ts, "cbc:TaxableAmount", NS_INVOICE))
        tax = parse_amount(text(ts, "cbc:TaxAmount", NS_INVOICE))
        percent = parse_amount(text(ts, "cac:TaxCategory/cbc:Percent", NS_INVOICE))
        yield {"code": code, "taxable": taxable, "tax": tax, "percent": percent}


def _allowance_charges(elem: etree._Element):
    for ac in all_(elem, "cac:AllowanceCharge", NS_INVOICE):
        ind = text(ac, "cbc:ChargeIndicator", NS_INVOICE)
        reason = text(ac, "cbc:AllowanceChargeReasonCode", NS_INVOICE)
        factor = parse_amount(text(ac, "cbc:MultiplierFactorNumeric", NS_INVOICE))
        amount = parse_amount(text(ac, "cbc:Amount", NS_INVOICE))
        base = parse_amount(text(ac, "cbc:BaseAmount", NS_INVOICE))
        yield {
            "indicator": ind,
            "reason": reason,
            "factor": factor,
            "amount": amount,
            "base": base,
        }


def _payment_terms(root: etree._Element):
    for pt in all_(root, "cac:PaymentTerms", NS_INVOICE):
        pt_id = text(pt, "cbc:ID", NS_INVOICE)
        means = text(pt, "cbc:PaymentMeansID", NS_INVOICE)
        amount = parse_amount(text(pt, "cbc:Amount", NS_INVOICE))
        due = text(pt, "cbc:PaymentDueDate", NS_INVOICE)
        yield {"id": pt_id, "means": means, "amount": amount, "due": due}


def _is_gratuita_line(line: etree._Element) -> bool:
    for info in _line_tax_subtotals(line):
        if info["code"] == "9996" and info["taxable"] is not None and info["taxable"] > 0:
            return True
    return False


def _line_amount(ac_iter, indicator: str, reasons: set[str]) -> Decimal:
    total = Decimal("0")
    for ac in ac_iter:
        if ac["indicator"] == indicator and ac["reason"] in reasons and ac["amount"] is not None:
            total += ac["amount"]
    return total


def _global_ac_amount(root: etree._Element, indicator: str, reasons: set[str]) -> Decimal:
    return _line_amount(_allowance_charges(root), indicator, reasons)


# ---------------------------------------------------------------------------
# Reglas de anticipos / prepagos
# ---------------------------------------------------------------------------

def _check_3220(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3220: si hay PrepaidPayment/PaidAmount > 0 debe existir PrepaidAmount > 0."""
    prepaid_amounts = all_(root, "cac:PrepaidPayment/cbc:PaidAmount", NS_INVOICE)
    has_positive = any(
        parse_amount(p.text) is not None and parse_amount(p.text) > 0
        for p in prepaid_amounts
    )
    if not has_positive:
        return
    total = parse_amount(text(root, "cac:LegalMonetaryTotal/cbc:PrepaidAmount", NS_INVOICE))
    if total is None or total <= 0:
        add_error(errors, "3220", "Si consigna montos de anticipo debe informar el Total de Anticipos")


def _check_3282(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3282: descuentos globales por anticipo requieren PrepaidAmount > 0."""
    for ac in _allowance_charges(root):
        if (
            ac["indicator"] == "false"
            and ac["reason"] in {"04", "05", "06"}
            and ac["amount"] is not None
            and ac["amount"] > 0
        ):
            total = parse_amount(
                text(root, "cac:LegalMonetaryTotal/cbc:PrepaidAmount", NS_INVOICE)
            )
            if total is None or total <= 0:
                add_error(
                    errors,
                    "3282",
                    "Si se informa descuentos globales por anticipo debe existir 'Total de anticipos' con monto mayor a cero",
                )
                return


def _check_3287(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3287: PrepaidAmount > 0 requiere descuentos globales por anticipo."""
    total = parse_amount(text(root, "cac:LegalMonetaryTotal/cbc:PrepaidAmount", NS_INVOICE))
    if total is None or total <= 0:
        return
    has_desc = False
    for ac in _allowance_charges(root):
        if (
            ac["indicator"] == "false"
            and ac["reason"] in {"04", "05", "06"}
            and ac["amount"] is not None
            and ac["amount"] > 0
        ):
            has_desc = True
            break
    if not has_desc:
        add_error(
            errors,
            "3287",
            "Si se informa 'Total de anticipos' debe consignar los descuentos globales por anticipo con monto mayor a cero",
        )


# ---------------------------------------------------------------------------
# Reglas de tributos por línea
# ---------------------------------------------------------------------------

def _check_3223(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3223: combinaciones permitidas de tributos por línea."""
    allowed = [
        {"1000", "2000", "9999"},
        {"1016", "9999"},
        {"9995", "9999"},
        {"9996", "2000", "9999"},
        {"9997", "2000", "9999"},
        {"9998", "2000", "9999"},
    ]
    for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
        codes = {
            info["code"]
            for info in _line_tax_subtotals(line)
            if info["taxable"] is not None and info["taxable"] > 0
        }
        if not codes:
            continue
        if not any(codes <= combo for combo in allowed):
            add_error(errors, "3223", "La combinación de tributos no es permitida")
            return


def _check_3224_and_3234(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3224 y 3234: relación entre operación gratuita y código de precio 02."""
    for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
        price_type = text(
            line,
            "cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceTypeCode",
            NS_INVOICE,
        )
        price_amount = parse_amount(
            text(
                line,
                "cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount",
                NS_INVOICE,
            )
        )
        gratuita = _is_gratuita_line(line)
        if not gratuita and price_type == "02" and price_amount is not None and price_amount > 0:
            add_error(
                errors,
                "3224",
                "Si existe 'Valor referencial unitario en operac. no onerosas' con monto mayor a cero, la operacion debe ser gratuita",
            )
        if gratuita and price_type is not None and price_type != "02":
            add_error(
                errors,
                "3234",
                "El código de precio '02' es sólo para operaciones gratuitas",
            )


def _check_3270(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3270: precio unitario en operaciones onerosas."""
    for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
        if _is_gratuita_line(line):
            continue
        qty = parse_amount(text(line, "cbc:InvoicedQuantity", NS_INVOICE))
        price = parse_amount(
            text(
                line,
                "cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount",
                NS_INVOICE,
            )
        )
        if qty is None or price is None or qty <= 0:
            continue
        line_ext = parse_amount(text(line, "cbc:LineExtensionAmount", NS_INVOICE))
        tax_total = parse_amount(text(line, "cac:TaxTotal/cbc:TaxAmount", NS_INVOICE))
        disc = _line_amount(_allowance_charges(line), "false", {"01"})
        cargo = _line_amount(_allowance_charges(line), "true", {"48"})
        base = (line_ext or Decimal("0")) + (tax_total or Decimal("0")) - disc + cargo
        expected = base / qty
        if abs(price - expected) > _TOLERANCE:
            add_error(
                errors,
                "3270",
                "El precio unitario de la operación difiere de los cálculos realizados",
            )
            return


def _check_3271(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3271: valor de venta por ítem."""
    for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
        line_ext = parse_amount(text(line, "cbc:LineExtensionAmount", NS_INVOICE))
        qty = parse_amount(text(line, "cbc:InvoicedQuantity", NS_INVOICE))
        if line_ext is None or qty is None:
            continue
        gratuita = _is_gratuita_line(line)
        if gratuita:
            unit = parse_amount(
                text(
                    line,
                    "cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount",
                    NS_INVOICE,
                )
            )
        else:
            unit = parse_amount(
                text(line, "cac:Price/cbc:PriceAmount", NS_INVOICE)
            )
        if unit is None:
            continue
        disc_base = _line_amount(_allowance_charges(line), "false", {"00"})
        cargo_base = _line_amount(_allowance_charges(line), "true", {"47"})
        expected = unit * qty - disc_base + cargo_base
        if abs(line_ext - expected) > _TOLERANCE:
            add_error(errors, "3271", "El valor de venta por ítem difiere de los importes consignados")
            return


def _check_3272(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3272: monto base por línea."""
    for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
        line_ext = parse_amount(text(line, "cbc:LineExtensionAmount", NS_INVOICE))
        if line_ext is None:
            continue
        has_isc = False
        isc_tax = Decimal("0")
        for info in _line_tax_subtotals(line):
            if info["code"] == "2000" and info["taxable"] is not None and info["taxable"] > 0:
                has_isc = True
                isc_tax = info["tax"] or Decimal("0")
                expected = line_ext + isc_tax
                if abs(info["taxable"] - expected) > _TOLERANCE:
                    add_error(
                        errors,
                        "3272",
                        "La base imponible a nivel de línea difiere de la información consignada",
                    )
                    return
        if not has_isc:
            for info in _line_tax_subtotals(line):
                if (
                    info["code"] not in {"2000", "9999"}
                    and info["taxable"] is not None
                    and info["taxable"] > 0
                    and abs(info["taxable"] - line_ext) > _TOLERANCE
                ):
                    add_error(
                        errors,
                        "3272",
                        "La base imponible a nivel de línea difiere de la información consignada",
                    )
                    return


def _check_3290(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3290: monto de cargo/descuento por línea = base * factor."""
    for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
        for ac in _allowance_charges(line):
            if ac["reason"] is None:
                continue
            if ac["factor"] is not None and ac["factor"] > 0:
                if ac["base"] is None or ac["amount"] is None:
                    continue
                expected = ac["base"] * ac["factor"]
                if abs(ac["amount"] - expected) > _TOLERANCE:
                    add_error(
                        errors,
                        "3290",
                        "El valor de cargo/descuento por ítem difiere de los importes consignados",
                    )
                    return


def _check_3292(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3292: monto total de tributos por línea = suma de tributos."""
    codes = {"1000", "1016", "2000", "7152", "9999"}
    for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
        total = parse_amount(text(line, "cac:TaxTotal/cbc:TaxAmount", NS_INVOICE))
        if total is None:
            continue
        subtotal = sum(
            (info["tax"] or Decimal("0"))
            for info in _line_tax_subtotals(line)
            if info["code"] in codes
        )
        if abs(total - subtotal) > _TOLERANCE:
            add_error(
                errors,
                "3292",
                "El importe total de impuestos por línea no coincide con la sumatoria de los impuestos por línea",
            )
            return


# ---------------------------------------------------------------------------
# Reglas de tributos globales
# ---------------------------------------------------------------------------

def _check_3294(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3294: monto total de tributos global = suma de tributos globales."""
    codes = {"1000", "1016", "2000", "7152", "9999"}
    total = parse_amount(text(root, "cac:TaxTotal/cbc:TaxAmount", NS_INVOICE))
    if total is None:
        return
    subtotal = sum(
        (info["tax"] or Decimal("0"))
        for info in _global_tax_subtotals(root)
        if info["code"] in codes
    )
    if abs(total - subtotal) > _TOLERANCE:
        add_error(
            errors,
            "3294",
            "La sumatoria de impuestos globales no corresponde al monto total de impuestos",
        )


def _check_taxable_sum(
    root: etree._Element,
    errors: list[ValidationError],
    code: str,
    error_code: str,
    message: str,
    adjust: Decimal = Decimal("0"),
) -> None:
    for info in _global_tax_subtotals(root):
        if info["code"] == code and info["taxable"] is not None:
            s = Decimal("0")
            for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
                line_ext = parse_amount(text(line, "cbc:LineExtensionAmount", NS_INVOICE))
                for li in _line_tax_subtotals(line):
                    if li["code"] == code and li["taxable"] is not None and li["taxable"] > 0:
                        s += line_ext or Decimal("0")
            expected = s + adjust
            if abs(info["taxable"] - expected) > _TOLERANCE:
                add_error(errors, error_code, message)
            return


def _check_3273_3274_3275_3276(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3273-3276: sumatorias de valor de venta global por tipo de operación."""
    # 9995 exportación
    _check_taxable_sum(
        root,
        errors,
        "9995",
        "3273",
        "La sumatoria del total valor de venta - Exportaciones de línea no corresponden al total",
    )
    # 9997 exoneradas
    disc_exo = _global_ac_amount(root, "false", {"05"})
    _check_taxable_sum(
        root,
        errors,
        "9997",
        "3275",
        "La sumatoria del total valor de venta - operaciones exoneradas de línea no corresponden al total",
        adjust=-disc_exo,
    )
    # 9998 inafectas
    disc_ina = _global_ac_amount(root, "false", {"06"})
    _check_taxable_sum(
        root,
        errors,
        "9998",
        "3274",
        "La sumatoria del total valor de venta - operaciones inafectas de línea no corresponden al total",
        adjust=-disc_ina,
    )
    # 9996 gratuitas
    _check_taxable_sum(
        root,
        errors,
        "9996",
        "3276",
        "La sumatoria del total valor de venta - operaciones gratuitas de línea no corresponden al total",
    )


def _check_3277_3293(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3277 / 3293: total valor de venta operaciones gravadas IGV / IVAP."""
    disc = _global_ac_amount(root, "false", {"02", "04"})
    cargo = _global_ac_amount(root, "true", {"49"})
    adjust = cargo - disc

    for info in _global_tax_subtotals(root):
        if info["code"] == "1000" and info["taxable"] is not None:
            s = Decimal("0")
            for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
                line_ext = parse_amount(text(line, "cbc:LineExtensionAmount", NS_INVOICE))
                for li in _line_tax_subtotals(line):
                    if li["code"] == "1000" and li["taxable"] is not None and li["taxable"] > 0:
                        s += line_ext or Decimal("0")
            if abs(info["taxable"] - (s + adjust)) > _TOLERANCE:
                add_error(
                    errors,
                    "3277",
                    "La sumatoria del total valor de venta - operaciones gravadas de línea no corresponden al total",
                )
        if info["code"] == "1016" and info["taxable"] is not None:
            s = Decimal("0")
            for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
                line_ext = parse_amount(text(line, "cbc:LineExtensionAmount", NS_INVOICE))
                for li in _line_tax_subtotals(line):
                    if li["code"] == "1016" and li["taxable"] is not None and li["taxable"] > 0:
                        s += line_ext or Decimal("0")
            if abs(info["taxable"] - (s + adjust)) > _TOLERANCE:
                add_error(
                    errors,
                    "3293",
                    "La sumatoria del total valor de venta - IVAP de línea no corresponden al total",
                )


def _check_3291_3295(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3291 / 3295: monto de IGV / IVAP global."""
    disc = _global_ac_amount(root, "false", {"02", "04"})
    cargo = _global_ac_amount(root, "true", {"49"})
    anticipo_isc = _global_ac_amount(root, "false", {"20"})

    for info in _global_tax_subtotals(root):
        if info["code"] == "1000" and info["tax"] is not None:
            base = Decimal("0")
            rate = Decimal("0")
            for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
                for li in _line_tax_subtotals(line):
                    if li["code"] == "1000" and li["taxable"] is not None and li["taxable"] > 0:
                        base += li["taxable"]
                        if li["percent"] is not None:
                            rate = li["percent"]
            if rate == 0:
                rate = Decimal("18")
            expected = (base - disc + cargo - anticipo_isc) * (rate / Decimal("100"))
            if abs(info["tax"] - expected) > _TOLERANCE:
                add_error(errors, "3291", "El cálculo del IGV es Incorrecto")
        if info["code"] == "1016" and info["tax"] is not None:
            base = Decimal("0")
            rate = Decimal("0")
            for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
                for li in _line_tax_subtotals(line):
                    if li["code"] == "1016" and li["taxable"] is not None and li["taxable"] > 0:
                        base += li["taxable"]
                        if li["percent"] is not None:
                            rate = li["percent"]
            if rate == 0:
                rate = Decimal("4")
            expected = (base - disc + cargo) * (rate / Decimal("100"))
            if abs(info["tax"] - expected) > _TOLERANCE:
                add_error(errors, "3295", "El importe del IVAP no corresponden al determinado por la información consignada")


def _check_3296_3297(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3296 / 3297: base ISC / otros tributos global."""
    # 3296 ISC
    for info in _global_tax_subtotals(root):
        if info["code"] == "2000" and info["taxable"] is not None:
            s = Decimal("0")
            for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
                if _is_gratuita_line(line):
                    continue
                for li in _line_tax_subtotals(line):
                    if li["code"] == "2000" and li["taxable"] is not None and li["taxable"] > 0:
                        s += li["taxable"]
            if abs(info["taxable"] - s) > _TOLERANCE:
                add_error(
                    errors,
                    "3296",
                    "La sumatoria del monto base - ISC de línea no corresponden al total",
                )
    # 3297 otros tributos
    for info in _global_tax_subtotals(root):
        if info["code"] == "9999" and info["taxable"] is not None:
            s = Decimal("0")
            for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
                for li in _line_tax_subtotals(line):
                    if li["code"] == "9999" and li["taxable"] is not None and li["taxable"] > 0:
                        s += li["taxable"]
            if abs(info["taxable"] - s) > _TOLERANCE:
                add_error(
                    errors,
                    "3297",
                    "La sumatoria del monto base - Otros tributos de línea no corresponden al total",
                )


def _check_3298_3299_3302_3306(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3298, 3299, 3302, 3306: sumatorias de tributos globales."""
    anticipo_isc = _global_ac_amount(root, "false", {"20"})
    for info in _global_tax_subtotals(root):
        if info["code"] == "2000" and info["tax"] is not None:
            s = Decimal("0")
            for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
                if _is_gratuita_line(line):
                    continue
                for li in _line_tax_subtotals(line):
                    if li["code"] == "2000" and li["tax"] is not None and li["tax"] > 0:
                        s += li["tax"]
            if abs(info["tax"] - (s - anticipo_isc)) > _TOLERANCE:
                add_error(
                    errors,
                    "3298",
                    "La sumatoria del total del importe del tributo ISC de línea no corresponden al total",
                )
        if info["code"] == "9999" and info["tax"] is not None:
            s = Decimal("0")
            for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
                for li in _line_tax_subtotals(line):
                    if li["code"] == "9999" and li["tax"] is not None and li["tax"] > 0:
                        s += li["tax"]
            if abs(info["tax"] - s) > _TOLERANCE:
                add_error(
                    errors,
                    "3299",
                    "La sumatoria del total del importe del tributo Otros tributos de línea no corresponden al total",
                )
        if info["code"] == "9996" and info["tax"] is not None:
            s = Decimal("0")
            for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
                for li in _line_tax_subtotals(line):
                    if (
                        li["code"] == "9996"
                        and li["taxable"] is not None
                        and li["taxable"] > 0
                        and li["tax"] is not None
                    ):
                        s += li["tax"]
            if abs(info["tax"] - s) > _TOLERANCE:
                add_error(
                    errors,
                    "3302",
                    "La sumatoria de los IGV de operaciones gratuitas de la línea no corresponden al total",
                )
        if info["code"] == "7152" and info["tax"] is not None:
            s = Decimal("0")
            for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
                for li in _line_tax_subtotals(line):
                    if li["code"] == "7152" and li["tax"] is not None and li["tax"] > 0:
                        s += li["tax"]
            if abs(info["tax"] - s) > _TOLERANCE:
                add_error(
                    errors,
                    "3306",
                    "La sumatoria del total del importe del tributo ICBPER de línea no corresponden al total",
                )


# ---------------------------------------------------------------------------
# Reglas de totales monetarios
# ---------------------------------------------------------------------------

def _check_3278(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3278: LineExtensionAmount global."""
    total = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount", NS_INVOICE)
    )
    if total is None:
        return
    disc = _global_ac_amount(root, "false", {"02"})
    cargo = _global_ac_amount(root, "true", {"49"})
    s = Decimal("0")
    for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
        line_ext = parse_amount(text(line, "cbc:LineExtensionAmount", NS_INVOICE))
        if line_ext is None:
            continue
        for info in _line_tax_subtotals(line):
            if info["code"] in {"1000", "1016", "9995", "9997", "9998"} and info["taxable"] is not None and info["taxable"] > 0:
                s += line_ext
                break
    expected = s - disc + cargo
    if abs(total - expected) > _TOLERANCE:
        add_error(
            errors,
            "3278",
            "La sumatoria de valor de venta no corresponde a los importes consignados",
        )


def _check_3279(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3279: TaxInclusiveAmount global."""
    total = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", NS_INVOICE)
    )
    if total is None:
        return
    line_ext = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount", NS_INVOICE)
    )
    tax_sum = Decimal("0")
    for info in _global_tax_subtotals(root):
        if info["tax"] is not None:
            tax_sum += info["tax"]
    expected = (line_ext or Decimal("0")) + tax_sum
    if abs(total - expected) > _TOLERANCE:
        add_error(
            errors,
            "3279",
            "La sumatoria del Total del valor de venta más los impuestos no concuerda con la base imponible",
        )


def _check_3280(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3280: PayableAmount global."""
    payable = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount", NS_INVOICE)
    )
    if payable is None:
        return
    tax_inclusive = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", NS_INVOICE)
    )
    charge = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:ChargeTotalAmount", NS_INVOICE)
    )
    allowance = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:AllowanceTotalAmount", NS_INVOICE)
    )
    prepaid = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:PrepaidAmount", NS_INVOICE)
    )
    rounding = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:PayableRoundingAmount", NS_INVOICE)
    )
    expected = (
        (tax_inclusive or Decimal("0"))
        + (charge or Decimal("0"))
        - (allowance or Decimal("0"))
        - (prepaid or Decimal("0"))
        + (rounding or Decimal("0"))
    )
    if abs(payable - expected) > _TOLERANCE:
        add_error(
            errors,
            "3280",
            "El importe total del comprobante no coincide con el valor calculado",
        )


def _check_3288(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3288: LineExtensionAmount debe existir."""
    if not exists(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount", NS_INVOICE):
        add_error(errors, "3288", "Debe consignar el Total Valor de Venta")


def _check_3305(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3305: TaxInclusiveAmount debe existir."""
    if not exists(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", NS_INVOICE):
        add_error(errors, "3305", "Debe consignar el Total Precio de Venta")


def _check_3303(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3303: PayableRoundingAmount absoluto <= 1."""
    val = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:PayableRoundingAmount", NS_INVOICE)
    )
    if val is not None and abs(val) > Decimal("1"):
        add_error(
            errors,
            "3303",
            "El monto para el redondeo del Importe Total excede el valor permitido",
        )


def _check_3300_3301(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3300 / 3301: AllowanceTotalAmount y ChargeTotalAmount por línea."""
    disc_line = Decimal("0")
    charge_line = Decimal("0")
    for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
        disc_line += _line_amount(_allowance_charges(line), "false", {"01"})
        charge_line += _line_amount(_allowance_charges(line), "true", {"48"})

    allowance_total = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:AllowanceTotalAmount", NS_INVOICE)
    )
    if allowance_total is not None and abs(allowance_total - disc_line) > _TOLERANCE:
        add_error(
            errors,
            "3300",
            "El valor del tag es diferente a la sumatoria de los 'Montos de descuentos' de línea",
        )

    charge_total = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:ChargeTotalAmount", NS_INVOICE)
    )
    if charge_total is not None and abs(charge_total - charge_line) > _TOLERANCE:
        add_error(
            errors,
            "3301",
            "El valor del tag es diferente a la sumatoria de los 'Montos de cargos' de línea",
        )


# ---------------------------------------------------------------------------
# Reglas de cargos/descuentos globales
# ---------------------------------------------------------------------------

def _check_3307(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3307: monto global = base * factor."""
    for ac in _allowance_charges(root):
        if ac["reason"] is None:
            continue
        if ac["factor"] is not None and ac["factor"] > 0:
            if ac["base"] is None or ac["amount"] is None:
                continue
            expected = ac["base"] * ac["factor"]
            if abs(ac["amount"] - expected) > _TOLERANCE:
                add_error(
                    errors,
                    "3307",
                    "El valor de cargo/descuento global difiere de los importes consignados",
                )
                return


def _check_percepcion_retencion(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3233, 3262, 3263, 3264, 3308, 3318, 3330."""
    tipo_op = _tipo_operacion(root)
    customer_type = _customer_type(root)
    payable = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount", NS_INVOICE)
    )

    forma_pago = None
    for pt in _payment_terms(root):
        if pt["id"] == "FormaPago" and pt["means"] in {"Contado", "Credito"}:
            forma_pago = pt["means"]
            break

    for ac in _allowance_charges(root):
        reason = ac["reason"]
        if reason in {"51", "52", "53"}:
            # 3308
            if tipo_op != "2001":
                add_error(
                    errors,
                    "3308",
                    "Solo debe consignar informacion de percepciones si el tipo de operación es 2001",
                )
            # 3330
            if tipo_op == "2001" and forma_pago is not None and forma_pago != "Contado":
                add_error(
                    errors,
                    "3330",
                    "Solo debe consignar informacion de percepciones si la forma de pago es 'Contado'",
                )
            # 3233
            if ac["base"] is None or ac["base"] <= 0:
                add_error(
                    errors,
                    "3233",
                    "Para cargo Percepción, debe ingresar monto base y debe ser mayor a 0.00",
                )
        if reason == "62":
            # 3262
            if customer_type != "6":
                add_error(
                    errors,
                    "3262",
                    "Si existe retencion de IGV en el comprobante, el receptor debe ser un Agente de Retencion",
                )
            # 3263
            if (
                ac["base"] is not None
                and ac["factor"] is not None
                and ac["amount"] is not None
            ):
                expected = ac["base"] * ac["factor"]
                if abs(ac["amount"] - expected) > _TOLERANCE:
                    add_error(
                        errors,
                        "3263",
                        "El Importe de la retencion no tiene el valor correcto",
                    )
            # 3264
            if ac["base"] is not None and payable is not None and ac["base"] > payable:
                add_error(
                    errors,
                    "3264",
                    "El importe total de la operación (base imponible de retencion) no puede ser mayor al importe total del comprobante",
                )
        if reason == "63" and ac["base"] is None:
            add_error(
                errors,
                "3318",
                "Debe consignar la base de la retencion de segunda categoria",
            )


def _check_percepcion_payment_terms(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3309, 3310, 3311."""
    tipo_op = _tipo_operacion(root)
    forma_pago = None
    for pt in _payment_terms(root):
        if pt["id"] == "FormaPago":
            if pt["means"] in {"Contado", "Credito"}:
                forma_pago = pt["means"]

    if tipo_op == "2001" and forma_pago == "Contado":
        has_perc = any(pt["id"] == "Percepcion" for pt in _payment_terms(root))
        if not has_perc:
            add_error(
                errors,
                "3309",
                "Si forma de pago es Contado debe consignar un Payment Terms con indicador Percepcion",
            )

    for pt in _payment_terms(root):
        if pt["id"] == "Percepcion":
            if pt["amount"] is None:
                add_error(errors, "3310", "Debe consignar el Monto total incluido la percepcion")
            elif pt["amount"] <= 0:
                add_error(
                    errors,
                    "3311",
                    "El Monto total incluido la percepción no cumple con el formato establecido",
                )


# ---------------------------------------------------------------------------
# Reglas de PaymentTerms / forma de pago
# ---------------------------------------------------------------------------

def _check_payment_terms(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3244-3248, 3249, 3250, 3251, 3252-3256, 3265, 3266, 3267, 3319, 3461."""
    terms = list(_payment_terms(root))
    forma_pago_terms = [pt for pt in terms if pt["id"] == "FormaPago"]

    # 3244
    if not forma_pago_terms:
        add_error(errors, "3244", "Debe consignar la informacion del tipo de transaccion del comprobante")
        return

    # 3245 / 3246 / 3248 / 3461
    seen_means: set[str] = set()
    for pt in forma_pago_terms:
        means = pt["means"]
        if means is None:
            add_error(errors, "3245", "Debe informar si el tipo de transaccion es al Contado o al Credito")
            continue
        if not (
            means == "Contado"
            or means == "Credito"
            or matches(means, r"^Cuota\d{3}$")
        ):
            add_error(
                errors,
                "3246",
                "El tipo de transaccion o el identificador de la cuota no cumple con el formato esperado",
            )
        if means in seen_means:
            add_error(
                errors,
                "3248",
                "El tipo de transaccion o el identificador de la cuota no debe repetirse en el comprobante",
            )
        seen_means.add(means)

    # 3247
    has_contado = any(pt["means"] == "Contado" for pt in forma_pago_terms)
    has_credito = any(pt["means"] == "Credito" for pt in forma_pago_terms)
    if has_contado and has_credito:
        add_error(
            errors,
            "3247",
            "El tipo de transaccion no puede ser a la vez al Contado y al Credito",
        )

    # 3252
    has_cuota = any(
        pt["means"] is not None and matches(pt["means"], r"^Cuota\d{3}$")
        for pt in forma_pago_terms
    )
    if has_cuota and not has_credito:
        add_error(
            errors,
            "3252",
            "Si existe información de cuota de pago, el tipo de transaccion debe ser al credito",
        )

    customer_type = _customer_type(root)
    issue_date = text(root, "cbc:IssueDate", NS_INVOICE)
    payable = parse_amount(
        text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount", NS_INVOICE)
    )

    neto = None
    suma_cuotas = Decimal("0")
    for pt in forma_pago_terms:
        means = pt["means"]
        amount = pt["amount"]
        due = pt["due"]

        if means == "Credito":
            neto = amount
            # 3250
            if amount is not None and (amount <= 0):
                add_error(
                    errors,
                    "3250",
                    "El Monto neto pendiente de pago no cumple el formato definido",
                )
            # 3251
            if customer_type == "6" and amount is None:
                add_error(
                    errors,
                    "3251",
                    "Si el tipo de transaccion es al Credito debe consignarse el Monto neto pendiente de pago",
                )
            # 3265
            if amount is not None and payable is not None and amount > payable:
                add_error(
                    errors,
                    "3265",
                    "El Monto neto pendiente de pago debe ser menor o igual al Importe total del comprobante",
                )

        if means is not None and matches(means, r"^Cuota\d{3}$"):
            # 3253
            if amount is not None and amount <= 0:
                add_error(
                    errors,
                    "3253",
                    "El Monto del pago único o de las cuotas no cumple el formato definido",
                )
            # 3254
            if customer_type == "6" and amount is None:
                add_error(
                    errors,
                    "3254",
                    "Si se consigna información de la cuota de pago, debe indicarse el monto de la cuota",
                )
            # 3266
            if amount is not None and payable is not None and amount > payable:
                add_error(
                    errors,
                    "3266",
                    "El Monto del pago único o de las cuotas debe ser menor o igual al Importe total del comprobante",
                )
            # 3255
            if due is not None and not matches(due, r"^\d{4}-\d{2}-\d{2}$"):
                add_error(
                    errors,
                    "3255",
                    "Fecha del pago único o de las cuotas no cumple el formato definido",
                )
            # 3256
            if customer_type == "6" and due is None:
                add_error(
                    errors,
                    "3256",
                    "Si se consigna información de la cuota de pago, debe indicarse la fecha del pago único o de las cuotas",
                )
            # 3267
            if due is not None and issue_date is not None and due <= issue_date:
                add_error(
                    errors,
                    "3267",
                    "Fecha del pago único o de las cuotas no puede ser anterior o igual a la fecha de emisión",
                )
            if amount is not None:
                suma_cuotas += amount

    # 3249
    if has_credito and customer_type == "6" and not has_cuota:
        add_error(
            errors,
            "3249",
            "Si el tipo de transaccion es al Credito debe existir al menos información de una cuota de pago",
        )

    # 3319
    if neto is not None and customer_type == "6" and abs(neto - suma_cuotas) > _TOLERANCE:
        add_error(
            errors,
            "3319",
            "La suma de las cuotas debe ser igual al Monto neto pendiente de pago",
        )

    # 3461
    for pt in all_(root, "cac:PaymentTerms", NS_INVOICE):
        means_nodes = all_(pt, "cbc:PaymentMeansID", NS_INVOICE)
        if len(means_nodes) > 1:
            add_error(
                errors,
                "3461",
                "La forma de pago y/o número de cuota no pueden estar contenidos en el mismo cac:PaymentTerms",
            )


# ---------------------------------------------------------------------------
# Reglas de información adicional por ítem
# ---------------------------------------------------------------------------

def _check_items_adicionales(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3241, 3242, 3243."""
    tipo_op = _tipo_operacion(root)

    # 3241
    if tipo_op in {"2100", "2101", "2102"}:
        ok = False
        for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
            codes = {
                text(p, "cbc:NameCode", NS_INVOICE)
                for p in all_(line, "cac:Item/cac:AdditionalItemProperty", NS_INVOICE)
            }
            if {"7004", "7005", "7012"} <= codes:
                ok = True
                break
        if not ok:
            add_error(
                errors,
                "3241",
                "Para el tipo de operación 2100, 2101 y 2102 (Creditos) debe consignar Numero de contrato, Fecha de otorgamiento y Monto del crédito otorgado",
            )

    # 3242
    if tipo_op == "2104":
        ok = False
        for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
            for p in all_(line, "cac:Item/cac:AdditionalItemProperty", NS_INVOICE):
                if text(p, "cbc:NameCode", NS_INVOICE) == "7015":
                    ok = True
                    break
        if not ok:
            add_error(
                errors,
                "3242",
                "Para el tipo de operación 2104 - Empresas del sistema de seguros, debe consignar Información adicional a nivel de ítem",
            )

    # 3243
    for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
        for p in all_(line, "cac:Item/cac:AdditionalItemProperty", NS_INVOICE):
            if text(p, "cbc:NameCode", NS_INVOICE) == "7014":
                if not exists(p, "cac:UsabilityPeriod/cbc:StartDate", NS_INVOICE):
                    add_error(
                        errors,
                        "3243",
                        "El XML no contiene tag o no existe información de la fecha del concepto por linea",
                    )
                    return


# ---------------------------------------------------------------------------
# Regla 3462: misma tasa de IGV en todas las líneas
# ---------------------------------------------------------------------------

def _check_3462(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3462: todas las líneas afectas al IGV deben tener la misma tasa."""
    rates: set[Decimal] = set()
    has_subject = False
    for line in all_(root, "cac:InvoiceLine", NS_INVOICE):
        for info in _line_tax_subtotals(line):
            if info["code"] == "1000" and info["taxable"] is not None and info["taxable"] > 0:
                has_subject = True
                if info["percent"] is not None:
                    rates.add(info["percent"])
            if (
                info["code"] == "9996"
                and info["taxable"] is not None
                and info["taxable"] > 0
                and info["afectacion"] in {"11", "12", "13", "14", "15", "16"}
            ):
                has_subject = True
                if info["percent"] is not None:
                    rates.add(info["percent"])
    if has_subject and len(rates) > 1:
        add_error(
            errors,
            "3462",
            "La tasa del IGV debe ser la misma en todas las líneas o ítems del documento",
        )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def validate_invoice_extra3(root: etree._Element, errors: list[ValidationError] | None = None) -> list[ValidationError]:
    """Ejecuta todas las reglas del batch 3 sobre un Invoice."""
    if errors is None:
        errors = []
    # Anticipos / prepagos
    _check_3220(root, errors)
    _check_3282(root, errors)
    _check_3287(root, errors)

    # Tributos por línea
    _check_3223(root, errors)
    _check_3224_and_3234(root, errors)
    _check_3270(root, errors)
    _check_3271(root, errors)
    _check_3272(root, errors)
    _check_3290(root, errors)
    _check_3292(root, errors)

    # Tributos globales
    _check_3294(root, errors)
    _check_3273_3274_3275_3276(root, errors)
    _check_3277_3293(root, errors)
    _check_3291_3295(root, errors)
    _check_3296_3297(root, errors)
    _check_3298_3299_3302_3306(root, errors)

    # Totales monetarios
    _check_3278(root, errors)
    _check_3279(root, errors)
    _check_3280(root, errors)
    _check_3288(root, errors)
    _check_3305(root, errors)
    _check_3303(root, errors)
    _check_3300_3301(root, errors)

    # Cargos/descuentos globales, percepción y retención
    _check_3307(root, errors)
    _check_percepcion_retencion(root, errors)
    _check_percepcion_payment_terms(root, errors)

    # Forma de pago
    _check_payment_terms(root, errors)

    # Información adicional por ítem
    _check_items_adicionales(root, errors)

    # Tasa IGV uniforme
    _check_3462(root, errors)

    # FUERA DE ALCANCE (documentadas):
    # 3240, 3258, 3268, 3269, 3283, 3284, 3285, 3289:
    # no se encuentran definidos en rules_Invoice.txt / corresponden a contextos
    # de otros documentos o requieren información externa.
    # 3286: regla de CreditNote (nombre de archivo / texto truncado), no aplica a Invoice.
    return errors
