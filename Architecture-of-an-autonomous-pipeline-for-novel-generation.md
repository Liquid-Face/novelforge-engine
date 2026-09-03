# Архитектура автономного pipeline генерации новелл

## Статус документа

Исходная идея проекта эволюционировала во время реализации. История решений
и изменений ведётся в `CHANGES.md`, а этот документ описывает текущее состояние
движка `0.2.0`. Источником истины при расхождениях являются исполняемый код и
`templates/project/project.yaml`.

## Обзор

NovelForge — текстовый pipeline для автономной генерации романа. Репозиторий
движка содержит Python-код, LangGraph-графы и Jinja2-шаблоны, а каждый роман
живёт в отдельном каталоге, переданном через `--project-dir`. Движок не пишет
данные романа в собственный репозиторий. Фазы pipeline: Foundation → Draft →
Revision → Review → Export.

Доступ к моделям выполняется через OpenAI-совместимые endpoints. Поддержаны
Ollama (`http://localhost:11434/v1`), AITUNNEL и другие совместимые серверы.

## Архитектурные принципы

- **Разделение движка и данных.** `novelforge-engine` содержит код, а каталог
  проекта содержит `project.yaml`, seed, lore, главы, состояние, логи и экспорт.
- **Role-first LLM.** Роли `writer`, `evaluator` и `reviewer` независимо
  выбирают `primary` и необязательный `fallback` endpoint.
- **Промпты как данные.** Пользовательские и системные инструкции находятся в
  `novelforge/prompts/templates/` в парах `<name>.jinja2` и
  `<name>.system.jinja2`, затем рендерятся через renderer.
- **Защита ручных правок.** `state/manifest.json` хранит хэши артефактов;
  изменённый человеком файл не перезаписывается без явного флага
  `--force-regenerate`.
- **LangGraph для стадий.** Foundation, Draft, Revision и Review реализованы
  как `StateGraph`. Checkpointer/HITL в текущем runtime не подключены.
  `checkpoints.db` остаётся зарезервированным путём, а Deep Agents могут
  рассматриваться только как будущая интеграция, не как часть runtime.

## Конфигурация проекта

Канонический пример находится в `templates/project/project.yaml`; он задаёт
role-first LLM, пороги, export, paths и logging. В шаблоне 20 глав и целевой
объём 70 000 слов. Для каждой роли обязательна собственная секция `primary`,
а `fallback` необязателен:

```yaml
llm:
  roles:
    writer:
      primary:
        provider: ollama
        base_url: "http://localhost:11434/v1"
        model: "qwen2.5:32b"
      fallback:
        provider: aitunnel
        base_url: "https://api.aitunnel.ru/v1"
        model: "claude-sonnet-4.6"
        api_key_env: AITUNNEL_API_KEY
    evaluator:
      primary:
        provider: aitunnel
        base_url: "https://api.aitunnel.ru/v1"
        model: "gpt-5.6-sol"
        api_key_env: AITUNNEL_API_KEY
    reviewer:
      primary:
        provider: aitunnel
        base_url: "https://api.aitunnel.ru/v1"
        model: "gemini-3.7-flash"
        api_key_env: AITUNNEL_API_KEY

thresholds:
  foundation_score: 7.5
  foundation_max_iterations: 8
  lore_score: 7.0
  chapter_score: 6.0
  max_draft_retries: 5
  revision_plateau_delta: 0.5
  revision_max_cycles: 6
  review_max_rounds: 4
  review_stop_max_items: 2

paths:
  manuscript_dir: manuscript/chapters
  lore_dir: manuscript
  state_dir: state
  logs_dir: logs
  briefs_dir: state/briefs
  export_dir: export

logging:
  console_verbosity: normal
  log_to_file: false
  log_file_path: logs/run.log
  log_evaluate: true
```

Дополнительные секции шаблона:

```yaml
project:
  title: "Working Title"
  language: ru
  genre: "dark fantasy"
  target_audience: adult
  chapters_total: 20
  chapter_length_words: [2200, 3200]
  total_length_words_target: 70000

export:
  typeset_engine: tectonic
  formats: [pdf, epub]
  trim_size: "5.5in x 8.5in"
  font: "EB Garamond"
```

Остальные общие параметры `llm` (`temperature`, `max_tokens`,
`request_timeout_s`) также находятся в каноническом шаблоне.

## Каталог проекта

