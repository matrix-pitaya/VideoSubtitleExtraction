"""Own synthetic audio/media fixtures; no customer data or remote sample licensing."""
import hashlib
import json
import math
from pathlib import Path
import struct
import wave
import av
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / 'public/samples'
with wave.open(str(folder / 'chinese.wav'), 'rb') as source:
    rate = source.getframerate()
    pcm = source.readframes(source.getnframes())
    duration = source.getnframes() / rate

def write_wav(name, samples):
    with wave.open(str(folder / name), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(np.asarray(samples, dtype='<i2').tobytes())

write_wav('silence.wav', np.zeros(32000))
time = np.arange(48000) / 16000
write_wav('bgm.wav', 1500 * (np.sin(2 * math.pi * 261.63 * time) + np.sin(2 * math.pi * 329.63 * time)))
write_wav('boundary.wav', np.tile(np.frombuffer(pcm, dtype='<i2'), 4))
(folder / 'broken.mp4').write_bytes(b'not an MP4 file\x00\xff\x00')

def media(name, include_audio=True):
    with av.open(str(folder / name), 'w', format='mov' if name.endswith('.mov') else 'mp4') as output:
        video = output.add_stream('libx264', rate=5)
        video.width, video.height, video.pix_fmt = 160, 90, 'yuv420p'
        audio = output.add_stream('aac', rate=16000) if include_audio else None
        if audio:
            audio.layout = 'mono'
            # Re-encode the WAV through the system-independent PyAV decoder.
            with av.open(str(folder / 'chinese.wav')) as source:
                for frame in source.decode(audio=0):
                    for packet in audio.encode(frame): output.mux(packet)
            for packet in audio.encode(): output.mux(packet)
        for i in range(math.ceil((duration if include_audio else 1) * 5)):
            frame = av.VideoFrame.from_ndarray(np.zeros((90, 160, 3), dtype=np.uint8), format='rgb24')
            frame.pts = i
            for packet in video.encode(frame): output.mux(packet)
        for packet in video.encode(): output.mux(packet)

media('chinese.mp4')
media('chinese.mov')
media('no-audio.mp4', False)
with av.open(str(folder / 'chinese.mp3'), 'w') as output:
    stream = output.add_stream('libmp3lame', rate=16000)
    stream.layout = 'mono'
    with av.open(str(folder / 'chinese.wav')) as source:
        for frame in source.decode(audio=0):
            for packet in stream.encode(frame): output.mux(packet)
    for packet in stream.encode(): output.mux(packet)

manifest = {'reference': '你好，这是浏览器本地识别测试。视频不会上传到服务器。',
            'source': 'Project-authored synthetic Chinese speech, Microsoft Huihui Desktop TTS',
            'durationSeconds': duration, 'files': []}
for path in sorted(folder.iterdir()):
    if path.suffix in ('.wav', '.mp4', '.mov', '.mp3'):
        manifest['files'].append({'path': path.name, 'bytes': path.stat().st_size,
                                  'sha256': hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()})
(folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(manifest, ensure_ascii=False))
