# openUBL

[![PyPI](https://img.shields.io/pypi/v/openubl)](https://pypi.org/project/openubl/)
[![npm](https://img.shields.io/npm/v/@openubl/sdk)](https://www.npmjs.com/package/@openubl/sdk)

**Genera, firma y valida documentos electrónicos UBL 2.1 para SUNAT (Perú) — sin complicaciones.**

openUBL es una biblioteca Python con API REST incluida. Genera XML válido para facturas, notas de crédito, notas de débito, comunicaciones de baja, resúmenes diarios, percepciones y retenciones. Firma digitalmente con certificados XAdES-EPES y valida contra las reglas SUNAT antes de enviar.

## ¿Por qué openUBL?

- **Sin dependencias externas** — todo en Python. No necesitas servicios de terceros para generar XML.
- **API REST lista para usar** — levantas FastAPI y generas documentos vía HTTP.
- **SDK TypeScript** — tipos generados desde OpenAPI, con autocompletado completo.
- **Firma digital integrada** — firma con certificado PEM sin herramientas externas.
- **Validación SUNAT** — detecta errores antes del envío, no después.
- **Documentación completa** — guías paso a paso en [https://darvin2c.github.io/openUBL](https://darvin2c.github.io/openUBL)

## Instalación rápida

### Python

```bash
pip install openubl
```

```python
from openubl.models import Invoice, Proveedor, Cliente, DocumentoVentaDetalle

invoice = Invoice(
    serie="F001",
    numero=1,
    proveedor=Proveedor(ruc="20100066603", razonSocial="Softgreen S.A.C."),
    cliente=Cliente(nombre="Carlos", numeroDocumentoIdentidad="12121212121", tipoDocumentoIdentidad="6"),
    detalles=[DocumentoVentaDetalle(descripcion="Item", cantidad=10, precio=100)],
)

xml = invoice.to_xml()
print(xml)  # XML UBL 2.1 listo para firmar
```

### TypeScript / JavaScript

```bash
npm install @openubl/sdk
```

```typescript
import { client, type Invoice } from "@openubl/sdk";

const invoice: Invoice = {
  serie: "F001",
  numero: 1,
  proveedor: { ruc: "20100066603", razonSocial: "Softgreen S.A.C." },
  cliente: { nombre: "Carlos", numeroDocumentoIdentidad: "12121212121", tipoDocumentoIdentidad: "6" },
  detalles: [{ descripcion: "Item", cantidad: 10, precio: 100 }],
};

const { data } = await client.POST("/api/v1/invoice/create", { body: invoice });
console.log(data?.xml); // XML UBL 2.1 generado
```

## Levantar la API REST

```bash
uv run uvicorn openubl.main:app --reload
```

Abre [http://localhost:8000/docs](http://localhost:8000/docs) para Swagger UI interactivo.

## Documentos soportados

| Tipo | Código SUNAT | Endpoint |
|------|-------------|----------|
| Factura | 01 | `POST /api/v1/invoice/create` |
| Boleta | 03 | `POST /api/v1/invoice/create` |
| Nota de Crédito | 07 | `POST /api/v1/credit-note/create` |
| Nota de Débito | 08 | `POST /api/v1/debit-note/create` |
| Comunicación de Baja | RA | `POST /api/v1/voided-documents/create` |
| Resumen Diario | RC | `POST /api/v1/summary-documents/create` |
| Percepción | 40 | `POST /api/v1/perception/create` |
| Retención | 20 | `POST /api/v1/retention/create` |

## Validación de versión

Verifica que tu SDK y la API compartan la misma versión:

```python
from openubl.version import check_api_version

result = check_api_version("http://localhost:8000")
assert result["ok"], f"Desfase: SDK {result['sdk_version']} vs API {result['api_version']}"
```

```typescript
import { checkApiVersion } from "@openubl/sdk";

const result = await checkApiVersion("http://localhost:8000");
if (!result.ok) throw new Error(`Desfase: SDK ${result.sdkVersion} vs API ${result.apiVersion}`);
```

## Documentación

- [Documentación completa](https://darvin2c.github.io/openUBL)
- [Guía de Python SDK](https://darvin2c.github.io/openUBL/sdk/python)
- [Guía de TypeScript SDK](https://darvin2c.github.io/openUBL/sdk/typescript)
- [Referencia de API](https://darvin2c.github.io/openUBL/api/referencia)

## Contribuir

Consulta `AGENTS.md` para el contexto técnico completo del proyecto.

## Licencia

MIT © openUBL
# Test release flow v2


