# Патч: role-first конфигурация LLM

## Изменённые файлы (заменить один в один в существующем novelforge-engine)

- `novelforge/config.py`
- `novelforge/llm/provider.py`
- `templates/project/project.yaml`

## Суть изменения

Конфигурация LLM переведена с модели "провайдер владеет ролями"
(`provider` + `fallback_provider`, единые для writer/evaluator/reviewer) на
модель "роль владеет endpoint'ами" (`llm.roles.<role>.primary` +
`llm.roles.<role>.fallback`). Каждая роль (writer/evaluator/reviewer) теперь
независимо настраивается на любой provider/base_url/model, и у каждой роли
свой собственный опциональный fallback endpoint.

## Что нужно сделать в вашем проекте романа

Если у вас уже создан проект через `novelforge init`, замените блок `llm:`
в его `project.yaml` на новую схему (см. `templates/project/project.yaml`
в этом архиве как образец) -- старый формат (`provider`/`models`/
`fallback_provider`/`fallback_models`) больше не валиден и будет отклонён
Pydantic-валидацией при загрузке.

## Тесты, выполненные перед сборкой архива

1. Загрузка `project.yaml` с новой role-first схемой -- OK.
2. Валидация: конфиг без одной из обязательных ролей (writer/evaluator/
   reviewer) корректно вызывает ValueError с явным указанием, каких ролей
   не хватает.
3. `LLMProvider._client_for`: два endpoint'а с одинаковым `base_url` и
   `api_key_env` (evaluator и reviewer на одном AITUNNEL) переиспользуют
   один и тот же клиент; разные endpoint'ы получают разные клиенты.
4. `LLMProvider.complete`: при ошибке primary endpoint (смоделирован
   `APIConnectionError`) запрос корректно переключается на fallback данной
   роли и возвращает результат с моделью/провайдером fallback'а.
5. `LLMProvider.complete`: если у роли нет fallback (пример: reviewer в
   тестовом сценарии), ошибка primary корректно пробрасывается наружу, а не
   заглушается.
6. Обновлённый `templates/project/project.yaml` успешно загружается через
   `ProjectConfig.load(...)` и корректно резолвит все три роли с ожидаемыми
   primary/fallback моделями.

## Что НЕ менялось

`novelforge/tools/*.py`, `novelforge/graphs/*.py`, `novelforge/api.py`,
`novelforge/cli.py` -- не затронуты, так как все они вызывают
`llm.complete(..., role=...)`, а выбор endpoint'а полностью инкапсулирован
внутри `LLMProvider`. Публичный интерфейс `complete()` не изменился.


# Патч: role-first конфигурация LLM

## Изменённые файлы (заменить один в один в существующем novelforge-engine)

- `novelforge/config.py`
- `novelforge/llm/provider.py`
- `templates/project/project.yaml`

## Суть изменения

Конфигурация LLM переведена с модели "провайдер владеет ролями"
(`provider` + `fallback_provider`, единые для writer/evaluator/reviewer) на
модель "роль владеет endpoint'ами" (`llm.roles.<role>.primary` +
`llm.roles.<role>.fallback`). Каждая роль (writer/evaluator/reviewer) теперь
независимо настраивается на любой provider/base_url/model, и у каждой роли
свой собственный опциональный fallback endpoint.

## Что нужно сделать в вашем проекте романа

Если у вас уже создан проект через `novelforge init`, замените блок `llm:`
в его `project.yaml` на новую схему (см. `templates/project/project.yaml`
в этом архиве как образец) -- старый формат (`provider`/`models`/
`fallback_provider`/`fallback_models`) больше не валиден и будет отклонён
Pydantic-валидацией при загрузке.

## Тесты, выполненные перед сборкой архива

1. Загрузка `project.yaml` с новой role-first схемой -- OK.
2. Валидация: конфиг без одной из обязательных ролей (writer/evaluator/
   reviewer) корректно вызывает ValueError с явным указанием, каких ролей
   не хватает.
3. `LLMProvider._client_for`: два endpoint'а с одинаковым `base_url` и
   `api_key_env` (evaluator и reviewer на одном AITUNNEL) переиспользуют
   один и тот же клиент; разные endpoint'ы получают разные клиенты.
4. `LLMProvider.complete`: при ошибке primary endpoint (смоделирован
   `APIConnectionError`) запрос корректно переключается на fallback данной
   роли и возвращает результат с моделью/провайдером fallback'а.
