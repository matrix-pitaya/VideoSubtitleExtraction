import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from zipfile import ZipFile
import core


class WorkflowTests(unittest.TestCase):
    def test_link_media_cleanup_on_success_and_failure(self):
        class Model:
            def transcribe(self, path, **kwargs):
                return iter([SimpleNamespace(start=0, end=1, text="口播")]), SimpleNamespace(language="zh")
        for fail in [False, True]:
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as tmp, patch.object(core, "ROOT", Path(tmp)):
                order = core.create_order("链接订单")
                item = core.add_item(order, "https://example.com/video", "视频")
                def downloader(item, folder, cookie):
                    folder.mkdir(parents=True)
                    path = folder / "video.mp4"
                    path.write_bytes(b"test")
                    (folder / "video.part").touch()
                    if fail:
                        raise ValueError("下载中断")
                    return str(path)
                with patch.object(core, "download", side_effect=downloader):
                    core.process_item(order, item, Model(), "zh")
                self.assertFalse((Path(tmp) / order["id"] / "media" / item["id"]).exists())
                self.assertEqual(item["path"], "")
                self.assertEqual(item["status"], "失败" if fail else "完成")
                if not fail:
                    self.assertEqual(item["text"], "口播")

    def test_cleanup_rejects_external_directory(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, "ROOT", Path(tmp) / "data"):
            original = Path(tmp) / "original"
            original.mkdir()
            video = original / "video.mp4"
            video.touch()
            with self.assertRaises(OSError):
                core.cleanup_download(original)
            self.assertTrue(video.exists())

    def test_links_and_timestamps(self):
        self.assertEqual(core.extract_links("分享 https://v.douyin.com/abc/。\nhttps://v.douyin.com/abc/"), ["https://v.douyin.com/abc/"])
        self.assertEqual(core.timestamp(59.9996), "00:01:00,000")
        self.assertIn("00:00:01,250 --> 00:00:02,500", core.srt([{"start": 1.25, "end": 2.5, "text": "你好"}]))

    def test_failure_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, "ROOT", Path(tmp)):
            order = core.create_order("测试")
            item = core.add_item(order, "https://example.com/a", "视频")
            with patch.object(core, "download", side_effect=ValueError("无法下载")):
                core.process_item(order, item, None, "zh")
            self.assertEqual(core.load_orders()[0]["items"][0]["status"], "失败")
            self.assertEqual(item["error"], "无法下载")

    def test_delivery_content(self):
        from openpyxl import load_workbook
        from docx import Document
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, "ROOT", Path(tmp)):
            order = core.create_order("客户")
            item = core.add_item(order, "local.mp4", "=1+1")
            item.update(status="完成", text="你好世界", segments=[{"start": 0, "end": 1.5, "text": "你好世界"}])
            archive = core.export_order(order)
            with ZipFile(archive) as zf:
                self.assertEqual(len(zf.namelist()), 5)
                self.assertIn("你好世界", zf.read("001_=1+1.srt").decode("utf-8-sig"))
            folder = archive.parent
            book = load_workbook(folder / "文案汇总.xlsx")
            self.assertEqual(book.active["B2"].data_type, "s")
            self.assertEqual(book.active["E2"].value, "你好世界")
            self.assertIn("你好世界", [p.text for p in Document(folder / "文案汇总.docx").paragraphs])

    def test_successful_transcription_is_persisted(self):
        class FakeModel:
            def transcribe(self, path, **kwargs):
                return iter([SimpleNamespace(start=0.2, end=1.2, text=" 测试口播 ")]), SimpleNamespace(language="zh")
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, "ROOT", Path(tmp)):
            media = Path(tmp) / "test.mp4"
            media.touch()
            order = core.create_order("测试")
            item = core.add_item(order, str(media), "测试视频", str(media))
            core.process_item(order, item, FakeModel(), "zh")
            restored = core.load_orders()[0]["items"][0]
            self.assertEqual(restored["status"], "完成")
            self.assertEqual(restored["text"], "测试口播")
            self.assertEqual(restored["segments"][0]["start"], 0.2)
            self.assertTrue(media.exists())


if __name__ == "__main__":
    unittest.main()
