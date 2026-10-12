import { createFile } from 'mp4box';
import { LIMITS } from './config.ts';

export class PrototypeError extends Error {
  code: string;
  detail?: string;
  constructor(code: string, message: string) { super(message); this.code = code; }
}

export function checkDuration(seconds: number): void {
  if (!Number.isFinite(seconds) || seconds <= 0) throw new PrototypeError('MEDIA_INVALID', '没有可用音频，或媒体时长无效。');
}

export function checkAudioMemory(seconds: number, rate: number, channels = 1, copies = 1): void {
  checkDuration(seconds);
  const bytes = seconds * 4 * (rate * channels * copies + LIMITS.sampleRate);
  if (!Number.isFinite(bytes) || bytes > LIMITS.maxDecodedBytes) throw new PrototypeError('MEMORY_LIMIT', '音频解码预计超过本设备原型的内存预算，请分段导入或使用电脑程序。没有固定的 60 秒限制。');
}

// Keep absolute sample phase and a small lookahead across decoder packets, avoiding drift.
export class StreamingResampler {
  private tail = new Float32Array(0);
  private total = 0;
  private emitted = 0;
  private rate: number;
  private target: number;
  constructor(rate: number, target = LIMITS.sampleRate) { this.rate = rate; this.target = target; }
  push(input: Float32Array, final = false): Float32Array {
    if (this.rate === this.target) return input;
    const start = this.total - this.tail.length;
    const data = new Float32Array(this.tail.length + input.length);
    data.set(this.tail); data.set(input, this.tail.length); this.total += input.length;
    const count = Math.max(0, Math.floor((final ? this.total : Math.max(0, this.total - 17)) * this.target / this.rate));
    const output = new Float32Array(Math.max(0, count - this.emitted));
    const cutoff = Math.min(1, this.target / this.rate) * 0.94;
    for (let n = 0; n < output.length; n++) {
      const position = (this.emitted + n) * this.rate / this.target;
      let sum = 0, weight = 0;
      for (let k = -16; k <= 16; k++) {
        const index = Math.floor(position) + k;
        if (index < 0 || index >= this.total || index < start) continue;
        const distance = position - index, x = Math.PI * distance * cutoff;
        const w = (x === 0 ? 1 : Math.sin(x) / x) * (0.5 + 0.5 * Math.cos(Math.PI * distance / 17));
        sum += data[index - start] * w; weight += w;
      }
      output[n] = weight ? sum / weight : 0;
    }
    this.emitted = count; this.tail = data.slice(-34); return output;
  }
}

export function resampleMono(input: Float32Array, sourceRate: number, targetRate = LIMITS.sampleRate): Float32Array {
  if (sourceRate === targetRate) return input;
  const output = new Float32Array(Math.floor(input.length * targetRate / sourceRate));
  const ratio = sourceRate / targetRate;
  const cutoff = Math.min(1, targetRate / sourceRate) * 0.94;
  for (let n = 0; n < output.length; n++) {
    const position = n * ratio;
    let total = 0, weight = 0;
    for (let k = -16; k <= 16; k++) {
      const index = Math.floor(position) + k;
      if (index < 0 || index >= input.length) continue;
      const distance = position - index;
      const x = Math.PI * distance * cutoff;
      const w = (x === 0 ? 1 : Math.sin(x) / x) * (0.5 + 0.5 * Math.cos(Math.PI * distance / 17));
      total += input[index] * w;
      weight += w;
    }
    output[n] = weight ? total / weight : 0;
  }
  return output;
}

