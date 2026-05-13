# Plants — Telegram-бот помощник по уходу за комнатными растениями

Телеграм-бот на [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI): по русскому названию растения отвечает карточкой с рекомендациями (освещение, полив, температура, пересадка). Справочник зашит в коде, при старте загружается в **SQLite** (`plants.db`). 

## Состав проекта

- `bot.py` — точка входа: проверка токена, регистрация обработчиков, long polling (`infinity_polling`).
- `config.py` — загрузка `.env` через `python-dotenv`, чтение `BOT_TOKEN`, константа `CHANNEL_USERNAME` для подписи в ответах.
- `database.py` — путь к БД, создание таблицы, полный пересид из `_seed_rows()`, поиск `find_plant`, выдача списка имён `list_plant_names`.
- `requirements.txt` — зависимости Python.
- `.env.example` — пример переменных окружения для копирования в `.env`.
- `.env` — локальные секреты (не коммитится, см. `.gitignore`).
- `plants.db` — файл SQLite рядом с `database.py`; создаётся при запуске, в репозиторий не попадает.

## Архитектура и поток данных

1. Пользователь пишет боту в Telegram (команда или текст).
2. Библиотека **pyTelegramBotAPI** в режиме long polling получает обновления и вызывает зарегистрированный обработчик.
3. При старте процесса `**main()`**:
  - настраивается `logging` в stdout;
  - проверяется наличие `**BOT_TOKEN**` (иначе `sys.exit(1)` с сообщением в лог);
  - вызывается `**init_db()**` — таблица `plants` очищается и заполняется из `**_seed_rows()**`;
  - создаётся `**telebot.TeleBot**` и регистрируются handlers.
4. Команда `**/start**` → ответ текстом `WELCOME` (приветствие + ссылка на канал `@CHANNEL_USERNAME`).
5. Команда `**/list**` → `**list_plant_names()**` → ответ списком строк «• имя» (имена из БД, `ORDER BY name`).
6. Любой другой **текст**:
  - пустая строка игнорируется;
  - если текст начинается с `**/`** (не `/start` и не `/list`) → ответ `NOT_FOUND`;
  - иначе `**find_plant(text)**` → при успехе `**format_plant_card**`, при неудаче `NOT_FOUND`.

Поиск растения в три этапа (см. `database.find_plant`): точное совпадение имени без учёта регистра (через пользовательскую SQL-функцию `py_lower`), затем имя **начинается с** запроса (приоритет более короткого имени), затем **подстрока** в имени.

## Основные модули и функции

### `bot.py`

- `**format_plant_card(plant)`** — форматирует карточку `Plant` для отправки пользователю.
- `**main()**` — конфигурация логов, проверка токена, `init_db()`, создание бота, регистрация `@bot.message_handler` для `start`, `list`, текста; запуск `**infinity_polling(skip_pending=True)**`.

Обработчики (вложенные в `main`):

- `**on_start**` — команда `/start`.
- `**on_list**` — команда `/list`, пустой каталог → короткое сообщение «В базе пока нет растений.»
- `**on_text**` — произвольный текст: фильтр `/`, вызов `find_plant`, ответ карточкой или `NOT_FOUND`.

### `config.py`

- `**load_dotenv()**` — подхватывает `.env` из текущего рабочего каталога процесса (важно для systemd: `WorkingDirectory` должен указывать на корень проекта, либо токен задаётся в `Environment` / `EnvironmentFile` unit-файла).
- `**BOT_TOKEN**` — из `os.environ.get("BOT_TOKEN", "").strip()`.
- `**CHANNEL_USERNAME**` — строка без `@`; в текстах бота подставляется как `@{CHANNEL_USERNAME}`.

### `database.py`

