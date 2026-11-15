import json
import tempfile
import unittest
from pathlib import Path

from docx import Document
from openpyxl import load_workbook

from src.fixtures import build_case


class FixtureTests(unittest.TestCase):
    def test_case_has_traceable_conflict_and_missing_equity(self):
        # Catches lost conflict, silently invented equity, and broken locators.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_case(root)
            paragraphs = [p.text for p in Document(root / 'source/project.docx').paragraphs]
            workbook = load_workbook(root / 'source/financials.xlsx', data_only=True)
            sheet = workbook['Forecast']
            self.assertIn('100 млн', paragraphs[3])
            self.assertEqual(sheet['B4'].value, 110000)
            self.assertEqual(sheet['C4'].value, 'thousand_rub')
            self.assertIsNone(sheet['B5'].value)
            self.assertEqual([sheet.cell(10, col).value for col in range(2, 7)], [24, 26, 28, 30, 32])
            gold = json.loads((root / 'gold.json').read_text())
            self.assertEqual(gold['fields']['budget']['value'], None)
            self.assertEqual([v['value'] for v in gold['fields']['budget']['candidates']], [100, 110000])
            self.assertEqual(gold['fields']['equity']['value'], None)
            self.assertEqual({(p['field'], p['kind']) for p in gold['issues']}, {('budget', 'conflict'), ('equity', 'missing')})
            self.assertIn('Синтетический', paragraphs[1])
            for field in gold['fields'].values():
                for source in field['sources']:
                    if source['file'].endswith('.docx'):
                        index = int(source['locator'].split(':')[1]) - 1
                        self.assertTrue(paragraphs[index])
                    else:
                        tab, cell = source['locator'].split('!')
                        self.assertIn(tab, workbook.sheetnames)
                        self.assertIsNotNone(workbook[tab][cell].value)
            workbook.close()


if __name__ == '__main__':
    unittest.main()
