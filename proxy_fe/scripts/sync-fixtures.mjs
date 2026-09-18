// Copies the contract's golden fixtures into the frontend test tree so the
// frontend can be developed and tested without the backend or CI running.
import { copyFileSync, mkdirSync, readdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const source = join(here, '..', '..', 'contract', 'fixtures');
const destination = join(here, '..', 'tests', 'fixtures');

rmSync(destination, { recursive: true, force: true });
mkdirSync(destination, { recursive: true });

const names = readdirSync(source).filter((name) => name.endsWith('.json'));
for (const name of names) {
  copyFileSync(join(source, name), join(destination, name));
}
console.log(`synced ${names.length} fixtures`);
