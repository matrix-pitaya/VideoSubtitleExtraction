"""Platform adapters for resolving public video share links."""
from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlunparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

MOBILE_UA = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"


def load_cookies(session, cookie_path: str):
    if cookie_path:
        import http.cookiejar
        jar = http.cookiejar.MozillaCookieJar(cookie_path)
        jar.load(ignore_discard=True, ignore_expires=True)
        session.cookies.update(jar)


def is_wechat_channels(url: str) -> bool:
    parsed = urlparse(url)
    return (parsed.hostname == "weixin.qq.com" and parsed.path.startswith("/sph/")) or (
        parsed.hostname == "channels.weixin.qq.com" and parsed.path.startswith("/finder-preview/pages/"))


def wechat_detail(session, url: str) -> dict:
    parsed = urlparse(url)
    match = re.fullmatch(r"/sph/([A-Za-z0-9_-]+)/?", parsed.path)
    query = parse_qs(parsed.query)
    short_id = match[1] if match else query.get("id", [""])[0]
    export_id = query.get("eid", [""])[0]
    if not short_id and not export_id:
        raise ValueError("视频号链接缺少作品标识，请复制完整分享链接")
    page = "https://channels.weixin.qq.com/finder-preview/pages/" + ("sph" if short_id else "feed")
    token = query.get("token", [""])[0]
    if not token:
        token = next((c.value for c in session.cookies if c.name == "token" and
                      (c.domain or "").lstrip(".") in ("weixin.qq.com", "channels.weixin.qq.com")), "")
    response = session.post("https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info",
        params={"_rid": f"{int(time.time()):x}-{secrets.token_hex(4)}", "_pageUrl": page},
        json={"baseReq": {"generalToken": token}, **({"shortUri": short_id} if short_id else {"exportId": export_id})},
        headers={"Referer": url if export_id else page, "Origin": "https://channels.weixin.qq.com"}, timeout=(10, 30))
    response.raise_for_status()
    data = response.json()
    if data.get("errCode") not in (None, 0):
        raise ValueError("视频号分享接口拒绝访问，请检查链接和登录 Cookies")
    feed = data.get("data", {}).get("feedInfo", {})
    if not feed:
        raise ValueError("视频号未返回作品信息，链接可能过期或限制访问")
    return feed


def wechat_media_urls(feed: dict) -> list[str]:
    return [url for url in [(feed.get("h264VideoInfo") or {}).get("videoUrl"),
                           (feed.get("h265VideoInfo") or {}).get("videoUrl"), feed.get("videoUrl")] if url]


def download_wechat_channels(item: dict, folder: Path, cookie_path: str = "",
                            parser_url: str = "", parser_key: str = "") -> str:
    with new_session() as session:
        session.headers["Referer"] = "https://channels.weixin.qq.com/"
        load_cookies(session, cookie_path)
        feed, official_error = {}, ""
        try:
            feed = wechat_detail(session, item["source"])
        except Exception:
            official_error = "官方分享接口访问失败"
        urls = wechat_media_urls(feed)
        login_error = ""
        if not urls:
            from channels_auth import SESSION_FILE, resolve_with_saved_session
            if SESSION_FILE.is_file():
                try:
                    playable = resolve_with_saved_session(item["source"])
                    feed = wechat_detail(session, playable)
                    urls = wechat_media_urls(feed)
                except ValueError as exc:
                    login_error = str(exc)
                except Exception:
                    login_error = "腾讯元宝解析连接失败，请检查网络后重试"
        if not urls and parser_url:
            if urlparse(parser_url).scheme not in ("http", "https"):
                raise ValueError("解析接口地址必须以 https:// 或 http:// 开头")
            # Never send platform cookies to an external resolver.
            headers = {"Authorization": "Bearer " + parser_key} if parser_key else {}
            try:
                response = requests.post(parser_url, json={"url": item["source"]}, headers=headers, timeout=(10, 45))
                response.raise_for_status()
                payload = response.json()
                if payload.get("errCode") not in (None, 0):
                    raise ValueError("解析接口返回错误")
                feed = payload.get("data", {}).get("feedInfo", {})
                urls = wechat_media_urls(feed)
            except requests.RequestException as exc:
                raise ValueError("视频号解析接口连接失败或授权无效，请检查接口地址与密钥") from exc
        if not urls:
            raise ValueError(login_error or "此分享页没有视频地址，请在侧栏点击“扫码登录视频号下载”，完成登录后重试。")
        item["title"] = (feed.get("description") or "视频号视频")[:200]
        path = download_media(session, urls, folder / (item["id"] + ".mp4"))
        item["download_engine"] = "wechat-channels-share"
        return path


