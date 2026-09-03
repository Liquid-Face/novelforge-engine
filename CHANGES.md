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
