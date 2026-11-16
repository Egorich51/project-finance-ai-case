"""Excel formula model and Word/Markdown conclusions for industrial projects."""
import json
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.workbook.properties import CalcProperties

from src.industrial_finance import audit_project

NAVY, TEAL = '17324D', '007F82'
MONEY = '#,##0.00;[Red](#,##0.00);"—"'


def _title(sheet, title, note, width=8):
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=width)
    sheet['A1'] = title
    sheet['A1'].font = Font(name='Arial', size=15, bold=True, color='FFFFFF')
    sheet['A1'].fill = PatternFill('solid', fgColor=NAVY)
    sheet.row_dimensions[1].height = 34
    sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=width)
    sheet['A2'] = note
    sheet['A2'].alignment = Alignment(wrap_text=True, vertical='center')
    sheet.row_dimensions[2].height = 32
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = 'C8'
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = 'landscape'
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth, sheet.page_setup.fitToHeight = 1, 1


def _band(sheet, row, values):
    for col, value in enumerate(values, 1):
        cell = sheet.cell(row, col, value)
        cell.fill = PatternFill('solid', fgColor=NAVY)
        cell.font = Font(name='Arial', size=10, bold=True, color='FFFFFF')
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    sheet.row_dimensions[row].height = 32


def _make_workbook(data, result, path):
    p, v = data['project'], data['business_plan_v2']
    book = Workbook();book.remove(book.active)
    for name in ('Выводы', 'Ввод', 'Кредит', 'Потоки', 'Годы', 'Экономика', 'Сценарии', 'История'):
        book.create_sheet(name)
    book.calculation = CalcProperties(fullCalcOnLoad=True, forceFullCalc=True)
    book.properties.creator = 'Technical project audit'
    book.properties.title = data['name']
    inputs = book['Ввод']
    _title(inputs, 'Условия и график финансирования', 'Все деньги — млн ₽. Значения получены из предоставленного JSON; синие ячейки — входные данные.')
    _band(inputs, 4, ['Параметр', 'Значение', 'Источник / граница'])
    params = [('Новый кредит', result['loan'], 'project.loan'), ('Собственное участие', result['equity'], 'project.equity_total'),
              ('Полный бюджет', result['budget'], 'project.total_funding'), ('Годовая ставка', result['rate'], 'project.annual_rate'),
              ('Срок, месяцев', 60, 'Количество строк фиксировано; смена срока требует регенерации'),
              ('Отсрочка основного долга', result['grace_months'], 'project.grace_months'),
              ('Ставка дисконтирования', result['discount_rate'], 'business_plan_v2.metrics.discount_rate'),
              ('Условный порог DSCR', 1.2, 'Скрининг; не норматив банка'),
              ('Снижение абсолютного EBITDA', 0.2, 'Механический стресс; налоги и оборотные статьи закреплены'),
              ('Капвложения без НДС', p['capex_net']/1000, 'project.capex_net'),
              ('Капвложения с НДС', p['capex_gross']/1000, 'project.capex_gross'),
              ('Бюджет оборотного капитала', p['working_capital']/1000, 'project.working_capital'),
              ('Стартовый резерв', p['liquidity_reserve']/1000, 'project.liquidity_reserve')]
    for row, values in enumerate(params, 5):
        for col, value in enumerate(values, 1):inputs.cell(row, col, value)
    for row in (8, 11, 13):inputs.cell(row, 2).number_format='0.0%'
    for row in (9, 10):inputs.cell(row, 2).number_format='0'
    _band(inputs, 21, ['№ месяца', 'Год', 'Месяц', 'Доля выборки', 'Доля собственных'])
    for index, source in enumerate(v['monthly']):
        draw = p['draw_months'][index] if index < len(p['draw_months']) else 0
        for col, value in enumerate([index+1, source['year'], source['month'], draw/p['loan'], source['equity']/p['equity_total']], 1):
            inputs.cell(index+22, col, value)
    inputs.column_dimensions['A'].width=35;inputs.column_dimensions['B'].width=19;inputs.column_dimensions['C'].width=77
    for col in 'DE':inputs.column_dimensions[col].width=19
    inputs.print_area='A1:E81';inputs.page_setup.fitToHeight=2

    debt, flow = book['Кредит'], book['Потоки']
    _title(debt, 'Новый кредит по месяцам', 'Выборка в начале месяца; проценты после выборки; погашение в конце месяца. Старый долг компании сюда не включён.')
    _band(debt, 7, ['Год', 'Месяц', 'Выборка', 'Долг на начало', 'Проценты', 'Погашение', 'Долг на конец', 'Обслуживание'])
    _title(flow, 'Помесячные денежные потоки проекта', 'Операционные входы и налоговый календарь — исходные данные JSON. Формулы независимо восстанавливают CFADS и остаток денег.', 14)
    _band(flow, 7, ['Год', 'Месяц', 'EBITDA', 'Налог деньгами', 'Изменение ОК', 'Поддержка CAPEX', 'Собственные', 'Инвест CAPEX с НДС', 'Возврат НДС', 'CFADS', 'Изменение денег', 'Деньги на конец', 'Стресс CFADS', 'Стресс деньги'])
    for index, source in enumerate(v['monthly']):
        row, driver = index+8, index+22
        values = [source['year'], source['month'], f"='Ввод'!$B$5*'Ввод'!D{driver}", '=0' if index==0 else f'=G{row-1}',
                  f"=(D{row}+C{row})*'Ввод'!$B$8/12",
                  f'=IF(ROW()-7>\'Ввод\'!$B$10,\'Ввод\'!$B$5/(\'Ввод\'!$B$9-\'Ввод\'!$B$10),0)',
                  f'=MAX(D{row}+C{row}-F{row},0)', f'=E{row}+F{row}']
        for col, value in enumerate(values, 1):debt.cell(row, col, value)
        values = [source['year'], source['month'], source['ebitda']/1000, source['tax']/1000, source['change_nwc']/1000, source['maintenance']/1000,
                  f"='Ввод'!$B$6*'Ввод'!E{driver}", source['capex']/1000, source['vat_refund']/1000,
                  f'=C{row}-D{row}-E{row}-F{row}', f'=J{row}-\'Кредит\'!H{row}+\'Кредит\'!C{row}+G{row}-H{row}+I{row}',
                  f'=K{row}' if index==0 else f'=L{row-1}+K{row}',
                  f'=J{row}-\'Ввод\'!$B$13*ABS(C{row})',
                  f'=M{row}-\'Кредит\'!H{row}+\'Кредит\'!C{row}+G{row}-H{row}+I{row}' + (f'+N{row-1}' if index else '')]
        for col, value in enumerate(values, 1):flow.cell(row, col, value)
    for sheet, end in [(debt,'H'),(flow,'N')]:
        sheet.print_area=f'A1:{end}67';sheet.print_title_rows='1:7';sheet.page_setup.fitToHeight=2
        for col in range(1,sheet.max_column+1):sheet.column_dimensions[chr(64+col)].width=16 if col>2 else 9
    flow.page_setup.paperSize=flow.PAPERSIZE_A3

    annual = book['Годы']
    _title(annual, 'Годовой результат периметра проекта', 'Поток обслуживания долга отличается от бездолгового FCF для NPV. В модернизации долг обслуживается всем участком, а эффективность — приростом.', 6)
    _band(annual, 4, ['Показатель',2027,2028,2029,2030,2031])
    labels={5:'Выручка источника',6:'EBITDA',7:'Денежный налог',8:'Изменение оборотного капитала',9:'Поддерживающие инвестиции',10:'Проценты',11:'Погашение основного долга',12:'CFADS',13:'Обслуживание долга',14:'DSCR',15:'Долг на конец года',16:'Деньги на конец года',17:'Стресс CFADS',18:'Стресс DSCR',19:'Стресс деньги на конец',20:'Бездолговой FCF источника',21:'Условный порог DSCR',22:'DSCR в годы погашения',23:'Стресс DSCR в годы погашения'}
    sums={6:('Потоки','C'),7:('Потоки','D'),8:('Потоки','E'),9:('Потоки','F'),10:('Кредит','E'),11:('Кредит','F'),12:('Потоки','J'),13:('Кредит','H'),17:('Потоки','M')}
    for row,label in labels.items():annual.cell(row,1,label)
    for i, year in enumerate(range(2027,2032)):
        col=chr(66+i);last=19+i*12
        annual[f'{col}5']=v['annual'][i]['revenue']/1000
        for row,(tab,column) in sums.items():annual[f'{col}{row}']=f'=SUMIF(\'{tab}\'!$A$8:$A$67,{col}$4,\'{tab}\'!${column}$8:${column}$67)'
        annual[f'{col}14']=f'=IF({col}13=0,"",{col}12/{col}13)'
        annual[f'{col}15']=f"='Кредит'!G{last}"
        annual[f'{col}16']=f"='Потоки'!L{last}"
        annual[f'{col}18']=f'=IF({col}13=0,"",{col}17/{col}13)'
        annual[f'{col}19']=f"='Потоки'!N{last}"
        annual[f'{col}20']=f"='Экономика'!B{6+i}"
        annual[f'{col}21']="='Ввод'!$B$12"
        annual[f'{col}22']=f'=IF({col}11>0,{col}14,"")'
        annual[f'{col}23']=f'=IF({col}11>0,{col}18,"")'
    annual.column_dimensions['A'].width=40
    for col in 'BCDEF':annual.column_dimensions[col].width=20
    annual.print_area='A1:F24'

    econ = book['Экономика']
    _title(econ, 'Эффективность инвестиций', 'FCF — предоставленный автором бездолговой поток; NPV и IRR пересчитаны формулами. Остаточная стоимость и высвобождение ОК не добавлялись.', 4)
    _band(econ,4,['Период','Бездолговой FCF','Коэффициент дисконтирования','Дисконтированный поток'])
    for index,value in enumerate(result['unlevered_flows']):
        row=5+index
        econ.cell(row,1,index);econ.cell(row,2,value)
        econ.cell(row,3,f'=1/(1+\'Ввод\'!$B$11)^A{row}');econ.cell(row,4,f'=B{row}*C{row}')
    econ['A12']='NPV';econ['B12']="=NPV('Ввод'!B11,B6:B10)+B5"
    econ['A13']='IRR';econ['B13']='=IRR(B5:B10)';econ['B13'].number_format='0.00%'
    for col in 'ABCD':econ.column_dimensions[col].width=28
    econ.print_area='A1:D15'

    scenarios = book['Сценарии']
    _title(scenarios, 'Сценарии инициатора', 'Это показатели из JSON автора, не независимый пересчёт сценариев. Наш отдельный механический стресс EBITDA показан на листах Потоки и Годы.', 5)
    _band(scenarios,4,['Сценарий','NPV, млн ₽','IRR','Минимум DSCR погашения','Минимум денег, млн ₽'])
    translations={'base':'База','volume_minus_20':'Объём −20%','price_minus_10':'Цена −10%','variable_plus_10':'Переменные затраты +10%','capex_plus_15':'Капвложения +15%'}
    for row,(name,item) in enumerate(v['scenarios'].items(),5):
        values=[translations[name],item['npv_22']/1000,item['irr'],item['min_dscr_repayment'],item['min_cash']/1000]
        for col,value in enumerate(values,1):scenarios.cell(row,col,value)
        scenarios.cell(row,3).number_format='0.00%'
    scenarios.column_dimensions['A'].width=32
    for col in 'BCDE':scenarios.column_dimensions[col].width=24
    scenarios.print_area='A1:E11'

    hist = book['История']
    _title(hist, 'Компания и проект разделены', '2023–2025 — исторические данные компании; 2026 — управленческий план. Это сведения JSON источника, а не прогноз баланса компании на 2027–2031.', 5)
    _band(hist,4,['Показатель','2023 факт','2024 факт','2025 факт','2026 план'])
    for row,(key,label) in enumerate([('revenue','Выручка'),('ebitda','EBITDA'),('net_profit','Чистая прибыль'),('cfo','Операционный денежный поток'),('cash','Деньги'),('debt','Долг'),('assets','Активы'),('equity','Капитал')],5):
        hist.cell(row,1,label)
        for col,year in enumerate(range(2023,2027),2):
            item=data['bridge_2026'] if year==2026 else data['closed_history'][str(year)]
            hist.cell(row,col,item[key]/1000)
    hist.column_dimensions['A'].width=38
    for col in 'BCDE':hist.column_dimensions[col].width=23
    hist.print_area='A1:E14'

    out=book['Выводы']
    _title(out, data['name'], 'Синтетический проект. Расчётная проверка источника и предварительный скрининг; окончательное решение банка не формируется.')
    _band(out,4,['Показатель','Значение','Единица'])
    gate="AND(COUNT('Ввод'!B5:B17)=13,COUNT('Потоки'!C8:I67)=420,'Ввод'!B5>0,'Ввод'!B6>=0,'Ввод'!B8>=0,'Ввод'!B9=60,'Ввод'!B10<60,'Ввод'!B10>=0,'Ввод'!B11>=0,'Ввод'!B12>0,'Ввод'!B13>=0,'Ввод'!B13<=1)"
    metrics=[('Полная потребность',"='Ввод'!B7",'млн ₽'),('Новый кредит',"='Ввод'!B5",'млн ₽'),('Собственное участие',"='Ввод'!B6",'млн ₽'),
             ('Минимум DSCR в годы погашения',f'=IF({gate},MIN(\'Годы\'!B22:F22),NA())','раз'),
             ('Минимум DSCR за все годы',"=MIN('Годы'!B14:F14)",'раз'),('Минимум месячных денег',"=MIN('Потоки'!L8:L67)",'млн ₽'),
             ('NPV источника, пересчитан',"='Экономика'!B12",'млн ₽'),('IRR источника, пересчитан',"='Экономика'!B13",'доля'),
             ('Стресс DSCR в годы погашения',"=MIN('Годы'!B23:F23)",'раз'),('Минимум денег в стрессе',"=MIN('Потоки'!N8:N67)",'млн ₽'),
             ('Базовый скрининговый предел',"=MAX(0,'Ввод'!B5*B8/'Ввод'!B12)",'млн ₽'),('Стрессовый скрининговый предел',"=MAX(0,'Ввод'!B5*B13/'Ввод'!B12)",'млн ₽'),
             ('Дефицит исходного бюджета',"=MAX(0,'Ввод'!B7-'Ввод'!B5-'Ввод'!B6)",'млн ₽'),('Ориентир суммы с двумя проверками',"=MIN('Ввод'!B5,B15,B16)",'млн ₽'),('Дополнительное покрытие при снижении','=MAX(0,B6-B18)','млн ₽')]
    for row,values in enumerate(metrics,5):
        for col,value in enumerate(values,1):out.cell(row,col,value)
    out['B12'].number_format='0.00%'
    out.merge_cells('A21:H22')
    out['A21']='=IF(ISERROR(B8),"Некорректные входные данные — расчёт заблокирован",IF(OR(B8<\'Ввод\'!B12,B10<0,B17>0),"Требуется пересмотр финансирования и проверка специалистом","Базовые численные проверки пройдены; нужна проверка рисков и заёмщика"))'
    out['A21'].fill=PatternFill('solid',fgColor='FFF1D6');out['A21'].alignment=Alignment(wrap_text=True,vertical='center')
    out.row_dimensions[21].height=25
    out.merge_cells('A24:H26');out['A24']='Скрининговые пределы предполагают фиксированный CFADS и тот же профиль выборки/погашения. Налоги при смене долга не пересчитаны. Снижение кредита требует закрыть дефицит собственными средствами. Механический стресс уменьшает CFADS на 20% абсолютного EBITDA; коммерческие сценарии автора показаны отдельно.'
    out['A24'].alignment=Alignment(wrap_text=True,vertical='center');out.row_dimensions[24].height=30
    chart=LineChart();chart.title='DSCR по годам';chart.y_axis.title='раз';chart.x_axis.title='год'
    for row in (14,18,21):chart.add_data(Reference(annual,min_col=1,max_col=6,min_row=row,max_row=row),from_rows=True,titles_from_data=True)
    chart.set_categories(Reference(annual,min_col=2,max_col=6,min_row=4,max_row=4))
    chart.width,chart.height=22,7
    for series,color in zip(chart.series,(NAVY,TEAL,'999999')):series.graphicalProperties.line.solidFill=color
    chart.series[2].graphicalProperties.line.prstDash='dash';out.add_chart(chart,'A28')
    out.merge_cells('A44:H44');out['A44']='Версия JSON при генерации; ручные правки Excel не обновляют отчёт и хеш'
    out.merge_cells('A45:H46');out['A45']=result['source_sha256'];out['A45'].alignment=Alignment(wrap_text=True)
    out.column_dimensions['A'].width=47;out.column_dimensions['B'].width=21;out.column_dimensions['C'].width=14
    for col in 'DEFGH':out.column_dimensions[col].width=12
    out.print_area='A1:H47';out.freeze_panes=None
    for sheet in book:
        for row in sheet:
            for cell in row:
                if cell.row in (1,2) or cell.fill.fgColor.rgb=='0017324D':continue
                formula=cell.data_type=='f'
                cell.font=Font(name='Arial',size=10,color='007A4B' if formula and '!' in str(cell.value) else ('253348' if formula else '164C96' if isinstance(cell.value,(int,float)) else '253348'))
                cell.alignment=Alignment(vertical='center',wrap_text=cell.column==1)
                if formula or isinstance(cell.value,(int,float)):
                    if cell.number_format=='General':cell.number_format=MONEY
        sheet.sheet_properties.tabColor=TEAL if sheet.title=='Выводы' else NAVY
    for sheet in (debt,flow):
        for row in range(8,68):
            for col in (1,2):sheet.cell(row,col).number_format='0'
    for row in range(22,82):
        for col in (1,2,3):inputs.cell(row,col).number_format='0'
    book.save(path);book.close()


