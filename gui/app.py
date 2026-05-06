"""
app.py — главное окно приложения СинтАналитик.
Вкладки: Анализ | Токены | Сущности | Тональность | Тест | История | Магазин | Помощь
"""
import os, sys, json, threading, random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as mpatches

# local
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.analyzer import get_analyzer, AnalysisResult
from core.loader   import load_file
from core.quiz     import generate_quiz
from core.database import get_db
from core.auth     import AuthWindow, save_score, get_leaderboard
from core.feats_ru import feats_to_ru
from core import sentiment as _sent_mod
from core.semantics import build_semantic_graph
from core.shop    import (get_purchases, buy_item, get_active_theme,
                          set_active_theme, get_user_balance,
                          UNLOCK_ITEMS, THEME_ITEMS)

# ── Цвета темы ────────────────────────────────────────────────────────────────

CLR = {
    'bg':      '#1E1E2E',
    'panel':   '#2A2A3E',
    'accent':  '#7C5CBF',
    'accent2': '#5C8CBF',
    'text':    '#CDD6F4',
    'text2':   '#A6ADC8',
    'green':   '#A6E3A1',
    'red':     '#F38BA8',
    'yellow':  '#F9E2AF',
    'blue':    '#89B4FA',
    'teal':    '#94E2D5',
    'border':  '#45475A',
    'pos_col': '#A6E3A1',
    'neg_col': '#F38BA8',
    'neu_col': '#F9E2AF',
}

SENT_COLOR = {
    'positive': CLR['green'],
    'negative': CLR['red'],
    'neutral':  CLR['yellow'],
}

POS_PALETTE = [
    '#7C5CBF','#5C8CBF','#A6E3A1','#F38BA8','#F9E2AF',
    '#89B4FA','#94E2D5','#CBA6F7','#FAB387','#A6ADC8',
    '#89DCEB','#B4BEFE',
]

# ── УВЕЛИЧЕННЫЕ ШРИФТЫ ────────────────────────────────────────────────────────
FT_TITLE  = ('Segoe UI', 20, 'bold')
FT_HDR    = ('Segoe UI', 14, 'bold')
FT_SUBHDR = ('Segoe UI', 13, 'bold')
FT_BODY   = ('Segoe UI', 12)
FT_BOLD   = ('Segoe UI', 12, 'bold')
FT_SMALL  = ('Segoe UI', 11)
FT_MINI   = ('Segoe UI', 10)
FT_BIG    = ('Segoe UI', 28, 'bold')


def _btn(parent, text, cmd, width=None, color=None, fg=None):
    kw = dict(text=text, command=cmd,
              bg=color or CLR['accent'], fg=fg or CLR['text'],
              font=FT_BOLD, relief='flat',
              activebackground=CLR['accent2'], activeforeground=CLR['text'],
              cursor='hand2', padx=10, pady=5)
    if width:
        kw['width'] = width
    return tk.Button(parent, **kw)


def _lbl(parent, text, size=12, bold=False, color=None):
    return tk.Label(parent, text=text,
                    bg=CLR['bg'], fg=color or CLR['text'],
                    font=('Segoe UI', size, 'bold' if bold else 'normal'))


def _entry(parent, textvariable=None, width=30):
    kw = dict(bg=CLR['panel'], fg=CLR['text'],
              insertbackground=CLR['text'], relief='flat',
              font=FT_BODY, width=width)
    if textvariable:
        kw['textvariable'] = textvariable
    return tk.Entry(parent, **kw)



class CloseDialog:
    """
    Модальный диалог с тремя кнопками: «Сменить пользователя», «Да», «Отмена».
    Результат в self.result:
      'switch' — сменить пользователя (вернуться в окно авторизации)
      'quit'   — выйти из приложения
      'cancel' — остаться
    """

    def __init__(self, parent):
        self.result = 'cancel'
        self.top = tk.Toplevel(parent)
        self.top.title('Выход')
        self.top.configure(bg=CLR['bg'])
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()

        W, H = 520, 240
        parent.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2 - W // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - H // 2
        self.top.geometry(f'{W}x{H}+{max(px,0)}+{max(py,0)}')

        # Заголовок
        tk.Label(self.top, text='🚪  Закрытие приложения',
                 bg=CLR['bg'], fg=CLR['text'],
                 font=FT_HDR).pack(pady=(18, 4))

        tk.Label(self.top,
                 text='Выберите, что сделать:',
                 bg=CLR['bg'], fg=CLR['text2'],
                 font=FT_BODY).pack(pady=(0, 14))

        btns = tk.Frame(self.top, bg=CLR['bg'])
        btns.pack(pady=4)

        tk.Button(btns, text='🔁 Сменить пользователя',
                  command=self._switch,
                  bg=CLR['accent'], fg=CLR['text'],
                  font=FT_BOLD, relief='flat',
                  activebackground=CLR['accent2'],
                  cursor='hand2', padx=14, pady=8).pack(side='left', padx=6)

        tk.Button(btns, text='✅ Да',
                  command=self._quit,
                  bg='#8C4A4A', fg=CLR['text'],
                  font=FT_BOLD, relief='flat',
                  activebackground='#B05050',
                  cursor='hand2', padx=22, pady=8).pack(side='left', padx=6)

        tk.Button(btns, text='Отмена',
                  command=self._cancel,
                  bg=CLR['border'], fg=CLR['text'],
                  font=FT_BOLD, relief='flat',
                  cursor='hand2', padx=14, pady=8).pack(side='left', padx=6)

        tk.Label(self.top,
                 text='«Сменить пользователя» — вернуться к окну входа\n«Да» — закрыть приложение полностью',
                 bg=CLR['bg'], fg=CLR['text2'],
                 font=FT_SMALL, justify='center').pack(pady=(16, 8))

        self.top.protocol('WM_DELETE_WINDOW', self._cancel)
        self.top.bind('<Escape>', lambda e: self._cancel())
        self.top.wait_window(self.top)

    def _switch(self):
        self.result = 'switch'
        self.top.destroy()

    def _quit(self):
        self.result = 'quit'
        self.top.destroy()

    def _cancel(self):
        self.result = 'cancel'
        self.top.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# Главное окно
# ══════════════════════════════════════════════════════════════════════════════