export function decodeWav(buffer: ArrayBuffer): Float32Array {
  const view = new DataView(buffer);
  const ascii = (offset: number, length: number) => String.fromCharCode(...new Uint8Array(buffer, offset, length));
  if (buffer.byteLength < 44 || ascii(0, 4) !== 'RIFF' || ascii(8, 4) !== 'WAVE') throw new PrototypeError('MEDIA_INVALID', 'WAV 文件损坏或不是标准 RIFF/WAVE。');
  let format = 0, channels = 0, rate = 0, bits = 0, offset = 0, size = 0;
  for (let p = 12; p + 8 <= buffer.byteLength;) {
    const name = ascii(p, 4), length = view.getUint32(p + 4, true), next = p + 8 + length;
    if (next > buffer.byteLength) throw new PrototypeError('MEDIA_INVALID', 'WAV 数据块不完整。');
    if (name === 'fmt ' && length >= 16) {
      format = view.getUint16(p + 8, true); channels = view.getUint16(p + 10, true);
      rate = view.getUint32(p + 12, true); bits = view.getUint16(p + 22, true);
      if (format === 65534 && length >= 40) format = view.getUint16(p + 32, true);
    }
    if (name === 'data' && !size) { offset = p + 8; size = length; }
    p = next + (length % 2);
  }
  if (!(channels > 0 && channels <= 2 && rate >= 8000 && rate <= 48000 && size)) throw new PrototypeError('FORMAT_UNSUPPORTED', '原型 WAV 限制为双声道以内、8–48kHz 的标准音轨。');
  if ((format !== 1 && format !== 3) || ![8, 16, 24, 32].includes(bits) || (format === 3 && bits !== 32)) throw new PrototypeError('FORMAT_UNSUPPORTED', '仅支持 PCM 8/16/24/32 位或浮点 32 位 WAV。');
  const bytes = bits / 8, frames = Math.floor(size / (bytes * channels));
  checkDuration(frames / rate);
  checkAudioMemory(frames / rate, rate);
  const pcm = new Float32Array(frames);
  for (let i = 0; i < frames; i++) {
    let sample = 0;
    for (let c = 0; c < channels; c++) {
      const p = offset + (i * channels + c) * bytes;
      let value = format === 3 ? view.getFloat32(p, true) : bits === 8 ? (view.getUint8(p) - 128) / 128 : bits === 16 ? view.getInt16(p, true) / 32768 : bits === 32 ? view.getInt32(p, true) / 2147483648 : ((view.getUint8(p) | view.getUint8(p + 1) << 8 | view.getInt8(p + 2) << 16) / 8388608);
      if (!Number.isFinite(value)) throw new PrototypeError('MEDIA_INVALID', 'WAV 包含无效采样值。');
      sample += Math.max(-1, Math.min(1, value));
    }
    pcm[i] = sample / channels;
  }
  return resampleMono(pcm, rate);
}

export function isSilent(pcm: Float32Array): boolean {
  let energy = 0, peak = 0;
  for (const sample of pcm) { energy += sample * sample; peak = Math.max(peak, Math.abs(sample)); }
  return peak < 0.003 && Math.sqrt(energy / Math.max(1, pcm.length)) < 0.0006;
}

interface AudioSample { data: Uint8Array; cts: number; duration: number; timescale: number }

