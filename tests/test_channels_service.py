import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import Mock, patch
import requests
from channels_server import make_handler
from channels_auth import parse_yuanbao


class ChannelsServiceTests(unittest.TestCase):
    def test_service_authorization_and_link_validation(self):
        resolver = Mock(return_value={"errCode": 0, "data": {"feedInfo": {"videoUrl": "https://example.org/video"}}})
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler("test-key", resolver))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/api/fetch_video_profile"
        try:
            response = requests.post(url, json={"url": "https://weixin.qq.com/sph/abc"}, timeout=3)
            self.assertEqual(response.status_code, 401)
            resolver.assert_not_called()
            headers = {"Authorization": "Bearer test-key"}
            response = requests.post(url, json={"url": "https://example.org"}, headers=headers, timeout=3)
            self.assertEqual(response.status_code, 400)
            resolver.assert_not_called()
            response = requests.post(url, json={"url": "https://weixin.qq.com/sph/abc"}, headers=headers, timeout=3)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["errCode"], 0)
            resolver.side_effect = RuntimeError("private-cookie-secret")
            response = requests.post(url, json={"url": "https://weixin.qq.com/sph/abc"}, headers=headers, timeout=3)
            self.assertEqual(response.status_code, 502)
            self.assertNotIn("private-cookie-secret", response.text)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_yuanbao_auth_does_not_import_unrelated_cookies(self):
        with patch('channels_auth.requests.Session') as factory:
            session = factory.return_value.__enter__.return_value
            session.post.return_value.json.return_value = {"code": 0, "data": {"playable_url": "https://channels.weixin.qq.com/finder-preview/pages/feed?token=abc&eid=export%2F123"}}
            cookies = [{"domain": ".yuanbao.tencent.com", "name": "session", "value": "local-secret"},
                       {"domain": "example.org", "name": "other", "value": "unrelated"}]
            result = parse_yuanbao("https://weixin.qq.com/sph/abc", cookies)
            self.assertIn("token=abc", result)
            self.assertEqual(session.cookies.set.call_count, 1)
            self.assertEqual(session.post.call_args.args[0], "https://yuanbao.tencent.com/api/weixin/get_parse_result")
            session.post.return_value.json.return_value = {"code": 0, "data": {"playable_url": "https://example.org/feed?token=abc&eid=123"}}
            with self.assertRaisesRegex(ValueError, '播放凭证'):
                parse_yuanbao("https://weixin.qq.com/sph/abc", cookies)

    def test_authentication_failure_is_actionable(self):
        with patch('channels_auth.requests.Session') as factory:
            factory.return_value.__enter__.return_value.post.return_value.status_code = 401
            with self.assertRaisesRegex(ValueError, '重新扫码登录'):
                parse_yuanbao("https://weixin.qq.com/sph/abc", [])

    def test_no_unauthenticated_service(self):
        with self.assertRaises(ValueError):
            make_handler("")
