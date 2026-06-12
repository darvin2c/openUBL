import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  client: '@hey-api/client-fetch',
  input: '../../openapi.json',
  output: 'src',
  plugins: [
    {
      name: '@hey-api/client-fetch',
      runtimeConfigPath: './src/client.config.js',
    },
    {
      name: '@hey-api/sdk',
      operations: {
        strategy: 'flat',
      },
      validator: true,
    },
    'zod',
  ],
});
