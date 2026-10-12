export interface AssetStore {
  kind: string;
  match(url: string): Promise<Response | undefined>;
  put(url: string, response: Response): Promise<void>;
  delete(url: string): Promise<void>;
}

// Internal, read-only model bytes. Transformers consumes arrayBuffer once; avoid
// duplicating gigabyte tensors in Response bodies before copying them into WASM.
export class ModelBytesResponse extends Response {
  private readonly modelBuffer: ArrayBuffer;
  constructor(modelBuffer: ArrayBuffer) { super(null); this.modelBuffer = modelBuffer; }
  override async arrayBuffer(): Promise<ArrayBuffer> { return this.modelBuffer; }
  override clone(): Response { return new ModelBytesResponse(this.modelBuffer); }
}

// IndexedDB works in Workers without requiring a service worker. Cache API is a fallback.
export async function openAssetStore(namespace: string): Promise<AssetStore> {
  try {
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open('VideoSubtitleExtraction-models', 1);
      const timer = setTimeout(() => reject(new Error('StorageUnavailable')), 3000);
      request.onupgradeneeded = () => { if (!request.result.objectStoreNames.contains('files')) request.result.createObjectStore('files'); };
      request.onsuccess = () => { clearTimeout(timer); resolve(request.result); };
      request.onerror = () => { clearTimeout(timer); reject(request.error); };
      request.onblocked = () => { clearTimeout(timer); reject(new Error('StorageBlocked')); };
    });
    const key = (url: string) => `${namespace}|${url}`;
    const read = (assetKey: string): Promise<any> => new Promise((resolve, reject) => {
      const request = database.transaction('files', 'readonly').objectStore('files').get(assetKey);
      request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
    });
    const chunkBytes = 32 * 1024 * 1024;
    return {
      kind: 'indexeddb',
      async match(url) {
        const stored = await read(key(url));
        if (!stored) return undefined;
        if (stored instanceof ArrayBuffer) return new ModelBytesResponse(stored);
        if (!Number.isSafeInteger(stored.bytes) || stored.bytes <= 0 || stored.bytes > 1024 * 1024 * 1024 || stored.chunks !== Math.ceil(stored.bytes / chunkBytes)) throw new Error('InvalidCacheManifest');
        const joined = new Uint8Array(stored.bytes);
        for (let i = 0; i < stored.chunks; i++) {
          const part = await read(`${key(url)}#${i}`);
          if (!(part instanceof ArrayBuffer) || part.byteLength !== Math.min(chunkBytes, stored.bytes - i * chunkBytes)) throw new Error('IncompleteCache');
          joined.set(new Uint8Array(part), i * chunkBytes);
        }
        return new ModelBytesResponse(joined.buffer);
      },
      async put(url, response) {
        const buffer = await response.arrayBuffer();
        const write = (value: unknown, assetKey: string) => new Promise<void>((resolve, reject) => {
          const transaction = database.transaction('files', 'readwrite');
          const store = transaction.objectStore('files');
          store.put(value, assetKey);
          transaction.oncomplete = () => resolve();
          transaction.onerror = () => reject(transaction.error);
          transaction.onabort = () => reject(transaction.error ?? new Error('StorageAborted'));
        });
        if (buffer.byteLength <= chunkBytes) await write(buffer, key(url));
        else {
          // Commit each chunk separately, then publish metadata only after all
          // writes succeed. Interrupted writes never expose a complete model.
          const chunks = Math.ceil(buffer.byteLength / chunkBytes);
          await new Promise<void>((resolve, reject) => {
            const transaction = database.transaction('files', 'readwrite');
            transaction.objectStore('files').delete(key(url));
            transaction.oncomplete = () => resolve();
            transaction.onabort = transaction.onerror = () => reject(transaction.error);
          });
          for (let i = 0; i < chunks; i++) await write(buffer.slice(i * chunkBytes, (i + 1) * chunkBytes), `${key(url)}#${i}`);
          await write({ bytes: buffer.byteLength, chunks }, key(url));
        }
      },
      async delete(url) {
        await new Promise<void>((resolve, reject) => {
          const transaction = database.transaction('files', 'readwrite');
          const store = transaction.objectStore('files'), request = store.get(key(url));
          request.onsuccess = () => {
            const stored = request.result;
            if (stored && !(stored instanceof ArrayBuffer) && Number.isSafeInteger(stored.chunks) && stored.chunks <= 32) for (let i = 0; i < stored.chunks; i++) store.delete(`${key(url)}#${i}`);
            store.delete(key(url));
          };
          transaction.oncomplete = () => resolve(); transaction.onerror = () => reject(transaction.error);
        });
      },
    };
  } catch {
    const cache = await caches.open(namespace);
    return { kind: 'cache-api', match: url => cache.match(url), async put(url, response) { await cache.put(url, new Response(await response.arrayBuffer())); }, async delete(url) { await cache.delete(url); } };
  }
}