def _conclusion(data, r):
    risks=[]
    if r['min_dscr_repayment'] < 1.2:risks.append('Базовый DSCR в годы погашения ниже условного ориентира 1.20; требуется изменить сумму, график или собственное участие.')
    if r['npv'] < 0:risks.append('NPV отрицательная: показанный пятилетний поток не достигает заданной доходности 22%; остаточная стоимость и высвобождение ОК исключены из исходной оценки.')
    if r['annual'][0]['cfads'] < 0:risks.append('CFADS первого года отрицательный. Положительный денежный остаток поддерживается источниками инвестиционной фазы и не означает операционного покрытия процентов.')
    if r['stress_min_dscr_repayment'] < 1.2:risks.append('При механическом стрессе EBITDA запас покрытия долга ниже 1.20; проверить коммерческий стресс и условия резерва.')
    if data['bridge_2026']['debt'] > 0:risks.append(f"Действующий долг компании на конец 2026 года — {data['bridge_2026']['debt']/1000:.2f} млн ₽. Он не включён в график нового проекта; нужен отдельный анализ совокупного потока заёмщика.")
    if data['id']=='02':risks.append('DSCR относится к потоку всего модернизируемого участка. NPV относится к приросту относительно варианта без модернизации; эти периметры не смешиваются.')
    risks.append('Проверить реализуемость продаж, затраты, обеспечение и исполнение условий до выдачи. Кредитный скоринг и решение уполномоченного органа банка здесь не рассчитываются.')
    table=[('Полный бюджет, млн ₽',f"{r['budget']:.2f}"),('Запрошенный новый кредит, млн ₽',f"{r['loan']:.2f}"),('Собственное участие, млн ₽',f"{r['equity']:.2f}"),
           ('Ставка / срок / отсрочка',f"{r['rate']:.1%} / {r['tenor_months']} мес. / {r['grace_months']} мес."),
           ('Минимальный DSCR в годы погашения',f"{r['min_dscr_repayment']:.6f}"),('Минимум месячных денег, млн ₽',f"{r['minimum_cash']:.6f}"),
           ('NPV / IRR исходного потока',f"{r['npv']:.6f} млн ₽ / {r['irr']:.2%}"),('Стрессовый DSCR в годы погашения',f"{r['stress_min_dscr_repayment']:.6f}"),
           ('Базовый / стрессовый предел, млн ₽',f"{r['base_screening_limit']:.6f} / {r['stress_screening_limit']:.6f}")]
    paragraphs=[
        f"{data['company']}. {data['name']}. Синтетический комплект пользователя, редакция 2; горизонт 2027–2031 годы.",
        'Основание — предоставленные бизнес-план, история РСБУ и структурированный JSON. Независимо проверены помесячный новый кредит, CFADS, ликвидность, NPV и IRR. Операционные прогнозы и налоговый календарь являются данными автора, а не независимо подтверждёнными предпосылками.',
        'Финансовая модель построена по структурированному JSON. Ответы AI оцениваются отдельно по MD/XLSX и не подставляются в расчёт автоматически. Результат является предварительной технической проверкой, а не одобрением банка.',
    ]
    method='Скрининговые пределы предполагают неизменный CFADS при масштабировании долга и неизменный профиль выборки. Налоговые эффекты смены долга не переоценены. Уменьшение кредита само по себе не закрывает бюджет: нужны дополнительные собственные средства или изменение проекта. Механический стресс: минус 20% абсолютного месячного EBITDA при закреплённых остальных потоках.'
    return paragraphs,table,risks,method


