"""Validaciones SUNAT adicionales para Invoice (batch 4).

Códigos cubiertos: 1003, 2364, 2365, 2410, 2595, 2596, 2597, 2954, 3051,
3064, 3088, 3099, 3136-3145, 3157, 3159-3167, 3168-3171, 3204, 3206,
3236, 3237, 3238, 3316, 3317, 3497-3502.

Fuente: Excel SUNAT "Reglas de validación actualizado al 24.04.2026".
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from lxml import etree

from openubl.validators.common import (
    CATALOG01,
    CATALOG05_NAMES,
    CATALOG51,
    CATALOG53,
    NS_INVOICE,
    ValidationError,
    add_error,
    all_,
    attr,
    exists,
    parse_amount,
    text,
)


# Catálogo N.° 02 – Tipo de moneda (ISO 4217 Alpha, subset SUNAT).
_CATALOG02 = {
    "AED", "AFN", "ALL", "AMD", "ANG", "AOA", "ARS", "AUD", "AWG", "AZN",
    "BAM", "BBD", "BDT", "BGN", "BHD", "BIF", "BMD", "BND", "BOB", "BOV",
    "BRL", "BSD", "BTN", "BWP", "BYN", "BZD", "CAD", "CDF", "CHE", "CHF",
    "CHW", "CLF", "CLP", "CNY", "COP", "COU", "CRC", "CUC", "CUP", "CVE",
    "CZK", "DJF", "DKK", "DOP", "DZD", "EGP", "ERN", "ETB", "EUR", "FJD",
    "FKP", "GBP", "GEL", "GHS", "GIP", "GMD", "GNF", "GTQ", "GYD", "HKD",
    "HNL", "HRK", "HTG", "HUF", "IDR", "ILS", "INR", "IQD", "IRR", "ISK",
    "JMD", "JOD", "JPY", "KES", "KGS", "KHR", "KMF", "KPW", "KRW", "KWD",
    "KYD", "KZT", "LAK", "LBP", "LKR", "LRD", "LSL", "LYD", "MAD", "MDL",
    "MGA", "MKD", "MMK", "MNT", "MOP", "MRU", "MUR", "MVR", "MWK", "MXN",
    "MXV", "MYR", "MZN", "NAD", "NGN", "NIO", "NOK", "NPR", "NZD", "OMR",
    "PAB", "PEN", "PGK", "PHP", "PKR", "PLN", "PYG", "QAR", "RON", "RSD",
    "RUB", "RWF", "SAR", "SBD", "SCR", "SDG", "SEK", "SGD", "SHP", "SLE",
    "SLL", "SOS", "SRD", "SSP", "STN", "SVC", "SYP", "SZL", "THB", "TJS",
    "TMT", "TND", "TOP", "TRY", "TTD", "TVD", "TWD", "TZS", "UAH", "UGX",
    "USD", "USN", "UYI", "UYU", "UYW", "UZS", "VED", "VES", "VND", "VUV",
    "WST", "XAF", "XAG", "XAU", "XBA", "XBB", "XBC", "XBD", "XCD", "XDR",
    "XOF", "XPD", "XPF", "XPT", "XSU", "XTS", "XUA", "XXX", "YER", "ZAR",
    "ZMW", "ZWL",
}

# Catálogo N.° 04 – Países (ISO 3166-1 alpha-2, subset usado por SUNAT).
_CATALOG04 = {
    "AF", "AX", "AL", "DZ", "AS", "AD", "AO", "AI", "AQ", "AG", "AR", "AM",
    "AW", "AU", "AT", "AZ", "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ",
    "BM", "BT", "BO", "BQ", "BA", "BW", "BV", "BR", "IO", "BN", "BG", "BF",
    "BI", "CV", "KH", "CM", "CA", "KY", "CF", "TD", "CL", "CN", "CX", "CC",
    "CO", "KM", "CG", "CD", "CK", "CR", "CI", "HR", "CU", "CW", "CY", "CZ",
    "DK", "DJ", "DM", "DO", "EC", "EG", "SV", "GQ", "ER", "EE", "ET", "FK",
    "FO", "FJ", "FI", "FR", "GF", "PF", "TF", "GA", "GM", "GE", "DE", "GH",
    "GI", "GR", "GL", "GD", "GP", "GU", "GT", "GG", "GN", "GW", "GY", "HT",
    "HM", "VA", "HN", "HK", "HU", "IS", "IN", "ID", "IR", "IQ", "IE", "IM",
    "IL", "IT", "JM", "JP", "JE", "JO", "KZ", "KE", "KI", "KP", "KR", "KW",
    "KG", "LA", "LV", "LB", "LS", "LR", "LY", "LI", "LT", "LU", "MO", "MG",
    "MW", "MY", "MV", "ML", "MT", "MH", "MQ", "MR", "MU", "YT", "MX", "FM",
    "MD", "MC", "MN", "ME", "MS", "MA", "MZ", "MM", "NA", "NR", "NP", "NL",
    "NC", "NZ", "NI", "NE", "NG", "NU", "NF", "MK", "MP", "NO", "OM", "PK",
    "PW", "PS", "PA", "PG", "PY", "PE", "PH", "PN", "PL", "PT", "PR", "QA",
    "RE", "RO", "RU", "RW", "BL", "SH", "KN", "LC", "MF", "PM", "VC", "WS",
    "SM", "ST", "SA", "SN", "RS", "SC", "SL", "SG", "SX", "SK", "SI", "SB",
    "SO", "ZA", "GS", "SS", "ES", "LK", "SD", "SR", "SJ", "SE", "CH", "SY",
    "TW", "TJ", "TZ", "TH", "TL", "TG", "TK", "TO", "TT", "TN", "TR", "TM",
    "TC", "TV", "UG", "UA", "AE", "GB", "US", "UM", "UY", "UZ", "VU", "VE",
    "VN", "VG", "VI", "WF", "EH", "YE", "ZM", "ZW",
}

# Catálogo N.° 16 – Tipo de precio de venta unitario.
_CATALOG16 = {"01", "02"}

# Conceptos adicionales de línea reconocidos localmente.
_HUESPED_CODES = {
    "0202": {"4009", "4008", "4000", "4007", "4001", "4002", "4003", "4004", "4006", "4005"},
    "0205": {"4009", "4008", "4000", "4007"},
}

_BVME_CODES = ["4040", "4041", "4049", "4042", "4043", "4044", "4045", "4046", "4047", "4048"]

_CARTA_PORTE_CODES = ["4030", "4031", "4032", "4033"]

# Conceptos AFP/CUSPP (valores aproximados usados en el Excel SUNAT).
_CUSPP_CODE = "7010"
_PERIODO_CODE = "7011"
_INTERES_MORATORIO_CODE = "7013"

# Contratos de colaboración empresarial.
_CONTRATO_DOC_TYPE_CODE = "07"  # valor asumido para documento adicional "contrato"


def validate_invoice_extra4(root: etree._Element, errors: list[ValidationError]) -> None:
    """Ejecuta todas las reglas del batch 4 sobre un Invoice."""
    ns = NS_INVOICE

    _validate_catalogos(root, ns, errors)
    _validate_referencias(root, ns, errors)
    _validate_lineas_impuestos(root, ns, errors)
    _validate_sectoriales(root, ns, errors)
    _validate_retencion_segunda(root, ns, errors)
    _validate_contratos_colaboracion(root, ns, errors)


def _tipo_operacion(root: etree._Element, ns: dict) -> str | None:
    """Devuelve el código numérico del tipo de operación (Catálogo 51)."""
    raw = text(root, "cbc:Note", ns)
    if raw is None:
        raw = attr(root, "cbc:InvoiceTypeCode", "listID", ns)
    if raw is None:
        return None
    if raw.startswith("Catalog51."):
        name = raw.split(".", 1)[1]
        mapping = {
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
            "VENTA_NO_DOMICILIADA_GRATUITA_2": "0208",
            "EXPORTACION_DE_SERVICIOS": "0301",
            "VENTA_INTERNA_OBRA_POR_IMPO_DIR": "0302",
            "VENTA_INTERNA_OBRA_POR_IMPO_IND": "0303",
            "VENTA_INTERNA_OBRA_POR_IMPO_DIR_2": "0304",
            "VENTA_INTERNA_OBRA_POR_IMPO_IND_2": "0305",
            "VENTA_INTERNA_OBRA_POR_IMPO_DIR_3": "0306",
            "VENTA_INTERNA_OBRA_POR_IMPO_IND_3": "0307",
            "VENTA_INTERNA_OBRA_POR_IMPO_DIR_4": "0308",
            "VENTA_INTERNA_OBRA_POR_IMPO_IND_4": "0309",
            "VENTA_INTERNA_OBRA_POR_IMPO_DIR_5": "0310",
            "VENTA_INTERNA_CREDITO": "1001",
            "VENTA_INTERNA_CREDITO_2": "1002",
            "VENTA_INTERNA_CREDITO_3": "1003",
            "VENTA_INTERNA_CREDITO_4": "1004",
            "OPERACION_SUJETA_PERCEPCION": "2001",
            "OPERACION_SUJETA_RETENCION": "2002",
            "OPERACION_SUJETA_DETRACCION": "2003",
            "OPERACION_SUJETA_RETENCION_Y_DETRACCION": "2004",
            "OPERACION_SUJETA_PERCEPCION_Y_DETRACCION": "2005",
            "OPERACION_SUJETA_PERCEPCION_RETENCION_Y_DETRACCION": "2006",
            "OPERACION_SUJETA_PERCEPCION_Y_RETENCION": "2007",
            "OPERACION_SUJETA_PERCEPCION_RETENCION_Y_DETRACCION_2": "2008",
            "OPERACION_SUJETA_PERCEPCION_2": "2009",
            "OPERACION_SUJETA_PERCEPCION_3": "2010",
            "OPERACION_SUJETA_PERCEPCION_4": "2011",
            "OPERACION_SUJETA_PERCEPCION_5": "2012",
            "OPERACION_SUJETA_PERCEPCION_6": "2013",
            "OPERACION_SUJETA_PERCEPCION_7": "2014",
            "OPERACION_SUJETA_PERCEPCION_8": "2015",
            "OPERACION_SUJETA_PERCEPCION_9": "2016",
            "OPERACION_SUJETA_PERCEPCION_10": "2017",
            "OPERACION_SUJETA_PERCEPCION_11": "2018",
            "OPERACION_SUJETA_PERCEPCION_12": "2019",
            "OPERACION_SUJETA_PERCEPCION_13": "2020",
            "OPERACION_SUJETA_PERCEPCION_14": "2021",
            "OPERACION_SUJETA_PERCEPCION_15": "2022",
            "OPERACION_SUJETA_PERCEPCION_16": "2023",
            "OPERACION_SUJETA_PERCEPCION_17": "2024",
            "OPERACION_SUJETA_PERCEPCION_18": "2025",
            "OPERACION_SUJETA_PERCEPCION_19": "2026",
            "OPERACION_SUJETA_PERCEPCION_20": "2027",
            "OPERACION_SUJETA_PERCEPCION_21": "2028",
            "OPERACION_SUJETA_PERCEPCION_22": "2029",
            "OPERACION_SUJETA_PERCEPCION_23": "2030",
            "OPERACION_SUJETA_RETENCION_2": "2031",
            "OPERACION_SUJETA_RETENCION_3": "2032",
            "OPERACION_SUJETA_RETENCION_4": "2033",
            "OPERACION_SUJETA_RETENCION_5": "2034",
            "OPERACION_SUJETA_RETENCION_6": "2035",
            "OPERACION_SUJETA_RETENCION_7": "2036",
            "OPERACION_SUJETA_RETENCION_8": "2037",
            "OPERACION_SUJETA_RETENCION_9": "2038",
            "OPERACION_SUJETA_RETENCION_10": "2039",
            "OPERACION_SUJETA_RETENCION_11": "2040",
            "OPERACION_SUJETA_RETENCION_12": "2041",
            "OPERACION_SUJETA_RETENCION_13": "2042",
            "OPERACION_SUJETA_RETENCION_14": "2043",
            "OPERACION_SUJETA_RETENCION_15": "2044",
            "OPERACION_SUJETA_RETENCION_16": "2045",
            "OPERACION_SUJETA_RETENCION_17": "2046",
            "OPERACION_SUJETA_RETENCION_18": "2047",
            "OPERACION_SUJETA_RETENCION_19": "2048",
            "OPERACION_SUJETA_RETENCION_20": "2049",
            "OPERACION_SUJETA_RETENCION_21": "2050",
            "OPERACION_SUJETA_RETENCION_22": "2051",
            "OPERACION_SUJETA_RETENCION_23": "2052",
            "OPERACION_SUJETA_RETENCION_24": "2053",
            "OPERACION_SUJETA_RETENCION_25": "2054",
            "OPERACION_SUJETA_RETENCION_26": "2055",
            "OPERACION_SUJETA_RETENCION_27": "2056",
            "OPERACION_SUJETA_RETENCION_28": "2057",
            "OPERACION_SUJETA_RETENCION_29": "2058",
            "OPERACION_SUJETA_RETENCION_30": "2059",
            "OPERACION_SUJETA_RETENCION_31": "2060",
            "OPERACION_SUJETA_RETENCION_32": "2061",
            "OPERACION_SUJETA_RETENCION_33": "2062",
            "OPERACION_SUJETA_RETENCION_34": "2063",
            "OPERACION_SUJETA_RETENCION_35": "2064",
            "OPERACION_SUJETA_RETENCION_36": "2065",
            "OPERACION_SUJETA_RETENCION_37": "2066",
            "OPERACION_SUJETA_RETENCION_38": "2067",
            "OPERACION_SUJETA_RETENCION_39": "2068",
            "OPERACION_SUJETA_RETENCION_40": "2069",
            "OPERACION_SUJETA_RETENCION_41": "2070",
            "OPERACION_SUJETA_RETENCION_42": "2071",
            "OPERACION_SUJETA_RETENCION_43": "2072",
            "OPERACION_SUJETA_RETENCION_44": "2073",
            "OPERACION_SUJETA_RETENCION_45": "2074",
            "OPERACION_SUJETA_RETENCION_46": "2075",
            "OPERACION_SUJETA_RETENCION_47": "2076",
            "OPERACION_SUJETA_RETENCION_48": "2077",
            "OPERACION_SUJETA_RETENCION_49": "2078",
            "OPERACION_SUJETA_RETENCION_50": "2079",
            "OPERACION_SUJETA_RETENCION_51": "2080",
            "OPERACION_SUJETA_RETENCION_52": "2081",
            "OPERACION_SUJETA_RETENCION_53": "2082",
            "OPERACION_SUJETA_RETENCION_54": "2083",
            "OPERACION_SUJETA_RETENCION_55": "2084",
            "OPERACION_SUJETA_RETENCION_56": "2085",
            "OPERACION_SUJETA_RETENCION_57": "2086",
            "OPERACION_SUJETA_RETENCION_58": "2087",
            "OPERACION_SUJETA_RETENCION_59": "2088",
            "OPERACION_SUJETA_RETENCION_60": "2089",
            "OPERACION_SUJETA_RETENCION_61": "2090",
            "OPERACION_SUJETA_RETENCION_62": "2091",
            "OPERACION_SUJETA_RETENCION_63": "2092",
            "OPERACION_SUJETA_RETENCION_64": "2093",
            "OPERACION_SUJETA_RETENCION_65": "2094",
            "OPERACION_SUJETA_RETENCION_66": "2095",
            "OPERACION_SUJETA_RETENCION_67": "2096",
            "OPERACION_SUJETA_RETENCION_68": "2097",
            "OPERACION_SUJETA_RETENCION_69": "2098",
            "OPERACION_SUJETA_RETENCION_70": "2099",
            "OPERACION_SUJETA_RETENCION_71": "2100",
            "OPERACION_SUJETA_RETENCION_72": "2101",
            "OPERACION_SUJETA_RETENCION_73": "2102",
            "OPERACION_SUJETA_RETENCION_74": "2103",
            "OPERACION_SUJETA_RETENCION_75": "2104",
        }
        return mapping.get(name, raw)
    return raw


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


def _format_percent(value: str | None) -> bool:
    """Valida formato porcentaje decimal positivo de hasta 3 enteros y 5 decimales."""
    if value is None:
        return False
    try:
        v = Decimal(value)
        if v < 0:
            return False
        s = value.lstrip("0") or "0"
        if "." in s:
            int_part, frac_part = s.split(".")
        else:
            int_part, frac_part = s, ""
        return len(int_part) <= 3 and len(frac_part) <= 5
    except InvalidOperation:
        return False


# ---------------------------------------------------------------------------
# Catálogos de cabecera
# ---------------------------------------------------------------------------

def _validate_catalogos(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    # ERROR 1003: InvoiceTypeCode válido según catálogo 01.
    invoice_type_code = text(root, "cbc:InvoiceTypeCode", ns)
    if invoice_type_code is not None and invoice_type_code not in CATALOG01:
        add_error(errors, "1003", "El valor del tipo de documento es inválido o no coincide con el nombre del archivo")

    # ERROR 3088: moneda válida según catálogo 02.
    currency = text(root, "cbc:DocumentCurrencyCode", ns)
    if currency is not None and currency not in _CATALOG02:
        add_error(errors, "3088", "El valor ingresado como moneda del comprobante no es valido (catalogo nro 02)")

    # ERROR 3206: tipo de operación válido según catálogo 51.
    op = _tipo_operacion(root, ns)
    if op is not None and op not in CATALOG51:
        add_error(errors, "3206", "El dato ingresado como tipo de operación no corresponde a un valor esperado (catálogo nro. 51)")


# ---------------------------------------------------------------------------
# Referencias (guías y documentos relacionados)
# ---------------------------------------------------------------------------

def _validate_referencias(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    # ERROR 2364: guía de remisión repetida.
    guias: list[tuple[str | None, str | None]] = []
    for ref in all_(root, "cac:DespatchDocumentReference", ns):
        ref_id = text(ref, "cbc:ID", ns)
        ref_type = text(ref, "cbc:DocumentTypeCode", ns)
        guias.append((ref_id, ref_type))
    if len(guias) != len(set(guias)):
        add_error(errors, "2364", "El comprobante contiene un tipo y número de Guía de Remisión repetido")

    # ERROR 2365: documento relacionado repetido.
    docs: list[tuple[str | None, str | None]] = []
    for ref in all_(root, "cac:AdditionalDocumentReference", ns):
        ref_id = text(ref, "cbc:ID", ns)
        ref_type = text(ref, "cbc:DocumentTypeCode", ns)
        docs.append((ref_id, ref_type))
    if len(docs) != len(set(docs)):
        add_error(errors, "2365", "El comprobante contiene un tipo y número de Documento Relacionado repetido")


# ---------------------------------------------------------------------------
# Líneas / impuestos
# ---------------------------------------------------------------------------

def _validate_lineas_impuestos(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    for line in all_(root, "cac:InvoiceLine", ns):
        # ERROR 2410: PriceTypeCode válido según catálogo 16.
        for acp in all_(line, "cac:PricingReference/cac:AlternativeConditionPrice", ns):
            price_type = text(acp, "cbc:PriceTypeCode", ns)
            if price_type is not None and price_type not in _CATALOG16:
                add_error(errors, "2410", "Se ha consignado un valor invalido en el campo cbc:PriceTypeCode")

        # ERROR 2954: motivo de cargo/descuento por línea válido según catálogo 53.
        for ac in all_(line, "cac:AllowanceCharge", ns):
            reason = text(ac, "cbc:AllowanceChargeReasonCode", ns)
            if reason is not None and reason not in CATALOG53:
                add_error(errors, "2954", "El valor ingresado como codigo de motivo de cargo/descuento por linea no es valido (catalogo 53)")

        # ERROR 3051: nombre de tributo vs código de tributo de línea.
        for ts in all_(line, "cac:TaxTotal/cac:TaxSubtotal", ns):
            tax_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns)
            tax_name = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:Name", ns)
            expected_name = CATALOG05_NAMES.get(tax_code) if tax_code is not None else None
            if expected_name is not None and tax_name is not None and tax_name != expected_name:
                add_error(errors, "3051", "Nombre de tributo no corresponde al código de tributo de la linea")

        # ERROR 3064: valor del concepto por línea.
        for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", ns):
            code = text(prop, "cbc:NameCode", ns)
            if code is None:
                continue
            has_value = text(prop, "cbc:Value", ns) is not None
            has_quantity = exists(prop, "cbc:ValueQuantity", ns)
            if not has_value and not has_quantity:
                add_error(errors, "3064", "El XML no contiene tag o no existe información del valor del concepto por linea")

        # ERROR 3236, 3237, 3238: BaseUnitMeasure y PerUnitAmount para ICBPER.
        for ts in all_(line, "cac:TaxTotal/cac:TaxSubtotal", ns):
            tax_code = text(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID", ns)
            if tax_code != "7152":
                continue
            base_unit = text(ts, "cbc:BaseUnitMeasure", ns)
            if base_unit is None:
                add_error(errors, "3237", "Debe consignar el campo cac:TaxSubtotal/cbc:BaseUnitMeasure a nivel de ítem")
            elif base_unit != "NIU":
                add_error(errors, "3236", "El valor ingresado en el campo cac:TaxSubtotal/cbc:BaseUnitMeasure no corresponde al valor esperado")
            per_unit = text(ts, "cbc:PerUnitAmount", ns)
            if per_unit is not None:
                amount = parse_amount(per_unit)
                if amount is None or amount <= 0:
                    add_error(errors, "3238", "El valor ingresado en el campo cac:TaxSubtotal/cbc:PerUnitAmount del ítem no corresponde al valor esperado")


# ---------------------------------------------------------------------------
# Casos especiales sectoriales
# ---------------------------------------------------------------------------

def _validate_sectoriales(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    op = _tipo_operacion(root, ns)

    # ERROR 3099: país de uso incorrecto (operaciones 0201 / 0208).
    if op in {"0201", "0208"}:
        country = text(root, "cac:Delivery/cac:DeliveryLocation/cac:Address/cac:Country/cbc:IdentificationCode", ns)
        if country is not None and country not in _CATALOG04:
            add_error(errors, "3099", "El dato ingresado como pais de uso, exploracion o aprovechamiento es incorrecto")

    for line in all_(root, "cac:InvoiceLine", ns):
        codes = _item_property_codes(line, ns)

        # Turismo (0202 / 0205).
        if op in _HUESPED_CODES:
            required = _HUESPED_CODES[op]
            for req in required:
                if req not in codes:
                    if req == "4009":
                        add_error(errors, "3136", "El XML no contiene el tag de numero de documentos del huesped")
                    elif req == "4008":
                        add_error(errors, "3137", "El XML no contiene el tag de tipo de documentos del huesped")
                    elif req == "4000":
                        add_error(errors, "3138", "El XML no contiene el tag de codigo de pais de emision del documento de identidad")
                    elif req == "4007":
                        add_error(errors, "3139", "El XML no contiene el tag de apellidos y nombres del huesped")
                    elif req == "4001":
                        add_error(errors, "3140", "El XML no contiene el tag de codigo del pais de residencia")
                    elif req == "4002":
                        add_error(errors, "3141", "El XML no contiene el tag de fecha de ingreso del pais")
                    elif req == "4003":
                        add_error(errors, "3142", "El XML no contiene el tag de fecha de ingreso al establecimiento")
                    elif req == "4004":
                        add_error(errors, "3143", "El XML no contiene el tag de fecha de salida del establecimiento")
                    elif req == "4006":
                        add_error(errors, "3144", "El XML no contiene el tag de fecha de consumo")
                    elif req == "4005":
                        add_error(errors, "3145", "El XML no contiene el tag de numero de dias de permanencia")

        # BVME transporte ferroviario (0302).
        if op == "0302":
            # ERROR 3157: tipo de documento del agente de viajes (schemeID).
            agent_id = root.find("cac:AccountingSupplierParty/cac:Party/cac:AgentParty/cac:PartyIdentification/cbc:ID", namespaces=ns)
            if agent_id is not None and agent_id.get("schemeID") is None:
                add_error(errors, "3157", "El XML no contiene el tag de BVME transporte ferroviario: Agente de Viajes: Tipo de documento")

            for req in _BVME_CODES:
                if req not in codes:
                    if req == "4040":
                        add_error(errors, "3159", "El XML no contiene el tag de BVME transporte ferroviario: Pasajero - Apellidos y Nombres")
                    elif req == "4041":
                        add_error(errors, "3160", "El XML no contiene el tag de BVME transporte ferroviario: Pasajero - Tipo de documento de identidad")
                    elif req == "4049":
                        add_error(errors, "3204", "El XML no contiene el tag de BVME transporte ferroviario: Pasajero - Número de documento de identidad")
                    elif req == "4042":
                        add_error(errors, "3161", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Ciudad o lugar de origen - Código de ubigeo")
                    elif req == "4043":
                        add_error(errors, "3162", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Ciudad o lugar de origen - Dirección detallada")
                    elif req == "4044":
                        add_error(errors, "3163", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Ciudad o lugar de destino - Código de ubigeo")
                    elif req == "4045":
                        add_error(errors, "3164", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Ciudad o lugar de destino - Dirección detallada")
                    elif req == "4046":
                        add_error(errors, "3165", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte:Número de asiento")
                    elif req == "4047":
                        add_error(errors, "3166", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Hora programada de inicio de viaje")
                    elif req == "4048":
                        add_error(errors, "3167", "El XML no contiene el tag de BVME transporte ferroviario: Servicio transporte: Fecha programada de inicio de viaje")

        # Carta porte aéreo (0301).
        if op == "0301":
            for req in _CARTA_PORTE_CODES:
                if req not in codes:
                    if req == "4030":
                        add_error(errors, "3168", "El XML no contiene el tag de Carta Porte Aéreo:  Lugar de origen - Código de ubigeo")
                    elif req == "4031":
                        add_error(errors, "3169", "El XML no contiene el tag de Carta Porte Aéreo:  Lugar de origen - Dirección detallada")
                    elif req == "4032":
                        add_error(errors, "3170", "El XML no contiene el tag de Carta Porte Aéreo:  Lugar de destino - Código de ubigeo")
                    elif req == "4033":
                        add_error(errors, "3171", "El XML no contiene el tag de Carta Porte Aéreo:  Lugar de destino - Dirección detallada")

        # AFP / CUSPP (conceptos adicionales).
        if _CUSPP_CODE in codes:
            if not _has_item_property(line, ns, _CUSPP_CODE):
                add_error(errors, "2595", "Falta consignar informacion del CUSPP")
            else:
                for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", ns):
                    if text(prop, "cbc:NameCode", ns) == _CUSPP_CODE and text(prop, "cbc:Value", ns) is None:
                        add_error(errors, "2595", "Falta consignar informacion del CUSPP")
                        break
        if _PERIODO_CODE in codes:
            for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", ns):
                if text(prop, "cbc:NameCode", ns) == _PERIODO_CODE and text(prop, "cbc:Value", ns) is None:
                    add_error(errors, "2596", "Falta consignar informacion del Periodo")
                    break
        if _INTERES_MORATORIO_CODE in codes:
            for prop in all_(line, "cac:Item/cac:AdditionalItemProperty", ns):
                if text(prop, "cbc:NameCode", ns) == _INTERES_MORATORIO_CODE and text(prop, "cbc:Value", ns) is None:
                    add_error(errors, "2597", "Falta consignar información del monto de interes moratorio")
                    break


# ---------------------------------------------------------------------------
# Retención de segunda categoría
# ---------------------------------------------------------------------------

def _validate_retencion_segunda(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    op = _tipo_operacion(root, ns)
    has_retencion = False
    for ac in all_(root, "cac:AllowanceCharge", ns):
        indicator = text(ac, "cbc:ChargeIndicator", ns)
        reason = text(ac, "cbc:AllowanceChargeReasonCode", ns)
        if indicator == "false" and reason == "63":
            has_retencion = True
            break

    # ERROR 3316: operación 2002 requiere datos de retención de segunda categoría.
    if op == "2002" and not has_retencion:
        add_error(errors, "3316", "Si el tipo de operación es 2002, debe informar los datos de la retención de segunda categoria")

    # ERROR 3317: datos de retención de segunda categoría requieren operación 2002.
    if has_retencion and op != "2002":
        add_error(errors, "3317", "Si consigna infomacion de la retencion de segunda categoria, el tipo de operacion debe ser 2002")


# ---------------------------------------------------------------------------
# Contratos de colaboración empresarial
# ---------------------------------------------------------------------------

def _validate_contratos_colaboracion(root: etree._Element, ns: dict, errors: list[ValidationError]) -> None:
    contratos = [
        ref
        for ref in all_(root, "cac:AdditionalDocumentReference", ns)
        if text(ref, "cbc:DocumentTypeCode", ns) == _CONTRATO_DOC_TYPE_CODE
    ]
    if not contratos:
        return

    # ERROR 3498: no más de un número de contrato.
    if len(contratos) > 1:
        add_error(errors, "3498", "No se permite mas de un numero de contrato de colaboracion empresarial")

    contrato = contratos[0]
    numero = text(contrato, "cbc:ID", ns)
    tipo = text(contrato, "cbc:DocumentType", ns)
    descripcion = text(contrato, "cbc:DocumentDescription", ns)

    # ERROR 3499: si informa número, debe informar tipo, descripción y porcentaje.
    porcentaje = None
    pp_elem = contrato.find("cac:ShareholderParty/cbc:PartecipationPercent", namespaces=ns)
    if pp_elem is not None:
        porcentaje = (pp_elem.text or "").strip() or None
    if numero is not None and (tipo is None or descripcion is None or porcentaje is None):
        add_error(errors, "3499", "Si informa Numero de contrato, debe consignar el Tipo de contrato, la Descripcion de contrato y el Porcentaje de participacion")

    # ERROR 3497: tipo de contrato debe ser 1 o 2.
    if tipo is not None and tipo not in {"1", "2"}:
        add_error(errors, "3497", "El tipo de contrato debe ser 1-ventas o 2-adquisiciones")

    # ERROR 3500: porcentaje con formato correcto.
    if porcentaje is not None and not _format_percent(porcentaje):
        add_error(errors, "3500", "El Porcentaje de participacion no cumple con el formato o longitud especificada")

    # ERROR 3501: número de contrato con formato correcto.
    if numero is not None and not (numero and 1 <= len(numero) <= 20):
        add_error(errors, "3501", "El Numero del contrato de colaboracion empresarial no cumple el formato o longitud establecida")

    # ERROR 3502: descripción con formato correcto.
    if descripcion is not None and not (1 <= len(descripcion) <= 100):
        add_error(errors, "3502", "La Descripcion del contrato de colaboracion empresarial no cumple el formato o longitud establecida")
