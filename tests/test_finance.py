import unittest

from src.finance import calculate
from tests.common import confirmed_case


class FinanceTests(unittest.TestCase):
    def test_known_case(self):
        result = calculate(confirmed_case())
        for key, expected in [('need', 60), ('capacity_base', 57.14285714), ('capacity_stress', 45.71428571), ('proposed_amount', 45.71428571), ('funding_gap', 14.28571429)]:
            with self.subTest(key=key):
                self.assertAlmostEqual(result[key], expected, places=6)
        self.assertAlmostEqual(result['stress_schedule'][0]['cfads'], 19.2)
        self.assertAlmostEqual(result['stress_schedule'][0]['debt_service'], 16)
        self.assertAlmostEqual(result['stress_schedule'][0]['dscr'], 1.2)

    def test_zero_rate(self):
        data = confirmed_case()
        data['rate'] = 0
        result = calculate(data)
        self.assertAlmostEqual(result['capacity_stress'], 80)
        self.assertEqual(result['proposed_amount'], 60)
        self.assertEqual(result['funding_gap'], 0)

    def test_nonpositive_cfads(self):
        for value in (0, -1):
            with self.subTest(value=value):
                data = confirmed_case()
                data['cfads'][0] = value
                result = calculate(data)
                self.assertEqual(result['capacity_stress'], 0)
                self.assertEqual(result['proposed_amount'], 0)
                self.assertEqual(result['funding_gap'], 60)

    def test_invalid_terms(self):
        for field, value in [('rate', -0.1), ('years', 0), ('cfads', [1]), ('equity', None), ('rate', float('inf'))]:
            with self.subTest(field=field):
                data = confirmed_case()
                data[field] = value
                with self.assertRaises(ValueError):
                    calculate(data)

    def test_schedule_conserves_principal(self):
        result = calculate(confirmed_case())
        for schedule in (result['base_schedule'], result['stress_schedule']):
            self.assertEqual(len(schedule), 5)
            self.assertAlmostEqual(sum(r['principal'] for r in schedule), result['proposed_amount'])
            self.assertAlmostEqual(schedule[-1]['closing_debt'], 0)
            for previous, current in zip(schedule, schedule[1:]):
                self.assertAlmostEqual(previous['closing_debt'], current['opening_debt'])
        self.assertAlmostEqual(min(r['dscr'] for r in result['stress_schedule']), 1.2)

    def test_equity_above_budget_has_no_debt(self):
        data = confirmed_case()
        data['equity'] = 110
        data['resolutions'][1]['value'] = 110
        result = calculate(data)
        self.assertEqual(result['need'], 0)
        self.assertEqual(result['proposed_amount'], 0)
        self.assertTrue(all(r['dscr'] is None for r in result['base_schedule']))


if __name__ == '__main__':
    unittest.main()
