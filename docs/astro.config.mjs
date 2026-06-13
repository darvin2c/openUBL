// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';

// https://astro.build/config
export default defineConfig({
	site: 'https://darvin2c.github.io',
	base: '/openUBL',
	integrations: [
		mermaid({
			autoTheme: true,
		}),
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
						{ label: 'Conceptos SUNAT', slug: 'getting-started/conceptos-sunat' },
						{ label: 'Arquitectura', slug: 'getting-started/arquitectura' },
						{ label: 'Como elegir', slug: 'getting-started/como-elegir' },
						{ label: 'Instalar Python', slug: 'getting-started/instalar-python' },
						{ label: 'Levantar el servidor', slug: 'getting-started/levantar-servidor' },
						{ label: 'Tu primer documento', slug: 'getting-started/primer-documento' },
					],
				},
				{
					label: 'SDK',
					items: [
						{ label: 'Instalacion SDK TypeScript', slug: 'sdk/instalacion' },
						{ label: 'TypeScript', slug: 'sdk/typescript' },
					],
				},
				{
					label: 'Testing y calidad',
					items: [
						{ label: 'Testing', slug: 'testing' },
						{ label: 'Troubleshooting', slug: 'guides/troubleshooting' },
					],
				},
				{
					label: 'Guias de documentos',
					items: [
						{ label: 'Factura y Boleta', slug: 'guides/factura' },
						{ label: 'Nota de Credito', slug: 'guides/nota-credito' },
						{ label: 'Nota de Debito', slug: 'guides/nota-debito' },
						{ label: 'Resumen Diario', slug: 'guides/resumen-diario' },
						{ label: 'Comunicacion de Baja', slug: 'guides/comunicacion-baja' },
						{ label: 'Percepcion', slug: 'guides/percepcion' },
						{ label: 'Retencion', slug: 'guides/retencion' },
					],
				},
				{
					label: 'Motor openUBL',
					items: [
						{ label: 'Enriquecimiento automatico', slug: 'engine/enriquecimiento' },
						{ label: 'Firma digital', slug: 'guides/firma-digital' },
						{ label: 'Validacion SUNAT', slug: 'guides/validacion' },
						{ label: 'Empaquetado ZIP', slug: 'engine/empaquetado' },
					],
				},
				{
					label: 'Catalogos SUNAT',
					items: [
						{ label: 'Catalogo 01 — Tipo de comprobante', slug: 'catalogs/catalogo-01' },
						{ label: 'Catalogo 02 — Moneda', slug: 'catalogs/catalogo-02' },
						{ label: 'Catalogo 05 — Tipo de tributo', slug: 'catalogs/catalogo-05' },
						{ label: 'Catalogo 06 — Tipo de documento de identidad', slug: 'catalogs/catalogo-06' },
						{ label: 'Catalogo 07 — Tipo de afectacion del IGV', slug: 'catalogs/catalogo-07' },
						{ label: 'Catalogo 16 — Tipo de precio', slug: 'catalogs/catalogo-16' },
						{ label: 'Catalogo 19 — Tipo de operacion (resumen)', slug: 'catalogs/catalogo-19' },
						{ label: 'Catalogo 20 — Motivo de traslado', slug: 'catalogs/catalogo-20' },
						{ label: 'Catalogo 22 — Regimen de percepcion', slug: 'catalogs/catalogo-22' },
						{ label: 'Catalogo 23 — Regimen de retencion', slug: 'catalogs/catalogo-23' },
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
