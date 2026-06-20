## 🔴 Критические дефекты (блокируют работу)

**1. `recorder.py:19` — изоляция путей всегда падает (проект не запускается end-to-end)**

```python
root_dir = Path("/home/gowen/.openclaw/workspace/poet_module").absolute()
if not str(self.storage_path).startswith(str(root_dir)):
    raise PermissionError(...)
```

- Реальный путь проекта — `.../workspace-pakhom-53bf485c/poet_module`, а не `.../workspace/poet_module`. Значит `startswith` **всегда** False → `PermissionError` на каждой записи → п.3 приёмки нарушен в обе стороны: валидные пути отклоняются.
- Сам подход `str.startswith` небезопасен (`/.../poet_module-evil/x` пройдёт проверку). TZ явно требует `os.path.commonpath()`.
- Решение: `root = Path(__file__).resolve().parent.parent` и `os.path.commonpath([root, self.storage_path]) == str(root)`.

**2. `recorder.py:32-33` — потеря данных при повреждении файла**

```python
except (json.JSONDecodeError, IOError) as e:
    logger.error("... Starting fresh.")
```

При битом `records.json` весь архив тихо уничтожается (`records = []`), а новая версия перезаписывает файл. Это прямо противоречит критерию приёмки 2 (целостность). Нужно: бэкапить повреждённый файл (`records.json.corrupt.<ts>`) и только потом стартовать заново.

**3. `generator.py` — отсутствует retry/backoff (требование TZ 2.1)**
TZ требует экспоненциальный backoff на `429` и `5xx`. Текущий код ловит любое исключение и сразу пробрасывает `RuntimeError`. Нет ни `time.sleep`, ни счётчика попыток, ни различения кодов ответа. Нужно: цикл до N попыток, `response.status_code in (429, 500, 502, 503, 504)` → backoff, прочие → fail-fast.

**4. Не реализован `data/error.log` (TZ 2.1, 2.4)**
В `main.py:15` добавлен только `FileHandler("data/app.log")`. Ошибки API должны дублироваться в `data/error.log` — нужен отдельный `FileHandler` с `level=ERROR` (или `logging.handlers` с фильтром).

## 🟡 Серьёзные проблемы

**5. Точка входа хрупкая (`main.py:7-9, 47`)**
`from src.generator import ...` требует запуска строго `python -m src.main` из корня проекта. `python src/main.py` → `ImportError`. Нет `src/__init__.py`, нет README. Решение: добавить `src/__init__.py` + документировать запуск (или использовать относительные импорты с пакетом).

**6. `main.py:16` — относительный путь лога зависит от cwd**
`logging.FileHandler("data/app.log")` создаёт файл относительно текущей директории, а не корня модуля. Запуск из другой директории → `FileNotFoundError` или мусор в неожиданном месте. Решение: `Path(__file__).resolve().parent.parent / "data"`.

**7. `generator.py:22` — утечка ресурса `httpx.Client`**
Клиент создаётся в `__init__`, но никогда не закрывается (нет `close()`, `__enter__/__exit__`, контекстного менеджера, `finally`). При повторных запусках/тестах копятся соединения. Решение: сделать `PoetryGenerator` контекстным менеджером или закрывать клиент в `finally`.

**8. `generator.py:15-17` — устаревший конфиг pydantic v2**

```python
class Config:
    env_file = ".env"
```

В `pydantic-settings 2.x` (а в `requirements.txt` именно 2.2.1) вложенный `class Config` депрекейтнут и выдаёт `PydanticDeprecatedSince20` warning. Нужно `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")`.

**9. `generator.py:75-77` — жадный fallback-парсинг**

```python
match_raw = re.search(r'\{.*\}', text, re.DOTALL)
```

`\{.*\}` жадный с `DOTALL` захватывает от первого `{` до последнего `}` — может включать посторонний текст/несколько объектов. Нужно ленивый захват + `json.loads` в try/except, при неудаче — `raise ValueError`, а не отдавать «какой-то» JSON.

## 🟢 Замечания и улучшения

- **`generator.py:61`** — `response.json()['choices'][0]['message']['content']` без проверки структуры; обёрнуто общим `except Exception`, но тип исключения теряется при перепаковке в `RuntimeError` (`raise ... from e` предпочтительнее для сохранения cause).
- **`recorder.py:37`** — `entry['version'] = version` мутирует словарь вызывающего (`poem_data`), затем этот же объект попадает в `notifier.notify` с навешанным `version` — скрытый побочный эффект.
- **`notifier.py`** — нет абстракции (`BaseNotifier`/`Protocol`). TZ 2.3 требует, чтобы замена на Telegram не правила остальной код; сейчас замена потребует правки `main.py`.
- **`main.py`** — нет DI: компоненты создаются жёстко внутри `main()`, что мешает тестированию.
- **`main.py:43`** — при сбое записи уже сгенерированное стихотворение теряется безвозвратно (нет дампа во временный файл).
- **`generator.py:54-58`** — нет `max_tokens`, нет валидации структуры распарсенного JSON (нет проверки ключей `motifs/antonyms/title/poem`).
- **`requirements.txt`** — нет dev-зависимостей (`pytest`, `ruff`), нет тестов вообще; нет закрепления интерпретатора (3.10+ из TZ нигде не проверяется).
- **`.gigacode/`, `code_review_report.md`** — артефакты не в `.gitignore`, попадут в коммит (как сейчас untracked). Решить: игнорировать или удалить.

## Соответствие TZ / критерии приёмки

| Критерий | Статус | Примечание |
|---|---|---|
| 1. API-ключ вне Git | ✅ | `.gitignore` содержит `.env` |
| 2. Целостность при `kill -9` | ⚠️ | `os.replace` реализован, но сбой чтения → потеря данных (дефект 2) |
| 3. Изоляция путей | ❌ | Проверка всегда падает + небезопасный `startswith` (дефект 1) |
| 4. Монотонность версий | ✅ | `max(...)+1` внутри `FileLock` корректен |
| 5. Валидация `.env` | ✅ | `pydantic-settings` выбрасывает `ValidationError` |
| 2.1 retry/backoff | ❌ | не реализован (дефект 3) |
| 2.1 `data/error.log` | ❌ | не реализован (дефект 4) |
| 2.3 свотчивость notifier | ⚠️ | нет интерфейса |
| 2.4 логирование | ⚠️ | есть, но путь хрупкий (дефект 6) |

## Рекомендуемый порядок правок

1. Динамический корень + `os.path.commonpath` в `recorder.py` (дефект 1) — иначе проект не запустится.
2. Бэкап повреждённого файла вместо «starting fresh» (дефект 2).
3. Retry с exponential backoff по статус-кодам в `generator.py` (дефект 3).
4. `data/error.log` handler + абсолютные пути логов (дефекты 4, 6).
5. Закрытие `httpx.Client`, `model_config`, ленивый fallback-парсинг (дефекты 7, 8, 9).
6. `src/__init__.py`, README с командой запуска, тесты на `_parse_json`/`record`/изоляцию путей.

Текущее состояние: **проект не выполняет основной сценарий «сгенерировать → записать» из-за дефекта 1**, поэтому до продакшена обязательны как минимум правки 1–4.
