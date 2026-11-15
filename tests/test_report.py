import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from src.finance import calculate
from src.report import write_outputs
from tests.common import confirmed_case


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_report_matches_calculation(self):
        data = confirmed_case()
        write_outputs(data, calculate(data), self.root)
        result = json.loads((self.root / 'calculation.json').read_text())
        text = (self.root / 'decision.md').read_text()
        self.assertAlmostEqual(result['proposed_amount'], 45.71428571, places=6)
        self.assertIn('45.714286', text)
        self.assertIn('14.285714', text)
        self.assertIn(result['input_sha256'], text)
        self.assertNotIn('проект полностью профинансирован', text.lower())
        book = load_workbook(self.root / 'model.xlsx', data_only=False)
        self.assertEqual(book.sheetnames, ['Output', 'Input', 'Base', 'Stress'])
        self.assertEqual(book['Input']['B4'].value, 100)
        self.assertEqual(book['Input']['B5'].value, 40)
        self.assertEqual(book['Output']['B8'].data_type, 'f')
        self.assertEqual(book['Base']['B6'].data_type, 'f')
        self.assertIn('Input!', book['Stress']['G6'].value)
        book.close()

    def test_invalid_input_does_not_write_outputs(self):
        data = confirmed_case()
        data['equity'] = None
        source = self.root / 'bad.json'
        source.write_text(json.dumps(data))
        destination = self.root / 'output'
        run = subprocess.run([sys.executable, 'scripts/run_case.py', '--input', str(source), '--output', str(destination)], capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('equity', run.stderr)
        self.assertFalse(destination.exists())

    def test_zero_debt_has_no_division_error(self):
        data = confirmed_case()
        data['equity'] = 110
        data['resolutions'][1]['value'] = 110
        write_outputs(data, calculate(data), self.root)
        text = (self.root / 'decision.md').read_text()
        self.assertIn('не требуется', text)
        self.assertNotIn('Infinity', (self.root / 'calculation.json').read_text())
        book = load_workbook(self.root / 'model.xlsx', data_only=False)
        self.assertTrue(book['Base']['H6'].value.startswith('=IF('))
        book.close()

    def test_report_rejects_stale_result(self):
        data = confirmed_case()
        result = calculate(data)
        data['rate'] = 0.2
        with self.assertRaises(ValueError):
            write_outputs(data, result, self.root / 'stale')
        self.assertFalse((self.root / 'stale').exists())

    def test_changed_confirmations_are_used_in_the_conclusion(self):
        data = confirmed_case()
        data['budget'], data['equity'] = 120, 50
        data['resolutions'][0]['value'] = 120
        data['resolutions'][1]['value'] = 50
        write_outputs(data, calculate(data), self.root)
        text = (self.root / 'decision.md').read_text()
        self.assertIn('выбрал 120', text)
        self.assertIn('участие 50', text)
        self.assertNotIn('участие 40', text)


if __name__ == '__main__':
    unittest.main()
