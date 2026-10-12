import './style.css';
import { toSimplified } from './chinese.ts';
import { officeFile } from './office-export.ts';
import { LIMITS, type Backend } from './config.ts';
import { PrototypeError } from './audio.ts';
import { nativeDecode } from './native-audio.ts';
import { WorkerClient } from './worker-client.ts';
import { safeFilename, toSrt, txtForDownload, type Task } from './protocol.ts';
import { MODELS, type ModelProfile } from './models.ts';
let manifest = MODELS.small;

const get = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const button = (id: string) => get<HTMLButtonElement>(id);
const text = (id: string, value: string) => { get(id).textContent = value; };
const baseUrl = new URL('./', location.href).href;
const client = new WorkerClient();
const report: any = { schemaVersion: '1.0', prototype: '0.1.5', createdAt: new Date().toISOString(), userAgent: navigator.userAgent, platform: navigator.platform, hardwareConcurrency: navigator.hardwareConcurrency ?? null, deviceMemoryGiB: (navigator as any).deviceMemory ?? null, secureContext: isSecureContext, model: { ...manifest, files: undefined }, samples: [], errors: [], limits: LIMITS, realDeviceVerified: false };
let generation = 0, busy = false, samplePassed = true, exporting = false;
let currentFile: File | undefined, task: Task | undefined, capabilities: any = {}, wake: any;
const clearButton = document.createElement('button'); clearButton.id = 'clear-speech'; clearButton.textContent = '确认无口播，清空候选'; clearButton.disabled = true;
get('segments').after(clearButton);

function updateButtons(): void {
  button('start').disabled = busy || exporting || !currentFile || currentFile.size > LIMITS.maxFileBytes;
  button('cancel').disabled = !busy;
  get<HTMLInputElement>('media').disabled = busy || exporting;
  button('gallery-button').disabled = busy || exporting;
  button('file-button').disabled = busy || exporting;
  get<HTMLInputElement>('gallery').disabled = busy || exporting;
  get<HTMLSelectElement>('model-profile').disabled = busy || exporting;
  const valid = Boolean(task?.segments.length && get<HTMLInputElement>('reviewed').checked && task.segments.every((s, i, all) => s.text.trim() && Number.isFinite(s.start) && Number.isFinite(s.end) && s.start >= 0 && s.end > s.start && (!i || s.start >= all[i - 1].end)));
  for (const id of ['txt', 'srt', 'docx', 'xlsx', 'share']) button(id).disabled = busy || exporting || !valid;
  const reviewedEmpty = Boolean(task?.state === 'no_speech' && get<HTMLInputElement>('reviewed').checked);
  for (const id of ['docx', 'xlsx']) button(id).disabled = busy || exporting || !(valid || reviewedEmpty);
  clearButton.disabled = busy || !task?.segments.length;
}

