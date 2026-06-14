"""Validaciones SUNAT adicionales para Notas de Débito (DebitNote) - batch 2.

Reglas faltantes del Excel SUNAT 2026 que no requieren padrones, listados ni
estados en SUNAT. Se ejecuta después de `validate_debit_note_extra`.
"""

from __future__ import annotations

import re
from decimal import Decimal

from lxml import etree

from openubl.models.catalog import Catalog16, Catalog2, Catalog6, Catalog7
from openubl.validators.common import (
    CATALOG05_NAMES,
    CATALOG07,
    NS_DEBIT_NOTE,
    ValidationError,
    add_error,
    all_,
    attr,
    exists,
    parse_amount,
    text,
)


# Catálogo N.° 02 - Tipo de Moneda (códigos ISO 4217 aceptados por SUNAT).
_CATALOG02 = {
    "PEN", "USD", "EUR", "GBP", "JPY", "CNY", "CAD", "AUD", "CHF", "SEK",
    "NZD", "MXN", "BRL", "ARS", "CLP", "COP", "UYU", "BOB", "PYG", "PAB",
    "VEF", "ZAR", "RUB", "INR", "KRW", "HKD", "SGD", "TWD", "THB", "MYR",
    "IDR", "PHP", "VND", "AED", "SAR", "QAR", "KWD", "OMR", "BHD", "JOD",
    "TRY", "NOK", "DKK", "PLN", "CZK", "HUF", "RON", "BGN", "HRK", "ILS",
    "EGP", "NGN", "KES", "MAD", "TND", "DZD", "XOF", "XAF", "CDF", "TZS",
    "UGX", "ZMW", "BWP", "NAD", "MZN", "GHS", "SLL", "LRD", "GNF", "ETB",
    "DJF", "RWF", "BIF", "MWK", "SCR", "MUR", "SZL", "LSL", "AOA", "ERN",
    "SOS", "ZWL", "MGA", "MRO", "STD", "CVE", "KMF", "XPF",
}

# Catálogo N.° 06 - Tipo de documento de identidad.
_CATALOG06 = {"0", "1", "4", "6", "7", "A", "B", "C", "D", "E", "G"}

# Códigos de propiedad adicional para contratos de colaboración empresarial.
_CONTRATO_INDICADOR = "7012"
_CONTRATO_NUMERO = "7013"
_CONTRATO_FECHA_INICIO = "7014"
_CONTRATO_TIPO = "7015"
_CONTRATO_DESCRIPCION = "7016"
_CONTRATO_PORCENTAJE = "7017"

# Códigos de propiedad adicional para créditos hipotecarios.
_CREDITO_PRODUCTO = "7000"
_CREDITO_INMUEBLE = "7002"
_CREDITO_PARTIDA = "7003"
_CREDITO_CONTRATO = "7004"
_CREDITO_FECHA = "7005"
_CREDITO_UBIGEO = "7006"
_CREDITO_DIRECCION = "7007"

_TOLERANCE = Decimal("1")


def _norm_catalog6(value: str | None) -> str | None:
    """Normaliza 'Catalog6.DNI' a '1'; deja los valores numéricos intactos."""
    if value is None:
        return None
    if value.startswith("Catalog6."):
        name = value.split(".", 1)[1]
        try:
            return Catalog6[name].value
        except KeyError:
            return None
    return value if value in _CATALOG06 else None


def _norm_catalog7(value: str | None) -> str | None:
    """Normaliza 'Catalog7.GRAVADO...' al código numérico SUNAT."""
    if value is None:
        return None
    if value.startswith("Catalog7."):
        name = value.split(".", 1)[1]
        try:
            return Catalog7[name].value
        except KeyError:
            return None
    return value if value in CATALOG07 else None


