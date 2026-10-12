"""Explicit adapter for existing Python order items; not a replacement for core.py."""
import math


def item_to_task(item, language='zh'):
    states = {'待处理': 'ready', '处理中': 'running', '完成': 'completed', '无口播': 'no_speech', '失败': 'failed'}
    state = states.get(item.get('status'), 'ready')
    segments = [] if state == 'no_speech' else [
        {'start': float(s['start']), 'end': float(s['end']), 'text': str(s['text']).strip()}
        for s in item.get('segments', [])]
    previous = 0
    for s in segments:
        if not math.isfinite(s['start']) or not math.isfinite(s['end']) or s['start'] < previous or s['end'] <= s['start'] or not s['text']:
            raise ValueError('Invalid subtitle segment')
        previous = s['end']
    if language not in ('zh', 'auto'):
        raise ValueError('Unsupported language in protocol v1')
    task = {'schemaVersion': '1.0', 'taskId': item['id'], 'title': item['title'], 'language': language, 'state': state, 'segments': segments}
    if state == 'failed':
        task['error'] = {'code': 'TRANSCRIPTION_FAILED', 'message': '处理失败，请在本机工作台查看详情。'}
    return task
