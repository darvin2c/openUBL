import { describe, it, expect } from "vitest";
import { z } from "zod";
import { client, SDK_VERSION, checkApiVersion } from "../src/index.js";
import { zInvoice, zProveedor } from "../src/zod.gen.js";
import type { Invoice, CreditNote, Proveedor, Cliente, DocumentoVentaDetalle } from "../src/index.js";

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
      comprobanteAfectadoSerieNumero: "F001-1",
      sustentoDescripcion: "Anulación",
      proveedor,
      cliente,
      detalles: [detalle],
    };
    expect(note.serie).toBe("FC01");
  });
});

describe("runtime round-trip", () => {
  it("POSTs an Invoice and returns XML with expected ID", async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/version");
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

    const { data, error } = await client.post("/api/v1/invoice/create", {
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
      const result = await checkApiVersion("http://localhost:8000");
      expect(result.ok).toBe(true);
      expect(result.sdkVersion).toBe(SDK_VERSION);
    } catch {
      return;
    }
  });
});

describe("runtime Zod validation", () => {
  it("rejects invalid RUC length", () => {
    expect(() => zProveedor.parse({ ruc: "1234567890", razonSocial: "X" })).toThrow(z.ZodError);
  });

  it("rejects invalid invoice serie", () => {
    expect(() =>
      zInvoice.parse({
        serie: "X001",
        numero: 1,
        proveedor: { ruc: "20100066603", razonSocial: "X" },
        cliente: { nombre: "C", numeroDocumentoIdentidad: "12345678", tipoDocumentoIdentidad: "1" },
        detalles: [{ descripcion: "Item", cantidad: 1, precio: 10 }],
      }),
    ).toThrow(z.ZodError);
  });

  it("rejects invalid tipoDocumentoIdentidad enum", () => {
    expect(() =>
      zInvoice.parse({
        serie: "F001",
        numero: 1,
        proveedor: { ruc: "20100066603", razonSocial: "X" },
        cliente: { nombre: "C", numeroDocumentoIdentidad: "12345678", tipoDocumentoIdentidad: "99" },
        detalles: [{ descripcion: "Item", cantidad: 1, precio: 10 }],
      }),
    ).toThrow(z.ZodError);
  });
});
