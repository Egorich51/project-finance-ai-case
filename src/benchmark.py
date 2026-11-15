"""Freeze two synthetic businesses and three document variants before inference."""
import hashlib
import json
from pathlib import Path

from docx import Document
from openpyxl import load_workbook

from src.extraction import prepare_input
from src.fixtures import build_case

PROFILES = {
    'small': {
        'title': 'Оснащение небольшой пекарни', 'budget': 8, 'conflicting_budget': 9,
        'equity': 3, 'rate': 0.18, 'years': 5, 'cfads': [2, 2.2, 2.4, 2.6, 2.8],
        'stress_factor': 0.75, 'dscr_floor': 1.2, 'cfads_unit': 'thousand_rub',
    },
    'medium': {
        'title': 'Расширение мебельного производства', 'budget': 120, 'conflicting_budget': 125,
        'equity': 45, 'rate': 0.16, 'years': 5, 'cfads': [32, 36, 40, 43, 46],
        'stress_factor': 0.8, 'dscr_floor': 1.2, 'cfads_unit': 'million_rub',
    },
}
VARIANTS = ('complete', 'budget_conflict', 'missing_equity')


def build_benchmark(destination: Path) -> None:
    prompt = (Path(__file__).resolve().parents[1] / 'case/prompt.md').read_text(encoding='utf-8')
    manifest = []
    for business, profile in PROFILES.items():
        for variant in VARIANTS:
            root = destination / business / variant
            build_case(root)
            doc_path = root / 'source/project.docx'
            document = Document(doc_path)
            document.paragraphs[0].text = profile['title']
            document.paragraphs[2].text = f"{profile['title']}. Прогнозный денежный поток для обслуживания долга (CFADS) приведён в financials.xlsx; он задан автором напрямую."
            document.paragraphs[3].text = f"Бюджет проекта составляет {profile['budget']} млн рублей. Сведения о бюджете также приведены в приложенной таблице."
            document.paragraphs[4].text = f"Фиксированная ставка кредита — {profile['rate']*100:g}% годовых. Комиссии в примере не учитываются."
            document.paragraphs[5].text = 'Срок кредита — 5 лет. Основной долг погашается равными ежегодными долями, проценты начисляются на остаток начала года.'
            document.paragraphs[6].text = f"Стрессовый сценарий: CFADS каждого года снижается на {(1-profile['stress_factor'])*100:g}%, остальные условия сохраняются."
            document.paragraphs[7].text = 'Демонстрационный порог DSCR — 1,2 в каждом году обоих сценариев. Это допущение автора, не методика банка.'
            missing = variant == 'missing_equity'
            document.paragraphs[8].text = ('Размер собственного участия в представленных документах не указан; требуется уточнение.' if missing else f"Собственное участие составляет {profile['equity']} млн рублей.")
            document.paragraphs[9].text = 'Перед расчётом необходимо проверить согласованность источников, периоды и единицы измерения. При нехватке критических данных расчёт должен быть остановлен.'
            document.core_properties.title = profile['title']
            document.save(doc_path)

            excel_budget = profile['conflicting_budget'] if variant == 'budget_conflict' else profile['budget']
            book = load_workbook(root / 'source/financials.xlsx')
            sheet = book['Forecast']
            sheet['A1'] = profile['title'] + ' — синтетические данные'
            sheet['B4'] = excel_budget * 1000
            sheet['A5'] = 'Собственное участие — не предоставлено' if missing else 'Собственное участие'
            sheet['B5'] = None if missing else profile['equity'] * 1000
            sheet['C5'] = 'thousand_rub'
            sheet['B7'] = profile['cfads_unit']
            scale = 1000 if profile['cfads_unit'] == 'thousand_rub' else 1
            for column, flow in enumerate(profile['cfads'], 2):
                sheet.cell(10, column, flow * scale)
            sheet['A12'] = 'Все суммы и прогнозы вымышлены. Применять единицы из соответствующей строки.'
            sheet.row_dimensions[12].height = 32
            sheet.sheet_properties.pageSetUpPr.fitToPage = True
            sheet.page_setup.orientation = 'landscape'
            sheet.page_setup.fitToWidth = sheet.page_setup.fitToHeight = 1
            sheet.print_area = 'A1:F12'
            book.save(root / 'source/financials.xlsx')
            book.close()

            gold = json.loads((root / 'gold.json').read_text(encoding='utf-8'))
            gold['case_id'] = f'{business}-{variant}'
            fields = gold['fields']
            fields['budget']['value'] = None if variant == 'budget_conflict' else profile['budget']
            if variant == 'budget_conflict':
                fields['budget']['candidates'][0]['value'] = profile['budget']
                fields['budget']['candidates'][1]['value'] = excel_budget * 1000
            else:
                del fields['budget']['candidates']
            fields['equity']['value'] = None if missing else profile['equity']
            fields['equity']['sources'] = [
                {'file': 'project.docx', 'locator': 'paragraph:9'},
                {'file': 'financials.xlsx', 'locator': 'Forecast!A5' if missing else 'Forecast!B5'},
            ]
            for key in ('rate', 'years', 'stress_factor', 'dscr_floor'):
                fields[key]['value'] = profile[key]
            for year, flow in enumerate(profile['cfads'], 1):
                fields[f'cfads_{year}']['value'] = flow * scale
                fields[f'cfads_{year}']['unit'] = profile['cfads_unit']
            gold['issues'] = []
            if variant == 'budget_conflict':
                gold['issues'].append({'field': 'budget', 'kind': 'conflict', 'sources': fields['budget']['sources']})
            if missing:
                gold['issues'].append({'field': 'equity', 'kind': 'missing', 'sources': fields['equity']['sources']})
            gold_text = json.dumps(gold, ensure_ascii=False, indent=2) + '\n'
            (root / 'gold.json').write_text(gold_text, encoding='utf-8')
            confirmed = {key: profile[key] for key in ('budget', 'equity', 'rate', 'years', 'cfads', 'stress_factor', 'dscr_floor')}
            confirmed.update(case_id=gold['case_id'], project_title=profile['title'], unit='million_rub', resolutions=[
                {'field': 'budget', 'value': profile['budget'], 'status': 'confirmed', 'confirmed_by': 'case_author',
                 'note': 'Автор синтетического примера задаёт действующий бюджет. Конфликтные версии в варианте budget_conflict требуют такого уточнения.',
                 'original_candidates': [{'value': profile['budget'], 'unit': 'million_rub'}, {'value': excel_budget*1000, 'unit': 'thousand_rub'}]},
                {'field': 'equity', 'value': profile['equity'], 'status': 'confirmed', 'confirmed_by': 'case_author',
                 'note': 'В missing_equity это новое уточнение автора после проверки; в остальных вариантах сумма присутствует в документах.'},
            ])
            (root / 'confirmed.json').write_text(json.dumps(confirmed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            (root / 'prompt.md').write_text(prompt, encoding='utf-8')
            text = prepare_input(root / 'source')
            (root / 'model-input.txt').write_text(text + '\n', encoding='utf-8')
            manifest.append({'case_id': gold['case_id'], 'business': business, 'variant': variant, 'path': f'{business}/{variant}',
                             'gold_sha256': hashlib.sha256(gold_text.encode()).hexdigest(), 'input_sha256': hashlib.sha256(text.encode()).hexdigest()})
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    build_benchmark(Path('benchmarks/cases'))
