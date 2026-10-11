"""Build a customer archive from explicit allowlists, never from order data."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import os
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED
from packaging.requirements import Requirement
from packaging.markers import default_environment

ROOT = Path(__file__).resolve().parent
SOURCES = ['app.py', 'core.py', 'link_download.py', 'screen_text.py',
           'download_models.py', 'portable_launcher.py']


def dependency_closure(desktop=False):
    files = ['requirements.txt'] + (['requirements-desktop.txt'] if desktop else [])
    requirements = [Requirement(line) for name in files for line in (ROOT / name).read_text().splitlines() if line.strip()]
    found, extras, pending = {}, {}, requirements[:]
    environment = default_environment()
    while pending:
        requirement = pending.pop()
        key = requirement.name.lower().replace('_', '-')
        previous_extras = extras.get(key, set())
        if key in found and requirement.extras <= previous_extras:
            continue
        distribution = metadata.distribution(requirement.name)
        if not requirement.specifier.contains(distribution.version, prereleases=True):
            raise ValueError(f'Installed dependency does not satisfy {requirement}')
        found[key] = distribution
        extras[key] = previous_extras | requirement.extras
        for text in distribution.requires or []:
            child = Requirement(text)
            if not child.marker or any(child.marker.evaluate({**environment, 'extra': extra}) for extra in extras[key] | {''}):
                pending.append(child)
    return found


def build(runtime_zip: Path, output: Path, desktop=False):
    if sys.version_info[:2] != (3, 12):
        raise ValueError('Build with Python 3.12 for the supplied runtime')
    # Nested platform directories can exceed Windows' legacy 260-character limit.
    output = output.resolve()
    if sys.platform == 'win32' and not str(output).startswith('\\\\?\\'):
        output = Path('\\\\?\\' + str(output))
    folder = output / 'VideoSubtitleExtraction-Windows-x64'
    if folder.exists():
        raise FileExistsError('Output folder already exists; choose a new output directory')
    folder.mkdir(parents=True)
    for name in SOURCES:
        shutil.copy2(ROOT / name, folder / name)
    if desktop:
        shutil.copy2(ROOT / 'desktop_launcher.py', folder / 'desktop_launcher.py')
        compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.is_file():
            raise RuntimeError('Install the .NET Framework C# compiler to build the desktop EXE')
        executable = str(folder / 'VideoSubtitleExtraction.exe').removeprefix('\\\\?\\')
        subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64',
                        '/codepage:65001', '/reference:System.Windows.Forms.dll',
                        '/out:' + executable, str(ROOT / 'desktop_bootstrap.cs')], check=True)
    runtime = folder / 'runtime'
    with ZipFile(runtime_zip) as archive:
        archive.extractall(runtime)
    (runtime / 'python312._pth').write_text('python312.zip\n.\nLib/site-packages\n..\nimport site\n', encoding='utf-8')
    (runtime / 'sitecustomize.py').write_text('import sys\nsys.dont_write_bytecode = True\n', encoding='utf-8')
    site = runtime / 'Lib' / 'site-packages'
    site.mkdir(parents=True)
    inventory = []
    for name, distribution in sorted(dependency_closure(desktop).items()):
        base = Path(distribution.locate_file('')).resolve()
        for relative in distribution.files or []:
            if '..' in Path(relative).parts or '__pycache__' in Path(relative).parts or str(relative).endswith('.pyc') or Path(relative).name == 'direct_url.json':
                continue
            source = Path(distribution.locate_file(relative)).resolve()
            if not source.is_relative_to(base) or not source.is_file():
                continue
            destination = site / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        inventory.append({'name': name, 'version': distribution.version,
                          'license': distribution.metadata.get('License-Expression') or distribution.metadata.get('License', ''),
                          'homepage': distribution.metadata.get('Home-page', '')})
    (folder / 'THIRD_PARTY.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'dependency-versions.txt').write_text('\n'.join(f"{p['name']}=={p['version']}" for p in inventory), encoding='utf-8')
    model = folder / 'models' / 'small'
    model.mkdir(parents=True)
    for name in ['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt']:
        shutil.copy2(ROOT / 'models' / 'small' / name, model / name)
    shutil.copy2(ROOT / 'MODEL_LICENSE.txt', model / 'LICENSE.txt')
    if not desktop:
        for name, flag in [('VideoSubtitleExtraction.cmd', ''), ('VideoSubtitleExtraction.Stop.cmd', '--stop')]:
            (folder / name).write_bytes(('@echo off\r\ncd /d "%~dp0"\r\n"%~dp0runtime\\python.exe" "%~dp0portable_launcher.py" ' + flag + '\r\nif errorlevel 1 pause\r\n').encode('ascii'))
    guide = 'CUSTOMER_GUIDE_DESKTOP.txt' if desktop else 'CUSTOMER_GUIDE.txt'
    shutil.copy2(ROOT / guide, folder / '使用说明.txt')
    manifest = []
    for path in sorted(folder.rglob('*')):
        if path.is_file():
            manifest.append({'path': path.relative_to(folder).as_posix(), 'bytes': path.stat().st_size,
                             'sha256': hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()})
    (folder / 'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    archive_path = output / (folder.name + '.zip')
    with ZipFile(archive_path, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
        for entry in manifest:
            archive.write(folder / entry['path'], folder.name + '/' + entry['path'])
        archive.write(folder / 'PACKAGE_MANIFEST.json', folder.name + '/PACKAGE_MANIFEST.json')
    (output / 'SHA256.txt').write_text(hashlib.file_digest(archive_path.open('rb'), 'sha256').hexdigest() + '  ' + archive_path.name, encoding='utf-8')
    print(json.dumps({'archive': str(archive_path), 'bytes': archive_path.stat().st_size, 'dependencies': len(inventory)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-zip', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--desktop', action='store_true', help='Build the independent Windows window with an EXE entry')
    args = parser.parse_args()
    build(args.runtime_zip, args.output, args.desktop)
