"""Bootstrap fixed small model, checking Git blob IDs and LFS SHA256 from its pinned revision."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = '36050c46d777d46dc4b5f43f6d90574fc38f8732'
FILES = {
    'config.json': ('git', 'b0447377b1ade057f991a6a0870d2a91de762f7f'),
    'generation_config.json': ('git', '703dc78ee83e87fca3ace72170253cdfe4cd2d13'),
    'preprocessor_config.json': ('git', '91876762a536a746d268353c5cba57286e76b058'),
    'tokenizer.json': ('git', '1e95340ff836fad1b5932e800fb7b8c5e6d78a74'),
    'tokenizer_config.json': ('git', 'd13b786c04765fb1a06492b53587752cd67665ea'),
    'onnx/encoder_model_quantized.onnx': ('sha256', 'a43a83f3c5361cd591cfa7c36f14b43cf7cb22f47a415cc14a8d557be800fa92'),
    'onnx/decoder_model_merged_quantized.onnx': ('sha256', 'ec07c3cbb64172c39791e26ee870a65ac22b458c36722bfe2776b3dbf741e0c9'),
}
manifest = {'model': 'whisper-small', 'repository': 'onnx-community/whisper-small', 'revision': REVISION, 'multilingual': True, 'dtype': 'q8', 'files': []}
for name, (kind, expected) in FILES.items():
    path = ROOT / 'public/models/whisper-small' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path if path.exists() else path.with_suffix(path.suffix + '.part')
    if not path.exists():
        request = urllib.request.Request(f'https://huggingface.co/onnx-community/whisper-small/resolve/{REVISION}/{name}', headers={'User-Agent': 'VideoSubtitleExtraction-Prototype/0.1.1'})
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
(ROOT / 'src/small-model-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
