"""A local Streamlit backend hosted in a Windows desktop window."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback
from urllib.request import urlopen
import uuid

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'


class Backend:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.process = None
        self.url = None

    def start(self, timeout=30):
        data = self.root / 'data'
        data.mkdir(exist_ok=True)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        base = 'desktop-' + uuid.uuid4().hex
        self.url = f'http://127.0.0.1:{port}/{base}/'
        # pythonw is reserved for the window process; use python.exe for Streamlit.
        python = Path(sys.executable).with_name('python.exe')
        command = [str(python), '-m', 'streamlit', 'run', str(self.root / 'app.py'),
                   '--server.address', '127.0.0.1', '--server.port', str(port),
                   '--server.baseUrlPath', base, '--server.headless', 'true',
                   '--server.maxUploadSize', '1024', '--browser.gatherUsageStats', 'false']
        with (data / 'desktop.stdout.log').open('wb') as out, (data / 'desktop.stderr.log').open('wb') as err:
            self.process = subprocess.Popen(command, cwd=self.root, stdout=out, stderr=err,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError('本地程序启动失败，请查看 data/desktop.stderr.log。')
            try:
                with urlopen(self.url + '_stcore/health', timeout=1) as response:
                    if response.read().strip() == b'ok':
                        return self.url
            except OSError:
                pass
            time.sleep(0.2)
        raise RuntimeError('本地程序启动超时，请查看 data/desktop.stderr.log。')

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    DATA.mkdir(exist_ok=True)
    os.chdir(ROOT)
    result = {'ok': False}
    backend = Backend()
    try:
        import webview
        url = backend.start()
        webview.settings['ALLOW_DOWNLOADS'] = True
        window = webview.create_window('VideoSubtitleExtraction', url, width=1280, height=850,
                                       min_size=(900, 600), hidden=args.self_test)

        def verify():
            try:
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    text = window.evaluate_js('document.body ? document.body.innerText : ""') or ''
                    if '订单管理' in text and '创建订单' in text:
                        result.update(ok=True, url=url, backend_pid=backend.process.pid,
                                      title=window.title, renderer='edgechromium')
                        return
                    time.sleep(0.3)
                raise RuntimeError('桌面窗口未加载订单界面。')
            except Exception:
                result['error'] = traceback.format_exc()
            finally:
                window.destroy()

        webview.start(verify if args.self_test else None, gui='edgechromium',
                      storage_path=str(DATA / 'webview'), private_mode=True)
        return 0 if not args.self_test or result['ok'] else 1
    finally:
        backend.stop()
        if args.self_test:
            result['backend_stopped'] = backend.process is None or backend.process.poll() is not None
            (DATA / 'desktop-self-test.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    try:
        DATA.mkdir(exist_ok=True)
        with (DATA / 'desktop-launcher.log').open('a', encoding='utf-8', buffering=1) as log:
            sys.stdout = sys.stderr = log
            try:
                code = main()
            except Exception:
                traceback.print_exc()
                if '--self-test' not in sys.argv:
                    ctypes.windll.user32.MessageBoxW(None,
                        '启动失败。请查看 data/desktop-launcher.log。\n'
                        '请确认已安装 Microsoft Edge WebView2 Runtime 和 .NET Framework 4.6.2 或更新版本。',
                        'VideoSubtitleExtraction', 0x10)
                code = 1
        sys.exit(code)
    except OSError:
        ctypes.windll.user32.MessageBoxW(None, '无法写入数据目录，请完整解压到有写入权限的文件夹。',
                                        'VideoSubtitleExtraction', 0x10)
        sys.exit(1)
