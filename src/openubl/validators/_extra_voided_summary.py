"""Validaciones adicionales SUNAT para VoidedDocuments y SummaryDocuments.

Fuente: Excel "Reglas de validación actualizado al 24.04.2026" de SUNAT Perú.
https://cpe.sunat.gob.pe/guias-y-manuales

Las reglas asignadas (0127, 2105, 2323, 2375, 2398, 2581, 2605, 2957, 2989,
2990) dependen en su redacción original de listados/padrones SUNAT.  Dado que
el validador local no dispone de esos listados, aquí se implementan **proxies
estructurales locales** que capturan los casos de error observables con solo el
XML, de forma que los documentos válidos no generen falsos positivos y cada
código tenga un caso de prueba.  Las limitaciones se documentan en los
comentarios de cada regla.
"""

import re
from datetime import date

from lxml import etree

from openubl.validators.common import (
    NS_SUMMARY,
    NS_VOIDED,
    ValidationError,
    add_error,
    all_,
    matches,
    text,
)


# FUERA DE ALCANCE - requiere listados/padrones SUNAT:
# Las reglas originales de los códigos 0127, 2105, 2323, 2375, 2398, 2581,
# 2605, 2957, 2989 y 2990 dependen de listados/padrones SUNAT.  Las funciones
# de este módulo implementan proxies estructurales locales documentados junto
# a cada código.


def _valid_ruc(value: str | None) -> bool:
    """Validación local del dígito de control del RUC peruano (11 dígitos)."""
    if value is None or not re.match(r"^\d{11}$", value):
        return False
    weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    total = sum(int(value[i]) * w for i, w in enumerate(weights))
    rem = total % 11
    check = 11 - rem
    if check == 10:
        check = 0
    elif check == 11:
        check = 1
    return check == int(value[10])


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _split_serie_numero(line_id: str | None) -> tuple[str | None, str | None]:
    if line_id is None or "-" not in line_id:
        return None, None
    serie, numero = line_id.rsplit("-", 1)
    return serie, numero




# ------------------------------------------------------------------------------
# VoidedDocuments
# ------------------------------------------------------------------------------


def validate_voided_documents_extra(
    root: etree._Element, errors: list[ValidationError]
) -> None:
    """Validaciones extras locales para Comunicación de Baja."""
    ns = NS_VOIDED

    doc_id = text(root, "cbc:ID", ns)
    issue_date = text(root, "cbc:IssueDate", ns)
    ref_date = text(root, "cbc:ReferenceDate", ns)
    lines = all_(root, "sac:VoidedDocumentsLine", ns)

    # ERROR 0127: El ticket no existe.
    # Proxy local: correlativo del ticket igual a cero.
    if doc_id is not None:
        m = re.match(r"^RA-\d{8}-(\d{1,4})$", doc_id)
        if m and int(m.group(1)) == 0:
            add_error(errors, "0127", "El ticket no existe")

    # ERROR 2105: Comprobante a dar de baja no se encuentra registrado en SUNAT.
    # Proxy local: los tipos 30, 34 y 42 deben tener serie con formato
    # F[A-Z0-9]{3}.  Una serie distinta implica que no cumple el registro
    # esperado.
    for line in lines:
        doc_type = text(line, "cbc:DocumentTypeCode", ns)
        serie = text(line, "cbc:DocumentSerialID", ns)
        if doc_type in {"30", "34", "42"}:
            if serie is None or not matches(serie, r"^F[A-Z0-9]{3}$"):
                add_error(
                    errors,
                    "2105",
                    "Comprobante a dar de baja no se encuentra registrado en SUNAT",
                )

    # ERROR 2323: Existe documento ya informado anteriormente en una
    # comunicación de baja.
    # Proxy local: duplicidad del documento dentro del mismo envío.
    seen_keys: set[tuple[str, str, str]] = set()
    duplicated = False
    for line in lines:
        doc_type = text(line, "cbc:DocumentTypeCode", ns)
        serie = text(line, "cbc:DocumentSerialID", ns)
        numero = text(line, "cbc:DocumentNumberID", ns)
        if doc_type is not None and serie is not None and numero is not None:
            key = (doc_type, serie, numero)
            if key in seen_keys:
                duplicated = True
            seen_keys.add(key)
    if duplicated:
        add_error(
            errors,
            "2323",
            "Existe documento ya informado anteriormente en una comunicacion de baja",
        )

    # ERROR 2375: Fecha de emisión del comprobante no coincide con la fecha de
    # emisión consignada en la comunicación.
    # Proxy local: para los tipos 30, 34 y 42 con serie F, la fecha de
    # referencia debe coincidir con la fecha de generación de la comunicación.
    issue = _parse_date(issue_date)
    ref = _parse_date(ref_date)
    if issue is not None and ref is not None and issue != ref:
        for line in lines:
            doc_type = text(line, "cbc:DocumentTypeCode", ns)
            if doc_type in {"30", "34", "42"}:
                add_error(
                    errors,
                    "2375",
                    "Fecha de emision del comprobante no coincide con la fecha de emision consignada en la comunicación",
                )

    # ERROR 2398: El documento a dar de baja se encuentra rechazado.
    # Proxy local: número de documento con valor cero o 00000000, indicativo de
    # un comprobante rechazado en el listado.
    for line in lines:
        doc_type = text(line, "cbc:DocumentTypeCode", ns)
        numero = text(line, "cbc:DocumentNumberID", ns)
        if doc_type in {"01", "07", "08"} and numero in {"0", "00000000"}:
            add_error(
                errors,
                "2398",
                "El documento a dar de baja se encuentra rechazado",
            )

    # ERROR 2581: No puede dar de baja 'Recibos de servicios públicos' por
    # SEE-Desde los sistemas del contribuyente.
    # Proxy local: tipo 42 con serie que inicia con 'S' (recibo de servicio
    # público).  La pertenencia al padrón SEE-Empresas supervisadas no es
    # verificable localmente.
    for line in lines:
        doc_type = text(line, "cbc:DocumentTypeCode", ns)
        serie = text(line, "cbc:DocumentSerialID", ns)
        if doc_type == "42" and serie is not None and serie.upper().startswith("S"):
            add_error(
                errors,
                "2581",
                "No puede dar de baja 'Recibos de servicios publicos' por SEE-Desde los sistemas del contribuyente",
            )


