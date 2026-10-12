import runpy
from pathlib import Path
import tempfile
import unittest

api = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/encoder-graph.py'))
encode = api['encoded']
def field(number, payload):
    return bytes(encode(number * 8 + 2)) + bytes(encode(len(payload))) + payload
def output(name):
    return field(12, field(1, name.encode()))

class EncoderGraphTests(unittest.TestCase):
    def test_only_output_declarations_change(self):
        preserved = field(1, b'node-bytes') + field(5, bytes(range(256)) * 8192) + field(11, b'input')
        original = field(1, b'producer') + field(7, preserved + output('last_hidden_state') + output('encoder_attentions.0')) + field(14, b'metadata')
        expected = field(1, b'producer') + field(7, preserved + output('last_hidden_state')) + field(14, b'metadata')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.onnx'; target = Path(directory) / 'target.onnx'
            source.write_bytes(original); result = api['prune'](source, target)
            self.assertEqual(target.read_bytes(), expected)
            self.assertEqual(result['removedOutputs'], ['encoder_attentions.0'])

    def test_missing_required_output_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.onnx'; target = Path(directory) / 'target.onnx'
            source.write_bytes(field(7, output('wrong_output')))
            with self.assertRaisesRegex(ValueError, 'Encoder output mismatch'): api['prune'](source, target)

    def test_truncated_model_refused(self):
        with self.assertRaisesRegex(ValueError, 'Truncated'): list(api['fields'](b'\x3a\x05x', 0, 3))

if __name__ == '__main__': unittest.main()
