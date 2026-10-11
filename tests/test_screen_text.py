import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import core
from screen_text import merge_sample


class ScreenTextTests(unittest.TestCase):
    def test_merges_repeated_text_but_preserves_gaps(self):
        segments = []
        merge_sample(segments, 0, 1, '画面字幕')
        merge_sample(segments, 1, 2, '画面字幕')
        merge_sample(segments, 3, 4, '画面字幕')
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]['end'], 2)

    def test_auto_ocr_fallback_preserves_original(self):
        class SilentModel:
            def transcribe(self, path, **kwargs):
                return iter([]), SimpleNamespace(language='zh')
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, 'ROOT', Path(tmp)):
            media = Path(tmp) / 'original.mp4'
            media.touch()
            order = core.create_order('无口播视频')
            item = core.add_item(order, str(media), '测试', str(media))
            segments = [{'start': 0, 'end': 2, 'text': '画面文案'}]
            with patch('screen_text.extract_screen_text', return_value=segments) as ocr:
                core.process_item(order, item, SilentModel(), 'zh')
            self.assertEqual(item['status'], '完成')
            self.assertEqual(item['text'], '画面文案')
            self.assertIn('OCR', item['text_origin'])
            self.assertTrue(media.exists())
            ocr.assert_called_once()
