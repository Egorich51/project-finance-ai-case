import json
import unittest
from pathlib import Path
from unittest.mock import patch
from src.industrial_evaluation import score_records

ROOT=Path(__file__).resolve().parents[1]/'studies/industrial-v2'

class IndustrialSavedTests(unittest.TestCase):
    def test_saved_first_responses_reproduce_report_counts(self):
        rows=score_records(ROOT)
        self.assertEqual(len(rows),12)
        for suffix,values,grounded,errors in [('1.5B-Instruct',0,0,6),('7B-Instruct',82,76,0)]:
            group=[r for r in rows if r['model'].endswith(suffix)]
            self.assertEqual(sum(r['evaluation']['total'] for r in group),114)
            self.assertEqual(sum(r['evaluation']['values_correct'] for r in group),values)
            self.assertEqual(sum(r['evaluation']['grounded_correct'] for r in group),grounded)
            self.assertEqual(sum(bool(r['parse_error']) for r in group),errors)
        saved=json.loads((ROOT/'results/summary.json').read_text())
        self.assertEqual(saved['records'],rows)

    def test_changed_reference_rejected_before_scoring(self):
        original=Path.read_bytes
        def altered(path):
            data=original(path)
            return data+b' ' if path==ROOT/'reference.json' else data
        with patch.object(Path,'read_bytes',altered):
            with self.assertRaisesRegex(ValueError,'Frozen artifact mismatch'):
                score_records(ROOT)
