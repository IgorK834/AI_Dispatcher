import path from 'node:path';
import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTypescript from 'eslint-config-next/typescript';
import { noHardcodedText } from './eslint-rules/no-hardcoded-text.mjs';
import { noRawColors } from './eslint-rules/no-raw-colors.mjs';

const boundaries = {
  rules: {
    'no-raw-colors': noRawColors,
    'no-hardcoded-text': noHardcodedText,
    imports: {
      meta: {
        type: 'problem',
        schema: [],
        messages: {
          boundary: 'Import another feature through its index.ts.',
          fetch: 'HTTP calls belong in lib/api.',
        },
      },
      create(context) {
        const filename = context.filename.replaceAll('\\', '/');
        function checkImport(node) {
          const source = node.source?.value;
          if (typeof source !== 'string') return;
          const target = source.startsWith('@/')
            ? path.resolve(import.meta.dirname, 'src', source.slice(2))
            : source.startsWith('.')
              ? path.resolve(path.dirname(filename), source)
              : source;
          const fromFeature = filename.match(/\/features\/([^/]+)\//)?.[1];
          const toFeature = target.match(/\/features\/([^/]+)(?:\/(.*))?$/);
          if (
            fromFeature &&
            toFeature &&
            fromFeature !== toFeature[1] &&
            toFeature[2] &&
            !/^index(?:\.tsx?)?$/.test(toFeature[2])
          ) {
            context.report({ node, messageId: 'boundary' });
          }
        }
        return {
          ImportDeclaration: checkImport,
          ExportNamedDeclaration: checkImport,
          ExportAllDeclaration: checkImport,
          CallExpression(node) {
            if (
              !filename.includes('/lib/api/') &&
              (node.callee.name === 'fetch' || node.callee.property?.name === 'fetch')
            ) {
              context.report({ node, messageId: 'fetch' });
            }
          },
        };
      },
    },
  },
};

export default defineConfig([
  ...nextVitals,
  ...nextTypescript,
  {
    files: ['src/**/*.{ts,tsx}'],
    plugins: { routepilot: boundaries },
    rules: { 'routepilot/imports': 'error' },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/**/*.test.{ts,tsx}', 'src/test/**'],
    plugins: { routepilot: boundaries },
    rules: { 'routepilot/no-raw-colors': 'error' },
  },
  {
    files: ['src/components/**/*.tsx', 'src/features/**/*.tsx', 'src/app/**/*.tsx'],
    ignores: ['src/**/*.test.tsx'],
    plugins: { routepilot: boundaries },
    rules: { 'routepilot/no-hardcoded-text': 'error' },
  },
  globalIgnores(['.next/**', 'next-env.d.ts', 'src/lib/api/schema.d.ts']),
]);
