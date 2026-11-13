// Fails when messages/en.json and messages/pl.json do not have identical key sets (FR-27).
// Usage: node scripts/check-messages.mjs [messagesDirectory]
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const directory = path.resolve(process.argv[2] ?? path.join(here, '..', 'messages'));

function keys(value, prefix = '') {
  return Object.entries(value).flatMap(([key, child]) =>
    typeof child === 'object' && child !== null
      ? keys(child, `${prefix}${key}.`)
      : [`${prefix}${key}`],
  );
}

const load = (locale) =>
  new Set(keys(JSON.parse(readFileSync(path.join(directory, `${locale}.json`), 'utf8'))));
const en = load('en');
const pl = load('pl');
const missingInPl = [...en].filter((key) => !pl.has(key));
const missingInEn = [...pl].filter((key) => !en.has(key));

if (missingInPl.length > 0 || missingInEn.length > 0) {
  console.error(
    [
      ...missingInPl.map((key) => `missing in pl.json: ${key}`),
      ...missingInEn.map((key) => `missing in en.json: ${key}`),
    ].join('\n'),
  );
  process.exit(1);
}
console.log(`messages: ${en.size} keys in both languages.`);
