"""Validate confirmed inputs and reproduce the calculation without a model."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.finance import calculate
from src.report import write_outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('case/confirmed.json'))
    parser.add_argument('--output', type=Path, default=Path('output'))
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('Входной JSON должен быть объектом')
        result = calculate(data)
        write_outputs(data, result, args.output)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f'Расчёт заблокирован: {error}\n')
    print(f'Сумма: {result["proposed_amount"]:.6f} млн ₽; дефицит: {result["funding_gap"]:.6f} млн ₽')
    print(f'Результаты: {args.output}')


if __name__ == '__main__':
    main()
