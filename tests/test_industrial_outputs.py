import copy
import json
import tempfile
import unittest
from pathlib import Path

from docx import Document
from openpyxl import load_workbook

from src.industrial_finance import audit_project
from src.industrial_outputs import write_industrial_outputs
from src.industrial_evaluation import evaluate_fields

ROOT = Path(__file__).resolve().parents[1] / 'studies/industrial-v2'


class IndustrialOutputTests(unittest.TestCase):
    def test_evaluation_handles_units_periods_sources_and_rounding(self):
        gold = {'fields': {'cash': {'value': 13.46, 'unit': 'million_rub', 'period': 2027,
                                   'allowed_sources': ['MD:L416'], 'tolerance': 0.005001}}, 'issues': []}
        pred = {'fields': {'cash': {'value': 13460.958, 'unit': 'thousand_rub', 'period': 2027, 'sources': ['MD:L416']}}, 'issues': []}
        result = evaluate_fields(pred, gold)
        self.assertEqual(result['values_correct'], 1)
        self.assertEqual(result['grounded_correct'], 1)
        pred['fields']['cash']['sources'] = ['[MD:L416]']
        self.assertEqual(evaluate_fields(pred, gold)['grounded_correct'], 0)
        pred['fields']['cash']['period'] = 2025
        self.assertEqual(evaluate_fields(pred, gold)['values_correct'], 0)
        pred['fields']['cash']['unit'] = []
        self.assertEqual(evaluate_fields(pred, gold)['values_correct'], 0)

    def test_output_contains_formula_models_and_project_specific_conclusion(self):
        source = json.loads(next((ROOT/'input').glob('03*/Входные данные.json')).read_text())
        result = audit_project(source)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            write_industrial_outputs(source, result, out)
            saved = json.loads((out/'audit.json').read_text())
            self.assertAlmostEqual(saved['npv'], -9.562913267, places=6)
            text = (out/'conclusion.md').read_text()
            self.assertIn('Синтез Лес', text)
            self.assertIn('18', text)
            self.assertIn('отрицател', text.lower())
            self.assertTrue(any('55.00' in p.text for p in Document(out/'conclusion.docx').paragraphs) or '55.00' in str([c.text for t in Document(out/'conclusion.docx').tables for r in t.rows for c in r.cells]))
            book = load_workbook(out/'financial-model.xlsx')
            self.assertEqual(book['Кредит']['F8'].data_type, 'f')
            self.assertEqual(book['Потоки']['L8'].data_type, 'f')
            self.assertEqual(book['Экономика']['B12'].data_type, 'f')
            self.assertEqual(len(book.sheetnames), 8)
            book.close()

    def test_stale_input_is_rejected_before_any_files_are_written(self):
        source = json.loads(next((ROOT/'input').glob('01*/Входные данные.json')).read_text())
        result = audit_project(source)
        source['project']['annual_rate'] = 0.25
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'stale'
            with self.assertRaises(ValueError):write_industrial_outputs(source, result, target)
            self.assertFalse(target.exists())
