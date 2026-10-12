import { test, expect } from '@playwright/test';

test('worker refuses accelerated modes and models below small before downloading', async ({ page, context }) => {
  const downloads: string[] = [];
  context.on('request', request => { if (request.url().includes('/models/')) downloads.push(request.url()); });
  const created = page.waitForEvent('worker'); await page.goto('/');
  const url = (await created).url();
  for (const [backend, modelProfile, expected] of [['webgpu', 'small', 'MODE_UNSUPPORTED'], ['auto', 'small', 'MODE_UNSUPPORTED'], ['wasm', 'tiny', 'MODEL_UNKNOWN'], ['wasm', 'base', 'MODEL_UNKNOWN'], ['wasm', 'large-v3', 'MODEL_UNKNOWN']]) {
    const result: any = await page.evaluate(async ({ url, backend, modelProfile }) => {
      const worker = new Worker(url, { type: 'module' });
      try {
        return await new Promise((resolve, reject) => {
          const timer = setTimeout(() => reject(new Error('Worker timeout')), 10000);
          worker.onmessage = event => { clearTimeout(timer); resolve(event.data); };
          worker.onerror = event => { clearTimeout(timer); reject(new Error(event.message)); };
          worker.postMessage({ id: 1, type: 'prepare', backend, modelProfile, baseUrl: new URL('./', location.href).href });
        });
      } finally { worker.terminate(); }
    }, { url, backend, modelProfile });
    expect(result.type).toBe('error'); expect(result.code).toBe(expected);
  }
  expect(downloads).toEqual([]);
});