5. `LLMProvider.complete`: если у роли нет fallback (пример: reviewer в
   тестовом сценарии), ошибка primary корректно пробрасывается наружу, а не
   заглушается.
6. Обновлённый `templates/project/project.yaml` успешно загружается через
   `ProjectConfig.load(...)` и корректно резолвит все три роли с ожидаемыми
   primary/fallback моделями.

## Что НЕ менялось

`novelforge/tools/*.py`, `novelforge/graphs/*.py`, `novelforge/api.py`,
`novelforge/cli.py` -- не затронуты, так как все они вызывают
`llm.complete(..., role=...)`, а выбор endpoint'а полностью инкапсулирован
внутри `LLMProvider`. Публичный интерфейс `complete()` не изменился.


# Патч: наблюдаемость pipeline (observability)

## Изменённые/новые файлы (заменить/добавить в существующем novelforge-engine)

- `novelforge/config.py` — изменён: добавлена секция `LoggingConfig`
  (`console_verbosity`, `log_to_file`, `log_file_path`) как часть
  `ProjectConfig`.
- `novelforge/llm/provider.py` — изменён: `LLMProvider` теперь накапливает
  токены (`usage_totals: TokenUsageTotals`) за весь запуск.
- `novelforge/observability/__init__.py` — новый пустой файл пакета.
- `novelforge/observability/reporter.py` — новый: `PipelineReporter` —
  единая точка вывода в консоль/файл (баннер запуска, узлы, роутеры,
  score, токены).
- `novelforge/graphs/foundation_graph.py` — изменён: каждый узел и роутер
  вызывают `state["reporter"]` для логирования.
- `novelforge/graphs/drafting_graph.py` — аналогично.
- `novelforge/graphs/revision_graph.py` — аналогично.
- `novelforge/graphs/review_graph.py` — аналогично.
- `novelforge/api.py` — изменён: `graph.invoke()` заменён на потоковый
  `_stream_graph()` (`graph.stream(..., stream_mode="values")`); добавлен
  баннер параметров запуска (`run_banner`) перед началом каждой стадии;
  добавлен параметр `verbosity_override` во все `run_*`/`run_stage`.
- `novelforge/cli.py` — изменён: добавлен флаг `--verbosity` для команд
  `run full` и `run stage`, передаётся в `api.*` как `verbosity_override`.
- `templates/project/project.yaml` — изменён: добавлена секция `logging`.

## Соответствие пунктам 1–8 из технического обзора

1. Единый модуль вывода — `observability/reporter.py` (`PipelineReporter`).
2. Узлы графов вызывают `reporter.node(...)` до/после инструмента.
3. Роутеры вызывают `reporter.router(...)` с решением и причиной.
4. `api.py` использует `graph.stream(stream_mode="values")` вместо
   `graph.invoke()` во всех стадиях (foundation/draft/revision/review).
5. Все `run_*` в `api.py` оборачивают вызов графа через `_stream_graph`.
6. В CLI добавлен флаг `--verbosity` (quiet|normal|verbose).
7. Счётчики токенов (`prompt_tokens`, `completion_tokens`, `total_tokens`)
   накапливаются в `LLMProvider.usage_totals` за весь запуск и печатаются
   после каждого шага, где происходит LLM-вызов.
8. `logging.log_to_file` + `logging.log_file_path` — явные параметры
   проекта (`project.yaml`), не хардкод; при включении пишут тот же текст
   в файл через `logging.FileHandler`.

Баннер параметров запуска (тип запуска, project-dir, все параметры
проекта и ролей LLM в табличном виде) выводится в начале каждой команды
`run_banner(...)`, до начала любой обработки узлов графа.

## Тесты, выполненные перед сборкой архива

Все тесты выполнялись с замоканным `openai.OpenAI` (без реальных сетевых
вызовов к Ollama/AITUNNEL):

1. `python -m py_compile` для всех изменённых файлов — успешно.
2. Загрузка обновлённого `templates/project/project.yaml` через
   `ProjectConfig.load(...)` — секция `logging` резолвится корректно.
3. Полный прогон `novelforge run stage foundation.world` через
   `novelforge.api.run_stage(...)`:
   - в консоли отображается баннер с типом запуска, project-dir и полной
     таблицей параметров (project/thresholds/logging/llm.<role>.primary/
     fallback);
   - отображается запуск узла `gen_world`;
   - отображается накопленное значение токенов (120 prompt / 340
     completion / 460 total);
   - при `logging.log_to_file: true` те же записи продублированы в
     `logs/run.log`.
