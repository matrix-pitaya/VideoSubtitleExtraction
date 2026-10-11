import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock

from link_download import is_douyin, video_id, douyin_detail


class LinkTests(unittest.TestCase):
    def test_url_recognition(self):
        self.assertTrue(is_douyin('https://v.douyin.com/abc/'))
        self.assertFalse(is_douyin('https://douyin.com.example.org/video/123'))
        self.assertEqual(video_id('https://www.iesdouyin.com/share/video/123/'), '123')
        self.assertEqual(video_id('https://www.douyin.com/?modal_id=456'), '456')

    def test_short_link_matches_requested_video(self):
        session = Mock()
        redirect = Mock(url='https://www.douyin.com/video/123')
        response = Mock()
        response.json.return_value = {'aweme_details': [{'aweme_id': '999'}, {'aweme_id': '123', 'desc': '正确视频'}]}
        session.get.side_effect = [redirect, response]
        self.assertEqual(douyin_detail(session, 'https://v.douyin.com/abc/')['desc'], '正确视频')

    def test_missing_video_is_failure(self):
        session = Mock()
        session.get.return_value.json.return_value = {'aweme_details': [{'aweme_id': '999'}]}
        with self.assertRaisesRegex(ValueError, '未返回这条视频'):
            douyin_detail(session, 'https://www.douyin.com/video/123')

    def test_real_audio_decoder_compatibility(self):
        from faster_whisper.audio import decode_audio
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'silence.wav'
            with wave.open(str(path), 'wb') as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(b'\0\0' * 16000)
            self.assertEqual(len(decode_audio(str(path))), 16000)