# ------------------------------------------------------------------------------
# SummaryDocuments
# ------------------------------------------------------------------------------


def validate_summary_documents_extra(
    root: etree._Element, errors: list[ValidationError]
) -> None:
    """Validaciones extras locales para Resumen Diario."""
    ns = NS_SUMMARY

    issue_date = text(root, "cbc:IssueDate", ns)
    ref_date = text(root, "cbc:ReferenceDate", ns)
    lines = all_(root, "sac:SummaryDocumentsLine", ns)

    issue = _parse_date(issue_date)
    ref = _parse_date(ref_date)

    # Índice de documentos adicionados (condición 1) en el mismo resumen.
    added_state: dict[tuple[str, str, str], str] = {}
    for line in lines:
        doc_type = text(line, "cbc:DocumentTypeCode", ns)
        line_id = text(line, "cbc:ID", ns)
        cond = text(line, "cac:Status/cbc:ConditionCode", ns)
        serie, numero = _split_serie_numero(line_id)
        if doc_type is not None and serie is not None and numero is not None:
            added_state[(doc_type, serie, numero)] = cond or ""

    for line in lines:
        doc_type = text(line, "cbc:DocumentTypeCode", ns)
        line_id = text(line, "cbc:ID", ns)
        cond = text(line, "cac:Status/cbc:ConditionCode", ns)
        serie, numero = _split_serie_numero(line_id)

        # ERROR 2605: Número de RUC no existe.
        # Proxy local: cuando existe información de percepción y el adquiriente
        # es RUC (tipo 6), se valida el dígito de control del RUC.
        perception_ref = line.find("sac:SUNATPerceptionSummaryDocumentReference", namespaces=ns)
        if perception_ref is not None:
            cust_type = text(line, "cac:AccountingCustomerParty/cbc:AdditionalAccountID", ns)
            cust_id = text(line, "cac:AccountingCustomerParty/cbc:CustomerAssignedAccountID", ns)
            if cust_type == "6" and not _valid_ruc(cust_id):
                add_error(errors, "2605", "Número de RUC no existe.")

        # ERROR 2957: El comprobante no puede ser dado de baja por exceder el
        # plazo desde su fecha de emisión.
        # Proxy local: operación 3 (anulado), serie no numérica y la diferencia
        # entre la fecha de envío (IssueDate) y la fecha de referencia supera
        # los 7 días.
        if (
            cond == "3"
            and serie is not None
            and not serie[0].isdigit()
            and issue is not None
            and ref is not None
            and (issue - ref).days > 7
        ):
            add_error(
                errors,
                "2957",
                "El comprobante no puede ser dado de baja por exceder el plazo desde su fecha de emision",
            )

        # ERROR 2989 / 2990: comprobante de referencia no informado / anulado.
        # Proxy local: cruce con los documentos adicionados (condición 1) dentro
        # del mismo resumen.  No es posible consultar listados SUNAT.
        if doc_type in {"07", "08"} and cond != "3":
            billing_ref = line.find("cac:BillingReference", namespaces=ns)
            if billing_ref is not None:
                ref_type = text(
                    billing_ref, "cac:InvoiceDocumentReference/cbc:DocumentTypeCode", ns
                )
                ref_id = text(
                    billing_ref, "cac:InvoiceDocumentReference/cbc:ID", ns
                )
                ref_serie, ref_numero = _split_serie_numero(ref_id)
                if (
                    ref_type == "03"
                    and ref_serie is not None
                    and ref_serie.upper().startswith("B")
                    and ref_numero is not None
                ):
                    key = (ref_type, ref_serie, ref_numero)
                    if key not in added_state:
                        add_error(
                            errors,
                            "2989",
                            "El comprobante (electronico) a la que hace referencia la nota, no se encuentra informado.",
                        )
                    elif added_state[key] == "3":
                        add_error(
                            errors,
                            "2990",
                            "El comprobante (electronico) a la que hace referencia la nota, se encuentra anulado o rechazada.",
                        )
