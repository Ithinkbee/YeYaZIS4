"""
auth.py — экран авторизации с разнообразными капчами и системой баллов.

Типы капчей (для регистрации берётся случайная, для входа — всегда математическая):
  • MathCaptcha        — классическая: +, −, ×  (данные — на canvas)
  • GuessNumberCaptcha — «угадай число» с подсказками больше/меньше
  • ReverseTextCaptcha — «напишите слово задом наперёд» (слово — на canvas)
  • EmojiCountCaptcha  — «посчитайте сколько раз встречается эмодзи» (строка — на canvas)
  • OddOneOutCaptcha   — «какое слово лишнее?» (список — на canvas)

Ключевые принципы отображения капчи:
  - description() возвращает ТОЛЬКО краткую инструкцию, БЕЗ самих данных
  - Все данные (пример, слово, список, эмодзи) — рисуются на canvas с тёмным фоном
  - Canvas ВСЕГДА виден для любого типа капчи
  - Порядок виджетов фиксирован: заголовок → инструкция → canvas → поле ввода
"""

import sqlite3, hashlib, random
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Callable, Optional

# ── БД пользователей (SQLite) ─────────────────────────────────────────────────
_DB_PATH = Path(__file__).parent.parent / 'data' / 'users.db'
_DB_PATH.parent.mkdir(exist_ok=True)