function selectFile(input: HTMLInputElement): void {
  const file = input.files?.[0];
  if (!file) return;
  currentFile = file;
  text('file-info', currentFile ? `${currentFile.name} · ${(currentFile.size / 1048576).toFixed(2)} MiB${currentFile.size > LIMITS.maxFileBytes ? '，超过限制' : ''}` : '尚未选择文件');
  task = undefined; renderSegments(); get<HTMLInputElement>('reviewed').checked = false; updateButtons();
}
for (const id of ['media', 'gallery']) get<HTMLInputElement>(id).addEventListener('change', event => selectFile(event.target as HTMLInputElement));
button('gallery-button').onclick = () => { const input = get<HTMLInputElement>('gallery'); input.value = ''; input.click(); };
button('file-button').onclick = () => { const input = get<HTMLInputElement>('media'); input.value = ''; input.click(); };
get<HTMLSelectElement>('model-profile').addEventListener('change', () => {
  manifest = MODELS[get<HTMLSelectElement>('model-profile').value as ModelProfile];
  report.model = { ...manifest, files: undefined };
  samplePassed = true; task = undefined; renderSegments(); client.restart('MODEL_CHANGED');
  text('compat-result', `已切换 ${manifest.model}，导入文件后即可识别；大模型耗时和内存更多，文案仍需校对。`);
  showLimits(); updateButtons();
});
button('start').onclick = () => void run(false);
button('cancel').onclick = () => cancel();
get<HTMLInputElement>('reviewed').onchange = updateButtons;
clearButton.onclick = () => { if (task) { task.segments = []; task.state = 'no_speech'; renderSegments(); text('status', '已人工确认无口播，候选文字已清空。'); updateButtons(); } };
button('txt').onclick = () => { try { const file = filesForExport()[0]; saveBlob(file, file.name); } catch { text('save-status', '字幕时间或文字无效，请校对。'); } };
button('srt').onclick = () => { try { const file = filesForExport()[1]; saveBlob(file, file.name); } catch { text('save-status', '字幕时间或文字无效，请校对。'); } };
for (const format of ['docx', 'xlsx'] as const) button(format).onclick = async () => {
  if (!task || exporting) return;
  exporting = true; updateButtons(); text('save-status', '正在本地生成交付文件…');
  try {
    const file = await officeFile(format, get<HTMLInputElement>('title').value || task.title, task.segments);
    saveBlob(file, file.name);
  } catch (error) { text('save-status', error instanceof Error ? error.message : '生成文件失败，请重试。'); }
  finally { exporting = false; updateButtons(); }
};
button('share').onclick = async () => {
  try { const files = filesForExport(); if (!navigator.canShare?.({ files })) { text('save-status', '此浏览器不支持文件分享，请使用保存 TXT/SRT。'); return; } await navigator.share({ files, title: '视频口播文案' }); }
  catch { text('save-status', '分享已取消或不可用，可使用保存 TXT/SRT。'); }
};
button('copy-link').onclick = async () => { try { await navigator.clipboard.writeText(location.href); text('compat-result', '链接已复制，请手动粘贴到系统浏览器。'); } catch { text('compat-result', '无法自动复制，请复制浏览器地址栏中的完整链接。'); } };
button('report').onclick = () => { report.deviceLabel = get<HTMLInputElement>('device-name').value.slice(0, 100); saveBlob(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }), 'VideoSubtitleExtraction-device-report.json'); };
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') cancel('BACKGROUND_INTERRUPTED'); });
window.addEventListener('pagehide', () => { client.close(); });
function showLimits(): void { text('limits', `当前试验限制：单文件，不超过 ${LIMITS.maxFileBytes / 1048576} MiB；没有固定时长限制，长音频分段识别，解码内存不足时会提示分段导入。所选模型首次下载约 ${(manifest.totalBytes / 1048576).toFixed(1)} MiB，另需加载浏览器运行组件；建议 Wi-Fi。`); }
showLimits();
void client.call('probe').then(result => {
  capabilities = result; report.capabilities = result;
  text('capabilities', `安全连接：${result.secureContext ? '是' : '否'} ｜ 本地计算：WASM ｜ 音频解码：${result.audioDecoder ? '接口可用，格式待验证' : '将尝试系统音频解码'}`);
  if (!result.secureContext) text('status', 'HTTPS_REQUIRED：公网 HTTP/IP 不是安全上下文。请使用可信 HTTPS；本机 localhost 仅用于开发测试。');
  updateButtons();
}).catch(() => { text('capabilities', '浏览器能力检测失败。请复制链接到系统浏览器重试。'); });

function renderSegments(): void {
  const container = get('segments'); container.replaceChildren();
  for (const [index, segment] of (task?.segments ?? []).entries()) {
    const row = document.createElement('div'); row.className = 'segment';
    for (const key of ['start', 'end'] as const) {
      const input = document.createElement('input'); input.type = 'number'; input.min = '0'; input.step = '0.01'; input.value = segment[key].toFixed(2);
      input.setAttribute('aria-label', `${index + 1} ${key === 'start' ? '开始' : '结束'}秒`);
      input.addEventListener('input', () => { segment[key] = Number(input.value); get<HTMLInputElement>('reviewed').checked = false; updateButtons(); });
      row.append(input);
    }
    segment.text = toSimplified(segment.text);
    const input = document.createElement('textarea'); input.value = segment.text; input.setAttribute('aria-label', `${index + 1} 口播文字`);
    input.addEventListener('input', () => { segment.text = input.value; get<HTMLInputElement>('reviewed').checked = false; updateButtons(); });
    input.addEventListener('change', () => { segment.text = toSimplified(input.value); input.value = segment.text; });
    row.append(input); container.append(row);
  }
}

function saveBlob(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.href = url; link.download = name; link.rel = 'noopener'; document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  text('save-status', '已请求保存。iPhone 如显示预览，请用分享菜单保存到“文件”；实际行为需真机确认。');
}

