"""Fixed synthetic documents; run before any model experiment."""
import json
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml.ns import qn
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill


def build_case(destination: Path) -> None:
    source_dir = destination / 'source'
    source_dir.mkdir(parents=True, exist_ok=True)
    document = Document()
    section = document.sections[0]
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin = section.right_margin = Cm(2.2)
    document.styles['Normal'].font.name = 'Arial'
    document.styles['Normal'].font.size = Pt(11)
    document.styles['Normal'].paragraph_format.space_after = Pt(10)
    document.styles['Title'].font.color.rgb = RGBColor(0, 0, 0)
    title_properties = document.styles['Title'].element.find(qn('w:pPr'))
    if title_properties is not None:
        for border in list(title_properties.findall(qn('w:pBdr'))):
            title_properties.remove(border)
    document.add_paragraph('Проект приобретения оборудования', 'Title')
    paragraphs = [
        'Синтетический пример для технической демонстрации. Все данные вымышлены.',
        'Проект предусматривает приобретение производственной линии. Денежный поток для обслуживания долга (CFADS) приведён в financials.xlsx. Полная прогнозная отчётность в примере не рассматривается.',
        'Бюджет проекта составляет 100 млн рублей. Значение требует сверки с приложенной таблицей.',
        'Предполагаемая фиксированная ставка кредита — 15% годовых. Комиссии в демонстрации не учитываются.',
        'Срок кредита — 5 лет. Основной долг погашается равными ежегодными долями, проценты начисляются на остаток начала года. Льготного периода нет.',
        'Демонстрационный стрессовый сценарий: CFADS каждого года снижается на 20%, остальные условия не меняются.',
        'Условное ограничение для примера: DSCR не ниже 1,2 в каждом году базового и стрессового сценариев. Это допущение автора, не методика банка.',
        'Размер собственного участия в представленных материалах не указан; требуется уточнение. Не подставлять ноль.',
        'Источники значений должны сохраняться до конкретного абзаца или ячейки. До разрешения противоречий и уточнения собственного участия расчёт не выполняется.',
    ]
    for text in paragraphs:
        document.add_paragraph(text)
    document.core_properties.author = 'Synthetic case'
    document.core_properties.last_modified_by = 'Synthetic case'
    document.core_properties.title = 'Синтетический проект приобретения оборудования'
    document.save(source_dir / 'project.docx')

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Forecast'
    rows = {
        1: ['Синтетический проект — исходные финансовые данные'],
        2: ['Все данные вымышлены. Это входные сведения, а не банковская методика.'],
        3: ['Показатель', 'Значение', 'Единица'],
        4: ['Бюджет проекта', 110000, 'thousand_rub'],
        5: ['Собственное участие — не предоставлено', None, 'million_rub'],
        7: ['Единица CFADS', 'million_rub'],
        8: ['CFADS — денежный поток до обслуживания долга, допущение автора'],
        9: ['Год', 1, 2, 3, 4, 5],
        10: ['CFADS', 24, 26, 28, 30, 32],
        12: ['Внимание: бюджет необходимо сопоставить с project.docx.'],
    }
    for row, values in rows.items():
        for col, value in enumerate(values, 1):
            sheet.cell(row, col, value)
    sheet.column_dimensions['A'].width = 72
    for column in 'BCDEF':
        sheet.column_dimensions[column].width = 19
    for row in sheet:
        for cell in row:
            cell.font = Font(name='Arial', size=11, color='164C96' if isinstance(cell.value, (float, int)) else '253348')
            cell.alignment = Alignment(vertical='center', wrap_text=True)
    for row in (1, 3, 9):
        sheet.row_dimensions[row].height = 28
        for cell in sheet[row]:
            cell.fill = PatternFill('solid', fgColor='17324D')
            cell.font = Font(name='Arial', size=11, bold=True, color='FFFFFF')
    sheet.row_dimensions[2].height = 32
    sheet.row_dimensions[8].height = 32
    sheet.freeze_panes = 'B4'
    sheet.sheet_view.showGridLines = False
    workbook.properties.creator = 'Synthetic case'
    workbook.save(source_dir / 'financials.xlsx')
    workbook.close()

    def src(file, locator):
        return {'file': file, 'locator': locator}

    def field(value, unit, period, sources):
        return {'value': value, 'unit': unit, 'period': period, 'sources': sources}

    budget_sources = [src('project.docx', 'paragraph:4'), src('financials.xlsx', 'Forecast!B4')]
    fields = {
        'budget': field(None, 'million_rub', 'project', budget_sources),
        'equity': field(None, 'million_rub', 'project', [src('financials.xlsx', 'Forecast!A5')]),
        'rate': field(0.15, 'fraction', 'project', [src('project.docx', 'paragraph:5')]),
        'years': field(5, 'year', 'project', [src('project.docx', 'paragraph:6')]),
        'stress_factor': field(0.8, 'fraction', 'project', [src('project.docx', 'paragraph:7')]),
        'dscr_floor': field(1.2, 'ratio', 'project', [src('project.docx', 'paragraph:8')]),
    }
    fields['budget']['candidates'] = [
        field(100, 'million_rub', 'project', [budget_sources[0]]),
        field(110000, 'thousand_rub', 'project', [budget_sources[1]]),
    ]
    for year, (col, value) in enumerate(zip('BCDEF', [24, 26, 28, 30, 32]), 1):
        fields[f'cfads_{year}'] = field(value, 'million_rub', year, [src('financials.xlsx', f'Forecast!{col}10')])
    gold = {
        'case_id': 'synthetic-equipment-001',
        'fields': fields,
        'issues': [
            {'field': 'budget', 'kind': 'conflict', 'sources': budget_sources},
            {'field': 'equity', 'kind': 'missing', 'sources': fields['equity']['sources']},
        ],
    }
    (destination / 'gold.json').write_text(json.dumps(gold, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    build_case(Path('case'))
