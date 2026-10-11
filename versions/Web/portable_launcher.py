"""Launcher for the relocatable Windows customer package."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import uuid
import webbrowser

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RECORD = DATA / "service.json"


def healthy(record):
    try:
        with urlopen(record["url"] + "_stcore/health", timeout=2) as response:
            return response.read().strip() == b"ok"
    except Exception:
        return False


def own_process(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return False
    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        return bool(kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))) and Path(buffer.value).resolve() == Path(sys.executable).resolve()
    finally:
        kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    DATA.mkdir(exist_ok=True)
    os.chdir(ROOT)
    # Serialize double clicks; every package instance gets its own health URL.
    import msvcrt
    with (DATA / "launch.lock").open("a+b") as lock:
        lock.seek(0)
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        try:
            try:
                record = json.loads(RECORD.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                record = {}
            if args.stop:
                if record and healthy(record) and own_process(record["pid"]):
                    subprocess.run(["taskkill", "/PID", str(record["pid"]), "/T", "/F"], check=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL)
                    RECORD.unlink(missing_ok=True)
                return
            if not record or not healthy(record):
                with socket.socket() as listener:
                    listener.bind(("127.0.0.1", 0))
                    port = listener.getsockname()[1]
                base = "workbench-" + uuid.uuid4().hex[:12]
                command = [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
                           "--server.address", "127.0.0.1", "--server.port", str(port),
                           "--server.baseUrlPath", base, "--server.headless", "true", "--browser.gatherUsageStats", "false"]
                with (DATA / "server.stdout.log").open("wb") as stdout, (DATA / "server.stderr.log").open("wb") as stderr:
                    process = subprocess.Popen(command, cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW, stdout=stdout, stderr=stderr)
                record = {"pid": process.pid, "url": f"http://127.0.0.1:{port}/{base}/"}
                for _ in range(60):
                    if healthy(record):
                        break
                    if process.poll() is not None:
                        raise RuntimeError("启动失败，请查看 data/server.stderr.log")
                    time.sleep(0.5)
                else:
                    process.terminate()
                    raise RuntimeError("启动超时，请检查 data/server.stderr.log")
                RECORD.write_text(json.dumps(record), encoding="utf-8")
            if not args.no_browser:
                webbrowser.open(record["url"])
            print(record["url"])
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc))
        sys.exit(1)