function filesForExport(): File[] {
  if (!task) return [];
  const title = safeFilename(get<HTMLInputElement>('title').value || task.title);
  return [new File([txtForDownload(task.segments)], title + '.txt', { type: 'text/plain;charset=utf-8' }), new File([toSrt(task.segments)], title + '.srt', { type: 'application/x-subrip;charset=utf-8' })];
}

async function releaseWake(): Promise<void> {
  const lock = wake; wake = undefined;
  try { await lock?.release(); } catch { /* already released by the OS */ }
}

function cancel(code = 'CANCELED'): void {
  if (!busy) return;
  generation++; client.restart(code); busy = false;
  if (task) { task.state = 'canceled'; task.error = { code, message: '任务中断，已有分段仅供校对。' }; }
  report.errors.push({ code, phase: 'task' });
  text('status', (code === 'BACKGROUND_INTERRUPTED' ? '已切到后台，任务已中断。回到前台后' : '已取消。') + '可重新点击开始本地识别。');
  void releaseWake(); updateButtons();
}

async function decode(file: File, token: number): Promise<{ pcm: Float32Array; decodeMs: number }> {
  const start = performance.now(), buffer = await file.arrayBuffer();
  if (token !== generation) throw new PrototypeError('CANCELED', '任务已取消。');
  const suffix = file.name.split('.').at(-1)?.toLowerCase();
  const mimeExtensions: Record<string, string> = { 'video/mp4': 'mp4', 'video/quicktime': 'mov', 'audio/mp4': 'm4a', 'audio/mpeg': 'mp3', 'audio/wav': 'wav', 'audio/x-wav': 'wav' };
  const extension = ['wav', 'mp3', 'mp4', 'mov', 'm4a'].includes(suffix ?? '') ? suffix : mimeExtensions[file.type];
  try { return await client.call('decode', { extension, buffer, modelProfile: get<HTMLSelectElement>('model-profile').value }, undefined, [buffer]); }
  catch (error) {
    if (token !== generation) throw new PrototypeError('CANCELED', '任务已取消。');
    // The lightweight MP4 path handles AAC-LC in the Worker. Other browser
    // supported MP4 audio profiles (for example HE-AAC) use the system decoder.
    if (!['NATIVE_AUDIO_REQUIRED', 'DECODER_UNAVAILABLE', 'FORMAT_UNSUPPORTED'].includes((error as PrototypeError).code)) throw error;
    return { pcm: await nativeDecode(file), decodeMs: performance.now() - start };
  }
}

