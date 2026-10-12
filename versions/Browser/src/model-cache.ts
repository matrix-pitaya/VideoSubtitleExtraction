import { env, pipeline, type AutomaticSpeechRecognitionPipeline } from '@huggingface/transformers';
import { MODELS, type ModelProfile } from './models.ts';
import type { Backend } from './config.ts';
import { PrototypeError } from './audio.ts';
import { openAssetStore, ModelBytesResponse, type AssetStore } from './asset-store.ts';

let manifest = MODELS.small;
export let CACHE_NAME = `vse-${manifest.model}-${manifest.revision}`;
export type Notify = (event: Record<string, unknown>) => void;
let recognizer: AutomaticSpeechRecognitionPipeline | undefined;
let activeBackend: Backend | undefined;
let assetBase = new URL('/', self.location.href).href;

export function setModel(profile: ModelProfile = 'small'): void {
  if (!Object.hasOwn(MODELS, profile)) throw new PrototypeError('MODEL_UNKNOWN', '请选择已固定版本的模型。');
  if (recognizer && manifest.model !== MODELS[profile].model) throw new PrototypeError('MODEL_CHANGED', '切换模型需要重新创建 Worker。');
  manifest = MODELS[profile];
  CACHE_NAME = `vse-${manifest.model}-${manifest.revision}`;
}

export function setAssetBase(url: string): void {
  const parsed = new URL(url);
  if (parsed.origin !== self.location.origin || !parsed.pathname.endsWith('/')) throw new PrototypeError('ASSET_ORIGIN', '资源目录必须位于本站。');
  assetBase = parsed.href;
}

function urlFor(path: string): string {
  return new URL(`models/${manifest.model}/${path}`, assetBase).href;
}

export async function prepare(backend: Backend, notify: Notify): Promise<AutomaticSpeechRecognitionPipeline> {
  if (recognizer && activeBackend === backend) {
    notify({ type: 'model-ready', modelName: manifest.model, backend, loadMs: 0, cachedBytes: 0, downloadedBytes: 0, totalBytes: manifest.totalBytes, revision: manifest.revision, storage: 'loaded-engine', reused: true });
    return recognizer;
  }
  if (!self.isSecureContext || !crypto.subtle) throw new PrototypeError('HTTPS_REQUIRED', '此原型需要可信 HTTPS 或本机 localhost，请勿忽略证书错误。');
  if (recognizer) { await recognizer.dispose(); recognizer = undefined; }
  const memory = new Map<string, Response>();
  let cache: AssetStore | undefined;
  try { cache = await openAssetStore(CACHE_NAME); } catch { notify({ type: 'cache-warning', code: 'CACHE_UNAVAILABLE', message: '浏览器缓存不可用，本次仍会尝试运行，下次可能需要重新下载模型。' }); }
  const started = performance.now();
  let cachedBytes = 0, downloadedBytes = 0, verifiedBytes = 0;
  for (const file of manifest.files) {
    const url = urlFor(file.path);
    let response: Response | undefined;
    try { response = await cache?.match(url); }
    catch { cache = undefined; notify({ type: 'cache-warning', code: 'CACHE_READ_FAILED', message: '缓存读取失败，本次重新下载并在内存中运行。' }); }
    let buffer: ArrayBuffer | undefined;
    if (response) {
      buffer = await response.arrayBuffer();
      if (buffer.byteLength !== file.bytes || await sha256(buffer) !== file.sha256) {
        try { await cache?.delete(url); } catch { /* invalid bytes are never loaded */ }
        buffer = undefined;
        notify({ type: 'cache-warning', message: '模型缓存校验失败，正在重新下载该文件。' });
      } else cachedBytes += file.bytes;
    }
    if (!buffer) {
      response = await fetch(url, { cache: 'no-store', credentials: 'omit' });
      if (!response.ok || !response.body) throw new PrototypeError('MODEL_MISSING', '模型文件不可用。请让维护者检查此原型的静态模型资源。');
      const reader = response.body.getReader();
      const joined = new Uint8Array(file.bytes);
      let received = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        received += value.length;
        if (received > file.bytes) { await reader.cancel(); throw new PrototypeError('MODEL_INTEGRITY', '模型文件大小与固定版本不一致。'); }
        joined.set(value, received - value.length);
        notify({ type: 'model-progress', file: file.path, received: downloadedBytes + received, total: manifest.totalBytes, cachedBytes, verifiedBytes });
      }
      buffer = joined.buffer;
      if (received !== file.bytes || await sha256(buffer) !== file.sha256) throw new PrototypeError('MODEL_INTEGRITY', '模型 SHA256 校验失败，未加载此文件。请重试或联系维护者。');
      downloadedBytes += received;
      response = new ModelBytesResponse(buffer);
      if (cache) {
        try { await cache.put(url, response.clone()); }
        catch { notify({ type: 'cache-warning', code: 'CACHE_WRITE_FAILED', message: '缓存写入失败或配额不足，模型本次在内存中运行；下次可能重新下载。' }); memory.set(url, response); }
      } else memory.set(url, response);
    }
    // Pipeline only sees the bytes verified in this run, even if storage changes mid-load.
    memory.set(url, new ModelBytesResponse(buffer));
    verifiedBytes += file.bytes;
    notify({ type: 'model-progress', file: file.path, received: downloadedBytes, total: manifest.totalBytes, cachedBytes, verifiedBytes });
  }
  env.allowRemoteModels = false;
  env.allowLocalModels = true;
  env.localModelPath = new URL('models/', assetBase).href;
  env.useBrowserCache = false;
  env.useFSCache = false;
  env.useCustomCache = true;
  env.customCache = {
    async match(request: string | Request) {
      const url = new URL(typeof request === 'string' ? request : request.url, assetBase).href;
      // Only files checked against the immutable manifest are eligible for inference.
      if (!manifest.files.some(file => urlFor(file.path) === url)) return undefined;
      return memory.get(url)?.clone();
    },
    async put() { /* verified files were inserted above; do not accept arbitrary model writes */ },
  };
  const wasm = env.backends.onnx.wasm;
  if (!wasm) throw new PrototypeError('ENGINE_FAILURE', 'WASM 引擎配置不可用。');
  wasm.wasmPaths = new URL('runtime/', assetBase).href;
  wasm.numThreads = 1;
  wasm.proxy = false;
  const createPipeline = pipeline as unknown as (task: string, model: string, options: Record<string, unknown>) => Promise<AutomaticSpeechRecognitionPipeline>;
  recognizer = await createPipeline('automatic-speech-recognition', manifest.model, { device: backend, dtype: 'q8', local_files_only: true });
  // These conversions also expose every encoder attention matrix. Transcription
  // consumes only last_hidden_state; fetching unused matrices can exhaust WASM memory.
  const encoder = (recognizer.model as any).sessions?.model;
  if (encoder?.outputNames?.includes('last_hidden_state') && encoder.outputNames.length > 1) {
    const runEncoder = encoder.run.bind(encoder);
    encoder.run = (feeds: Record<string, unknown>) => runEncoder(feeds, ['last_hidden_state']);
  }
  activeBackend = backend;
  memory.clear();
  notify({ type: 'model-ready', modelName: manifest.model, backend, loadMs: performance.now() - started, cachedBytes, downloadedBytes, totalBytes: manifest.totalBytes, revision: manifest.revision, storage: cache?.kind ?? 'memory' });
  return recognizer;
}

export async function sha256(buffer: ArrayBuffer): Promise<string> {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', buffer)), n => n.toString(16).padStart(2, '0')).join('');
}
