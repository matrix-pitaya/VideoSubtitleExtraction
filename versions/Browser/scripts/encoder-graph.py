"""Remove unused ONNX encoder graph outputs, preserving every node and weight byte."""
import hashlib
import mmap
from pathlib import Path

def varint(data, offset):
    value = shift = 0
    while True:
        byte = data[offset]; offset += 1; value |= (byte & 127) << shift
        if byte < 128: return value, offset
        shift += 7
        if shift > 63: raise ValueError('Invalid protobuf varint')

def fields(data, start, end):
    while start < end:
        original = start; tag, start = varint(data, start); kind = tag & 7
        if kind == 2:
            length, payload = varint(data, start); finish = payload + length
        elif kind == 0:
            _, finish = varint(data, start); payload = start
        elif kind in (1, 5):
            payload = start; finish = start + (8 if kind == 1 else 4)
        else: raise ValueError('Unsupported protobuf wire type')
        if finish > end: raise ValueError('Truncated protobuf')
        yield tag >> 3, kind, original, payload, finish
        start = finish

def encoded(value):
    result = bytearray()
    while value >= 128: result.append((value & 127) | 128); value >>= 7
    result.append(value); return result

def prune(source: Path, destination: Path):
    with source.open('rb') as file, mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as data:
        graphs = [f for f in fields(data, 0, len(data)) if f[0] == 7 and f[1] == 2]
        if len(graphs) != 1: raise ValueError('Expected one ONNX graph')
        _, _, graph_start, graph_payload, graph_end = graphs[0]
        kept = []; outputs = []
        for number, kind, start, payload, end in fields(data, graph_payload, graph_end):
            if number == 12:
                name = next(bytes(data[p:e]).decode() for n, k, s, p, e in fields(data, payload, end) if n == 1 and k == 2)
                outputs.append(name)
                if name != 'last_hidden_state': continue
            kept.append((start, end))
        if outputs.count('last_hidden_state') != 1: raise ValueError('Encoder output mismatch')
        _, length_start = varint(data, graph_start)
        with destination.open('wb') as output:
            def copy(start, end):
                while start < end:
                    finish = min(start + 4 * 1024 * 1024, end); output.write(data[start:finish]); start = finish
            copy(0, length_start)
            output.write(encoded(sum(end-start for start,end in kept)))
            for start,end in kept: copy(start,end)
            copy(graph_end,len(data))
    digest = hashlib.sha256()
    with destination.open('rb') as file:
        while chunk := file.read(4 * 1024 * 1024): digest.update(chunk)
    return {'bytes': destination.stat().st_size, 'sha256': digest.hexdigest(), 'removedOutputs': [n for n in outputs if n != 'last_hidden_state']}
