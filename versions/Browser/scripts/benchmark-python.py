"""Same synthetic sample as browser tests; local Python small baseline only."""
import json
from pathlib import Path
import platform
import time
from faster_whisper import WhisperModel

root = Path(__file__).resolve().parents[1]
started = time.perf_counter()
model = WhisperModel(str(root.parent / 'Web/models/small'), device='cpu', compute_type='int8', cpu_threads=4, local_files_only=True)
loaded = time.perf_counter()
segments, info = model.transcribe(str(root / 'public/samples/chinese.wav'), language='zh', beam_size=1, vad_filter=True)
values = [{'start': s.start, 'end': s.end, 'text': s.text} for s in segments]
finished = time.perf_counter()
report = {'environment': 'local Windows desktop, not production server or phone', 'platform': platform.platform(),
          'model': 'faster-whisper small', 'device': 'cpu', 'computeType': 'int8', 'cpuThreads': 4,
          'durationSeconds': info.duration, 'loadMs': (loaded - started) * 1000,
          'inferenceMs': (finished - loaded) * 1000, 'segments': values, 'text': ''.join(s['text'] for s in values)}
(root / 'artifacts/python-benchmark.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=True))
