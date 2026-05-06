"""
quiz.py — движок геймификации.

Типы вопросов (category):
  'pos'       — часть речи
  'dep'       — синтаксическая роль
  'lemma'     — начальная форма
  'fill'      — заполнить пропуск в предложении
  'match'     — сопоставить 4 слова → 4 части речи
  'joke'      — шуточный вопрос 

Каждый вопрос — dict со стандартными полями:
  question, options, correct, hint, explanation, category, sentence_context,
  target_word. Для 'match' дополнительно: pairs (список (слово, правильный_ответ)).

Система очков:
  Базовые очки за правильный ответ: 10
  Комбо-множитель:  серия 2 = ×1.5 | 3 = ×2 | 4+ = ×3
"""

import random
from typing import List, Optional, Dict, Any

from core.analyzer import AnalysisResult, Token, Sentence, POS_RU, DEP_RU


# ── Очки ──────────────────────────────────────────────────────────────────────

BASE_POINTS = 10
COMBO_MULTIPLIER = {0: 1, 1: 1, 2: 1.5, 3: 2}   # 4+ → 3

def calc_points(streak: int) -> int:
    mult = COMBO_MULTIPLIER.get(min(streak, 3), 3)
    return int(BASE_POINTS * mult)


# ── Шуточные вопросы  ────────────────────────────────────

JOKE_QUESTIONS = [
    {
        'question':    '🤔 Сколько лошадиных сил у одной лошади?',
        'options':     ['0.7', '1', '1.5', 'Зависит от породы'],
        'correct':     '0.7',
        'hint':        'Удивительно, но меньше единицы!',
        'explanation': 'Лошадь в среднем развивает около 0.7 л.с. — единица измерения была калиброванной Джеймсом Уаттом для шахтных пони.',
    },
    {
        'question':    '🤔 Если в комнате 4 угла и в каждом углу сидит кошка, а напротив каждой кошки по 3 кошки, то сколько всего кошек в комнате?',
        'options':     ['4', '12', '16', '13'],
        'correct':     '4',
        'hint':        'Подумайте — кошки смотрят друг на друга.',
        'explanation': 'Всего 4 кошки: каждая из них видит 3 других напротив себя.',
    },
    {
        'question':    '🤔 Сколько месяцев в году имеют 28 дней?',
        'options':     ['Один (февраль)', 'Все 12', 'Два', 'Ноль'],
        'correct':     'Все 12',
        'hint':        'Ловушка в формулировке!',
        'explanation': 'Во всех 12 месяцах есть 28 дней — в некоторых просто больше.',
    },
    {
        'question':    '🤔 Что тяжелее: килограмм пуха или килограмм железа?',
        'options':     ['Одинаково', 'Железо', 'Пух', 'Зависит от влажности'],
        'correct':     'Одинаково',
        'hint':        'Классика!',
        'explanation': 'Килограмм есть килограмм, независимо от материала.',
    },
    {
        'question':    '🤔 Сколько горошин можно положить в пустой стакан?',
        'options':     ['Одну (после неё он уже не пустой)', 'Столько, сколько поместится', 'Ни одной', 'Бесконечно много'],
        'correct':     'Одну (после неё он уже не пустой)',
        'hint':        'Играем словами.',
        'explanation': 'После первой горошины стакан перестаёт быть пустым.',
    },
    {
        'question':    '🤔 На какое дерево садится ворона во время дождя?',
        'options':     ['На мокрое', 'На дуб', 'На берёзу', 'На сосну'],
        'correct':     'На мокрое',
        'hint':        'Очевидно же!',
        'explanation': 'Любое дерево под дождём становится мокрым.',
    },
    {
        'question':    '🤔 У фермера 17 овец. Все, кроме 9, убежали. Сколько овец осталось?',
        'options':     ['9', '8', '17', '0'],
        'correct':     '9',
        'hint':        'Читайте внимательно: «все, кроме 9».',
        'explanation': 'Осталось как раз 9 — остальные убежали.',
    },
    {
        'question':    '🤔 Что можно увидеть с закрытыми глазами?',
        'options':     ['Сон', 'Темноту', 'Ничего', 'Всё сразу'],
        'correct':     'Сон',
        'hint':        'Только во сне.',
        'explanation': 'Сны мы видим именно с закрытыми глазами.',
    },
    {
        'question':    '🤔 Какая буква в русском алфавите считается «самой гордой»?',
        'options':     ['Я', 'А', 'Э', 'Ъ'],
        'correct':     'Я',
        'hint':        'Она всегда ставит себя на первое место.',
        'explanation': 'Шутливый ответ: «Я» — потому что гордо ставит себя впереди.',
    },
    {
        'question':    '🤔 Сколько нужно программистов, чтобы вкрутить лампочку?',
        'options':     ['Это аппаратная проблема', '1', '42', 'Ни одного — это фича'],
        'correct':     'Это аппаратная проблема',
        'hint':        'Классика IT-юмора.',
        'explanation': 'Программисты не чинят железо — это «hardware problem».',
    },
]


