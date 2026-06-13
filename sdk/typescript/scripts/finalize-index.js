import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const srcDir = path.join(__dirname, '..', 'src');
const indexPath = path.join(srcDir, 'index.ts');
const versionPath = path.join(srcDir, 'version.ts');
const clientConfigPath = path.join(srcDir, 'client.config.ts');
const openapiPath = path.join(__dirname, '..', '..', '..', 'openapi.json');

const versionTemplate = (version) => `export const SDK_VERSION = "${version}";

export async function checkApiVersion(
  baseUrl: string = "http://localhost:8000"
): Promise<{ ok: boolean; sdkVersion: string; apiVersion: string }> {
  const res = await fetch(\`\${baseUrl}/api/v1/version\`);
  if (!res.ok) {
    throw new Error(\`Failed to fetch API version: \${res.status}\`);
  }
  const { version } = (await res.json()) as { version: string };
  return { ok: version === SDK_VERSION, sdkVersion: SDK_VERSION, apiVersion: version };
}
`;

const clientConfig = `import type { CreateClientConfig } from './client.gen.js';

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: 'http://localhost:8000',
});
`;

const indexBlock = `export { client } from "./client.gen.js";
export { SDK_VERSION, checkApiVersion } from "./version.js";
export * from "./sdk.gen.js";
`;

// 1. Regenerate version.ts from openapi.json (openapi-ts wipes src/)
const openapi = JSON.parse(fs.readFileSync(openapiPath, 'utf-8'));
const version = openapi.info?.version ?? '';
if (!version) {
  throw new Error('Could not read version from openapi.json');
}
fs.writeFileSync(versionPath, versionTemplate(version));

// 2. Recreate client.config.ts (openapi-ts wipes src/)
fs.writeFileSync(clientConfigPath, clientConfig);

// 3. Idempotently append re-exports to index.ts
let content = fs.readFileSync(indexPath, 'utf-8');
content = content
  .split('\n')
  .filter((line) =>
    !line.includes('export { client }') &&
    !line.includes('export { SDK_VERSION') &&
    !line.includes('export * from "./sdk.gen.js"')
  )
  .join('\n');
content = content.replace(/\n*$/, '\n');
fs.writeFileSync(indexPath, content + indexBlock);
