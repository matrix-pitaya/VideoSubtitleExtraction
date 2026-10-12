import { test, expect, type Page } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

async function sample(page: Page) {
  await page.goto('/');
  await expect(page.locator('#capabilities')).toContainText('安全连接：是');
  await page.click('#sample');
  await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150_000 });
  const status = await page.locator('#status').innerText();
  expect(status, await page.locator('#compat-result').innerText()).toContain('候选口播');
  await expect(page.locator('#compat-result')).toContainText('短样例已');
}

async function exportReport(page: Page): Promise<any> {
  await page.locator('summary').click();
  const download = page.waitForEvent('download'); await page.click('#report');
  const file = await download;
  return JSON.parse(await readFile((await file.path())!, 'utf-8'));
}

test('Chinese inference, local file, cache, export and network privacy', async ({ page, browser, context }, info) => {
  test.setTimeout(600000);
  const requests: { method: string; url: string; body: number }[] = [];
  const errors: string[] = [];
  context.on('request', req => requests.push({ method: req.method(), url: req.url(), body: req.postDataBuffer()?.length ?? 0 }));
  page.on('pageerror', error => errors.push(error.message));
  await sample(page);
  const firstText = await page.locator('#segments textarea').evaluateAll(elements => elements.map(e => (e as HTMLTextAreaElement).value));
  await expect(page.locator('#txt')).toBeDisabled();
  await page.check('#reviewed');
  const txtEvent = page.waitForEvent('download'); await page.click('#txt');
  const txtDownload = await txtEvent;
  const txtBytes = await readFile((await txtDownload.path())!);
  expect([...txtBytes.subarray(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
  const txt = txtBytes.toString('utf-8');
  expect(txt).toMatch(/[\u3400-\u9fff]/);
  const srtEvent = page.waitForEvent('download'); await page.click('#srt');
  const srt = await readFile((await (await srtEvent).path())!, 'utf-8');
  expect(srt).toMatch(/00:00:\d{2},\d{3} --> 00:00:\d{2},\d{3}/);
  const firstReport = await exportReport(page);
  await page.reload(); await expect(page.locator('#capabilities')).toContainText('安全连接：是');
  await page.click('#sample');
  await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150_000 });
  await expect(page.locator('#compat-result')).toContainText('短样例已');
  const cachedReport = await exportReport(page);
  expect(cachedReport.samples[0].model.downloadedBytes).toBe(0);
  await page.setInputFiles('#media', { name: '中文视频路径.mp4', mimeType: 'video/mp4', buffer: await readFile(resolve('public/samples/chinese.mp4')) });
  await page.click('#start');
  await expect(page.locator('#cancel')).toBeDisabled({ timeout: 120_000 });
  const mp4Status = await page.locator('#status').innerText();
  const mp4Text = await page.locator('#segments textarea').evaluateAll(elements => elements.map(e => (e as HTMLTextAreaElement).value));
  if (info.project.name === 'iphone-emulated-webkit') expect(mp4Status).toContain('FORMAT_UNSUPPORTED');
  else { expect(mp4Status).toContain('候选口播'); expect(mp4Text.length).toBeGreaterThan(0); }
  const mediaResults: Record<string, unknown> = {};
  for (const name of ['chinese.mov', 'chinese.mp3', 'silence.wav', 'bgm.wav', 'boundary.wav', 'no-audio.mp4', 'broken.mp4', 'chinese.wav']) {
    await page.setInputFiles('#media', resolve('public/samples/' + name));
    await page.click('#start');
    await expect(page.locator('#cancel')).toBeDisabled({ timeout: 120_000 });
    const status = await page.locator('#status').innerText();
    const texts = await page.locator('#segments textarea').evaluateAll(elements => elements.map(e => (e as HTMLTextAreaElement).value));
    mediaResults[name] = { status, texts };
    if (name === 'silence.wav') { expect(status).toContain('文案留空'); expect(texts).toEqual([]); await expect(page.locator('#txt')).toBeDisabled(); }
    else if (name === 'no-audio.mp4') expect(status).toContain('NO_AUDIO');
    else if (name === 'broken.mp4') expect(status).toContain('MEDIA_INVALID');
    else if (name === 'bgm.wav') {
      await expect(page.locator('#txt')).toBeDisabled();
      if (texts.length) { await page.click('#clear-speech'); await expect(page.locator('#segments textarea')).toHaveCount(0); }
    } else if (info.project.name === 'iphone-emulated-webkit' && ['chinese.mov', 'chinese.mp3'].includes(name)) {
      expect(status).toContain('FORMAT_UNSUPPORTED');
    } else { expect(status).toContain('候选口播'); expect(texts.length).toBeGreaterThan(0); }
    if (name === 'boundary.wav') {
      const times = await page.locator('#segments input').evaluateAll(elements => elements.map(e => Number((e as HTMLInputElement).value)));
      expect(times.every(Number.isFinite)).toBeTruthy();
      expect(times.at(-1)).toBeGreaterThan(20);
      for (let i = 0; i < times.length; i += 2) { expect(times[i + 1]).toBeGreaterThan(times[i]); if (i) expect(times[i]).toBeGreaterThanOrEqual(times[i - 1]); }
    }
  }
  // Browser-owned download panels (edge://) are not network calls from this application.
  const networkRequests = requests.filter(req => ['http:', 'https:'].includes(new URL(req.url).protocol));
  const nonLocal = networkRequests.filter(req => new URL(req.url).origin !== 'http://127.0.0.1:5174');
  expect(nonLocal).toEqual([]);
  expect(networkRequests.filter(req => req.body || !['GET', 'HEAD'].includes(req.method))).toEqual([]);
  expect(errors).toEqual([]);
  await mkdir('artifacts', { recursive: true });
  await writeFile(`artifacts/${info.project.name}-benchmark.json`, JSON.stringify({ deviceKind: 'desktop-or-emulated-not-real-phone', browserVersion: browser.version(), firstReport, cachedReport, firstText, mp4Status, mp4Text, mediaResults, network: { requests: networkRequests.length, browserInternalRequests: requests.length - networkRequests.length, nonLocal: nonLocal.length, uploads: 0 }, txt, srt }, null, 2));
  await page.screenshot({ path: `artifacts/${info.project.name}.png`, fullPage: true });
});