class Application:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('СинтАналитик — Семантико-синтаксический анализ')
        self.root.geometry('1380x880')
        self.root.configure(bg=CLR['bg'])
        self.root.minsize(1100, 700)

        # state
        self.result: 'AnalysisResult | None' = None
        self.current_user: dict | None = None
        self.current_file   = tk.StringVar(value='Файл не выбран')
        self.status_var     = tk.StringVar(value='Готов')
        self.db_status_var  = tk.StringVar(value='БД: проверяется…')
        self._quiz_questions = []
        self._quiz_idx       = 0
        self._quiz_score     = 0
        self._quiz_streak    = 0
        self._quiz_max_streak = 0
        self._quiz_answered  = False
        self._last_opened_path = ''
        if hasattr(self, '_dev_perf_log'): self._dev_perf_log = []

        self._cheat_btn: tk.Button | None = None
        self._last_opened_path: str = ''
        self._cheat_used_in_question = False

        # Match-вопрос UI — виджеты (заполняются при отрисовке такого вопроса)
        self._match_rows: list = []

        self._unlocks: set = set()
        self._active_theme: str = 'default'

        self.root.withdraw()
        AuthWindow(self.root, self._on_auth_success)

    # ── Auth callback ─────────────────────────────────────────────────────────

    def _on_auth_success(self, user: dict):
        self.current_user = user
        uname = user.get('username', '')
        self._unlocks = get_purchases(uname)
        self._active_theme = get_active_theme(uname)
        from core.shop import THEME_ITEMS as _TI
        if self._active_theme in _TI:
            CLR.update(_TI[self._active_theme]['colors'])
        self._build_ui()
        self.root.configure(bg=CLR['bg'])
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self._check_db_async()
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    # ── UI build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # header
        hdr = tk.Frame(self.root, bg=CLR['accent'], height=62)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text='🔬 СинтАналитик', bg=CLR['accent'],
                 fg='white', font=FT_TITLE).pack(side='left', padx=16)
        if self.current_user:
            uname = self.current_user.get('username', '')
            score = self.current_user.get('total_score', 0)
            self._user_score_var = tk.StringVar(
                value=f'👤 {uname}   🏆 {score} баллов')
            tk.Label(hdr, textvariable=self._user_score_var,
                     bg=CLR['accent'], fg=CLR['yellow'],
                     font=FT_BOLD).pack(side='left', padx=24)
        tk.Label(hdr, textvariable=self.db_status_var, bg=CLR['accent'],
                 fg=CLR['text2'], font=FT_SMALL).pack(side='right', padx=16)

        # toolbar
        tb = tk.Frame(self.root, bg=CLR['panel'], pady=8)
        tb.pack(fill='x')
        _btn(tb, '📂 Загрузить файл', self._open_file).pack(side='left', padx=8)
        _btn(tb, '⚡ Анализировать', self._run_analysis, color='#5C8CBF').pack(side='left', padx=4)
        _btn(tb, '💾 Сохранить в БД', self._save_to_db, color='#4A9C6B').pack(side='left', padx=4)
        self._export_btn = _btn(tb, '📄 Экспорт JSON', self._export_json, color='#6B7A9C')
        self._export_btn.pack(side='left', padx=4)
        tk.Label(tb, textvariable=self.current_file,
                 bg=CLR['panel'], fg=CLR['text2'],
                 font=FT_SMALL, wraplength=500).pack(side='left', padx=12)

        # notebook
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=CLR['bg'], borderwidth=0)
        style.configure('TNotebook.Tab',
                        background=CLR['panel'], foreground=CLR['text2'],
                        font=FT_BODY, padding=[14, 8])
        style.map('TNotebook.Tab',
                  background=[('selected', CLR['accent'])],
                  foreground=[('selected', 'white')])
        style.configure('Treeview',
                        background=CLR['panel'], foreground=CLR['text'],
                        fieldbackground=CLR['panel'], rowheight=26,
                        font=FT_SMALL)
        style.configure('Treeview.Heading',
                        background=CLR['accent'], foreground='white',
                        font=FT_BOLD)
        style.map('Treeview', background=[('selected', CLR['accent2'])])

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill='both', expand=True, padx=6, pady=4)

        self._build_tab_analysis()
        self._build_tab_tokens()
        self._build_tab_entities()
        self._build_tab_sentiment()
        self._build_tab_semantics()
        self._build_tab_quiz()
        self._build_tab_history()
        self._build_tab_shop()
        self._build_tab_help()
        # Dev-only tab: только для пользователя Ibee
        uname = (self.current_user or {}).get('username', '')
        if uname.lower() == 'ibee':
            self._build_tab_devcharts()
        self._apply_locks()

        # status bar
        sb = tk.Frame(self.root, bg=CLR['border'], height=30)
        sb.pack(fill='x', side='bottom')
        tk.Label(sb, textvariable=self.status_var,
                 bg=CLR['border'], fg=CLR['text2'],
                 font=FT_SMALL).pack(side='left', padx=8)

    # ── Tab: Анализ ───────────────────────────────────────────────────────────

    def _build_tab_analysis(self):
        tab = tk.Frame(self.nb, bg=CLR['bg'])
        self.nb.add(tab, text='📊 Анализ')

        left = tk.Frame(tab, bg=CLR['bg'])
        left.pack(side='left', fill='both', expand=True, padx=8, pady=8)
        _lbl(left, 'Исходный текст', bold=True, size=13).pack(anchor='w')
        self.text_input = scrolledtext.ScrolledText(
            left, bg=CLR['panel'], fg=CLR['text'],
            insertbackground=CLR['text'], font=FT_BODY,
            relief='flat', wrap='word')
        self.text_input.pack(fill='both', expand=True, pady=(4, 0))
        bf = tk.Frame(left, bg=CLR['bg'])
        bf.pack(fill='x', pady=4)
        _btn(bf, '🗑 Очистить', self._clear_text, color=CLR['border']).pack(side='left')
        self._word_count_var = tk.StringVar(value='')
        tk.Label(bf, textvariable=self._word_count_var,
                 bg=CLR['bg'], fg=CLR['text2'], font=FT_SMALL).pack(side='right')
        self.text_input.bind('<KeyRelease>', self._update_word_count)

        right = tk.Frame(tab, bg=CLR['bg'], width=480)
        right.pack(side='right', fill='y', padx=(0, 8), pady=8)
        right.pack_propagate(False)
        _lbl(right, 'Статистика', bold=True, size=13).pack(anchor='w')

        stats_frame = tk.Frame(right, bg=CLR['panel'], relief='flat', pady=10, padx=12)
        stats_frame.pack(fill='x', pady=(4, 8))
        self._stat_vars = {}
        for key, label in [
            ('sentence_count', '📝 Предложений:'),
            ('word_count',     '🔤 Слов (без пункт.):'),
            ('char_count',     '🔡 Символов:'),
            ('avg_word_len',   '📏 Средняя длина слова:'),
            ('elapsed_ms',     '⏱ Время анализа (мс):'),
        ]:
            row = tk.Frame(stats_frame, bg=CLR['panel'])
            row.pack(fill='x', pady=3)
            tk.Label(row, text=label, bg=CLR['panel'], fg=CLR['text2'],
                     font=FT_SMALL, width=24, anchor='w').pack(side='left')
            v = tk.StringVar(value='—')
            self._stat_vars[key] = v
            tk.Label(row, textvariable=v, bg=CLR['panel'], fg=CLR['blue'],
                     font=FT_BOLD).pack(side='left')

        _lbl(right, 'Распределение частей речи', bold=True, size=13).pack(anchor='w', pady=(4, 0))
        self._chart_frame = tk.Frame(right, bg=CLR['bg'])
        self._chart_frame.pack(fill='both', expand=True)
        self._chart_canvas = None

    def _update_word_count(self, *_):
        t = self.text_input.get('1.0', 'end').strip()
        n = len(t.split()) if t else 0
        self._word_count_var.set(f'{n} слов')

    def _clear_text(self):
        self.text_input.delete('1.0', 'end')
        self._word_count_var.set('')

    # ── Tab: Токены ───────────────────────────────────────────────────────────

    def _build_tab_tokens(self):
        tab = tk.Frame(self.nb, bg=CLR['bg'])
        self.nb.add(tab, text='🧩 Токены')

        ff = tk.Frame(tab, bg=CLR['bg'])
        ff.pack(fill='x', padx=8, pady=6)
        _lbl(ff, 'Фильтр по POS:').pack(side='left')
        self._pos_filter = tk.StringVar(value='Все')
        pos_opts = ['Все','существительное','глагол','прилагательное','наречие',
                    'местоимение','числительное','предлог','союз','частица','имя собств.']
        ttk.Combobox(ff, textvariable=self._pos_filter, values=pos_opts,
                     width=18, state='readonly', font=FT_SMALL).pack(side='left', padx=4)
        _lbl(ff, '  Поиск слова:').pack(side='left')
        self._tok_search = tk.StringVar()
        _entry(ff, textvariable=self._tok_search, width=18).pack(side='left', padx=4)
        _btn(ff, '🔍 Применить', self._filter_tokens, color=CLR['accent2']).pack(side='left', padx=4)
        _btn(ff, '↺ Сбросить', self._reset_token_filter, color=CLR['border']).pack(side='left')

        sf = tk.Frame(tab, bg=CLR['bg'])
        sf.pack(fill='x', padx=8)
        _lbl(sf, 'Предложение:').pack(side='left')
        self._sent_var = tk.StringVar(value='Все')
        self._sent_combo = ttk.Combobox(sf, textvariable=self._sent_var,
                                        values=['Все'], width=60, state='readonly',
                                        font=FT_SMALL)
        self._sent_combo.pack(side='left', padx=4)
        self._sent_combo.bind('<<ComboboxSelected>>', lambda *_: self._filter_tokens())

        cols = ('word','lemma','pos','dep','head','feats')
        self._tok_tree = ttk.Treeview(tab, columns=cols, show='headings', selectmode='browse')
        for col, h, w in zip(cols,
                             ('Слово','Лемма','Часть речи','Синт. роль','Голова','Признаки'),
                             (130, 130, 170, 190, 90, 280)):
            self._tok_tree.heading(col, text=h)
            self._tok_tree.column(col, width=w, anchor='w')
        sb_y = ttk.Scrollbar(tab, orient='vertical', command=self._tok_tree.yview)
        sb_x = ttk.Scrollbar(tab, orient='horizontal', command=self._tok_tree.xview)
        self._tok_tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        sb_y.pack(side='right', fill='y')
        self._tok_tree.pack(fill='both', expand=True, padx=8, pady=4)
        sb_x.pack(fill='x', padx=8)

    # ── Tab: Сущности ─────────────────────────────────────────────────────────

    def _build_tab_entities(self):
        tab = tk.Frame(self.nb, bg=CLR['bg'])
        self.nb.add(tab, text='🏷 Сущности')

        top = tk.Frame(tab, bg=CLR['bg'])
        top.pack(fill='x', padx=8, pady=8)
        _lbl(top, 'Именованные сущности (NER)', bold=True, size=14).pack(side='left')

        _lbl(top, '  Тип:').pack(side='left', padx=(20, 4))
        self._ner_filter = tk.StringVar(value='Все')
        ttk.Combobox(top, textvariable=self._ner_filter,
                     values=['Все','Персона','Организация','Место','Дата','Деньги'],
                     width=14, state='readonly', font=FT_SMALL).pack(side='left')
        _btn(top, '🔍', lambda: self._show_entities(), color=CLR['accent2']).pack(side='left', padx=4)

        cols = ('text','label_ru','context')
        self._ent_tree = ttk.Treeview(tab, columns=cols, show='headings')
        for col, h, w in zip(cols, ('Текст','Тип','Контекст'), (220, 160, 540)):
            self._ent_tree.heading(col, text=h)
            self._ent_tree.column(col, width=w, anchor='w')
        sb = ttk.Scrollbar(tab, orient='vertical', command=self._ent_tree.yview)
        self._ent_tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._ent_tree.pack(fill='both', expand=True, padx=8)

        self._ner_stats_var = tk.StringVar(value='')
        tk.Label(tab, textvariable=self._ner_stats_var,
                 bg=CLR['bg'], fg=CLR['text2'], font=FT_SMALL).pack(pady=4)

    # ── Tab: Тональность ──────────────────────────────────────────────────────

    def _build_tab_sentiment(self):
        tab = tk.Frame(self.nb, bg=CLR['bg'])
        self.nb.add(tab, text='💬 Тональность')

        left = tk.Frame(tab, bg=CLR['bg'])
        left.pack(side='left', fill='both', expand=True, padx=8, pady=8)

        _lbl(left, 'Общая тональность текста', bold=True, size=14).pack(anchor='w')

        card = tk.Frame(left, bg=CLR['panel'], padx=18, pady=14, relief='flat')
        card.pack(fill='x', pady=8)
        self._sent_label_var = tk.StringVar(value='—')
        self._sent_score_var = tk.StringVar(value='—')
        self._sent_counts_var = tk.StringVar(value='—')
        tk.Label(card, textvariable=self._sent_label_var,
                 bg=CLR['panel'], fg=CLR['yellow'],
                 font=('Segoe UI', 30, 'bold')).pack()
        tk.Label(card, textvariable=self._sent_score_var,
                 bg=CLR['panel'], fg=CLR['text2'], font=FT_SUBHDR).pack()
        tk.Label(card, textvariable=self._sent_counts_var,
                 bg=CLR['panel'], fg=CLR['text2'], font=FT_BODY).pack()

        # Предупреждение если dostoevsky не установлена
        self._sent_engine_warn = tk.Label(left, text='', bg=CLR['bg'],
                                           fg=CLR['yellow'], font=FT_SMALL,
                                           wraplength=700, justify='left')
        self._sent_engine_warn.pack(anchor='w', pady=(0, 4))
        # Показываем статус при построении вкладки
        from core.sentiment import get_error, is_available
        if not is_available():
            err = get_error() or ''
            self._sent_engine_warn.config(
                text='⚠️ dostoevsky недоступна — ' + err.splitlines()[0])

        _lbl(left, 'Тональность по предложениям', bold=True, size=13).pack(anchor='w', pady=(4, 2))
        cols = ('id','text','score','label','top')
        self._sent_tree = ttk.Treeview(left, columns=cols, show='headings', height=12)
        for col, h, w in zip(cols,
                ('#','Предложение','Оценка','Тональность','Dostoevsky (топ)'),
                (40, 430, 80, 140, 130)):
            self._sent_tree.heading(col, text=h)
            self._sent_tree.column(col, width=w, anchor='w')
        sb = ttk.Scrollbar(left, orient='vertical', command=self._sent_tree.yview)
        self._sent_tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._sent_tree.pack(fill='both', expand=True)

        right = tk.Frame(tab, bg=CLR['bg'], width=380)
        right.pack(side='right', fill='y', padx=(0, 8), pady=8)
        right.pack_propagate(False)
        _lbl(right, 'График тональности', bold=True, size=13).pack(anchor='w')
        self._sent_chart_frame = tk.Frame(right, bg=CLR['bg'])
        self._sent_chart_frame.pack(fill='both', expand=True)
        self._sent_chart_canvas = None
    # ── Tab: Семантика ─────────────────────────────────────────────────────────

    def _build_tab_semantics(self):
        tab = tk.Frame(self.nb, bg=CLR['bg'])
        self.nb.add(tab, text='🔗 Семантика')
        self._sem_tab = tab

        # ── Верхняя панель (два ряда) ────────────────────────────────────────
        top_wrap = tk.Frame(tab, bg=CLR['panel'], pady=6, padx=12)
        top_wrap.pack(fill='x')

        # Ряд 1: выбор предложения
        top1 = tk.Frame(top_wrap, bg=CLR['panel'])
        top1.pack(fill='x', pady=(0, 4))
        tk.Label(top1, text='Предложение:', bg=CLR['panel'],
                 fg=CLR['text'], font=FT_BODY).pack(side='left')
        self._sem_sent_var = tk.StringVar(value='— сначала запустите анализ —')
        self._sem_combo = ttk.Combobox(top1, textvariable=self._sem_sent_var,
                                        state='readonly', font=FT_SMALL)
        self._sem_combo.pack(side='left', padx=8, fill='x', expand=True)
        self._sem_combo.bind('<<ComboboxSelected>>', lambda e: self._draw_semantic_graph())

        # Ряд 2: кнопки и опции
        top2 = tk.Frame(top_wrap, bg=CLR['panel'])
        top2.pack(fill='x')
        _btn(top2, '▶ Построить граф', self._draw_semantic_graph,
             color=CLR['accent']).pack(side='left', padx=(0, 4))
        _btn(top2, '💾 Экспорт SVG', self._export_sem_svg,
             color=CLR['accent2']).pack(side='left', padx=4)
        tk.Label(top2, text='   Парсер:', bg=CLR['panel'],
                 fg=CLR['text2'], font=FT_SMALL).pack(side='left')
        self._sem_parser_var = tk.StringVar(value='natasha')
        for _val, _lbl in [('natasha', 'natasha'), ('stanza', 'stanza'),
                            ('groq', 'Groq (Gemma 2)')]:
            tk.Radiobutton(top2, text=_lbl, variable=self._sem_parser_var, value=_val,
                           bg=CLR['panel'], fg=CLR['text'], selectcolor=CLR['bg'],
                           activebackground=CLR['panel'], activeforeground=CLR['text'],
                           font=FT_SMALL,
                           command=self._on_parser_change).pack(side='left', padx=2)

        # Статус ключа (показывается только при выборе Groq)
        self._groq_key_frame = tk.Frame(top2, bg=CLR['panel'])
        from core.llm_semantics import is_api_key_set
        _key_ok  = is_api_key_set()
        _key_txt = '🔑 ключ загружен' if _key_ok else '⚠ GROQ_API_KEY не задан в .env'
        _key_clr = '#A6E3A1'          if _key_ok else '#F38BA8'
        self._groq_key_lbl = tk.Label(self._groq_key_frame, text=_key_txt,
                                      bg=CLR['panel'], fg=_key_clr, font=FT_SMALL)
        self._groq_key_lbl.pack(side='left', padx=(8, 0))

        tk.Label(top2, text='  ', bg=CLR['panel']).pack(side='left')
        self._sem_similarity_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top2, text='Сходство (sentence-transformers)',
                       variable=self._sem_similarity_var,
                       bg=CLR['panel'], fg=CLR['text'], selectcolor=CLR['bg'],
                       activebackground=CLR['panel'], activeforeground=CLR['text'],
                       font=FT_SMALL,
                       command=self._draw_semantic_graph).pack(side='left', padx=(6, 4))

        # ── Строка с полным текстом предложения ──────────────────────────────
        ft_row = tk.Frame(tab, bg=CLR['panel'], padx=12, pady=5)
        ft_row.pack(fill='x')
        tk.Label(ft_row, text='Текст:', bg=CLR['panel'],
                 fg=CLR['text2'], font=FT_SMALL).pack(side='left', padx=(0, 6))
        self._sem_fulltext_var = tk.StringVar(value='— сначала запустите анализ —')
        tk.Label(ft_row, textvariable=self._sem_fulltext_var,
                 bg=CLR['panel'], fg=CLR['text'], font=FT_SMALL,
                 anchor='w', justify='left', wraplength=1100).pack(side='left', fill='x', expand=True)

        # ── Легенда ──────────────────────────────────────────────────────────
        leg = tk.Frame(tab, bg=CLR['bg'], pady=4)
        leg.pack(fill='x', padx=12)
        for label, color in [
            ('Агент',        '#89B4FA'),
            ('Действие',     '#F9E2AF'),
            ('Объект',       '#A6E3A1'),
            ('Получатель',   '#89DCEB'),
            ('Признак',      '#F38BA8'),
            ('Место',        '#94E2D5'),
            ('Время',        '#FAB387'),
            ('Цель',         '#CBA6F7'),
            ('Причина',      '#EBA0AC'),
            ('Образ д.',     '#B4BEFE'),
            ('Принадл.',     '#F5C2E7'),
            ('Обст.',        '#A6ADC8'),
        ]:
            f = tk.Frame(leg, bg=color, padx=6, pady=2)
            f.pack(side='left', padx=4)
            tk.Label(f, text=label, bg=color, fg='#1E1E2E', font=FT_SMALL).pack()
        tk.Label(leg, text=' ✋ Тащите узлы мышью  |  🖱 колёсико = масштаб  |  ПКМ = панорама',
                 bg=CLR['bg'], fg=CLR['text2'], font=FT_SMALL).pack(side='left', padx=12)

        # ── Canvas с прокруткой ───────────────────────────────────────────────
        cf = tk.Frame(tab, bg=CLR['bg'])
        cf.pack(fill='both', expand=True, padx=8, pady=4)
        self._sem_canvas = tk.Canvas(cf, bg=CLR['bg'], highlightthickness=0)
        h_sb = ttk.Scrollbar(cf, orient='horizontal', command=self._sem_canvas.xview)
        v_sb = ttk.Scrollbar(cf, orient='vertical',   command=self._sem_canvas.yview)
        self._sem_canvas.configure(xscrollcommand=h_sb.set, yscrollcommand=v_sb.set)
        h_sb.pack(side='bottom', fill='x')
        v_sb.pack(side='right',  fill='y')
        self._sem_canvas.pack(side='left', fill='both', expand=True)

        # ── Bindings ─────────────────────────────────────────────────────────
        # Масштаб
        self._sem_canvas.bind('<MouseWheel>', self._sem_zoom)
        self._sem_canvas.bind('<Button-4>',   lambda e: self._sem_zoom(e, +1))
        self._sem_canvas.bind('<Button-5>',   lambda e: self._sem_zoom(e, -1))
        # Панорама (средняя кнопка / правая кнопка)
        self._sem_canvas.bind('<ButtonPress-2>',  self._sem_pan_start)
        self._sem_canvas.bind('<B2-Motion>',      self._sem_pan_move)
        self._sem_canvas.bind('<ButtonPress-3>',  self._sem_pan_start)
        self._sem_canvas.bind('<B3-Motion>',      self._sem_pan_move)
        # Drag-to-move узлов (левая кнопка)
        self._sem_canvas.bind('<ButtonPress-1>',  self._sem_drag_start)
        self._sem_canvas.bind('<B1-Motion>',      self._sem_drag_move)
        self._sem_canvas.bind('<ButtonRelease-1>',self._sem_drag_end)

        # ── Состояние ────────────────────────────────────────────────────────
        self._sem_graph           = None
        self._sem_node_items      = {}   # canvas item → SemNode
        self._sem_node_to_items   = {}   # node.id → [canvas item ids]
        self._sem_item_to_node    = {}   # canvas item id → node.id
        self._sem_drag_node_id    = None
        self._sem_drag_node_ids   = []
        self._sem_drag_last_x     = 0
        self._sem_drag_last_y     = 0
        self._sem_sentences_ref   = []
        self._last_analyzed_text  = ''
        self._sem_similarities    = {}

        # Статус
        self._sem_info_var = tk.StringVar(value='')
        tk.Label(tab, textvariable=self._sem_info_var,
                 bg=CLR['bg'], fg=CLR['text2'], font=FT_SMALL,
                 anchor='w').pack(fill='x', padx=12, pady=(0, 4))

    def _populate_semantics_sentences(self, r: AnalysisResult):
        if not hasattr(self, '_sem_combo'):
            return
        self._sem_sentences_ref = r.sentences
        values = [f'[{s.id+1}]  {s.text[:100]}{"…" if len(s.text)>100 else ""}'
                  for s in r.sentences]
        self._sem_combo['values'] = values
        if values:
            self._sem_combo.current(0)
        self._draw_semantic_graph()

    def _toggle_groq_ui(self):
        if getattr(self, '_sem_parser_var', None) and self._sem_parser_var.get() == 'groq':
            self._groq_key_frame.pack(side='left', padx=(6, 0))
        else:
            self._groq_key_frame.pack_forget()

    def _on_parser_change(self):
        self._toggle_groq_ui()
        if self._sem_parser_var.get() != 'groq':
            self._draw_semantic_graph()

    def _draw_semantic_graph(self):
        if not self._sem_sentences_ref:
            return
        idx = self._sem_combo.current()
        if idx < 0:
            return

        parser = (getattr(self, '_sem_parser_var', None) or tk.StringVar(value='natasha')).get()

        # ── Groq (LLM) ───────────────────────────────────────────────────────
        if parser == 'groq':
            from core.llm_semantics import analyze_with_groq, is_groq_available, is_api_key_set
            if not is_groq_available():
                messagebox.showwarning('Groq',
                    'Пакет groq не установлен.\nВыполните: pip install groq')
                return
            if not is_api_key_set():
                messagebox.showwarning('Groq',
                    'GROQ_API_KEY не задан.\n'
                    'Добавьте строку  GROQ_API_KEY=ваш_ключ  в файл .env в корне проекта.')
                return
            sent_text = self._sem_sentences_ref[idx].text
            if hasattr(self, '_sem_fulltext_var'):
                self._sem_fulltext_var.set(sent_text)
            try:
                self._sem_graph = analyze_with_groq(sent_text)
            except Exception as ex:
                messagebox.showerror('Groq', f'Ошибка API:\n{ex}')
                return
            self._sem_similarities = {}
            self._render_graph(self._sem_graph)
            return

        use_stanza = parser == 'stanza'
        if use_stanza:
            from core.stanza_bridge import get_stanza_sentences, is_stanza_available
            if not is_stanza_available():
                messagebox.showwarning('Stanza',
                    'Пакет stanza не установлен.\nВыполните: pip install stanza')
                self._sem_parser_var.set('natasha')
                use_stanza = False
            elif not self._last_analyzed_text:
                use_stanza = False

        if use_stanza:
            try:
                sents = get_stanza_sentences(self._last_analyzed_text)
                sent = sents[idx] if idx < len(sents) else self._sem_sentences_ref[idx]
            except Exception as ex:
                messagebox.showerror('Stanza', f'Ошибка парсинга:\n{ex}')
                return
        else:
            sent = self._sem_sentences_ref[idx]

        if hasattr(self, '_sem_fulltext_var'):
            self._sem_fulltext_var.set(sent.text)
        self._sem_graph = build_semantic_graph(sent)

        use_sim = (getattr(self, '_sem_similarity_var', None) is not None
                   and self._sem_similarity_var.get())
        if use_sim:
            from core.semantic_similarity import compute_similarities, is_sentence_transformers_available
            if is_sentence_transformers_available():
                try:
                    self._sem_similarities = compute_similarities(self._sem_graph)
                except Exception:
                    self._sem_similarities = {}
            else:
                self._sem_similarities = {}
                messagebox.showwarning('Сходство',
                    'Пакет sentence-transformers не установлен.\nВыполните: pip install sentence-transformers')
        else:
            self._sem_similarities = {}

        self._render_graph(self._sem_graph)

    def _render_graph(self, graph):
        c = self._sem_canvas
        c.delete('all')
        self._sem_node_items    = {}
        self._sem_node_to_items = {}
        self._sem_item_to_node  = {}
        self._sem_drag_node_id  = None
        self._sem_drag_node_ids = []

        if not graph.nodes:
            c.create_text(400, 200, justify='center', fill=CLR['text2'], font=FT_BODY,
                          text='Не удалось извлечь семантические роли. Попробуйте другое предложение.')
            return

        NODE_COLORS = {
            'AGENT':        ('#89B4FA', '#1E1E2E'),
            'FORCE':        ('#FF9E64', '#1E1E2E'),
            'PREDICATE':    ('#F9E2AF', '#1E1E2E'),
            'PATIENT':      ('#A6E3A1', '#1E1E2E'),
            'THEME':        ('#94E2D5', '#1E1E2E'),
            'RECIPIENT':    ('#89DCEB', '#1E1E2E'),
            'BENEFICIARY':  ('#CBA6F7', '#1E1E2E'),
            'EXPERIENCER':  ('#D4B8FF', '#1E1E2E'),
            'STIMULUS':     ('#FFE08A', '#1E1E2E'),
            'INSTRUMENT':   ('#E8C99A', '#1E1E2E'),
            'ATTRIBUTE':    ('#F38BA8', '#1E1E2E'),
            'LOCATION':     ('#82D4C8', '#1E1E2E'),
            'SOURCE':       ('#FFA07A', '#1E1E2E'),
            'GOAL':         ('#B5EAD7', '#1E1E2E'),
            'TIME':         ('#FAB387', '#1E1E2E'),
            'PURPOSE':      ('#CBA6F7', '#1E1E2E'),
            'CAUSE':        ('#EBA0AC', '#1E1E2E'),
            'MANNER':       ('#B4BEFE', '#1E1E2E'),
            'COMITATIVE':   ('#9CE8E0', '#1E1E2E'),
            'GENITIVE':     ('#F5C2E7', '#1E1E2E'),
            'CIRCUMSTANCE': ('#A6ADC8', '#1E1E2E'),
            'CONJUNCT':     ('#B4BEFE', '#1E1E2E'),
        }

        positions = self._hierarchical_layout(graph)

        import math

        def _edge_label_pos(p1, p2):
            """Позиция метки ребра — 40% длины от src, смещена перпендикулярно."""
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            dist = max(math.hypot(dx, dy), 1)
            # Точка на 40% пути от src к dst
            mx = p1[0] + dx * 0.40
            my = p1[1] + dy * 0.40
            # Смещение 11px перпендикулярно влево от направления ребра
            mx += (-dy / dist) * 11
            my += ( dx / dist) * 11
            return mx, my

        # Рёбра (рисуем первыми, потом опустим под узлы)
        edge_drawn = set()
        for edge in graph.edges:
            key = (edge.src, edge.dst)
            if key in edge_drawn:
                continue
            edge_drawn.add(key)
            p1 = positions.get(edge.src)
            p2 = positions.get(edge.dst)
            if not p1 or not p2:
                continue
            is_impl = (edge.dep == 'implied')
            c.create_line(p1[0], p1[1], p2[0], p2[1],
                          fill='#6E6E8E' if is_impl else CLR['border'],
                          width=1 if is_impl else 2,
                          arrow='last', arrowshape=(10,12,4),
                          dash=(5, 3) if is_impl else (),
                          smooth=True, tags='sem_edge')
            mx, my = _edge_label_pos(p1, p2)
            c.create_text(mx, my, text=edge.label_ru, fill=CLR['text2'],
                          font=('Segoe UI', 9, 'italic'), tags='sem_edge')

        # Узлы
        NW, NH = 160, 54
        for node in graph.nodes:
            px, py = positions[node.id]
            bg_col, fg_col = NODE_COLORS.get(node.role, ('#45475A','#CDD6F4'))
            x0,y0,x1,y1 = px-NW//2, py-NH//2, px+NW//2, py+NH//2
            # Тень (implied-узлы не имеют тени — они прозрачные/виртуальные)
            if not node.implied:
                shadow_id = c.create_rectangle(x0+3, y0+3, x1+3, y1+3,
                                    fill='#0D0D1A', outline='', tags='node_shadow')
            else:
                shadow_id = c.create_rectangle(x0, y0, x1, y1,
                                    fill='', outline='', tags='node_shadow')
            # Фон: implied-узлы — полупрозрачный, пунктирная рамка
            if node.implied:
                rect_id = c.create_rectangle(x0, y0, x1, y1,
                                              fill=bg_col,
                                              outline=CLR['border'],
                                              width=1,
                                              dash=(5, 3),
                                              tags='node')
            else:
                rect_id = c.create_rectangle(x0, y0, x1, y1,
                                              fill=bg_col,
                                              outline=CLR['border'],
                                              width=2 if node.is_predicate else 1,
                                              tags='node')
            # Роль (мелко, сверху)
            role_lbl = ('подразум.' if node.implied else node.role_ru)
            role_id = c.create_text(px, y0+10, text=role_lbl,
                                     fill='#333344' if fg_col=='#1E1E2E' else CLR['text2'],
                                     font=('Segoe UI', 8), tags='node')
            # Лемма: implied в скобках
            raw = f'[{node.lemma}]' if node.implied else node.lemma
            txt = raw if len(raw) <= 18 else raw[:16]+'…'
            txt_id = c.create_text(px, py+7, text=txt,
                                    fill=fg_col,
                                    font=('Segoe UI', 11, 'bold' if not node.implied else 'italic'),
                                    tags='node')

            # Регистрируем для drag и hover (включая тень, чтобы двигалась вместе)
            node_items = [rect_id, txt_id, role_id, shadow_id]
            self._sem_node_to_items[node.id] = node_items
            for iid in node_items:
                self._sem_node_items[iid]   = node
                self._sem_item_to_node[iid] = node.id
                c.tag_bind(iid, '<Enter>',
                           lambda e, n=node: self._sem_node_hover(n, True))
                c.tag_bind(iid, '<Leave>',
                           lambda e, n=node: self._sem_node_hover(n, False))

        # Рёбра семантического сходства (пунктир поверх фона, под узлами)
        if self._sem_similarities:
            syn_pairs = ({(e.src, e.dst) for e in graph.edges}
                         | {(e.dst, e.src) for e in graph.edges})
            drawn_sim: set = set()
            for (src, dst), score in self._sem_similarities.items():
                if src >= dst:
                    continue
                if (src, dst) in syn_pairs:
                    continue
                if (src, dst) in drawn_sim:
                    continue
                drawn_sim.add((src, dst))
                p1 = positions.get(src)
                p2 = positions.get(dst)
                if not p1 or not p2:
                    continue
                c.create_line(p1[0], p1[1], p2[0], p2[1],
                              fill='#89DCEB', width=1,
                              dash=(4, 6), tags='sim_edge')
                mx = (p1[0] + p2[0]) / 2 + 8
                my = (p1[1] + p2[1]) / 2 - 8
                c.create_text(mx, my, text=f'{score:.2f}',
                              fill='#89DCEB', font=('Segoe UI', 8), tags='sim_edge')

        # Рёбра под узлами
        c.tag_lower('sim_edge')
        c.tag_lower('sem_edge')
        c.tag_lower('node_shadow')

        # Обновляем scrollregion
        c.update_idletasks()
        bbox = c.bbox('all')
        if bbox:
            p = 40
            c.configure(scrollregion=(bbox[0]-p, bbox[1]-p, bbox[2]+p, bbox[3]+p))

        pred = graph.node_by_id(graph.predicate_id)
        self._sem_info_var.set(
            f'Предикат: «{pred.lemma}»  |  Узлов: {len(graph.nodes)}  |  '
            f'Связей: {len(graph.edges)}'
            if pred else '')

    # ── Иерархическая раскладка ───────────────────────────────────────────────

    def _hierarchical_layout(self, graph) -> dict:
        """
        BFS-обход от корня → каждый узел получает уровень (глубину).
        Узлы одного уровня распределяются горизонтально.
        Агент считается дочерним для своего предиката в раскладке
        (семантически он его порождает, визуально — дочерний).
        """
        if not graph.nodes:
            return {}

        # ── Строим родительский словарь (для раскладки) ───────────────────────
        layout_parent: dict = {}          # child_id → parent_id
        node_ids = {n.id for n in graph.nodes}

        for edge in graph.edges:
            if edge.src not in node_ids or edge.dst not in node_ids:
                continue
            src_node = next((n for n in graph.nodes if n.id == edge.src), None)
            if src_node is None:
                continue
            if src_node.role == 'AGENT':
                # AGENT→PREDICATE: в раскладке предикат = родитель агента
                if edge.src not in layout_parent:
                    layout_parent[edge.src] = edge.dst
            else:
                if edge.dst not in layout_parent:
                    layout_parent[edge.dst] = edge.src

        # ── BFS для назначения уровней ────────────────────────────────────────
        layout_roots = [n.id for n in graph.nodes if n.id not in layout_parent]
        if not layout_roots:
            layout_roots = [graph.predicate_id or graph.nodes[0].id]

        levels: dict = {}
        queue = [(r, 0) for r in layout_roots]
        visited: set = set()
        while queue:
            nid, lvl = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            levels[nid] = lvl
            for n in graph.nodes:
                if layout_parent.get(n.id) == nid and n.id not in visited:
                    queue.append((n.id, lvl + 1))

        max_lvl = max(levels.values(), default=0)
        for n in graph.nodes:
            if n.id not in levels:
                levels[n.id] = max_lvl + 1

        # ── Группируем по уровням и сортируем по id (порядок в предложении) ──
        by_level: dict = {}
        for nid, lvl in levels.items():
            by_level.setdefault(lvl, []).append(nid)
        for lvl in by_level:
            by_level[lvl].sort()

        # ── Вычисляем координаты ──────────────────────────────────────────────
        H_GAP   = 215   # горизонтальный шаг между узлами
        V_GAP   = 145   # вертикальный шаг между уровнями
        START_Y = 80
        CENTER_X = 500

        # Ширина самого широкого уровня определяет центрирование
        max_count = max(len(ids) for ids in by_level.values()) if by_level else 1

        positions: dict = {}
        for lvl, nids in by_level.items():
            y = START_Y + lvl * V_GAP
            total_w = len(nids) * H_GAP
            start_x = CENTER_X - total_w // 2 + H_GAP // 2
            for i, nid in enumerate(nids):
                positions[nid] = (start_x + i * H_GAP, y)

        return positions

    # ── Drag-to-move ───────────────────────────────────────────────────────────

    def _sem_drag_start(self, event):
        c = self._sem_canvas
        cx, cy = c.canvasx(event.x), c.canvasy(event.y)
        items = c.find_overlapping(cx-3, cy-3, cx+3, cy+3)
        hit = None
        for item in reversed(items):
            nid = self._sem_item_to_node.get(item)
            if nid is not None:
                hit = nid
                break
        self._sem_drag_node_id  = hit
        self._sem_drag_node_ids = self._sem_node_to_items.get(hit, []) if hit else []
        self._sem_drag_last_x   = cx
        self._sem_drag_last_y   = cy

    def _sem_drag_move(self, event):
        if self._sem_drag_node_id is None:
            return
        c = self._sem_canvas
        cx, cy = c.canvasx(event.x), c.canvasy(event.y)
        dx, dy = cx - self._sem_drag_last_x, cy - self._sem_drag_last_y
        for iid in self._sem_drag_node_ids:
            c.move(iid, dx, dy)
        self._sem_drag_last_x, self._sem_drag_last_y = cx, cy
        self._sem_redraw_edges()

    def _sem_drag_end(self, event):
        self._sem_drag_node_id  = None
        self._sem_drag_node_ids = []
        bbox = self._sem_canvas.bbox('all')
        if bbox:
            p = 40
            self._sem_canvas.configure(
                scrollregion=(bbox[0]-p, bbox[1]-p, bbox[2]+p, bbox[3]+p))

    def _sem_redraw_edges(self):
        import math
        if not self._sem_graph:
            return
        c = self._sem_canvas
        c.delete('sem_edge')
        c.delete('sim_edge')
        centers = {}
        for nid, items in self._sem_node_to_items.items():
            if not items:
                continue
            try:
                bb = c.bbox(items[0])
                if bb:
                    centers[nid] = ((bb[0]+bb[2])/2, (bb[1]+bb[3])/2)
            except Exception:
                pass
        edge_drawn = set()
        for edge in self._sem_graph.edges:
            key = (edge.src, edge.dst)
            if key in edge_drawn:
                continue
            edge_drawn.add(key)
            p1 = centers.get(edge.src)
            p2 = centers.get(edge.dst)
            if not p1 or not p2:
                continue
            is_impl = (edge.dep == 'implied')
            c.create_line(p1[0], p1[1], p2[0], p2[1],
                          fill='#6E6E8E' if is_impl else CLR['border'],
                          width=1 if is_impl else 2,
                          arrow='last', arrowshape=(10,12,4),
                          dash=(5, 3) if is_impl else (),
                          smooth=True, tags='sem_edge')
            dx, dy = p2[0]-p1[0], p2[1]-p1[1]
            dist = max(math.hypot(dx, dy), 1)
            mx = p1[0] + dx*0.40 + (-dy/dist)*11
            my = p1[1] + dy*0.40 + ( dx/dist)*11
            c.create_text(mx, my, text=edge.label_ru, fill=CLR['text2'],
                          font=('Segoe UI', 9, 'italic'), tags='sem_edge')

        if self._sem_similarities:
            syn_pairs = ({(e.src, e.dst) for e in self._sem_graph.edges}
                         | {(e.dst, e.src) for e in self._sem_graph.edges})
            drawn_sim: set = set()
            for (src, dst), score in self._sem_similarities.items():
                if src >= dst:
                    continue
                if (src, dst) in syn_pairs:
                    continue
                if (src, dst) in drawn_sim:
                    continue
                drawn_sim.add((src, dst))
                p1 = centers.get(src)
                p2 = centers.get(dst)
                if not p1 or not p2:
                    continue
                c.create_line(p1[0], p1[1], p2[0], p2[1],
                              fill='#89DCEB', width=1,
                              dash=(4, 6), tags='sim_edge')
                mx = (p1[0] + p2[0]) / 2 + 8
                my = (p1[1] + p2[1]) / 2 - 8
                c.create_text(mx, my, text=f'{score:.2f}',
                              fill='#89DCEB', font=('Segoe UI', 8), tags='sim_edge')

        c.tag_lower('sim_edge')
        c.tag_lower('sem_edge')

    # ── Zoom / Pan ────────────────────────────────────────────────────────────

    def _sem_pan_start(self, event):
        self._sem_canvas.scan_mark(event.x, event.y)

    def _sem_pan_move(self, event):
        self._sem_canvas.scan_dragto(event.x, event.y, gain=1)

    def _sem_zoom(self, event, delta=None):
        if delta is None:
            delta = 1 if event.delta > 0 else -1
        f = 1.1 if delta > 0 else 0.9
        cx = self._sem_canvas.winfo_width()  / 2
        cy = self._sem_canvas.winfo_height() / 2
        self._sem_canvas.scale('all', cx, cy, f, f)
        self._sem_canvas.configure(scrollregion=self._sem_canvas.bbox('all'))

    # ── Hover / Click ─────────────────────────────────────────────────────────

    def _sem_node_hover(self, node, entering: bool):
        if entering:
            info = (f'[{node.role_ru}]  {node.word}  →  лемма: «{node.lemma}»  '
                    f'(ЧР: {node.pos})')
            if self._sem_similarities and self._sem_graph:
                pred_id = self._sem_graph.predicate_id
                if pred_id is not None and node.id != pred_id:
                    sim = (self._sem_similarities.get((node.id, pred_id))
                           or self._sem_similarities.get((pred_id, node.id)))
                    if sim:
                        info += f'  |  близость к предикату: {sim:.2f}'
            self._sem_info_var.set(info)
        else:
            pred = self._sem_graph.node_by_id(self._sem_graph.predicate_id) \
                if self._sem_graph else None
            self._sem_info_var.set(
                f'Предикат: «{pred.lemma}»  |  '
                f'Узлов: {len(self._sem_graph.nodes)}  |  '
                f'Связей: {len(self._sem_graph.edges)}'
                if pred else '')

    # ── SVG export ────────────────────────────────────────────────────────────

    def _export_sem_svg(self):
        if not self._sem_graph or not self._sem_graph.nodes:
            messagebox.showwarning('Экспорт', 'Сначала постройте граф.')
            return
        from tkinter.filedialog import asksaveasfilename
        path = asksaveasfilename(
            defaultextension='.svg',
            filetypes=[('SVG файл', '*.svg')],
            title='Сохранить граф как SVG')
        if not path:
            return
        self._write_sem_svg(path)
        messagebox.showinfo('Экспорт', f'SVG сохранён:\n{path}')

    def _write_sem_svg(self, path: str):
        import math
        graph = self._sem_graph
        W, H  = 1000, 700
        NODE_COLORS = {
            'AGENT':        '#89B4FA',
            'FORCE':        '#FF9E64',
            'PREDICATE':    '#F9E2AF',
            'PATIENT':      '#A6E3A1',
            'THEME':        '#94E2D5',
            'RECIPIENT':    '#89DCEB',
            'BENEFICIARY':  '#CBA6F7',
            'EXPERIENCER':  '#D4B8FF',
            'STIMULUS':     '#FFE08A',
            'INSTRUMENT':   '#E8C99A',
            'ATTRIBUTE':    '#F38BA8',
            'LOCATION':     '#82D4C8',
            'SOURCE':       '#FFA07A',
            'GOAL':         '#B5EAD7',
            'TIME':         '#FAB387',
            'PURPOSE':      '#CBA6F7',
            'CAUSE':        '#EBA0AC',
            'MANNER':       '#B4BEFE',
            'COMITATIVE':   '#9CE8E0',
            'GENITIVE':     '#F5C2E7',
            'CIRCUMSTANCE': '#A6ADC8',
            'CONJUNCT':     '#B4BEFE',
        }
        CX, CY, R = W//2, H//2, min(W,H)//3
        positions = {}
        pred = graph.node_by_id(graph.predicate_id)
        if pred:
            positions[pred.id] = (CX, CY)
        others = [n for n in graph.nodes if not n.is_predicate]
        for i, n in enumerate(others):
            a = 2*math.pi*i/max(len(others),1) - math.pi/2
            positions[n.id] = (CX+R*math.cos(a), CY+R*math.sin(a))

        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
            f'<rect width="{W}" height="{H}" fill="{CLR["bg"]}"/>',
            '<defs><marker id="arr" markerWidth="10" markerHeight="7" '
            'refX="9" refY="3.5" orient="auto">'
            '<polygon points="0 0,10 3.5,0 7" fill="#6C7086"/></marker></defs>',
        ]
        drawn = set()
        for e in graph.edges:
            if (e.src, e.dst) in drawn:
                continue
            drawn.add((e.src, e.dst))
            p1 = positions.get(e.src)
            p2 = positions.get(e.dst)
            if not p1 or not p2:
                continue
            lines.append(
                f'<line x1="{p1[0]:.0f}" y1="{p1[1]:.0f}" '
                f'x2="{p2[0]:.0f}" y2="{p2[1]:.0f}" '
                f'stroke="#6C7086" stroke-width="2" marker-end="url(#arr)"/>')
            lines.append(
                f'<text x="{(p1[0]+p2[0])/2:.0f}" y="{(p1[1]+p2[1])/2-12:.0f}" '
                f'text-anchor="middle" fill="{CLR["text2"]}" '
                f'font-family="Segoe UI" font-size="11" '
                f'font-style="italic">{e.label_ru}</text>')
        NW, NH = 160, 54
        for n in graph.nodes:
            px, py = positions.get(n.id, (0, 0))
            bg = NODE_COLORS.get(n.role, '#45475A')
            lines.append(
                f'<rect x="{px-NW//2}" y="{py-NH//2}" '
                f'width="{NW}" height="{NH}" rx="6" '
                f'fill="{bg}" stroke="#45475A" stroke-width="1.5"/>')
            lines.append(
                f'<text x="{px:.0f}" y="{py-8:.0f}" text-anchor="middle" '
                f'fill="#666" font-family="Segoe UI" font-size="9">{n.role_ru}</text>')
            lines.append(
                f'<text x="{px:.0f}" y="{py+14:.0f}" text-anchor="middle" '
                f'fill="#1E1E2E" font-family="Segoe UI" '
                f'font-size="13" font-weight="bold">{n.lemma[:18]}</text>')
        lines.append('</svg>')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))


    # ── Tab: Тест ─────────────────────────────────────────────────────────────

    def _build_tab_quiz(self):
        tab = tk.Frame(self.nb, bg=CLR['bg'])
        self.nb.add(tab, text='🎮 Тест')

        # top bar
        tb = tk.Frame(tab, bg=CLR['bg'])
        tb.pack(fill='x', padx=12, pady=8)
        _lbl(tb, 'Тест по результатам анализа', bold=True, size=15).pack(side='left')
        self._quiz_progress_var = tk.StringVar(value='')
        tk.Label(tb, textvariable=self._quiz_progress_var,
                 bg=CLR['bg'], fg=CLR['blue'], font=FT_HDR).pack(side='right')

        # score/combo bar
        score_bar = tk.Frame(tab, bg=CLR['bg'])
        score_bar.pack(fill='x', padx=20)
        self._quiz_score_var = tk.StringVar(value='Очки: 0')
        tk.Label(score_bar, textvariable=self._quiz_score_var,
                 bg=CLR['bg'], fg=CLR['yellow'],
                 font=('Segoe UI', 15, 'bold')).pack(side='left')
        self._quiz_combo_var = tk.StringVar(value='')
        tk.Label(score_bar, textvariable=self._quiz_combo_var,
                 bg=CLR['bg'], fg=CLR['green'],
                 font=FT_HDR).pack(side='right')

        # question
        self._quiz_q_frame = tk.Frame(tab, bg=CLR['panel'],
                                      padx=22, pady=18, relief='flat')
        self._quiz_q_frame.pack(fill='x', padx=20, pady=8)
        self._quiz_q_var = tk.StringVar(value='Загрузите текст и запустите анализ для начала теста.')
        tk.Label(self._quiz_q_frame, textvariable=self._quiz_q_var,
                 bg=CLR['panel'], fg=CLR['text'],
                 font=('Segoe UI', 14), wraplength=980,
                 justify='left', anchor='w').pack(fill='x')

        # sentence context
        self._quiz_ctx_var = tk.StringVar(value='')
        self._quiz_word_var = tk.StringVar(value='')
        ctx_frame = tk.Frame(tab, bg=CLR['panel'], padx=16, pady=8)
        ctx_frame.pack(fill='x', padx=20, pady=(0, 4))
        tk.Label(ctx_frame, text='📖 Контекст предложения:',
                 bg=CLR['panel'], fg=CLR['text2'],
                 font=FT_MINI).pack(anchor='w')
        self._quiz_ctx_text = tk.Text(ctx_frame, height=3,
                 bg=CLR['panel'], fg=CLR['blue'],
                 font=('Segoe UI', 11, 'italic'),
                 relief='flat', wrap='word', state='disabled',
                 highlightthickness=0)
        self._quiz_ctx_text.pack(fill='x', pady=(2, 0))
        self._quiz_ctx_text.tag_configure('highlight',
            foreground='#FFD700', font=('Segoe UI', 11, 'bold italic'),
            background='#3A3A00')

        # hint
        self._quiz_hint_var = tk.StringVar(value='')
        tk.Label(tab, textvariable=self._quiz_hint_var,
                 bg=CLR['bg'], fg=CLR['text2'],
                 font=('Segoe UI', 11, 'italic')).pack()

        # ── Зона ответов ─────────────────────────────────────────────
        # Обычные вопросы используют self._opt_frame с 4 кнопками.
        # Match-вопросы используют self._match_frame.
        self._answers_area = tk.Frame(tab, bg=CLR['bg'])
        self._answers_area.pack(pady=8, fill='x', padx=24)

        # Кадр с обычными вариантами (4 кнопки)
        self._opt_frame = tk.Frame(self._answers_area, bg=CLR['bg'])
        self._opt_frame.pack(fill='x')
        # Настраиваем сетку кадра ответов: два столбца равной ширины
        self._opt_frame.grid_columnconfigure(0, weight=1, uniform='opt')
        self._opt_frame.grid_columnconfigure(1, weight=1, uniform='opt')
        self._quiz_opt_btns = []
        self._quiz_opt_vars = []
        for i in range(4):
            v = tk.StringVar(value=f'Вариант {i+1}')
            self._quiz_opt_vars.append(v)
            btn = tk.Button(self._opt_frame, textvariable=v,
                            command=lambda i=i: self._quiz_answer(i),
                            bg=CLR['panel'], fg=CLR['text'],
                            font=FT_BODY, relief='flat',
                            activebackground=CLR['accent2'], activeforeground='white',
                            cursor='hand2', pady=10, anchor='w',
                            wraplength=440, padx=14)
            btn.grid(row=i//2, column=i%2, padx=12, pady=6, sticky='nsew')
            self._quiz_opt_btns.append(btn)

        self._match_frame = tk.Frame(self._answers_area, bg=CLR['bg'])

        # explanation
        self._quiz_expl_var = tk.StringVar(value='')
        self._quiz_expl_lbl = tk.Label(tab, textvariable=self._quiz_expl_var,
                                       bg=CLR['bg'], fg=CLR['text'],
                                       font=FT_BODY, wraplength=980)
        self._quiz_expl_lbl.pack(pady=4)

        # nav buttons
        nav = tk.Frame(tab, bg=CLR['bg'])
        nav.pack(pady=10)
        _btn(nav, '▶ Следующий вопрос', self._quiz_next, color=CLR['accent']).pack(side='left', padx=8)
        _btn(nav, '✓ Проверить (сопост.)', self._quiz_submit_match, color=CLR['accent2']).pack(side='left', padx=8)
        _btn(nav, '🔄 Новый тест', self._quiz_start, color='#4A9C6B').pack(side='left', padx=8)

        # final score
        self._quiz_final_var = tk.StringVar(value='')
        tk.Label(tab, textvariable=self._quiz_final_var,
                 bg=CLR['bg'], fg=CLR['green'],
                 font=FT_HDR).pack(pady=6)

    # ── Tab: История ──────────────────────────────────────────────────────────

    def _build_tab_history(self):
        tab = tk.Frame(self.nb, bg=CLR['bg'])
        self.nb.add(tab, text='🗂 История')

        tb = tk.Frame(tab, bg=CLR['bg'])
        tb.pack(fill='x', padx=8, pady=6)
        _btn(tb, '🔄 Обновить', self._load_history, color=CLR['accent2']).pack(side='left')
        _lbl(tb, '  Поиск:').pack(side='left', padx=(12, 4))
        self._hist_search = tk.StringVar()
        _entry(tb, textvariable=self._hist_search, width=22).pack(side='left')
        _btn(tb, '🔍', self._search_history, color=CLR['accent']).pack(side='left', padx=4)
        _btn(tb, '✏️ Переименовать', self._rename_history, color='#6B7A9C').pack(side='left', padx=8)
        _btn(tb, '📝 Заметка', self._edit_notes, color='#6B7A9C').pack(side='left', padx=4)
        _btn(tb, '🗑 Удалить', self._delete_history, color='#8C4A4A').pack(side='left', padx=4)
        _btn(tb, '📂 Загрузить', self._load_from_history, color='#4A9C6B').pack(side='left', padx=4)

        cols = ('id','date','name','sents','words','sentiment','score','notes')
        self._hist_tree = ttk.Treeview(tab, columns=cols, show='headings')
        for col, h, w in zip(cols,
                             ('ID','Дата','Название','Пред.','Слов','Тональность','Оценка','Заметка'),
                             (50, 160, 260, 70, 70, 120, 80, 270)):
            self._hist_tree.heading(col, text=h)
            self._hist_tree.column(col, width=w, anchor='w')
        sb = ttk.Scrollbar(tab, orient='vertical', command=self._hist_tree.yview)
        self._hist_tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._hist_tree.pack(fill='both', expand=True, padx=8)

    # ── Tab: Графики ───────────────────────────────────────

    def _build_tab_devcharts(self):
        """Вкладка разработчика: графики производительности.
        Отображается только если current_user.username == 'Ibee' (case-insensitive).
        """
        tab = tk.Frame(self.nb, bg=CLR['bg'])
        self.nb.add(tab, text='📈 Графики')
        self._dev_tab = tab

        # Заголовок
        hdr = tk.Frame(tab, bg=CLR['panel'], pady=10)
        hdr.pack(fill='x', padx=8, pady=(8, 0))
        tk.Label(hdr, text='📈  Графики производительности  [Dev Only]',
                 bg=CLR['panel'], fg=CLR['accent'],
                 font=FT_HDR).pack(side='left', padx=12)
        tk.Label(hdr, text='Обновляется при каждом анализе',
                 bg=CLR['panel'], fg=CLR['text2'],
                 font=FT_SMALL).pack(side='right', padx=12)

        # Scrollable canvas для графиков
        canvas_outer = tk.Canvas(tab, bg=CLR['bg'], highlightthickness=0)
        sb_dev = ttk.Scrollbar(tab, orient='vertical', command=canvas_outer.yview)
        canvas_outer.configure(yscrollcommand=sb_dev.set)
        sb_dev.pack(side='right', fill='y', pady=4)
        canvas_outer.pack(side='left', fill='both', expand=True, padx=(8,0), pady=4)
        inner = tk.Frame(canvas_outer, bg=CLR['bg'])
        wid = canvas_outer.create_window((0,0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas_outer.configure(
            scrollregion=canvas_outer.bbox('all')))
        canvas_outer.bind('<Configure>', lambda e: canvas_outer.itemconfig(wid, width=e.width))

        def _mw(ev):
            if ev.num == 4: canvas_outer.yview_scroll(-1, 'units')
            elif ev.num == 5: canvas_outer.yview_scroll(1, 'units')
            else: canvas_outer.yview_scroll(int(-1*(ev.delta/120)), 'units')
        canvas_outer.bind('<MouseWheel>', _mw)
        canvas_outer.bind('<Button-4>', _mw)
        canvas_outer.bind('<Button-5>', _mw)

        self._dev_inner = inner
        self._dev_canvas_outer = canvas_outer
        self._dev_perf_log = []          # [(label, elapsed_ms, word_count, file_size_kb)]

        # Placeholder при отсутствии данных
        self._dev_placeholder = tk.Label(
            inner,
            text='Запустите анализ хотя бы одного текста — здесь появятся графики.',
            bg=CLR['bg'], fg=CLR['text2'], font=FT_BODY)
        self._dev_placeholder.pack(pady=40)

    def _dev_log_analysis(self, label: str, elapsed_ms: float,
                           word_count: int, file_size_kb: float = 0.0):
        """Вызывается после каждого анализа; обновляет графики."""
        if not hasattr(self, '_dev_perf_log'):
            return
        self._dev_perf_log.append((label, elapsed_ms, word_count, file_size_kb))
        self._dev_redraw_charts()

    def _dev_redraw_charts(self):
        """Перерисовывает все графики на вкладке разработчика."""
        import matplotlib.pyplot as _plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as _FCA

        inner = self._dev_inner
        for w in inner.winfo_children():
            try: w.destroy()
            except Exception: pass

        log = self._dev_perf_log
        if not log:
            lbl = tk.Label(inner,
                text='Нет данных. Запустите анализ.',
                bg=CLR['bg'], fg=CLR['text2'], font=FT_BODY)
            lbl.pack(pady=40)
            return

        labels     = [str(i+1) for i in range(len(log))]
        elapsed    = [e for _, e, _, _ in log]
        words      = [w for _, _, w, _ in log]
        filesizes  = [s for _, _, _, s in log]
        names      = [n[:18]+'…' if len(n)>18 else n for n, *_ in log]

        bg_c  = CLR['bg']
        pan_c = CLR['panel']
        acc_c = CLR['accent']
        txt_c = CLR['text']
        txt2  = CLR['text2']

        def make_fig(title, xlabel, ylabel, xs, ys, color, bar=False):
            fig, ax = _plt.subplots(figsize=(8, 2.8), facecolor=bg_c)
            ax.set_facecolor(pan_c)
            if bar:
                ax.bar(xs, ys, color=color, edgecolor='none', alpha=0.85)
            else:
                ax.plot(xs, ys, color=color, marker='o', linewidth=2, markersize=6)
                ax.fill_between(xs, ys, alpha=0.15, color=color)
            ax.set_title(title, color=txt_c, fontsize=11, pad=8)
            ax.set_xlabel(xlabel, color=txt2, fontsize=9)
            ax.set_ylabel(ylabel, color=txt2, fontsize=9)
            ax.tick_params(colors=txt2, labelsize=8)
            for spine in ax.spines.values():
                spine.set_color(CLR['border'])
            if len(xs) > 1:
                ax.set_xticks(range(len(xs)))
                ax.set_xticklabels(xs, rotation=20, ha='right', fontsize=8, color=txt2)
            _plt.tight_layout()
            return fig

        charts = [
            ('Время анализа (мс)',       'Запуск №', 'мс',
             labels, elapsed, '#CBA6F7', False),
            ('Слов в тексте',            'Запуск №', 'слов',
             labels, words,   CLR['blue'],  True),
            ('Скорость обработки (сл/с)', 'Запуск №', 'слов/с',
             labels,
             [round(w / (e/1000), 1) if e > 0 else 0 for e, w in zip(elapsed, words)],
             CLR['green'], False),
        ]
        # Добавляем график размера файла только если хотя бы одно ненулевое значение
        if any(s > 0 for s in filesizes):
            charts.append((
                'Размер файла (КБ)', 'Запуск №', 'КБ',
                labels, filesizes, CLR['yellow'], True
            ))

        for title, xl, yl, xs, ys, col, bar in charts:
            fig = make_fig(title, xl, yl, xs, ys, col, bar)
            fc  = _FCA(fig, inner)
            fc.draw()
            fc.get_tk_widget().pack(fill='x', padx=12, pady=6)
            _plt.close(fig)

        # Сводная таблица
        tk.Label(inner, text='📋  История запусков',
                 bg=CLR['bg'], fg=acc_c, font=FT_HDR).pack(anchor='w', padx=12, pady=(10,4))
        cols = ('n','name','elapsed','words','speed','size')
        tree = ttk.Treeview(inner, columns=cols, show='headings', height=min(len(log), 8))
        for col_, hdr_, w_ in zip(cols,
                ('№','Файл','Время (мс)','Слов','Скорость сл/с','Размер КБ'),
                (40, 200, 90, 70, 110, 80)):
            tree.heading(col_, text=hdr_)
            tree.column(col_, width=w_, anchor='center')
        for i, (name, e, w, s) in enumerate(log, 1):
            speed = round(w/(e/1000), 1) if e > 0 else '—'
            size  = f'{s:.1f}' if s > 0 else '—'
            tree.insert('', 'end', values=(i, name[:30], f'{e:.1f}', w, speed, size))
        tree.pack(fill='x', padx=12, pady=(0,12))

        # Обновляем scrollregion
        inner.update_idletasks()
        self._dev_canvas_outer.configure(
            scrollregion=self._dev_canvas_outer.bbox('all'))

    # ── Tab: Помощь ───────────────────────────────────────────────────────────

    def _build_tab_help(self):
        tab = tk.Frame(self.nb, bg=CLR['bg'])
        self.nb.add(tab, text='❓ Помощь')

        txt = scrolledtext.ScrolledText(
            tab, bg=CLR['panel'], fg=CLR['text'],
            font=FT_BODY, relief='flat', wrap='word',
            state='normal', padx=16, pady=12)
        txt.pack(fill='both', expand=True, padx=8, pady=8)
        txt.insert('1.0', HELP_TEXT)
        txt.configure(state='disabled')

    # ── Actions ───────────────────────────────────────────────────────────────

    def _open_file(self):
        path = filedialog.askopenfilename(
            title='Открыть файл',
            filetypes=[
                ('Поддерживаемые форматы', '*.doc *.docx *.txt *.pdf *.rtf *.html *.htm'),
                ('Word документы', '*.doc *.docx'),
                ('Текстовые файлы', '*.txt'),
                ('PDF', '*.pdf'),
                ('Все файлы', '*.*'),
            ]
        )
        if not path:
            return
        try:
            self.status_var.set('Загрузка файла…')
            self.root.update()
            text = load_file(path)
            self.text_input.delete('1.0', 'end')
            self.text_input.insert('1.0', text)
            self.current_file.set(f'📄 {Path(path).name}  ({len(text)} симв.)')
            self._last_opened_path = path
            self._update_word_count()
            self.status_var.set(f'Файл загружен: {Path(path).name}')
        except Exception as e:
            messagebox.showerror('Ошибка', str(e))
            self.status_var.set('Ошибка загрузки файла')

    def _run_analysis(self):
        text = self.text_input.get('1.0', 'end').strip()
        self._last_analyzed_text = text
        if not text:
            messagebox.showwarning('Предупреждение', 'Введите или загрузите текст для анализа.')
            return
        self.status_var.set('Анализ… (может занять несколько секунд)')
        self.root.update()

        def worker():
            try:
                analyzer = get_analyzer()
                result   = analyzer.analyze(text)
                self.result = result
                self.root.after(0, lambda: self._show_results(result))
            except Exception as e:
                err_msg = str(e)
                self.root.after(0, lambda m=err_msg: (
                    messagebox.showerror('Ошибка анализа', m),
                    self.status_var.set('Ошибка анализа'),
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _show_results(self, r: AnalysisResult):
        self._show_stats(r)
        self._show_pos_chart(r)
        self._show_tokens(r)
        self._show_entities()
        self._show_sentiment(r)
        self._populate_semantics_sentences(r)
        self.status_var.set(
            f'Анализ завершён за {r.elapsed_ms} мс  |  '
            f'{r.stats["sentence_count"]} предл., {r.stats["word_count"]} слов'
        )
        self.nb.select(0)
        # Логируем производительность для вкладки разработчика
        import os as _os
        file_label = self.current_file.get().replace('📄 ', '').split('  (')[0] or 'текст'
        # Пробуем получить размер файла (если путь сохранён)
        fsize_kb = 0.0
        if hasattr(self, '_last_opened_path') and self._last_opened_path:
            try:
                fsize_kb = _os.path.getsize(self._last_opened_path) / 1024
            except Exception:
                pass
        self._dev_log_analysis(file_label, r.elapsed_ms, r.stats['word_count'], fsize_kb)

    def _show_stats(self, r: AnalysisResult):
        s = r.stats
        self._stat_vars['sentence_count'].set(str(s['sentence_count']))
        self._stat_vars['word_count'].set(str(s['word_count']))
        self._stat_vars['char_count'].set(str(s['char_count']))
        self._stat_vars['avg_word_len'].set(str(s['avg_word_len']))
        self._stat_vars['elapsed_ms'].set(str(r.elapsed_ms))

    def _show_pos_chart(self, r: AnalysisResult):
        for w in self._chart_frame.winfo_children():
            w.destroy()
        data = r.stats['pos_distribution'][:10]
        if not data:
            return
        labels, vals = zip(*data)
        fig, ax = plt.subplots(figsize=(4.4, 3.6), facecolor=CLR['bg'])
        ax.set_facecolor(CLR['bg'])
        wedges, texts, auto = ax.pie(
            vals, labels=None, autopct='%1.0f%%',
            colors=POS_PALETTE[:len(vals)],
            startangle=140, pctdistance=0.78,
            wedgeprops={'linewidth': 1, 'edgecolor': CLR['bg']},
        )
        for t in auto:
            t.set_color('white'); t.set_fontsize(8)
        patches = [mpatches.Patch(color=POS_PALETTE[i], label=f'{labels[i]} ({vals[i]})')
                   for i in range(len(labels))]
        ax.legend(handles=patches, loc='lower center', bbox_to_anchor=(0.5, -0.32),
                  ncol=2, fontsize=8, frameon=False,
                  labelcolor=CLR['text'], facecolor=CLR['bg'])
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, self._chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
        self._chart_canvas = canvas
        plt.close(fig)

    def _show_tokens(self, r: AnalysisResult):
        self._tok_tree.delete(*self._tok_tree.get_children())
        sent_opts = ['Все'] + [
            f'{s.id}: {s.text[:55]}…' if len(s.text) > 55 else f'{s.id}: {s.text}'
            for s in r.sentences
        ]
        self._sent_combo['values'] = sent_opts
        self._sent_var.set('Все')
        self._populate_tokens(r.sentences)

    def _populate_tokens(self, sentences, pos_f=None, search_f=None, sent_f=None):
        self._tok_tree.delete(*self._tok_tree.get_children())
        row_colors = {
            'существительное': CLR['blue'],
            'глагол': CLR['green'],
            'прилагательное': CLR['teal'],
            'наречие': CLR['yellow'],
            'имя собств.': '#CBA6F7',
        }
        cnt = 0
        for s in sentences:
            if sent_f is not None and s.id != sent_f:
                continue
            for t in s.tokens:
                if pos_f and pos_f != 'Все' and t.pos_ru != pos_f:
                    continue
                if search_f and search_f.lower() not in t.word.lower() and search_f.lower() not in t.lemma.lower():
                    continue
                feats_str = feats_to_ru(t.feats) if t.feats else ''
                iid = self._tok_tree.insert(
                    '', 'end',
                    values=(t.word, t.lemma, t.pos_ru, t.dep_ru, t.head_id, feats_str),
                    tags=(t.pos_ru,)
                )
                color = row_colors.get(t.pos_ru, CLR['text'])
                self._tok_tree.tag_configure(t.pos_ru, foreground=color)
                cnt += 1
        self.status_var.set(f'Отображено токенов: {cnt}')

    def _filter_tokens(self):
        if not self.result:
            return
        pos_f  = self._pos_filter.get()
        search = self._tok_search.get().strip()
        sent_s = self._sent_var.get()
        sent_f = None
        if sent_s != 'Все':
            try:
                sent_f = int(sent_s.split(':')[0])
            except Exception:
                pass
        self._populate_tokens(self.result.sentences, pos_f or None, search or None, sent_f)

    def _reset_token_filter(self):
        self._pos_filter.set('Все')
        self._tok_search.set('')
        self._sent_var.set('Все')
        if self.result:
            self._populate_tokens(self.result.sentences)

    def _show_entities(self):
        if not self.result:
            return
        self._ent_tree.delete(*self._ent_tree.get_children())
        filt = self._ner_filter.get()
        src  = self.text_input.get('1.0', 'end')
        ents = self.result.entities
        if filt != 'Все':
            ents = [e for e in ents if e.label_ru == filt]
        cnt: dict = {}
        for e in ents:
            ctx_start = max(0, e.start - 30)
            ctx_end   = min(len(src), e.stop + 30)
            ctx = '…' + src[ctx_start:ctx_end].replace('\n', ' ') + '…'
            self._ent_tree.insert('', 'end', values=(e.text, e.label_ru, ctx))
            cnt[e.label_ru] = cnt.get(e.label_ru, 0) + 1
        stats = '  |  '.join(f'{k}: {v}' for k, v in cnt.items())
        self._ner_stats_var.set(f'Всего: {len(ents)}  |  {stats}' if stats else f'Сущностей: {len(ents)}')

    def _show_sentiment(self, r: AnalysisResult):
        s = r.sentiment
        label_ru = s.get('overall_ru', '—')
        score    = s.get('score', 0)
        engine   = s.get('engine', 'lexical')
        raw_sc   = s.get('raw_scores', {})

        emoji = {'позитивный': '😊', 'негативный': '😞', 'нейтральный': '😐'}.get(label_ru, '')
        self._sent_label_var.set(f'{emoji} {label_ru.capitalize()}')

        # Показываем движок и оценку
        eng_badge = '🤖 dostoevsky' if engine == 'dostoevsky' else '📖 лексический'
        self._sent_score_var.set(f'Оценка: {score:+.3f}   [{eng_badge}]')

        # Если dostoevsky — показываем полные 5-классовые вероятности
        if raw_sc and engine == 'dostoevsky':
            labels5 = {'positive':'позит.','negative':'негат.',
                       'neutral':'нейтр.','speech':'речь','skip':'пропуск'}
            parts = '  '.join(
                f'{labels5.get(k,k)}: {v:.2f}'
                for k, v in sorted(raw_sc.items(), key=lambda x: -x[1])
                if v > 0.01
            )
            self._sent_counts_var.set(f'Классификатор: {parts}')
        else:
            self._sent_counts_var.set(
                f'🟢 Позитивных слов: {s.get("positive_count", 0)}   '
                f'🔴 Негативных слов: {s.get("negative_count", 0)}'
            )

        # Таблица предложений — теперь с 5 классами если есть
        self._sent_tree.delete(*self._sent_tree.get_children())
        for item in s.get('per_sentence', []):
            sid   = item['id']
            sc    = item['score']
            stext = r.sentences[sid].text[:70] if sid < len(r.sentences) else ''
            # Используем label из dostoevsky если есть
            item_label = item.get('label_ru') or (
                '😊 позитивный' if sc > .2 else
                ('😞 негативный' if sc < -.2 else '😐 нейтральный'))
            if not item_label.startswith('😊') and not item_label.startswith('😞') and not item_label.startswith('😐'):
                em_map = {'позитивный':'😊','негативный':'😞','нейтральный':'😐'}
                item_label = em_map.get(item_label, '') + ' ' + item_label
            tag   = 'pos' if sc > .2 else ('neg' if sc < -.2 else 'neu')
            # Дополнительно: топ-класс от dostoevsky
            scores5 = item.get('scores', {})
            top_str = ''
            if scores5:
                top_k, top_v = max(scores5.items(), key=lambda x: x[1])
                labels5 = {'positive':'позит.','negative':'негат.',
                           'neutral':'нейтр.','speech':'речь','skip':'пропуск'}
                top_str = f'{labels5.get(top_k, top_k)}: {top_v:.2f}'
            self._sent_tree.insert('', 'end',
                values=(sid + 1, stext, f'{sc:+.3f}', item_label, top_str),
                tags=(tag,))
        self._sent_tree.tag_configure('pos', foreground=CLR['green'])
        self._sent_tree.tag_configure('neg', foreground=CLR['red'])
        self._sent_tree.tag_configure('neu', foreground=CLR['yellow'])

        # Предупреждение если dostoevsky недоступна
        from core.sentiment import get_error
        err = get_error()
        if err and hasattr(self, '_sent_engine_warn'):
            self._sent_engine_warn.config(text=f'⚠️  {err.splitlines()[0]}')

        self._draw_sentiment_chart(r)

    def _draw_sentiment_chart(self, r: AnalysisResult):
        for w in self._sent_chart_frame.winfo_children():
            w.destroy()
        per = r.sentiment.get('per_sentence', [])
        if not per:
            return
        ids    = [p['id'] for p in per]
        scores = [p['score'] for p in per]
        colors = [CLR['green'] if sc > .2 else (CLR['red'] if sc < -.2 else CLR['yellow'])
                  for sc in scores]
        fig, ax = plt.subplots(figsize=(3.8, 3.6), facecolor=CLR['bg'])
        ax.set_facecolor(CLR['bg'])
        ax.bar(ids, scores, color=colors, edgecolor=CLR['bg'], linewidth=0.5)
        ax.axhline(0, color=CLR['text2'], linewidth=0.8, linestyle='--')
        ax.set_xlabel('№ предл.', color=CLR['text2'], fontsize=9)
        ax.set_ylabel('Тональность', color=CLR['text2'], fontsize=9)
        ax.tick_params(colors=CLR['text2'], labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(CLR['border'])
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, self._sent_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
        self._sent_chart_canvas = canvas
        plt.close(fig)

    def _quiz_start(self):
        if not self.result:
            messagebox.showinfo('Тест', 'Сначала выполните анализ текста.')
            return
        self._quiz_questions = generate_quiz(self.result, count=10)
        if not self._quiz_questions:
            messagebox.showinfo('Тест', 'Недостаточно данных для формирования вопросов.')
            return
        self._quiz_idx        = 0
        self._quiz_score      = 0
        self._quiz_streak     = 0
        self._quiz_max_streak = 0
        self._quiz_final_var.set('')
        self._quiz_score_var.set('Очки: 0')
        self._quiz_combo_var.set('')
        self.nb.select(4)
        self._quiz_show_question()

    # ── Кнопка «Существительное» ──────────────────────────────────────────
    def _destroy_cheat(self):
        if self._cheat_btn is not None:
            try:
                self._cheat_btn.destroy()
            except Exception:
                pass
            self._cheat_btn = None

    def _spawn_cheat_button(self):
        """
        Полностью невидимая кнопка, размещённая в одном из двух нижних углов окна.
        Обнаруживается только ховером — становится еле-еле видной.
        Всегда засчитывает верный ответ.
        """
        self._destroy_cheat()

        def on_click():
            self._cheat_used_in_question = True
            self._quiz_cheat_answer()

        root_bg = self.root.cget('bg')

        def on_enter(_e):
            btn.configure(bg='#2E2E42', fg='#505068')

        def on_leave(_e):
            btn.configure(bg=root_bg, fg=root_bg)

        btn = tk.Button(self.root, text='Существительное',
                        command=on_click,
                        bg=root_bg, fg=root_bg,
                        activebackground=root_bg, activeforeground=root_bg,
                        relief='flat', borderwidth=0,
                        highlightthickness=0,
                        font=FT_BODY,
                        cursor='hand2',
                        padx=14, pady=10)

        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)

        # Случайно: левый нижний или правый нижний угол
        if random.choice([True, False]):
            # Левый нижний
            btn.place(relx=0.0, rely=1.0, anchor='sw', x=8, y=-8)
        else:
            # Правый нижний
            btn.place(relx=1.0, rely=1.0, anchor='se', x=-8, y=-8)

        self._cheat_btn = btn

    def _quiz_cheat_answer(self):
        """Обрабатывает чит: засчитывает верный ответ для ЛЮБОГО типа вопроса."""
        if self._quiz_answered:
            return
        self._quiz_answered = True
        from core.quiz import calc_points
        q = self._quiz_questions[self._quiz_idx]
        self._quiz_streak += 1
        if self._quiz_streak > self._quiz_max_streak:
            self._quiz_max_streak = self._quiz_streak
        pts = calc_points(self._quiz_streak)
        self._quiz_score += pts
        combo_txt = f'  🔥 Комбо x{self._quiz_streak}  +{pts} очков!' if self._quiz_streak >= 2 else ''
        self._quiz_expl_var.set(f'✅ Верно! +{pts} очков.  {q.get("explanation", "")}')
        self._quiz_combo_var.set(combo_txt)
        self._quiz_score_var.set(f'Очки: {self._quiz_score}')
        # Блокируем все обычные кнопки
        for b in self._quiz_opt_btns:
            b.configure(state='disabled')
        # Подсвечиваем правильные
        if q.get('category') == 'match':
            for widgets in self._match_rows:
                word, correct, var, btns = widgets
                for lbl_text, btn in btns.items():
                    if lbl_text == correct:
                        btn.configure(bg=CLR['green'], fg='#1E1E2E')
                    btn.configure(state='disabled')
        else:
            correct = q.get('correct', '')
            for i, opt in enumerate(q.get('options', [])):
                if opt == correct:
                    self._quiz_opt_btns[i].configure(bg=CLR['green'], fg='#1E1E2E')
        self._destroy_cheat()

    # ── Отображение вопроса (разветвление по типу) ────────────────────────────

    def _show_normal_options(self, q):
        """Обычные 4 кнопки-варианта."""
        self._match_frame.pack_forget()
        self._opt_frame.pack(fill='x')
        options = q.get('options', [])
        for i, btn in enumerate(self._quiz_opt_btns):
            text = options[i] if i < len(options) else ''
            self._quiz_opt_vars[i].set(f'  {chr(65+i)}.  {text}')
            btn.configure(bg=CLR['panel'], fg=CLR['text'], state='normal')
            btn.grid(row=i//2, column=i%2, padx=12, pady=6, sticky='nsew')

    def _show_match_ui(self, q):
        """Для вопроса типа match: 4 строки со словом слева и кнопками-метками справа."""
        self._opt_frame.pack_forget()
        for w in self._match_frame.winfo_children():
            w.destroy()
        self._match_rows = []
        self._match_frame.pack(fill='x')

        pairs = q.get('pairs', [])
        all_labels = list({p[1] for p in pairs})   
        random.shuffle(all_labels)

        head = tk.Label(self._match_frame,
                        text='Выберите часть речи для каждого слова:',
                        bg=CLR['bg'], fg=CLR['text2'],
                        font=FT_SMALL)
        head.pack(anchor='w', pady=(0, 6))

        for word, correct in pairs:
            row = tk.Frame(self._match_frame, bg=CLR['panel'], padx=10, pady=6)
            row.pack(fill='x', pady=3)
            tk.Label(row, text=f'«{word}»', bg=CLR['panel'], fg=CLR['yellow'],
                     font=FT_HDR, width=18, anchor='w').pack(side='left', padx=(4, 8))
            var = tk.StringVar(value='')
            btns_map: dict = {}
            btn_row = tk.Frame(row, bg=CLR['panel'])
            btn_row.pack(side='left', fill='x', expand=True)
            for lbl in all_labels:
                b = tk.Button(btn_row, text=lbl,
                              bg=CLR['border'], fg=CLR['text'],
                              font=FT_SMALL, relief='flat',
                              activebackground=CLR['accent2'],
                              cursor='hand2', padx=8, pady=4)
                def _on_pick(w=word, l=lbl, v=var, local_btns=btns_map):
                    v.set(l)
                    for tt, bb in local_btns.items():
                        bb.configure(bg=CLR['border'], fg=CLR['text'])
                    local_btns[l].configure(bg=CLR['accent'], fg='white')
                b.configure(command=_on_pick)
                b.pack(side='left', padx=3)
                btns_map[lbl] = b
            self._match_rows.append((word, correct, var, btns_map))

    def _quiz_show_question(self):
        if self._quiz_idx >= len(self._quiz_questions):
            self._quiz_finish()
            return
        q = self._quiz_questions[self._quiz_idx]
        self._quiz_answered = False
        self._cheat_used_in_question = False

        self._quiz_q_var.set(q.get('question', ''))
        self._quiz_hint_var.set(f'💡 {q.get("hint", "")}' if q.get('hint') else '')

        # Context
        ctx = q.get('sentence_context', '')
        word = q.get('target_word', '')
        self._quiz_ctx_text.config(state='normal')
        self._quiz_ctx_text.delete('1.0', 'end')
        if word and ctx:
            import re as _re
            pattern = _re.compile(_re.escape(word), _re.IGNORECASE)
            last = 0
            for m in pattern.finditer(ctx):
                self._quiz_ctx_text.insert('end', ctx[last:m.start()])
                self._quiz_ctx_text.insert('end', ctx[m.start():m.end()], 'highlight')
                last = m.end()
            self._quiz_ctx_text.insert('end', ctx[last:])
        else:
            self._quiz_ctx_text.insert('end', ctx)
        self._quiz_ctx_text.config(state='disabled')

        self._quiz_expl_var.set('')
        self._quiz_progress_var.set(
            f'{self._quiz_idx + 1} / {len(self._quiz_questions)}')
        self._quiz_final_var.set('')

        # Разветвление по типу
        if q.get('category') == 'match':
            self._show_match_ui(q)
        else:
            self._show_normal_options(q)

        if q.get('category') != 'match':
            self._spawn_cheat_button()

    def _quiz_answer(self, idx: int):
        """Обработка обычного ответа (pos/dep/lemma/fill/joke)."""
        if self._quiz_answered:
            return
        self._quiz_answered = True
        q       = self._quiz_questions[self._quiz_idx]
        if idx >= len(q.get('options', [])):
            return
        chosen  = q['options'][idx]
        correct = q.get('correct', '')
        from core.quiz import calc_points
        if chosen == correct:
            self._quiz_streak += 1
            if self._quiz_streak > self._quiz_max_streak:
                self._quiz_max_streak = self._quiz_streak
            pts = calc_points(self._quiz_streak)
            self._quiz_score += pts
            self._quiz_opt_btns[idx].configure(bg=CLR['green'], fg='#1E1E2E')
            combo_txt = ''
            if self._quiz_streak >= 2:
                combo_txt = f'  🔥 Комбо x{self._quiz_streak}  +{pts} очков!'
            self._quiz_expl_var.set(f'✅ Верно! +{pts} очков.  {q.get("explanation", "")}')
            self._quiz_combo_var.set(combo_txt)
        else:
            self._quiz_streak = 0
            self._quiz_opt_btns[idx].configure(bg=CLR['red'], fg='#1E1E2E')
            for i, opt in enumerate(q.get('options', [])):
                if opt == correct:
                    self._quiz_opt_btns[i].configure(bg=CLR['green'], fg='#1E1E2E')
            self._quiz_expl_var.set(f'❌ Неверно.  {q.get("explanation", "")}')
            self._quiz_combo_var.set('')
        self._quiz_score_var.set(f'Очки: {self._quiz_score}')
        for btn in self._quiz_opt_btns:
            btn.configure(state='disabled')
        self._destroy_cheat()

    def _quiz_submit_match(self):
        """Проверка match-вопроса."""
        if self._quiz_answered:
            return
        q = self._quiz_questions[self._quiz_idx]
        if q.get('category') != 'match':
            return
        all_picked = all(var.get() for _, _, var, _ in self._match_rows)
        if not all_picked:
            messagebox.showinfo('Сопоставление', 'Выберите часть речи для каждого слова.')
            return
        self._quiz_answered = True
        all_correct = True
        for word, correct, var, btns_map in self._match_rows:
            picked = var.get()
            if picked == correct:
                btns_map[picked].configure(bg=CLR['green'], fg='#1E1E2E')
            else:
                all_correct = False
                if picked in btns_map:
                    btns_map[picked].configure(bg=CLR['red'], fg='#1E1E2E')
                if correct in btns_map:
                    btns_map[correct].configure(bg=CLR['green'], fg='#1E1E2E')
            for b in btns_map.values():
                b.configure(state='disabled')
        from core.quiz import calc_points
        if all_correct:
            self._quiz_streak += 1
            if self._quiz_streak > self._quiz_max_streak:
                self._quiz_max_streak = self._quiz_streak
            pts = calc_points(self._quiz_streak)
            self._quiz_score += pts
            combo_txt = f'  🔥 Комбо x{self._quiz_streak}  +{pts} очков!' if self._quiz_streak >= 2 else ''
            self._quiz_expl_var.set(f'✅ Все соответствия верны! +{pts} очков.')
            self._quiz_combo_var.set(combo_txt)
        else:
            self._quiz_streak = 0
            self._quiz_expl_var.set(f'❌ Есть ошибки. {q.get("explanation", "")}')
            self._quiz_combo_var.set('')
        self._quiz_score_var.set(f'Очки: {self._quiz_score}')
        self._destroy_cheat()

    def _quiz_next(self):
        if not self._quiz_questions:
            self._quiz_start()
            return
        self._quiz_idx += 1
        self._destroy_cheat()
        self._quiz_show_question()

    def _quiz_finish(self):
        total = len(self._quiz_questions)
        pct   = round(self._quiz_score / total * 10) if total else 0
        grade = '🏆 Отлично!' if pct >= 80 else ('👍 Хорошо!' if pct >= 60 else '📚 Нужна практика')
        self._quiz_final_var.set(
            f'{grade}  Сессия: {self._quiz_score} очков  |  '
            f'Лучшая серия: {self._quiz_max_streak}  |  '
            f'Вопросов: {total}')
        self._quiz_q_var.set('Тест завершён! Нажмите «Новый тест» для повторного прохождения.')
        self._quiz_hint_var.set('')
        self._quiz_ctx_text.config(state='normal')
        self._quiz_ctx_text.delete('1.0', 'end')
        self._quiz_ctx_text.config(state='disabled')
        self._quiz_combo_var.set('')
        self._quiz_expl_var.set('')
        for btn in self._quiz_opt_btns:
            btn.configure(bg=CLR['border'], fg=CLR['text2'], state='disabled')
        self._destroy_cheat()
        for w in self._match_frame.winfo_children():
            w.destroy()
        if self.current_user:
            save_score(self.current_user['username'],
                       self._quiz_score, self._quiz_max_streak)
            self._update_balance_display()

    def _update_balance_display(self):
        """Синхронизирует отображение баланса в шапке и в магазине."""
        if not self.current_user:
            return
        from core.shop import get_user_balance as _gub
        uname    = self.current_user.get('username', '')
        real_bal = _gub(uname)
        self.current_user['total_score'] = real_bal
        if hasattr(self, '_user_score_var'):
            self._user_score_var.set(f'👤 {uname}   🏆 {real_bal} баллов')
        if hasattr(self, '_shop_balance_var'):
            self._shop_balance_var.set(f'💰 Баланс: {real_bal} баллов')

    # ── DB actions ────────────────────────────────────────────────────────────

    def _save_to_db(self):
        if not self.result:
            messagebox.showinfo('Сохранение', 'Нет результатов анализа для сохранения.')
            return
        db = get_db()
        if not db.is_available():
            messagebox.showerror('БД недоступна',
                'Не удалось подключиться к PostgreSQL.\n'
                'Проверьте настройки (DB_NAME, DB_USER, DB_PASSWORD, DB_HOST).')
            return
        name = Path(self.current_file.get().replace('📄 ', '').split('  ')[0]).name or 'текст'
        text = self.text_input.get('1.0', 'end').strip()
        aid  = db.save_analysis(name, text, self.result,
                                self.result.sentiment, self.result.entities)
        if aid:
            messagebox.showinfo('Сохранено', f'Анализ сохранён в БД (ID={aid}).')
            self.status_var.set(f'Сохранено в БД, ID={aid}')
        else:
            messagebox.showerror('Ошибка', 'Не удалось сохранить в БД.')

    def _export_json(self):
        if not self.result:
            messagebox.showinfo('Экспорт', 'Нет данных для экспорта.')
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.json',
            filetypes=[('JSON файл', '*.json'), ('Все файлы', '*.*')],
        )
        if not path:
            return
        r = self.result
        data = {
            'stats': r.stats,
            'sentiment': r.sentiment,
            'elapsed_ms': r.elapsed_ms,
            'sentences': [
                {'id': s.id, 'text': s.text,
                 'tokens': [t.to_dict() for t in s.tokens]}
                for s in r.sentences
            ],
            'entities': [
                {'text': e.text, 'label': e.label, 'label_ru': e.label_ru}
                for e in r.entities
            ],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        messagebox.showinfo('Экспорт', f'Данные сохранены в {path}')

    # ── History ───────────────────────────────────────────────────────────────

    def _load_history(self):
        db = get_db()
        rows = db.get_history(limit=100)
        self._populate_history(rows)

    def _populate_history(self, rows):
        self._hist_tree.delete(*self._hist_tree.get_children())
        for row in rows:
            d = dict(row)
            date = str(d.get('created_at', ''))[:16]
            sent_color = {'positive': '😊', 'negative': '😞', 'neutral': '😐'}
            slbl = sent_color.get(d.get('sentiment', ''), '') + ' ' + str(d.get('sentiment', ''))
            self._hist_tree.insert('', 'end', values=(
                d.get('id', ''),
                date,
                d.get('source_name', ''),
                d.get('sentence_count', ''),
                d.get('word_count', ''),
                slbl,
                f'{d.get("sentiment_score", 0):.3f}',
                d.get('notes', '') or '',
            ))

    def _search_history(self):
        q = self._hist_search.get().strip()
        if not q:
            self._load_history()
            return
        db  = get_db()
        res = db.search_by_name(q) or db.search_by_word(q) or []
        self._populate_history(res)

    def _get_selected_history_id(self):
        sel = self._hist_tree.selection()
        if not sel:
            messagebox.showinfo('История', 'Выберите запись в таблице.')
            return None
        vals = self._hist_tree.item(sel[0])['values']
        return int(vals[0])

    def _rename_history(self):
        aid = self._get_selected_history_id()
        if aid is None:
            return
        new_name = simpledialog.askstring('Переименовать', 'Новое название:')
        if new_name:
            get_db().rename_analysis(aid, new_name)
            self._load_history()

    def _edit_notes(self):
        aid = self._get_selected_history_id()
        if aid is None:
            return
        notes = simpledialog.askstring('Заметка', 'Введите заметку:')
        if notes is not None:
            get_db().update_notes(aid, notes)
            self._load_history()

    def _delete_history(self):
        aid = self._get_selected_history_id()
        if aid is None:
            return
        if messagebox.askyesno('Удалить', f'Удалить анализ ID={aid}?'):
            get_db().delete_analysis(aid)
            self._load_history()

    def _load_from_history(self):
        aid = self._get_selected_history_id()
        if aid is None:
            return
        row = get_db().get_analysis(aid)
        if not row:
            messagebox.showerror('Ошибка', 'Запись не найдена.')
            return
        self.text_input.delete('1.0', 'end')
        self.text_input.insert('1.0', row.get('source_text', ''))
        self.current_file.set(f'📄 {row["source_name"]}  (из БД)')
        self.nb.select(0)
        self.status_var.set(f'Текст загружен из БД (ID={aid})')

    # ── DB check ──────────────────────────────────────────────────────────────

    def _check_db_async(self):
        def check():
            try:
                ok = get_db().is_available()
                txt = '🟢 БД: подключена' if ok else '🔴 БД: нет соединения'
            except Exception:
                txt = '🔴 БД: нет соединения'
            self.root.after(0, lambda: self.db_status_var.set(txt))
        threading.Thread(target=check, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # Close / Logout — кастомный диалог: «Сменить пользователя», «Да», «Отмена»
    # ══════════════════════════════════════════════════════════════════════════

    def _on_close(self):
        dlg = CloseDialog(self.root)
        if dlg.result == 'cancel':
            return
        if dlg.result == 'switch':
            # Возврат в окно авторизации
            for w in self.root.winfo_children():
                w.destroy()
            self.root.withdraw()
            self.current_user = None
            self._unlocks = set()
            AuthWindow(self.root, self._restart_after_auth)
        else:  # 'quit'
            self.root.destroy()

    def _restart_after_auth(self, user: dict):
        self.current_user = user
        uname = user.get('username', '')
        self._unlocks = get_purchases(uname)
        self._active_theme = get_active_theme(uname)
        from core.shop import THEME_ITEMS as _TI
        if self._active_theme in _TI:
            CLR.update(_TI[self._active_theme]['colors'])
        self.result = None
        self.current_file    = tk.StringVar(value='Файл не выбран')
        self.status_var      = tk.StringVar(value='Готов')
        self.db_status_var   = tk.StringVar(value='БД: проверяется…')
        self._quiz_questions = []
        self._quiz_idx = self._quiz_score = self._quiz_streak = self._quiz_max_streak = 0
        self._quiz_answered  = False
        self._cheat_btn = None
        self._build_ui()
        self.root.configure(bg=CLR['bg'])
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self._check_db_async()

    # ── Locks ─────────────────────────────────────────────────────────────────

    def _apply_locks(self):
        lock_map = {1: 'tokens', 2: 'entities', 3: 'sentiment', 4: 'semantics'}
        for tab_idx, item_id in lock_map.items():
            state = 'normal' if item_id in self._unlocks else 'disabled'
            self.nb.tab(tab_idx, state=state)
        if 'export' in self._unlocks:
            self._export_btn.config(state='normal', text='📄 Экспорт JSON')
        else:
            self._export_btn.config(state='disabled', text='📄 Экспорт JSON 🔒')

    def _build_tab_shop(self):
        tab = tk.Frame(self.nb, bg=CLR['bg'])
        self.nb.add(tab, text='🛒 Магазин')
        self._shop_tab = tab
        self._refresh_shop()

    def _refresh_shop(self):
        for w in self._shop_tab.winfo_children():
            w.destroy()
        tab = self._shop_tab
        uname   = self.current_user.get('username', '') if self.current_user else ''
        balance = get_user_balance(uname)
        if self.current_user:
            self.current_user['total_score'] = balance
        owned   = get_purchases(uname)
        active_theme = get_active_theme(uname)

        hdr = tk.Frame(tab, bg=CLR['panel'], pady=12)
        hdr.pack(fill='x', padx=8, pady=(8, 0))
        _lbl(hdr, '🛒  Магазин', bold=True, size=15).pack(side='left', padx=12)
        self._shop_balance_var = tk.StringVar(value=f'💰 Баланс: {balance} баллов')
        tk.Label(hdr, textvariable=self._shop_balance_var,
                 bg=CLR['panel'], fg=CLR['yellow'],
                 font=FT_HDR).pack(side='right', padx=16)

        canvas = tk.Canvas(tab, bg=CLR['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y', pady=4)
        canvas.pack(side='left', fill='both', expand=True, padx=(8, 0), pady=4)
        inner = tk.Frame(canvas, bg=CLR['bg'])
        win_id = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))

        def _on_mousewheel(event):
            if event.num == 4:
                canvas.yview_scroll(-1, 'units')
            elif event.num == 5:
                canvas.yview_scroll(1, 'units')
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        def _bind_wheel(widget):
            """Рекурсивно привязываем скролл ко всем дочерним виджетам inner."""
            widget.bind('<MouseWheel>', _on_mousewheel)
            widget.bind('<Button-4>',   _on_mousewheel)
            widget.bind('<Button-5>',   _on_mousewheel)
            for child in widget.winfo_children():
                _bind_wheel(child)

        canvas.bind('<MouseWheel>', _on_mousewheel)
        canvas.bind('<Button-4>',   _on_mousewheel)
        canvas.bind('<Button-5>',   _on_mousewheel)
        inner.bind('<Map>', lambda e: _bind_wheel(inner))

        def section_hdr(title):
            f = tk.Frame(inner, bg=CLR['bg'])
            f.pack(fill='x', padx=8, pady=(14, 4))
            tk.Label(f, text=title, bg=CLR['bg'], fg=CLR['accent'],
                     font=FT_HDR).pack(anchor='w')
            tk.Frame(inner, bg=CLR['border'], height=1).pack(fill='x', padx=8, pady=(0, 6))

        def shop_card(item_id, item, is_theme=False):
            is_owned = item_id in owned
            card = tk.Frame(inner, bg=CLR['panel'], padx=16, pady=12)
            card.pack(fill='x', padx=8, pady=3)
            info = tk.Frame(card, bg=CLR['panel'])
            info.pack(side='left', fill='both', expand=True)
            tk.Label(info, text=item['name'], bg=CLR['panel'], fg=CLR['text'],
                     font=FT_BOLD).pack(anchor='w')
            tk.Label(info, text=item['desc'], bg=CLR['panel'], fg=CLR['text2'],
                     font=FT_SMALL).pack(anchor='w')
            right = tk.Frame(card, bg=CLR['panel'])
            right.pack(side='right')
            price_str = ('Бесплатно'
                         if item['price'] == 0 else f'{item["price"]} 💰')
            tk.Label(right, text=price_str, bg=CLR['panel'],
                     fg=CLR['green'] if item['price'] == 0 else CLR['yellow'],
                     font=FT_BOLD).pack(anchor='e')
            if is_theme:
                if is_owned:
                    if item_id == active_theme:
                        tk.Label(right, text='✅ Активна',
                                 bg=CLR['panel'], fg=CLR['green'],
                                 font=FT_SMALL).pack(pady=2)
                    else:
                        _btn(right, '🎨 Применить',
                             lambda iid=item_id: self._apply_theme(iid),
                             color=CLR['accent2']).pack(pady=2)
                else:
                    _btn(right, 'Купить',
                         lambda iid=item_id: self._shop_buy(iid),
                         color=CLR['accent']).pack(pady=2)
            else:
                if is_owned:
                    tk.Label(right, text='✅ Куплено',
                             bg=CLR['panel'], fg=CLR['green'],
                             font=FT_SMALL).pack(pady=2)
                else:
                    _btn(right, 'Купить',
                         lambda iid=item_id: self._shop_buy(iid),
                         color=CLR['accent']).pack(pady=2)

        section_hdr('🔓  Разблокировки функций')
        for iid, item in UNLOCK_ITEMS.items():
            shop_card(iid, item, is_theme=False)

        section_hdr('🎨  Цветовые схемы')
        for iid, item in THEME_ITEMS.items():
            shop_card(iid, item, is_theme=True)

        _bind_wheel(inner)

    def _shop_buy(self, item_id: str):
        uname = self.current_user.get('username', '') if self.current_user else ''
        ok, msg = buy_item(uname, item_id)
        if ok:
            self._unlocks = get_purchases(uname)
            self._apply_locks()
            self._update_balance_display()
            self._refresh_shop()
            messagebox.showinfo('Магазин', f'✅ {msg}')
        else:
            messagebox.showerror('Магазин', f'❌ {msg}')

    def _apply_theme(self, theme_id: str):
        """Применяет тему МГНОВЕННО: пересобирает весь UI, не требуя перезапуска."""
        uname = self.current_user.get('username', '') if self.current_user else ''
        ok = set_active_theme(uname, theme_id)
        if not ok:
            messagebox.showerror('Тема', 'Не удалось применить тему.')
            return
        self._active_theme = theme_id
        from core.shop import THEME_ITEMS as _TI
        CLR.update(_TI[theme_id]['colors'])
        # Сохраняем текущее состояние перед пересборкой
        saved_text = self.text_input.get('1.0', 'end') if hasattr(self, 'text_input') else ''
        saved_tab  = self.nb.index('current') if hasattr(self, 'nb') else 0
        # Уничтожаем все дочерние виджеты корня и собираем UI заново
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=CLR['bg'])
        self._cheat_btn = None
        self._build_ui()
        # Восстанавливаем текст и результаты
        try:
            self.text_input.delete('1.0', 'end')
            self.text_input.insert('1.0', saved_text.rstrip('\n'))
            self._update_word_count()
            if self.result:
                self._show_results(self.result)
                self.nb.select(min(saved_tab, 6))
            else:
                self.nb.select(min(saved_tab, 6))
        except Exception:
            pass
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self._check_db_async()
        messagebox.showinfo('Тема',
            f'Тема «{_TI[theme_id]["name"]}» применена!')

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


# ══════════════════════════════════════════════════════════════════════════════
# Help text
# ══════════════════════════════════════════════════════════════════════════════

HELP_TEXT = """
╔══════════════════════════════════════════════════════════════════╗
║           СинтАналитик — Полное руководство пользователя         ║
╚══════════════════════════════════════════════════════════════════╝

ВЕРСИЯ: 2.1  |  Лабораторная работа №4, Вариант 4 (DOC, русский язык)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 АВТОРИЗАЦИЯ И АККАУНТ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

При первом запуске откроется экран входа/регистрации.

  Регистрация:
  • Введите имя пользователя (минимум 3 символа)
  • Введите пароль (минимум 4 символа)
  • Решите капчу. При регистрации тип капчи выбирается СЛУЧАЙНО:
      – Математика (сложение/вычитание/умножение)
      – Угадай число от 1 до 100 (с подсказками «больше/меньше»)
      – Напишите слово задом наперёд
      – Посчитайте сколько раз встречается эмодзи
      – Какое слово лишнее

  Вход:
  • Используется простая математическая капча.
  • Нажмите 🔄 чтобы сменить задачу капчи.

  Диалог закрытия приложения (кнопка ×):
  • «Сменить пользователя» — вернуться к окну авторизации
  • «Да» — полностью закрыть приложение
  • «Отмена» — продолжить работу

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ВКЛАДКА ТЕСТ — ТИПЫ ВОПРОСОВ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

10 вопросов, сгенерированных из вашего текста.

  • Часть речи       — какая ЧР у слова из текста
  • Синт. роль       — определите синтаксическую роль слова
  • Лемма            — укажите начальную форму слова
  • Пропуск          — вставьте пропущенное слово в предложении
  • Сопоставление    — соедините 4 слова с их частями речи
                          (кнопка «✓ Проверить» под вариантами)
  • Шуточный         — один на тест.
                       

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ЦВЕТОВЫЕ ТЕМЫ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Темы применяются МГНОВЕННО — перезапуск приложения НЕ требуется.
Выберите тему в Магазине и нажмите «Применить».

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 СИСТЕМА БАЛЛОВ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Базовые очки за правильный ответ: 10
  Комбо-множители (серия правильных ответов):
    Серия 1  →  10 очков (×1)
    Серия 2  →  15 очков (×1.5)
    Серия 3  →  20 очков (×2)
    Серия 4+ →  30 очков (×3)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ПОДДЕРЖИВАЕМЫЕ ФАЙЛЫ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  .docx   — python-docx (встроено)
  .doc    — через LibreOffice
  .txt    — UTF-8 / CP1251 (автоопределение)
  .pdf    — pdfplumber
  .rtf    — базовая поддержка
  .html   — встроенная поддержка

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 NLP-ТЕХНОЛОГИИ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  natasha    — сегментация, морфология, синтаксис, NER
  pymorphy2  — лемматизация русских слов
  matplotlib — визуализация (графики, диаграммы)
  tkinter    — графический интерфейс
  sqlite3    — пользователи, баллы, покупки
  psycopg2   — PostgreSQL (опциональная история анализов)
"""