def _conn():
    c = sqlite3.connect(str(_DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        username     TEXT UNIQUE NOT NULL COLLATE NOCASE,
        pwd_hash     TEXT NOT NULL,
        total_score  INTEGER DEFAULT 0,
        best_streak  INTEGER DEFAULT 0,
        games_played INTEGER DEFAULT 0,
        created_at   TEXT DEFAULT (datetime('now','localtime'))
    )''')
    c.commit()
    return c


def _h(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


def register_user(username: str, password: str) -> tuple:
    username = username.strip()
    if len(username) < 3:
        return False, 'Имя пользователя — минимум 3 символа.'
    if len(password) < 4:
        return False, 'Пароль — минимум 4 символа.'
    try:
        db = _conn()
        db.execute('INSERT INTO users (username, pwd_hash) VALUES (?,?)',
                   (username, _h(password)))
        db.commit()
        db.close()
        return True, 'Регистрация успешна!'
    except sqlite3.IntegrityError:
        return False, f'Пользователь «{username}» уже существует.'


def login_user(username: str, password: str) -> Optional[dict]:
    db = _conn()
    row = db.execute(
        'SELECT * FROM users WHERE username=? AND pwd_hash=?',
        (username.strip(), _h(password))
    ).fetchone()
    db.close()
    return dict(row) if row else None


def save_score(username: str, session_score: int, streak: int):
    db = _conn()
    db.execute('''UPDATE users SET
        total_score  = total_score + ?,
        best_streak  = MAX(best_streak, ?),
        games_played = games_played + 1
        WHERE username = ?''', (session_score, streak, username))
    db.commit()
    db.close()


def get_leaderboard(limit: int = 10) -> list:
    db = _conn()
    rows = db.execute(
        'SELECT username, total_score, best_streak, games_played '
        'FROM users ORDER BY total_score DESC LIMIT ?', (limit,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# Базовый класс капчи
# ══════════════════════════════════════════════════════════════════════════════

class BaseCaptcha:
    """
    Базовый класс капчи.

    Контракт:
      description() → короткая инструкция БЕЗ данных задачи
                       например: «Решите пример:» или «Напишите слово наоборот:»
      draw(canvas)  → рисует данные задачи на canvas (всегда вызывается)
      check(str)    → True/False
    """
    name  = 'base'
    title = 'Капча'

    # Размер canvas — все подклассы используют одинаковый
    CANVAS_W = 430
    CANVAS_H = 78

    def __init__(self):
        self._hint = ''

    def generate(self) -> None:
        raise NotImplementedError

    def description(self) -> str:
        """ТОЛЬКО инструкция, без данных задачи."""
        raise NotImplementedError

    def draw(self, canvas: tk.Canvas) -> None:
        """Рисует данные задачи на canvas с тёмным фоном."""
        raise NotImplementedError

    def check(self, val: str) -> bool:
        raise NotImplementedError

    def hint_after_fail(self) -> str:
        return self._hint

    def is_multi_attempt(self) -> bool:
        return False

    # ── Общие утилиты отрисовки ──────────────────────────────────────────────

    @staticmethod
    def _bg(canvas: tk.Canvas):
        """Рисует стандартный зашумлённый фон."""
        W, H = int(canvas['width']), int(canvas['height'])
        canvas.delete('all')
        canvas.create_rectangle(0, 0, W, H, fill='#0E0E20', outline='')
        # Вертикальные линии-помехи
        for x in range(0, W, 18):
            canvas.create_line(x, 0, x + random.randint(-8, 8), H,
                               fill='#1E1E38', width=1)
        # Горизонтальные
        for y in range(0, H, 12):
            canvas.create_line(0, y, W, y + random.randint(-4, 4),
                               fill='#1E1E38', width=1)
        # Точки
        for _ in range(35):
            x, y = random.randint(0, W), random.randint(0, H)
            canvas.create_oval(x, y, x+2, y+2, fill='#2A2A50', outline='')
        return W, H

    @staticmethod
    def _draw_text_distorted(canvas: tk.Canvas, text: str,
                              y_center: int, x_start: int = 14,
                              colors=None, size_range=(17, 24)):
        """Рисует строку с искажением — каждый символ немного смещён."""
        if colors is None:
            colors = ['#CDD6F4', '#89B4FA', '#A6E3A1', '#F9E2AF', '#CBA6F7', '#F38BA8']
        x = x_start
        for ch in text:
            dy   = random.randint(-6, 6)
            size = random.randint(*size_range)
            col  = random.choice(colors)
            canvas.create_text(x, y_center + dy, text=ch, fill=col,
                               font=('Courier New', size, 'bold'), anchor='w')
            x += size + random.randint(1, 5)

    @staticmethod
    def _draw_crossing_lines(canvas: tk.Canvas, W: int, H: int, n: int = 3):
        for _ in range(n):
            canvas.create_line(
                random.randint(0, W//3), random.randint(0, H),
                random.randint(2*W//3, W), random.randint(0, H),
                fill='#3A3A60', width=random.randint(1, 2))


# ── Математическая капча ──────────────────────────────────────────────────────

class MathCaptcha(BaseCaptcha):
    name  = 'math'
    title = '🧮 Математика'

    def __init__(self):
        super().__init__()
        self.answer = 0
        self._question = ''

    def generate(self):
        kind = random.choice(['add', 'sub', 'mul'])
        if kind == 'add':
            a, b = random.randint(10, 50), random.randint(5, 30)
            self._question, self.answer = f'{a} + {b} = ?', a + b
        elif kind == 'sub':
            a, b = random.randint(20, 60), random.randint(5, 20)
            self._question, self.answer = f'{a} - {b} = ?', a - b
        else:
            a, b = random.randint(2, 9), random.randint(2, 9)
            self._question, self.answer = f'{a} x {b} = ?', a * b
        self._hint = ''

    def description(self) -> str:
        return 'Решите пример:'

    def draw(self, canvas: tk.Canvas):
        W, H = self._bg(canvas)
        self._draw_text_distorted(canvas, self._question, H // 2)
        self._draw_crossing_lines(canvas, W, H)

    def check(self, val: str) -> bool:
        try:
            return int(val.strip()) == self.answer
        except ValueError:
            return False


# ── «Угадай число» ────────────────────────────────────────────────────────────

class GuessNumberCaptcha(BaseCaptcha):
    name  = 'guess'
    title = '🎯 Угадай число'

    def __init__(self):
        super().__init__()
        self.answer   = 0
        self.attempts = 0
        self._range_hint = '?'   # сужается по ходу игры: «от X до Y»

    def generate(self):
        self.answer       = random.randint(1, 100)
        self.attempts     = 0
        self._lo          = 1
        self._hi          = 100
        self._range_hint  = '1 — 100'
        self._hint        = ''

    def description(self) -> str:
        return 'Угадайте число на картинке (подсказки появятся после каждой попытки):'

    def draw(self, canvas: tk.Canvas):
        W, H = self._bg(canvas)
        # Отображаем текущий диапазон крупно
        rng_text = f'{self._lo} — {self._hi}'
        self._draw_text_distorted(canvas, rng_text, H // 2,
                                   colors=['#F9E2AF', '#FFD700', '#FFA500'],
                                   size_range=(20, 28))
        # Подпись мелко
        canvas.create_text(W // 2, H - 10,
                           text=f'диапазон поиска  (попытка {self.attempts + 1})',
                           fill='#606080', font=('Segoe UI', 9), anchor='center')
        self._draw_crossing_lines(canvas, W, H, n=2)

    def is_multi_attempt(self) -> bool:
        return True

    def check(self, val: str) -> bool:
        try:
            n = int(val.strip())
        except ValueError:
            self._hint = '⚠️ Введите целое число.'
            return False
        self.attempts += 1
        if n == self.answer:
            return True
        if n < self.answer:
            self._lo   = max(self._lo, n + 1)
            self._hint = f'↑ Больше, чем {n}  (попытка {self.attempts})'
        else:
            self._hi   = min(self._hi, n - 1)
            self._hint = f'↓ Меньше, чем {n}  (попытка {self.attempts})'
        self._range_hint = f'{self._lo} — {self._hi}'
        return False


# ── «Напишите слово задом наперёд» ────────────────────────────────────────────

class ReverseTextCaptcha(BaseCaptcha):
    name  = 'reverse'
    title = '🔄 Наоборот'

    WORDS = [
        'привет', 'капча', 'компьютер', 'телефон', 'клавиатура',
        'лингвистика', 'синтаксис', 'анализатор', 'пользователь',
        'регистрация', 'морфология', 'предложение', 'токен', 'разбор',
    ]

    def __init__(self):
        super().__init__()
        self._word     = ''
        self._reversed = ''

    def generate(self):
        self._word     = random.choice(self.WORDS)
        self._reversed = self._word[::-1]
        self._hint     = ''

    def description(self) -> str:
        return 'Напишите слово с картинки задом наперёд:'

    def draw(self, canvas: tk.Canvas):
        W, H = self._bg(canvas)
        self._draw_text_distorted(canvas, self._word, H // 2,
                                   colors=['#94E2D5', '#A6E3A1', '#89DCEB', '#B4BEFE'])
        self._draw_crossing_lines(canvas, W, H)

    def check(self, val: str) -> bool:
        return val.strip().lower() == self._reversed


# ── «Посчитайте эмодзи» ──────────────────────────────────────────────────────

class EmojiCountCaptcha(BaseCaptcha):
    name  = 'emoji'
    title = '🔢 Счёт эмодзи'

    TARGETS = ['🐱', '🌟', '🎈', '🍕', '🚀', '❤️', '🌈', '⚡']
    NOISE   = ['🐶', '🍎', '🌙', '🎵', '🔥', '💎', '🌸', '⭐']

    def __init__(self):
        super().__init__()
        self._target  = ''
        self._display = ''
        self.answer   = 0

    def generate(self):
        self._target = random.choice(self.TARGETS)
        noise        = [e for e in self.NOISE if e != self._target]
        self.answer  = random.randint(3, 8)
        chars        = [self._target] * self.answer
        for _ in range(random.randint(5, 12)):
            chars.append(random.choice(noise))
        random.shuffle(chars)
        self._display = '  '.join(chars)
        self._hint    = ''

    def description(self) -> str:
        return f'Посчитайте, сколько раз встречается {self._target} на картинке:'

    def draw(self, canvas: tk.Canvas):
        W, H = self._bg(canvas)
        # Эмодзи рисуем в несколько строк если длинная строка
        items = self._display.split('  ')
        per_row = 10
        rows = [items[i:i+per_row] for i in range(0, len(items), per_row)]
        row_h = H // (len(rows) + 1)
        for ri, row in enumerate(rows):
            x = 12
            y = row_h * (ri + 1)
            for em in row:
                size = random.randint(15, 20)
                dy   = random.randint(-4, 4)
                canvas.create_text(x, y + dy, text=em,
                                   font=('Segoe UI Emoji', size), anchor='w')
                x += size + random.randint(6, 12)
        self._draw_crossing_lines(canvas, W, H, n=2)

    def check(self, val: str) -> bool:
        try:
            return int(val.strip()) == self.answer
        except ValueError:
            return False


# ── «Какое слово лишнее» ─────────────────────────────────────────────────────

class OddOneOutCaptcha(BaseCaptcha):
    name  = 'odd'
    title = '🤔 Что лишнее'

    GROUPS = [
        (['яблоко', 'груша', 'слива', 'морковь'],       'морковь',  'остальное — фрукты'),
        (['кошка', 'собака', 'машина', 'корова'],        'машина',   'остальное — животные'),
        (['круг', 'квадрат', 'треугольник', 'дом'],      'дом',      'остальное — геом. фигуры'),
        (['красный', 'синий', 'большой', 'зелёный'],     'большой',  'остальное — цвета'),
        (['понедельник', 'вторник', 'среда', 'январь'],  'январь',   'остальное — дни недели'),
        (['бежать', 'прыгать', 'стол', 'плавать'],       'стол',     'остальное — глаголы'),
        (['Москва', 'Париж', 'Россия', 'Берлин'],        'Россия',   'остальное — города'),
        (['один', 'два', 'три', 'буква'],                'буква',    'остальное — числительные'),
    ]

    def __init__(self):
        super().__init__()
        self._words:   list = []
        self._correct        = ''
        self._explain        = ''

    def generate(self):
        words, correct, explain = random.choice(self.GROUPS)
        self._words   = list(words)
        random.shuffle(self._words)
        self._correct = correct
        self._explain = explain
        self._hint    = ''

    def description(self) -> str:
        return 'Введите НОМЕР лишнего слова с картинки:'

    def draw(self, canvas: tk.Canvas):
        W, H = self._bg(canvas)
        COLORS = ['#F9E2AF', '#A6E3A1', '#89B4FA', '#F38BA8']
        col_x  = [W // 8, W * 3 // 8, W * 5 // 8, W * 7 // 8]
        for i, (word, cx) in enumerate(zip(self._words, col_x)):
            dy   = random.randint(-5, 5)
            col  = COLORS[i % len(COLORS)]
            size = random.randint(13, 16)
            canvas.create_text(cx, H // 2 + dy,
                               text=f'{i+1}) {word}',
                               fill=col,
                               font=('Segoe UI', size, 'bold'),
                               anchor='center')
        self._draw_crossing_lines(canvas, W, H, n=2)

    def check(self, val: str) -> bool:
        try:
            n = int(val.strip())
        except ValueError:
            return False
        if 1 <= n <= len(self._words):
            return self._words[n - 1] == self._correct
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Фабрика
# ══════════════════════════════════════════════════════════════════════════════

CAPTCHA_CLASSES = [
    MathCaptcha,
    GuessNumberCaptcha,
    ReverseTextCaptcha,
    EmojiCountCaptcha,
    OddOneOutCaptcha,
]


def make_random_captcha() -> BaseCaptcha:
    cls = random.choice(CAPTCHA_CLASSES)
    cap = cls()
    cap.generate()
    return cap


# ── Цвета ─────────────────────────────────────────────────────────────────────
C = {
    'bg':     '#1E1E2E',
    'panel':  '#2A2A3E',
    'acc':    '#7C5CBF',
    'acc2':   '#5C8CBF',
    'text':   '#CDD6F4',
    'text2':  '#A6ADC8',
    'green':  '#A6E3A1',
    'red':    '#F38BA8',
    'yellow': '#F9E2AF',
    'border': '#45475A',
    'entry':  '#313244',
    'inp_fg': '#FFFFFF',
}


def _mk_entry(parent, show=None, textvariable=None):
    kw = dict(bg=C['entry'], fg=C['inp_fg'],
              insertbackground=C['inp_fg'], relief='flat',
              font=('Segoe UI', 13),
              highlightthickness=1,
              highlightcolor=C['acc'],
              highlightbackground=C['border'])
    if textvariable:
        kw['textvariable'] = textvariable
    if show:
        kw['show'] = show
    return tk.Entry(parent, **kw)


def _mk_btn(parent, text, cmd, bg=None):
    return tk.Button(parent, text=text, command=cmd,
                     bg=bg or C['acc'], fg=C['text'],
                     font=('Segoe UI', 12, 'bold'), relief='flat',
                     activebackground=C['acc2'], activeforeground='white',
                     cursor='hand2', padx=14, pady=7)


def _mk_lbl(parent, text, size=12, bold=False, color=None, bg=None):
    return tk.Label(parent, text=text,
                    bg=bg or C['panel'],
                    fg=color or C['text'],
                    font=('Segoe UI', size, 'bold' if bold else 'normal'))


# ══════════════════════════════════════════════════════════════════════════════
# Окно авторизации
# ══════════════════════════════════════════════════════════════════════════════

class AuthWindow:
    """
    Toplevel поверх скрытого root.
    Структура капча-блока фиксирована и не меняется при смене типа капчи:
      [заголовок типа] → [инструкция] → [canvas] → [поле ввода + кнопка 🔄]
    Данные задачи всегда на canvas — никогда не в тексте label.
    """

    def __init__(self, root: tk.Tk, on_success: Callable[[dict], None]):
        self._root        = root
        self._on_success  = on_success
        self._login_cap   = MathCaptcha()
        self._login_cap.generate()
        self._reg_cap: BaseCaptcha = make_random_captcha()
        self._mode        = 'login'

        self.win = tk.Toplevel(root)
        self.win.title('СинтАналитик — Вход')
        self.win.resizable(True, True)
        self.win.configure(bg=C['bg'])
        self.win.protocol('WM_DELETE_WINDOW', root.destroy)

        self._build()

        # Центрируем с ограничением высоты 90% экрана
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        W_win = self.win.winfo_reqwidth()
        H_win = self.win.winfo_reqheight()
        max_h = int(sh * 0.90)
        H_final = min(H_win, max_h)
        x = (sw - W_win) // 2
        y = max(0, (sh - H_final) // 2)
        self.win.geometry(f'{W_win}x{H_final}+{x}+{y}')
        self.win.minsize(W_win, min(H_final, 520))

    # ── Построение UI ─────────────────────────────────────────────────────────

    def _build(self):
        w   = self.win
        bg  = C['bg']
        pan = C['panel']

        # ── Прокручиваемый контейнер для всего содержимого ──────────────────
        # Позволяет видеть все элементы даже на маленьких экранах
        _outer_canvas = tk.Canvas(w, bg=bg, highlightthickness=0)
        _vscroll = tk.Scrollbar(w, orient='vertical', command=_outer_canvas.yview)
        _outer_canvas.configure(yscrollcommand=_vscroll.set)
        _vscroll.pack(side='right', fill='y')
        _outer_canvas.pack(side='left', fill='both', expand=True)
        # Внутренний фрейм — в него кладём весь UI
        _inner = tk.Frame(_outer_canvas, bg=bg)
        _win_id = _outer_canvas.create_window((0, 0), window=_inner, anchor='nw')
        _inner.bind('<Configure>',
                    lambda e: _outer_canvas.configure(
                        scrollregion=_outer_canvas.bbox('all')))
        _outer_canvas.bind('<Configure>',
                           lambda e: _outer_canvas.itemconfig(_win_id, width=e.width))
        # Колёсико мыши
        def _mw(ev):
            if ev.num == 4:   _outer_canvas.yview_scroll(-1, 'units')
            elif ev.num == 5: _outer_canvas.yview_scroll(1, 'units')
            else:             _outer_canvas.yview_scroll(int(-1*(ev.delta/120)), 'units')
        _outer_canvas.bind('<MouseWheel>', _mw)
        _outer_canvas.bind('<Button-4>',   _mw)
        _outer_canvas.bind('<Button-5>',   _mw)
        _inner.bind('<MouseWheel>', _mw)
        _inner.bind('<Button-4>',   _mw)
        _inner.bind('<Button-5>',   _mw)

        # Все виджеты кладём в _inner, а не в w
        w = _inner   # noqa: переопределяем для удобства

        # Заголовок
        tk.Label(w, text='⚡  СинтАналитик', bg=bg, fg=C['text'],
                 font=('Segoe UI', 22, 'bold')).pack(pady=(22, 4))
        tk.Label(w, text='Семантико-синтаксический анализ текста',
                 bg=bg, fg=C['text2'],
                 font=('Segoe UI', 10)).pack(pady=(0, 14))

        # ── Карточка формы ──────────────────────────────────────────────────
        card = tk.Frame(w, bg=pan, padx=24, pady=16)
        card.pack(fill='x', padx=28)

        # Переключатель
        tabs = tk.Frame(card, bg=pan)
        tabs.pack(fill='x', pady=(0, 16))
        self._tab_login = tk.Button(
            tabs, text='  Вход  ',
            command=lambda: self._switch('login'),
            bg=C['acc'], fg=C['text'], relief='flat',
            font=('Segoe UI', 12, 'bold'), cursor='hand2', padx=10, pady=5)
        self._tab_login.pack(side='left', padx=(0, 4))
        self._tab_reg = tk.Button(
            tabs, text='  Регистрация  ',
            command=lambda: self._switch('register'),
            bg=C['border'], fg=C['text2'], relief='flat',
            font=('Segoe UI', 12), cursor='hand2', padx=10, pady=5)
        self._tab_reg.pack(side='left')

        # Поля
        _mk_lbl(card, 'Имя пользователя').pack(anchor='w')
        self._uvar = tk.StringVar()
        _mk_entry(card, textvariable=self._uvar).pack(fill='x', pady=(3, 12))

        _mk_lbl(card, 'Пароль').pack(anchor='w')
        self._pvar = tk.StringVar()
        _mk_entry(card, show='•', textvariable=self._pvar).pack(
            fill='x', pady=(3, 16))

        # ── Блок капчи — фиксированный порядок, ничего не скрывается ────────
        sep = tk.Frame(card, bg=C['border'], height=1)
        sep.pack(fill='x', pady=(0, 10))

        # 1) Заголовок типа капчи
        self._cap_title_var = tk.StringVar()
        tk.Label(card, textvariable=self._cap_title_var,
                 bg=pan, fg=C['yellow'],
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w')

        # 2) Краткая инструкция (БЕЗ данных задачи)
        self._cap_desc_var = tk.StringVar()
        tk.Label(card, textvariable=self._cap_desc_var,
                 bg=pan, fg=C['text'],
                 font=('Segoe UI', 11),
                 wraplength=520, justify='left').pack(
                     anchor='w', pady=(2, 6))

        # 3) Canvas — ВСЕГДА виден, данные задачи здесь
        self._cap_canvas = tk.Canvas(
            card,
            width=BaseCaptcha.CANVAS_W,
            height=BaseCaptcha.CANVAS_H,
            bg='#0E0E20',
            highlightthickness=1,
            highlightbackground=C['border'])
        self._cap_canvas.pack(anchor='w', pady=(0, 6))

        # 4) Поле ввода + кнопка обновления
        cap_row = tk.Frame(card, bg=pan)
        cap_row.pack(fill='x', pady=(0, 4))
        self._cvar = tk.StringVar()
        _mk_entry(cap_row, textvariable=self._cvar).pack(
            side='left', ipady=2, fill='x', expand=True)
        _mk_btn(cap_row, '🔄', self._regen, bg=C['border']).pack(
            side='left', padx=8)

        # 5) Подсказка (для GuessNumber)
        self._cap_hint_var = tk.StringVar()
        tk.Label(card, textvariable=self._cap_hint_var,
                 bg=pan, fg=C['yellow'],
                 font=('Segoe UI', 11, 'italic'),
                 wraplength=520, justify='left').pack(
                     anchor='w', pady=(2, 0))

        # Сообщение об ошибке
        self._msg = tk.StringVar()
        tk.Label(card, textvariable=self._msg,
                 bg=pan, fg=C['red'],
                 font=('Segoe UI', 11),
                 wraplength=520, justify='left').pack(
                     pady=(6, 0), anchor='w')

        # Кнопка действия
        self._act_btn = _mk_btn(card, 'Войти', self._submit)
        self._act_btn.pack(fill='x', pady=(14, 4), ipady=4)

        # ── Таблица лидеров ──────────────────────────────────────────────────
        lb = tk.Frame(w, bg=bg)
        lb.pack(fill='x', padx=28, pady=(12, 12))
        tk.Label(lb, text='🏆  Таблица лидеров', bg=bg, fg=C['text'],
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w')

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Auth.Treeview',
            background=pan, foreground=C['text'],
            fieldbackground=pan, rowheight=24,
            font=('Segoe UI', 11))
        style.configure('Auth.Treeview.Heading',
            background=C['border'], foreground=C['text'],
            font=('Segoe UI', 11, 'bold'), relief='flat')
        style.map('Auth.Treeview', background=[('selected', C['acc'])])

        cols = ('r', 'u', 's', 'st', 'g')
        self._lb = ttk.Treeview(lb, columns=cols, show='headings',
                                 height=5, style='Auth.Treeview')
        for col, hdr, w_ in zip(
                cols,
                ('№', 'Игрок', 'Баллы', 'Лучшая серия', 'Игр'),
                (30,   150,     70,       110,             50)):
            self._lb.heading(col, text=hdr)
            self._lb.column(col, width=w_, anchor='center')
        self._lb.pack(fill='x')
        self._lb.bind('<MouseWheel>', _mw)
        self._lb.bind('<Button-4>',   _mw)
        self._lb.bind('<Button-5>',   _mw)
        self._refresh_lb()

        # Enter → submit на реальном окне (не _inner)
        self.win.bind('<Return>', lambda e: self._submit())

        # Первичная отрисовка капчи
        self._refresh_captcha_view()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _current_cap(self) -> BaseCaptcha:
        return self._reg_cap if self._mode == 'register' else self._login_cap

    def _switch(self, mode: str):
        self._mode = mode
        if mode == 'login':
            self._tab_login.config(bg=C['acc'],    fg=C['text'])
            self._tab_reg.config(  bg=C['border'], fg=C['text2'])
            self._act_btn.config(text='Войти')
        else:
            self._tab_login.config(bg=C['border'], fg=C['text2'])
            self._tab_reg.config(  bg=C['acc'],    fg=C['text'])
            self._act_btn.config(text='Зарегистрироваться')
        self._msg.set('')
        self._cvar.set('')
        self._refresh_captcha_view()

    def _refresh_captcha_view(self):
        """Обновляет заголовок, инструкцию и перерисовывает canvas."""
        cap = self._current_cap()
        self._cap_title_var.set(f'Капча: {cap.title}')
        self._cap_desc_var.set(cap.description())
        self._cap_hint_var.set(cap.hint_after_fail())
        cap.draw(self._cap_canvas)

    def _regen(self):
        if self._mode == 'register':
            self._reg_cap = make_random_captcha()
        else:
            self._login_cap.generate()
        self._cvar.set('')
        self._cap_hint_var.set('')
        self._refresh_captcha_view()

    def _submit(self):
        username = self._uvar.get().strip()
        password = self._pvar.get().strip()
        cap_ans  = self._cvar.get().strip()

        if not username or not password:
            self._msg.set('Заполните имя пользователя и пароль.')
            return

        cap = self._current_cap()
        if not cap.check(cap_ans):
            if cap.is_multi_attempt():
                self._cap_hint_var.set(cap.hint_after_fail())
                self._msg.set('❌ Неверно — подсказка обновлена. Попробуйте ещё раз.')
                cap.draw(self._cap_canvas)   # обновляем диапазон на canvas
                self._cvar.set('')
                return
            self._msg.set('❌ Неверный ответ. Новая задача — попробуйте снова.')
            self._regen()
            return

        if self._mode == 'register':
            ok, msg = register_user(username, password)
            if not ok:
                self._msg.set(msg)
                self._regen()
                return
            user = login_user(username, password)
            if user is None:
                self._msg.set('Регистрация прошла, но вход не удался. Попробуйте вручную.')
                self._switch('login')
                return
        else:
            user = login_user(username, password)
            if user is None:
                self._msg.set('❌ Неверное имя пользователя или пароль.')
                self._regen()
                return

        self.win.destroy()
        self._on_success(user)

    def _refresh_lb(self):
        self._lb.delete(*self._lb.get_children())
        for i, r in enumerate(get_leaderboard(8), 1):
            medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, str(i))
            self._lb.insert('', 'end', values=(
                medal, r['username'], r['total_score'],
                r['best_streak'], r['games_played']))