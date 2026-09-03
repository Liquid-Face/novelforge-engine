# Архитектура автономного pipeline генерации новелл

## Чем является данный документ

Данный документ описыает начальную идею, то на чем она основана и стартовую архитектуры рещения, которая в процессе резработки может меняться. Изменения фиксируются последовательно в файле CHANGES.md в котором описаны последовательные изменения повер начальной архитектуры и решения. Файл CHANGES.md отражает эволюцию рещения.  

## Обзор решения

Задача — построить текстовый аналог NousResearch/autonovel, убрав генерацию изображений и аудио, устранив жёсткую привязку к Anthropic, разделив код-движок и данные конкретного романа, и заложив основу для будущего UI. Ниже — полная архитектура, состав компонентов, схема данных и обоснование выбора инструментов (LangGraph + опционально Deep Agents поверх Ollama/AITUNNEL).[^1][^2][^3]

## Ключевые архитектурные принципы

- **Разделение движка и данных** — репозиторий `novelforge-engine` (код, промпты-шаблоны, графы LangGraph) содержит только логику; каждый роман — это отдельный "проект-каталог" (`--project-dir`), который движок принимает как параметр и никогда не коммитит в свой репозиторий.
- **Провайдер-агностичность** — единый интерфейс `LLMProvider` (обёртка над OpenAI-совместимым Chat Completions API), под который подключаются и Ollama (`http://localhost:11434/v1`), и AITUNNEL (`https://api.aitunnel.ru/v1`), и любой другой OpenAI-совместимый бэкенд — без хардкода конкретной модели или вендора.[^4][^5]
- **Промпты как данные, не как код** — все текстовые инструкции (жанр, стиль, критерии оценки) вынесены в Jinja2-шаблоны и YAML-конфиги проекта, а не встроены строками в `.py`-файлы.
- **Идемпотентность и ручные правки** — каждый артефакт (world.md, characters.md, ch_NN.md) версионируется через git-репозиторий внутри проекта романа плюс хэш-манифест; при повторном запуске стадии движок проверяет, менялся ли файл человеком (diff от последнего сгенерированного хэша), и не перезаписывает ручные правки без явного флага `--force-regenerate`.
- **LangGraph как runtime** — каждая фаза pipeline — это `StateGraph` с узлами-функциями (generate → evaluate → keep/discard → loop), с checkpointer'ом (SQLite/Postgres) для возобновляемости и человеческого контроля (human-in-the-loop breakpoints). Deep Agents можно опционально подключить как harness для открытых, "исследовательских" подзадач (например, свободный ревью-агент фазы 3b), где не нужен жёсткий DAG.[^6][^7][^8][^9]

## Структура репозиториев

| Репозиторий | Содержимое | Версионируется |
|---|---|---|
| `novelforge-engine` | Python-пакет: графы LangGraph, CLI, провайдеры LLM, шаблоны промптов, схемы Pydantic | Git, отдельно от романов |
| `<project-dir>/` (любое место на диске) | `project.yaml`, `state/`, `manuscript/`, `logs/`, экспорт PDF/ePub | Отдельный git-репозиторий на роман |

Движок устанавливается как пакет (`pip install novelforge-engine` или `uv tool install`) и вызывается CLI-командой с обязательным параметром пути к проекту — это устраняет пересечение кода и текста романа.

## Файл конфигурации проекта (project.yaml)

Единый настроечный файл, отделяющий "производственные" параметры от "мира" романа:

```yaml
project:
  title: "Working Title"
  language: ru
  genre: "dark fantasy"
  target_audience: adult
  chapters_total: 24
  chapter_length_words: [2200, 3200]
  total_length_words_target: 80000

llm:
  provider: aitunnel          # aitunnel | ollama | openai_compatible
  base_url: "https://api.aitunnel.ru/v1"
  api_key_env: AITUNNEL_API_KEY
  models:
    writer: "claude-sonnet-4.6"
    evaluator: "gpt-5.6-sol"
    reviewer: "gemini-3.7-flash"
  fallback_provider: ollama
  fallback_base_url: "http://localhost:11434/v1"
  fallback_models:
    writer: "qwen2.5:32b"
    evaluator: "qwen2.5:32b"

thresholds:
  foundation_score: 7.5
  lore_score: 7.0
  chapter_score: 6.0
  max_draft_retries: 5
  revision_plateau_delta: 0.5
  revision_max_cycles: 6
  review_max_rounds: 4

export:
  typeset_engine: tectonic     # tectonic | pdflatex
  formats: [pdf, epub]

paths:
  manuscript_dir: manuscript/chapters
  state_dir: state
  logs_dir: logs
  briefs_dir: state/briefs
```

