# 💡 Bollette Bot — Telegram бот для учёта электроэнергии

Бот для внесения данных о потреблении электроэнергии в Google Sheets.

---

## Команды бота

- `/start` — приветствие и список команд
- `/add` — внести данные за месяц (диалог по шагам)
- `/get` — посмотреть данные и итоги за месяц
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

### Шаг 4 — Задеплоить на Railway

1. Открой [railway.app](https://railway.app) → **Login with GitHub**
2. Нажми **New Project → Deploy from GitHub repo**
3. Выбери репозиторий `bollette-bot`
4. После деплоя перейди в **Variables** и добавь:

| Переменная | Значение |
|---|---|
| `TELEGRAM_TOKEN` | Токен от BotFather |
| `GOOGLE_CREDENTIALS_JSON` | Всё содержимое файла credentials.json |
| `SPREADSHEET_ID` | `1zLO85tPtJkAyPclcWYlTCSlznz-oFtzOqUvhwFMtUTg` |

5. Railway автоматически перезапустит бота после добавления переменных

---

### Шаг 5 — Проверить

Открой Telegram, найди своего бота по username и отправь `/start`

---

## Структура файлов

```
electricity_bot/
├── bot.py          # Основная логика бота
├── sheets.py       # Работа с Google Sheets
├── requirements.txt
├── railway.toml    # Конфиг Railway
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