def _make_joke_question() -> Dict[str, Any]:
    """Генерирует один шуточный вопрос."""
    jq = random.choice(JOKE_QUESTIONS).copy()
    options = list(jq['options'])
    random.shuffle(options)
    return {
        'question':          jq['question'],
        'options':           options,
        'correct':           jq['correct'],
        'hint':              f'💭 {jq["hint"]}',
        'explanation':       jq['explanation'],
        'category':          'joke',
        'sentence_context':  '— Шуточный вопрос  —',
        'target_word':       '',
    }


# ── Генераторы вопросов ───────────────────────────────────────────────────────

def _pos_question(token: Token, sentence: Sentence,
                  all_pos_ru: List[str]) -> Dict[str, Any]:
    correct = token.pos_ru
    distractors = [p for p in all_pos_ru if p != correct]
    random.shuffle(distractors)
    options = [correct] + distractors[:3]
    random.shuffle(options)
    return {
        'question':          f'Какая часть речи у слова «{token.word}»?',
        'options':           options,
        'correct':           correct,
        'hint':              f'Лемма (начальная форма): {token.lemma}',
        'explanation':       f'«{token.word}» → {token.pos_ru}  (лемма: {token.lemma})',
        'category':          'pos',
        'sentence_context':  sentence.text,
        'target_word':       token.word,
    }


def _dep_question(token: Token, sentence: Sentence,
                  all_dep_ru: List[str]) -> Dict[str, Any]:
    correct = token.dep_ru
    distractors = [d for d in all_dep_ru if d != correct]
    random.shuffle(distractors)
    options = [correct] + distractors[:3]
    random.shuffle(options)
    return {
        'question':          f'Какую синтаксическую роль выполняет слово «{token.word}»?',
        'options':           options,
        'correct':           correct,
        'hint':              f'Часть речи: {token.pos_ru}',
        'explanation':       f'«{token.word}» выполняет роль: {token.dep_ru}',
        'category':          'dep',
        'sentence_context':  sentence.text,
        'target_word':       token.word,
    }


def _lemma_question(token: Token, sentence: Sentence) -> Optional[Dict[str, Any]]:
    if token.lemma.lower() == token.word.lower():
        return None
    fake_endings = ['ать', 'ить', 'ого', 'ому', 'ами', 'ах', 'ый', 'ой', 'ей', 'ев']
    base = token.lemma[:max(3, len(token.lemma) - 3)]
    distractors = list({base + e for e in fake_endings} - {token.lemma})
    random.shuffle(distractors)
    options = [token.lemma] + distractors[:3]
    for ex in [token.word + s for s in ('а', 'ов', 'е', 'и', 'у')]:
        if len(options) >= 4:
            break
        if ex not in options:
            options.append(ex)
    options = list(dict.fromkeys(options))[:4]
    if token.lemma not in options:
        options[0] = token.lemma
    random.shuffle(options)
    return {
        'question':          f'Какова начальная форма (лемма) слова «{token.word}»?',
        'options':           options,
        'correct':           token.lemma,
        'hint':              f'Часть речи: {token.pos_ru}',
        'explanation':       f'Начальная форма «{token.word}» → «{token.lemma}»',
        'category':          'lemma',
        'sentence_context':  sentence.text,
        'target_word':       token.word,
    }


def _fill_blank_question(token: Token, sentence: Sentence) -> Optional[Dict[str, Any]]:
    """Заполнить пропуск в предложении."""
    if len(token.word) < 3:
        return None
    distractors = [
        t.word for t in sentence.tokens
        if t.word != token.word and t.pos == token.pos and len(t.word) > 2
    ]
    if len(distractors) < 3:
        others = [t.word for t in sentence.tokens
                  if t.word != token.word and len(t.word) > 2 and t.word not in distractors]
        random.shuffle(others)
        distractors += others[:3 - len(distractors)]
    if len(distractors) < 3:
        return None
    random.shuffle(distractors)
    options = [token.word] + distractors[:3]
    options = list(dict.fromkeys(options))[:4]
    if len(options) < 4:
        return None
    random.shuffle(options)
    blank_text = sentence.text.replace(token.word, '_____', 1)
    return {
        'question':          f'Вставьте пропущенное слово:\n«{blank_text}»',
        'options':           options,
        'correct':           token.word,
        'hint':              f'Часть речи пропущенного слова: {token.pos_ru}',
        'explanation':       f'Пропущено слово «{token.word}»',
        'category':          'fill',
        'target_word':       token.word,
    }