4. Полный прогон `novelforge run stage draft` (граф с streaming) на
   2 главах с моком, всегда возвращающим `score=7.0 >= threshold 6.0`:
   - видны оба узла (`draft_chapter`, `evaluate_chapter`, `build_arc_summary`)
     через `graph.stream()`;
   - роутер `after_evaluate` корректно выбирает `advance` на первой главе
     и `done` на последней;
   - токены накопительно растут между главами (300 → 750 total).
5. Сценарий retry: мок `evaluate_chapter` возвращает `score=4.0` два раза
   подряд (ниже порога 6.0), затем `score=8.0`:
   - роутер `after_evaluate` корректно выбирает `retry` дважды, затем
     `done`;
   - `draft_chapter` вызывается повторно для той же главы;
   - токены накопительно растут на каждой попытке (60 → 120 → 180 total).

## Что НЕ менялось

`novelforge/project.py`, `novelforge/state/*.py`, `novelforge/tools/*.py`,
`novelforge/prompts/*` — не затронуты. Инструменты (`tools/foundation.py`
и т.д.) остаются чистыми функциями без вывода; весь вывод инкапсулирован
в `PipelineReporter`, вызываемый только из узлов графов и `api.py`
(соответствует SRP).


# Патч: Patch with role/model visibility

Patch with role/model visibility, persistent token totals, artifact reporting, and reporter injection. See conversation for tested scenarios.


# Патч: исправление критического бага + шаблоны foundation

## Найденная ошибка

В `novelforge/tools/foundation.py` функции `gen_characters`, `gen_outline`,
`gen_canon`, `voice_fingerprint` и `evaluate_foundation` отправляли в LLM
литеральные строки-заглушки ("chars", "outline", "canon", "voice", "eval")
вместо реального рендеринга Jinja2-шаблонов. Модель получала слово "chars"
вместо промпта с миром, сидом, жанром и предыдущими слоями лора.

Также `foundation_graph.py` не передавал `feedback` в `gen_canon` и
`voice_fingerprint`, из-за чего цикл доработки не мог улучшить именно эти
слои по замечаниям evaluator'а.

## Исправление

- `tools/foundation.py`: каждая функция теперь рендерит свой Jinja2-шаблон
  с полным, специфичным для неё контекстом (world -> characters -> outline ->
  canon/voice -> evaluate), по образцу предоставленного gen_characters.jinja2.
- `graphs/foundation_graph.py`: `feedback` теперь консистентно передаётся во
  все регенерируемые слои, включая canon и voice.
- `state/manifest.py`: убран неиспользуемый импорт `Optional` (чистота кода,
  без изменения поведения).
- Добавлены сами шаблоны `gen_world.jinja2`, `gen_characters.jinja2`,
  `gen_outline.jinja2`, `gen_canon.jinja2`, `voice_fingerprint.jinja2`,
  `evaluate_foundation.jinja2` (ранее это были dummy-заглушки).

## Тесты

1. Полный прогон foundation-графа с mock LLM: подтверждено, что промпт
   gen_characters содержит сгенерированный world, outline содержит
   characters, canon содержит outline, evaluate содержит canon+voice.
   Ни один вызов не содержит литеральных строк-заглушек.
2. Manifest-guard: подтверждено, что ручное редактирование world.md
   блокирует перезапись без `force=True` и разрешает её с `force=True`.


# Релиз v0.2.0: генерация foundation-слоёв

Версия движка повышена до `0.2.0`. Foundation теперь действительно генерирует
все пять слоёв последовательно: `world`, `characters`, `outline`, `canon` и
`voice`. Каждый слой получает контекст уже созданных материалов, собственный
шаблон промпта и отдельную оценку evaluator'ом.

Для каждого слоя добавлен управляемый цикл качества: движок повторяет генерацию
до достижения настроенного порога или лимита итераций, сохраняет лучшего
кандидата и передаёт feedback в следующую попытку. Запуск отдельного слоя
(`foundation.world`, `foundation.characters` и т.д.) использует тот же pipeline,
но останавливается после выбранного слоя.

Генерация учитывает manifest-guard: существующий артефакт, изменённый вручную,
не перезаписывается без явного `--force`. В pipeline state сохраняются оценки
слоёв и минимальная итоговая оценка foundation. Для диагностики попыток
добавлено опциональное логирование промптов, результатов, оценок и feedback в
`logs/foundation/<layer>/`.
