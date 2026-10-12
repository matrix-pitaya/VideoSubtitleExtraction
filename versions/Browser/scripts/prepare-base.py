"""Bootstrap fixed base model, checking Git blob IDs and LFS SHA256 from its pinned revision."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = '1846881b6b3a3024392c1eea3ad983695bc23925'
FILES = {
    'config.json': ('git', 'ce7faf5d5e56e82d4800e55f524582a525639ff7'),
    'generation_config.json': ('git', 'a57cdbf036979f80bb7ff092a0fee6256a81d329'),
    'preprocessor_config.json': ('git', '91876762a536a746d268353c5cba57286e76b058'),
    'tokenizer.json': ('git', '1e95340ff836fad1b5932e800fb7b8c5e6d78a74'),
    'tokenizer_config.json': ('git', '25be523be5ac50a7671a77f55acba082459d6314'),
    'onnx/encoder_model_quantized.onnx': ('sha256', '5862993336bf33acd23736071aae2b32261d3b1b2f37780194460d4ef974dd46'),
    'onnx/decoder_model_merged_quantized.onnx': ('sha256', 'fa3ef9902734ce5ae6f9ef2bdb2ba9a6c4b5785b09f4f420ce036573dc9d090b'),
}
manifest = {'model': 'whisper-base', 'repository': 'onnx-community/whisper-base', 'revision': REVISION, 'multilingual': True, 'dtype': 'q8', 'files': []}
for name, (kind, expected) in FILES.items():
    path = ROOT / 'public/models/whisper-base' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path if path.exists() else path.with_suffix(path.suffix + '.part')
    if not path.exists():
        request = urllib.request.Request(f'https://huggingface.co/onnx-community/whisper-base/resolve/{REVISION}/{name}', headers={'User-Agent': 'VideoSubtitleExtraction-Prototype/0.1.1'})
        with urllib.request.urlopen(request, timeout=90) as response, target.open('wb') as output:
            while chunk := response.read(1024 * 1024): output.write(chunk)
    data = target.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    upstream = digest if kind == 'sha256' else hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
    if upstream != expected: raise ValueError(f'Immutable asset integrity failed: {name}')
    if target != path: target.replace(path)
    manifest['files'].append({'path': name, 'bytes': len(data), 'sha256': digest})
    print(name, len(data), digest, flush=True)
manifest['totalBytes'] = sum(file['bytes'] for file in manifest['files'])
(ROOT / 'src/base-model-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