def _match_question(pairs_src: List[tuple], sentence: Sentence) -> Optional[Dict[str, Any]]:
    """
    Сопоставление 4 слов → 4 частям речи.
    pairs_src: список кортежей (токен, предложение), из которого выбираем 4 с разными ЧР.
    """
    # Группируем по части речи
    by_pos: Dict[str, List[Token]] = {}
    for t, _s in pairs_src:
        if len(t.word) < 3:
            continue
        by_pos.setdefault(t.pos_ru, []).append(t)
    # Нужно не меньше 4 разных ЧР
    distinct_pos = [p for p, lst in by_pos.items() if lst]
    if len(distinct_pos) < 4:
        return None
    random.shuffle(distinct_pos)
    chosen_pos = distinct_pos[:4]
    pairs: List[tuple] = []
    for p in chosen_pos:
        tok = random.choice(by_pos[p])
        pairs.append((tok.word, p))
    random.shuffle(pairs)
    words = [w for w, _ in pairs]
    labels = [p for _, p in pairs]
    # Генерируем представление как набор пар
    return {
        'question':          'Сопоставьте каждое слово с его частью речи:',
        'options':           labels,     # используется движком UI для отрисовки кнопок-меток
        'correct':           'MATCH',    # спец-маркер: проверка идёт по pairs
        'pairs':             pairs,      # [(слово, правильная_часть_речи), ...]
        'hint':              'Выберите правильную часть речи для каждого слова.',
        'explanation':       'Правильные соответствия: ' + ', '.join(f'«{w}» → {l}' for w, l in pairs),
        'category':          'match',
        'sentence_context':  sentence.text if sentence else '',
        'target_word':       '',
    }


# ── Публичный API ─────────────────────────────────────────────────────────────

def generate_quiz(result: AnalysisResult, count: int = 10) -> List[Dict[str, Any]]:
    """
    Генерирует список вопросов.
    Гарантирует ровно один шуточный вопрос на тест (вставляется в случайную позицию).
    """
    interesting_pos = {'NOUN', 'VERB', 'ADJ', 'ADV', 'PRON', 'PROPN', 'NUM'}

    pairs = [
        (t, s)
        for s in result.sentences
        for t in s.tokens
        if t.pos in interesting_pos and len(t.word) > 2
    ]
    if not pairs:
        return []

    all_pos_ru = list(set(POS_RU.values()))
    all_dep_ru = list(set(DEP_RU.values()))

    questions: List[Dict[str, Any]] = []
    random.shuffle(pairs)
    used_words: set = set()

    # Оставляем место под шуточный вопрос: генерируем (count - 1) из текста
    text_count = max(count - 1, 1)

    # Бюджет по типам (приблизительный, дополняется вольно)
    pos_budget   = max(1, text_count * 3 // 10)
    dep_budget   = max(1, text_count * 2 // 10)
    lemma_budget = max(1, text_count * 2 // 10)
    fill_budget  = max(1, text_count * 2 // 10)
    match_budget = 1 if text_count >= 5 else 0

    # Сначала — один matching-вопрос, если есть данные
    if match_budget > 0:
        mq = _match_question(pairs, pairs[0][1] if pairs else None)
        if mq:
            questions.append(mq)
            match_budget = 0

    for token, sentence in pairs:
        if len(questions) >= text_count:
            break
        if token.word in used_words:
            continue
        used_words.add(token.word)

        if pos_budget > 0:
            questions.append(_pos_question(token, sentence, all_pos_ru))
            pos_budget -= 1
        elif dep_budget > 0:
            questions.append(_dep_question(token, sentence, all_dep_ru))
            dep_budget -= 1
        elif lemma_budget > 0:
            q = _lemma_question(token, sentence)
            if q:
                questions.append(q)
                lemma_budget -= 1
        elif fill_budget > 0:
            q = _fill_blank_question(token, sentence)
            if q:
                questions.append(q)
                fill_budget -= 1

    # Добираем pos/dep, если не хватает
    random.shuffle(pairs)
    for token, sentence in pairs:
        if len(questions) >= text_count:
            break
        if token.word in used_words:
            continue
        used_words.add(token.word)
        questions.append(
            _pos_question(token, sentence, all_pos_ru)
            if random.random() < 0.5
            else _dep_question(token, sentence, all_dep_ru)
        )

    random.shuffle(questions)
    questions = questions[:text_count]

    # Вставляем РОВНО ОДИН шуточный вопрос в случайную позицию
    joke = _make_joke_question()
    insert_pos = random.randint(0, len(questions))
    questions.insert(insert_pos, joke)

    return questions[:count]