def _norm_catalog2(value: str | None) -> str | None:
    """Normaliza 'Catalog2.PEN' a 'PEN'."""
    if value is None:
        return None
    if value.startswith("Catalog2."):
        name = value.split(".", 1)[1]
        try:
            return Catalog2[name].value
        except KeyError:
            return name if re.fullmatch(r"[A-Z]{3}", name) else None
    return value if re.fullmatch(r"[A-Z]{3}", value) else None


def _norm_catalog16(value: str | None) -> str | None:
    """Normaliza 'Catalog16.PRECIO_UNITARIO...' al código numérico."""
    if value is None:
        return None
    if value.startswith("Catalog16."):
        name = value.split(".", 1)[1]
        try:
            return Catalog16[name].value
        except KeyError:
            return None
    return value if value in {"01", "02"} else None


def _matches(value: str | None, pattern: str) -> bool:
    if value is None:
        return False
    return re.match(pattern, value) is not None


def _doc_serie(root: etree._Element) -> str:
    doc_id = text(root, "cbc:ID", NS_DEBIT_NOTE) or ""
    return doc_id.split("-")[0] if "-" in doc_id else doc_id


def _resp_code(root: etree._Element) -> str | None:
    return text(root, "cac:DiscrepancyResponse/cbc:ResponseCode", NS_DEBIT_NOTE)


def _item_property_codes(line: etree._Element) -> set[str]:
    """Devuelve los cbc:NameCode de AdditionalItemProperty de la línea."""
    codes: set[str] = set()
    for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", NS_DEBIT_NOTE):
        code = text(prop, "cbc:NameCode", NS_DEBIT_NOTE)
        if code is not None:
            codes.add(code)
    return codes


def _item_properties(line: etree._Element) -> list[etree._Element]:
    return all_(line, "cac:Item/cac:AdditionalItemProperty", NS_DEBIT_NOTE)


def _line_tax_subtotals(line: etree._Element) -> list[etree._Element]:
    return all_(line, "cac:TaxTotal/cac:TaxSubtotal", NS_DEBIT_NOTE)


def _line_tax_total_amount(line: etree._Element) -> Decimal | None:
    return parse_amount(text(line, "cac:TaxTotal/cbc:TaxAmount", NS_DEBIT_NOTE))


def _within_tolerance(a: Decimal | None, b: Decimal | None, tol: Decimal = _TOLERANCE) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
# Dispatcher principal
# ---------------------------------------------------------------------------

def validate_debit_note_extra2(root: etree._Element, errors: list[ValidationError]) -> None:
    """Ejecuta las reglas SUNAT faltantes para un DebitNote ya parseado."""
    _check_discrepancy_response(root, errors)
    _check_parties(root, errors)
    _check_billing_references(root, errors)
    _check_lines(root, errors)
    _check_line_tax_names(root, errors)
    _check_line_tax_total(root, errors)
    _check_igv_rate(root, errors)
    _check_currency(root, errors)
    _check_item_properties(root, errors)
    _check_despatch_document_references(root, errors)
    _check_additional_document_references(root, errors)


# ---------------------------------------------------------------------------
# DiscrepancyResponse (cabecera / discrepancia)
# ---------------------------------------------------------------------------

