import json
import tempfile
import unittest
from pathlib import Path

from src.industrial_v2 import build_jobs, audit_project


ROOT = Path(__file__).resolve().parents[1] / 'studies/industrial-v2'


class IndustrialTests(unittest.TestCase):
    def test_six_source_only_jobs_and_periods(self):
        jobs, gold = build_jobs(ROOT / 'input')
        self.assertEqual(len(jobs), 6)
        self.assertEqual(len(gold), 6)
        for job in jobs:
            self.assertNotIn('business_plan_v2', job['prompt'])
            self.assertNotIn('Входные данные.json', job['prompt'])
            self.assertIn('MD:L', job['prompt'])
            self.assertTrue(gold[job['case_id']]['fields'])
        project = gold['01_terms']['fields']
        self.assertEqual(project['budget_total']['value'], 107.6)
        self.assertEqual(project['company_cash_contribution']['value'], 7.6)
        self.assertEqual(project['draw_2027_01']['period'], '2027-01')
        forecast = gold['01_financials']['fields']
        self.assertEqual(forecast['revenue_2025']['value'], 180)
        self.assertEqual(forecast['revenue_2025']['period'], 2025)
        self.assertEqual(forecast['cfads_2027']['value'], 13.46)
        self.assertEqual(forecast['cfads_2027']['period'], 2027)

    def test_monthly_audit_reproduces_three_supplied_models(self):
        expected = {'01': (-5.840427271, 0.189964167, 1.187976260),
                    '02': (24.324975790, 0.413148441, 2.737243807),
                    '03': (-9.562913267, 0.173624433, 1.454213330)}
        for file in sorted((ROOT / 'input').glob('*/Входные данные.json')):
            data = json.loads(file.read_text())
            result = audit_project(data)
            npv, irr, dscr = expected[data['id']]
            self.assertAlmostEqual(result['npv'], npv, places=6)
            self.assertAlmostEqual(result['irr'], irr, places=6)
            self.assertAlmostEqual(result['min_dscr_repayment'], dscr, places=6)
            self.assertEqual(len(result['monthly']), 60)
            self.assertAlmostEqual(result['monthly'][-1]['debt_closing'], 0, places=8)
            self.assertLess(result['max_reference_difference'], 1e-7)
        dry = json.loads(next((ROOT / 'input').glob('03*/Входные данные.json')).read_text())
        result = audit_project(dry)
        self.assertEqual(result['monthly'][1]['draw'], 0)
        self.assertEqual(result['monthly'][3]['draw'], 20)
        self.assertEqual(result['monthly'][6]['draw'], 15)
        self.assertEqual(result['monthly'][17]['principal'], 0)
        self.assertGreater(result['monthly'][18]['principal'], 0)
        self.assertLess(result['annual'][0]['cfads'], 0)
        self.assertGreater(result['minimum_cash'], 0)
