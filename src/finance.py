"""Deterministic annual debt schedule; demonstration rules, not bank policy."""
import hashlib
import json

from src.extraction import validate_confirmed


def calculate(data: dict) -> dict:
    errors = validate_confirmed(data)
    if errors:
        raise ValueError('; '.join(errors))
    years, rate, floor = data['years'], data['rate'], data['dscr_floor']
    base = data['cfads']
    stress = [value * data['stress_factor'] for value in base]

    def capacity(flows):
        if min(flows) <= 0:
            return 0.0
        return min(flow / (floor * (1 / years + rate * (1 - t / years))) for t, flow in enumerate(flows))

    need = max(data['budget'] - data['equity'], 0)
    capacity_base, capacity_stress = capacity(base), capacity(stress)
    amount = min(need, capacity_base, capacity_stress)

    def schedule(flows):
        rows = []
        principal = amount / years
        for t, flow in enumerate(flows):
            opening = max(amount - t * principal, 0.0)
            interest = opening * rate
            service = principal + interest
            rows.append({
                'year': t + 1,
                'opening_debt': opening,
                'principal': principal,
                'interest': interest,
                'debt_service': service,
                'cfads': flow,
                'dscr': flow / service if service > 0 else None,
                'closing_debt': max(amount - (t + 1) * principal, 0.0),
            })
        return rows

    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return {
        'case_id': data.get('case_id', 'synthetic-case'),
        'input_sha256': fingerprint,
        'unit': 'million_rub',
        'need': need,
        'capacity_base': capacity_base,
        'capacity_stress': capacity_stress,
        'proposed_amount': amount,
        'funding_gap': need - amount,
        'base_schedule': schedule(base),
        'stress_schedule': schedule(stress),
    }
