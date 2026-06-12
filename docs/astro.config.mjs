// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	site: 'https://darvin2c.github.io',
	base: '/openUBL',
	integrations: [
		starlight({
			title: 'openUBL',
			tagline: 'Facturación electrónica SUNAT, hecha simple.',
			favicon: '/favicon.svg',
			logo: {
				src: './src/assets/logo.svg',
				replacesTitle: true,
			},
			components: {
				Hero: './src/components/Hero.astro',
			},
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/darvin2c/openUBL', attrs: { target: '_blank', rel: 'noopener noreferrer' } },
			],
			editLink: {
				baseUrl: 'https://github.com/darvin2c/openUBL/edit/main/docs/',
				attrs: { target: '_blank', rel: 'noopener noreferrer' },
			},
			customCss: [
				'./src/styles/custom.css',
			],
			expressiveCode: {
				themes: ['github-light', 'github-dark'],
				styleOverrides: {
					borderRadius: '0.75rem',
					borderWidth: '1px',
				},
			},
			locales: {
				root: {
					label: 'Espanol',
					lang: 'es',
				},
			},
			lastUpdated: true,
			pagination: true,
			tableOfContents: {
				minHeadingLevel: 2,
				maxHeadingLevel: 4,
			},
			sidebar: [
				{
					label: 'Comenzar',
					items: [
						{ label: 'Introduccion', slug: 'getting-started/introduccion' },
						{ label: 'Instalacion', slug: 'getting-started/instalacion' },
						{ label: 'Conceptos SUNAT', slug: 'getting-started/conceptos-sunat' },
						{ label: 'Tu primer documento', slug: 'getting-started/primer-documento' },
						{ label: 'Testing', slug: 'testing' },
					],
				},
				{
					label: 'Guías de documentos',
					items: [
						{ label: 'Factura y Boleta', slug: 'guides/factura' },
						{ label: 'Nota de Crédito', slug: 'guides/nota-credito' },
						{ label: 'Nota de Débito', slug: 'guides/nota-debito' },
						{ label: 'Resumen Diario', slug: 'guides/resumen-diario' },
						{ label: 'Comunicación de Baja', slug: 'guides/comunicacion-baja' },
						{ label: 'Percepción', slug: 'guides/percepcion' },
						{ label: 'Retención', slug: 'guides/retencion' },
					],
				},
				{
					label: 'Motor openUBL',
					items: [
						{ label: 'Enriquecimiento automático', slug: 'engine/enriquecimiento' },
						{ label: 'Firma digital', slug: 'guides/firma-digital' },
						{ label: 'Validación SUNAT', slug: 'guides/validacion' },
						{ label: 'Empaquetado ZIP', slug: 'engine/empaquetado' },
					],
				},
				{
					label: 'Catálogos SUNAT',
					items: [
						{ label: 'Catálogo 01 — Tipo de comprobante', slug: 'catalogs/catalogo-01' },
						{ label: 'Catálogo 02 — Moneda', slug: 'catalogs/catalogo-02' },
						{ label: 'Catálogo 05 — Tipo de tributo', slug: 'catalogs/catalogo-05' },
						{ label: 'Catálogo 06 — Tipo de documento de identidad', slug: 'catalogs/catalogo-06' },
						{ label: 'Catálogo 07 — Tipo de afectación del IGV', slug: 'catalogs/catalogo-07' },
						{ label: 'Catálogo 16 — Tipo de precio', slug: 'catalogs/catalogo-16' },
						{ label: 'Catálogo 19 — Tipo de operación (resumen)', slug: 'catalogs/catalogo-19' },
						{ label: 'Catálogo 20 — Motivo de traslado', slug: 'catalogs/catalogo-20' },
						{ label: 'Catálogo 22 — Régimen de percepción', slug: 'catalogs/catalogo-22' },
						{ label: 'Catálogo 23 — Régimen de retención', slug: 'catalogs/catalogo-23' },
					],
				},
				{
					label: 'SDKs',
					items: [
						{ label: 'TypeScript', slug: 'sdk/typescript' },
						{ label: 'Python', slug: 'sdk/python' },
						{ label: 'Java', slug: 'sdk/java' },
						{ label: 'Go', slug: 'sdk/go' },
						{ label: 'C#', slug: 'sdk/csharp' },
					],
				},
				{
					label: 'API',
					items: [
						{ label: 'Referencia de endpoints', slug: 'api/referencia' },
						{ label: 'Esquema OpenAPI', slug: 'api/openapi' },
					],
				},
				{
					label: 'Ejemplos',
					items: [
						{ label: 'cURL', slug: 'examples/curl' },
						{ label: 'TypeScript', slug: 'examples/typescript' },
						{ label: 'Python', slug: 'examples/python' },
					],
				},
				{
					label: 'Preguntas frecuentes',
					items: [
						{ label: 'FAQ', slug: 'faq' },
					],
				},
			],
		}),
	],
});
