# Documentación de openUBL

Sitio de documentación de openUBL, generado con [Astro Starlight](https://starlight.astro.build). Contiene guías de uso, referencia de API y documentación del SDK TypeScript.

## Comandos

Los comandos se ejecutan desde la raíz del repositorio:

| Comando | Acción |
|---|---|
| `npm install` | Instala las dependencias del workspace |
| `npm run docs:dev` | Inicia el servidor de desarrollo en `localhost:4321` |
| `npm run docs:build` | Compila el sitio estático en `docs/dist/` |
| `npm run docs:preview` | Previsualiza la compilación localmente |

## Cómo editar contenido

Los archivos de documentación viven en `src/content/docs/`. Cada archivo `.mdx` se expone como una ruta según su ruta relativa dentro de ese directorio.

- Guías de inicio rápido: `src/content/docs/getting-started/`
- Guías por documento: `src/content/docs/guides/`
- Ejemplos: `src/content/docs/examples/`
- Referencia API: `src/content/docs/api/referencia.mdx` (generado)
- SDK TypeScript: `src/content/docs/sdk/typescript.mdx` (generado)

## Regenerar documentación generada

No edites manualmente estos archivos; se regeneran desde fuentes oficiales:

```bash
# Regenera openapi.json desde la app FastAPI
npm run generate:openapi

# Regenera docs/src/content/docs/api/referencia.mdx y docs/src/content/docs/sdk/typescript.mdx
npm run generate:docs
```

## Sitio publicado

La documentación se publica en [https://darvin2c.github.io/openUBL](https://darvin2c.github.io/openUBL).