```text
my-novel/
  project.yaml
  seed.md
  manuscript/
    world.md
    characters.md
    outline.md
    canon.md
    voice.md
    arc_summary.md
    chapters/
      ch_01.md ... ch_NN.md
  state/
    pipeline_state.json
    token_usage.json
    briefs/
    manifest.json
    checkpoints.db       # путь есть, checkpointer не подключён
  logs/
    foundation/<layer>/
    draft/ch_NN/
  export/
    novel.tex
    novel.pdf
    novel.epub
```

## Слой LLM и наблюдаемость

Инструменты обращаются к `LLMProvider.complete(..., role=...)`. Провайдер
выбирает endpoint по роли, использует fallback при ошибках OpenAI API,
таймаутах и соединении, и переиспользует клиент для одинаковой пары
`(base_url, api_key_env)`. Токены суммируются за запуск, затем добавляются к
проектному итогу в `state/token_usage.json`.

Графы получают `PipelineReporter` и передают состояние через
`graph.stream(..., stream_mode="values")`. Reporter выводит стадии, узлы,
роутеры, оценки, feedback и токены; уровень консоли задаётся `--verbosity` или
`logging.console_verbosity`, файловое логирование — параметрами `logging.*`.

## Инструменты

| Группа | Функции | Назначение |
|---|---|---|
| Foundation | `gen_world`, `gen_characters`, `gen_outline`, `gen_canon`, `voice_fingerprint`, `evaluate_foundation_layer` | Генерация и оценка слоёв lore |
| Draft | `draft_chapter`, `evaluate_chapter` | Генерация и оценка глав |
| Revision | `adversarial_edit`, `apply_cuts`, `reader_panel`, `gen_brief`, `gen_revision` | Цикл улучшения главы |
| Review | `review_manuscript` | Поиск actionable items по рукописи |
| Rebuild | `build_arc_summary` | Пересборка сводки сюжетной дуги |
| Export | `build_tex`, `typeset_pdf`, `build_epub` | LaTeX/PDF и EPUB3 |

Единого инструмента `evaluate --phase` нет; также нет инструментов `seed`,
`gen_outline_foreshadow` или `compare_chapters`.

## Графы и оркестрация

- **Foundation:** для каждого слоя выполняется generate → evaluate; при
  недостаточном score повторяется тот же слой, затем pipeline переходит к
  следующему. Запуск `foundation.<layer>` завершается после выбранного слоя.
- **Draft:** draft → evaluate → retry или advance/done. После advance
  вызывается `build_arc_summary`; при исчерпании retry-бюджета записывается
  лучшая попытка.
- **Revision:** API перебирает главы, а граф выполняет
  adversarial → cuts → reader_panel → brief → revise → evaluate. Цикл
  останавливается по `max_cycles` или plateau.
- **Review:** review → fix_items → review; остановка определяется числом
  actionable items или `max_rounds`.
- **Export:** это не граф, а прямые вызовы `build_tex`, `typeset_pdf` и
  `build_epub`.
- **Full pipeline:** `run_full_pipeline` последовательно вызывает
  `run_foundation`, `run_draft`, `run_revision`, `run_review` и `run_export`;
  graph-of-graphs не используется.

## CLI

```bash
novelforge init --project-dir ./my-novel
novelforge run full --project-dir ./my-novel
novelforge run stage foundation --project-dir ./my-novel
novelforge run stage foundation.world --project-dir ./my-novel
novelforge run stage draft --from-chapter 5 --to-chapter 10 --project-dir ./my-novel
novelforge run stage revision --cycles 3 --project-dir ./my-novel
novelforge run stage review --project-dir ./my-novel
novelforge run stage export --formats pdf,epub --project-dir ./my-novel
novelforge status --project-dir ./my-novel
```

`run full` и `run stage` принимают `--verbosity quiet|normal|verbose`.
`--force-regenerate` доступен для `run stage` и передаёт внутренний параметр
`force=True`, разрешая осознанную замену ручных правок. Foundation поддерживает
слои `world`, `characters`, `outline`, `canon`, `voice`; Draft поддерживает
`--from-chapter` и `--to-chapter`, Revision — `--cycles`, Export — `--formats`.

## References

- [NousResearch/autonovel](https://github.com/NousResearch/autonovel)
- [AITUNNEL documentation](https://aitunnel.ru/docs)
- [LangGraph documentation](https://langchain-ai.github.io/langgraph/)

Deep Agents не являются частью текущего runtime; соответствующие материалы
сохранены только как направление для будущих решений.
