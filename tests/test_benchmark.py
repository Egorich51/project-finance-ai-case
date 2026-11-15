import json
import tempfile
import unittest
from pathlib import Path

from docx import Document
from openpyxl import load_workbook

from src.benchmark import build_benchmark
from src.extraction import evaluate, prepare_input, validate_confirmed
from src.finance import calculate
from src.report import write_outputs


class BenchmarkTests(unittest.TestCase):
    def test_two_businesses_and_three_controlled_variants(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_benchmark(root)
            cases = list(root.glob('*/*/gold.json'))
            self.assertEqual(len(cases), 6)
            for business, budget, equity, cfads in [('small', 8, 3, [2, 2.2, 2.4, 2.6, 2.8]), ('medium', 120, 45, [32, 36, 40, 43, 46])]:
                for variant in ('complete', 'budget_conflict', 'missing_equity'):
                    case = root / business / variant
                    gold = json.loads((case / 'gold.json').read_text())
                    confirmed = json.loads((case / 'confirmed.json').read_text())
                    self.assertEqual(confirmed['budget'], budget)
                    self.assertEqual(confirmed['equity'], equity)
                    self.assertEqual(confirmed['cfads'], cfads)
                    self.assertEqual(validate_confirmed(confirmed), [])
                    self.assertEqual(evaluate(gold, gold)['fields']['correct'], 11)
                    expected = [] if variant == 'complete' else [('budget', 'conflict')] if variant == 'budget_conflict' else [('equity', 'missing')]
                    self.assertEqual([(i['field'], i['kind']) for i in gold['issues']], expected)
                    text = prepare_input(case / 'source')
                    self.assertIn('Синтетический', text)
                    self.assertNotIn('case_author', text)
                    doc = Document(case / 'source/project.docx')
                    self.assertIn(str(budget), doc.paragraphs[3].text)
                    book = load_workbook(case / 'source/financials.xlsx', data_only=True)
                    self.assertEqual(book['Forecast']['B5'].value is None, variant == 'missing_equity')
                    book.close()

    def test_business_reports_do_not_reuse_old_case_facts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_benchmark(root / 'cases')
            for business, title in [('small', 'Оснащение небольшой пекарни'), ('medium', 'Расширение мебельного производства')]:
                data = json.loads((root / 'cases' / business / 'complete/confirmed.json').read_text())
                output = root / 'output' / business
                write_outputs(data, calculate(data), output)
                text = (output / 'decision.md').read_text()
                self.assertIn(title, text)
                self.assertNotIn('100 млн ₽ в Word', text)
                self.assertNotIn('В исходных документах его нет', text)
                book = load_workbook(output / 'model.xlsx')
                self.assertNotIn('100 / 110', book['Input']['C4'].value)
                book.close()


if __name__ == '__main__':
    unittest.main()