Это единственное место, где задаются нероманные параметры (число глав, жанр, длины, пороги оценки, выбор модели/провайдера). Всё, что относится к самому миру романа (seed, world.md, characters.md), живёт в отдельных markdown-файлах внутри `manuscript/`.

## Структура каталога проекта романа

```
my-novel/
  project.yaml
  seed.md
  manuscript/
    world.md
    characters.md
    outline.md
    voice.md
    canon.md
    mystery.md
    chapters/
      ch_01.md ... ch_NN.md
  state/
    pipeline_state.json
    eval_logs/*.json
    edit_logs/*.json
    briefs/*.md
    results.tsv
    manifest.json        # хэши последних сгенерированных версий файлов
  export/
    novel.tex
    novel.pdf
    novel.epub
  logs/
    run_*.log
```

## Программные компоненты движка

### Слой провайдеров LLM (Ports & Adapters)

Интерфейс `LLMProvider` (Protocol/ABC) с методом `complete(messages, model_role, **kwargs)`. Конкретные реализации — `OpenAICompatibleProvider(base_url, api_key)`, используемая одинаково и для Ollama, и для AITUNNEL, так как оба совместимы с Chat Completions API. Роли моделей (writer/evaluator/reviewer) настраиваются в `project.yaml`, что позволяет назначить дешёвую модель на черновики и мощную — на ревью, без изменений кода. При недоступности основного провайдера включается `fallback_provider` (например, локальный Ollama), реализуя паттерн Circuit Breaker.[^10][^4]

### Слой шаблонов промптов

Каждый инструмент (`gen_world`, `draft_chapter`, `evaluate` и т.д.) хранит свой промпт в `engine/prompts/<name>.jinja2`, куда подставляются переменные из `project.yaml` и файлов манускрипта. Никакой текст, специфичный для конкретного романа (имена персонажей, жанровые детали), не встраивается в `.py`-код — только в шаблоны и данные проекта, что удовлетворяет требование об отсутствии специфичных промптов в скриптах.

### Слой инструментов (аналог 27 скриптов autonovel, без арт/аудио)

| Группа | Инструменты | Назначение |
|---|---|---|
| Foundation | `seed`, `gen_world`, `gen_characters`, `gen_outline`, `gen_outline_foreshadow`, `gen_canon`, `voice_fingerprint` | Мир, персонажи, план, голос, канон[^1] |
| Drafting | `draft_chapter`, `run_drafts` | Последовательное написание глав |
| Evaluation | `evaluate` (mechanical + LLM judge, режимы `--phase=foundation/--chapter=N/--full`) | Оценка качества |
| Revision | `adversarial_edit`, `compare_chapters`, `reader_panel`, `gen_brief`, `gen_revision`, `apply_cuts` | Циклы улучшения |
| Review | `review` (dual-persona: критик + профессор литературы) | Финальный ревью-луп через любую LLM |
| Rebuild | `build_arc_summary`, `build_outline` | Пересборка сводных документов из глав |
| Export | `build_tex`, `build_epub` | Типографика LaTeX и ePub без арт-модуля |
| Orchestration | `run_pipeline`, `run_stage` | CLI-раннеры |

Каждый инструмент — чистая функция вида `(project_dir, config) -> артефакты`, без побочных глобальных состояний, что соответствует принципам SOLID (единственная ответственность, инверсия зависимостей через `LLMProvider`).

### Оркестрация на LangGraph

Каждая фаза — отдельный `StateGraph`:

- **Foundation graph**: узлы `gen_world → gen_characters → gen_outline → gen_canon → voice_discovery → evaluate_foundation`, условное ребро возврата на "слабейший слой" пока `foundation_score < 7.5`.[^1]
- **Drafting graph**: цикл по главам с узлами `draft_chapter → evaluate_chapter → conditional(keep/retry, max 5)`, состояние хранит `current_chapter`, `retry_count`.
- **Revision graph**: подграфы `adversarial_edit → apply_cuts → reader_panel → gen_brief → gen_revision → evaluate`, с детектором плато (`|Δscore| < 0.5` два цикла подряд).
- **Review graph**: цикл `review → parse_items → fix_top_items → commit`, останов по критериям (нет крупных пунктов / >50% формулировок носят "смягчённый" характер / ≤2 пункта).
- **Export graph**: линейный DAG `normalize_titles → build_tex → typeset_pdf → build_epub`.

Верхнеуровневый `run_pipeline` — граф графов (subgraph composition в LangGraph), с checkpointer'ом на SQLite в `state/checkpoints.db`, что даёт паузу/резюме на любом узле и человеческий контроль через breakpoints.[^9]

### Управление состоянием и ручными правками

`state/pipeline_state.json` хранит: текущую фазу, номер итерации/главы, последние оценки, список "долгов" пропагации (изменение мира → устаревшая глава). `state/manifest.json` хранит SHA-256 каждого сгенерированного файла на момент генерации; при запуске стадии движок сравнивает текущий хэш файла с сохранённым — если они различаются, файл считается отредактированным вручную и не перетирается автоматически (запрашивается подтверждение или пропускается regenerate).

## CLI и запуск по частям

Единый CLI (`novelforge`) с подкомандами, каждая принимает `--project-dir`:

```bash
novelforge init --project-dir ./my-novel --config project.yaml
novelforge run full --project-dir ./my-novel
novelforge run stage foundation --project-dir ./my-novel
novelforge run stage foundation.world --project-dir ./my-novel
novelforge run stage draft --from-chapter 5 --to-chapter 10 --project-dir ./my-novel
novelforge run stage revision --cycles 3 --project-dir ./my-novel
novelforge run stage review --project-dir ./my-novel
novelforge run stage export --formats pdf,epub --project-dir ./my-novel
novelforge status --project-dir ./my-novel
```

Такая гранулярность закрывает требование запуска "по готовому seed", "только генерация персонажей", "только конкретные главы" и т.д., при этом каждая подкоманда просто запускает соответствующий LangGraph-подграф с сохранённым чекпоинтом.

## Пороговые значения и метрики (перенос из оригинального pipeline)

Пороги полностью конфигурируемы в `project.yaml`, но по умолчанию наследуют проверенные значения из исходного pipeline:[^1]

| Метрика | Порог по умолчанию | Фаза |
|---|---|---|
| foundation_score | > 7.5 | Foundation |
| lore_score | > 7.0 | Foundation |
| chapter_score | > 6.0, до 5 попыток | Draft |
| revision plateau | Δ < 0.5 за 2 цикла подряд | Revision |
| review stopping | ≤2 пункта или >50% "смягчённых" замечаний | Review |

## Расширяемость под UI

Для будущего графического/веб-интерфейса заложены следующие развязки:

- CLI — это тонкий слой над публичным Python API (`novelforge.api.run_stage(...)`), поэтому UI (FastAPI backend + любой фронтенд) может импортировать те же функции без дублирования логики.
- Все результаты — файлы и JSON-состояние на диске, что позволяет UI просто читать/писать в тот же `project-dir` без специального API хранения.
- LangGraph checkpointer уже поддерживает потоковую передачу событий узлов (streaming), что напрямую подключается к WebSocket для live-отображения прогресса генерации в UI.[^6][^9]
- Конфигурация — декларативный YAML/Pydantic-схема, что упрощает автогенерацию форм настроек в UI.

## Технологический стек

