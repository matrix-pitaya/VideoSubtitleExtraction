"""Platform adapters for resolving public video share links."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

MOBILE_UA = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"


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
