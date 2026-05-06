"""
shop.py — Магазин: разблокировки функций и цветовые схемы.
Данные хранятся в том же users.db (SQLite).
"""

import sqlite3
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent.parent / 'data' / 'users.db'

# ── Товары магазина ────────────────────────────────────────────────────────────

UNLOCK_ITEMS = {
    'tokens':    {'name': 'Вкладка «Токены»',      'price': 30,  'desc': 'Разблокирует таблицу токенов с морфологической разметкой'},
    'entities':  {'name': 'Вкладка «Сущности»',    'price': 40,  'desc': 'Разблокирует поиск именованных сущностей (NER)'},
    'sentiment': {'name': 'Вкладка «Тональность»', 'price': 50,  'desc': 'Разблокирует анализ тональности текста'},
    'semantics': {'name': 'Вкладка «Семантика»',   'price': 60,  'desc': 'Разблокирует семантический анализ текста'},
    'export':    {'name': 'Кнопка «Экспорт JSON»', 'price': 20,  'desc': 'Разблокирует экспорт результатов в JSON'},
}

THEME_ITEMS = {
    'default': {
        'name': '🌑 Классическая (тёмная)',
        'price': 0,
        'desc': 'Стандартная тёмно-синяя тема',
        'colors': {
            'bg': '#1E1E2E', 'panel': '#2A2A3E', 'accent': '#7C5CBF',
            'accent2': '#5C8CBF', 'text': '#CDD6F4', 'text2': '#A6ADC8',
            'green': '#A6E3A1', 'red': '#F38BA8', 'yellow': '#F9E2AF',
            'blue': '#89B4FA', 'teal': '#94E2D5', 'border': '#45475A',
            'pos_col': '#A6E3A1', 'neg_col': '#F38BA8', 'neu_col': '#F9E2AF',
        },
    },
    'forest': {
        'name': '🌲 Лесная (зелёная)',
        'price': 80,
        'desc': 'Тёмно-зелёная тема в стиле природы',
        'colors': {
            'bg': '#1A2318', 'panel': '#243020', 'accent': '#4A8C3F',
            'accent2': '#3A7C6B', 'text': '#D4E8C2', 'text2': '#99B888',
            'green': '#7EC850', 'red': '#E87070', 'yellow': '#E8D070',
            'blue': '#70B8E8', 'teal': '#70E8C8', 'border': '#3A5030',
            'pos_col': '#7EC850', 'neg_col': '#E87070', 'neu_col': '#E8D070',
        },
    },
    'ocean': {
        'name': '🌊 Океан (синяя)',
        'price': 80,
        'desc': 'Глубокая синяя тема в морском стиле',
        'colors': {
            'bg': '#0A1628', 'panel': '#0E2040', 'accent': '#1A6B9C',
            'accent2': '#2A8CBF', 'text': '#C2D8F0', 'text2': '#88AACC',
            'green': '#50D8A0', 'red': '#E87090', 'yellow': '#E8C870',
            'blue': '#50A8E8', 'teal': '#50E8D8', 'border': '#1A3050',
            'pos_col': '#50D8A0', 'neg_col': '#E87090', 'neu_col': '#E8C870',
        },
    },
    'crimson': {
        'name': '🔴 Малиновый закат',
        'price': 100,
        'desc': 'Тёплая тёмно-красная тема',
        'colors': {
            'bg': '#1E1010', 'panel': '#2E1818', 'accent': '#9C2A2A',
            'accent2': '#BF4A3A', 'text': '#F0D0C8', 'text2': '#C09090',
            'green': '#80C870', 'red': '#F05050', 'yellow': '#F0C050',
            'blue': '#7090E0', 'teal': '#70D0C0', 'border': '#503020',
            'pos_col': '#80C870', 'neg_col': '#F05050', 'neu_col': '#F0C050',
        },
    },
    'light': {
        'name': '☀️ Светлая',
        'price': 60,
        'desc': 'Светлая тема для работы при дневном освещении',
        'colors': {
            'bg': '#F5F5FA', 'panel': '#E8E8F0', 'accent': '#6040B0',
            'accent2': '#4060C0', 'text': '#202040', 'text2': '#505070',
            'green': '#208040', 'red': '#C02020', 'yellow': '#A06000',
            'blue': '#2060A0', 'teal': '#107060', 'border': '#C0C0D0',
            'pos_col': '#208040', 'neg_col': '#C02020', 'neu_col': '#A06000',
        },
    },
}

ALL_ITEMS = {**UNLOCK_ITEMS, **THEME_ITEMS}


# ── БД ────────────────────────────────────────────────────────────────────────

def _conn():
    c = sqlite3.connect(str(_DB_PATH))
    c.row_factory = sqlite3.Row
    # Таблица покупок пользователя
    c.execute('''CREATE TABLE IF NOT EXISTS user_purchases (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT NOT NULL COLLATE NOCASE,
        item_id     TEXT NOT NULL,
        purchased_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(username, item_id)
    )''')
    # Активная тема
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings (
        username    TEXT PRIMARY KEY COLLATE NOCASE,
        active_theme TEXT DEFAULT "default"
    )''')
    c.commit()
    return c


def get_purchases(username: str) -> set:
    """Возвращает множество item_id, купленных пользователем."""
    db = _conn()
    rows = db.execute(
        'SELECT item_id FROM user_purchases WHERE username=?', (username,)
    ).fetchall()
    db.close()
    # 'default' theme always owned
    owned = {'default'} | {r['item_id'] for r in rows}
    return owned


def buy_item(username: str, item_id: str) -> tuple:
    """
    Покупка товара. Возвращает (успех: bool, сообщение: str).
    Списывает баллы из таблицы users.
    """
    if item_id not in ALL_ITEMS:
        return False, 'Товар не найден.'
    owned = get_purchases(username)
    if item_id in owned:
        return False, 'Уже куплено.'

    price = ALL_ITEMS[item_id]['price']
    db = _conn()
    try:
        row = db.execute(
            'SELECT total_score FROM users WHERE username=?', (username,)
        ).fetchone()
        if not row:
            return False, 'Пользователь не найден.'
        balance = row['total_score']
        if balance < price:
            return False, f'Недостаточно баллов. Нужно {price}, у вас {balance}.'
        db.execute('UPDATE users SET total_score = total_score - ? WHERE username=?',
                   (price, username))
        db.execute('INSERT INTO user_purchases (username, item_id) VALUES (?,?)',
                   (username, item_id))
        db.commit()
        return True, f'Куплено: {ALL_ITEMS[item_id]["name"]}'
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()


def get_active_theme(username: str) -> str:
    db = _conn()
    row = db.execute(
        'SELECT active_theme FROM user_settings WHERE username=?', (username,)
    ).fetchone()
    db.close()
    return row['active_theme'] if row else 'default'


def set_active_theme(username: str, theme_id: str) -> bool:
    owned = get_purchases(username)
    if theme_id not in owned:
        return False
    db = _conn()
    db.execute(
        'INSERT INTO user_settings (username, active_theme) VALUES (?,?) '
        'ON CONFLICT(username) DO UPDATE SET active_theme=?',
        (username, theme_id, theme_id)
    )
    db.commit()
    db.close()
    return True


def get_user_balance(username: str) -> int:
    db = _conn()
    row = db.execute('SELECT total_score FROM users WHERE username=?', (username,)).fetchone()
    db.close()
    return row['total_score'] if row else 0