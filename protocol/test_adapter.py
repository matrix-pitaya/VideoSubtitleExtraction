import json
from pathlib import Path
import unittest
from python_adapter import item_to_task


class ProtocolTests(unittest.TestCase):
    def test_shared_fixture_has_no_internal_paths(self):
        fixture = json.loads((Path(__file__).parent / 'examples/task-v1.json').read_text(encoding='utf-8'))
        item = {'id': fixture['taskId'], 'title': fixture['title'], 'status': '完成', 'segments': fixture['segments'], 'path': 'private-path', 'source': 'private-link'}
        self.assertEqual(item_to_task(item), fixture)

    def test_no_speech_clears_old_hallucination(self):
        task = item_to_task({'id': '1', 'title': 'BGM', 'status': '无口播', 'segments': [{'start': 0, 'end': 1, 'text': '旧幻觉'}]})
        self.assertEqual(task['segments'], [])

    def test_nonfinite_and_overlapping_timestamps_are_rejected(self):
        for segments in [[{'start': float('nan'), 'end': 1, 'text': 'a'}], [{'start': 0, 'end': 2, 'text': 'a'}, {'start': 1, 'end': 3, 'text': 'b'}]]:
            with self.assertRaises(ValueError): item_to_task({'id': '1', 'title': 'bad', 'segments': segments})

if __name__ == '__main__': unittest.main()
