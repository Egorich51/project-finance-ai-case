# Financing Case Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Подготовить за три часа воспроизводимый синтетический пример и короткое исследование для приложения к заявке по одной ссылке.

**Architecture:** DOCX и XLSX преобразуются в текст с адресами источников для AI. Сохранённый ответ оценивается по независимому эталону, подтверждённые человеком данные поступают в детерминированный расчёт. Один скрипт формирует Excel, JSON и Markdown-отчёт; README объединяет материалы.

**Tech Stack:** Python 3.11+, unittest, openpyxl, python-docx; готовая доступная языковая модель без обучения.

**Spec:** `docs/superpowers/specs/2026-11-15-financing-case-design.md` — предложенный дизайн, требует проверки пользователем перед реализацией.

## Global Constraints

- Бюджет времени: 180 минут, включая 30 минут резерва на проверку и публикацию.
- Денежная единица расчёта — млн рублей.
- Ответ AI сохраняется до исправлений; эталон не передаётся модели. Исправления хранятся отдельно.
- 30% экономии времени и 95% точности из заявки остаются целями будущей проверки.
- Синтетические документы не содержат персональных или конфиденциальных сведений. Ключи API и локальные настройки не публикуются.
- Нет веб-сервиса, RAG, обучения моделей, реального скоринга, полной прогнозной отчётности и интеграций.
- Все численные ограничения демонстрационные, не нормативы банка. Перезапуск расчёта не требует API.

## Review Focus

- Отсутствующее собственное участие не превращается в ноль: расчёт блокируется — Task 2.
- Противоречивые бюджеты не разрешаются молча: нужен подтверждённый выбор — Task 2.
- Тысячи и миллионы рублей нормализуются с сохранением периода и источника — Task 1 и Task 2.
- Нулевая ставка и неположительный CFADS обрабатываются явно — Task 3.
- При пределе ниже потребности отчёт показывает дефицит, а не обещает полное финансирование — Task 3 и Task 4.

---

## File Structure

- `README.md`: главная страница и ограничения.
- `requirements.txt`, `.gitignore`: две зависимости, исключение секретов и временных файлов.
- `case/source/project.docx`, `case/source/financials.xlsx`: синтетические исходники.
- `case/gold.json`: независимый эталон полей и проблем.
- `case/prompt.md`, `case/model-response.txt`, `case/extracted.json`: промпт, сырой ответ, разобранный ответ до исправлений.
- `case/confirmed.json`: подтверждённые значения и история разрешения проблем.
- `src/fixtures.py`: создание документов и эталона.
- `src/extraction.py`: подготовка входа, оценка и проверка данных.
- `src/finance.py`: расчёты без внешних зависимостей.
- `src/report.py`: Excel и Markdown из одного результата.
- `scripts/run_case.py`: запуск проверки, расчёта и экспорта.
- `tests/test_fixtures.py`, `tests/test_extraction.py`, `tests/test_finance.py`, `tests/test_report.py`: проверки существенных ошибок.
- `output/`: подготовленные результаты и протокол исследования.

### Task 1: Синтетические документы и независимый эталон — 25 минут

**Files:** Create `src/__init__.py`, `src/fixtures.py`, `tests/__init__.py`, `tests/test_fixtures.py`, `requirements.txt`, `.gitignore`, `case/source/*`, `case/gold.json`.

**Interfaces:** Produces `build_case(destination: pathlib.Path) -> None`. JSON поля имеют структуру `{value, unit, period, sources}`; источник — `{file, locator}`. Периоды CFADS: годы 1–5, остальных условий: `project`. Отсутствующее значение — null. Проблемы — `{field, kind, sources}`, kind: `missing` или `conflict`.

