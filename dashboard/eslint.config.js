// Flat config: typescript-eslint (type-aware), React, hooks, a11y, import.
import importPlugin from 'eslint-plugin-import';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  // types.gen.ts is generated from the API schema; tsc still checks it.
  { ignores: ['node_modules/', 'src/api/types.gen.ts'] },
  ...tseslint.configs.strictTypeChecked,
  react.configs.flat.recommended,
  react.configs.flat['jsx-runtime'],
  reactHooks.configs.flat['recommended-latest'],
  jsxA11y.flatConfigs.strict,
  importPlugin.flatConfigs.recommended,
  importPlugin.flatConfigs.typescript,
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    settings: { react: { version: 'detect' } },
    rules: {
      // Stored text is data: it is only ever rendered as text.
      'react/no-danger': 'error',
      '@typescript-eslint/no-explicit-any': 'error',
      'max-lines': ['error', { max: 300 }],
      // tsc resolves every import, including package "exports" maps that
      // the import plugin's node resolver cannot read.
      'import/no-unresolved': 'off',
      'import/order': ['error', { alphabetize: { order: 'asc' } }],
    },
  },
  {
    files: ['eslint.config.js', 'scripts/*.mjs'],
    extends: [tseslint.configs.disableTypeChecked],
  },
);
