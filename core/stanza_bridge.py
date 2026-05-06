"""
stanza_bridge.py — адаптер парсера Stanza (Stanford NLP).

Возвращает List[Sentence] в том же формате, что и analyzer.py,
позволяя использовать Stanza как альтернативный синтаксический парсер
с более высокой точностью для сложных русских предложений.

Первый вызов скачивает модель (~165 MB) однократно.
"""

from __future__ import annotations
from typing import List, Optional
from core.analyzer import Sentence, Token, POS_RU, DEP_RU

_stanza_nlp = None   # ленивая инициализация


def _get_stanza_nlp():
    global _stanza_nlp
    if _stanza_nlp is None:
        import stanza
        stanza.download('ru', logging_level='ERROR')
        _stanza_nlp = stanza.Pipeline(
            'ru',
            processors='tokenize,pos,lemma,depparse',
            logging_level='ERROR',
        )
    return _stanza_nlp


def get_stanza_sentences(text: str) -> List[Sentence]:
    """
    Парсит текст через Stanza и возвращает List[Sentence] в формате analyzer.py.
    Совместим с build_semantic_graph() из semantics.py.
    """
    import re
    text = re.sub(r'\r\n', '\n', text).strip()
    nlp = _get_stanza_nlp()
    doc = nlp(text)
    result = []
    for si, stanza_sent in enumerate(doc.sentences):
        tokens: List[Token] = []
        for word in stanza_sent.words:
            # Пропускаем мульти-токенные слова (MWT) — они имеют tuple id
            if not isinstance(word.id, int):
                continue
            tok_id = word.id - 1                          # 1-based → 0-based
            head_id = (word.head - 1) if word.head > 0 else tok_id

            # Разбираем строку морфологических признаков "Case=Acc|Number=Sing"
            feats: dict = {}
            if word.feats:
                for pair in word.feats.split('|'):
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        feats[k] = v

            pos = word.upos or 'X'
            dep = word.deprel or 'dep'

            tokens.append(Token(
                id=tok_id,
                sentence_id=si,
                word=word.text,
                lemma=word.lemma or word.text.lower(),
                pos=pos,
                pos_ru=POS_RU.get(pos, pos),
                dep=dep,
                dep_ru=DEP_RU.get(dep, dep),
                head_id=head_id,
                feats=feats,
            ))
        result.append(Sentence(id=si, text=stanza_sent.text, tokens=tokens))
    return result


def is_stanza_available() -> bool:
    """Проверяет, установлен ли пакет stanza."""
    try:
        import stanza  # noqa: F401
        return True
    except ImportError:
        return False


def is_stanza_model_ready() -> bool:
    """Проверяет, загружена ли модель (без попытки скачать)."""
    if not is_stanza_available():
        return False
    try:
        import stanza
        import os
        model_dir = os.path.join(stanza.resources.common.DEFAULT_MODEL_DIR, 'ru')
        return os.path.isdir(model_dir)
    except Exception:
        return False
