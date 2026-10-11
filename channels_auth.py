"""Local Yuanbao session used only for resolving WeChat Channels share links."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

AUTH_DIR = Path(__file__).resolve().parent / "data" / "auth"
SESSION_FILE = AUTH_DIR / "yuanbao.json"
STATUS_FILE = AUTH_DIR / "login_status.json"
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def parse_yuanbao(source: str, cookies: list[dict], user_agent: str = DESKTOP_UA) -> str:
    # Use a separate session: Yuanbao credentials never reach finder or resolvers.
    with requests.Session() as session:
        for cookie in cookies:
            domain = cookie.get("domain", "").lstrip(".")
            if domain == "yuanbao.tencent.com":
                session.cookies.set(cookie["name"], cookie["value"], domain=cookie["domain"], path=cookie.get("path", "/"))
        response = session.post("https://yuanbao.tencent.com/api/weixin/get_parse_result",
            json={"type": "video_channel_url", "url": source, "scene": 1},
            headers={"User-Agent": user_agent, "Origin": "https://yuanbao.tencent.com",
                     "Referer": "https://yuanbao.tencent.com/", "X-Source": "web"}, timeout=(10, 30))
        if response.status_code in (401, 403):
            raise ValueError("腾讯元宝登录已失效，请在侧栏重新扫码登录")
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") not in (None, 0):
            raise ValueError("腾讯元宝未能解析这条视频号链接，请检查登录状态或链接有效性")
        playable = payload.get("data", {}).get("playable_url", "")
        parsed = urlparse(playable)
        query = parse_qs(parsed.query)
        if parsed.scheme != "https" or parsed.hostname != "channels.weixin.qq.com" or parsed.path != "/finder-preview/pages/feed" or not query.get("token") or not query.get("eid"):
            raise ValueError("腾讯元宝未返回有效播放凭证，链接可能已失效或限制访问")
        return playable


def resolve_with_saved_session(source: str) -> str:
    if not SESSION_FILE.is_file():
        raise ValueError("请先在侧栏点击“扫码登录视频号下载”，完成腾讯元宝登录")
    saved = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    return parse_yuanbao(source, saved["cookies"], saved.get("user_agent", DESKTOP_UA))


def write_status(state: str, message: str):
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STATUS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps({"state": state, "message": message, "updated": time.time()}, ensure_ascii=False), encoding="utf-8")
    temporary.replace(STATUS_FILE)


def login_status() -> dict:
    try:
        status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        if status["state"] == "waiting" and time.time() - status["updated"] > 660:
            return {"state": "error", "message": "登录窗口已超时，请重新打开"}
        return status
    except (OSError, ValueError, KeyError):
        return {"state": "idle", "message": "尚未登录"}


def start_login(source: str) -> None:
    if login_status()["state"] == "waiting":
        return
    write_status("waiting", "请在打开的 Edge / Chrome 窗口中登录腾讯元宝；登录完成后会自动验证并保存")
    try:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--login", source],
                         cwd=str(Path(__file__).resolve().parent),
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        write_status("error", "登录窗口启动失败，请检查浏览器和 Python 环境")
        raise


def run_login(source: str):
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = None
            for channel in ("msedge", "chrome"):
                try:
                    browser = p.chromium.launch(channel=channel, headless=False)
                    break
                except Exception:
                    continue
            if browser is None:
                raise ValueError("未找到可用的 Edge / Chrome，请先安装浏览器")
            context = browser.new_context()
            page = context.new_page()
            page.goto("https://yuanbao.tencent.com/", wait_until="domcontentloaded", timeout=45000)
            agent = page.evaluate("navigator.userAgent")
            # No browser profile is imported. Only this dedicated login session is used.
            last_fingerprint = None
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline and not page.is_closed():
                cookies = context.cookies("https://yuanbao.tencent.com/")
                fingerprint = sorted((c["name"], c["value"]) for c in cookies)
                if cookies and fingerprint != last_fingerprint:
                    last_fingerprint = fingerprint
                    try:
                        parse_yuanbao(source, cookies, agent)
                    except (ValueError, requests.RequestException):
                        pass
                    else:
                        temporary = SESSION_FILE.with_suffix(".tmp")
                        temporary.write_text(json.dumps({"cookies": cookies, "user_agent": agent}), encoding="utf-8")
                        temporary.replace(SESSION_FILE)
                        write_status("ready", "登录成功，已验证视频号播放凭证；可以开始或重试")
                        browser.close()
                        return
                page.wait_for_timeout(3000)
            browser.close()
            write_status("error", "登录已取消或超时，请重新打开扫码登录")
    except Exception as exc:
        import traceback
        AUTH_DIR.mkdir(parents=True, exist_ok=True)
        (AUTH_DIR / "login_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        write_status("error", str(exc) if isinstance(exc, ValueError) else "登录页面连接失败，请检查网络并重新打开")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--login":
        run_login(sys.argv[2])
