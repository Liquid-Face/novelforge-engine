# Патч: role-first конфигурация LLM

Конфигурация LLM переведена с модели "провайдер владеет ролями" на модель
"роль владеет endpoint'ами": `llm.roles.<role>.primary` и необязательный
`llm.roles.<role>.fallback`. Роли writer/evaluator/reviewer независимо
настраиваются на provider/base_url/model.

В существующем проекте, созданном через `novelforge init`, блок `llm:` нужно
заменить на новую схему из `templates/project/project.yaml`. Старый формат
(`provider`/`models`/`fallback_provider`/`fallback_models`) больше не валиден.

Проверены загрузка и валидация role-first схемы, обязательность всех трёх ролей,
переиспользование клиентов для одинаковых endpoint'ов и fallback на уровне
роли. Инструменты по-прежнему вызывают `llm.complete(..., role=...)`.

# Патч: наблюдаемость pipeline (observability)

Добавлены `LoggingConfig`, `PipelineReporter`, потоковая обработка графов через
`graph.stream(..., stream_mode="values")`, параметр CLI `--verbosity`,
накопление токенов за запуск и файловое логирование через `logging.*`.
Foundation и Draft сохраняют диагностические попытки в логах своих слоёв и
глав.

# Патч: исправление критического бага + шаблоны foundation

Исправлено использование dummy-промптов в foundation: генераторы теперь
рендерят специфичные Jinja2-шаблоны с контекстом предыдущих слоёв и feedback.
Добавлены шаблоны `gen_world.jinja2`, `gen_characters.jinja2`,
`gen_outline.jinja2`, `gen_canon.jinja2`, `voice_fingerprint.jinja2` и
`evaluate_foundation.jinja2`. Manifest-guard сохраняет защиту ручных правок.

# Релиз v0.2.0: генерация foundation-слоёв

Foundation генерирует пять слоёв последовательно: `world`, `characters`,
`outline`, `canon` и `voice`. Для каждого слоя действует цикл до порога или
лимита итераций; отдельный запуск `foundation.<layer>` останавливается после
выбранного слоя. Попытки и feedback можно диагностировать в
`logs/foundation/<layer>/`.

# Документация актуализирована для v0.2.0

Пользовательские документы (`README.md`, архитектура, `AGENTS.md` и README
каталога проекта) приведены в соответствие с текущим кодом: role-first LLM,
последовательная per-layer Foundation, observability и отсутствие подключённых
SQLite checkpointer и Deep Agents в runtime.