def is_xiaohongshu(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith("." + domain)
               for domain in ("xiaohongshu.com", "xhslink.com", "xhslink.cn"))


def unwrap_xhs_login(url: str) -> str:
    for _ in range(3):
        parsed = urlparse(url)
        if not is_xiaohongshu(url) or parsed.path != "/login":
            break
        target = parse_qs(parsed.query).get("redirectPath", [""])[0]
        if target.startswith("/"):
            target = "https://www.xiaohongshu.com" + target
        if not is_xiaohongshu(target) or urlparse(target).scheme not in ("http", "https"):
            raise ValueError("小红书登录跳转中没有有效作品链接")
        url = urlunparse(urlparse(target)._replace(scheme="https"))
    return url


def xiaohongshu_detail(session, url: str) -> dict:
    from yt_dlp.utils import js_to_json
    url = unwrap_xhs_login(url)
    requested_id = re.search(r"/(?:explore|discovery/item)/([a-fA-F0-9]+)", url)
    response = session.get(url, timeout=(10, 30))
    response.raise_for_status()
    if not is_xiaohongshu(response.url):
        raise ValueError("小红书链接跳转到了其他站点")
    recovered = unwrap_xhs_login(response.url)
    if recovered != response.url:
        response = session.get(recovered, timeout=(10, 30))
        response.raise_for_status()
    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(.*?)</script>", response.text, re.S)
    if not match:
        raise ValueError("小红书未返回作品内容；链接可能已失效或需要登录 Cookie")
    state = json.loads(js_to_json(match[1].strip().rstrip(";")))
    identifier_match = re.search(r"/(?:explore|discovery/item)/([a-fA-F0-9]+)", recovered)
    identifier = requested_id[1] if requested_id else identifier_match[1] if identifier_match else None
    note = state.get("noteData", {}).get("data", {}).get("noteData", {})
    if not note:
        entries = state.get("note", {}).get("noteDetailMap", {})
        note = entries.get(identifier, {}).get("note", {})
    if not note or (identifier and str(note.get("noteId")) != identifier):
        raise ValueError("小红书未返回所请求的作品，可能已删除或限制访问")
    return note


def download_xiaohongshu(item: dict, folder: Path, cookie_path: str = "") -> str:
    with new_session() as session:
        session.headers["Referer"] = "https://www.xiaohongshu.com/"
        load_cookies(session, cookie_path)
        note = xiaohongshu_detail(session, item["source"])
        streams = note.get("video", {}).get("media", {}).get("stream", {})
        urls = []
        for codec in ("h264", "h265", "av1"):
            for stream in streams.get(codec, []):
                urls += [stream.get("masterUrl", "")] + (stream.get("backupUrls") or [])
        urls = [re.sub(r"^http://", "https://", u) for u in urls if u]
        if not urls:
            raise ValueError("此小红书作品没有可下载的视频，可能是图文笔记")
        item["title"] = (note.get("title") or note.get("desc") or "小红书视频")[:200]
        path = download_media(session, urls, folder / (str(note["noteId"]) + ".mp4"))
        item["download_engine"] = "xiaohongshu-share"
        return path


