"""Reglas SUNAT adicionales para Invoice (batch 2).

Cubre los códigos 3092-3217 del Excel "Reglas de validación actualizado al
24.04.2026" publicado en https://cpe.sunat.gob.pe/guias-y-manuales.

Fuente de verdad: rules_Invoice.txt
"""

from __future__ import annotations

import re
from decimal import Decimal

from lxml import etree

from openubl.validators.common import (
    CATALOG05,
    NS_INVOICE,
    ValidationError,
    add_error,
    all_,
    attr,
    exists,
    parse_amount,
    text,
)


_NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
_NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"

_CATALOG51_BY_NAME = {
    "VENTA_INTERNA": "0101",
    "EXPORTACION": "0102",
    "NO_DOMICILIADO": "0103",
    "VENTA_INTERNA_ANTICIPOS": "0104",
    "VENTA_ITINERANTE": "0105",
    "VENTA_IGV": "0106",
    "VENTA_NO_DOMICILIADA_NO_GRAVADA": "0107",
    "FACTURA_AMPARADA_EXPORTACION": "0108",
    "VENTA_ITINERANTE_ANTICIPOS": "0110",
    "VENTA_INTERNA_SUSTENTO_TRIBUTARIO": "0200",
    "VENTA_INTERNA_NO_SUSTENTO_TRIBUTARIO": "0201",
    "EXPORTACION_DE_BIENES_NO_GRAVADA": "0202",
    "VENTA_NO_DOMICILIADA_NO_GRAVADA_2": "0203",
    "VENTA_NO_DOMICILIADA_GRAVADA": "0204",
    "VENTA_INTERNA_GRATUITA": "0205",
    "VENTA_INTERNA_ANTICIPOS_GRATUITA": "0206",
    "VENTA_NO_DOMICILIADA_GRATUITA": "0207",
}

_EXPORT_OPERATIONS = {"0200", "0201", "0202", "0203", "0204", "0205", "0206", "0207", "0208"}


def _operacion(root: etree._Element, ns: dict) -> str | None:
    """Extrae el código numérico de tipo de operación (Catalog51)."""
    raw = attr(root, "cbc:InvoiceTypeCode", "listID", ns)
    if raw is None:
        return None
    raw = raw.strip()
    if raw.startswith("Catalog51."):
        name = raw.split(".", 1)[1]
        return _CATALOG51_BY_NAME.get(name)
    if re.fullmatch(r"\d{4}", raw):
        return raw
    return raw


def _moneda(root: etree._Element, ns: dict) -> str | None:
    """Extrae el código de moneda (Catalog2) del documento."""
    raw = text(root, "cbc:DocumentCurrencyCode", ns)
    if raw is None:
        return None
    raw = raw.strip()
    if raw.startswith("Catalog2."):
        return raw.split(".", 1)[1]
    return raw


def _has_tax_subtotal_with(
    line: etree._Element, ns: dict, tax_code: str | None = None, taxable_gt_zero: bool | None = None
) -> bool:
    """Indica si la línea tiene al menos un TaxSubtotal con el código/base indicados."""
    for ts in all_(line, "cac:TaxTotal/cac:TaxSubtotal", ns):
        code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns)
        if tax_code is not None and code != tax_code:
            continue
        if taxable_gt_zero is not None:
            taxable = parse_amount(text(ts, "cbc:TaxableAmount", ns))
            if taxable is None:
                continue
            if taxable_gt_zero and taxable <= 0:
                continue
            if not taxable_gt_zero and taxable > 0:
                continue
        return True
    return False