def _check_discrepancy_response(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 2128, 2135, 2136, 3203, 3230, 3221."""
    resp_code = _resp_code(root)
    if resp_code is None:
        add_error(
            errors,
            "2128",
            "No existe el Tag UBL cac:DiscrepancyResponse/cbc:ResponseCode o es vacío",
        )

    resp_codes = all_(root, "cac:DiscrepancyResponse/cbc:ResponseCode", NS_DEBIT_NOTE)
    if len(resp_codes) > 1:
        add_error(
            errors,
            "3203",
            "El tag UBL cac:DiscrepancyResponse/cbc:ResponseCode se repite dentro del mismo documento",
        )

    resp_desc = text(root, "cac:DiscrepancyResponse/cbc:Description", NS_DEBIT_NOTE)
    if resp_desc is None:
        add_error(
            errors,
            "2136",
            "No existe el Tag UBL cac:DiscrepancyResponse/cbc:Description o es vacío",
        )
    elif not _matches(resp_desc, r"^.{1,500}$"):
        add_error(
            errors,
            "2135",
            "El formato del Tag UBL cac:DiscrepancyResponse/cbc:Description es diferente a alfanumérico de 1 hasta 500 caracteres",
        )

    # ERROR 3230: afectación IVAP (17) requiere tipo de nota 12.
    if resp_code != "12":
        for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
            for ts in _line_tax_subtotals(line):
                exemption = _norm_catalog7(
                    text(ts, "cac:TaxCategory/cbc:TaxExemptionReasonCode", NS_DEBIT_NOTE)
                )
                if exemption == "17":
                    add_error(
                        errors,
                        "3230",
                        "Si 'Afectación al IGV o IVAP' es '17', el 'Código de tipo de nota de débito' debe ser '12' (Ajustes afectos al IVAP)",
                    )
                    return

    # ERROR 3221: tipo de nota 12 no admite tributos 9995, 9997 ni 9998.
    if resp_code == "12":
        for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
            tax_codes = {
                text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
                for ts in _line_tax_subtotals(line)
            }
            if tax_codes.intersection({"9995", "9997", "9998"}):
                add_error(
                    errors,
                    "3221",
                    "Si 'Código de tipo de nota de débito' es '12' (IVAP), no puede existir código de tributo 9995, 9997 ni 9998",
                )
                return


# ---------------------------------------------------------------------------
# Emisor / receptor
# ---------------------------------------------------------------------------

def _check_parties(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3029, 2511, 2679."""
    supplier_id_elem = root.find(
        "cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID",
        namespaces=NS_DEBIT_NOTE,
    )
    if supplier_id_elem is not None:
        scheme = supplier_id_elem.get("schemeID")
        if scheme is None or scheme == "":
            add_error(
                errors,
                "3029",
                "No existe el atributo cac:AccountingSupplierParty/.../cbc:ID@schemeID o es vacío",
            )
        elif _norm_catalog6(scheme) != "6":
            add_error(
                errors,
                "2511",
                "El valor del Tag UBL cac:AccountingSupplierParty/.../cbc:ID@schemeID es diferente a '6'",
            )

    customer_id_elem = root.find(
        "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
        namespaces=NS_DEBIT_NOTE,
    )
    if customer_id_elem is None:
        add_error(
            errors,
            "2679",
            "No existe el Tag UBL cac:AccountingCustomerParty/.../cbc:ID o es vacío",
        )
    else:
        scheme = customer_id_elem.get("schemeID")
        if scheme is None or scheme == "":
            add_error(
                errors,
                "2679",
                "No existe el atributo cac:AccountingCustomerParty/.../cbc:ID@schemeID o es vacío",
            )


# ---------------------------------------------------------------------------
# BillingReference (documento modificado)
# ---------------------------------------------------------------------------

def _check_billing_references(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 2524, 2884, 3194, 2594."""
    refs = all_(root, "cac:BillingReference/cac:InvoiceDocumentReference", NS_DEBIT_NOTE)
    doc_serie = _doc_serie(root)
    resp_code = _resp_code(root)

    if not refs:
        add_error(
            errors,
            "2524",
            "Debe indicar el documento afectado por la nota",
        )
        return

    if len(refs) > 1:
        add_error(
            errors,
            "3194",
            "Solo es permitido registrar un documento que modifica",
        )

    doc_types = [
        text(ref, "cbc:DocumentTypeCode", NS_DEBIT_NOTE)
        for ref in refs
        if text(ref, "cbc:DocumentTypeCode", NS_DEBIT_NOTE) is not None
    ]
    if len(doc_types) > 1 and len(set(doc_types)) > 1:
        add_error(
            errors,
            "2884",
            "Si existe más de un documento que se modifica, no todos tienen el mismo 'Tipo de documento que modifica'",
        )

    for ref in refs:
        ref_type = text(ref, "cbc:DocumentTypeCode", NS_DEBIT_NOTE)
        if resp_code not in {"03", "13"} and doc_serie and doc_serie[0].isdigit() and ref_type not in {"01", "03"}:
            add_error(
                errors,
                "2594",
                "Si 'Código de tipo de nota de débito' es diferente de '03' y '13' y la Serie empieza con número, el 'Tipo de documento que modifica' debe ser '01' o '03'",
            )


# ---------------------------------------------------------------------------
# Líneas
# ---------------------------------------------------------------------------

def _check_lines(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 2137, 2139, 2410."""
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        line_id = text(line, "cbc:ID", NS_DEBIT_NOTE)
        if line_id is None or not _matches(line_id, r"^\d{1,3}$") or line_id == "0":
            add_error(
                errors,
                "2137",
                "El formato del Tag UBL cbc:ID es diferente de numérico de hasta 3 dígitos; o es igual a cero",
            )

        qty_text = text(line, "cbc:DebitedQuantity", NS_DEBIT_NOTE)
        if qty_text is not None and not _matches(qty_text, r"^\d{1,12}(\.\d{1,10})?$"):
            add_error(
                errors,
                "2139",
                "El formato del Tag UBL cbc:DebitedQuantity es diferente de decimal positivo de 12 enteros y hasta 10 decimales",
            )

        for acp in all_(line, "cac:PricingReference/cac:AlternativeConditionPrice", NS_DEBIT_NOTE):
            price_type = _norm_catalog16(text(acp, "cbc:PriceTypeCode", NS_DEBIT_NOTE))
            if price_type is None:
                add_error(
                    errors,
                    "2410",
                    "Se ha consignado un valor inválido en el campo cbc:PriceTypeCode",
                )


# ---------------------------------------------------------------------------
# Nombres de tributo por línea
# ---------------------------------------------------------------------------

def _check_line_tax_names(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3051: nombre de tributo debe coincidir con el código."""
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        for ts in _line_tax_subtotals(line):
            tax_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
            tax_name = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name", NS_DEBIT_NOTE)
            expected = CATALOG05_NAMES.get(tax_code) if tax_code is not None else None
            if expected is not None and tax_name != expected:
                add_error(
                    errors,
                    "3051",
                    f"Nombre de tributo no corresponde al código de tributo '{tax_code}' de la línea",
                )
                return


# ---------------------------------------------------------------------------
# Total de tributos por línea
# ---------------------------------------------------------------------------

def _check_line_tax_total(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3292: TaxTotal/cbc:TaxAmount = suma de TaxSubtotal/cbc:TaxAmount."""
    codes = {"1000", "1016", "2000", "7152", "9999"}
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        total = _line_tax_total_amount(line)
        if total is None:
            continue
        subtotal = Decimal("0")
        for ts in _line_tax_subtotals(line):
            code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
            if code in codes:
                subtotal += parse_amount(text(ts, "cbc:TaxAmount", NS_DEBIT_NOTE)) or Decimal("0")
        if not _within_tolerance(total, subtotal):
            add_error(
                errors,
                "3292",
                "El importe total de impuestos por línea no coincide con la sumatoria de los impuestos por línea",
            )
            return


# ---------------------------------------------------------------------------
# Tasa del IGV
# ---------------------------------------------------------------------------

def _check_igv_rate(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3462: misma tasa de IGV en todas las líneas afectas."""
    rates: set[Decimal] = set()
    has_subject = False
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        for ts in _line_tax_subtotals(line):
            tax_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", NS_DEBIT_NOTE)
            taxable = parse_amount(text(ts, "cbc:TaxableAmount", NS_DEBIT_NOTE))
            percent = parse_amount(text(ts, "cac:TaxCategory/cbc:Percent", NS_DEBIT_NOTE))
            exemption = _norm_catalog7(
                text(ts, "cac:TaxCategory/cbc:TaxExemptionReasonCode", NS_DEBIT_NOTE)
            )
            if tax_code == "1000" and taxable is not None and taxable > 0:
                has_subject = True
                if percent is not None:
                    rates.add(percent)
            if (
                tax_code == "9996"
                and taxable is not None
                and taxable > 0
                and exemption in {"11", "12", "13", "14", "15", "16"}
            ):
                has_subject = True
                if percent is not None:
                    rates.add(percent)
    if has_subject and len(rates) > 1:
        add_error(
            errors,
            "3462",
            "La tasa del IGV debe ser la misma en todas las líneas o ítems del documento y debe corresponder con una tasa vigente",
        )


# ---------------------------------------------------------------------------
# Moneda
# ---------------------------------------------------------------------------

def _check_currency(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3088: moneda válida según catálogo 02."""
    currency = _norm_catalog2(text(root, "cbc:DocumentCurrencyCode", NS_DEBIT_NOTE))
    if currency is not None and currency not in _CATALOG02:
        add_error(
            errors,
            "3088",
            "El valor ingresado como moneda del comprobante no es válido (catálogo nro 02)",
        )


# ---------------------------------------------------------------------------
# Propiedades adicionales del ítem
# ---------------------------------------------------------------------------

def _check_item_properties(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 3064, 3151-3155, 3497-3502."""
    for line in all_(root, "cac:DebitNoteLine", NS_DEBIT_NOTE):
        codes = _item_property_codes(line)
        props = {text(p, "cbc:NameCode", NS_DEBIT_NOTE): p for p in _item_properties(line)}

        # ERROR 3064: si existe la propiedad, debe tener valor.
        for prop in _item_properties(line):
            code = text(prop, "cbc:NameCode", NS_DEBIT_NOTE)
            value = text(prop, "cbc:Value", NS_DEBIT_NOTE)
            if code is not None and value is None:
                add_error(
                    errors,
                    "3064",
                    "El XML no contiene tag o no existe información del valor del concepto por línea",
                )
                return

        # Créditos hipotecarios (producto 84121901 aproximado por propiedad 7000).
        if _CREDITO_PRODUCTO in codes:
            for req in (_CREDITO_CONTRATO, _CREDITO_FECHA):
                if req not in codes:
                    if req == _CREDITO_CONTRATO:
                        add_error(
                            errors,
                            "3152",
                            "El XML no contiene el tag de Créditos Hipotecarios: Número de contrato",
                        )
                    else:
                        add_error(
                            errors,
                            "3153",
                            "El XML no contiene el tag de Créditos Hipotecarios: Fecha de otorgamiento del crédito",
                        )
            if _CREDITO_INMUEBLE in codes:
                for req in (_CREDITO_PARTIDA, _CREDITO_UBIGEO, _CREDITO_DIRECCION):
                    if req not in codes:
                        if req == _CREDITO_PARTIDA:
                            add_error(
                                errors,
                                "3151",
                                "El XML no contiene el tag de Créditos Hipotecarios: Partida Registral",
                            )
                        elif req == _CREDITO_UBIGEO:
                            add_error(
                                errors,
                                "3154",
                                "El XML no contiene el tag de Créditos Hipotecarios: Dirección del predio - Código de ubigeo",
                            )
                        else:
                            add_error(
                                errors,
                                "3155",
                                "El XML no contiene el tag de Créditos Hipotecarios: Dirección del predio - Dirección completa",
                            )

        # Contratos de colaboración empresarial.
        contrato_codes = {
            _CONTRATO_NUMERO, _CONTRATO_TIPO, _CONTRATO_DESCRIPCION, _CONTRATO_PORCENTAJE
        }
        if contrato_codes.intersection(codes):
            numero_count = sum(
                1 for p in _item_properties(line)
                if text(p, "cbc:NameCode", NS_DEBIT_NOTE) == _CONTRATO_NUMERO
            )
            if numero_count > 1:
                add_error(
                    errors,
                    "3498",
                    "No se permite más de un número de contrato de colaboración empresarial",
                )

            if _CONTRATO_NUMERO in props:
                numero = text(props[_CONTRATO_NUMERO], "cbc:Value", NS_DEBIT_NOTE)
                if numero is None or not _matches(numero, r"^.{1,30}$"):
                    add_error(
                        errors,
                        "3501",
                        "El Número del contrato de colaboración empresarial no cumple el formato o longitud establecida",
                    )
                # ERROR 3499: si hay número, deben existir tipo, descripción y porcentaje.
                if _CONTRATO_TIPO not in codes:
                    add_error(
                        errors,
                        "3499",
                        "Si informa Número de contrato, debe consignar el Tipo de contrato, la Descripción de contrato y el Porcentaje de participación",
                    )
                if _CONTRATO_DESCRIPCION not in codes:
                    add_error(
                        errors,
                        "3499",
                        "Si informa Número de contrato, debe consignar el Tipo de contrato, la Descripción de contrato y el Porcentaje de participación",
                    )
                if _CONTRATO_PORCENTAJE not in codes:
                    add_error(
                        errors,
                        "3499",
                        "Si informa Número de contrato, debe consignar el Tipo de contrato, la Descripción de contrato y el Porcentaje de participación",
                    )

            if _CONTRATO_TIPO in props:
                tipo = text(props[_CONTRATO_TIPO], "cbc:Value", NS_DEBIT_NOTE)
                if tipo not in {"1", "2"}:
                    add_error(
                        errors,
                        "3497",
                        "El tipo de contrato debe ser 1-ventas o 2-adquisiciones",
                    )

            if _CONTRATO_DESCRIPCION in props:
                descripcion = text(props[_CONTRATO_DESCRIPCION], "cbc:Value", NS_DEBIT_NOTE)
                if descripcion is None or not _matches(descripcion, r"^.{1,100}$"):
                    add_error(
                        errors,
                        "3502",
                        "La Descripción del contrato de colaboración empresarial no cumple el formato o longitud establecida",
                    )

            if _CONTRATO_PORCENTAJE in props:
                porcentaje = text(props[_CONTRATO_PORCENTAJE], "cbc:Value", NS_DEBIT_NOTE)
                if porcentaje is None or not _matches(porcentaje, r"^\d{1,3}(\.\d{1,2})?$"):
                    add_error(
                        errors,
                        "3500",
                        "El Porcentaje de participación no cumple con el formato o longitud especificada",
                    )


# ---------------------------------------------------------------------------
# Guías de remisión y documentos relacionados
# ---------------------------------------------------------------------------

def _check_despatch_document_references(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 2364: guía de remisión repetida."""
    pairs: list[tuple[str | None, str | None]] = []
    for ref in all_(root, "cac:DespatchDocumentReference", NS_DEBIT_NOTE):
        ref_type = text(ref, "cbc:DocumentTypeCode", NS_DEBIT_NOTE)
        ref_id = text(ref, "cbc:ID", NS_DEBIT_NOTE)
        pairs.append((ref_type, ref_id))
    if len(pairs) != len(set(pairs)):
        add_error(
            errors,
            "2364",
            "El comprobante contiene un tipo y número de Guía de Remisión repetido",
        )


def _check_additional_document_references(root: etree._Element, errors: list[ValidationError]) -> None:
    """ERROR 2365, 2426: documento relacionado / otro documento relacionado duplicado."""
    pairs: list[tuple[str | None, str | None]] = []
    for ref in all_(root, "cac:AdditionalDocumentReference", NS_DEBIT_NOTE):
        ref_type = text(ref, "cbc:DocumentTypeCode", NS_DEBIT_NOTE)
        ref_id = text(ref, "cbc:ID", NS_DEBIT_NOTE)
        pairs.append((ref_type, ref_id))
    if len(pairs) != len(set(pairs)):
        add_error(
            errors,
            "2365",
            "El comprobante contiene un tipo y número de Documento Relacionado repetido",
        )
        add_error(
            errors,
            "2426",
            "Documentos relacionados duplicados en el comprobante",
        )