- `**Plant**` — frozen dataclass полей карточки.
- `**_py_lower**` / регистрация `**py_lower**` в SQLite — нижний регистр в Python для согласованного поиска по кириллице.
- `**_connect()**` — соединение с `DB_PATH`, `row_factory=sqlite3.Row`.
- `**init_db()**` — `CREATE TABLE IF NOT EXISTS`, затем `**DELETE FROM plants**`, затем массовая вставка из `_seed_rows()` (полная синхронизация каталога с кодом).
- `**find_plant(user_text)**` — трёхшаговый поиск, возвращает `Plant | None`.
- `**list_plant_names()**` — список всех `name`, сортировка по `name`.
- `_seed_rows()` — источник по данным; кортежи `(name, light, water, temperature, repot)`.

## Используемые библиотеки

- `pyTelegramBotAPI` (пакет `**telebot**`) — Telegram Bot API, long polling, декораторы `message_handler`.
- `python-dotenv` — загрузка переменных из `.env`.

Стандартная библиотека Python:

- `logging`, `sys` — логирование и выход при отсутствии токена;
- `sqlite3` — БД;
- `dataclasses`, `pathlib`, `os` — модель данных и пути.

## Переменные окружения (`.env`)

Создайте файл `.env` в корне проекта (можно скопировать из `**.env.example**`) и задайте значения.

### Обязательные

```env
BOT_TOKEN=ваш_токен_от_BotFather
```

Токен выдаётся в Telegram у [@BotFather](https://t.me/BotFather).

### Не через `.env`

Имя канала в сообщениях задаётся в `**config.py**` константой `**CHANNEL_USERNAME**` (не секрет). При смене канала отредактируйте файл и перезапустите бота.

## Логи: где смотреть

По умолчанию используется `**logging.basicConfig**` в `bot.py`: сообщения пишутся в **stdout/stderr**.

- **Локальный запуск** — вывод в терминале (PowerShell, bash и т.д.).
- **Запуск через systemd** — логи попадают в **journald**:
  ```bash
  journalctl -u plants-bot.service -n 100 --no-pager
  journalctl -u plants-bot.service -f
  ```

Типичные строки при успешном старте: уровень **INFO**, текст **«Бот запущен.»** При отсутствии токена: **ERROR** с текстом про `**BOT_TOKEN`**.

Важно: отдельный лог-файл (например, `bot.log`) в коде **не настраивается**; при необходимости используйте перенаправление вывода процесса или расширение конфигурации `logging` в приложении.

## Команды управления ботом (systemd)

Имя unit-файла в примерах: `**plants-bot.service`** (замените на фактическое имя у себя на сервере).

### Перезапуск / запуск / остановка

```bash
sudo systemctl restart plants-bot.service
sudo systemctl start plants-bot.service
sudo systemctl stop plants-bot.service
```

### Проверка состояния

```bash
sudo systemctl status plants-bot.service
```

### Просмотр логов

```bash
# Последние 100 строк
journalctl -u plants-bot.service -n 100 --no-pager

# «Живой» просмотр
journalctl -u plants-bot.service -f
```

### Автозапуск

```bash
sudo systemctl enable plants-bot.service
sudo systemctl disable plants-bot.service
```

## Быстрый запуск локально

### Windows (PowerShell)

```powershell
cd D:\Plants
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Отредактируйте .env: вставьте BOT_TOKEN
python bot.py
```

### Linux / macOS

```bash
cd /path/to/Plants
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Отредактируйте .env: вставьте BOT_TOKEN
python3 bot.py
```

Операционные сценарии, инциденты и пример **unit** для production — в **[RUNBOOK.md](RUNBOOK.md)**. Чек-лист передачи заказчику — в **[HANDOVER.md](HANDOVER.md)**.

## Ограничения Telegram

- Лимит длины одного сообщения — **4096** символов. Команда **`/list`** отправляет один текст; при очень большом каталоге ответ может не поместиться (потребуется доработка: разбиение на несколько сообщений).

## Лицензия

Файл лицензии в репозитории при необходимости добавьте отдельно; справочный текст по растениям распространяется вместе с кодом проекта.