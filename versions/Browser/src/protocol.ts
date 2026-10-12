import { toSimplified } from './chinese.ts';
export interface Segment { start: number; end: number; text: string }

// An explicit BOM helps Android/Windows viewers distinguish UTF-8 from legacy encodings.
export function txtForDownload(segments: Segment[]): string {
  return '\uFEFF' + segments.map(s => toSimplified(s.text).replace(/\r?\n/g, '\r\n')).join('\r\n');
}
export interface Task {
  schemaVersion: '1.0'; taskId: string; title: string; language: 'zh' | 'auto';
  state: 'ready' | 'running' | 'needs_review' | 'completed' | 'no_speech' | 'canceled' | 'failed';
  segments: Segment[]; error?: { code: string; message: string };
}

export function cleanSegments(segments: Segment[], duration: number): Segment[] {
  let previous = 0;
  return segments.flatMap(s => {
    const start = Math.max(previous, s.start, 0);
    const end = Math.min(duration, s.end);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start || !s.text.trim()) return [];
    previous = end;
    return [{ start, end, text: toSimplified(s.text.trim()) }];
  });
}

export function timestamp(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) throw new Error('字幕时间无效');
  const ms = Math.round(seconds * 1000);
  return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms / 60000) % 60).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`;
}

export function toSrt(segments: Segment[]): string {
  return segments.map((s, i) => {
    if (!s.text.trim() || s.end <= s.start) throw new Error('请填写有效文字与起止时间');
    return `${i + 1}\n${timestamp(s.start)} --> ${timestamp(s.end)}\n${toSimplified(s.text.trim())}\n`;
  }).join('\n');
}

export function safeFilename(title: string): string {
  return title.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').replace(/[. ]+$/g, '').slice(0, 80) || '文案';
}

// Only remove repeated boundary text when timestamps also overlap.
export function appendChunk(existing: Segment[], incoming: Segment[]): Segment[] {
  const output = existing.map(s => ({ ...s, text: toSimplified(s.text) }));
  for (const segment of incoming) {
    const last = output.at(-1);
    let { start, end, text } = segment;
    text = toSimplified(text);
    if (last && start < last.end) {
      if (last.text === text && end <= last.end + 2) continue;
      for (let n = Math.min(last.text.length, text.length); n >= 2; n--) {
        if (last.text.slice(-n) === text.slice(0, n)) { text = text.slice(n); break; }
      }
      start = last.end;
    }
    if (end > start && text.trim()) output.push({ start, end, text: text.trim() });
  }
  return output;
}