- [ ] Написать тест `test_case_has_traceable_conflict_and_missing_equity`: прочитать созданные DOCX/XLSX; бюджет в DOCX 100 млн, в Excel 110000 тыс.; equity отсутствует; CFADS [24,26,28,30,32] млн; для всех эталонных значений существуют указанные ячейки/абзацы. Эталон хранит обе версии бюджета и две ожидаемые проблемы.
- [ ] Выполнить `python -m unittest tests.test_fixtures -v`: ожидается ошибка импорта до реализации.
- [ ] Реализовать `build_case` с фиксированными значениями дизайна; создать окружение и установить только openpyxl/python-docx. Сгенерировать документы в `case/`. Эталон создаётся до обращения к AI.
- [ ] Повторить тест: PASS. Просмотреть текст DOCX и значения XLSX, убедиться в синтетической маркировке.
- [ ] Инициализировать Git в текущей папке, если он по-прежнему отсутствует; добавлять только файлы задачи, не существующие пользовательские материалы. Commit: `feat: add synthetic financing case`.

### Task 2: Фактический запуск AI, проверка и подтверждение — 45 минут

**Files:** Create `src/extraction.py`, `tests/test_extraction.py`, `case/prompt.md`, `case/model-response.txt`, `case/extracted.json`, `case/confirmed.json`, `output/extraction-evaluation.json`.

**Interfaces:** Consumes Task 1 schema. Produces `prepare_input(source_dir: Path) -> str`, `evaluate(predicted: dict, gold: dict) -> dict`, `validate_confirmed(data: dict) -> list[str]`. Confirmed JSON содержит `budget`, `equity`, `rate`, `years`, `cfads`, `stress_factor`, `dscr_floor`, `unit`, `resolutions`; числовые значения — из дизайна, unit=`million_rub`. `resolutions` явно фиксирует оба исходных бюджета, выбранные 100 млн и добавленные 40 млн equity как решение автора синтетического кейса.

- [ ] Написать тесты: `test_input_preserves_locators` проверяет адрес каждой ячейки/абзаца; `test_missing_equity_blocks` проверяет непустые ошибки при null; `test_unresolved_budget_blocks` проверяет ошибку без разрешения conflict; `test_units_and_periods_matter` не засчитывает 110000 тыс. как 110000 млн или CFADS другого года; `test_missing_prediction_counts_wrong` оставляет отсутствующее поле в знаменателе.
- [ ] Выполнить `python -m unittest tests.test_extraction -v`: ожидается ошибка импорта.
- [ ] Реализовать функции. Метрики: верные поля / все ожидаемые поля; верные пары поле–источник / все ожидаемые пары; отдельно найденные/пропущенные/ложные проблемы. Числовая погрешность после нормализации: 1e-6 млн. Известный конфликт засчитывается только при сохранении обеих версий. Подготовить промпт без эталона, запрещающий угадывать пропуски.
- [ ] Повторить тесты: PASS. Выполнить один фактический запуск доступной модели на подготовленных документах; сохранить сырой ответ, дату, название модели и способ запуска. Не создавать фиктивный ответ. Если API недоступен, использовать ручной запуск; если и он невозможен, записать «не выполнено» и продолжить как расчётный пример.
- [ ] Оценить неизменённый ответ, записать ошибки и ограничения; отдельно подготовить confirmed JSON с пояснениями автора. Commit: `feat: record extraction experiment and confirmed inputs`.

### Task 3: Прозрачный расчёт — 40 минут

**Files:** Create `src/finance.py`, `tests/test_finance.py`.

**Interfaces:** Consumes validated confirmed JSON. Produces `calculate(data: dict) -> dict` с ключами `need`, `capacity_base`, `capacity_stress`, `proposed_amount`, `funding_gap`, `base_schedule`, `stress_schedule`. Строка графика: `year`, `opening_debt`, `principal`, `interest`, `debt_service`, `cfads`, `dscr`, `closing_debt`. DSCR при нулевом debt_service — null, не Infinity.

