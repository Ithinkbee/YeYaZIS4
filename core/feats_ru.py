"""
feats_ru.py — русские названия для Universal Dependencies морфологических признаков.
"""

FEAT_NAME_RU = {
    'Animacy':    'Одушевл.',
    'Aspect':     'Вид',
    'Case':       'Падеж',
    'Degree':     'Степень',
    'Gender':     'Род',
    'Mood':       'Наклонение',
    'Number':     'Число',
    'Person':     'Лицо',
    'Polarity':   'Полярность',
    'Tense':      'Время',
    'VerbForm':   'Форма гл.',
    'Voice':      'Залог',
    'Foreign':    'Иностр.',
    'Hyph':       'Дефис',
    'NumType':    'Тип числ.',
    'Poss':       'Притяж.',
    'Reflex':     'Возвратн.',
    'Variant':    'Вариант',
}

FEAT_VAL_RU = {
    # Animacy
    'Anim':   'одуш.',
    'Inan':   'неодуш.',
    # Aspect
    'Imp':    'несов.',
    'Perf':   'сов.',
    # Case
    'Nom':    'Им.',
    'Gen':    'Род.',
    'Dat':    'Дат.',
    'Acc':    'Вин.',
    'Ins':    'Тв.',
    'Loc':    'Пред.',
    'Voc':    'Зват.',
    # Degree
    'Pos':    'полож.',
    'Cmp':    'сравн.',
    'Sup':    'превосх.',
    # Gender
    'Masc':   'муж.',
    'Fem':    'жен.',
    'Neut':   'ср.',
    # Mood
    'Ind':    'изъявит.',
    'Imp':    'повелит.',
    'Cnd':    'условн.',
    # Number
    'Sing':   'ед.ч.',
    'Plur':   'мн.ч.',
    # Person
    '1':      '1 л.',
    '2':      '2 л.',
    '3':      '3 л.',
    # Polarity
    'Neg':    'отриц.',
    'Pos':    'полож.',
    # Tense
    'Past':   'прош.',
    'Pres':   'наст.',
    'Fut':    'буд.',
    # VerbForm
    'Fin':    'личн.',
    'Inf':    'инфинит.',
    'Part':   'прич.',
    'Conv':   'дееприч.',
    # Voice
    'Act':    'действит.',
    'Mid':    'средний',
    'Pass':   'страдат.',
    # NumType
    'Card':   'колич.',
    'Ord':    'поряд.',
    # misc
    'Yes':    'да',
}


def feats_to_ru(feats: dict) -> str:
    """Переводит словарь признаков в читаемую русскую строку."""
    if not feats:
        return ''
    parts = []
    for key, val in feats.items():
        k_ru = FEAT_NAME_RU.get(key, key)
        v_ru = FEAT_VAL_RU.get(val, val)
        parts.append(f'{k_ru}: {v_ru}')
    return ', '.join(parts)