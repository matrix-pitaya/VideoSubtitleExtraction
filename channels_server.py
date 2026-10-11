"""Seller-operated resolver: customers submit links without platform login.

Run after authorizing Yuanbao on the seller's machine:
  $env:CHANNELS_SERVER_KEY = '<your service key>'
  .venv/Scripts/python.exe channels_server.py --port 8020
Put an HTTPS reverse proxy in front of it for remote customers.
"""
from __future__ import annotations
import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from channels_auth import resolve_with_saved_session
from link_download import is_wechat_channels, new_session, wechat_detail, wechat_media_urls


def resolve(source: str) -> dict:
    if not is_wechat_channels(source):
        raise ValueError("请提供有效视频号分享链接")
    playable = resolve_with_saved_session(source)
    with new_session() as session:
        feed = wechat_detail(session, playable)
    if not wechat_media_urls(feed):
        raise ValueError("平台没有返回可下载的视频")
    return {"errCode": 0, "data": {"feedInfo": feed}}


def make_handler(access_key: str, resolver=resolve):
    if not access_key:
        raise ValueError("必须设置 CHANNELS_SERVER_KEY，不能运行无授权解析服务")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Do not log signed URLs, cookies or authorization headers.

        def reply(self, status: int, data: dict):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.reply(200, {"status": "ok"}) if self.path == "/health" else self.reply(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/api/fetch_video_profile":
                return self.reply(404, {"error": "not found"})
            supplied = self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied.encode(), ("Bearer " + access_key).encode()):
                return self.reply(401, {"error": "unauthorized"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16384:
                    return self.reply(413, {"error": "invalid request size"})
                source = json.loads(self.rfile.read(size)).get("url", "")
                if not isinstance(source, str) or not is_wechat_channels(source):
                    return self.reply(400, {"error": "invalid share URL"})
            except (ValueError, AttributeError):
                return self.reply(400, {"error": "invalid request"})
            try:
                self.reply(200, resolver(source))
            except Exception:
                self.reply(502, {"error": "解析服务暂不可用，请运营者检查登录状态、网络或作品有效性"})

    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="视频号后台解析服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8020)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(os.environ.get("CHANNELS_SERVER_KEY", "")))
    server.serve_forever()
