import { describe, it, expect } from "vitest";
import { client, type Invoice, type CreditNote, type Proveedor, type Cliente, type DocumentoVentaDetalle, SDK_VERSION, checkApiVersion } from "../src/index.js";

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

describe("type-safety", () => {
  it("accepts a valid Invoice payload", () => {
    const invoice: Invoice = {
      serie: "F001",
      numero: 1,
      proveedor,
      cliente,
      detalles: [detalle],
    };
    expect(invoice.serie).toBe("F001");
    expect(invoice.numero).toBe(1);
  });

  it("accepts a valid CreditNote payload", () => {
    const note: CreditNote = {
      serie: "FC01",
      numero: 1,
      proveedor,
      cliente,
      detalles: [detalle],
      comprobanteAfectado: {
        tipoComprobante: "01",
        serieNumero: "F001-1",
        motivo: "Anulación",
      },
    };
    expect(note.serie).toBe("FC01");
  });
});

describe("runtime round-trip", () => {
  it("POSTs an Invoice and returns XML with expected ID", async () => {
    // Skip if no server is running
    try {
      const res = await fetch("http://localhost:8000/api/v1/invoice/create", { method: "HEAD" });
      if (!res.ok) return;
    } catch {
      return;
    }

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

    expect(data).toBeDefined();
    expect(data!.xml).toContain("<cbc:ID>F001-1</cbc:ID>");
  });
});

describe("version sync", () => {
  it("exports a non-empty SDK_VERSION", () => {
    expect(SDK_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
  });

  it("checkApiVersion matches when server is up", async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/version", { method: "HEAD" });
      if (!res.ok) return;
    } catch {
      return;
    }
    const result = await checkApiVersion();
    expect(result.ok).toBe(true);
    expect(result.sdkVersion).toBe(SDK_VERSION);
    expect(result.apiVersion).toBe(SDK_VERSION);
  });
});