export async function decodeMp4(buffer: ArrayBuffer): Promise<Float32Array> {
  const file = createFile();
  const samples: AudioSample[] = [];
  let track: any;
  let parsingError: string | undefined;
  let durationError: Error | undefined;
  file.onError = error => { parsingError = String(error); };
  file.onReady = info => {
    try { checkDuration(info.duration / info.timescale); }
    catch (error) { durationError = error as Error; return; }
    track = info.audioTracks[0];
    if (track) {
      file.setExtractionOptions(track.id, null, { nbSamples: 1000 });
      file.start();
    }
  };
  file.onSamples = (_id, _user, extracted) => { samples.push(...extracted as AudioSample[]); };
  const data = buffer as ArrayBuffer & { fileStart: number };
  data.fileStart = 0;
  try { file.appendBuffer(data); file.flush(); } catch { throw new PrototypeError('MEDIA_INVALID', 'MP4/MOV 数据损坏或无法解复用。'); }
  if (durationError) throw durationError;
  if (parsingError || !track) {
    let hasTracks = false;
    try { hasTracks = Boolean(file.getInfo().tracks.length); } catch { /* incomplete movie metadata */ }
    if (!parsingError && hasTracks) throw new PrototypeError('NO_AUDIO', '这个视频没有音轨。');
    throw new PrototypeError('MEDIA_INVALID', 'MP4/MOV 数据损坏或找不到音轨。');
  }
  checkDuration(track.duration / track.timescale);
  checkAudioMemory(track.duration / track.timescale, LIMITS.sampleRate);
  if (track.codec !== 'mp4a.40.2') throw new PrototypeError('FORMAT_UNSUPPORTED', `此音轨是 ${track.codec}。当前原型仅测试 AAC-LC 音轨；请转为 WAV 或 MP3 后重试。`);
  if (track.audio.sample_rate > 48000 || track.audio.channel_count > 2) throw new PrototypeError('FORMAT_UNSUPPORTED', '原型 AAC 限制为双声道以内、48kHz 以内，避免过大的解码内存。');
  if (typeof AudioDecoder === 'undefined') throw new PrototypeError('DECODER_UNAVAILABLE', '当前浏览器缺少音频解码接口，请用系统浏览器重试，或先转成 WAV/MP3。');
  const frequencies = [96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350];
  const sampleRate = track.audio.sample_rate, channels = track.audio.channel_count;
  const index = frequencies.indexOf(sampleRate);
  if (index < 0 || channels < 1 || channels > 7) throw new PrototypeError('FORMAT_UNSUPPORTED', '此 AAC 音轨采样率或声道布局暂不支持。');
  const asc = (2 << 11) | (index << 7) | (channels << 3);
  const config = { codec: 'mp4a.40.2', sampleRate, numberOfChannels: channels, description: new Uint8Array([asc >> 8, asc & 255]) };
  if (!(await AudioDecoder.isConfigSupported(config)).supported) throw new PrototypeError('DECODER_UNAVAILABLE', '这个浏览器无法解码 AAC 音轨，请用系统浏览器或 WAV 文件重试。');
  const frames: Float32Array[] = [];
  let outputRate = sampleRate, decodingError: Error | undefined, totalFrames = 0;
  let resampler: StreamingResampler | undefined;
  const decoder = new AudioDecoder({
    output(frame) {
      try {
        outputRate = frame.sampleRate;
        if (!resampler) resampler = new StreamingResampler(outputRate);
        if (frame.sampleRate !== sampleRate || frame.numberOfChannels > 2) throw new PrototypeError('FORMAT_UNSUPPORTED', '音轨解码参数与声明不一致。');
        const mono = new Float32Array(frame.numberOfFrames), channel = new Float32Array(frame.numberOfFrames);
        for (let c = 0; c < frame.numberOfChannels; c++) {
          frame.copyTo(channel, { planeIndex: c, format: 'f32-planar' });
          for (let i = 0; i < mono.length; i++) mono[i] += channel[i] / frame.numberOfChannels;
        }
        const reduced = resampler.push(mono);
        totalFrames += reduced.length;
        checkAudioMemory(totalFrames / LIMITS.sampleRate, LIMITS.sampleRate);
        frames.push(reduced);
      } catch (error) { decodingError = error as Error; } finally { frame.close(); }
    },
    error(error) { decodingError = error; },
  });
  try {
    decoder.configure(config);
    for (const sample of samples) {
      decoder.decode(new EncodedAudioChunk({ type: 'key', timestamp: Math.round(sample.cts / sample.timescale * 1e6), duration: Math.round(sample.duration / sample.timescale * 1e6), data: sample.data }));
      if (decoder.decodeQueueSize > 16) await decoder.flush();
      if (decodingError) throw decodingError;
    }
    await decoder.flush();
    if (decodingError) throw decodingError;
  } catch (error) {
    if (error instanceof PrototypeError) throw error;
    throw new PrototypeError('DECODE_FAILED', 'AAC 音轨解码失败，文件可能损坏或浏览器不支持。');
  } finally { if (decoder.state !== 'closed') decoder.close(); }
  const tail = resampler?.push(new Float32Array(0), true);
  if (tail?.length) { frames.push(tail); totalFrames += tail.length; }
  if (totalFrames) checkAudioMemory(totalFrames / LIMITS.sampleRate, LIMITS.sampleRate);
  if (!totalFrames) throw new PrototypeError('DECODE_FAILED', '没有解码出音频采样。');
  const joined = new Float32Array(totalFrames);
  let offset = 0;
  for (const frame of frames) { joined.set(frame, offset); offset += frame.length; }
  return joined;
}
