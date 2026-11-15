import json
import unittest
from pathlib import Path

from src.finance import calculate
from src.gpu_benchmark import score_gpu_records


class SavedGpuTests(unittest.TestCase):
    def test_saved_scores_reproduce_from_twelve_first_responses(self):
        root = Path(__file__).resolve().parents[1] / 'benchmarks'
        fresh = score_gpu_records(root / 'results/raw', root / 'cases')
        saved = json.loads((root / 'results/summary.json').read_text())
        self.assertEqual(len(fresh), 12)
        self.assertEqual(fresh, saved['cases'])
        self.assertEqual(len({(r['model'], r['case_id']) for r in fresh}), 12)
        for record in (root / 'results/raw').glob('*/*.json'):
            data = json.loads(record.read_text())
            if 'case_id' in data:
                self.assertTrue(data['raw_text'])
                self.assertNotIn('error', data)

    def test_two_business_financial_examples_match_reference_values(self):
        root = Path(__file__).resolve().parents[1] / 'benchmarks'
        for business, need, amount, gap in [('small', 5, 3.289473684, 1.710526316), ('medium', 75, 59.259259259, 15.740740741)]:
            with self.subTest(business=business):
                data = json.loads((root / 'cases' / business / 'complete/confirmed.json').read_text())
                expected = calculate(data)
                saved = json.loads((root / 'examples' / business / 'calculation.json').read_text())
                self.assertEqual(expected, saved)
                self.assertEqual(saved['need'], need)
                self.assertAlmostEqual(saved['proposed_amount'], amount, places=6)
                self.assertAlmostEqual(saved['funding_gap'], gap, places=6)
