"""Download immutable model files for local prototype hosting; never use main/latest."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'ff4177021cc41f7db950912b73ea4fdf7d01d8e7'
REPOSITORY = 'onnx-community/whisper-tiny'
FILES = {
    'config.json': '46aeea0a406afbeb563fc8e59ca10609203df4299af6a83f73752fef369efd2d',
    'generation_config.json': 'f5c67e5a4f7102f8cb4d058bc95da276bbc19eeec997267c3bb0f25ef68facd1',
    'tokenizer.json': '27fc476bfe7f17299480be2273fc0608e4d5a99aba2ab5dec5374b4482d1a566',
    'tokenizer_config.json': '2a4c4281cf9f51ac6ccc406fdc711a087afe6530f671fa7b80953edc498275ce',
    'preprocessor_config.json': 'a6a76d28c93edb273669eb9e0b0636a2bddbb1272c3261e47b7ca6dfdbac1b8d',
    'onnx/encoder_model_quantized.onnx': '2af4a414ca47aa30f61246017e5fe82b0a8d229281d1255ba666a2a7f6b84d19',
    'onnx/decoder_model_merged_quantized.onnx': '25e807a962b6349356d0ea5d0dfe530b7e5bf0e2a484aeca0359d03143faddd3',
}
manifest = {'model': 'whisper-tiny', 'repository': REPOSITORY, 'revision': REVISION,
            'multilingual': True, 'dtype': 'q8', 'files': []}
for name, expected in FILES.items():
    path = ROOT / 'public/models/whisper-tiny' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        request = urllib.request.Request(f'https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{name}',
                                         headers={'User-Agent': 'VideoSubtitleExtraction-Prototype/0.1'})
        partial = path.with_suffix(path.suffix + '.part')
        with urllib.request.urlopen(request, timeout=90) as response, partial.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        with partial.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != expected:
                raise ValueError(f'Model integrity check failed: {name}')
        partial.replace(path)
    digest = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
    if expected and digest != expected:
        raise ValueError(f'Model integrity check failed: {name}; discard this partial file before retrying')
    manifest['files'].append({'path': name, 'bytes': path.stat().st_size, 'sha256': digest})
    print(name, path.stat().st_size, digest, flush=True)
manifest['totalBytes'] = sum(f['bytes'] for f in manifest['files'])
(ROOT / 'src/model-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
