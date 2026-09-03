# Novel Project

Это каталог данных отдельного романа. Он НЕ содержит кода движка —
только конфигурацию (`project.yaml`), исходный seed, генерируемые
lore-документы (`manuscript/*.md`), главы (`manuscript/chapters/`),
состояние пайплайна (`state/`) и экспортированные файлы (`export/`).

## Быстрый старт

```bash
novelforge run stage foundation --project-dir .
novelforge run stage draft --project-dir .
novelforge run stage revision --project-dir .
novelforge run stage review --project-dir .
novelforge run stage export --project-dir .
```

Или всё сразу:

```bash
novelforge run full --project-dir .
```

Отредактируйте `project.yaml`, чтобы задать жанр, число глав, объём глав и
маршрутизацию моделей (Ollama и/или AITUNNEL) до запуска.