- [ ] Написать тесты `test_known_case`: need=60, base capacity≈57.14285714, stress capacity≈45.71428571, proposed≈45.71428571, gap≈14.28571429 (погрешность 1e-6); `test_zero_rate`: ставка 0 даёт stress capacity=80; proposed=60 из-за ограничения потребностью; `test_nonpositive_cfads`: при CFADS первого года 0 или -1 capacity=0; `test_invalid_terms`: отрицательная ставка, years=0 и несовпадающая длина CFADS дают ValueError; `test_schedule_conserves_principal`: сумма principal равна долгу, closing_debt последнего года≈0, минимум стрессового DSCR≈1.2.
- [ ] Выполнить `python -m unittest tests.test_finance -v`: ожидается ошибка импорта.
- [ ] Реализовать `calculate`. Для положительного CFADS предел в году t: CFADS[t] / (dscr_floor × (1/years + rate × (1 − t/years))), t начинается с 0. Предел сценария — минимум за годы. При неположительном CFADS предел 0. Proposed=min(max(budget−equity,0), capacity_base, capacity_stress); gap=need−proposed. Проценты на остаток начала года; равное погашение основного долга. При equity>budget need=0.
- [ ] Повторить тесты: PASS. Сверить первый стрессовый год вручную: CFADS=19.2, обслуживание долга=16, DSCR=1.2 при proposed≈45.71428571.
- [ ] Commit: `feat: calculate transparent debt capacity`.

### Task 4: Один комплект для просмотра и воспроизведения — 40 минут

**Files:** Create `src/report.py`, `scripts/run_case.py`, `tests/test_report.py`, `README.md`, `output/model.xlsx`, `output/decision.md`, `output/calculation.json`, `output/research.md`.

**Interfaces:** Consumes Task 2 validation and Task 3 result. Produces `write_outputs(data: dict, result: dict, destination: Path) -> None`; CLI `python scripts/run_case.py --input case/confirmed.json --output output`. При невалидных данных CLI завершается ненулевым кодом до записи новых результатов.

- [ ] Написать тесты `test_report_matches_calculation`: JSON и Markdown содержат одну сумму и дефицит, Excel Input хранит те же параметры, Output и графики используют формулы; `test_invalid_input_does_not_write_outputs`: нет новых файлов при пропуске equity; `test_zero_debt_has_no_division_error`: Excel защищает деление при нулевом долге. Проверить отсутствие утверждения «проект полностью профинансирован» при gap>0.
- [ ] Выполнить `python -m unittest tests.test_report -v`: ожидается ошибка импорта.
- [ ] Реализовать экспорт и CLI. Листы Excel: Input, Base, Stress, Output; формулы повторяют расчёт Python и ссылаются на Input. Включить пересчёт при открытии. В research.md разделить протокол, фактические наблюдения, ошибки и ограничения; при отсутствии AI-запуска явно написать это. Не включать выдуманные результаты.
- [ ] Написать README: задача, синтетическая маркировка, короткий маршрут просмотра с относительными ссылками, схема Mermaid, запуск, результаты, ограничения и отличие демонстрации от полного MVP. Указать, что скоринг и полная отчётность не реализованы.
- [ ] Выполнить `python -m unittest discover -s tests -v` и команду CLI: все тесты PASS, файлы созданы. Открыть Excel в доступном табличном движке, пересчитать и сравнить Output с Python в пределах 1e-6. Если движка нет, не утверждать проверку вычисленных Excel-формул: указать ограничение и оставить JSON источником проверенных чисел.
- [ ] Commit: `docs: package reproducible financing case`.

## Резерв: 30 минут и публикация

- [ ] Проверить состав Git: только предназначенные для публикации материалы, без ключей, .env и пользовательских черновиков. Не использовать `git add .`.
- [ ] Проверить доступный GitHub-аккаунт и способ публикации. Создать отдельный публичный репозиторий для этого синтетического комплекта, если публичная публикация подтверждена пользователем при выборе плана; иначе подготовить локальный комплект и запросить конкретную недостающую настройку видимости/назначения.
- [ ] Проверить главную страницу и ссылки в опубликованном репозитории без авторизации. Вернуть одну ссылку для анкеты. При отсутствии доступа честно сообщить, что готов локальный материал, а не опубликованная ссылка.

## Self-Review

Покрыты все требования предложенного дизайна. Пять рисков Review Focus закреплены за проверками. Интерфейсы evaluate/validate_confirmed/calculate/write_outputs согласованы. Четыре задачи и резерв укладываются в 180 минут; при задержке исключать оформление и API-автоматизацию, сохранять расчёт, проверку и честность выводов. Этот план не является разрешением начать реализацию до пользовательской проверки.
