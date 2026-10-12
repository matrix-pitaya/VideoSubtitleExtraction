import { LIMITS } from './config.ts';
import { PrototypeError, checkDuration, checkAudioMemory } from './audio.ts';

export async function nativeDecode(file: File): Promise<Float32Array> {
  const url = URL.createObjectURL(file), media = document.createElement('audio');
  media.preload = 'metadata';
  try {
    const duration = await new Promise<number>((resolve, reject) => {
      const timer = setTimeout(() => reject(new PrototypeError('DECODE_FAILED', '无法读取音频时长，请使用标准 WAV 或系统浏览器重试。')), 10_000);
      media.onloadedmetadata = () => { clearTimeout(timer); resolve(media.duration); };
      media.onerror = () => { clearTimeout(timer); reject(new PrototypeError('FORMAT_UNSUPPORTED', '当前浏览器无法读取这个媒体文件。')); };
      media.src = url;
    });
    checkDuration(duration);
    checkAudioMemory(duration, LIMITS.sampleRate, 2, 2);
    const Audio = window.AudioContext ?? (window as any).webkitAudioContext;
    if (!Audio) throw new PrototypeError('DECODER_UNAVAILABLE', '当前浏览器缺少系统音频解码。');
    const context: AudioContext = new Audio({ sampleRate: LIMITS.sampleRate });
    try {
      const decoded = await context.decodeAudioData(await file.arrayBuffer());
      checkDuration(decoded.duration);
      checkAudioMemory(decoded.duration, decoded.sampleRate, decoded.numberOfChannels, 2);
      if (decoded.numberOfChannels > 2 || decoded.sampleRate > 48000) throw new PrototypeError('FORMAT_UNSUPPORTED', '原型限制为双声道以内、48kHz 以内的音频。');
      const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * LIMITS.sampleRate), LIMITS.sampleRate);
      const source = offline.createBufferSource(); source.buffer = decoded; source.connect(offline.destination); source.start();
      return (await offline.startRendering()).getChannelData(0).slice();
    } finally { await context.close(); }
  } finally { media.removeAttribute('src'); media.load(); URL.revokeObjectURL(url); }
}
