import copy
import json
import tempfile
import unittest
from pathlib import Path

from src.extraction import evaluate, prepare_input, validate_confirmed
from src.fixtures import build_case
from tests.common import confirmed_case


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        build_case(self.root)
        self.gold = json.loads((self.root / 'gold.json').read_text())

    def test_input_preserves_locators(self):
        text = prepare_input(self.root / 'source')
        self.assertIn('[project.docx|paragraph:4]', text)
        self.assertIn('[financials.xlsx|Forecast!B4] 110000', text)
        self.assertIn('[financials.xlsx|Forecast!C4] thousand_rub', text)
        self.assertIn('[financials.xlsx|Forecast!B5] null', text)
        self.assertIn('[financials.xlsx|Forecast!F10] 32', text)
        self.assertNotIn('candidates', text)

    def test_missing_equity_blocks(self):
        data = confirmed_case()
        data['equity'] = None
        self.assertTrue(any('equity' in e for e in validate_confirmed(data)))
        self.assertEqual(validate_confirmed(confirmed_case()), [])

    def test_unresolved_budget_blocks(self):
        data = confirmed_case()
        data['resolutions'] = [r for r in data['resolutions'] if r['field'] != 'budget']
        self.assertTrue(any('budget' in e for e in validate_confirmed(data)))
        data = confirmed_case()
        data['resolutions'][0]['value'] = 110
        self.assertTrue(validate_confirmed(data))

    def test_units_and_periods_matter(self):
        predicted = copy.deepcopy(self.gold)
        baseline = evaluate(predicted, self.gold)
        self.assertEqual(baseline['fields']['correct'], 11)
        predicted['fields']['cfads_1']['unit'] = 'thousand_rub'
        predicted['fields']['cfads_2']['period'] = 3
        predicted['fields']['budget']['candidates'][1]['unit'] = 'million_rub'
        result = evaluate(predicted, self.gold)
        self.assertEqual(result['fields']['correct'], 8)
        self.assertEqual(set(result['incorrect_fields']), {'cfads_1', 'cfads_2', 'budget'})

    def test_equivalent_money_units_are_accepted(self):
        predicted = copy.deepcopy(self.gold)
        predicted['fields']['cfads_1'].update(value=24000, unit='thousand_rub')
        self.assertEqual(evaluate(predicted, self.gold)['fields']['correct'], 11)

    def test_missing_prediction_counts_wrong(self):
        predicted = copy.deepcopy(self.gold)
        del predicted['fields']['equity']
        result = evaluate(predicted, self.gold)
        self.assertEqual(result['fields']['correct'], 10)
        self.assertEqual(result['fields']['total'], 11)
        self.assertEqual(evaluate({}, self.gold)['fields']['correct'], 0)

    def test_source_and_issue_errors_are_visible(self):
        predicted = copy.deepcopy(self.gold)
        predicted['fields']['rate']['sources'][0]['locator'] = 'paragraph:1'
        predicted['issues'] = [{'field': 'rate', 'kind': 'missing', 'sources': []}]
        result = evaluate(predicted, self.gold)
        self.assertEqual(result['sources']['correct'], 11)
        self.assertEqual(result['sources']['total'], 12)
        self.assertEqual(result['issues']['true_positive'], 0)
        self.assertEqual(result['issues']['false_positive'], 1)
        self.assertEqual(result['issues']['false_negative'], 2)

    def test_nonfinite_bool_and_invalid_scenario_are_rejected(self):
        for key, value in [('rate', float('nan')), ('budget', True), ('stress_factor', 1.1), ('dscr_floor', 0), ('years', 2.5), ('unit', 'rub')]:
            with self.subTest(key=key, value=value):
                data = confirmed_case()
                data[key] = value
                self.assertTrue(validate_confirmed(data))

    def test_malformed_model_collections_are_scored_without_crashing(self):
        predicted = copy.deepcopy(self.gold)
        predicted['issues'] = None
        predicted['fields']['rate']['sources'] = [{'file': [], 'locator': {}}]
        result = evaluate(predicted, self.gold)
        self.assertEqual(result['issues']['false_negative'], 2)
        self.assertEqual(result['sources']['correct'], 11)

    def test_boolean_period_does_not_count_as_year_one(self):
        predicted = copy.deepcopy(self.gold)
        predicted['fields']['cfads_1']['period'] = True
        self.assertEqual(evaluate(predicted, self.gold)['fields']['correct'], 10)

    def test_nonstring_units_count_wrong_without_aborting_evaluation(self):
        for unit in (['million_rub'], {'unit': 'million_rub'}):
            with self.subTest(unit=unit):
                predicted = copy.deepcopy(self.gold)
                predicted['fields']['cfads_1']['unit'] = unit
                result = evaluate(predicted, self.gold)
                self.assertEqual(result['fields']['correct'], 10)
                self.assertIn('cfads_1', result['incorrect_fields'])

    def test_null_money_values_accept_equivalent_monetary_units(self):
        predicted = copy.deepcopy(self.gold)
        predicted['fields']['equity']['unit'] = 'thousand_rub'
        self.assertEqual(evaluate(predicted, self.gold)['fields']['correct'], 11)


if __name__ == '__main__':
    unittest.main()