| Компонент | Выбор | Обоснование |
|---|---|---|
| Оркестрация | LangGraph (StateGraph, checkpointer) | Явный контроль DAG, циклов, ретраев, персистентность[^3][^6] |
| Опциональный harness | Deep Agents (langchain-ai/deepagents) | Для открытых подзадач ревью/исследования правок, где не нужен жёсткий граф[^2][^7] |
| LLM-доступ | OpenAI-совместимый клиент (`openai` SDK) | Работает одинаково с Ollama и AITUNNEL без переписывания кода[^4][^11] |
| Локальные модели | Ollama (`localhost:11434/v1`) | Бесплатный локальный инференс, fallback | 
| Облачные модели | AITUNNEL (`api.aitunnel.ru/v1`) | Российский OpenAI-совместимый агрегатор (GPT, Claude, Gemini, Qwen, DeepSeek)[^4][^12] |
| Конфигурация | Pydantic Settings + YAML | Валидация, единая точка настроек проекта |
| Хранение состояния | SQLite (checkpointer) + JSON/Markdown файлы | Простота, портируемость, git-friendly |
| Типографика | LaTeX (tectonic) + ePub-билдер | Печатный PDF и ePub без арт-модуля[^1] |

Такая архитектура сохраняет полный функциональный охват оригинального autonovel (Foundation → Draft → Revision → Review → Export), убирает генерацию изображений и аудио, снимает привязку к Anthropic через провайдер-агностичный слой на базе Ollama и AITUNNEL, разносит движок и текст романа по разным репозиториям с конфигурацией через единый `project.yaml`, и закладывает чистые границы (SOLID, DI через `LLMProvider`, файловый API) для последующего наращивания UI поверх LangGraph.[^11][^4][^1]
</content>

---

## References

1. [NousResearch/autonovel: An autonomous novel writing ...](https://github.com/NousResearch/autonovel) - NousResearch / **
autonovel ** Public

2. [Doubling down on DeepAgents - LangChain Blog](https://www.blog.langchain.com/doubling-down-on-deepagents/) - Two months ago we wrote about Deep Agents - a term we coined for agents that are able to do complex,...

3. [Deep Agents vs LangChain vs LangGraph](https://www.langchain.com/blog/deep-agents-vs-langchain-vs-langgraph) - LangGraph is an agent runtime, LangChain is an agent framework, and Deep Agents is an agent harness....

4. [⚡ Документация AITUNNEL](https://aitunnel.ru/docs) - единый OpenAI-совместимый API к ведущим ИИ-моделям: GPT, Claude, Gemini, DeepSeek, Qwen, Kimi и друг...

5. [Справочник API | AITUNNEL Docs](https://docs.aitunnel.ru/api/reference) - Схемы запросов и ответов AITUNNEL очень похожи на OpenAI Chat API, с небольшими отличиями. В целом, ...

6. [Introducing LangGraph: A Framework for Stateful, Multi-Agent AI Workflows](https://medium.com/@ansurkar.tejasvi12/introducing-langgraph-a-framework-for-stateful-multi-agent-ai-workflows-f5bcec09ddc0) - By Tejasvi Nandkumar

7. [deepagents vs LangGraph in 2026: When the Anthropic- ...](https://callsphere.ai/blog/vw3g-deepagents-vs-langgraph-when-to-pick-anthropic-style-harness)

8. [Langchain vs Langgraph vs Deepagents](https://www.linkedin.com/pulse/langchain-vs-langgraph-deepagents-rachit-lohani-byibc) - LangChain helps you build agents fast, LangGraph helps you make them reliable and controllable, and ...

9. [Production-Ready Multi-Agent Systems with LangGraph](https://dev.to/sidkul2000/production-ready-multi-agent-systems-with-langgraph-a-complete-tutorial-20j1) - A step-by-step guide to building, testing and deploying a multi-agent document processing pipeline.....

10. [AI API для разработчиков](https://aitunnel.ru/use-cases/ai-for-developers) - AI API для разработчиков в России. Интеграция OpenAI GPT-5, Claude 4.5, Gemini в приложения. Python,...

11. [Интеграция OpenCode | AITUNNEL Docs](https://docs.aitunnel.ru/guides/opencode-integration) - Построен на AI SDK и поддерживает 75+ провайдеров «из коробки», включая OpenAI-совместимые endpoints...

12. [AITUNNEL Агрегатор API нейросетей в России без VPN в ...](https://aitunnel.ru/) - Замените API-адрес на api.aitunnel.ru/v1— и всё работает. Полная совместимость с OpenAI SDK, никаких...

