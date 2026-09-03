# Novel Project

Это каталог данных отдельного романа. Здесь нет кода движка: только
конфигурация (`project.yaml`), исходный seed, lore-документы
(`manuscript/*.md`), главы (`manuscript/chapters/`), состояние пайплайна
(`state/`) и экспортированные файлы (`export/`). Движок устанавливается
отдельно, а команда CLI называется `novelforge`. Установка описана в
[README движка](../../README.md).

## Перед запуском

Отредактируйте `project.yaml`: укажите жанр, число и объём глав, role-first
маршрутизацию в `llm.roles` и ключи endpoint'ов. Подготовьте `seed.md` с
исходной идеей романа. Полная установка движка описана в
<https://github.com/Liquid-Face/novelforge-engine>.

## Быстрый старт

```bash
novelforge run stage foundation --project-dir .
novelforge run stage draft --project-dir .
novelforge run stage revision --project-dir .
novelforge run stage review --project-dir .
novelforge run stage export --project-dir .
novelforge status --project-dir .
```

Или всё сразу:

```bash
novelforge run full --project-dir .
```

Для отдельных запусков доступны параметры:

```bash
novelforge run stage foundation.world --project-dir .
novelforge run stage draft --project-dir . --from-chapter 1 --to-chapter 5
novelforge run stage revision --project-dir . --cycles 3
novelforge run stage export --project-dir . --formats pdf,epub
novelforge run stage foundation --project-dir . --verbosity verbose
```

`--force-regenerate` доступен только для `run stage` и нужен лишь при
осознанной замене ручных правок. Manifest-защита не перезаписывает изменённые
вручную файлы. При первом прогоне появляются логи в `logs/` и состояние в
`state/`, включая `state/token_usage.json`.
