import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core
from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def test_create_order_and_render(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, "ROOT", Path(tmp)):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
            app.run(timeout=20)
            self.assertEqual(len(app.exception), 0)
            app.text_input[0].set_value("客户测试")
            app.button[0].click().run(timeout=20)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(core.load_orders()[0]["name"], "客户测试")
            self.assertEqual(app.metric[0].value, "0")
