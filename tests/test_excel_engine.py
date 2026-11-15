"""Optional real spreadsheet-engine checks: set FINANCE_SOFFICE to LibreOffice."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from src.finance import calculate
from src.report import write_outputs
from tests.common import confirmed_case


@unittest.skipUnless(os.environ.get('FINANCE_SOFFICE'), 'Set FINANCE_SOFFICE for real Excel-formula recalculation')
class ExcelEngineTests(unittest.TestCase):
    def test_recalculation_and_missing_input_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_outputs(confirmed_case(), calculate(confirmed_case()), root / 'original')
            inputs, outputs = root / 'inputs', root / 'recalculated'
            inputs.mkdir()
            outputs.mkdir()
            changes = {
                'base': {}, 'zero_rate': {'B6': 0},
                'no_debt': {'B5': 110}, 'missing_equity': {'B5': None},
                'wrong_years': {'B7': 6}, 'negative_rate': {'B6': -0.1},
            }
            files = []
            for name, edits in changes.items():
                book = load_workbook(root / 'original/model.xlsx')
                for cell, value in edits.items():
                    book['Input'][cell] = value
                path = inputs / f'{name}.xlsx'
                book.save(path)
                book.close()
                files.append(str(path))
            profile = (root / 'profile').as_uri()
            command = [os.environ['FINANCE_SOFFICE'], f'-env:UserInstallation={profile}', '--headless', '--convert-to', 'xlsx', '--outdir', str(outputs), *files]
            run = subprocess.run(command, capture_output=True, text=True, timeout=90)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            books = {name: load_workbook(outputs / f'{name}.xlsx', data_only=True) for name in changes}
            try:
                self.assertAlmostEqual(books['base']['Output']['B8'].value, 45.71428571, places=6)
                self.assertAlmostEqual(books['base']['Output']['B9'].value, 14.28571429, places=6)
                self.assertEqual(books['zero_rate']['Output']['B8'].value, 60)
                self.assertEqual(books['no_debt']['Output']['B8'].value, 0)
                self.assertIsNone(books['no_debt']['Base']['H6'].value)
                for name in ('missing_equity', 'wrong_years', 'negative_rate'):
                    self.assertEqual(books[name]['Output']['B8'].data_type, 'e', name)
            finally:
                for book in books.values():
                    book.close()
