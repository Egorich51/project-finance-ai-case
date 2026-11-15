"""Reproduce GPU scores and two financial examples using saved answers only."""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.finance import calculate
from src.gpu_benchmark import score_gpu_records
from src.report import write_outputs


def main():
    root = Path(__file__).resolve().parents[1] / 'benchmarks'
    rows = score_gpu_records(root / 'results/raw', root / 'cases')
    models = ['Qwen/Qwen2.5-1.5B-Instruct', 'Qwen/Qwen2.5-7B-Instruct']
    cases = {item['case_id'] for item in json.loads((root / 'cases/manifest.json').read_text())}
    if len(rows) != 12 or {row['model'] for row in rows} != set(models):
        raise SystemExit(f'Expected twelve first responses from two models; found {len(rows)}. No report written.')
    for model in models:
        if {r['case_id'] for r in rows if r['model'] == model} != cases:
            raise SystemExit('Incomplete case coverage: ' + model)
    summary = []
    for model in models:
        selected = [row for row in rows if row['model'] == model]
        summary.append({
            'model': model,
            'fields_correct': sum(r['evaluation']['fields']['correct'] for r in selected),
            'fields_total': sum(r['evaluation']['fields']['total'] for r in selected),
            'sources_correct': sum(r['evaluation']['sources']['correct'] for r in selected),
            'sources_total': sum(r['evaluation']['sources']['total'] for r in selected),
            'issues_true_positive': sum(r['evaluation']['issues']['true_positive'] for r in selected),
            'issues_false_negative': sum(r['evaluation']['issues']['false_negative'] for r in selected),
            'issues_false_positive': sum(r['evaluation']['issues']['false_positive'] for r in selected),
            'parse_failures': sum(bool(r['parse_error']) for r in selected),
            'top_level_contract': sum(r['top_level_contract'] for r in selected),
            'median_generation_seconds': statistics.median(r['elapsed_seconds'] for r in selected if r['elapsed_seconds'] is not None),
        })
    environments = {slug: json.loads((root / 'results/raw' / slug / 'environment.json').read_text()) for slug in ('qwen-1.5b', 'qwen-7b')}
    result = {'summary': summary, 'cases': rows, 'environment': environments}
    (root / 'results/summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# Извлечение данных для малого и среднего бизнеса', '',
        'Два синтетических бизнес-сценария, по три варианта документов, две модели на двух Tesla T4 в Kaggle. Двенадцать первых ответов сохранены без отбора удачных попыток. Это техническое сравнение конфигураций, а не оценка точности на банковской выборке.', '',
        '## Результат сравнения', '',
        '| Модель | Верные поля | Адреса источников | Найдено проблем | Ложные сигналы | Ошибки JSON/обрезка | Медиана генерации, с |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for item in summary:
        lines.append(f"| {item['model'].split('/')[-1]} | {item['fields_correct']}/{item['fields_total']} | {item['sources_correct']}/{item['sources_total']} | {item['issues_true_positive']}/{item['issues_true_positive']+item['issues_false_negative']} | {item['issues_false_positive']} | {item['parse_failures']}/6 | {item['median_generation_seconds']:.2f} |")
    lines += ['', '## Как понимать эти числа', '',
        'Доля верных полей относится только к значению, единице и периоду. Это не общая точность системы: адреса источников и ложные сигналы считаются отдельно. В зафиксированном прогоне 7B дала 64/66 таких полей, но 0/78 точных ожидаемых адресов и 18 лишних сигналов проблем.', '',
        'Нулевой результат маленькой модели по полям вызван непригодностью всех шести ответов для прямого JSON-разбора, а не доказательством, что она не прочитала ни одного числа. Например, small-complete содержит Markdown-ограждение и выражение `18 / 100` вместо JSON-числа. Снятие одних ограждений не исправляет такой ответ; автоматическая или ручная починка перед основной оценкой не применялась.', '',
        'У 7B многие адреса узнаваемы человеком, но записаны как `"locator": "[financials.xlsx|Forecast!B4]"` вместо требуемого `"locator": "Forecast!B4"`. Поэтому ноль в строгой метрике не равен утверждению, что все ссылки семантически неверны. Формат можно нормализовать в следующей версии пайплайна; текущая таблица сохраняет первоначальный контракт.', '',
        '7B указала все четыре заложенные проблемы, однако 18 ложных сигналов показывают высокую стоимость проверки. Кроме того, в обоих конфликтных случаях модель самостоятельно выбрала одну сумму бюджета вместо null и списка двух версий. Поэтому два бюджетных поля не засчитаны, а прямое заполнение расчёта остаётся недопустимым без подтверждения.', '']
    lines += ['', '## По каждому варианту', '', '| Бизнес | Документы | Модель | Поля | Источники | TP / FN / FP проблем | Ошибка разбора |', '|---|---|---|---:|---:|---:|---|']
    for row in sorted(rows, key=lambda r: (r['business'], r['variant'], r['model'])):
        fields, sources, issues = (row['evaluation'][key] for key in ('fields', 'sources', 'issues'))
        lines.append(f"| {row['business']} | {row['variant']} | {row['model'].split('/')[-1]} | {fields['correct']}/{fields['total']} | {sources['correct']}/{sources['total']} | {issues['true_positive']} / {issues['false_negative']} / {issues['false_positive']} | {'Да' if row['parse_error'] else 'Нет'} |")
    lines += ['', '## Протокол', '',
        '- `small`: небольшая пекарня, бюджет 8 млн ₽, собственное участие 3 млн ₽; CFADS задан в тысячах рублей.',
        '- `medium`: расширение мебельного производства, бюджет 120 млн ₽, собственное участие 45 млн ₽; CFADS задан в миллионах рублей.',
        '- `complete`: сведения согласованы; `budget_conflict`: бюджеты различаются между Word и Excel; `missing_equity`: собственное участие отсутствует в обоих документах.',
        '- Эталоны, промпты и источники зафиксированы в коммите `fc169b2` до запуска. На GPU переданы только исходные тексты и промпты; эталоны и финансовые уточнения остались локально. input_sha256 относится к пользовательскому промпту; одинаковый системный промпт зафиксирован в коде worker.',
        '- Один общий системный промпт и один контракт извлечения. Обе модели: 4-bit NF4, double quantization, FP16 compute; greedy decoding, seed=42, max_new_tokens=2500, без обрезки входных документов.',
        '- Метрики посчитаны по первым сырым ответам. Невалидный JSON и достижение предела токенов считаются неудачей. Никакой ручной починки перед оценкой нет.', '',
        'Верное поле означает совпадение значения, единицы и периода одновременно. Деньги нормализуются с допуском 0.000001 млн ₽. Конфликт требует сохранения обеих версий, пропуск — явного null. Источники оцениваются отдельно по ожидаемым адресам и не подтверждают смысловую поддержку значения. Альтернативные допустимые цитаты не размечены. Проблемы учитываются только в предусмотренном верхнеуровневом issues; TP — верные сигналы, FN — пропущенные, FP — лишние.', '',
        'Числовое значение может быть верным, но поле не засчитано из-за неправильной единицы или периода. Формат и качество каждого ответа можно проверить в [сырых результатах](results/raw/); полные списки ошибок находятся в [summary.json](results/summary.json).', '',
        '## Окружение', '',
    ]
    for slug, env in environments.items():
        lines.append(f"- {env['model']}, revision `{env['revision']}`, {env['gpu_name']}, версии: `{json.dumps(env['versions'], ensure_ascii=False)}`. [Метаданные](results/raw/{slug}/environment.json).")
    lines += ['', 'Каждая модель работала на своей T4. Время — длительность генерации с синхронизацией GPU, без загрузки весов. Это не время подготовки проверенного кредитного заключения и не замер экономии труда. Одновременная работа и общий CPU/диск ограничивают интерпретацию скоростного сравнения.', '',
        '## Два расчётных примера', '', '| Бизнес | Потребность, млн ₽ | Базовый предел | Стрессовый предел | Дефицит |', '|---|---:|---:|---:|---:|']
    for business in ('small', 'medium'):
        data = json.loads((root / 'cases' / business / 'complete/confirmed.json').read_text())
        financial = calculate(data)
        write_outputs(data, financial, root / 'examples' / business)
        lines.append(f"| [{business}](examples/{business}/decision.md) | {financial['need']:.6f} | {financial['capacity_base']:.6f} | {financial['capacity_stress']:.6f} | {financial['funding_gap']:.6f} |")
    lines += ['', 'Финансовые результаты строятся по отдельно подтверждённым автором условиям, а не непосредственно по ответу модели. При конфликте бюджета или отсутствии собственного участия автоматический расчёт должен останавливаться; файлы confirmed.json содержат явные уточнения для продолжения демонстрации. Выполнение условного DSCR не является одобрением кредита.', '',
        '## Границы выводов', '',
        'Это два авторских примера; три варианта одного бизнеса зависимы и не являются тремя независимыми компаниями. Модели не обучались и промпт не подбирался по этим ответам. Сравнение с ручной работой и извлечением по правилам не выполнено. Оценки не подтверждают качество на других шаблонах, реальных сделках или экономию 30% рабочего времени.', '',
        'Предварительный [запуск Ollama](../output/research.md) сохранён отдельно: другие входные данные, квантование и runtime не позволяют смешивать его цифры с этим сравнением. Разницу двух новых конфигураций также нельзя объяснять только числом параметров — отличаются конкретные обученные модели.', '',
        'Воспроизведение оценки и финансовых примеров без GPU и сети: `python scripts/summarize_gpu_benchmark.py`. Полный [протокол](../docs/benchmark-protocol.md) и [манифест](cases/manifest.json) доступны в репозитории.', '']
    (root / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
