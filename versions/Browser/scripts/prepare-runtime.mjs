import { copyFile, mkdir, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
const source = resolve('node_modules/onnxruntime-web/dist');
const destination = resolve('public/runtime');
await mkdir(destination, { recursive: true });
const files = [];
for (const name of await readdir(source)) {
  if (name.endsWith('.wasm') || name.endsWith('.mjs')) {
    await copyFile(resolve(source, name), resolve(destination, name));
    const data = await readFile(resolve(destination, name));
    files.push({ path: name, bytes: data.length, sha256: createHash('sha256').update(data).digest('hex') });
  }
}
const manifest = JSON.stringify({ package: 'onnxruntime-web', version: '1.22.0-dev.20250409-89f8206ba4', files }, null, 2);
await writeFile(resolve(destination, 'manifest.json'), manifest);
await writeFile(resolve('src/runtime-manifest.json'), manifest + '\n');
console.log(`Prepared ${files.length} pinned runtime files`);
