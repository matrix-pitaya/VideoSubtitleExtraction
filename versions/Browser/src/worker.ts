/// <reference lib="webworker" />
import { decodeWav, decodeMp4, isSilent, checkDuration, PrototypeError } from './audio.ts';
import { LIMITS, type Backend } from './config.ts';
import { prepare, setAssetBase, setModel } from './model-cache.ts';
import { appendChunk, cleanSegments, type Segment } from './protocol.ts';

let busy = false;
self.onmessage = async event => {
  const { id, type, backend, buffer, extension, pcm } = event.data;
  const notify = (payload: Record<string, unknown>) => self.postMessage({ id, ...payload });
  if (busy) { notify({ type: 'error', code: 'BUSY', message: '已有任务正在运行。' }); return; }
  busy = true;
  try {
    setAssetBase(event.data.baseUrl);
    setModel(event.data.modelProfile ?? 'small');
    if (['prepare', 'infer'].includes(type) && backend !== 'wasm') throw new PrototypeError('MODE_UNSUPPORTED', '当前版本仅启用兼容模式（WASM）。');
    if (type === 'probe') {
      notify({ type: 'done', result: { secureContext: self.isSecureContext, webgpu: false, webgpuEnabled: false, wasm: typeof WebAssembly !== 'undefined', audioDecoder: typeof AudioDecoder !== 'undefined', worker: true } });
    } else if (type === 'prepare') {
      await prepare(backend as Backend, notify);
      notify({ type: 'done', result: { backend } });
    } else if (type === 'decode') {
      const start = performance.now();
      if (buffer.byteLength > LIMITS.maxFileBytes) throw new PrototypeError('SIZE_LIMIT', '文件超过原型体积限制。');
      const audio = extension === 'wav' ? decodeWav(buffer) : ['mp4', 'mov', 'm4a'].includes(extension) ? await decodeMp4(buffer) : undefined;
      if (!audio && extension !== 'mp3') throw new PrototypeError('FORMAT_UNSUPPORTED', '原型仅接受 WAV、MP3、MP4、MOV 和 M4A。');
      if (!audio) throw new PrototypeError('NATIVE_AUDIO_REQUIRED', '尝试系统音频解码。');
      self.postMessage({ id, type: 'done', result: { pcm: audio, decodeMs: performance.now() - start } }, { transfer: [audio.buffer] });
    } else if (type === 'infer') {
      const audio = pcm as Float32Array;
      const duration = audio.length / LIMITS.sampleRate;
      checkDuration(duration);
      const started = performance.now();
      if (isSilent(audio)) {
        notify({ type: 'done', result: { segments: [], state: 'no_speech', duration, inferenceMs: 0, backend, note: '仅检测到近静音；无口播留空。' } });
      } else {
        const recognizer = await prepare(backend, notify);
        let segments: Segment[] = [];
        const step = LIMITS.chunkSeconds - LIMITS.overlapSeconds;
        for (let start = 0; start < duration; start += step) {
          const end = Math.min(duration, start + LIMITS.chunkSeconds);
          const chunk = audio.subarray(Math.floor(start * LIMITS.sampleRate), Math.floor(end * LIMITS.sampleRate));
          if (isSilent(chunk)) {
            notify({ type: 'partial', segments, progress: end / duration });
            if (end === duration) break;
            continue;
          }
          const result: any = await recognizer(chunk, { language: 'chinese', task: 'transcribe', return_timestamps: true, max_new_tokens: 128, num_beams: 1, do_sample: false });
          const incoming = (result.chunks?.length ? result.chunks : [{ timestamp: [0, end - start], text: result.text }]).map((s: any) => ({ start: start + (s.timestamp?.[0] ?? 0), end: start + (s.timestamp?.[1] ?? end - start), text: String(s.text ?? '').trim() }));
          segments = cleanSegments(appendChunk(segments, incoming), duration);
          notify({ type: 'partial', segments, progress: end / duration });
          if (end === duration) break;
        }
        notify({ type: 'done', result: { segments, state: 'needs_review', duration, inferenceMs: performance.now() - started, backend, note: '候选文案需人工校对；此原型不可靠区分 BGM 与口播。' } });
      }
    }
  } catch (error) {
    const failure = error as Error;
    notify({ type: 'error', code: error instanceof PrototypeError ? error.code : 'ENGINE_FAILURE', message: error instanceof PrototypeError ? error.message : '本地识别失败，可能是可用内存不足或运行组件加载失败。请重试、换用 small 模型或在系统浏览器打开。', detail: failure.message });
  } finally { busy = false; }
};
