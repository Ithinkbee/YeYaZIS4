# СинтАналитик

**Лабораторная работа №4 — Вариант 4 (DOC, русский язык)**  
Система автоматического семантико-синтаксического анализа текстов естественного языка

---

## Возможности

| Функция | Описание |
|---|---|
| 📂 Загрузка файлов | DOC, DOCX, TXT, PDF, RTF, HTML |
| 🔤 Токенизация | Разбиение на токены с леммами |
| 📚 Морфоанализ | Часть речи (14 тегов Universal POS) |
| 🔗 Синтаксис | Синтаксические роли (Universal Dependencies) |
| 🏷️ NER | Именованные сущности (персоны, орг., места, даты) |
| 💬 Тональность | Позитивный / нейтральный / негативный + оценка −1..+1 |
| 🎮 Квиз | 10 вопросов с 4 вариантами ответа по реальному тексту |
| 🗂️ История | Хранение всех анализов в PostgreSQL |
| 📤 Экспорт | TXT, JSON, HTML-отчёт |

---

## Установка

### 1. Python-зависимости

```bash
pip install -r requirements.txt
```

Для чтения `.doc` установите LibreOffice:
```bash
sudo apt install libreoffice        # Ubuntu/Debian
# или
brew install libreoffice            # macOS
```

### 2. PostgreSQL (опционально)

```bash
# Создать базу данных
createdb sintanalitik

# Таблицы создаются автоматически при первом запуске
```

Задайте переменные окружения (или оставьте дефолтные в `core/database.py`):

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=sintanalitik
export DB_USER=postgres
export DB_PASSWORD=1111
```

Если PostgreSQL не настроен — приложение работает без БД (вкладка «История» будет недоступна).

### 3. Запуск

```bash
cd sintanalitik
python main.py
```

---

## Структура проекта

```
sintanalitik/
├── main.py              # Точка входа
├── requirements.txt
├── README.md
├── core/
│   ├── analyzer.py      # NLP-движок (natasha + pymorphy2)
│   ├── loader.py        # Загрузка файлов разных форматов
│   ├── database.py      # PostgreSQL ORM
│   ├── exporter.py      # Экспорт TXT/JSON/HTML
│   └── quiz.py          # Движок квиза
└── gui/
    ├── app.py           # Главное окно (7 вкладок)
    └── styles.py        # Цвета, шрифты, константы
```

---

## Схема базы данных

```sql
analyses   -- id, created_at, source_name, source_text,
           -- sentence_count, word_count, elapsed_ms,
           -- sentiment, sentiment_score, notes, sentences_json

tokens     -- id, analysis_id, word, pos, role, sentence_id

entities   -- id, analysis_id, text, label, label_ru
```

---

## Используемые библиотеки

| Библиотека | Назначение |
|---|---|
| **natasha** | Сегментация, морфологический теггинг, синтаксический разбор, NER |
| **pymorphy2** | Лемматизация русских слов |
| **python-docx** | Чтение DOCX файлов |
| **psycopg2** | Работа с PostgreSQL |
| **tkinter** | Графический интерфейс (встроен в Python) |
| **matplotlib** | Визуализация (графики) |

---

## Горячие клавиши

| Клавиша | Действие |
|---|---|
| `Ctrl+O` | Открыть файл |
| `Ctrl+R` | Запустить анализ |
| `Ctrl+S` | Сохранить в БД |
| `Ctrl+Q` | Выйти |

---

## Примечание о первом запуске

При первом запуске natasha загружает нейросетевые модели (~100 МБ).  
Последующие запуски используют кэш и работают значительно быстрее.

---

## Лицензия

Учебный проект. Лабораторная работа №4.