def download_media(session, urls: list[str], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".mp4.part")
    errors = []
    for url in dict.fromkeys(urls):
        if url.startswith("//"):
            url = "https:" + url
        if urlparse(url).scheme not in ("https", "http"):
            continue
        try:
            with session.get(url, stream=True, timeout=(10, 60)) as response:
                response.raise_for_status()
                if "text/html" in response.headers.get("Content-Type", "").lower():
                    raise ValueError("媒体地址返回了网页")
                size = 0
                with partial.open("wb") as file:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            size += len(chunk)
                            if size > 2 * 1024 ** 3:
                                raise ValueError("单条视频超过 2GB 下载限制")
                            file.write(chunk)
                if not size:
                    raise ValueError("下载视频为空")
            import av
            with av.open(str(partial)) as media:
                if not media.streams.audio and not media.streams.video:
                    raise ValueError("下载文件没有有效音视频流")
            partial.replace(path)
            return str(path)
        except Exception as exc:
            # Signed media URLs may contain credentials; keep only the error type.
            errors.append(type(exc).__name__)
            partial.unlink(missing_ok=True)
    raise ValueError("媒体下载失败：" + "、".join(errors[-2:]))


def is_douyin(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith("." + domain) for domain in ("douyin.com", "iesdouyin.com"))


def video_id(url: str) -> str | None:
    parsed = urlparse(url)
    match = re.search(r"/(?:share/)?video/(\d+)", parsed.path)
    if match:
        return match[1]
    for key in ("modal_id", "aweme_id", "item_id"):
        value = parse_qs(parsed.query).get(key, [""])[0]
        if value.isdigit():
            return value
    return None


def new_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": MOBILE_UA, "Referer": "https://www.iesdouyin.com/"})
    return session


def douyin_detail(session, url: str) -> dict:
    identifier = video_id(url)
    if not identifier:
        response = session.get(url, timeout=(10, 30))
        response.raise_for_status()
        if not is_douyin(response.url):
            raise ValueError("抖音分享链接跳转到了非抖音站点")
        identifier = video_id(response.url)
    if not identifier:
        raise ValueError("无法从链接中识别单条抖音视频，请粘贴视频分享链接")
    response = session.get(
        "https://www.iesdouyin.com/web/api/v2/aweme/slidesinfo/",
        params={"aweme_ids": json.dumps([int(identifier)])}, timeout=(10, 30))
    response.raise_for_status()
    try:
        details = response.json().get("aweme_details") or []
    except ValueError as exc:
        raise ValueError("抖音分享接口未返回视频信息") from exc
    detail = next((d for d in details if isinstance(d, dict) and str(d.get("aweme_id")) == identifier), None)
    if not detail:
        raise ValueError("抖音未返回这条视频；可能已删除、私密或当前访问受限")
    return detail


def download_douyin(item: dict, folder: Path) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    with new_session() as session:
        detail = douyin_detail(session, item["source"])
        urls = detail.get("video", {}).get("play_addr", {}).get("url_list") or []
        if not urls:
            raise ValueError("此抖音作品没有可下载视频音轨，可能是图文作品")
        item["title"] = (detail.get("desc") or f"抖音视频_{detail['aweme_id']}")[:200]
        path = folder / (str(detail["aweme_id"]) + ".mp4")
        partial = path.with_suffix(".mp4.part")
        errors = []
        for url in dict.fromkeys(urls):
            if url.startswith("//"):
                url = "https:" + url
            if urlparse(url).scheme not in ("https", "http"):
                continue
            try:
                with session.get(url, stream=True, timeout=(10, 60)) as response:
                    response.raise_for_status()
                    if "text/html" in response.headers.get("Content-Type", "").lower():
                        raise ValueError("媒体地址返回了网页，未获取到视频")
                    size = 0
                    with partial.open("wb") as file:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                size += len(chunk)
                                if size > 2 * 1024 ** 3:
                                    raise ValueError("单条视频超过 2GB 下载限制")
                                file.write(chunk)
                    if not size:
                        raise ValueError("下载的视频为空")
                import av
                with av.open(str(partial)) as media:
                    if not media.streams.audio and not media.streams.video:
                        raise ValueError("下载文件没有有效音视频流")
                partial.replace(path)
                item["download_engine"] = "douyin-share"
                return str(path)
            except Exception as exc:
                errors.append(str(exc))
                partial.unlink(missing_ok=True)
        raise ValueError("抖音媒体下载失败：" + "；".join(errors[-2:]))
