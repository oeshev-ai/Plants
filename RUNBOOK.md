# RUNBOOK: Plants Telegram Bot (Production)

Операционный документ для поддержки бота **Plants** в продакшене и для администраторов, которые поднимают сервис на сервере или восстанавливают работу после сбоев.

## 1) Быстрый доступ (шаблон)

Замените пути и имена на фактические в вашей инфраструктуре.

| Параметр | Пример значения |
|----------|-----------------|
| Сервис systemd | `plants-bot.service` |
| Пользователь процесса (рекомендуется) | `deploy` |
| Каталог проекта | `/home/deploy/Plants` |
| Точка входа | `bot.py` |
| Интерпретатор venv | `/home/deploy/Plants/venv/bin/python3` |
| Файл секретов | `/home/deploy/Plants/.env` |
| SQLite (создаётся автоматически) | `/home/deploy/Plants/plants.db` |

Точка входа всегда одна: **`python bot.py`** (или `python3 bot.py`) из каталога проекта либо с корректными **`WorkingDirectory`** / путями в unit-файле.

## 2) Стандартные команды управления (systemd)

```bash
# Статус
sudo systemctl status plants-bot.service

# Перезапуск
sudo systemctl restart plants-bot.service

# Запуск / остановка
sudo systemctl start plants-bot.service
sudo systemctl stop plants-bot.service

# Автозапуск при загрузке ОС
sudo systemctl enable plants-bot.service
sudo systemctl disable plants-bot.service
```

После правки unit-файла:

```bash
sudo systemctl daemon-reload
sudo systemctl restart plants-bot.service
```

## 3) Просмотр логов

```bash
# Последние 100 строк
journalctl -u plants-bot.service -n 100 --no-pager

# Live-режим
journalctl -u plants-bot.service -f

# Логи за последний час
journalctl -u plants-bot.service --since "1 hour ago" --no-pager
```

Что искать в логах:

- **`Задайте переменную окружения BOT_TOKEN`** — процесс завершился на старте (`sys.exit(1)`).
- Ошибки **`telebot`** / **`ApiTelegramException`** / сетевые таймауты к `api.telegram.org`.
- Повторяющиеся рестарты unit-а (`Restart=always`) без строки **«Бот запущен.»** — стоит смотреть полный трассинг первой ошибки после рестарта.

На Windows без journald логи видны только в консоли/файле перенаправления, если его настроил администратор.

## 4) Чеклист после деплоя

1. Убедиться, что на сервере есть актуальный **`.env`** с валидным **`BOT_TOKEN`** (или переменная задана в unit-файле).
2. Проверить налие **venv** и установку зависимостей: `pip install -r requirements.txt`.
3. Проверить, что в unit-файле **`ExecStart`** указывает на существующий бинарник **`venv/bin/python3`** и на существующий **`bot.py`**.
4. Проверить **`WorkingDirectory`** — обычно корень репозитория, чтобы **`load_dotenv()`** нашёл **`.env`** (если токен не проброшен через `EnvironmentFile`).
5. Выполнить **`daemon-reload`**, **`restart`**, затем **`status`** — состояние **active (running)**.
6. Просмотреть хвост журнала: ошибок при старте быть не должно, должна быть строка **«Бот запущен.»**
7. Smoke-test в Telegram (раздел 8).

Полезные команды на сервере:

```bash
cd /home/deploy/Plants
ls -la venv/bin/python*
python3 -V
test -f .env && echo ".env exists"
sudo systemctl daemon-reload
sudo systemctl restart plants-bot.service
sudo systemctl status plants-bot.service
journalctl -u plants-bot.service -n 50 --no-pager
```

## 5) Типовые инциденты и решение

### A. `status=203/EXEC`

**Причина:** неверный путь в **`ExecStart`**, отсутствует интерпретатор Python или скрипт **`bot.py`**.

**Проверка:**

```bash
ls -la /home/deploy/Plants/venv/bin/python*
ls -la /home/deploy/Plants/bot.py
sudo systemctl cat plants-bot.service
```

**Решение:**

- Исправить **`ExecStart`** и **`WorkingDirectory`** на реальные абсолютные пути.
- Выполнить **`sudo systemctl daemon-reload`** и **`sudo systemctl restart plants-bot.service`**.

---

### B. В логах: «Задайте переменную окружения BOT_TOKEN»

**Причина:** переменная **`BOT_TOKEN`** пустая или не видна процессу.

**Проверка:**

- Есть ли **`.env`** в **`WorkingDirectory`** и строка вида **`BOT_TOKEN=...`** без пробелов вокруг **`=`**.
- Для systemd: подключён ли **`EnvironmentFile=/home/deploy/Plants/.env`** или эквивалент.

**Решение:**

- Исправить **`.env`** или unit-файл.
- Перезапустить сервис.

---

### C. Сервис `active (running)`, бот не отвечает в Telegram

**Возможные причины:**