async function run(sample: boolean): Promise<void> {
  if (busy) return;
  const token = ++generation;
  busy = true; updateButtons(); get<HTMLInputElement>('reviewed').checked = false;
  get<HTMLProgressElement>('progress').value = 0;
  text('download-progress', ''); text('save-status', '');
  let modelMetrics: any;
  const started = performance.now();
  try {
    const file = sample ? new File([await (await fetch(new URL('samples/chinese.wav', baseUrl))).arrayBuffer()], '免费中文短样例.wav', { type: 'audio/wav' }) : currentFile;
    if (token !== generation) return;
    if (!file) throw new PrototypeError('NO_FILE', '请先选择文件。');
    if (file.size > LIMITS.maxFileBytes) throw new PrototypeError('SIZE_LIMIT', `文件超过 ${LIMITS.maxFileBytes / 1048576} MiB 原型限制。`);
    task = { schemaVersion: '1.0', taskId: crypto.randomUUID(), title: file.name.replace(/\.[^.]+$/, ''), language: 'zh', state: 'running', segments: [] };
    get<HTMLInputElement>('title').value = task.title; renderSegments();
    if ('wakeLock' in navigator) {
      try {
        const lock = await (navigator as any).wakeLock.request('screen');
        if (token !== generation) { await lock.release(); return; }
        wake = lock;
        lock.addEventListener('release', () => { if (busy && token === generation) text('wake-status', '屏幕常亮已失效，请自行保持屏幕开启和页面在前台。'); });
        text('wake-status', '已申请屏幕常亮，请保持页面在前台。');
      }
      catch { text('wake-status', '屏幕常亮申请未成功，请自行保持屏幕开启。'); }
    } else text('wake-status', '此浏览器不提供屏幕常亮，请自行保持屏幕开启。');
    const backends: Backend[] = ['wasm'];
    for (const [attempt, backend] of backends.entries()) {
      if (token !== generation) return;
      try {
        text('status', '正在读取本地音轨…');
        const decoded = await decode(file, token);
        if (token !== generation) return;
        text('status', `正在加载并校验 ${manifest.model}，首次使用需要下载…`);
        const modelProfile = get<HTMLSelectElement>('model-profile').value as ModelProfile;
        await client.call('prepare', { backend, modelProfile }, event => {
          if (event.type === 'model-progress') text('download-progress', `本次下载 ${(event.received / 1048576).toFixed(1)} MiB；缓存命中 ${(event.cachedBytes / 1048576).toFixed(1)} MiB；已校验 ${(event.verifiedBytes / 1048576).toFixed(1)} / ${(event.total / 1048576).toFixed(1)} MiB。`);
          if (event.type === 'cache-warning') { text('compat-result', event.message); report.errors.push({ code: event.code ?? 'CACHE_REPAIRED', phase: 'cache' }); }
          if (event.type === 'model-ready') modelMetrics = event;
        });
        if (token !== generation) return;
        text('status', `正在设备上识别（${backend === 'webgpu' ? '加速模式' : '兼容模式'}），请保持前台…`);
        const result = await client.call('infer', { backend, modelProfile, pcm: decoded.pcm }, event => {
          if (token === generation && event.type === 'partial' && task) { task.segments = event.segments; renderSegments(); get<HTMLProgressElement>('progress').value = event.progress; }
        }, [decoded.pcm.buffer]);
        if (token !== generation) return;
        if (sample && !result.segments.some((segment: any) => /[\u3400-\u9fff]/.test(segment.text))) throw new PrototypeError('SAMPLE_INVALID', '短中文样例没有产生有效中文候选，此模式未通过测试。');
        task.segments = result.segments; task.state = result.state;
        renderSegments(); get<HTMLProgressElement>('progress').value = 1;
        text('status', result.state === 'no_speech' ? '近静音音频，文案留空。' : `已生成 ${result.segments.length} 段候选口播，请校对后保存。`);
        text('result-warning', result.note + ' BGM、噪声和纯音乐可能产生幻觉，可手动确认无口播并清空。');
        if (sample) {
          samplePassed = Boolean(result.segments.length);
          report.samples.push({ success: samplePassed, backend, model: modelMetrics, durationSeconds: result.duration, decodeMs: decoded.decodeMs, inferenceMs: result.inferenceMs, totalMs: performance.now() - started });
          text('compat-result', samplePassed ? `短样例已在本设备的${backend === 'webgpu' ? '加速' : '兼容'}模式完成。只证明这次短样例可运行，请校对质量；不代表所有文件或手机兼容。` : '未得到有效中文口播，样例测试未通过，请更换模式或系统浏览器。');
        }
        break;
      } catch (error) {
        if (token !== generation) return;
        const code = (error as PrototypeError).code ?? 'ENGINE_FAILURE';
        if (backend === 'webgpu' && attempt + 1 < backends.length && ['GPU_UNAVAILABLE', 'ENGINE_FAILURE', 'ENGINE_LOAD_FAILED', 'SAMPLE_INVALID'].includes(code)) {
          report.errors.push({ code, phase: 'webgpu-fallback' });
          text('compat-result', '加速模式未通过实际运行，正在用新 Worker 尝试兼容模式。');
          client.restart('BACKEND_RETRY'); continue;
        }
        throw error;
      }
    }
  } catch (error) {
    if (token !== generation) return;
    const failure = error as PrototypeError, code = failure.code ?? 'ENGINE_FAILURE';
    if (task) { task.state = 'failed'; task.error = { code, message: failure.message }; }
    report.errors.push({ code, phase: sample ? 'sample' : 'local-file', detail: failure.detail });
    text('status', `${code}：${failure.message}`);
    if (sample) { samplePassed = false; report.samples.push({ success: false, errorCode: code, totalMs: performance.now() - started }); text('compat-result', '样例未通过。可重试、选择 small 模型，或复制链接到系统浏览器打开。'); }
    client.restart('FAILED_RETRY');
  } finally {
    if (token === generation) { busy = false; await releaseWake(); updateButtons(); }
  }
}
