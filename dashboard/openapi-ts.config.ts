import { defineConfig, plugins } from '@hey-api/openapi-ts';

export default defineConfig({
  input: '../openspec/openapi-v1.yaml',
  output: 'src/api/generated/openapi-v1',
  plugins: [
    plugins.typescript(),
    plugins.clientAxios(),
    plugins.sdk({
      client: '@hey-api/client-axios',
    }),
  ],
});
