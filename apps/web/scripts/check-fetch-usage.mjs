// Fails when `fetch(` appears in application code outside src/lib/api (FR-26, CI Gate 4).
// Usage: node scripts/check-fetch-usage.mjs [sourceDirectory]
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(process.argv[2] ?? path.join(here, '..', 'src'));
const FETCH = /(?<![\w.$])fetch\s*\(|\.fetch\s*\(/;

function* walk(directory) {
  for (const name of readdirSync(directory)) {
    const full = path.join(directory, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.(ts|tsx|js|jsx|mjs)$/.test(name) && !/\.test\./.test(name)) yield full;
  }
}

const offenders = [];
for (const file of walk(root)) {
  const relative = path.relative(root, file).replaceAll('\\', '/');
  if (relative.startsWith('lib/api/')) continue;
  readFileSync(file, 'utf8')
    .split('\n')
    .forEach((line, index) => {
      if (FETCH.test(line)) offenders.push(`${relative}:${index + 1}: ${line.trim()}`);
    });
}

if (offenders.length > 0) {
  console.error('fetch( is only allowed in src/lib/api:\n' + offenders.join('\n'));
  process.exit(1);
}
console.log('No fetch( outside src/lib/api.');
