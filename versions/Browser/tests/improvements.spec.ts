import { test, expect } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

test('gallery invokes a video picker and a 28 MiB video is decoded', async ({ page }, info) => {
  await page.goto('/'); await expect(page.locator('#capabilities')).toContainText('安全连接：是');
  await expect(page.locator('#gallery')).toHaveAttribute('accept', 'video/*');
  expect(await page.locator('#gallery').getAttribute('capture')).toBeNull();
  await expect(page.locator('#media')).toBeHidden();
  const fileChooser = page.waitForEvent('filechooser'); await page.click('#file-button');
  await (await fileChooser).setFiles(resolve('public/samples/chinese.wav'));
  await expect(page.locator('#file-info')).toContainText('chinese.wav');
  const chooser = page.waitForEvent('filechooser'); await page.click('#gallery-button');
  const mp4 = await readFile(resolve('public/samples/chinese.mp4'));
  const padding = Buffer.alloc(28 * 1048576 - mp4.length);
  padding.writeUInt32BE(padding.length, 0); padding.write('free', 4, 'ascii');
  await (await chooser).setFiles({ name: '图库视频', mimeType: 'video/mp4', buffer: Buffer.concat([mp4, padding]) });
  await expect(page.locator('#file-info')).toContainText('28.00 MiB');
  await expect(page.locator('#file-info')).not.toContainText('超过限制');
  await page.click('#sample');
  await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150000 });
  await expect(page.locator('#start')).toBeEnabled(); await page.click('#start');
  await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150000 });
  if (info.project.name === 'iphone-emulated-webkit') await expect(page.locator('#status')).toContainText('FORMAT_UNSUPPORTED');
  else await expect(page.locator('#status')).toContainText('候选口播');
});

test('small runs actual Chinese inference and long audio keeps offsets beyond 60 seconds', async ({ page, browser }, info) => {
  test.skip(info.project.name !== 'desktop-edge');
  await page.goto('/'); await expect(page.locator('#capabilities')).toContainText('安全连接：是');
  
  await page.click('#sample'); await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150000 });
  await expect(page.locator('#compat-result')).toContainText('短样例已');
  const texts = await page.locator('#segments textarea').evaluateAll(elements => elements.map(e => (e as HTMLTextAreaElement).value));
  await page.locator('summary').click(); const event = page.waitForEvent('download'); await page.click('#report');
  const report = JSON.parse(await readFile((await (await event).path())!, 'utf-8'));
  expect(report.model.model).toBe('whisper-small');
  await writeFile('artifacts/desktop-edge-small-benchmark.json', JSON.stringify({ realPhone: false, browserVersion: browser.version(), report, texts }, null, 2));
  const original = await readFile(resolve('public/samples/chinese.wav'));
  const sourceOffset = original.indexOf(Buffer.from('data')) + 8;
  expect(sourceOffset).toBeGreaterThan(8);
  const wav = Buffer.alloc(44 + 66 * 32000);
  const silence = await readFile(resolve('public/samples/silence.wav'));
  silence.copy(wav, 0, 0, 44); wav.writeUInt32LE(wav.length - 8, 4); wav.writeUInt32LE(wav.length - 44, 40);
  original.copy(wav, 44 + 58 * 32000, sourceOffset);
  await page.setInputFiles('#media', { name: '66-seconds.wav', mimeType: 'audio/wav', buffer: wav });
  await page.click('#start'); await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150000 });
  await expect(page.locator('#status')).toContainText('候选口播');
  await page.check('#reviewed'); const srtEvent = page.waitForEvent('download'); await page.click('#srt');
  const srt = await readFile((await (await srtEvent).path())!, 'utf-8');
  expect(srt).toMatch(/00:01:0[0-6],\d{3}/);
  await writeFile('artifacts/long-audio-result.json', JSON.stringify({ seconds: 66, srt, realPhone: false }, null, 2));
});

test('PC model choices switch without downloading; computation has no dropdown', async ({ page, context }) => {
  const requests: string[] = [];
  context.on('request', request => { if (request.url().includes('/models/')) requests.push(request.url()); });
  await page.goto('/'); await expect(page.locator('#capabilities')).toContainText('安全连接：是');
  await expect(page.locator('#backend')).toHaveCount(0);
  await expect(page.locator('#model-profile')).toBeEnabled();
  await expect(page.locator('#model-profile')).toHaveValue('small');
  await expect(page.locator('#model-profile option')).toHaveCount(2);
  await page.selectOption('#model-profile', 'medium'); await expect(page.locator('#limits')).toContainText('742.8 MiB');
  await expect(page.locator('#start')).toBeDisabled();
  await page.selectOption('#model-profile', 'small');
  expect(requests).toEqual([]);
});
