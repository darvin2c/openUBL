# Plan de implementación: 100% de validaciones SUNAT locales

## Contexto del proyecto

openUBL es una biblioteca Python para generar, firmar y validar documentos electrónicos UBL 2.1 para SUNAT Perú.
El validador actual está en `src/openubl/validator.py` (`SunatValidator`).
La fuente de verdad es el Excel `sunat_validaciones.xlsx` y los archivos `rules_*.txt`.

## Convenciones de código

- Python `snake_case`, tipado estricto.
- Errores se devuelven como `ValidationError(code, message)`.
- Cada regla implementada se anota con `# ERROR XXXX`.
- Las reglas fuera de alcance se marcan `# FUERA DE ALCANCE` y documentan el motivo.

## Alcance

Se implementarán **todas las reglas ERROR que se puedan evaluar localmente** con solo el XML de entrada.

**Fuera de alcance** (requieren contexto externo):
- Reglas que requieren padrón/listado SUNAT.
- Reglas que comparan con el nombre del archivo XML/ZIP.
- Reglas que dependen de la fecha de recepción/envío por SUNAT.
- Reglas que requieren consultar establecimientos anexos registrados.

## Helpers disponibles

Desde `src/openubl/validators/common.py`:

```python
from openubl.validators.common import (
    ValidationError,
    parse_xml, text, attr, exists, all_,
    is_numeric, parse_amount, matches, one_of, add_error,
    NS_INVOICE, NS_CREDIT_NOTE, NS_DEBIT_NOTE,
    NS_VOIDED, NS_SUMMARY, NS_PERCEPTION, NS_RETENTION, NS_SIGNATURE,
    CATALOG01, CATALOG03, CATALOG05, CATALOG05_NAMES,
    CATALOG06, CATALOG07, CATALOG51, CATALOG53,
)
```

## Estrategia

1. Cada subagente recibe un documento y la lista de reglas faltantes.
2. Crea un archivo `src/openubl/validators/_extra_<documento>.py` con funciones de validación.
3. Crea un archivo `tests/_test_validator_<documento>_extra.py` con tests parametrizados.
4. No modifica `src/openubl/validator.py` ni `tests/test_validator.py` (el agente principal integra al final).
5. Usa los fixtures existentes o crea helpers para generar XML válido y mutarlo.

## Estructura del módulo extra

```python
# src/openubl/validators/_extra_invoice.py
from lxml import etree
from openubl.validators.common import (
    ValidationError, text, attr, exists, all_, parse_amount,
    matches, add_error, NS_INVOICE, CATALOG03,
)


def validate_invoice_extra(root: etree._Element, errors: list[ValidationError]) -> None:
    ns = NS_INVOICE
    # ERROR 1004: InvoiceTypeCode
    if text(root, "cbc:InvoiceTypeCode", ns) is None:
        add_error(errors, "1004", "No existe el tag cbc:InvoiceTypeCode o es vacío")
    # ... más reglas
```

Luego se integra en `SunatValidator.validate_invoice` llamando a `validate_invoice_extra(root, errors)`.

## Reglas asignadas por documento

Ver `validator-gap-classified.json` para la lista completa.
Resumen de reglas implementables faltantes:

- Invoice: 223
- CreditNote: 92
- DebitNote: 88
- Retention: 26
- Perception: 8
- VoidedDocuments: 6
- SummaryDocuments: 4
- Signature: 8

## Tests

Cada regla debe tener un caso de prueba parametrizado:

```python
@pytest.mark.parametrize("code,mutator", [
    ("1004", lambda r: r.find("cbc:InvoiceTypeCode", namespaces=NS_INVOICE).getparent().remove(...)),
])
def test_invoice_extra(code, mutator):
    root = etree.fromstring(_valid_invoice_xml().encode("utf-8"))
    mutator(root)
    errors = validate_invoice_extra(root, [])
    codes = [e.code for e in errors]
    assert code in codes
```

## Integración final

El agente principal:
1. Revisa los módulos extra.
2. Los importa en `src/openubl/validator.py`.
3. Llama a cada función desde el dispatcher correspondiente.
4. Integra los tests en `tests/test_validator.py`.
5. Ejecuta el suite completo y corrige fallas.
6. Actualiza documentación.
