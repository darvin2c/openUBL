# openUBL Multi-Language SDK Generation

The `openapi.json` at the repo root is the single source of truth for all SDKs.

## Supported languages

| Language | Generator | Output directory |
|----------|-----------|------------------|
| TypeScript | `openapi-typescript` | `sdk/typescript/src/openubl-types.ts` |
| Java | `openapi-generator-cli` | `sdk/java/` |
| Go | `openapi-generator-cli` | `sdk/go/` |
| Python | `openapi-generator-cli` | `sdk/python/` |
| C# | `openapi-generator-cli` | `sdk/csharp/` |

## Quick start

Refresh the OpenAPI schema from the running FastAPI app:

```bash
uv run python scripts/export_openapi.py
```

Generate all SDKs:

```bash
uv run python sdk/generate.py
```

Generate specific languages:

```bash
uv run python sdk/generate.py java go
```

## TypeScript usage

```bash
cd sdk/typescript
npm install
npm run generate
npm run build
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
```

## Java usage

```bash
npx @openapitools/openapi-generator-cli generate -i openapi.json -g java --library native -o sdk/java
```

```java
Invoice invoice = new Invoice()
    .serie("F001")
    .numero(1)
    .proveedor(new Proveedor().ruc("20100066603").razonSocial("Softgreen S.A.C."));
```

## Go usage

```bash
npx @openapitools/openapi-generator-cli generate -i openapi.json -g go -o sdk/go
```

```go
invoice := openubl.Invoice{
    Serie:  "F001",
    Numero: 1,
    Proveedor: &openubl.Proveedor{Ruc: "20100066603", RazonSocial: "Softgreen S.A.C."},
}
```

## Python usage

```bash
npx @openapitools/openapi-generator-cli generate -i openapi.json -g python -o sdk/python
```

```python
from openubl.models.invoice import Invoice
from openubl.models.proveedor import Proveedor

invoice = Invoice(
    serie="F001",
    numero=1,
    proveedor=Proveedor(ruc="20100066603", razon_social="Softgreen S.A.C."),
)
```

## C# usage

```bash
npx @openapitools/openapi-generator-cli generate -i openapi.json -g csharp -o sdk/csharp
```

```csharp
var invoice = new Invoice(
    serie: "F001",
    numero: 1,
    proveedor: new Proveedor(ruc: "20100066603", razonSocial: "Softgreen S.A.C.")
);
```

## Fallback: Docker

If `npx` is not available, use the Docker image:

```bash
docker run --rm -v ${PWD}:/local openapitools/openapi-generator-cli generate \
  -i /local/openapi.json \
  -g java \
  -o /local/sdk/java
```

## Notes

- Only `sdk/typescript/src/client.ts`, `sdk/typescript/src/index.ts`, and tests are hand-written; everything under `sdk/java/`, `sdk/go/`, `sdk/python/`, and `sdk/csharp/` is generated.
- Run `scripts/check_sdk_sync.py` in CI to ensure `openapi.json` is never stale.
