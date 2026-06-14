"""Validaciones SUNAT adicionales para Perception y Retention.

Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
https://cpe.sunat.gob.pe/guias-y-manuales

Este módulo cubre las reglas faltantes del catálogo Percepciones/Retenciones
que pueden evaluarse localmente con solo el XML de entrada. Las reglas que
requieren padrón/listado SUNAT se marcan como FUERA DE ALCANCE.
"""

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
    NS_PERCEPTION,
    NS_RETENTION,
)


# ---------------------------------------------------------------------------
# Perception
# ---------------------------------------------------------------------------

def validate_perception_extra(root: etree._Element, errors: list[ValidationError]) -> None:
    """Reglas SUNAT adicionales para comprobantes de Percepción.

    Estas validaciones se ejecutan sobre el XML renderizado de un
    comprobante de percepción UBL 2.1. Reglas que requieren padrones o
    listados SUNAT se documentan como FUERA DE ALCANCE.
    """
    ns = NS_PERCEPTION

    # FUERA DE ALCANCE - 2609: requiere "Listado de comprobantes de pago electrónicos"
    # FUERA DE ALCANCE - 2610: requiere "Listado de comprobantes de pago electrónicos"
    # FUERA DE ALCANCE - 3312: requiere "Listado de autorizaciones de comprobantes de pago físicos"
    # 3323 ya está implementado en SunatValidator._validate_perception
    # FUERA DE ALCANCE - 3325: requiere "Listado de autorizaciones de comprobantes de pago físicos"
    # FUERA DE ALCANCE - 3326: requiere listado de comprobantes de percepción excepcional activos
    # FUERA DE ALCANCE - 3328: requiere "Listado de comprobantes de pago electrónicos"
    # FUERA DE ALCANCE - 3329: requiere "Listado de comprobantes de pago electrónicos"

    # ERROR 3327: emisión excepcional con régimen 02 no puede referenciar documento régimen 01.
    # Según SUNAT, si el Indicador de emisión excepcional es "01" y el régimen de percepción
    # es "02" (adquisición de combustible), no está permitido que el documento relacionado sea
    # del régimen "01" (venta interna). Localmente se interpreta el tipo de documento "01" como
    # indicativo del régimen 01.
    exceptional = text(root, "sac:ExceptionalIndicator", ns)
    regime = text(root, "sac:SUNATPerceptionSystemCode", ns)
    if exceptional == "01" and regime == "02":
        for ref in all_(root, "sac:SUNATPerceptionDocumentReference", ns):
            ref_id_elem = ref.find("cbc:ID", namespaces=ns)
            ref_type = ref_id_elem.get("schemeID") if ref_id_elem is not None else None
            if ref_type == "01":
                add_error(
                    errors,
                    "3327",
                    "No esta permitido referenciar el Código del régimen de percepción con el regimen del documento relacionado.",
                )


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

