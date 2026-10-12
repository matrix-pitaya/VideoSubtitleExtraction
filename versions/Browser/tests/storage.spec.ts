import { test, expect } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';

test('cache corruption is repaired using the immutable digest', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop-edge');
  await page.goto('/'); await expect(page.locator('#capabilities')).toContainText('安全连接：是');
  await page.click('#sample');
  await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150000 });
  await expect(page.locator('#compat-result')).toContainText('短样例已');
  await page.evaluate(async () => {
    await new Promise<void>((resolve, reject) => {
      const request = indexedDB.open('VideoSubtitleExtraction-models', 1);
      request.onsuccess = () => {
        const db = request.result, tx = db.transaction('files', 'readwrite'), store = tx.objectStore('files');
        const keys = store.getAllKeys();
        keys.onsuccess = () => { for (const key of keys.result) if (String(key).endsWith('/config.json')) store.put(new ArrayBuffer(4), key); };
        tx.oncomplete = () => { db.close(); resolve(); }; tx.onerror = () => reject(tx.error);
      };
      request.onerror = () => reject(request.error);
    });
  });
  await page.reload(); await expect(page.locator('#capabilities')).toContainText('安全连接：是');
  await page.click('#sample');
  await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150000 });
  await expect(page.locator('#compat-result')).toContainText('短样例已');
  await page.locator('summary').click(); const event = page.waitForEvent('download'); await page.click('#report');
  const report = JSON.parse(await readFile((await (await event).path())!, 'utf-8'));
  expect(report.errors.some((e: any) => e.code === 'CACHE_REPAIRED')).toBe(true);
  expect(report.samples[0].model.downloadedBytes).toBe(2227);
});

for (const fault of ['unavailable', 'quota'] as const) {
  test(`storage ${fault} reports a warning and runs in memory`, async ({ page, context }, info) => {
    test.skip(info.project.name !== 'desktop-edge');
    await context.route('**/assets/worker-*.js', async route => {
      const response = await route.fetch(), original = await response.text();
      const injection = fault === 'quota'
        ? "IDBObjectStore.prototype.put=function(){throw new DOMException('Injected quota failure','QuotaExceededError')};"
        : "Object.defineProperty(self,'indexedDB',{value:{open(){throw new Error('Injected storage denial')}}});Object.defineProperty(self,'caches',{value:{open(){throw new Error('Injected storage denial')}}});";
      await route.fulfill({ response, body: injection + original });
    });
    await page.goto('/'); await expect(page.locator('#capabilities')).toContainText('安全连接：是');
    await page.click('#sample');
    await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150000 });
    await expect(page.locator('#compat-result')).toContainText('短样例已');
    await page.locator('summary').click(); const event = page.waitForEvent('download'); await page.click('#report');
    const report = JSON.parse(await readFile((await (await event).path())!, 'utf-8'));
    expect(report.errors.some((e: any) => e.code === (fault === 'quota' ? 'CACHE_WRITE_FAILED' : 'CACHE_UNAVAILABLE'))).toBe(true);
    await writeFile(`artifacts/storage-${fault}.json`, JSON.stringify({ faultInjection: true, report }, null, 2));
  });
}
