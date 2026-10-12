import { readFile, writeFile, mkdir, readdir, copyFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
const lock = JSON.parse(await readFile('package-lock.json', 'utf8'));
await mkdir('public/licenses', { recursive: true });
await mkdir('reports', { recursive: true });
const packages = [];
for (const [path, entry] of Object.entries(lock.packages)) {
  if (!path) continue;
  try {
    const pkg = JSON.parse(await readFile(resolve(path, 'package.json'), 'utf8'));
    const notices = [];
    const filenames = await readdir(path);
    if (pkg.name === 'opencc-js') filenames.push('LICENSES/Apache-2.0.txt');
    for (const filename of filenames) {
      if (!/^(licen[cs]es?|copying|notice|third_party_licenses)(\.|\/|$)/i.test(filename)) continue;
      try {
        const bytes = await readFile(resolve(path, filename));
        const output = `${pkg.name.replaceAll('/', '_')}-${pkg.version}-${filename.replaceAll('/', '_')}`;
        await copyFile(resolve(path, filename), resolve('public/licenses', output));
        notices.push({ file: output, sha256: createHash('sha256').update(bytes).digest('hex') });
      } catch { /* some packages put multiple license files in a directory */ }
    }
    packages.push({ name: pkg.name, version: pkg.version, license: pkg.license ?? entry.license ?? 'CHECK_REQUIRED', development: Boolean(entry.dev), npmIntegrity: entry.integrity ?? null, notices });
  } catch { /* optional package not installed on this OS; lockfile still pins it */ }
}
await copyFile('../Web/MODEL_LICENSE.txt', 'public/licenses/OpenAI-Whisper-MIT.txt');
await writeFile('reports/dependency-licenses.json', JSON.stringify({ scope: 'installed packages including development tooling; not all are delivered to browsers', packages }, null, 2) + '\n');
console.log(`Recorded ${packages.length} installed packages and available notices`);
