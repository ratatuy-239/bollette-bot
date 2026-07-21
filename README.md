# 💡 Bollette Bot — Telegram бот для учёта электроэнергии

Бот для внесения данных о потреблении электроэнергии в Google Sheets.

---

## Команды бота

- `/start` — приветствие и список команд
- `/add` — внести данные за месяц (прислать PDF болле́тты, дальше по шагам)
- `/get` — посмотреть данные и итоги за месяц
- `/postino` — сгенерировать текст болеттино для чата
- `/debug` — проверить, находит ли бот нужные строки в таблице
- `/cancel` — отменить текущую операцию

---

## Настройка и деплой

### Шаг 1 — Создать Telegram бота

1. Открой Telegram, найди **@BotFather**
2. Отправь `/newbot`
3. Придумай имя и username (например `BolletteLightBot`)
4. Скопируй токен вида `7123456789:AAHxxxx...` — он понадобится позже

---

### Шаг 2 — Настроить Google Sheets API

1. Открой [Google Cloud Console](https://console.cloud.google.com)
2. Выбери свой проект (у тебя уже настроен)
3. Перейди в **APIs & Services → Credentials**
4. Нажми **Create Credentials → Service Account**
5. Дай любое имя, нажми **Done**
6. Открой созданный Service Account → вкладка **Keys**
7. **Add Key → Create new key → JSON** — скачается файл `credentials.json`
8. Открой этот файл в текстовом редакторе и **скопируй всё содержимое** — это `GOOGLE_CREDENTIALS_JSON`

> ⚠️ Убедись, что Sheets API включён: **APIs & Services → Enable APIs → Google Sheets API → Enable**

**Дать доступ к таблице:**
1. Открой файл `credentials.json`, найди поле `"client_email"` — там будет адрес вида `xxx@xxx.iam.gserviceaccount.com`
2. Открой свою таблицу в Google Sheets
3. Нажми **Share**, вставь этот email, дай права **Editor**

---

### Шаг 3 — Залить код на GitHub

```bash
# В папке electricity_bot:
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/ТВО_ИМЯ/bollette-bot.git
git push -u origin main
```

---

### Шаг 4 — Задеплоить на Google Cloud Run (бесплатно)

Бот работает через **webhook**: между сообщениями не крутится ни одного процесса,
Cloud Run гасит контейнер до нуля и не тарифицирует простой. Бесплатный лимит —
2 млн запросов в месяц, бот расходует пару десятков.

Текущая установка:

| | |
|---|---|
| Проект | `idyllic-parser-493511-q3` |
| Сервис | `bollette-bot`, регион `europe-west1` |
| Работает от имени | `picotti-bot@idyllic-parser-493511-q3.iam.gserviceaccount.com` |
| Адрес | `https://bollette-bot-325120116454.europe-west1.run.app` |

**1. Поставить gcloud и залогиниться**

Если нет Homebrew — скачать напрямую:

```bash
curl -o gcloud.tar.gz https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-arm.tar.gz
tar -xzf gcloud.tar.gz -C "$HOME"
"$HOME/google-cloud-sdk/install.sh" --usage-reporting=false --path-update=true
```

Установщик может ругнуться, что не смог поставить системный Python через sudo —
это необязательная часть, у SDK есть свой встроенный.

```bash
gcloud auth login
gcloud config set project idyllic-parser-493511-q3
```

**2. Включить нужные API**

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

Требуется привязанный к проекту платёжный аккаунт. Cloud Run укладывается в
бесплатный лимит (2 млн запросов в месяц), бот расходует пару десятков.

**3. Заполнить переменные**

```bash
cp env.yaml.example env.yaml
```

Нужны только `TELEGRAM_TOKEN` и `WEBHOOK_SECRET`, остальное уже заполнено.
Секрет сгенерировать так:

```bash
python3 -c "import secrets;print(secrets.token_urlsafe(32))"
```

> `env.yaml` в `.gitignore` — в репозиторий он не попадёт.

Ключ сервис-аккаунта не нужен: сервис запускается от имени `picotti-bot`
и авторизуется в Google по этой личности. См. `SheetsClient._build_credentials`.

`WEBHOOK_URL` известен заранее — Cloud Run собирает адрес по схеме
`имя-сервиса + номер проекта + регион`, поэтому деплой одноразовый.

**4. Деплой**

```bash
gcloud run deploy bollette-bot \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --service-account picotti-bot@idyllic-parser-493511-q3.iam.gserviceaccount.com \
  --env-vars-file env.yaml
```

`--allow-unauthenticated` нужен, чтобы Telegram мог достучаться. Эндпоинт
защищён секретным заголовком: запрос без него получает 403.

> **Токен не должен попадать в URL.** Cloud Run пишет адрес каждого запроса в
> свой журнал, поэтому токен в пути утёк бы в логи. Путь фиксированный
> (`/telegram`), проверка — через заголовок `secret_token`, заголовки не логируются.

---

### Шаг 5 — Проверить

Открой Telegram, найди своего бота по username и отправь `/start`.

Первое сообщение после долгого простоя идёт с задержкой в несколько секунд —
это Cloud Run поднимает уснувший контейнер. Дальше отвечает мгновенно.

Если бот молчит, посмотреть логи:

```bash
gcloud run services logs read bollette-bot --region europe-west1 --limit 50
```

---

## Локальный запуск

Без `WEBHOOK_URL` бот поднимается в режиме polling — публичный адрес не нужен:

```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN="..."
export GOOGLE_CREDENTIALS_JSON="$(cat credentials.json)"
python bot.py
```

---

## Структура файлов

```
bollette-bot/
├── bot.py             # Основная логика бота
├── sheets.py          # Работа с Google Sheets
├── bolletta_parser.py # Разбор PDF бollette E.ON
├── Dockerfile         # Сборка контейнера для Cloud Run
├── env.yaml.example   # Шаблон переменных окружения
├── requirements.txt
├── railway.toml       # Старый конфиг Railway (больше не используется)
└── .gitignore
```

---

## Как работает запись данных

При команде `/add` бот:
1. Спрашивает месяц
2. Показания счётчика → записывает в лист **Contattore Picotti** (колонки A, B)
3. Стоимость энергии, доп. стоимость, кВт всего, кВт сверху → записывает в лист **Luce** (колонки A–F)
4. kWh снизу считается автоматически: `kWh total − kWh su`
5. После записи читает рассчитанные значения из колонок I–L (Costo 1kWh, A testa su, A testa giu, Torna?)

Если строка с таким месяцем уже есть — данные обновляются. Если нет — добавляется новая строка.
