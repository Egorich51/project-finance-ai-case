"""Excel formulas and a decision draft generated from the same input version."""
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.chart.series import SeriesLabel
from openpyxl.comments import Comment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import Alignment, Font, PatternFill, Protection
from openpyxl.workbook.properties import CalcProperties

from src.finance import calculate

NAVY = '17324D'
TEAL = '007F82'
MONEY = '#,##0.00;[Red](#,##0.00);"—"'


def _header(sheet, title, subtitle, end=8):
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=end)
    sheet['A1'] = title
    sheet['A1'].font = Font(name='Arial', size=19, bold=True, color='FFFFFF')
    sheet['A1'].fill = PatternFill('solid', fgColor=NAVY)
    sheet.row_dimensions[1].height = 37
    sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=end)
    sheet['A2'] = subtitle
    sheet['A2'].alignment = Alignment(wrap_text=True, vertical='center')
    sheet.row_dimensions[2].height = 34
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = 'B6'
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = 'landscape'
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 1


def _band(sheet, row, labels):
    for col, label in enumerate(labels, 1):
        cell = sheet.cell(row, col, label)
        cell.font = Font(name='Arial', size=10, bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor=NAVY)
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    sheet.row_dimensions[row].height = 34


def _workbook(data, result, target):
    book = Workbook()
    book.remove(book.active)
    for name in ('Output', 'Input', 'Base', 'Stress'):
        book.create_sheet(name)
    book.calculation = CalcProperties(calcId=191029, fullCalcOnLoad=True, forceFullCalc=True)
    book.properties.creator = 'Synthetic financing case'
    book.properties.title = 'Синтетический пример проектного финансирования'
    sheet = book['Input']
    _header(sheet, 'Условия расчётного примера', 'Все данные вымышлены. Синие ячейки — входные данные; бюджет и собственное участие уточнены автором примера.')
    _band(sheet, 3, ['Параметр', 'Значение', 'Единица / источник'])
    inputs = [
        ('Бюджет', data['budget'], 'млн ₽; уточнение автора, исходный конфликт 100 / 110'),
        ('Собственное участие', data['equity'], 'млн ₽; новое условие автора, отсутствовало в документах'),
        ('Годовая ставка', data['rate'], 'доля; project.docx, абзац 5'),
        ('Срок кредита', data['years'], 'лет; изменение срока через JSON и повторный запуск'),
        ('Множитель CFADS в стрессе', data['stress_factor'], 'доля; project.docx, абзац 7'),
        ('Минимальный DSCR', data['dscr_floor'], 'раз; условие автора, project.docx, абзац 8'),
    ]
    for row, values in enumerate(inputs, 4):
        for col, value in enumerate(values, 1):
            sheet.cell(row, col, value)
        sheet.cell(row, 2).protection = Protection(locked=(row == 7))
        sheet.cell(row, 2).fill = PatternFill('solid', fgColor='E8F4FA')
    sheet['B6'].number_format = sheet['B8'].number_format = '0.0%'
    sheet['B7'].number_format = '0'
    sheet['B7'].comment = Comment('Срок определяет число строк графика. Измените years и cfads в confirmed.json и запустите скрипт заново.', 'Case author')
    _band(sheet, 12, ['Год', 'CFADS, млн ₽', 'Источник'])
    for row, value in enumerate(data['cfads'], 13):
        year = row - 12
        sheet.cell(row, 1, year)
        sheet.cell(row, 2, value).protection = Protection(locked=False)
        sheet.cell(row, 2).fill = PatternFill('solid', fgColor='E8F4FA')
        sheet.cell(row, 3, f'Исходник: financials.xlsx, Forecast!{chr(65 + year)}10; текущее значение из JSON')
    sheet.column_dimensions['A'].width = 35
    sheet.column_dimensions['B'].width = 20
    sheet.column_dimensions['C'].width = 76
    sheet.protection.sheet = True
    for cells, operator, minimum, maximum in [('B4:B6', 'greaterThanOrEqual', '0', None), ('B8', 'between', '0', '1'), ('B9', 'greaterThan', '0', None)]:
        rule = DataValidation(type='decimal', operator=operator, formula1=minimum, formula2=maximum, allow_blank=False)
        rule.showErrorMessage = True
        rule.errorTitle = 'Некорректное условие'
        rule.error = 'Проверьте числовое значение и единицу измерения.'
        sheet.add_data_validation(rule)
        rule.add(cells)

    for name in ('Base', 'Stress'):
        schedule = book[name]
        _header(schedule, 'Базовый сценарий' if name == 'Base' else 'Стрессовый сценарий', 'Годовое равномерное погашение основного долга; проценты на остаток начала года. Все денежные показатели — млн ₽.', end=11)
        _band(schedule, 5, ['Год', 'Долг на начало', 'Погашение', 'Проценты', 'Долг на конец', 'Обслуживание долга', 'CFADS', 'DSCR, раз', 'Платёж на 1 ₽ долга', 'Предел долга', 'Порог DSCR'])
        for t in range(data['years']):
            row = t + 6
            formulas = [
                t + 1,
                '=Output!$B$8' if t == 0 else f'=E{row-1}',
                '=Output!$B$8/Input!$B$7',
                f'=B{row}*Input!$B$6',
                f'=MAX(B{row}-C{row},0)',
                f'=C{row}+D{row}',
                f'=Input!B{13+t}' + ('*Input!$B$8' if name == 'Stress' else ''),
                f'=IF(F{row}=0,"",G{row}/F{row})',
                f'=1/Input!$B$7+Input!$B$6*(1-(A{row}-1)/Input!$B$7)',
                f'=MAX(0,G{row}/(Input!$B$9*I{row}))',
                '=Input!$B$9',
            ]
            for col, value in enumerate(formulas, 1):
                schedule.cell(row, col, value)
        for col in 'BCDEFGHIJK':
            schedule.column_dimensions[col].width = 18
        schedule.column_dimensions['A'].width = 9
        schedule.print_area = f'A1:K{data["years"]+6}'

    out = book['Output']
    _header(out, 'Предварительный расчёт финансирования', 'Синтетический пример. Расчётный предел по условному DSCR — не одобрение кредита и не оценка кредитного риска.')
    _band(out, 4, ['Показатель', 'Значение', 'Единица'])
    end = data['years'] + 5
    input_gate = f'AND(COUNT(Input!B4:B9,Input!B13:B{12+data["years"]})={6+data["years"]},Input!B4>=0,Input!B5>=0,Input!B6>=0,Input!B7={data["years"]},Input!B8>=0,Input!B8<=1,Input!B9>0)'
    outputs = [
        ('Потребность в кредите', f'=IF({input_gate},MAX(Input!B4-Input!B5,0),NA())', 'млн ₽'),
        ('Предел в базовом сценарии', f'=MIN(Base!J6:J{end})', 'млн ₽'),
        ('Предел в стрессовом сценарии', f'=MIN(Stress!J6:J{end})', 'млн ₽'),
        ('Сумма для рассмотрения', '=MIN(B5:B7)', 'млн ₽'),
        ('Дефицит финансирования', '=MAX(B5-B8,0)', 'млн ₽'),
        ('Минимальный DSCR в стрессе', f'=IF(B8=0,"",MIN(Stress!H6:H{end}))', 'раз'),
    ]
    for row, values in enumerate(outputs, 5):
        for col, value in enumerate(values, 1):
            out.cell(row, col, value)
    out.merge_cells('A12:H13')
    out['A12'] = '=IF(ISERROR(B8),"Недостаточно корректных данных — расчёт заблокирован",IF(B8=0,IF(B5=0,"Кредит по заданному бюджету не требуется","Положительная сумма долга не проходит условия примера"),IF(B9>0.000001,"Требуется дополнительное финансирование или пересмотр условий","Сумма укладывается в условия примера; требуется проверка специалистом")))'
    out['A12'].alignment = Alignment(wrap_text=True, vertical='center')
    out['A12'].fill = PatternFill('solid', fgColor='FFF1D6')
    out.row_dimensions[12].height = 25
    out.merge_cells('A15:H16')
    out['A15'] = 'CFADS задан напрямую. Налоги, оборотный капитал, комиссии, обеспечение и кредитный скоринг отдельно не моделируются. Исходный ответ AI не используется как подтверждённый ввод.'
    out['A15'].alignment = Alignment(wrap_text=True, vertical='center')
    out.row_dimensions[15].height = 25
    chart = LineChart()
    chart.title = 'DSCR по годам'
    chart.y_axis.title = 'раз'
    chart.x_axis.title = 'год'
    for name in ('Base', 'Stress'):
        chart.add_data(Reference(book[name], min_col=8, min_row=5, max_row=end), titles_from_data=True)
        chart.series[-1].tx = SeriesLabel(strRef=None, v='База' if name == 'Base' else 'Стресс')
    chart.add_data(Reference(book['Stress'], min_col=11, min_row=5, max_row=end), titles_from_data=True)
    chart.set_categories(Reference(book['Base'], min_col=1, min_row=6, max_row=end))
    chart.width, chart.height = 22, 8
    chart.style = 13
    for series, color in zip(chart.series, (NAVY, TEAL, '9A9A9A')):
        series.graphicalProperties.line.solidFill = color
    chart.series[2].graphicalProperties.line.prstDash = 'dash'
    out.add_chart(chart, 'A18')
    out.merge_cells('A35:H35')
    out['A35'] = 'SHA256 данных при генерации; ручные правки Excel его не обновляют'
    out.merge_cells('A36:H37')
    out['A36'] = result['input_sha256']
    out['A36'].alignment = Alignment(wrap_text=True, vertical='center')
    out.row_dimensions[35].height = 22
    out.row_dimensions[36].height = 24
    out.column_dimensions['A'].width = 39
    out.column_dimensions['B'].width = 23
    out.column_dimensions['C'].width = 13
    for col in 'DEFGH':
        out.column_dimensions[col].width = 13
    out.print_area = 'A1:H40'

    for tab in book:
        for row in tab:
            for cell in row:
                if cell.row in (1, 2) or cell.fill.fgColor.rgb == '0017324D':
                    continue
                formula = cell.data_type == 'f'
                color = '007A4B' if formula and '!' in str(cell.value) else ('172B40' if formula else ('164C96' if isinstance(cell.value, (int, float)) else '253348'))
                cell.font = Font(name='Arial', size=11, color=color, bold=tab.title == 'Output' and cell.row in (8, 9))
                cell.alignment = Alignment(vertical='center', wrap_text=cell.column == 1 or tab.title == 'Input' and cell.column == 3)
                if formula or isinstance(cell.value, (int, float)):
                    if cell.number_format == 'General':
                        cell.number_format = MONEY
        tab.sheet_properties.tabColor = TEAL if tab.title == 'Output' else NAVY
    for name in ('Base', 'Stress'):
        for row in range(6, data['years'] + 6):
            book[name].cell(row, 1).number_format = '0'
    for row in range(13, data['years'] + 13):
        sheet.cell(row, 1).number_format = '0'
    book.save(target)
    book.close()