def _customer_type(root: etree._Element, ns: dict) -> str | None:
    """Extrae el tipo de documento del cliente (valor numérico Catalog6)."""
    raw = attr(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID", "schemeID", ns)
    if raw is None:
        return None
    raw = raw.strip()
    if raw.startswith("Catalog6."):
        name = raw.split(".", 1)[1]
        mapping = {"DOC_NO_DOMICILIADO": "0", "DNI": "1", "CE": "4", "RUC": "6", "PASAPORTE": "7"}
        return mapping.get(name, raw)
    return raw


def _line_tax_subtotals(line: etree._Element, ns: dict) -> list[etree._Element]:
    return all_(line, "cac:TaxTotal/cac:TaxSubtotal", ns)


def _item_property_codes(line: etree._Element, ns: dict) -> set[str]:
    """Devuelve los cbc:NameCode de AdditionalItemProperty de la línea."""
    codes: set[str] = set()
    for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", ns):
        code = text(prop, "cbc:NameCode", ns)
        if code is not None:
            codes.add(code)
    return codes


def _has_item_property(line: etree._Element, ns: dict, code: str) -> bool:
    return code in _item_property_codes(line, ns)


def _format_amount_positive(value: str | None, int_digits: int = 12, frac_digits: int = 2) -> bool:
    """Valida formato decimal positivo con los límites indicados."""
    if value is None:
        return False
    pattern = rf"^\d{{1,{int_digits}}}(\.\d{{1,{frac_digits}}})?$"
    if not re.match(pattern, value):
        return False
    try:
        return Decimal(value) > 0
    except Exception:
        return False


def _format_percent(value: str | None) -> bool:
    """Valida formato decimal positivo de hasta 3 enteros y 5 decimales."""
    if value is None:
        return False
    if not re.match(r"^\d{1,3}(\.\d{1,5})?$", value):
        return False
    try:
        return Decimal(value) > 0
    except Exception:
        return False


def validate_invoice_extra2(root: etree._Element, errors: list[ValidationError]) -> None:
    ns = NS_INVOICE
    op = _operacion(root, ns)
    currency = _moneda(root, ns)
    lines = all_(root, "cac:InvoiceLine", ns)

    _validate_invoice_line_taxes(root, ns, op, lines, errors)
    _validate_invoice_allowance_charges(root, ns, op, currency, errors)
    _validate_invoice_perception(root, ns, op, errors)
    _validate_invoice_detraccion(root, ns, op, errors)
    _validate_invoice_special_operations(root, ns, op, lines, errors)
    _validate_invoice_anticipos(root, ns, errors)
    _validate_invoice_forma_pago(root, ns, errors)
    _validate_invoice_tipo_operacion(root, ns, errors)
    _document_out_of_scope(errors)


def _validate_invoice_line_taxes(
    root: etree._Element, ns: dict, op: str | None, lines: list[etree._Element], errors: list[ValidationError]
) -> None:
    for line in lines:
        tax_subtotals = _line_tax_subtotals(line, ns)

        for ts in tax_subtotals:
            tax_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns)
            taxable = parse_amount(text(ts, "cbc:TaxableAmount", ns))
            tax_amount = parse_amount(text(ts, "cbc:TaxAmount", ns))
            percent = text(ts, "cac:TaxCategory/cbc:Percent", ns)
            tier_range = text(ts, "cac:TaxCategory/cbc:TierRange", ns)

            # ERROR 3102: formato del porcentaje/factor
            if percent is not None and not _format_percent(percent):
                add_error(errors, "3102", "El formato del Tag UBL cbc:Percent es diferente de decimal positivo de hasta 3 enteros y hasta 5 decimales")

            # ERROR 3103: IGV/IVAP percent * taxable ≈ tax_amount
            if tax_code in {"1000", "1016"} and taxable is not None and tax_amount is not None and percent is not None:
                try:
                    expected = (taxable * Decimal(percent)) / Decimal("100")
                    if abs(expected - tax_amount) > Decimal("1"):
                        add_error(errors, "3103", "El producto del factor y monto base de la afectación del IGV/IVAP no corresponde al monto de afectacion de linea")
                except Exception:
                    pass

            # ERROR 3104: ISC percent no debe ser 0
            if tax_code == "2000" and taxable is not None and taxable > 0 and percent is not None:
                if parse_amount(percent) == Decimal("0"):
                    add_error(errors, "3104", "El factor de afectación de ISC por linea debe ser diferente a 0.00")

            # ERROR 3108: ISC percent * taxable ≈ tax_amount
            if tax_code == "2000" and taxable is not None and tax_amount is not None and percent is not None:
                try:
                    expected = (taxable * Decimal(percent)) / Decimal("100")
                    if abs(expected - tax_amount) > Decimal("1"):
                        add_error(errors, "3108", "El producto del factor y monto base de la afectación del ISC no corresponde al monto de afectacion de linea")
                except Exception:
                    pass

            # ERROR 3109: Otros tributos percent * taxable ≈ tax_amount
            if tax_code == "9999" and taxable is not None and tax_amount is not None and percent is not None:
                try:
                    expected = (taxable * Decimal(percent)) / Decimal("100")
                    if abs(expected - tax_amount) > Decimal("1"):
                        add_error(errors, "3109", "El producto del factor y monto base de la afectación de otros tributos no corresponde al monto de afectacion de linea")
                except Exception:
                    pass

            # ERROR 3110: 9995/9997/9998 tax_amount debe ser 0
            if tax_code in {"9995", "9997", "9998"} and tax_amount is not None and tax_amount != 0:
                add_error(errors, "3110", "El monto de afectacion de IGV por linea debe ser igual a 0.00 para Exoneradas, Inafectas o Exportación")

            # ERROR 3111: 9996 con afectación 11-17 y taxable>0.06 debe tener tax_amount>0
            if tax_code == "9996" and taxable is not None and taxable > Decimal("0.06"):
                exemp = text(ts, "cac:TaxCategory/cbc:TaxExemptionReasonCode", ns)
                if exemp in {"11", "12", "13", "14", "15", "16", "17"} and tax_amount == 0:
                    add_error(errors, "3111", "El monto de afectación de IGV por linea debe ser diferente a 0.00")

            # ERROR 3210: TierRange solo debe existir para ISC
            if tax_code != "2000" and tier_range is not None:
                add_error(errors, "3210", "Solo debe consignar sistema de calculo si el tributo es ISC")

        # ERROR 3105: al menos un tributo de afectación por IGV
        if op not in {"2100", "2101", "2102", "2103", "2104", "0112"}:
            if not any(
                text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns) in {"1000", "1016", "9995", "9996", "9997", "9998"}
                and parse_amount(text(ts, "cbc:TaxableAmount", ns)) is not None
                and parse_amount(text(ts, "cbc:TaxableAmount", ns)) > 0
                for ts in tax_subtotals
            ):
                add_error(errors, "3105", "El XML debe contener al menos un tributo por linea de afectacion por IGV")

    # ERROR 3107: operación exportación no debe tener ciertos tributos globales
    if op in _EXPORT_OPERATIONS:
        for ts in all_(root, "cac:TaxTotal/cac:TaxSubtotal", ns):
            tax_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns)
            if tax_code in {"9997", "9998", "1000", "1016", "2000", "9999"}:
                add_error(errors, "3107", "El dato ingresado como codigo de tributo global es invalido para tipo de operación")

    # ERROR 3195: cada línea debe tener TaxTotal
    for line in lines:
        if not exists(line, "cac:TaxTotal", ns):
            add_error(errors, "3195", "El xml no contiene el tag de impuesto por linea (TaxTotal)")


