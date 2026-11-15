import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.benchmark import build_benchmark
from src.gpu_benchmark import build_gpu_inputs, score_gpu_records


class GpuBenchmarkTests(unittest.TestCase):
    def test_gpu_payload_contains_only_source_prompt_not_gold_or_confirmations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_benchmark(root)
            inputs = build_gpu_inputs(root)
            self.assertEqual(len(inputs), 6)
            for item in inputs:
                self.assertEqual(set(item), {'case_id', 'business', 'variant', 'prompt', 'input_sha256'})
                self.assertNotIn('case_author', item['prompt'])
                self.assertEqual(hashlib.sha256(item['prompt'].encode()).hexdigest(), item['input_sha256'])

    def test_scoring_preserves_bad_json_and_checks_input_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_benchmark(root / 'cases')
            item = build_gpu_inputs(root / 'cases')[0]
            runs = root / 'runs/model'
            runs.mkdir(parents=True)
            record = {'case_id': item['case_id'], 'model': 'test-only-model', 'input_sha256': item['input_sha256'], 'raw_text': '{broken', 'finish_reason': 'stop'}
            path = runs / 'result.json'
            path.write_text(json.dumps(record))
            summary = score_gpu_records(root / 'runs', root / 'cases')
            self.assertEqual(summary[0]['evaluation']['fields']['correct'], 0)
            self.assertTrue(summary[0]['parse_error'])
            self.assertEqual(json.loads(path.read_text())['raw_text'], '{broken')
            record['input_sha256'] = 'wrong'
            path.write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                score_gpu_records(root / 'runs', root / 'cases')


if __name__ == '__main__':
    unittest.main()
