"""Download optional medium/large-v3 assets using pinned revisions and SHA256."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import runpy

ROOT = Path(__file__).resolve().parents[1]
sources = json.loads((ROOT / 'scripts/extra-model-sources.json').read_text())
prune = runpy.run_path(str(ROOT / 'scripts/encoder-graph.py'))['prune']
def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as file:
        while chunk := file.read(4 * 1024 * 1024): digest.update(chunk)
    return digest.hexdigest()
parser = argparse.ArgumentParser()
parser.add_argument('profiles', nargs='*', choices=['medium', 'large-v3'])
args = parser.parse_args()
for profile in args.profiles or ['medium']:
    model = sources[profile]
    for name, expected in model['files'].items():
        path = ROOT / 'public/models' / model['model'] / name
        path.parent.mkdir(parents=True, exist_ok=True)
        optimization = model.get('encoderGraphOptimization') if name == 'onnx/encoder_model_quantized.onnx' else None
        if optimization and path.exists() and path.stat().st_size == optimization['bytes'] and sha256(path) == optimization['sha256']:
            print('Verified optimized encoder', profile, flush=True); continue
        if not path.exists():
            temporary = path.with_suffix(path.suffix + '.part')
            for attempt in range(3):
                offset = temporary.stat().st_size if temporary.exists() else 0
                if offset == expected['bytes']: break
                headers = {'User-Agent': 'VideoSubtitleExtraction/0.1.5'}
                if offset: headers['Range'] = f'bytes={offset}-'
                request = urllib.request.Request(f"https://huggingface.co/{model['repository']}/resolve/{model['revision']}/{name}?download=true", headers=headers)
                with urllib.request.urlopen(request, timeout=120) as response:
                    resumed = offset > 0 and response.status == 206
                    if resumed and not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'): raise ValueError('Invalid resume range')
                    with temporary.open('ab' if resumed else 'wb') as output:
                        total = offset if resumed else 0
                        milestone = total // (64 * 1024 * 1024)
                        while total < expected['bytes'] and (chunk := response.read1(min(4 * 1024 * 1024, expected['bytes'] - total))):
                            output.write(chunk); total += len(chunk)
                            if total // (64 * 1024 * 1024) > milestone:
                                milestone = total // (64 * 1024 * 1024); print(profile, name, total, flush=True)
                            if total > expected['bytes']: raise ValueError('Asset size mismatch')
                if total == expected['bytes']: break
                print('Retry incomplete download', profile, name, total, flush=True)
            candidate = temporary
        else:
            candidate = path
        if candidate.stat().st_size != expected['bytes'] or sha256(candidate) != expected['sha256']:
            raise ValueError(f'Pinned asset integrity failed: {profile}/{name}')
        if optimization:
            optimized = path.with_suffix('.optimized')
            result = prune(candidate, optimized)
            if result['sha256'] != optimization['sha256'] or result['bytes'] != optimization['bytes']:
                raise ValueError('Optimized encoder integrity mismatch')
            original = ROOT / 'artifacts' / f"{model['model']}-encoder-original.onnx"
            original.parent.mkdir(parents=True, exist_ok=True); candidate.replace(original); optimized.replace(path)
        elif candidate != path: candidate.replace(path)
        print('Verified', profile, name, expected['bytes'], flush=True)