def _validate_invoice_allowance_charges(
    root: etree._Element, ns: dict, op: str | None, currency: str | None, errors: list[ValidationError]
) -> None:
    # AllowanceCharge a nivel de línea
    for line in all_(root, "cac:InvoiceLine", ns):
        for ac in all_(line, "cac:AllowanceCharge", ns):
            indicator = text(ac, "cbc:ChargeIndicator", ns)
            reason_code = text(ac, "cbc:AllowanceChargeReasonCode", ns)

            # ERROR 3114: indicador correcto según código
            if reason_code in {"47", "48"} and indicator != "true":
                add_error(errors, "3114", "El indicador de cargo/descuento no corresponde al valor esperado")
            if reason_code in {"00", "01"} and indicator != "false":
                add_error(errors, "3114", "El indicador de cargo/descuento no corresponde al valor esperado")

    # AllowanceCharge globales
    for ac in all_(root, "cac:AllowanceCharge", ns):
        indicator = text(ac, "cbc:ChargeIndicator", ns)
        reason_code = text(ac, "cbc:AllowanceChargeReasonCode", ns)
        amount = parse_amount(text(ac, "cbc:Amount", ns))
        base_amount = parse_amount(text(ac, "cbc:BaseAmount", ns))
        factor = text(ac, "cbc:MultiplierFactorNumeric", ns)

        # ERROR 3114 (global): indicador según código
        if reason_code in {"45", "46", "49", "50", "51", "52", "53"} and indicator != "true":
            add_error(errors, "3114", "El indicador de cargo/descuento no corresponde al valor esperado")
        if reason_code in {"02", "03", "04", "05", "06", "20"} and indicator != "false":
            add_error(errors, "3114", "El indicador de cargo/descuento no corresponde al valor esperado")

        # ERROR 3092: monto base > 0 cuando código 45
        if reason_code == "45" and (base_amount is None or base_amount <= 0):
            add_error(errors, "3092", "Para cargo/descuento FISE, debe ingresar monto base y debe ser mayor a 0.00")

        # ERROR 3074: amount > 0 cuando código 45
        if reason_code == "45" and amount is not None and amount <= 0:
            # Cubierto por regla 3074 en validator principal; no duplicamos mensaje.
            pass

        # ERROR 3233: monto base > 0 cuando código 51/52/53
        if reason_code in {"51", "52", "53"} and (base_amount is None or base_amount <= 0):
            add_error(errors, "3233", "Para cargo Percepción, debe ingresar monto base y debe ser mayor a 0.00")

        # ERROR 2797: percepción no puede superar importe total
        if reason_code in {"51", "52", "53"} and currency == "PEN" and amount is not None:
            payable = parse_amount(text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount", ns))
            if payable is not None and amount > payable:
                add_error(errors, "2797", "El Monto de percepcion no puede ser mayor al importe total del comprobante")


def _validate_invoice_perception(
    root: etree._Element, ns: dict, op: str | None, errors: list[ValidationError]
) -> None:
    # Detectar forma de pago
    forma_pago_terms = [pt for pt in all_(root, "cac:PaymentTerms", ns) if text(pt, "cbc:ID", ns) == "FormaPago"]
    formas = {text(pt, "cbc:PaymentMeansID", ns) for pt in forma_pago_terms}
    has_contado = "Contado" in formas

    # ERROR 3093: operación sujeta a percepción + contado requiere cargo 51/52/53
    if op == "2001" and has_contado:
        charge_codes = {
            text(ac, "cbc:AllowanceChargeReasonCode", ns)
            for ac in all_(root, "cac:AllowanceCharge", ns)
        }
        if not charge_codes.intersection({"51", "52", "53"}):
            add_error(errors, "3093", "Si operación es sujeta a percepción y la forma de pago es Contado, debe ingresar cargo para Percepción")

    # ERROR 3309: operación sujeta a percepción + contado requiere PaymentTerms Percepcion
    if op == "2001" and has_contado:
        if not any(text(pt, "cbc:ID", ns) == "Percepcion" for pt in all_(root, "cac:PaymentTerms", ns)):
            add_error(errors, "3309", "Si forma de pago es Contado debe consignar un Payment Terms con indicador Percepcion")

    # ERROR 3310/3311: monto total incluido percepción
    for pt in all_(root, "cac:PaymentTerms", ns):
        if text(pt, "cbc:ID", ns) == "Percepcion":
            amount = text(pt, "cbc:Amount", ns)
            if amount is None:
                add_error(errors, "3310", "Debe consignar el Monto total incluido la percepcion")
            elif not _format_amount_positive(amount):
                add_error(errors, "3311", "El Monto total incluido la percepción no cumple con el formato establecido")


def _validate_invoice_detraccion(
    root: etree._Element, ns: dict, op: str | None, errors: list[ValidationError]
) -> None:
    if op not in {"1001", "1002", "1003", "1004"}:
        # ERROR 3128: PaymentTerms Detraccion solo para tipos 1001-1004
        for pt in all_(root, "cac:PaymentTerms", ns):
            if text(pt, "cbc:ID", ns) == "Detraccion":
                add_error(errors, "3128", "El XML contiene información de codigo de bien y servicio de detracción que no corresponde al tipo de operación")
        return

    # ERROR 3127: debe existir al menos un PaymentTerms con ID Detraccion
    detraccion_terms = [pt for pt in all_(root, "cac:PaymentTerms", ns) if text(pt, "cbc:ID", ns) == "Detraccion"]
    if not detraccion_terms:
        add_error(errors, "3127", "El XML no contiene el tag o no existe información del Codigo de BBSS de detracción para el tipo de operación")
        return

    for pt in detraccion_terms:
        bbss = text(pt, "cbc:PaymentMeansID", ns)
        # ERROR 3127: código de bien o servicio requerido
        if bbss is None or bbss == "":
            add_error(errors, "3127", "El XML no contiene el tag o no existe información del Codigo de BBSS de detracción para el tipo de operación")
            continue

        # ERROR 3129: código BBSS según tipo de operación
        expected_bbss = {"1002": "004", "1003": "028", "1004": "027"}.get(op)
        if expected_bbss is not None and bbss != expected_bbss:
            add_error(errors, "3129", "El dato ingresado como codigo de BBSS de detracción no corresponde al valor esperado")

        # ERROR 3035: monto de detracción requerido
        amount = text(pt, "cbc:Amount", ns)
        if amount is None:
            add_error(errors, "3035", "El xml no contiene el tag o no existe información en el monto de detraccion")
        elif not _format_amount_positive(amount):
            add_error(errors, "3037", "El dato ingresado en monto de detraccion no cumple con el formato establecido")

        # ERROR 3208: moneda de detracción debe ser PEN
        curr = attr(pt, "cbc:Amount", "currencyID", ns)
        if curr is not None and curr != "PEN":
            add_error(errors, "3208", "La moneda del monto de la detracción debe ser PEN")

    # ERROR 3034: PaymentMeans Detraccion y número de cuenta
    detraccion_means = [pm for pm in all_(root, "cac:PaymentMeans", ns) if text(pm, "cbc:ID", ns) == "Detraccion"]
    if not detraccion_means:
        add_error(errors, "3034", "El xml no contiene el tag o no existe información en el nro de cuenta de detracción")
    for pm in detraccion_means:
        account = text(pm, "cac:PayeeFinancialAccount/cbc:ID", ns)
        if account is None or account == "":
            add_error(errors, "3034", "El xml no contiene el tag o no existe información en el nro de cuenta de detracción")


def _validate_invoice_special_operations(
    root: etree._Element, ns: dict, op: str | None, lines: list[etree._Element], errors: list[ValidationError]
) -> None:
    # ERROR 3098: código de país para operación 0201/0208
    if op in {"0201", "0208"}:
        country = text(root, "cac:Delivery/cac:DeliveryLocation/cac:Address/cac:Country/cbc:IdentificationCode", ns)
        if country is None or country == "":
            add_error(errors, "3098", "El XML no contiene el tag o no existe información del pais de uso, exploración o aprovechamiento")

    # Reglas para operación 1004 (transporte de carga)
    if op == "1004":
        for line in lines:
            # ERROR 3117: dirección origen
            origin = text(line, "cac:Delivery/cac:Despatch/cac:DespatchAddress/cac:AddressLine/cbc:Line", ns)
            if origin is None or origin == "":
                add_error(errors, "3117", "El XML no contiene el tag o no existe información de la dirección del punto de origen en Detracciones - Servicio de transporte de carga")

            # ERROR 3118: ubigeo destino
            dest_id = text(line, "cac:Delivery/cac:DeliveryLocation/cac:Address/cbc:ID", ns)
            if dest_id is None or dest_id == "":
                add_error(errors, "3118", "El XML no contiene el tag o no existe información del ubigeo de punto de destino en Detracciones - Servicio de transporte de carga")

            # ERROR 3119: dirección destino
            dest_line = text(line, "cac:Delivery/cac:DeliveryLocation/cac:Address/cac:AddressLine/cbc:Line", ns)
            if dest_line is None:
                add_error(errors, "3119", "El XML no contiene el tag o no existe información de la dirección del punto de destino en Detracciones - Servicio de transporte de carga")

            # ERROR 3120: detalle del viaje
            instructions = text(line, "cac:Delivery/cac:Despatch/cbc:Instructions", ns)
            if instructions is None or instructions == "":
                add_error(errors, "3120", "El XML no contiene el tag o no existe información del Detalle del viaje en Detracciones - Servicio de transporte de carga")

            # Valores referenciales (01, 02, 03)
            delivery_terms = all_(line, "cac:Delivery/cac:DeliveryTerms", ns)
            if not delivery_terms:
                add_error(errors, "3122", "El XML no contiene el tag o no existe información del monto del valor referencial en Detracciones - Servicios de transporte de carga")
            else:
                ref_types = [text(dt, "cbc:ID", ns) for dt in delivery_terms]
                for ref_type in ("01", "02", "03"):
                    count = ref_types.count(ref_type)
                    if count != 1:
                        if ref_type == "01":
                            add_error(errors, "3124", "Detracciones - Servicio de transporte de carga, debe tener un (y solo uno) Valor Referencial del Servicio de Transporte")
                        elif ref_type == "02":
                            add_error(errors, "3125", "Detracciones - Servicio de transporte de carga, debe tener un (y solo uno) Valor Referencial sobre la carga efectiva")
                        else:
                            add_error(errors, "3126", "Detracciones - Servicio de transporte de carga, debe tener un (y solo uno) Valor Referencial sobre la carga util nominal")

                # ERROR 3123: Amount de DeliveryTerms
                for dt in delivery_terms:
                    amount = text(dt, "cbc:Amount", ns)
                    if amount is None:
                        add_error(errors, "3122", "El XML no contiene el tag o no existe información del monto del valor referencial en Detracciones - Servicios de transporte de carga")
                    elif not _format_amount_positive(amount):
                        add_error(errors, "3123", "El dato ingresado como monto valor referencial en Detracciones - Servicios de transporte de carga no cumple con el formato establecido")
                    curr = attr(dt, "cbc:Amount", "currencyID", ns)
                    if curr is not None and curr != "PEN":
                        add_error(errors, "3208", "La moneda del monto de la detracción debe ser PEN")

    # ERROR 3115: unidad de medida para cantidad de especie (3006) debe ser TNE
    if op == "1002":
        for line in lines:
            for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", ns):
                if text(prop, "cbc:NameCode", ns) == "3006":
                    vq = prop.find("cbc:ValueQuantity", namespaces=ns)
                    if vq is not None:
                        unit = vq.get("unitCode")
                        if unit is not None and unit != "TNE":
                            add_error(errors, "3115", "El dato ingresado como unidad de medida de cantidad de especie vendidas no corresponde al valor esperado")

    # Operación 1002: conceptos adicionales 3001-3004, 3006
    if op == "1002":
        for line in lines:
            codes = _item_property_codes(line, ns)
            for required in ("3001", "3002", "3003", "3004"):
                if required not in codes:
                    if required == "3001":
                        add_error(errors, "3063", "El XML no contiene el tag de matricula de embarcación en Detracciones para recursos hidrobiologicos")
                    elif required == "3002":
                        add_error(errors, "3130", "El XML no contiene el tag de nombre de embarcación en Detracciones para recursos hidrobiologicos")
                    elif required == "3003":
                        add_error(errors, "3131", "El XML no contiene el tag de tipo de especie vendidas en Detracciones para recursos hidrobiologicos")
                    else:
                        add_error(errors, "3132", "El XML no contiene el tag de lugar de descarga en Detracciones para recursos hidrobiologicos")
            if "3006" not in codes:
                add_error(errors, "3133", "El XML no contiene el tag de cantidad de especies vendidas en Detracciones para recursos hidrobiologicos")

            # ERROR 3135: si existe concepto 3006 debe existir ValueQuantity
            if "3006" in codes:
                found = False
                for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", ns):
                    if text(prop, "cbc:NameCode", ns) == "3006" and exists(prop, "cbc:ValueQuantity", ns):
                        found = True
                        break
                if not found:
                    add_error(errors, "3135", "El XML no contiene tag de la cantidad del concepto por linea")

    # Operación 0202 / 0205: hospedaje no dom / paquete turístico
    if op in {"0202", "0205"}:
        required = {"4009", "4008", "4000", "4007"}
        if op == "0202":
            required.update({"4001", "4002", "4003", "4004", "4006", "4005"})
        for line in lines:
            codes = _item_property_codes(line, ns)
            for code in required:
                if code not in codes:
                    c, m = code_mapping_hospedaje(code)
                    add_error(errors, c, m)

    # ERROR 3146-3149: Proveedores Estado (conceptos 5000-5003)
    for line in lines:
        codes = _item_property_codes(line, ns)
        present = codes.intersection({"5000", "5001", "5002", "5003"})
        if present:
            for req in ({"5000", "5001", "5002", "5003"} - present):
                if req == "5000":
                    add_error(errors, "3146", "El XML no contiene el tag de Proveedores Estado: Número de Expediente")
                elif req == "5001":
                    add_error(errors, "3147", "El XML no contiene el tag de Proveedores Estado: Código de Unidad Ejecutora")
                elif req == "5002":
                    add_error(errors, "3148", "El XML no contiene el tag de Proveedores Estado: N° de Proceso de Selección")
                else:
                    add_error(errors, "3149", "El XML no contiene el tag de Proveedores Estado: N° de Contrato")

    # Operación 0301: Carta de porte aéreo
    if op == "0301":
        for line in lines:
            codes = _item_property_codes(line, ns)
            for req in ("4030", "4031", "4032", "4033"):
                if req not in codes:
                    c, m = carta_porte_error(req)
                    add_error(errors, c, m)

    # Operación 0302: BVME transporte ferroviario
    if op == "0302":
        # ERROR 3156: Agente de ventas RUC
        agent = text(root, "cac:AccountingSupplierParty/cac:Party/cac:AgentParty/cac:PartyIdentification/cbc:ID", ns)
        if agent is None:
            add_error(errors, "3156", "El XML no contiene el tag de BVME transporte ferroviario: Agente de Viajes: Numero de Ruc")
        else:
            # ERROR 3158: tipo de documento del agente debe ser 6
            scheme = attr(root, "cac:AccountingSupplierParty/cac:Party/cac:AgentParty/cac:PartyIdentification/cbc:ID", "schemeID", ns)
            if scheme is not None and scheme != "6":
                add_error(errors, "3158", "El dato ingresado como Agente de Viajes-Tipo de documento no corresponde al valor esperado")

        required_bvme = {
            "4040", "4041", "4049", "4042", "4043", "4044", "4045",
            "4046", "4047", "4048",
        }
        for line in lines:
            codes = _item_property_codes(line, ns)
            for req in required_bvme:
                if req not in codes:
                    c, m = bvme_error(req)
                    add_error(errors, c, m)

        # ERROR 3173: PaymentMeans/PaymentMeansCode
        if not exists(root, "cac:PaymentMeans/cbc:PaymentMeansCode", ns):
            add_error(errors, "3173", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Forma de Pago")

        # ERROR 3175: PaymentMeans/PaymentID
        if not exists(root, "cac:PaymentMeans/cbc:PaymentID", ns):
            add_error(errors, "3175", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Número de autorización de la transacción")

    # Créditos hipotecarios (producto 84121901)
    for line in lines:
        codes = _item_property_codes(line, ns)
        producto_84121901 = "7000" in codes  # aproximación local
        indicador_3 = "7002" in codes
        if producto_84121901:
            for req in ("7004", "7005"):
                if req not in codes:
                    if req == "7004":
                        add_error(errors, "3152", "El XML no contiene el tag de Créditos Hipotecarios: Número de contrato")
                    else:
                        add_error(errors, "3153", "El XML no contiene el tag de Créditos Hipotecarios: Fecha de otorgamiento del crédito")
            if indicador_3:
                for req in ("7003", "7006", "7007"):
                    if req not in codes:
                        if req == "7003":
                            add_error(errors, "3151", "El XML no contiene el tag de Créditos Hipotecarios: Partida Registral")
                        elif req == "7006":
                            add_error(errors, "3154", "El XML no contiene el tag de Créditos Hipotecarios: Dirección del predio - Código de ubigeo")
                        else:
                            add_error(errors, "3155", "El XML no contiene el tag de Créditos Hipotecarios: Dirección del predio - Dirección completa")

    # ERROR 3172: hora de inicio cuando existe concepto 3060 o 4047
    for line in lines:
        for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", ns):
            code = text(prop, "cbc:NameCode", ns)
            if code in {"3060", "4047"} and not exists(prop, "cac:UsabilityPeriod/cbc:StartTime", ns):
                add_error(errors, "3172", "El XML no contiene tag de la Hora del concepto por linea")


def code_mapping_hospedaje(code: str) -> tuple[str, str]:
    mapping = {
        "4009": ("3136", "El XML no contiene el tag de numero de documentos del huesped"),
        "4008": ("3137", "El XML no contiene el tag de tipo de documentos del huesped"),
        "4000": ("3138", "El XML no contiene el tag de codigo de pais de emision del documento de identidad"),
        "4007": ("3139", "El XML no contiene el tag de apellidos y nombres del huesped"),
        "4001": ("3140", "El XML no contiene el tag de codigo del pais de residencia"),
        "4002": ("3141", "El XML no contiene el tag de fecha de ingreso del pais"),
        "4003": ("3142", "El XML no contiene el tag de fecha de ingreso al establecimiento"),
        "4004": ("3143", "El XML no contiene el tag de fecha de salida del establecimiento"),
        "4006": ("3144", "El XML no contiene el tag de fecha de consumo"),
        "4005": ("3145", "El XML no contiene el tag de numero de dias de permanencia"),
    }
    return mapping.get(code, ("0000", "Concepto no mapeado"))


def carta_porte_error(code: str) -> tuple[str, str]:
    mapping = {
        "4030": ("3168", "El XML no contiene el tag de Carta Porte Aéreo: Lugar de origen - Código de ubigeo"),
        "4031": ("3169", "El XML no contiene el tag de Carta Porte Aéreo: Lugar de origen - Dirección detallada"),
        "4032": ("3170", "El XML no contiene el tag de Carta Porte Aéreo: Lugar de destino - Código de ubigeo"),
        "4033": ("3171", "El XML no contiene el tag de Carta Porte Aéreo: Lugar de destino - Dirección detallada"),
    }
    return mapping.get(code, ("0000", "Concepto no mapeado"))


def bvme_error(code: str) -> tuple[str, str]:
    mapping = {
        "4040": ("3159", "El XML no contiene el tag de BVME transporte ferroviario: Pasajero - Apellidos y Nombres"),
        "4041": ("3160", "El XML no contiene el tag de BVME transporte ferroviario: Pasajero - Tipo de documento de identidad"),
        "4049": ("3204", "El XML no contiene el tag de BVME transporte ferroviario: Pasajero - Número de documento de identidad"),
        "4042": ("3161", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Ciudad o lugar de origen - Código de ubigeo"),
        "4043": ("3162", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Ciudad o lugar de origen - Dirección detallada"),
        "4044": ("3163", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Ciudad o lugar de destino - Código de ubigeo"),
        "4045": ("3164", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Ciudad o lugar de destino - Dirección detallada"),
        "4046": ("3165", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte:Número de asiento"),
        "4047": ("3166", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Hora programada de inicio de viaje"),
        "4048": ("3167", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Fecha programada de inicio de viaje"),
    }
    return mapping.get(code, ("0000", "Concepto no mapeado"))


def _validate_invoice_anticipos(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    prepaid_payments = all_(root, "cac:PrepaidPayment", ns)
    add_doc_refs = all_(root, "cac:AdditionalDocumentReference", ns)
    total_prepaid = parse_amount(text(root, "cac:LegalMonetaryTotal/cbc:PrepaidAmount", ns))

    # Recopilar identificadores de pago
    payment_ids: list[str] = []
    for pp in prepaid_payments:
        pp_id = text(pp, "cbc:ID", ns)
        paid = parse_amount(text(pp, "cbc:PaidAmount", ns))

        # ERROR 3211: identificador de pago requerido
        if pp_id is None or pp_id == "":
            add_error(errors, "3211", "Falta identificador del pago del Monto de anticipo para relacionarlo con el comprobante que se realizo el anticipo")
        else:
            payment_ids.append(pp_id)

        # ERROR 2503: PaidAmount > 0
        if paid is not None and paid <= 0:
            add_error(errors, "2503", "PaidAmount: monto anticipado por documento debe ser mayor a cero")

    # ERROR 3212: identificadores repetidos
    if len(payment_ids) != len(set(payment_ids)):
        add_error(errors, "3212", "El comprobante contiene un identificador de pago repetido en los montos anticipados")

    # ERROR 3220: si hay anticipos debe existir Total Anticipos > 0
    if prepaid_payments and (total_prepaid is None or total_prepaid <= 0):
        add_error(errors, "3220", "Si consigna montos de anticipo debe informar el Total de Anticipos")

    # Documentos de anticipo
    ref_ids: list[str] = []
    for adr in add_doc_refs:
        doc_type = text(adr, "cbc:DocumentTypeCode", ns)
        doc_status = text(adr, "cbc:DocumentStatusCode", ns)
        doc_id = text(adr, "cbc:ID", ns)
        issuer_id = text(adr, "cac:IssuerParty/cac:PartyIdentification/cbc:ID", ns)

        if doc_type in {"02", "03"}:
            # ERROR 3216: DocumentStatusCode requerido
            if doc_status is None or doc_status == "":
                add_error(errors, "3216", "Falta identificador del pago del comprobante para relacionarlo con el monto de anticipo")
            else:
                ref_ids.append(doc_status)

            # ERROR 3214: debe existir PrepaidPayment con mismo ID
            if doc_status not in payment_ids:
                add_error(errors, "3214", "No existe información del Monto Anticipado para el comprobante que se realizo el anticipo")

            # ERROR 2521: formato de serie-número
            if doc_id is not None:
                if doc_type == "02" and not re.match(r"^[FE][A-Z0-9]{3}-\d{1,8}$|^\(E001\)-\d{1,8}$|^\d{1,4}-\d{1,8}$", doc_id):
                    add_error(errors, "2521", "El dato ingresado debe indicar SERIE-CORRELATIVO del documento que se realizo el anticipo")
                if doc_type == "03" and not re.match(r"^[B][A-Z0-9]{3}-\d{1,8}$|^\(EB01\)-\d{1,8}$|^\d{1,4}-\d{1,8}$", doc_id):
                    add_error(errors, "2521", "El dato ingresado debe indicar SERIE-CORRELATIVO del documento que se realizo el anticipo")

            # ERROR 3217: emisor del anticipo requerido
            if issuer_id is None or issuer_id == "":
                add_error(errors, "3217", "Debe consignar Numero de RUC del emisor del comprobante de anticipo")

    # ERROR 3215: identificadores repetidos en documentos de anticipo
    if len(ref_ids) != len(set(ref_ids)):
        add_error(errors, "3215", "El comprobante contiene un identificador de pago repetido en los comprobantes que se realizo el anticipo")

    # ERROR 3213: cada identificador de pago debe tener documento 02/03
    for pp_id in payment_ids:
        if pp_id not in ref_ids:
            add_error(errors, "3213", "El comprobante contiene un pago anticipado pero no se ha consignado el documento que se realizo el anticipo")

    # ERROR 2509: suma de anticipos coincide con total
    if total_prepaid is not None and total_prepaid > 0:
        sum_pp = sum(parse_amount(text(pp, "cbc:PaidAmount", ns)) or Decimal("0") for pp in prepaid_payments)
        if total_prepaid != sum_pp:
            add_error(errors, "2509", "Total de anticipos diferente a los montos anticipados por documento")

    # ERROR 3287: si hay total anticipos debe haber descuentos globales 04/05/06
    if total_prepaid is not None and total_prepaid > 0:
        has_discount = any(
            text(ac, "cbc:AllowanceChargeReasonCode", ns) in {"04", "05", "06"}
            and parse_amount(text(ac, "cbc:Amount", ns)) is not None
            and parse_amount(text(ac, "cbc:Amount", ns)) > 0
            for ac in all_(root, "cac:AllowanceCharge", ns)
        )
        if not has_discount:
            add_error(errors, "3287", "Si se informa 'Total de anticipos' debe consignar los descuentos globales por anticipo con monto mayor a cero")


def _validate_invoice_forma_pago(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    terms = all_(root, "cac:PaymentTerms", ns)
    forma_pago_terms = [pt for pt in terms if text(pt, "cbc:ID", ns) == "FormaPago"]

    # ERROR 3244: debe existir al menos un FormaPago
    if not forma_pago_terms:
        add_error(errors, "3244", "Debe consignar la informacion del tipo de transaccion del comprobante")
        return

    means_ids: list[str | None] = []
    for pt in forma_pago_terms:
        means_id = text(pt, "cbc:PaymentMeansID", ns)
        means_ids.append(means_id)

        # ERROR 3245: PaymentMeansID requerido
        if means_id is None:
            add_error(errors, "3245", "Debe informar si el tipo de transaccion es al Contado o al Credito")
            continue

        # ERROR 3246: valores permitidos
        if means_id not in {"Contado", "Credito"} and not re.match(r"^Cuota\d{3}$", means_id):
            add_error(errors, "3246", "El tipo de transaccion o el identificador de la cuota no cumple con el formato esperado")

    # ERROR 3247: no puede haber Contado y Credito
    has_contado = "Contado" in means_ids
    has_credito = "Credito" in means_ids
    if has_contado and has_credito:
        add_error(errors, "3247", "El tipo de transaccion no puede ser a la vez al Contado y al Credito")

    # ERROR 3248: PaymentMeansID repetido
    non_none = [m for m in means_ids if m is not None]
    if len(non_none) != len(set(non_none)):
        add_error(errors, "3248", "El tipo de transaccion o el identificador de la cuota no debe repetirse en el comprobante")

    # ERROR 3461: más de un PaymentMeansID dentro del mismo PaymentTerms
    for pt in forma_pago_terms:
        if len(all_(pt, "cbc:PaymentMeansID", ns)) > 1:
            add_error(errors, "3461", "La forma de pago y/o número de cuota no pueden estar contenidos en el mismo cac:PaymentTerms")

    # ERROR 3249/3251/3250/3253/3254/3255/3256/3265/3266/3267: crédito
    customer_type = _customer_type(root, ns)
    if has_credito and customer_type == "6":
        cuotas = [pt for pt in forma_pago_terms if re.match(r"^Cuota\d{3}$", text(pt, "cbc:PaymentMeansID", ns) or "")]
        if not cuotas:
            add_error(errors, "3249", "Si el tipo de transaccion es al Credito debe existir al menos información de una cuota de pago")

        # Monto neto pendiente
        net_term = next((pt for pt in forma_pago_terms if text(pt, "cbc:PaymentMeansID", ns) == "Credito"), None)
        if net_term is not None:
            net_amount = text(net_term, "cbc:Amount", ns)
            if net_amount is None:
                add_error(errors, "3251", "Si el tipo de transaccion es al Credito debe consignarse el Monto neto pendiente de pago")
            elif not _format_amount_positive(net_amount):
                add_error(errors, "3250", "El Monto neto pendiente de pago no cumple el formato definido")
            else:
                payable = parse_amount(text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount", ns))
                if payable is not None and parse_amount(net_amount) > payable:
                    add_error(errors, "3265", "El Monto neto pendiente de pago debe ser menor o igual al Importe total del comprobante")

                # ERROR 3319: suma de cuotas = monto neto
                sum_cuotas = sum(parse_amount(text(c, "cbc:Amount", ns)) or Decimal("0") for c in cuotas)
                if sum_cuotas != parse_amount(net_amount):
                    add_error(errors, "3319", "La suma de las cuotas debe ser igual al Monto neto pendiente de pago")

        for c in cuotas:
            cuota_amount = text(c, "cbc:Amount", ns)
            if cuota_amount is None:
                add_error(errors, "3254", "Si se consigna información de la cuota de pago, debe indicarse el monto de la cuota")
            elif not _format_amount_positive(cuota_amount):
                add_error(errors, "3253", "El Monto del pago único o de las cuotas no cumple el formato definido")
            else:
                payable = parse_amount(text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount", ns))
                if payable is not None and parse_amount(cuota_amount) > payable:
                    add_error(errors, "3266", "El Monto del pago único o de las cuotas debe ser menor o igual al Importe total del comprobante")

            due_date = text(c, "cbc:PaymentDueDate", ns)
            if due_date is None:
                add_error(errors, "3256", "Si se consigna información de la cuota de pago, debe indicarse la fecha del pago único o de las cuotas")
            elif not re.match(r"^\d{4}-\d{2}-\d{2}$", due_date):
                add_error(errors, "3255", "Fecha del pago único o de las cuotas no cumple el formato definido")
            else:
                issue = text(root, "cbc:IssueDate", ns)
                if issue is not None and due_date <= issue:
                    add_error(errors, "3267", "Fecha del pago único o de las cuotas no puede ser anterior o igual a la fecha de emisión del comprobante")

    # ERROR 3252: si existe cuota debe existir Credito
    cuotas = [pt for pt in forma_pago_terms if re.match(r"^Cuota\d{3}$", text(pt, "cbc:PaymentMeansID", ns) or "")]
    if cuotas and not has_credito:
        add_error(errors, "3252", "Si existe información de cuota de pago, el tipo de transaccion debe ser al credito")


def _validate_invoice_tipo_operacion(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    # ERROR 3205: InvoiceTypeCode@listID requerido
    if attr(root, "cbc:InvoiceTypeCode", "listID", ns) is None:
        add_error(errors, "3205", "Debe consignar el tipo de operación")


def _document_out_of_scope(errors: list[ValidationError]) -> None:
    """Reglas del batch que no están en rules_Invoice.txt o requieren contexto externo."""
    # FUERA DE ALCANCE - no aparecen en rules_Invoice.txt para Invoice:
    # 3094, 3095, 3096, 3097, 3099, 3100, 3101, 3106, 3112, 3113, 3116,
    # 3121, 3134, 3150, 3157, 3174, 3176-3203, 3206, 3207, 3209.
    # FUERA DE ALCANCE - requieren listado/padrón SUNAT:
    # 3262 (agente de retención), 3263, 3264, 3318, 3319 (ya cubiertas parcialmente),
    # 3151-3155 requieren código de producto SUNAT (no siempre disponible localmente).
    pass
