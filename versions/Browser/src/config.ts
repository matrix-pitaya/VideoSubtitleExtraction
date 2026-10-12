export const LIMITS = Object.freeze({ maxFileBytes: 100 * 1024 * 1024, maxDecodedBytes: 128 * 1024 * 1024, sampleRate: 16_000, chunkSeconds: 20, overlapSeconds: 2 });
export type Backend = 'wasm' | 'webgpu';
export type Mode = Backend | 'auto';
