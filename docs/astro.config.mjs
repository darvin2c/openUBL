// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	site: 'https://openubl.github.io',
	base: '/openubl',
	integrations: [
		starlight({
			title: 'openUBL',
			tagline: 'Facturacion electronica SUNAT, hecha simple.',
			favicon: '/favicon.svg',
			logo: {
				src: './src/assets/logo.svg',
				replacesTitle: true,
			},
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/openubl/openubl' },
			],
			editLink: {
				baseUrl: 'https://github.com/openubl/openubl/edit/main/docs/',
			},
			customCss: [
				'./src/styles/custom.css',
			],
			 expressiveCode: {
				 themes: ['github-light', 'github-dark'],
			 },
			locales: {
				root: {
					label: 'Espanol',
					lang: 'es',
				},
			},
			lastUpdated: true,
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
						{ label: 'Primer documento', slug: 'getting-started/primer-documento' },
					],
				},
				{
					label: 'Guia de uso',
					items: [
						{ label: 'Factura', slug: 'guides/factura' },
						{ label: 'Nota de Credito', slug: 'guides/nota-credito' },
						{ label: 'Nota de Debito', slug: 'guides/nota-debito' },
						{ label: 'Resumen Diario', slug: 'guides/resumen-diario' },
						{ label: 'Comunicacion de Baja', slug: 'guides/comunicacion-baja' },
						{ label: 'Percepcion', slug: 'guides/percepcion' },
						{ label: 'Retencion', slug: 'guides/retencion' },
						{ label: 'Firma digital', slug: 'guides/firma-digital' },
						{ label: 'Validacion SUNAT', slug: 'guides/validacion' },
					],
				},
				{
					label: 'SDKs',
					items: [
						{ label: 'TypeScript', slug: 'sdk/typescript' },
						{ label: 'Java', slug: 'sdk/java' },
						{ label: 'Go', slug: 'sdk/go' },
						{ label: 'Python', slug: 'sdk/python' },
						{ label: 'C#', slug: 'sdk/csharp' },
					],
				},
				{
					label: 'API',
					items: [
						{ label: 'Referencia', slug: 'api/referencia' },
						{ label: 'OpenAPI', slug: 'api/openapi' },
					],
				},
				{
					label: 'Ejemplos',
					items: [
						{ label: 'Curl', slug: 'examples/curl' },
						{ label: 'TypeScript', slug: 'examples/typescript' },
						{ label: 'Python', slug: 'examples/python' },
					],
				},
			],
		}),
	],
});
