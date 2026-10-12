import { test, expect } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

test('non-loopback HTTP is a real insecure context and cannot start', async ({ page, context }, info) => {
  test.skip(info.project.name !== 'desktop-edge');
  // Serve local fixture responses under a non-loopback HTTP origin without contacting that host.
  await context.route('http://vse-http-test.invalid/**', async route => {
    const url = new URL(route.request().url());
    const response = await context.request.get('http://127.0.0.1:5174' + url.pathname + url.search);
    await route.fulfill({ response });
  });
  await page.goto('http://vse-http-test.invalid/');
  expect(await page.evaluate(() => isSecureContext)).toBe(false);
  await expect(page.locator('#capabilities')).toContainText('安全连接：否');
  await expect(page.locator('#status')).toContainText('HTTPS_REQUIRED');
  await expect(page.locator('#sample')).toBeDisabled();
});

test('cancel and background interruption terminate the task and allow retry', async ({ page, context }) => {
  await context.route('**/models/**', async route => { await new Promise(r => setTimeout(r, 1500)); await route.continue().catch(() => {}); });
  await page.goto('/');
  await expect(page.locator('#capabilities')).toContainText('安全连接：是');
  const request = page.waitForRequest('**/models/**');
  await page.click('#sample'); await request; await page.click('#cancel');
  await expect(page.locator('#status')).toContainText('已取消');
  await expect(page.locator('#sample')).toBeEnabled();
  await context.unroute('**/models/**');
  await page.click('#sample');
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { get: () => 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    delete (document as any).visibilityState;
  });
  await expect(page.locator('#status')).toContainText('已切到后台');
  await page.click('#sample');
  await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150000 });
  await expect(page.locator('#compat-result')).toContainText('短样例已');
  const oversizedPath = resolve('artifacts/oversize.wav');
  await writeFile(oversizedPath, Buffer.alloc(100 * 1048576 + 1));
  await page.setInputFiles('#media', oversizedPath);
  await expect(page.locator('#start')).toBeDisabled();
  await expect(page.locator('#file-info')).toContainText('超过限制');
  const wav = Buffer.alloc(44 + 61 * 32000);
  Buffer.from(await readFile(resolve('public/samples/silence.wav'))).copy(wav, 0, 0, 44);
  wav.writeUInt32LE(wav.length - 8, 4); wav.writeUInt32LE(wav.length - 44, 40);
  await page.setInputFiles('#media', { name: 'long.wav', mimeType: 'audio/wav', buffer: wav });
  await page.click('#start'); await expect(page.locator('#cancel')).toBeDisabled();
  await expect(page.locator('#status')).toContainText('文案留空');
});

test('missing or tampered model is refused before inference', async ({ page, context }) => {
  await context.route('**/models/**/config.json', route => route.fulfill({ status: 404, body: '' }));
  await page.goto('/'); await expect(page.locator('#capabilities')).toContainText('安全连接：是');
  await page.click('#sample');
  await expect(page.locator('#status')).toContainText('MODEL_MISSING');
  await expect(page.locator('#start')).toBeDisabled();
  await context.unroute('**/models/**/config.json');
  await context.route('**/models/**/config.json', async route => {
    const response = await route.fetch(); const body = Buffer.from(await response.body()); body[0] ^= 1;
    await route.fulfill({ response, body });
  });
  await page.click('#sample');
  await expect(page.locator('#status')).toContainText('MODEL_INTEGRITY');
  await expect(page.locator('#segments textarea')).toHaveCount(0);
});

