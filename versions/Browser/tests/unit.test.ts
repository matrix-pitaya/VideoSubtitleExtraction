import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { decodeWav, decodeMp4, resampleMono, StreamingResampler, isSilent, checkDuration, checkAudioMemory } from '../src/audio.ts';
import { timestamp, toSrt, txtForDownload, cleanSegments, appendChunk, safeFilename } from '../src/protocol.ts';
import { ModelBytesResponse } from '../src/asset-store.ts';

test('verified model cache reads reuse tensor bytes without a Response body copy', async () => {
  const buffer = new Uint8Array([0, 1, 255, 128]).buffer;
  const response = new ModelBytesResponse(buffer);
  assert.equal(response.status, 200);
  assert.equal(await response.arrayBuffer(), buffer);
  assert.equal(await response.clone().arrayBuffer(), buffer);
  assert.deepEqual(new Uint8Array(await response.clone().arrayBuffer()), new Uint8Array([0, 1, 255, 128]));
});

test('Simplified Chinese is consistent in recognition, overlap, TXT and SRT', () => {
  const traditional = '你好，這是瀏覽器本地識別測試。視頻不會上傳到服務器。';
  const simplified = '你好，这是浏览器本地识别测试。视频不会上传到服务器。';
  const segments = [{ start: 0, end: 2, text: traditional }];
  assert.equal(cleanSegments(segments, 2)[0].text, simplified);
  assert.equal(txtForDownload(segments), '\uFEFF' + simplified);
  assert.ok(toSrt(segments).includes(simplified));
  assert.equal(appendChunk([{ start: 0, end: 2, text: simplified }], [{ start: 1, end: 2, text: traditional }]).length, 1);
  assert.equal(cleanSegments([{ start: 0, end: 1, text: 'OpenAI 123 English' }], 1)[0].text, 'OpenAI 123 English');
});

test('UTF-8 shared protocol and millisecond rollover', () => {
  const task = JSON.parse(readFileSync('../../protocol/examples/task-v1.json', 'utf-8'));
  const srt = toSrt(task.segments);
  assert.ok(srt.includes('00:00:00,125 --> 00:00:01,999'));
  assert.ok(srt.includes('视频不会上传。'));
  assert.equal(timestamp(59.9996), '00:01:00,000');
  assert.throws(() => timestamp(NaN));
  assert.equal(safeFilename('中文/测试.mp4'), '中文_测试.mp4');
  const txt = Buffer.from(txtForDownload(task.segments), 'utf8');
  assert.deepEqual([...txt.subarray(0, 3)], [0xef, 0xbb, 0xbf]);
  assert.ok(txt.toString('utf8').includes('你好，这是测试。\r\n视频不会上传。'));
});

test('boundary overlap dedup preserves nonoverlapping repetition', () => {
  const first = [{ start: 0, end: 20, text: '你好，今天测试' }];
  assert.deepEqual(appendChunk(first, [{ start: 18, end: 25, text: '今天测试完成' }]), [...first, { start: 20, end: 25, text: '完成' }]);
  assert.equal(appendChunk(first, [{ start: 21, end: 25, text: '你好，今天测试' }]).length, 2);
  assert.equal(cleanSegments([{ start: 0, end: NaN, text: 'x' }], 10).length, 0);
});

test('actual WAV decode and resampling length', () => {
  const source = readFileSync('public/samples/chinese.wav');
  const pcm = decodeWav(source.buffer.slice(source.byteOffset, source.byteOffset + source.byteLength));
  assert.equal(pcm.length, 117120);
  assert.ok(!isSilent(pcm));
  assert.equal(resampleMono(new Float32Array(48000), 48000).length, 16000);
});

test('silence is not confused with energetic BGM', () => {
  for (const [file, expected] of [['silence.wav', true], ['bgm.wav', false]] as const) {
    const source = readFileSync('public/samples/' + file);
    assert.equal(isSilent(decodeWav(source.buffer.slice(source.byteOffset, source.byteOffset + source.byteLength))), expected);
  }
});

test('invalid media, absent audio and duration limits', async () => {
  assert.throws(() => decodeWav(new ArrayBuffer(50)), /损坏/);
  assert.doesNotThrow(() => checkDuration(61));
  assert.throws(() => checkAudioMemory(1e9, 48000), /内存预算/);
  const source = readFileSync('public/samples/no-audio.mp4');
  await assert.rejects(decodeMp4(source.buffer.slice(source.byteOffset, source.byteOffset + source.byteLength)), /没有音轨/);
  const broken = readFileSync('public/samples/broken.mp4');
  await assert.rejects(decodeMp4(broken.buffer.slice(broken.byteOffset, broken.byteOffset + broken.byteLength)), /损坏/);
});

test('streaming resampling preserves sample count and phase across packets', () => {
  const input = Float32Array.from({ length: 48000 }, (_, i) => Math.sin(i * 2 * Math.PI * 440 / 48000));
  const expected = resampleMono(input, 48000);
  const stream = new StreamingResampler(48000), chunks: Float32Array[] = [];
  for (let i = 0; i < input.length; i += 1024) chunks.push(stream.push(input.subarray(i, i + 1024)));
  chunks.push(stream.push(new Float32Array(0), true));
  const actual = new Float32Array(chunks.reduce((n, chunk) => n + chunk.length, 0));
  let offset = 0;
  for (const chunk of chunks) { actual.set(chunk, offset); offset += chunk.length; }
  assert.equal(actual.length, 16000);
  assert.ok(actual.every((sample, i) => Math.abs(sample - expected[i]) < 0.00001));
});
