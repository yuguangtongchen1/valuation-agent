import { readFileSync, writeFileSync } from 'node:fs';
const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
const entry = html.match(/<script[^>]*src="([^"]+)"/)[1];
writeFileSync(new URL('../dist/assets/current-build.json', import.meta.url), JSON.stringify({entry}));