def write_outputs(data: dict, result: dict, destination: Path) -> None:
    if result != calculate(data):
        raise ValueError('Результат не соответствует версии входных данных')
    amount, gap = result['proposed_amount'], result['funding_gap']
    if result['need'] == 0:
        status = 'Кредит по заданному бюджету не требуется.'
    elif amount == 0:
        status = 'Положительная сумма долга не проходит условия примера; требуется пересмотр проекта.'
    elif gap > 1e-6:
        status = 'Потребность не покрыта. Требуется дополнительное собственное участие либо пересмотр условий и повторный расчёт.'
    else:
        status = 'Сумма укладывается в демонстрационные ограничения. Это не решение об одобрении кредита.'
    text = f'''# Предварительное расчётное заключение

Синтетический проект приобретения оборудования. Все данные и ограничения вымышлены. Заключение сформировано кодом по подтверждённым автором условиям; банковская экспертиза не проводилась.

**Статус:** {status}

| Показатель | млн ₽ |
|---|---:|
| Бюджет | {data['budget']:.6f} |
| Собственное участие | {data['equity']:.6f} |
| Потребность в кредите | {result['need']:.6f} |
| Предел в базовом сценарии | {result['capacity_base']:.6f} |
| Предел в стрессовом сценарии | {result['capacity_stress']:.6f} |
| Сумма для рассмотрения | {amount:.6f} |
| Дефицит финансирования | {gap:.6f} |

Расчётные условия: ставка {data['rate']:.1%} годовых, срок {data['years']} лет, равномерное ежегодное погашение основного долга. Стрессовый CFADS составляет {data['stress_factor']:.0%} от базового, порог DSCR — {data['dscr_floor']:.2f}. При нулевом долге DSCR не определяется.

## Уточнения и вопросы

- В исходных документах бюджеты различаются: 100 млн ₽ в Word и 110000 тыс. ₽ в Excel. Автор примера выбрал {data['budget']:g} млн ₽ как новое уточнение.
- Собственное участие {data['equity']:g} млн ₽ добавлено автором после проверки. В исходных документах его нет; AI эту сумму не извлекал.
- Нужна проверка исходного CFADS, налогов, оборотного капитала, обеспечения и остальных условий специалистом. В этом примере они отдельно не моделируются.
- Сублимиты и кредитный скоринг не рассчитывались. Базовый и стрессовый графики доступны в model.xlsx и calculation.json.

## Версия

SHA256 входных данных: `{result['input_sha256']}`. Суммы в таблице округлены только для отображения. Машиночитаемые значения сохраняют полную точность.
'''
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'calculation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    (destination / 'decision.md').write_text(text, encoding='utf-8')
    _workbook(data, result, destination / 'model.xlsx')
