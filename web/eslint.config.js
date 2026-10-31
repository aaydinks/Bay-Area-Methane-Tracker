import eslintPluginAstro from 'eslint-plugin-astro';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import tseslint from 'typescript-eslint';

export default [
  { ignores: ['dist/**', '.astro/**', 'node_modules/**', 'src/data/**', 'public/**'] },
  ...tseslint.configs.recommended,
  ...eslintPluginAstro.configs['flat/recommended'],
  { files: ['**/*.tsx'], ...jsxA11y.flatConfigs.recommended },
  {
    files: ['scripts/**/*.mjs', 'fixtures/**/*.mjs', 'playwright.config.ts', 'tests/**/*.ts'],
    languageOptions: {
      globals: { process: 'readonly', console: 'readonly', URL: 'readonly', fetch: 'readonly' },
    },
  },
];
