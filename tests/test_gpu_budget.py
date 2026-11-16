import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'scripts/run_gpu_benchmark.py'
spec = importlib.util.spec_from_file_location('gpu_worker', path)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class BudgetTests(unittest.TestCase):
    def test_larger_frozen_budget_and_no_silent_truncation(self):
        worker.validate_token_budget(7000, 3000, 12288)
        with self.assertRaises(ValueError):
            worker.validate_token_budget(10000, 3000, 12288)
        with self.assertRaises(ValueError):
            worker.validate_token_budget(1, 0, 12288)
