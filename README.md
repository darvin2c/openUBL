# openUBL

Peruvian SUNAT Electronic Documents Library — generate, sign, and validate UBL 2.1 XML for invoices, credit notes, debit notes, voided documents, summary documents, perceptions, and retentions.

## Levantar openUBL

Start the development server and open Swagger UI:

```bash
uv run uvicorn openubl.main:app --reload
```

Navigate to [http://localhost:8000/docs](http://localhost:8000/docs) for interactive documentation.

## Documentacion

La documentacion completa esta disponible en:
[https://openubl.github.io/openubl](https://openubl.github.io/openubl)

## SDK Generation

The OpenAPI 3.1.0 schema is the single source of truth for all client SDKs.

Refresh the schema from the running FastAPI app:

```bash
uv run python scripts/export_openapi.py
```

Generate TypeScript types:

```bash
cd sdk/typescript && npm run generate
```

Generate other languages:

```bash
uv run python sdk/generate.py java go python csharp
```

Or directly with the OpenAPI Generator:

```bash
npx @openapitools/openapi-generator-cli generate -i openapi.json -g java -o sdk/java
```

## TypeScript Usage

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
console.log(data?.xml);
```

## Project Structure

```
openubl/
├── src/openubl/          # Core library (models, renderer, signer, validator)
├── scripts/              # Development automation
├── sdk/                  # Generated and hand-written SDKs
│   ├── typescript/       # TypeScript client with openapi-fetch
│   ├── generate.py       # Multi-language generator orchestrator
│   └── README.md         # Per-language usage examples
├── tests/                # pytest suite
├── openapi.json          # Exported FastAPI schema (single source of truth)
└── pyproject.toml        # Python project configuration
```

## Development

Install dependencies:

```bash
uv sync
```

Run tests:

```bash
uv run pytest
```

Check that `openapi.json` is up to date:

```bash
uv run python scripts/check_sdk_sync.py
```

## Supported Documents

| Tipo | Schema | Endpoint |
|------|--------|----------|
| Factura (01) | `Invoice` | `POST /api/v1/invoice/create` |
| Boleta (03) | `Invoice` (serie B###) | `POST /api/v1/invoice/create` |
| Nota de Crédito (07) | `CreditNote` | `POST /api/v1/credit-note/create` |
| Nota de Débito (08) | `DebitNote` | `POST /api/v1/debit-note/create` |
| Anulaciones (RA) | `VoidedDocuments` | `POST /api/v1/voided-documents/create` |
| Resumen Diario (RC) | `SummaryDocuments` | `POST /api/v1/summary-documents/create` |
| Percepción (40) | `Perception` | `POST /api/v1/perception/create` |
| Retención (20) | `Retention` | `POST /api/v1/retention/create` |
