"""Local OCR for text-only videos; timestamps reflect one-second frame sampling."""
from difflib import SequenceMatcher
from functools import lru_cache


@lru_cache(maxsize=1)
def engine():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


def merge_sample(segments: list, start: float, end: float, text: str) -> None:
    if not text:
        return
    if segments and start <= segments[-1]['end'] + 0.05 and SequenceMatcher(None, segments[-1]['text'], text).ratio() >= 0.9:
        segments[-1]['end'] = end
    else:
        segments.append({'start': start, 'end': end, 'text': text})


def extract_screen_text(path: str, on_progress=None) -> list[dict]:
    import av
    segments = []
    next_sample = 0.0
    with av.open(path) as media:
        if not media.streams.video:
            return []
        stream = media.streams.video[0]
        duration = float(stream.duration * stream.time_base) if stream.duration is not None else (media.duration / 1000000 if media.duration else None)
        for frame in media.decode(stream):
            if frame.time is None:
                continue
            time = float(frame.time)
            if time + 0.001 < next_sample:
                continue
            next_sample = time + 1.0
            image = frame.to_ndarray(format='bgr24')
            results, _ = engine()(image)
            lines = []
            for box, text, score in results or []:
                if score >= 0.65 and text.strip():
                    lines.append((min(point[1] for point in box), min(point[0] for point in box), text.strip()))
            lines.sort(key=lambda line: (round(line[0] / 15), line[1]))
            text = '\n'.join(line[2] for line in lines)
            end = min(time + 1.0, duration) if duration else time + 1.0
            if end > time:
                merge_sample(segments, time, end, text)
            if on_progress:
                on_progress(f'识别画面文字 · {time:.0f} 秒')
    return segments
