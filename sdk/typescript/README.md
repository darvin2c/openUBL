# @openubl/sdk

SDK de TypeScript para openUBL. Ofrece tipos, cliente fetch y schemas Zod generados automáticamente desde el esquema OpenAPI.

## Instalación

```bash
npm install @openubl/sdk
```

## Uso

```typescript
import { createInvoice, SDK_VERSION, checkApiVersion } from "@openubl/sdk";
import { zInvoice } from "@openubl/sdk/zod.gen";

const invoice = zInvoice.parse({
  serie: "F001",
  numero: 1,
  proveedor: { ruc: "20100066603", razonSocial: "Softgreen S.A.C." },
  cliente: { nombre: "Carlos", numeroDocumentoIdentidad: "12121212121", tipoDocumentoIdentidad: "6" },
  detalles: [{ descripcion: "Item", cantidad: 10, precio: 100 }],
});

const { data, error } = await createInvoice({ body: invoice });
```

## Validación de versión

```typescript
import { checkApiVersion } from "@openubl/sdk";

const result = await checkApiVersion("http://localhost:8000");
if (!result.ok) {
  throw new Error(`Desfase de versión: SDK ${result.sdkVersion} vs API ${result.apiVersion}`);
}
```

## Desarrollo

```bash
cd sdk/typescript
npm install
npm run generate   # regenera src/ desde openapi.json
npm run build      # compila TypeScript
npm test           # ejecuta la suite de tests
```
