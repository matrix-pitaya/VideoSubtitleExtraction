import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import ExcelJS from 'exceljs';
import JSZip from 'jszip';

test('validated device can retry after cancel and background; exports are Simplified Chinese', async ({ page }, info) => {
  const network: string[] = [];
  page.context().on('request', req => { if (req.method() !== 'GET' && req.method() !== 'HEAD') network.push(req.method() + ' ' + req.url()); });
  await page.goto('/'); await expect(page.locator('#capabilities')).toContainText('安全连接：是');
  await expect(page.locator('#backend')).toHaveCount(0);
  await expect(page.locator('#model-profile')).toHaveValue('small');
  await expect(page.locator('.setting-info')).toContainText(['本地计算（WASM）', '简体中文']);
  await expect(page.locator('#model-profile option')).toHaveCount(2);
  await expect(page.locator('#docx')).toBeDisabled(); await expect(page.locator('#xlsx')).toBeDisabled();
  await page.click('#sample');
  await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150000 });
  await expect(page.locator('#compat-result')).toContainText('短样例已');
  await page.setInputFiles('#media', resolve('public/samples/chinese.wav'));
  await page.click('#start'); await page.click('#cancel');
  await expect(page.locator('#status')).toContainText('已取消');
  await expect(page.locator('#start')).toBeEnabled();
  await page.click('#start');
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { get: () => 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange')); delete (document as any).visibilityState;
  });
  await expect(page.locator('#status')).toContainText('已切到后台');
  await expect(page.locator('#start')).toBeEnabled();
  await page.click('#start'); await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150000 });
  await expect(page.locator('#status')).toContainText('候选口播');
  const first = page.locator('#segments textarea').first();
  await first.fill('視頻不會上傳到服務器。'); await first.blur();
  await expect(first).toHaveValue('视频不会上传到服务器。');
  await page.check('#reviewed');
  for (const format of ['txt', 'srt']) {
    const event = page.waitForEvent('download'); await page.click('#' + format);
    const content = await readFile((await (await event).path())!, 'utf-8');
    expect(content).toContain('视频不会上传到服务器。'); expect(content).not.toContain('視頻');
  }
  await page.fill('#title', '客户交付测试');
  for (const format of ['docx', 'xlsx']) {
    const event = page.waitForEvent('download'); await page.click('#' + format);
    const download = await event; expect(download.suggestedFilename()).toBe('客户交付测试.' + format);
    const bytes = await readFile((await download.path())!);
    if (format === 'docx') {
      const zip = await JSZip.loadAsync(bytes); const xml = await zip.file('word/document.xml')!.async('string');
      expect(xml).toContain('1. 客户交付测试'); expect(xml).toContain('视频不会上传到服务器。');
      expect(xml).not.toContain('視頻'); expect(xml).toContain('Heading1');
    } else {
      const workbook = new ExcelJS.Workbook(); await workbook.xlsx.load(bytes as any);
      const sheet = workbook.worksheets[0]; expect(sheet.columnCount).toBe(3);
      expect(sheet.getRow(1).values).toEqual([undefined, '编号', '标题', '文案']);
      expect(sheet.getCell('A2').value).toBe(1); expect(sheet.getCell('B2').value).toBe('客户交付测试');
      expect(sheet.getCell('C2').value).toContain('视频不会上传到服务器。');
    }
    await expect(page.locator('#xlsx')).toBeEnabled();
  }
  await page.click('#clear-speech'); await page.check('#reviewed');
  await expect(page.locator('#txt')).toBeDisabled(); await expect(page.locator('#xlsx')).toBeEnabled();
  const emptyEvent = page.waitForEvent('download'); await page.click('#xlsx');
  const emptyBook = new ExcelJS.Workbook(); await emptyBook.xlsx.load(await readFile((await (await emptyEvent).path())!) as any);
  expect(emptyBook.worksheets[0].getCell('C2').value ?? '').toBe('');
  await page.reload(); await expect(page.locator('#capabilities')).toContainText('安全连接：是');
  await page.click('#sample'); await expect(page.locator('#cancel')).toBeDisabled({ timeout: 150000 });
  await expect(page.locator('#compat-result')).toContainText('短样例已');
  await page.locator('summary').click(); const reportEvent = page.waitForEvent('download'); await page.click('#report');
  const report = JSON.parse(await readFile((await (await reportEvent).path())!, 'utf-8'));
  expect(report.model.model).toBe('whisper-small'); expect(report.samples[0].backend).toBe('wasm');
  expect(report.samples[0].model.downloadedBytes).toBe(0);
  expect(report.samples[0].model.cachedBytes).toBe(251846613);
  expect(network).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `artifacts/${info.project.name}-workbench.png`, fullPage: true });

});
