def confirmed_case():
    return {
        'budget': 100, 'equity': 40, 'rate': 0.15, 'years': 5,
        'cfads': [24, 26, 28, 30, 32], 'stress_factor': 0.8,
        'dscr_floor': 1.2, 'unit': 'million_rub',
        'resolutions': [
            {'field': 'budget', 'value': 100, 'status': 'confirmed', 'confirmed_by': 'case_author', 'note': 'Synthetic clarification'},
            {'field': 'equity', 'value': 40, 'status': 'confirmed', 'confirmed_by': 'case_author', 'note': 'Synthetic clarification'},
        ],
    }
