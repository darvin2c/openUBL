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
[https://darvin2c.github.io/openUBL](https://darvin2c.github.io/openUBL)

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

## Releases

The project uses [Semantic Versioning](https://semver.org/).

### Flujo automático (recomendado)

Cada vez que mergeas un PR a `main`, puedes solicitar un release automático agregando un **label** al PR antes de mergearlo:

| Label | Color | Resultado |
|-------|-------|-----------|
| `release:patch` | <span style="background:#22c55e;color:#fff;padding:2px 6px;border-radius:4px;">#22c55e</span> | Bugfix → `0.1.0` → `0.1.1` |
| `release:minor` | <span style="background:#f59e0b;color:#fff;padding:2px 6px;border-radius:4px;">#f59e0b</span> | Feature → `0.1.0` → `0.2.0` |
| `release:major` | <span style="background:#ef4444;color:#fff;padding:2px 6px;border-radius:4px;">#ef4444</span> | Breaking → `0.1.0` → `1.0.0` |

> El label `release` (color <span style="background:#3b82f6;color:#fff;padding:2px 6px;border-radius:4px;">#3b82f6</span>) se aplica automáticamente al PR de release generado por el workflow; no hace falta crearlo manualmente.

**Qué pasa automáticamente:**
1. Al mergear el PR, un workflow crea un **PR de release** con el bump de versión ya aplicado.
2. Tú revisas y mergeas el PR de release.
3. Al mergear el PR de release, otro workflow crea automáticamente el **tag** `vX.Y.Z`.
4. El tag dispara la publicación a **npm** (`@openubl/sdk`) y **PyPI** (`openubl`).

**Nada se pushea directo a `main` sin un PR.** El flujo es seguro y auditable.

### Flujo manual (fallback)

Si prefieres control total, usa el script local:

```bash
uv run python scripts/create_release.py 0.2.0
git push origin main
git push origin v0.2.0
```

Esto ejecuta `bump_version.py`, crea el commit `release: v0.2.0` y el tag anotado `v0.2.0`.

### Prerequisites

Repository secrets required for CI publication:

- `NPM_TOKEN` — npm access token with publish rights for `@openubl` scope.
- `PYPI_API_TOKEN` — PyPI API token for the `openubl` project.

### Validate before releasing

```bash
uv run python scripts/check_sdk_sync.py
```

This verifies:
- All 7 version sources are identical.
- `openapi.json` is up to date with the FastAPI schema.

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