def validate_retention_extra(root: etree._Element, errors: list[ValidationError]) -> None:
    """Reglas SUNAT adicionales para comprobantes de Retención."""
    ns = NS_RETENTION

    # ERROR 2111 / 2110: UBLVersionID
    ubl_version = text(root, "cbc:UBLVersionID", ns)
    if ubl_version is None or ubl_version == "":
        add_error(errors, "2111", "El Tag UBL cbc:UBLVersionID está vacío")
    elif ubl_version != "2.0":
        add_error(errors, "2110", "El valor del Tag UBL cbc:UBLVersionID es diferente a '2.0'")

    # ERROR 2113 / 2112: CustomizationID
    customization = text(root, "cbc:CustomizationID", ns)
    if customization is None or customization == "":
        add_error(errors, "2113", "El Tag UBL cbc:CustomizationID está vacío")
    elif customization != "1.0":
        add_error(errors, "2112", "El valor del Tag UBL cbc:CustomizationID es diferente a '1.0'")

    # ERROR 1001: ID format
    doc_id = text(root, "cbc:ID", ns)
    if doc_id is None or not matches(doc_id, r"^(R[A-Z0-9]{3}-\d{1,8}|\d{1,4}-\d{1,8})$"):
        add_error(
            errors,
            "1001",
            "El formato del Tag UBL cbc:ID no tiene el formato: [R][A-Z0-9]{3}-[0-9]{1,8} o [0-9]{1,4}-[0-9]{1,8}",
        )

    # ERROR 2678 / 2511: AgentParty schemeID
    agent_id_elem = root.find("cac:AgentParty/cac:PartyIdentification/cbc:ID", namespaces=ns)
    if agent_id_elem is not None:
        agent_scheme = agent_id_elem.get("schemeID")
        if agent_scheme is None or agent_scheme == "":
            add_error(
                errors,
                "2678",
                "No existe el Tag UBL cac:AgentParty/.../cbc:ID@schemeID o es vacío",
            )
        elif agent_scheme != "6":
            add_error(
                errors,
                "2511",
                "El valor del Tag UBL cac:AgentParty/.../cbc:ID@schemeID es diferente a '6'",
            )

    # ERROR 1037 / 1038: AgentParty RegistrationName
    agent_name = text(root, "cac:AgentParty/cac:PartyLegalEntity/cbc:RegistrationName", ns)
    if agent_name is None:
        add_error(
            errors,
            "1037",
            "No existe el Tag UBL cac:AgentParty/.../cbc:RegistrationName o es vacío",
        )
    elif not matches(agent_name, r"^.{1,1500}$"):
        add_error(
            errors,
            "1038",
            "El formato del Tag UBL cac:AgentParty/.../cbc:RegistrationName es diferente a alfanumérico de hasta 1500 caracteres",
        )

    # ERROR 2548: AgentParty Country = PE
    agent_country = text(
        root, "cac:AgentParty/cac:PostalAddress/cac:Country/cbc:IdentificationCode", ns
    )
    if agent_country is not None and agent_country != "PE":
        add_error(
            errors,
            "2548",
            "El valor del Tag UBL cac:AgentParty/.../cbc:IdentificationCode es diferente a 'PE'",
        )

    # ERROR 2723 / 2724 / 2620 ya están en SunatValidator._validate_retention
    # ERROR 2516: ReceiverParty schemeID
    receiver_id_elem = root.find("cac:ReceiverParty/cac:PartyIdentification/cbc:ID", namespaces=ns)
    if receiver_id_elem is not None:
        receiver_scheme = receiver_id_elem.get("schemeID")
        if receiver_scheme is None or receiver_scheme == "":
            add_error(
                errors,
                "2516",
                "No existe el Tag UBL cac:ReceiverParty/.../cbc:ID@schemeID o es vacío",
            )

    # ERROR 2134 / 2133: ReceiverParty RegistrationName
    receiver_name = text(root, "cac:ReceiverParty/cac:PartyLegalEntity/cbc:RegistrationName", ns)
    if receiver_name is None:
        add_error(
            errors,
            "2134",
            "No existe el Tag UBL cac:ReceiverParty/.../cbc:RegistrationName o es vacío",
        )
    elif not matches(receiver_name, r"^.{1,1500}$"):
        add_error(
            errors,
            "2133",
            "El formato del Tag UBL cac:ReceiverParty/.../cbc:RegistrationName es diferente a alfanumérico de hasta 1500 caracteres",
        )

    # ERROR 2548: ReceiverParty Country = PE
    receiver_country = text(
        root, "cac:ReceiverParty/cac:PostalAddress/cac:Country/cbc:IdentificationCode", ns
    )
    if receiver_country is not None and receiver_country != "PE":
        add_error(
            errors,
            "2548",
            "El valor del Tag UBL cac:ReceiverParty/.../cbc:IdentificationCode es diferente a 'PE'",
        )

    # ERROR 2669: TotalInvoiceAmount format
    total_invoice_amount = parse_amount(text(root, "cbc:TotalInvoiceAmount", ns))
    if total_invoice_amount is None or total_invoice_amount <= 0:
        add_error(
            errors,
            "2669",
            "El formato del Tag UBL cbc:TotalInvoiceAmount es diferente a decimal positivo de 12 enteros y 2 decimales o es cero (0)",
        )

    # ERROR 2691 / 2692 / 2693 / 2694 / 2696: document references
    for ref in all_(root, "sac:SUNATRetentionDocumentReference", ns):
        ref_id_elem = ref.find("cbc:ID", namespaces=ns)
        ref_id = (ref_id_elem.text or "").strip() if ref_id_elem is not None else ""
        ref_type = ref_id_elem.get("schemeID") if ref_id_elem is not None else None

        # ERROR 2691 / 2692
        if ref_type is None or ref_type == "":
            add_error(
                errors,
                "2691",
                "No existe el Tag UBL sac:SUNATRetentionDocumentReference/cbc:ID@schemeID o es vacío",
            )
        elif ref_type not in {"01", "12", "07", "08", "20"}:
            add_error(
                errors,
                "2692",
                "El valor del Tag UBL sac:SUNATRetentionDocumentReference/cbc:ID@schemeID es diferente a '01', '12', '07', '08', '20'",
            )

        # ERROR 2693
        if ref_id == "":
            add_error(
                errors,
                "2693",
                "El valor del Tag UBL sac:SUNATRetentionDocumentReference/cbc:ID está vacío",
            )
        # ERROR 2694
        elif ref_type is not None:
            if ref_type == "12":
                if not matches(ref_id, r"^[a-zA-Z0-9-]{1,20}(-\d{1,20})$"):
                    add_error(
                        errors,
                        "2694",
                        "Si 'Tipo de documento relacionado' es '12', el formato del Tag UBL es diferente a alfanumérico de 1 a 20 caracteres seguido de guión y número",
                    )
            else:
                if not matches(ref_id, r"^(E001|((F|R)[A-Z0-9]{3})|(\d{4}))-(?!0+$)(\d{1,8})$"):
                    add_error(
                        errors,
                        "2694",
                        "Si 'Tipo de documento relacionado' es diferente a '12', el formato del Tag UBL es diferente a (E001|((F|R)[A-Z0-9]{3})|([0-9]{4}))-[0-9]{1,8}",
                    )

        # ERROR 2696
        ref_total = parse_amount(text(ref, "cbc:TotalInvoiceAmount", ns))
        if ref_total is None or ref_total <= 0:
            add_error(
                errors,
                "2696",
                "El formato del Tag UBL sac:SUNATRetentionDocumentReference/cbc:TotalInvoiceAmount es diferente a decimal positivo de 12 enteros y 2 decimales o es cero (0)",
            )
    # ERROR 2626: uniqueness of document reference + payment id
    payment_keys: list[tuple[str, str]] = []
    for ref in all_(root, "sac:SUNATRetentionDocumentReference", ns):
        ref_id_elem = ref.find("cbc:ID", namespaces=ns)
        ref_id = (ref_id_elem.text or "").strip() if ref_id_elem is not None else ""
        ref_type = ref_id_elem.get("schemeID") if ref_id_elem is not None else None
        if ref_type == "07":
            continue
        payment = ref.find("cac:Payment", namespaces=ns)
        payment_id = text(payment, "cbc:ID", ns) if payment is not None else None
        if payment_id is not None:
            key = (ref_id, payment_id)
            if key in payment_keys:
                add_error(
                    errors,
                    "2626",
                    "El Nro. de documento con el número de pago ya se encuentra en la Relación de Documentos Relacionados agregados.",
                )
            payment_keys.append(key)

    # ERROR 2719 / 2715 / 2716 / 2721 / 2722 / 2749: ExchangeRate for non-PEN references
    for ref in all_(root, "sac:SUNATRetentionDocumentReference", ns):
        ref_id_elem = ref.find("cbc:ID", namespaces=ns)
        ref_type = ref_id_elem.get("schemeID") if ref_id_elem is not None else None
        if ref_type == "07":
            continue
        ref_currency = attr(ref, "cbc:TotalInvoiceAmount", "currencyID", ns)
        info = ref.find("sac:SUNATRetentionInformation", namespaces=ns)
        if info is None:
            continue
        exchange = info.find("cac:ExchangeRate", namespaces=ns)
        if ref_currency is not None and ref_currency != "PEN":
            if exchange is None:
                add_error(
                    errors,
                    "2719",
                    "El XML no contiene el tag o no existe información de la moneda de referencia para el tipo de cambio",
                )
                continue
            if not exists(exchange, "cbc:SourceCurrencyCode", ns):
                add_error(
                    errors,
                    "2719",
                    "El XML no contiene el tag o no existe información de la moneda de referencia para el tipo de cambio",
                )
            if not exists(exchange, "cbc:CalculationRate", ns):
                add_error(
                    errors,
                    "2721",
                    "El XML no contiene el tag o no existe información del tipo de cambio",
                )
            if not exists(exchange, "cbc:Date", ns):
                add_error(
                    errors,
                    "2722",
                    "El XML no contiene el tag o no existe información de la fecha de cambio",
                )
        if exchange is not None:
            source = text(exchange, "cbc:SourceCurrencyCode", ns)
            target = text(exchange, "cbc:TargetCurrencyCode", ns)
            calc = parse_amount(text(exchange, "cbc:CalculationRate", ns))
            if ref_currency is not None and source != ref_currency:
                add_error(
                    errors,
                    "2749",
                    "La moneda de referencia para el tipo de cambio debe ser la misma que la del documento relacionado",
                )
            if target is not None and target != "PEN":
                add_error(
                    errors,
                    "2715",
                    "El valor de la moneda objetivo para la Tasa de Cambio debe ser PEN",
                )
            if calc is not None and calc <= 0:
                add_error(
                    errors,
                    "2716",
                    "El dato ingresado en el tipo de cambio debe ser numérico mayor a cero",
                )

    # FUERA DE ALCANCE - 2602: requiere Catálogo N.° 22 (régimen de percepción)
    # FUERA DE ALCANCE - 2603: requiere Catálogo N.° 22 (porcentaje de percepción)
    # FUERA DE ALCANCE - 2609: requiere listado de comprobantes de pago electrónicos
    # FUERA DE ALCANCE - 2610: requiere listado de comprobantes de pago electrónicos
    # FUERA DE ALCANCE - 2617: requiere padrón de contribuyentes
    # FUERA DE ALCANCE - 2618: requiere Catálogo N.° 23 (régimen de retención)
    # FUERA DE ALCANCE - 2619: requiere Catálogo N.° 23 (tasa de retención)
    # FUERA DE ALCANCE - 2621: requiere listado de contribuyentes
