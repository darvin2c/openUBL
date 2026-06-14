# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0](https://github.com/darvin2c/openUBL/compare/v1.0.1..v1.1.0) - 2026-06-14

### Features

- *(validation)* Implement remaining SUNAT rules and coverage audit ([#29](https://github.com/darvin2c/openUBL/issues/29)) - ([afc0edb](https://github.com/darvin2c/openUBL/commit/afc0edb56282d4b5c2c3bf91fca0687dc27ffea1))
## [1.0.1](https://github.com/darvin2c/openUBL/compare/v1.0.0..v1.0.1) - 2026-06-13

### Miscellaneous Tasks

- Configura basedpyright en dev y elimina referencias a XBuilder ([#28](https://github.com/darvin2c/openUBL/issues/28)) - ([b994607](https://github.com/darvin2c/openUBL/commit/b9946076eb54184853a221d8bddd53bbea2f32c3))
## [1.0.0](https://github.com/darvin2c/openUBL/compare/v0.2.3..v1.0.0) - 2026-06-13

### Features

- *(signer)* Migra firma digital SUNAT a RSA-SHA-256/SHA-256 ([#27](https://github.com/darvin2c/openUBL/issues/27)) - ([874fdcb](https://github.com/darvin2c/openUBL/commit/874fdcb74bce77746884fc7a382018943503e643))

### Miscellaneous Tasks

- Corrige dependencias de release-notes - ([06aea00](https://github.com/darvin2c/openUBL/commit/06aea00c81e5084f842f28a3ff71bc58754d003f))
- Publicaciones idempotentes para npm y PyPI - ([e9ddd5f](https://github.com/darvin2c/openUBL/commit/e9ddd5f717503f9503e8849f4cc3249d0e1f89fc))
## [0.2.3](https://github.com/darvin2c/openUBL/compare/v0.2.2..v0.2.3) - 2026-06-13

### Miscellaneous Tasks

- Evita doble bump y re-publica tag pendiente - ([0ed6733](https://github.com/darvin2c/openUBL/commit/0ed67332201c81eb9bcbccfd02ed59e289780461))
## [0.2.2](https://github.com/darvin2c/openUBL/compare/v0.2.1..v0.2.2) - 2026-06-13

### Miscellaneous Tasks

- Añade uv al job publish-npm - ([af9c5f0](https://github.com/darvin2c/openUBL/commit/af9c5f0c27d6c12d6c71cf7dee61d24d20db293f))
- Workflow único de release con publish a npm/PyPI integrado - ([ece5933](https://github.com/darvin2c/openUBL/commit/ece59332a68096882db57e4db4680b4a239f4c4c))
## [0.2.1](https://github.com/darvin2c/openUBL/compare/v0.2.0..v0.2.1) - 2026-06-13

### Features

- *(api,docs)* Typed XML responses and improved TypeScript examples ([#24](https://github.com/darvin2c/openUBL/issues/24)) - ([d919ba6](https://github.com/darvin2c/openUBL/commit/d919ba6a2f04378cd386ef20b248403fd7c71a3a))

### Documentation

- *(getting-started)* Reorganiza guía inicial, añade arquitectura e instala diagramas Mermaid ([#25](https://github.com/darvin2c/openUBL/issues/25)) - ([de22d69](https://github.com/darvin2c/openUBL/commit/de22d6941b86c4279a0a08aa38d086e256c01b75))

### Miscellaneous Tasks

- Release automático directo al mergear PR con label release:* - ([5ddb880](https://github.com/darvin2c/openUBL/commit/5ddb880fd4976866344e4b40a02381a9d9aa0e67))
- Restaura flujo automático de release con PR y tag - ([5413c4f](https://github.com/darvin2c/openUBL/commit/5413c4f6cef60088403af6da7bb1d3b3abac9a31))
## [0.2.0](https://github.com/darvin2c/openUBL/compare/v0.1.4..v0.2.0) - 2026-06-11

### Features

- *(api)* Soporte PFX/P12 en /api/v1/sign y ejemplos en SDKs ([#23](https://github.com/darvin2c/openUBL/issues/23)) - ([c230bc6](https://github.com/darvin2c/openUBL/commit/c230bc66b1bdb05325c85359f9aa53344c3c1fb9))

### Bug Fixes

- Corregir regex en cliff.toml que ignoraba todos los commits - ([772ddf0](https://github.com/darvin2c/openUBL/commit/772ddf0ac6d847307b11f46cb474380b0decfbc3))
## [0.1.4](https://github.com/darvin2c/openUBL/compare/v0.1.2..v0.1.4) - 2026-06-11

### Features

- Simplify release flow to single local script + unified publish workflow ([#22](https://github.com/darvin2c/openUBL/issues/22)) - ([3ae0fba](https://github.com/darvin2c/openUBL/commit/3ae0fba454af370fd07eec4f6dada1cd7867e49a))

### Bug Fixes

- Detectar npm en PATH para tests TS en Windows - ([7420751](https://github.com/darvin2c/openUBL/commit/7420751261a46ae78b2b778e566f9c416d963577))
## [0.1.2](https://github.com/darvin2c/openUBL/compare/v0.1.1..v0.1.2) - 2026-06-11

### Documentation

- Comprehensive redesign with professional theme, new guides, and catalog pages ([#20](https://github.com/darvin2c/openUBL/issues/20)) - ([2b193eb](https://github.com/darvin2c/openUBL/commit/2b193eb21ce5583a7d3a08176770f5f83136cd89))

### Miscellaneous Tasks

- Add git-cliff changelog and release notes ([#19](https://github.com/darvin2c/openUBL/issues/19)) - ([32a782a](https://github.com/darvin2c/openUBL/commit/32a782ab33ff9d5b426654689b5c91d1ed50bff0))
## [0.1.1] - 2026-06-11

### Features

- *(core)* Initial openUBL project with SUNAT electronic invoicing - ([9eeae61](https://github.com/darvin2c/openUBL/commit/9eeae610527ddf49af5307013c66dded77e50e0d))
- *(docs)* Astro Starlight documentation site - ([f1ad39b](https://github.com/darvin2c/openUBL/commit/f1ad39b670944f3cc8105d994d76b8dd9ca6cebe))
- *(sdk)* Multi-language SDK generation from OpenAPI - ([3e02820](https://github.com/darvin2c/openUBL/commit/3e02820f513848da9a3061c328793c168c506474))
- Centralized version bump and static sync validation - ([c474191](https://github.com/darvin2c/openUBL/commit/c474191c2ba10f1b87cd90797a2587f35f5e90d6))
- Add /api/v1/version endpoint and runtime SDK sync checks - ([0e7ce10](https://github.com/darvin2c/openUBL/commit/0e7ce10c782124168366f15bd7adc00acacefd15))

### Bug Fixes

- Agregar conditionals a todos los steps de create-release-pr ([#16](https://github.com/darvin2c/openUBL/issues/16)) - ([448efba](https://github.com/darvin2c/openUBL/commit/448efba0702da4f867589fac7abde9b3e999b5b2))
- Usar una sola línea para gh pr create en workflow de release ([#14](https://github.com/darvin2c/openUBL/issues/14)) - ([08cb650](https://github.com/darvin2c/openUBL/commit/08cb650b18667d4cc41273a5d8a3e1278b32c189))
- Leer versión desde pyproject.toml y forzar push de release branch ([#12](https://github.com/darvin2c/openUBL/issues/12)) - ([597e495](https://github.com/darvin2c/openUBL/commit/597e495ce5d1331df2caa92479ea84c186c9869f))
- Corregir sintaxis YAML en create-release-pr workflow ([#10](https://github.com/darvin2c/openUBL/issues/10)) - ([d622e6d](https://github.com/darvin2c/openUBL/commit/d622e6ded9ae4cf5deef2e7f939a9322eb44a682))
- Agregar npm ci antes de bump en release workflow ([#8](https://github.com/darvin2c/openUBL/issues/8)) - ([27e40b5](https://github.com/darvin2c/openUBL/commit/27e40b5a7bd23ed06e88cdb1b9956e987e1d82c9))
- Cambiar trigger de pull_request a push en workflows de release ([#6](https://github.com/darvin2c/openUBL/issues/6)) - ([87231e1](https://github.com/darvin2c/openUBL/commit/87231e1c0a45cd2c611031e0db574cacc237dd14))
- Usar mergedAt en vez de merged para detectar PR mergeado ([#4](https://github.com/darvin2c/openUBL/issues/4)) - ([cf1e2f1](https://github.com/darvin2c/openUBL/commit/cf1e2f1f096a15df9eb898ef8769738153682654))
- Use actual repo URL for GitHub Pages base and link - ([215c78f](https://github.com/darvin2c/openUBL/commit/215c78f79e3f9abe459a9acb2e62285f2a918ac7))

### Documentation

- Reescribir README.md como pitch de venta ([#3](https://github.com/darvin2c/openUBL/issues/3)) - ([8c458c4](https://github.com/darvin2c/openUBL/commit/8c458c4aca410499790559ee04e6263b74f86826))
- Add AGENTS.md for AI agent context - ([0149a45](https://github.com/darvin2c/openUBL/commit/0149a45fd42da9e74eafe38db27bf078ed816582))
- Add release process and create_release.py script - ([e8393bd](https://github.com/darvin2c/openUBL/commit/e8393bdf4a52d4b4c3d61c3d7c5b662478adf64c))
- Add SDK README, testing guide, and version validation docs - ([55d175c](https://github.com/darvin2c/openUBL/commit/55d175cbbb9966b91c8b79fe6a6d2f53d62b1d40))
- Deploy Astro docs to GitHub Pages and simplify README - ([0ef8651](https://github.com/darvin2c/openUBL/commit/0ef8651f5081bdb48059b21542278aa4883c8bc5))

### Testing

- Add version endpoint, runtime sync, and static sync tests - ([e6462b8](https://github.com/darvin2c/openUBL/commit/e6462b83c03554aa7768e8e0c6269ceb2d0ccb5e))

### Miscellaneous Tasks

- Test auto-release flow v8 ([#17](https://github.com/darvin2c/openUBL/issues/17)) - ([4346978](https://github.com/darvin2c/openUBL/commit/4346978a024eaf1af13a20bf3be029b145bbcc98))
- Test auto-release flow v7 ([#15](https://github.com/darvin2c/openUBL/issues/15)) - ([33dac0c](https://github.com/darvin2c/openUBL/commit/33dac0c1ea4731d861397248f53402bd777a3820))
- Test auto-release flow v6 ([#13](https://github.com/darvin2c/openUBL/issues/13)) - ([b5dd851](https://github.com/darvin2c/openUBL/commit/b5dd8519a6d91adeb00115d793b828137cf6d59c))
- Test auto-release flow v5 ([#11](https://github.com/darvin2c/openUBL/issues/11)) - ([788e976](https://github.com/darvin2c/openUBL/commit/788e9766a0d1730c229c652970276054a17c51da))
- Test auto-release flow v4 ([#9](https://github.com/darvin2c/openUBL/issues/9)) - ([b48175c](https://github.com/darvin2c/openUBL/commit/b48175c938b6b501fb6efb7ca07b03cef06b83f7))
- Test auto-release flow v3 ([#7](https://github.com/darvin2c/openUBL/issues/7)) - ([9163ca2](https://github.com/darvin2c/openUBL/commit/9163ca218deca03dffee9ecb66c93c3a4270a1a8))
- Test auto-release flow v2 ([#5](https://github.com/darvin2c/openUBL/issues/5)) - ([0b81db4](https://github.com/darvin2c/openUBL/commit/0b81db44291925b88f935781ef9c3e585076f9f0))
- Add PR checks workflow ([#2](https://github.com/darvin2c/openUBL/issues/2)) - ([883237d](https://github.com/darvin2c/openUBL/commit/883237dc69284adae4eeb7c90028f0d03c477e29))
- Remove personal email from project docs - ([db4731e](https://github.com/darvin2c/openUBL/commit/db4731e544d13d8b23af54c7c7ddad15be4f342c))
- Add automated release flow via PR labels - ([287b86f](https://github.com/darvin2c/openUBL/commit/287b86f9d26ae7b5095b767dc281d82d707d5388))
- Add GitHub Actions workflows for npm and PyPI publication - ([207ac55](https://github.com/darvin2c/openUBL/commit/207ac557cae559e6f7480cfc3b692b06522ab80a))
- Use Node 22 for docs build - ([ce88442](https://github.com/darvin2c/openUBL/commit/ce88442e46a63011759043c1762a8a14e63bd3a4))
<!-- generated by git-cliff -->
