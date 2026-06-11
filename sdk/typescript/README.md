# @openubl/sdk

SDK de TypeScript para openUBL. Ofrece tipos generados a partir del esquema OpenAPI y un cliente con autocompletado para todos los endpoints de la API REST.

## Instalación

```bash
npm install @openubl/sdk
```

## Uso

Importa el cliente y los tipos. El cliente está construido con `openapi-fetch`, por lo que cada llamada cuenta con tipado completo de rutas, cuerpo de solicitud y respuesta.

```typescript
import { client, type Invoice, type Proveedor, type Cliente, type DocumentoVentaDetalle } from "@openubl/sdk";

const proveedor: Proveedor = {
  ruc: "20100066603",
  razonSocial: "Softgreen S.A.C.",
};

const cliente: Cliente = {
  nombre: "Carlos",
  numeroDocumentoIdentidad: "12121212121",
  tipoDocumentoIdentidad: "6",
};

const detalle: DocumentoVentaDetalle = {
  descripcion: "Item",
  cantidad: 10,
  precio: 100,
};

const invoice: Invoice = {
  serie: "F001",
  numero: 1,
  proveedor,
  cliente,
  detalles: [detalle],
};

const { data, error } = await client.POST("/api/v1/invoice/create", {
  body: invoice,
});

if (error) {
  throw new Error(JSON.stringify(error));
}

console.log(data.xml); // XML UBL 2.1 generado
```

## Validación de versión

El SDK expone `checkApiVersion` para verificar en runtime que la versión de la API coincide con la del SDK:

```typescript
import { checkApiVersion } from "@openubl/sdk";

const result = await checkApiVersion("http://localhost:8000");
if (!result.ok) {
  throw new Error(
    `Desfase de versión: SDK ${result.sdkVersion} vs API ${result.apiVersion}`
  );
}
```

Si la API no responde o las versiones difieren, la función lanza un error o retorna `ok: false`.

## Desarrollo

```bash
cd sdk/typescript
npm install
npm run generate   # regenera src/openubl-types.ts desde openapi.json
npm run build      # compila TypeScript
npm test           # ejecuta la suite de tests
```
