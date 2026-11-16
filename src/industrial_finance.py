"""Independent schedule and cash arithmetic for the supplied industrial models.

Money is converted from source thousands of RUB to millions. Operating drivers,
tax payments and unlevered FCF remain explicitly supplied source assumptions.
"""
import math
import hashlib
import json


def npv(rate: float, flows: list[float]) -> float:
    return sum(value / (1 + rate) ** period for period, value in enumerate(flows))


def irr(flows: list[float]) -> float:
    nonzero = [v for v in flows if v]
    if sum(a * b < 0 for a, b in zip(nonzero, nonzero[1:])) != 1:
        raise ValueError('IRR requires a single sign change in this audit')
    low, high = -0.99, 1.0
    while npv(high, flows) > 0 and high < 1024:
        high *= 2
    if npv(low, flows) * npv(high, flows) > 0:
        raise ValueError('IRR not bracketed')
    for _ in range(120):
        middle = (low + high) / 2
        if npv(middle, flows) > 0:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def audit_project(data: dict) -> dict:
    p, original = data['project'], data['business_plan_v2']
    if not math.isfinite(p['annual_rate']) or p['annual_rate'] < 0:
        raise ValueError('Invalid annual rate')
    tenor, grace = p['tenor_months'], p['grace_months']
    loan, equity, budget = (p[key] / 1000 for key in ('loan', 'equity_total', 'total_funding'))
    if not isinstance(tenor, int) or not isinstance(grace, int) or not 0 <= grace < tenor:
        raise ValueError('Invalid tenor/grace')
    if len(original['monthly']) != tenor or abs(sum(p['draw_months']) / 1000 - loan) > 1e-8:
        raise ValueError('Missing months or draw/limit mismatch')
    if abs(loan + equity - budget) > 1e-8:
        raise ValueError('Sources do not cover the investment budget')
    if abs((p['capex_gross'] + p['working_capital'] + p['liquidity_reserve']) / 1000 - budget) > 1e-8:
        raise ValueError('Budget components mismatch')
    debt, cash, stressed_cash = 0.0, 0.0, 0.0
    monthly, differences = [], []
    for index, source in enumerate(original['monthly']):
        if (source['year'], source['month']) != (2027 + index // 12, 1 + index % 12):
            raise ValueError('Monthly periods out of order')
        draw = p['draw_months'][index] / 1000 if index < len(p['draw_months']) else 0.0
        row = {key: source[key] / 1000 for key in ('ebitda', 'tax', 'change_nwc', 'maintenance', 'equity', 'capex', 'vat_refund')}
        if not all(math.isfinite(v) for v in row.values()):
            raise ValueError('Non-finite operating input')
        row.update(year=source['year'], month=source['month'], draw=draw, debt_opening=debt)
        interest = (debt + draw) * p['annual_rate'] / 12
        principal = loan / (tenor - grace) if index >= grace else 0.0
        debt = debt + draw - principal
        if abs(debt) < 1e-9:
            debt = 0.0
        cfads = row['ebitda'] - row['tax'] - row['change_nwc'] - row['maintenance']
        service = interest + principal
        delta = cfads - service + draw + row['equity'] - row['capex'] + row['vat_refund']
        cash += delta
        stress_cfads = cfads - 0.2 * abs(row['ebitda'])
        stressed_cash += stress_cfads - service + draw + row['equity'] - row['capex'] + row['vat_refund']
        row.update(interest=interest, principal=principal, debt_closing=debt, cfads=cfads,
                   debt_service=service, cash_change=delta, cash=cash, stress_cfads=stress_cfads, stress_cash=stressed_cash)
        for key in ('interest', 'principal', 'draw', 'cash', 'cash_change'):
            differences.append(abs(row[key] - source[key] / 1000))
        monthly.append(row)
    annual = []
    source_annual = {item['year']: item for item in original['annual']}
    for year in range(2027, 2032):
        rows = [r for r in monthly if r['year'] == year]
        sums = {key: sum(r[key] for r in rows) for key in ('ebitda', 'tax', 'change_nwc', 'maintenance', 'interest', 'principal', 'draw', 'equity', 'capex', 'vat_refund', 'cfads', 'debt_service', 'stress_cfads')}
        sums.update(year=year, debt_closing=rows[-1]['debt_closing'], cash=rows[-1]['cash'],
                    stress_cash=rows[-1]['stress_cash'], dscr=sums['cfads'] / sums['debt_service'] if sums['debt_service'] else None,
                    stress_dscr=sums['stress_cfads'] / sums['debt_service'] if sums['debt_service'] else None)
        for key in ('cfads', 'ebitda', 'interest', 'principal', 'cash'):
            differences.append(abs(sums[key] - source_annual[year][key] / 1000))
        differences.append(abs(sums['dscr'] - source_annual[year]['dscr']))
        annual.append(sums)
    flows = [value / 1000 for value in original['unlevered_flows']]
    discount = original['metrics']['discount_rate']
    calculated_npv, calculated_irr = npv(discount, flows), irr(flows)
    differences.extend([abs(calculated_npv - original['metrics']['npv_22'] / 1000), abs(calculated_irr - original['metrics']['irr'])])
    repay = [r for r in annual if r['principal'] > 1e-9]
    minimum = min(r['dscr'] for r in repay)
    stressed_minimum = min(r['stress_dscr'] for r in repay)
    return {
        'source_sha256': hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest(),
        'project_id': data['id'], 'project_name': data['name'], 'company': data['company'],
        'unit': 'million_rub', 'loan': loan, 'equity': equity, 'budget': budget,
        'rate': p['annual_rate'], 'tenor_months': tenor, 'grace_months': grace,
        'monthly': monthly, 'annual': annual, 'unlevered_flows': flows, 'discount_rate': discount,
        'npv': calculated_npv, 'irr': calculated_irr,
        'min_dscr_repayment': minimum, 'min_dscr_all': min(r['dscr'] for r in annual),
        'minimum_cash': min(r['cash'] for r in monthly), 'minimum_cash_month': min(monthly, key=lambda r: r['cash'])['month'],
        'stress_min_dscr_repayment': stressed_minimum, 'stress_minimum_cash': min(r['stress_cash'] for r in monthly),
        'screening_dscr_floor': 1.2,
        'base_screening_limit': max(0, loan * minimum / 1.2),
        'stress_screening_limit': max(0, loan * stressed_minimum / 1.2),
        'max_reference_difference': max(differences),
        'notes': ['Операционные потоки, налоговые платежи и бездолговой FCF взяты из предоставленного JSON.',
                  'Независимо пересчитаны проценты, погашение, CFADS, деньги, DSCR, NPV и IRR.',
                  'Скрининговый лимит предполагает фиксированный CFADS; налоги и операционные потоки при смене долга не переоцениваются.',
                  'Механический стресс: CFADS уменьшается на 20% абсолютного месячного EBITDA; прочие потоки закреплены.',
                  'Существующие кредиты компании не включены в график нового проекта; анализ всего заёмщика требует отдельного потока.'],
    }