- неверный или отозванный **`BOT_TOKEN`**;
- сетевой доступ к **`https://api.telegram.org`** заблокирован;
- второй экземпляр с тем же токеном забирает обновления (конфликт long polling);
- необработанное исключение в обработчике (реже при текущей простой логике).

**Проверка:**

```bash
journalctl -u plants-bot.service -n 200 --no-pager
```

С сервера (при наличии `curl`):

```bash
curl -sS -o /dev/null -w "%{http_code}" "https://api.telegram.org"
```

**Решение:**

- Перевыпустить токен в BotFather при подозрении на компрометацию или ошибку копирования.
- Убедиться, что не запущен второй процесс **`bot.py`** с тем же токеном (другой сервер, локальная машина, старый screen-сессия).
- Исправить сеть / firewall / прокси по результатам проверки.

---

### D. Ошибки SQLite (`database is locked`, повреждённый файл)

**Причины:**

- одновременная запись из нескольких процессов в один **`plants.db`** (не штатно для одного бота);
- обрыв диска / права на каталог.

**Проверка:**

```bash
cd /home/deploy/Plants
ls -la plants.db
```

**Решение:**

- Оставить один рабочий процесс бота.
- При повреждении файла: остановить сервис, удалить **`plants.db`**, запустить сервис — при **`init_db()`** файл и данные восстановятся из **`_seed_rows()`** (ручные правки только в SQLite будут потеряны — это ожидаемое поведение текущей версии).

---

### E. Ответ на `/list` не доходит или обрезан

**Причина:** лимит Telegram **4096** символов на одно сообщение; каталог вырос.

**Проверка:** оценить длину ответа или воспроизвести вручную локально.

**Решение:** доработка кода (разбиение списка на несколько сообщений или постраничный вывод). До доработки — сократить каталог или временно не использовать `/list` для полного вывода.

---

### F. Сервис уходит в цикл рестартов (`Restart=always`)

**Причина:** процесс падает сразу после старта (часто из-за п. B или п. A).

**Проверка:**

```bash
journalctl -u plants-bot.service -n 200 --no-pager
```

**Решение:** устранить первопричину по логам, затем **`restart`**.

## 6) Проверка unit-файла systemd

Рекомендуемый шаблон (пути заменить на свои):

```ini
[Unit]
Description=Plants Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/Plants
ExecStart=/home/deploy/Plants/venv/bin/python3 /home/deploy/Plants/bot.py
EnvironmentFile=/home/deploy/Plants/.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Файл разместить, например, в **`/etc/systemd/system/plants-bot.service`**, затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable plants-bot.service
sudo systemctl start plants-bot.service
```

**Замечания:**

- Если **`BOT_TOKEN`** не в **`.env`**, а в секрет-хранилище, используйте директивы **`Environment=`** вместо или вместе с **`EnvironmentFile`**.
- **`User`/`Group`** должны иметь право на чтение каталога проекта и на запись **`plants.db`** в каталоге проекта (создание файла при первом старте).

## 7) Проверка окружения (ручной запуск под тем же пользователем)

```bash
sudo -u deploy -i
cd /home/deploy/Plants
source venv/bin/activate
pip install -r requirements.txt
python3 bot.py
```

Если такой запуск успешен (в логе **«Бот запущен.»**), а systemd падает — почти всегда проблема в **путях**, **рабочем каталоге**, **переменных окружения** или **пользователе** unit-файла.

## 8) Минимальный smoke-test

1. В Telegram отправить **`/start`** — приветствие и упоминание канала.
2. Отправить **`/list`** — длинный список с префиксом из **`LIST_HEADER`** и маркерами **•**.
3. Отправить **`Сансевиерия`** (или другое имя из списка) — карточка с полями освещение / полив / температура / пересадка.
4. Отправить заведомо несуществующее слово — ответ «не понимаю» (`NOT_FOUND`).
5. Отправить **`/unknown`** — тот же тип ответа, что и для нераспознанного растения (обработчик текста с ведущим **`/`**).

## 9) Обновление контента и конфигурации без смены кода деплоя

- **Новые растения / правки текстов карточек:** изменить **`_seed_rows()`** в **`database.py`**, задеплоить код, **перезапустить** сервис (при старте данные перезальются в SQLite).
- **Другой канал в подписи:** изменить **`CHANNEL_USERNAME`** в **`config.py`**, перезапуск.

## 10) Резервное копирование

Каталог растений воспроизводим из репозитория (**`_seed_rows()`**). Имеет смысл бэкапить **код и `.env` (секретно)**; отдельный бэкап **`plants.db`** для текущей логики опционален, так как файл пересобирается при каждом запуске.

## 11) Эскалация

Если за **15–30** минут восстановить не удалось, сохраните и передайте ответственному:

- вывод **`sudo systemctl status plants-bot.service`**;
- **`journalctl -u plants-bot.service -n 300 --no-pager`**;
- **`sudo systemctl cat plants-bot.service`**;
- время инцидента и идентификатор последнего деплоя / коммита.
