# Transportir

Сайт для подготовки к экзаменам: статьи с выделениями, конспекты, тесты, открытые вопросы, карточки, соответствия и словарь. Flask + SQLite.

## Запуск на своём компьютере

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m flask --app wsgi run --port 5057
```

Сайт откроется на http://localhost:5057. База и секретный ключ создаются сами в папке `instance/`.

## Публикация на PythonAnywhere

**1. Соберите архив** (в папке проекта, без `.venv` и `instance`):

```bash
tar -a -cf transportir.zip --exclude=__pycache__ app content wsgi.py requirements.txt README.md
```

**2. Загрузите и распакуйте.** Вкладка *Files* → загрузите `transportir.zip`. Затем *Consoles* → *Bash*:

```bash
mkdir -p ~/transportir && unzip -o ~/transportir.zip -d ~/transportir
mkvirtualenv --python=/usr/bin/python3.10 transportir
pip install -r ~/transportir/requirements.txt
```

**3. Создайте веб-приложение.** Вкладка *Web* → *Add a new web app* → *Manual configuration* → Python 3.10. Версия должна совпадать с версией виртуального окружения.

**4. Настройте его** на той же вкладке (вместо `USERNAME` — ваш логин):

| Поле | Значение |
|---|---|
| Source code | `/home/USERNAME/transportir` |
| Virtualenv | `/home/USERNAME/.virtualenvs/transportir` |
| Static files: URL `/static/` | `/home/USERNAME/transportir/app/static` |
| Force HTTPS | Enabled |

**5. Откройте WSGI-файл** (ссылка *WSGI configuration file*) и замените всё его содержимое:

```python
import os
import sys

sys.path.insert(0, "/home/USERNAME/transportir")
os.environ["HTTPS_ONLY"] = "1"  # только при включённом Force HTTPS

from wsgi import application
```

**6. Нажмите *Reload*.** Сайт будет на `https://USERNAME.pythonanywhere.com`.

### Обновление сайта

Загрузите новый архив, распакуйте той же командой `unzip` и нажмите *Reload*. Папку `~/transportir/instance` удалять нельзя: там аккаунты, прогресс и конспекты пользователей. Её стоит иногда скачивать как резервную копию.

### Забытый пароль

Восстановления по почте нет. Новый пароль задаётся в Bash-консоли:

```bash
workon transportir && cd ~/transportir && flask --app wsgi reset-password ЛОГИН
```

## Как добавить предмет

Создайте папку `content/<slug>/` и нажмите *Reload*. Код менять не нужно. Обязателен только `subject.json`, а разделы без файлов на сайте просто не появятся.

```
content/biology/
  subject.json       название и темы
  articles/01-cells.md
  quiz.json
  open.json
  definitions.json
  glossary.json      словарь, из него же строятся карточки перевода
  matching.json
```

`content/psychology/` — полный пример формата каждого файла.

`subject.json`:

```json
{"title": "Biology", "title_ru": "Биология", "description": "...", "order": 20,
 "topics": [{"slug": "cells", "title": "Cells", "title_ru": "Клетки"}]}
```

Начало статьи:

```
---
title: Cell structure
title_ru: Строение клетки
topic: cells
summary: Краткое описание для списка.
source: Откуда взят материал
---

Текст в Markdown. Поддерживаются таблицы.
```

Правила:

- `id` каждого элемента не должны меняться: по ним хранится прогресс. Новые элементы получают новые `id`.
- При ошибке в контенте (повтор `id`, неизвестная тема, неверный индекс ответа) сайт не запустится и в *Error log* будет указано, что исправить.
- Выделения привязаны к тексту статьи. Правку текста они переживают, пока выделенный фрагмент остаётся в статье без изменений.
