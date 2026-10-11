import tempfile
import unittest
import wave
import json
from urllib.parse import urlencode
from pathlib import Path
from unittest.mock import Mock, patch

from link_download import is_douyin, video_id, douyin_detail
from link_download import (is_xiaohongshu, unwrap_xhs_login, xiaohongshu_detail,
                           is_wechat_channels, wechat_detail, wechat_media_urls, download_wechat_channels)


class LinkTests(unittest.TestCase):
    def test_xhs_login_unwrap_preserves_signed_query(self):
        target = 'http://www.xiaohongshu.com/discovery/item/abc123?xsec_token=abc%3D'
        login = 'https://www.xiaohongshu.com/login?' + urlencode({'redirectPath': target})
        self.assertEqual(unwrap_xhs_login(login), target.replace('http:', 'https:', 1))
        self.assertTrue(is_xiaohongshu('https://xhslink.cn/test'))
        self.assertFalse(is_xiaohongshu('https://xiaohongshu.com.evil.test/a'))
        with self.assertRaises(ValueError):
            unwrap_xhs_login('https://www.xiaohongshu.com/login?' + urlencode({'redirectPath': 'https://example.org'}))

    def test_xhs_mobile_state_and_wrong_note(self):
        session = Mock()
        response = session.get.return_value
        response.url = 'https://www.xiaohongshu.com/discovery/item/abc123'
        note = {'noteId': 'abc123', 'title': '正确标题', 'video': {}}
        response.text = '<script>window.__INITIAL_STATE__=' + json.dumps({'noteData': {'data': {'noteData': note}}}) + ';</script>'
        self.assertEqual(xiaohongshu_detail(session, response.url)['title'], '正确标题')
        with self.assertRaisesRegex(ValueError, '所请求的作品'):
            xiaohongshu_detail(session, 'https://www.xiaohongshu.com/explore/def456')

    def test_xhs_desktop_state_and_login_response(self):
        session = Mock()
        first = Mock(url='https://www.xiaohongshu.com/login?' + urlencode({'redirectPath': 'https://www.xiaohongshu.com/explore/abc123'}))
        second = Mock(url='https://www.xiaohongshu.com/explore/abc123')
        second.text = '<script>window.__INITIAL_STATE__=' + json.dumps({'note': {'noteDetailMap': {'abc123': {'note': {'noteId': 'abc123'}}}}}) + ';</script>'
        session.get.side_effect = [first, second]
        self.assertEqual(xiaohongshu_detail(session, first.url)['noteId'], 'abc123')

    def test_wechat_api_uses_original_share_id(self):
        session = Mock(cookies=[])
        session.post.return_value.json.return_value = {'errCode': 0, 'data': {'feedInfo': {'description': '作品'}}}
        self.assertEqual(wechat_detail(session, 'https://weixin.qq.com/sph/abc123')['description'], '作品')
        arguments = session.post.call_args.kwargs
        self.assertEqual(arguments['json']['shortUri'], 'abc123')
        self.assertIn('_rid', arguments['params'])
        self.assertFalse(is_wechat_channels('https://weixin.qq.com.evil.test/sph/abc'))

    def test_wechat_cover_is_never_video(self):
        self.assertEqual(wechat_media_urls({'coverUrl': 'https://example.org/cover.jpg'}), [])
        with patch('link_download.new_session') as new_session, patch('link_download.wechat_detail', return_value={'coverUrl': 'cover'}), patch('link_download.download_media') as media:
            with self.assertRaisesRegex(ValueError, '没有视频地址'):
                download_wechat_channels({'id': '123', 'source': 'https://weixin.qq.com/sph/abc'}, Path('unused'))
            media.assert_not_called()

    def test_wechat_resolver_does_not_receive_platform_cookies(self):
        with patch('link_download.new_session'), patch('link_download.load_cookies'), patch('link_download.wechat_detail', return_value={}), patch('link_download.requests.post') as post, patch('link_download.download_media', return_value='video.mp4'):
            post.return_value.json.return_value = {'data': {'feedInfo': {'h264VideoInfo': {'videoUrl': 'https://example.org/video.mp4'}}}}
            result = download_wechat_channels({'id': '123', 'source': 'https://weixin.qq.com/sph/abc'}, Path('unused'), 'cookies.txt', 'https://resolver.example.org/api', 'secret')
            self.assertEqual(result, 'video.mp4')
            self.assertEqual(post.call_args.kwargs['headers'], {'Authorization': 'Bearer secret'})
            self.assertNotIn('cookies', post.call_args.kwargs)

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
