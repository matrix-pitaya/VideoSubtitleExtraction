import { PrototypeError } from './audio.ts';

export class WorkerClient {
  private worker!: Worker;
  private id = 0;
  private pending = new Map<number, { resolve: (value: any) => void; reject: (error: Error) => void; notify?: (event: any) => void }>();
  constructor() { this.spawn(); }
  private spawn(): void {
    this.worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' });
    this.worker.onmessage = ({ data }) => {
      const request = this.pending.get(data.id);
      if (!request) return;
      if (data.type === 'done') { this.pending.delete(data.id); request.resolve(data.result); }
      else if (data.type === 'error') {
        this.pending.delete(data.id);
        const failure = new PrototypeError(data.code, data.message);
        if (typeof data.detail === 'string') failure.detail = data.detail;
        request.reject(failure);
      }
      else request.notify?.(data);
    };
    this.worker.onerror = () => this.rejectAll('ENGINE_LOAD_FAILED');
  }
  private rejectAll(code: string): void {
    for (const request of this.pending.values()) request.reject(new PrototypeError(code, '浏览器 Worker 中断，请重试或换用系统浏览器。'));
    this.pending.clear();
  }
  restart(code = 'CANCELED'): void { this.worker.terminate(); this.rejectAll(code); this.spawn(); }
  close(): void { this.worker.terminate(); this.rejectAll('CANCELED'); }
  call(type: string, values: Record<string, unknown> = {}, notify?: (event: any) => void, transfer: Transferable[] = []): Promise<any> {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, notify });
      this.worker.postMessage({ id, type, baseUrl: new URL('./', location.href).href, ...values }, transfer);
    });
  }
}
