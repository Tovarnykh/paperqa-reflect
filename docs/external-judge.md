# Внешний оценщик: запуск dev-пилота

**Текущий результат 3 октября:** [ограниченная правка extraction v2 завершена](../results/reports/2026-10-03-measurement-repair-v2.md). 20/20 новых извлечений (включая шесть реальных ответов) получили faithful/complete; проверка оценщика 15/16, спорная формулировка сохранена как ограничение. Используем v2 как рабочую версию и возвращаемся к B0/B1/B2 dev experiment, без нового цикла полировки. Для следующих запусков bounded revision явно указывать `--extraction-version v2` (legacy default v1). API ledger $1,201638 / 177 calls. Более ранние checkpoints ниже — история.

Реализован этап A из [evaluation v2](evaluation-judge-protocol-v2.md): отдельная
модель оценивает готовые claims по оригинальным cited passages. В этом CLI нет
генерации PaperQA, автоматического выделения claims, pairwise оценки или исправления
ответов. Это последующие этапы, а не скрытые возможности текущего прототипа.

## Выбор модели и доступа

Профиль `configs/judge-openai-dev-v1.json`: **gpt-6.1-sol**, reasoning medium,
max output 8192 (включает скрытые reasoning tokens), максимум input 60000,
Responses API, строгий JSON, `store:false`, truncation disabled, standard tier,
без tools/поиска/истории чата. Цена проверена по официальной странице 3 октября:
input $2/M, output $10/M, cached input $0.10/M, cache writes $2.50/M.
Для резерва и консервативного учёта весь input считаем по максимуму $2.50/M;
скидки не предполагаем. Это верхний расчёт по usage, не точная копия счёта провайдера.

Выбор — практический компромисс для внешнего judge в бюджете $100, не доказательство
его точности на научных claims. Официальная страница описывает Sol как модель для
сложных задач дешевле Astra. Доступ конкретного API-проекта ещё не проверен.
В разделе snapshots указан только `gpt-6.1-sol`; датированный ID не выдумываем.
Сохраняем запрошенный/возвращённый ID, время, prompt/schema и raw responses.
Одинаковый ID не гарантирует неизменности hosted weights или детерминизма ответов.

Документация: [модель и цена](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[Responses Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[подсчёт токенов](https://developers.openai.com/api/docs/guides/token-counting).

## Подготовка и команды

Команды ниже выполняются из `research/paperqa-reflect` на ноутбуке Windows.
Настоящий API-запуск закреплён за этим host, чтобы две несинхронные копии проекта
не расходовали общий бюджет независимо. На UiA храним код и проверяем тесты;
GPU для внешнего judge не требуется. `.env`, ledger и API-results не синхронизируем.

Ключ читается из `OPENAI_API_KEY` текущего процесса или из локального `.env`.
В созданном `.env` достаточно заполнить строку `OPENAI_API_KEY=`. `.env.example`
содержит пустой шаблон. Ключ не передавать в чат, не коммитить, не копировать в wiki.
`doctor` показывает только наличие ключа, без сети и без проверки оплаты/прав доступа.

```powershell
.venv/Scripts/python.exe -X utf8 -m paperqa_reflect.judge doctor
.venv/Scripts/python.exe -X utf8 -m paperqa_reflect.judge plan
```

`plan` ничего не отправляет: сохраняет 26 анонимных запросов, случайный порядок,
отдельную локальную таблицу соответствий, исходные hashes, prompt/config и
предварительную оценку. Смотрит только cases/passages/manifest, не annotations,
reference answers, predictions или provenance. Полные passages не обрезаются.
Schema содержит названия классов, но не правильные метки конкретных случаев.

План получает уникальный путь `results/judge/<id>`. Подставить **уже подготовленный
и проверенный** путь, не создавать дополнительные планы ради повторных попыток:

```powershell
.venv/Scripts/python.exe -X utf8 -m paperqa_reflect.judge run results/judge/<id>
```

Перед генерацией runner проверяет доступ к точному model ID, считает все входы
через `/v1/responses/input_tokens` с теми же prompt/schema и проверяет лимиты.
Полученный контекст не обязан целиком помещаться в ответ: output8192 предназначен
для краткого verdict плюс reasoning. При исчерпании output результат not_checked,
без автоматического увеличения бюджета. Настройки меняются только новой версией.

Каждый результат содержит raw API response, verdict, точные offsets в originals,
usage, elapsed time, ошибки и ledger ID. Возвращённые model/tier должны совпасть
с квалифицированным профилем. Если hosted API использует другой ID, сначала
разбираем его значение и тариф; автоматической подмены модели нет.

## Лимиты и сбои

- Группа `external-judge-pilot-v1`: максимум $5 на все её планы/попытки вместе.
  Общий проектный максимум ledger: $100. Лимит не сбрасывается новым запуском.
- SQLite ledger `results/api-budget.sqlite3` резервирует возможную стоимость до
  отправки. Транзакции сериализуют конкурирующие вызовы. Ledger нельзя удалять
  ради повтора. Он учитывает вызовы этого runner; внешние траты проекта нужно
  внести отдельно перед следующими сериями. Это не provider-side billing cap.
- После известного usage резерв заменяется консервативным расчётом; reasoning
  уже входит в output_tokens и не начисляется второй раз.
- Timeout, неизвестный usage или незавершённый процесс оставляют полную сумму
  зарезервированной. «Нет ответа» не означает «не было списания». Автоматических
  retries нет. Старый план повторно не запускается. Разбор по журналу и API usage
  предшествует любому осознанному новому вызову.
- Некорректная цитата/JSON, отказ или incomplete остаются not_checked, не insufficient.
  Провал транспорта останавливает серию; семантически невалидный результат
  сохраняется и не исключается из отчёта. Все попытки остаются на диске.
- Цена действует в профиле 14 дней с проверки, затем run потребует её обновления.
  Предварительная byte-based оценка не является измеренным token count или ценой;
  настоящий резерв использует серверный count и max output. Если runtime usage
  превысит резерв, перерасход записывается и новые вызовы блокируются до разбора.

## Отчёт

После реального запуска:

```powershell
.venv/Scripts/python.exe -X utf8 -m paperqa_reflect.judge_report results/judge/<id> results/verifier/20261003T134932Z-f2aafd --output results/judge/<id>/comparison
```

Отчёт не меняет предыдущий run и assistant annotations. Он создаёт новые
`annotations.external-judge.jsonl`, `assessment.json` и `assessment.md`.
Reference type явно `external_llm_judge`, independently_adjudicated=false.
Natural/control разделены; coverage и неизвестные reference cases показаны
отдельно. Метрики считаются относительно доступных verdicts внешней модели,
с границами agreement для неизвестной части, не называются экспертной accuracy.
Пропущенные проверки не превращаются в удобные метки и не исчезают из знаменателей.

План из первого чернового dry-run до тестов имел Windows newline/hash дефект.
Он не отправлялся. Исправленная реализация пишет prompt bytes без преобразования
переносов строк; использовать актуальный проверенный план из отчёта подготовки.
