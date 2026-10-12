import { test, expect } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';

for (const profile of ['medium']) test(`${profile} actual browser sample and diagnostic`, async ({ page, browser }, info) => {
  test.skip(info.project.name !== 'desktop-edge'); test.setTimeout(600000);
  const diagnostics: string[] = [];
  page.on('console', message => { if (['error', 'warning'].includes(message.type())) diagnostics.push(message.text()); });
  page.on('requestfailed', request => diagnostics.push(`${request.url()}: ${request.failure()?.errorText}`));
  page.on('crash', () => diagnostics.push('Browser renderer crashed'));
  await page.goto('/'); await expect(page.locator('#capabilities')).toContainText('安全连接：是');
  await page.selectOption('#model-profile', profile); await page.click('#sample');
  let lastState = '';
  const timer = setInterval(async () => {
    try {
      lastState = await page.locator('#status').innerText({ timeout: 2000 });
      await writeFile(`artifacts/${profile}-loading-diagnostic.json`, JSON.stringify({ status: lastState, diagnostics }, null, 2));
    } catch { /* main assertion owns the timeout */ }
  }, 10000);
  try { await expect(page.locator('#cancel')).toBeDisabled({ timeout: 540000 }); }
  finally { clearInterval(timer); }
  const status = await page.locator('#status').innerText();
  const texts = await page.locator('#segments textarea').evaluateAll(elements => elements.map(e => (e as HTMLTextAreaElement).value));
  await page.locator('summary').click(); const event = page.waitForEvent('download'); await page.click('#report');
  const report = JSON.parse(await readFile((await (await event).path())!, 'utf-8'));
  await writeFile(`artifacts/${profile}-browser-benchmark.json`, JSON.stringify({ realPhone: false, browserVersion: browser.version(), status, texts, report, diagnostics }, null, 2));
  expect(report.model.model).toBe('whisper-' + profile);
  expect(report.samples[0].success, status).toBe(true);
  expect(report.samples[0].model.modelName).toBe('whisper-' + profile);
  expect(report.samples[0].backend).toBe('wasm');
});