def write_industrial_outputs(data: dict, result: dict, destination: Path) -> None:
    if result != audit_project(data):raise ValueError('Stale or mismatched financial audit result')
    destination.mkdir(parents=True,exist_ok=True)
    paragraphs,table,risks,method=_conclusion(data,result)
    lines=['# Предварительное заключение по проекту','']
    lines += [p+'\n' for p in paragraphs]
    lines += ['| Показатель | Результат |','|---|---:|']+[f'| {a} | {b} |' for a,b in table]
    lines += ['','## Риски и вопросы','']+['- '+risk for risk in risks]
    lines += ['','## Границы скрининга','',method,'',f"Максимальное расхождение с помесячными и годовыми показателями исходного JSON: {result['max_reference_difference']:.12g}. Совпадение арифметики не подтверждает реалистичность предпосылок.",'',f"Канонический SHA256 исходного JSON: `{result['source_sha256']}`.",'']
    (destination/'conclusion.md').write_text('\n'.join(lines),encoding='utf-8')
    (destination/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    doc=Document();section=doc.sections[0]
    section.top_margin=section.bottom_margin=Cm(1.8);section.left_margin=section.right_margin=Cm(2)
    normal=doc.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(10)
    normal.paragraph_format.space_after=Pt(6)
    title=doc.styles['Title'];title.font.name='Arial';title.font.size=Pt(20);title.font.color.rgb=RGBColor(0,0,0)
    props=title.element.find(qn('w:pPr'))
    if props is not None:
        for border in list(props.findall(qn('w:pBdr'))):props.remove(border)
    doc.add_paragraph('Предварительное заключение по проекту','Title')
    for text in paragraphs:doc.add_paragraph(text)
    t=doc.add_table(rows=1,cols=2);t.style='Light Shading Accent 1'
    t.rows[0].cells[0].text='Показатель';t.rows[0].cells[1].text='Результат'
    for label,value in table:
        cells=t.add_row().cells;cells[0].text=label;cells[1].text=value
    doc.add_heading('Риски и вопросы',level=1)
    for risk in risks:doc.add_paragraph(risk,style='List Bullet')
    doc.add_heading('Границы расчёта',level=1);doc.add_paragraph(method)
    doc.add_paragraph(f"Сверка арифметики: максимальное отклонение {result['max_reference_difference']:.3g}. Предпосылки автора требуют отдельной проверки.")
    doc.core_properties.author='Technical project audit';doc.core_properties.last_modified_by='Technical project audit'
    doc.save(destination/'conclusion.docx')
    _make_workbook(data,result,destination/'financial-model.xlsx')
