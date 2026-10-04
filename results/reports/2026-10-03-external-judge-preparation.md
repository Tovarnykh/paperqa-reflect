# Внешний judge подготовлен; API-пилот ожидает ключ

**Обновление 3 октября:** [API pilot завершён](../../results/reports/2026-10-03-external-judge-pilot.md): 26/26 checks, agreement 20/20 natural и 5/6 controlled, учтено $0,210922. Ключ предоставлен; прежние описания ожидания исторические. Локальный bounded-revision pilot запущен, результат ещё не установлен.

Поручение пользователя: последовательно выполнять план до действия, требуемого
с его стороны. Реализован отдельный внешний evaluator для готовых claim cases,
не меняющий baseline, локальный verifier или сохранённые ответы.

## Готово и проверено

- `paperqa_reflect.judge plan|doctor|run`: анонимизация, независимый prompt,
  проверяемые полные входы, frozen request/config hashes, Responses JSON schema,
  exact evidence quotes/offsets, raw outputs, usage, errors, time и source snapshots.
- `paperqa_reflect.judge_report`: сравнение local verifier с внешними labels,
  natural/control отдельно, известные/неизвестные reference cases, false flags,
  confusion, agreement bounds. LLM labels не помечаются human gold.
- SQLite ledger: атомарный резерв перед запросом, общий pilot cap $5 и project
  cap $100, учёт reasoning в output, сохранение неизвестной стоимости после
  timeout, без автоматических retries. Платный run закреплён за ноутбуком.
- **99 tests passed**, Ruff passed на Windows и UiA; перенос 7 code/doc файлов проверен по hashes. Сеть заменена MockTransport в
  integration tests: это проверка реализации, не API/model integration.
- Исходный пакет: **26 cases / 16 passages / 16 исходных ответов в inventory**,
  контроль hashes/offsets `INTEGRITY_OK`. Assistant labels, local predictions,
  baseline и holdout не менялись.
- Проверено отсутствие OPENAI_API_KEY в Windows process/user/machine; до
  создания пустого шаблона не было project `.env`. На UiA process key и project
  `.env` также отсутствуют. Значения credentials не выводились и не извлекались.
- `.env`, API plans/results и ledger исключены из Git. Шаблон `.env` создан
  только на ноутбуке, пуст. На сервер копируются код/документы, не секреты.

## Подготовленная конфигурация

`configs/judge-openai-dev-v1.json`: gpt-6.1-sol, reasoning medium, output cap8192,
input cap60000, request timeout600s. Официальные цены проверены 3 октября:
$2/M input, $10/M output; бюджетный учёт всего input по верхней ставке $2.50/M,
учитывающей cache writes. Это консервативный расход по usage, не точный invoice.
Sol выбран для сложного внешнего анализа в данном бюджете, не как доказанный
лучший научный judge. API-доступ и его качество пока не проверены.

В официальном разделе snapshots указан только `gpt-6.1-sol`, без датированного
варианта. Запрошенный/возвращённый ID сохраняется; неизменность весов не гарантируется.
[Первичный источник модели и цен](https://developers.openai.com/api/docs/models/gpt-6.1-sol).

## Точный checkpoint продолжения

Рабочий offline plan: **`results/judge/20261003T145512Z-24c127`**.
Все 26 запросов сохранены; предварительный byte-based резерв: **USD 3.169510**,
включая максимальный output/reasoning. Это не measured token count и не расход.
Перед платным вызовом обязательны server input counts и повторная проверка cap.
Цена профиля требует перепроверки после 17 октября; протокол не меняет её молча.

```powershell
# Из research/paperqa-reflect, после заполнения локального .env:
.venv/Scripts/python.exe -X utf8 -m paperqa_reflect.judge doctor
.venv/Scripts/python.exe -X utf8 -m paperqa_reflect.judge run results/judge/20261003T145512Z-24c127
.venv/Scripts/python.exe -X utf8 -m paperqa_reflect.judge_report results/judge/20261003T145512Z-24c127 results/verifier/20261003T134932Z-f2aafd --output results/judge/20261003T145512Z-24c127/comparison
```

Попытка запуска сейчас корректно вернула **missing_openai_api_key**, до сети,
создания run.json и настоящего budget ledger. API spend в этой подготовке: **$0**.
Следующее необходимое действие пользователя — заполнить OPENAI_API_KEY в `.env`;
ключ в чат не нужен. После этого можно проверить доступ и выполнить пилот.

При первой локальной проверке был найден Windows CRLF/hash дефект prompt.txt;
исправлен до API. Старый неотправленный draft-plan `20261003T145019Z-8d2a07`
сохранён, не использовать. Текущий план прошёл integrity path до проверки ключа.

## Ещё не выполнено

Нет реальных external judge verdicts, оценки расхождений, автоматического claim
extraction, pairwise comparator или bounded revision. Эти этапы следуют после
реального пилота; unit tests не заменяют его. Правила, отказ от обязательной
ручной разметки и будущий B0/B1/B2 сохранены в [evaluation v2](../../docs/evaluation-judge-protocol-v2.md).
[Руководство](../../docs/external-judge.md).
