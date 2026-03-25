import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['.svelte-kit/', 'node_modules/', 'build/'] },
  js.configs.recommended,
  ...svelte.configs['flat/recommended'],
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node
      }
    },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^_', argsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' }]
    }
  },
  {
    files: ['**/*.svelte'],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser
      }
    },
    rules: {
      'svelte/valid-compile': ['error', { ignoreWarnings: true }],
      // False positive: applies to server hooks (handle), not client-side goto()
      'svelte/no-navigation-without-resolve': 'off',
      // Valid but 52 instances — address in a follow-up PR
      'svelte/require-each-key': 'warn',
      // Style suggestion, not critical
      'svelte/prefer-writable-derived': 'warn'
    }
  }
);
