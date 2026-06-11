# openUBL — Contexto para Agentes de IA

## Qué es este proyecto

openUBL es una biblioteca Python para generar, firmar y validar documentos electrónicos UBL 2.1 para SUNAT (Perú). Expone una API REST FastAPI y SDKs generados a partir de OpenAPI.

## Estructura clave

```
openubl/
├── src/openubl/           # Biblioteca core Python
│   ├── models/            # Pydantic models (Invoice, CreditNote, etc.)
│   ├── api/router.py      # Endpoints FastAPI
│   ├── main.py            # App FastAPI
│   ├── renderer.py        # Renderizado Jinja2 → XML UBL
│   ├── signer.py          # Firma digital XAdES-EPES
│   ├── validator.py       # Validación SUNAT sobre XML
│   ├── enricher.py        # Enriquecimiento automático de campos
│   └── version.py         # check_api_version() para sincronización runtime
├── sdk/typescript/        # SDK TypeScript (@openubl/sdk)
│   ├── src/               # Código fuente (client.ts, version.ts, openubl-types.ts)
│   ├── test/              # Tests Vitest
│   └── dist/              # Emitido por tsc
  ├── scripts/
  │   ├── export_openapi.py      # Exporta openapi.json desde FastAPI
  │   ├── check_sdk_sync.py      # Valida sincronización de versiones + openapi.json
  │   ├── bump_version.py        # Bump atómico de versión en todas las fuentes
  │   └── release.py             # Script único de release (bump, commit, tag, push, rollback)
  ├── .github/workflows/
  │   ├── ci.yml                 # Tests y build en PR
  │   └── publish.yml            # Publica en PyPI + npm y crea GitHub Release
├── tests/                 # Suite pytest
├── openapi.json           # Esquema OpenAPI 3.1.0 (single source of truth)
├── pyproject.toml         # Config Python (openubl)
└── package.json           # Config root (scripts/docs)
```

## Convenciones de código

- **Idioma**: Código en inglés, documentación y mensajes de usuario en español.
- **Python**: `snake_case`, tipado estricto (mypy-friendly), docstrings en español para FastAPI OpenAPI.
- **TypeScript**: `camelCase`, ES modules (`"type": "module"`), tipos exportados desde `openubl-types.ts`.
- **Versionado**: SemVer. La versión debe ser idéntica en los 7 archivos. Nunca editar a mano; usar `scripts/bump_version.py`.

## Cómo ejecutar tests

```bash
# Python (todos excepto E2E)
uv run pytest -m "not e2e"

# TypeScript SDK
cd sdk/typescript && npm test

# Sincronización
uv run python scripts/check_sdk_sync.py
```

## Cómo crear un release

Cuando un PR se mergea a `main` con un label `release:patch`, `release:minor` o `release:major`:

| Label | Color HEX | Resultado |
|-------|-----------|-----------|
| `release:patch` | `#22c55e` | Bugfix → `0.1.0` → `0.1.1` |
| `release:minor` | `#f59e0b` | Feature → `0.1.0` → `0.2.0` |
| `release:major` | `#ef4444` | Breaking → `0.1.0` → `1.0.0` |

1. Ejecuta localmente (detecta el label automáticamente):
   ```bash
   uv run python scripts/release.py --from-label --push
   ```
   > Requiere la CLI `gh` instalada y autenticada.

2. El workflow `.github/workflows/publish.yml` se disparará automáticamente en GitHub Actions por el tag `v*`.

### Flujo manual (fallback)

```bash
# Bump por tipo
uv run python scripts/release.py --type minor --push

# O versión exacta
uv run python scripts/release.py 0.2.0 --push
```

### Rollback

Si algo sale mal después de crear el release localmente:

```bash
uv run python scripts/release.py --rollback
```

Esto elimina el tag local y hace `git reset --hard HEAD~1`.

## Reglas de dominio (no inventar)

### Fuente de verdad obligatoria

Antes de implementar o modificar cualquier regla de validación, formato, catálogo o estructura XML relacionada con SUNAT, **debes consultar primero** la documentación oficial en:

**https://cpe.sunat.gob.pe/guias-y-manuales**

Esta es la fuente autorizada de SUNAT para:
- Guías de emisión electrónica (factura, boleta, notas de crédito/débito, etc.)
- Especificaciones técnicas de XML UBL 2.1
- Catálogos de códigos (tipo de documento, tipo de operación, moneda, etc.)
- Reglas de validación y rechazo
- Formatos de firma digital y envío

**Nunca asumas, inventes ni "alucines" reglas SUNAT.** Si la información no está clara en el código existente, busca en la URL oficial antes de escribir código nuevo.

### Reglas del código existente

- Los documentos SUNAT usan catálogos fijos (tipo de documento, moneda, etc.). Están en `src/openubl/models/catalog.py`.
- La firma digital requiere certificado PEM y clave privada PEM. No inventar formatos.
- El XML UBL 2.1 generado debe pasar validación SUNAT (`validator.py`) antes del envío.
- El ambiente beta de SUNAT requiere credenciales reales (`SUNAT_BETA_RUC`); los tests E2E están marcados con `pytest.mark.e2e`.

## Qué NO hacer

- No editar versiones a mano en `__init__.py`, `pyproject.toml`, `package.json`, etc. Usar `bump_version.py`.
- No modificar `openapi.json` manualmente. Usar `export_openapi.py`.
- No romper la sincronización entre API y SDKs. Siempre ejecutar `check_sdk_sync.py` antes de un release.
- No agregar dependencias runtime innecesarias. `urllib.request` ya cubre HTTP simple en Python.

## Endpoints principales (FastAPI)

- `POST /api/v1/invoice/create` → Genera XML de factura/boleta
- `POST /api/v1/credit-note/create` → Nota de crédito
- `POST /api/v1/debit-note/create` → Nota de débito
- `POST /api/v1/voided-documents/create` → Comunicación de baja (RA)
- `POST /api/v1/summary-documents/create` → Resumen diario (RC)
- `POST /api/v1/perception/create` → Percepción
## Contacto / autor

Consulta el repositorio en GitHub para información del mantenedor.
