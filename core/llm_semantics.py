"""
llm_semantics.py — семантический анализ через Groq API.

Поддерживает сложные предложения: каждый предикат получает свою клаузу
со своими аргументами; клаузы связываются рёбрами (CONJUNCT, PURPOSE и т.д.).

Ключ читается из GROQ_API_KEY (.env в корне проекта или переменная окружения).
"""

from __future__ import annotations
import json
import os
import re
from pathlib import Path
from typing import Optional

from core.semantics import (
    SemanticGraph, SemNode, SemEdge,
    SEM_LABELS, ROLE_EDGE, SUBJ_ROLES,
)

GROQ_MODEL = 'llama-3.3-70b-versatile'

_VALID_ROLES    = set(SEM_LABELS.keys()) - {'PREDICATE', 'CONJUNCT'}
_VALID_RELATIONS = {'CONJUNCT', 'PURPOSE', 'CAUSE', 'CIRCUMSTANCE'}

# ── Загрузка .env ─────────────────────────────────────────────────────────────

def _load_env_file() -> None:
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        os.environ.setdefault(key.strip(), val.strip())

_load_env_file()


def get_api_key() -> str:
    return os.environ.get('GROQ_API_KEY', '')


# ── Системный промпт ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
Ты — эксперт по семантическому анализу русского языка.

Верни ТОЛЬКО валидный JSON без пояснений и без markdown-обёрток:
{
  "clauses": [
    {
      "predicate": {"word": "<словоформа>", "lemma": "<инфинитив>"},
      "roles": [
        {"role": "<РОЛЬ>", "word": "<словоформа>", "lemma": "<начальная форма>"}
      ],
      "linked_to": null
    }
  ]
}

════════════════════════════════════════════════════════════════════════════════
ШАГ 1 — ВЫПИШИ ВСЕ ГЛАГОЛЫ (мысленно, перед заполнением JSON)
════════════════════════════════════════════════════════════════════════════════
Перед тем как писать JSON, мысленно перечисли КАЖДЫЙ глагол в предложении:
личные глаголы (окутывает, кажется, замедляет, передаются...) И деепричастия
(давая, сохраняя, используя...). Каждый из них ОБЯЗАН стать отдельной клаузой.
ПРОПУСКАТЬ ГЛАГОЛЫ ЗАПРЕЩЕНО.

════════════════════════════════════════════════════════════════════════════════
ШАГ 2 — ОПРЕДЕЛИ РОЛЬ КАЖДОГО СЛОВА ПО ПАДЕЖУ
════════════════════════════════════════════════════════════════════════════════
Падеж определяет роль; не угадывай наугад:

  Им.п. (кто? что?) — это ПОДЛЕЖАЩЕЕ:
      одушевлённое  → AGENT   (студент, природа-субъект, они)
      неодушевлённое → FORCE  (мир, время, ветер, мгла)
      !! НИКОГДА не назначай Им.п. роль PATIENT !!

  Вин.п. (кого? что?) — прямой объект → PATIENT
  Дат.п. (кому? чему?) → RECIPIENT или EXPERIENCER
  Тв.п. с одушевл.    → COMITATIVE;  с неодушевл. → INSTRUMENT или MANNER
  Предл.п. (о ком? о чём?) → THEME или LOCATION
  Род.п. после существительного → GENITIVE
  Род.п. после предлога → см. таблицу предлогов ниже

════════════════════════════════════════════════════════════════════════════════
ШАГ 3 — ТОЛЬКО СЛОВА ИЗ ТЕКСТА, ТОЧНЫЕ ЛЕММЫ
════════════════════════════════════════════════════════════════════════════════
"word"  = точная словоформа из предложения (как написано).
"lemma" = начальная форма ЭТОГО ЖЕ слова.
ЗАПРЕЩЕНО: угадывать слово, заменять похожим, изменять смысл.

Примеры типичных ошибок (избегать!):
  «лощины»     → lemma "лощина"    (НЕ "лещина")
  «своеобразие»→ lemma "своеобразие" (НЕ "своевидный" — это другое слово!)
  «тепло»      → lemma "тепло"     (НЕ "тёплый")

════════════════════════════════════════════════════════════════════════════════
ШАГ 4 — ATTRIBUTE ТОЛЬКО ДЛЯ ПРИЛАГАТЕЛЬНЫХ, НЕ ДЛЯ СУЩЕСТВИТЕЛЬНЫХ
════════════════════════════════════════════════════════════════════════════════
ATTRIBUTE — исключительно прилагательные и причастия.
Существительные — НИКОГДА ATTRIBUTE, даже стоя рядом с прилагательным.

  «зеркальную гладь» → "зеркальную" = ATTRIBUTE (прил.), "гладь" = PATIENT (сущ.)
  «лесных озер»      → "лесных" = ATTRIBUTE (прил.),     "озер"  = GENITIVE (сущ.)
  «туманные часы»    → "туманные" = ATTRIBUTE,           "часы"  = TIME (сущ.)

════════════════════════════════════════════════════════════════════════════════
ШАГ 5 — ПОЛНОТА: КАЖДОЕ СЛОВО ДОЛЖНО БЫТЬ В ROLES
════════════════════════════════════════════════════════════════════════════════
После заполнения clauses пройдись по каждому знаменательному слову предложения
(существительные, прилагательные, наречия, местоимения, числительные) и убедись,
что каждое попало в какой-нибудь roles. Ни одно не должно остаться за бортом.

  Однородные объекты (X и Y) → отдельный элемент для КАЖДОГО:
    НЕВЕРНО: {"role": "PATIENT", "word": "радость и тепло", ...}
    ВЕРНО:   {"role": "PATIENT", "word": "радость", ...},
             {"role": "PATIENT", "word": "тепло",   ...}

  Существительное в Род.п., зависящее от другого сущ. → GENITIVE:
    «радость открытий» → "открытий" = GENITIVE
    «гладь озёр»       → "озёр"     = GENITIVE
    «бег времени»      → "времени"  = GENITIVE

  Прилагательное при существительном → ATTRIBUTE:
    «туманные часы»    → "туманные"   = ATTRIBUTE
    «зеркальную гладь» → "зеркальную" = ATTRIBUTE

  Деепричастный оборот (давая, сохраняя...) → отдельная клауза с CIRCUMSTANCE:
    «давая возможность природе перевести дыхание»
    → clause {predicate "давая/давать", roles [...], linked_to: {relation: "CIRCUMSTANCE"}}

════════════════════════════════════════════════════════════════════════════════
СВЯЗИ МЕЖДУ КЛАУЗАМИ
════════════════════════════════════════════════════════════════════════════════
linked_to: {"clause_index": <индекс>, "relation": "<СВЯЗЬ>"}
Допустимые relation:
  CONJUNCT    — однородные личные глаголы (и ... и ...)
  PURPOSE     — придаточное цели (чтобы + инфинитив)
  CAUSE       — причина (потому что, так как)
  CIRCUMSTANCE — деепричастный оборот, обстоятельственное придаточное

Общий АГЕНТ/СИЛА цепочки однородных предикатов — только у ПЕРВОГО предиката.

════════════════════════════════════════════════════════════════════════════════
ЕСЛИ ВХОДНАЯ СТРОКА — заголовок, имя или фрагмент без глагола
════════════════════════════════════════════════════════════════════════════════
Верни: {"clauses": []}

════════════════════════════════════════════════════════════════════════════════
РОЛИ
════════════════════════════════════════════════════════════════════════════════
AGENT       — одушевлённый деятель / подлежащее (Им.п., одушевлённое)
FORCE       — неодушевлённый причинитель / подлежащее (Им.п., неодушевлённое)
PATIENT     — прямой объект (Вин.п.)
THEME       — тема / содержание (Предл.п. после «о»)
RECIPIENT   — получатель, адресат (Дат.п., одушевлённое)
BENEFICIARY — бенефициар (в чью пользу; «вам», «нам» без движения)
EXPERIENCER — переживающий (при казаться, нравиться, хотеться)
STIMULUS    — стимул переживания
INSTRUMENT  — орудие, средство (Тв.п., неодушевлённое)
LOCATION    — место нахождения (где)
SOURCE      — источник / откуда
GOAL        — направление / куда
TIME        — временной ориентир
PURPOSE     — цель (зачем / для чего; «для X», «чтобы»)
CAUSE       — причина (из-за чего / благодаря чему)
MANNER      — образ действия (как; наречия типа «плотно», «вновь», «медленно»)
COMITATIVE  — совместность (Тв.п., одушевлённое)
ATTRIBUTE   — прилагательное / причастие при существительном
GENITIVE    — зависимое существительное в Род.п.
CIRCUMSTANCE — прочее обстоятельство

════════════════════════════════════════════════════════════════════════════════
ПРЕДЛОГИ → РОЛИ
════════════════════════════════════════════════════════════════════════════════
из, от, с(+Род.п.)           → SOURCE
к, ко(+Дат.п.)               → GOAL
в, на(+Вин.п.)               → GOAL      (движение куда)
в, на(+Предл.п.)             → LOCATION  (нахождение где)
с(+Тв.п.) + одушевл.         → COMITATIVE
с(+Тв.п.) + неодушевл.       → INSTRUMENT
для, ради                    → PURPOSE
из-за, благодаря, вследствие → CAUSE
через, после, до, во время, перед → TIME
у, около, рядом, над, под    → LOCATION

════════════════════════════════════════════════════════════════════════════════
ПРИМЕР (полный разбор: два личных глагола + деепричастие)
════════════════════════════════════════════════════════════════════════════════
Вход: «Молодой студент принёс книгу истории и тетрадь из библиотеки, радуясь новым знаниям.»
{
  "clauses": [
    {
      "predicate": {"word": "принёс", "lemma": "принести"},
      "roles": [
        {"role": "AGENT",     "word": "студент",    "lemma": "студент"},
        {"role": "ATTRIBUTE", "word": "молодой",    "lemma": "молодой"},
        {"role": "PATIENT",   "word": "книгу",      "lemma": "книга"},
        {"role": "GENITIVE",  "word": "истории",    "lemma": "история"},
        {"role": "PATIENT",   "word": "тетрадь",    "lemma": "тетрадь"},
        {"role": "SOURCE",    "word": "библиотеки", "lemma": "библиотека"}
      ],
      "linked_to": null
    },
    {
      "predicate": {"word": "радуясь", "lemma": "радоваться"},
      "roles": [
        {"role": "STIMULUS",  "word": "знаниям",  "lemma": "знание"},
        {"role": "ATTRIBUTE", "word": "новым",    "lemma": "новый"}
      ],
      "linked_to": {"clause_index": 0, "relation": "CIRCUMSTANCE"}
    }
  ]
}

════════════════════════════════════════════════════════════════════════════════
ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА (итог)
════════════════════════════════════════════════════════════════════════════════
1. НЕ включай глагол-предикат в список roles своей клаузы.
2. Им.п. = AGENT или FORCE — никогда не PATIENT.
3. Каждый глагол (личный и деепричастие) — отдельный predicate.
4. Lemma = точная начальная форма слова из текста; не изобретай.
5. ATTRIBUTE — только прилагательные/причастия, не существительные.
6. Каждое знаменательное слово — в roles хотя бы одной клаузы.
7. Предлоги, союзы, частицы, знаки препинания — НЕ включать.
8. Отвечай ТОЛЬКО JSON.
"""


# ── Внутренние утилиты ────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    text = text.strip()
    # убираем ```json ... ```
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.M)
    text = re.sub(r'\s*```\s*$', '', text, flags=re.M)
    # ищем первый {...}
    m = re.search(r'\{[\s\S]*\}', text)
    if not m:
        raise ValueError('Модель не вернула JSON-объект')
    return json.loads(m.group())


def _build_graph(sentence_text: str, data: dict) -> SemanticGraph:
    """
    Строит SemanticGraph из dict с ключом 'clauses'.
    Поддерживает устаревший формат {'predicate': ..., 'roles': [...]}.
    """
    graph = SemanticGraph(sentence_text=sentence_text)
    nid = 0

    # Нормализуем к единому формату
    clauses = data.get('clauses')
    if not isinstance(clauses, list):
        clauses = []
    if not clauses and 'predicate' in data:
        # Старый формат — оборачиваем
        clauses = [{'predicate': data['predicate'],
                    'roles': data.get('roles', []),
                    'linked_to': None}]

    if not clauses:
        return graph  # заголовок / фрагмент без предиката

    # ── Проход 1: создаём узлы-предикаты ────────────────────────────────────
    pred_nid: dict[int, int] = {}   # clause_index → node.id

    for ci, clause in enumerate(clauses):
        info = clause.get('predicate') or {}
        word  = str(info.get('word',  '') or '').strip()
        lemma = str(info.get('lemma', '') or word).lower().strip()
        if not word:
            word = sentence_text.split()[0] if sentence_text.split() else '?'
        if not lemma:
            lemma = word.lower()

        node = SemNode(
            id=nid, lemma=lemma, word=word, pos='VERB',
            role='PREDICATE', role_ru=SEM_LABELS['PREDICATE'], is_predicate=True,
        )
        graph.nodes.append(node)
        pred_nid[ci] = nid
        if ci == 0:
            graph.predicate_id = nid
        nid += 1

    # Множество слов предикатов (для фильтрации самоссылок)
    pred_words = {n.word.lower() for n in graph.nodes if n.is_predicate}
    pred_words |= {n.lemma.lower() for n in graph.nodes if n.is_predicate}

    # ── Проход 2: создаём узлы-аргументы и рёбра ────────────────────────────
    for ci, clause in enumerate(clauses):
        clause_pred = pred_nid[ci]

        for item in clause.get('roles') or []:
            word  = str(item.get('word',  '') or '').strip()
            lemma = str(item.get('lemma', '') or word).lower().strip()

            # Пропускаем пустые и самоссылки (Геракл→Геракл)
            if not word or word.lower() in pred_words or lemma in pred_words:
                continue

            role = str(item.get('role', 'CIRCUMSTANCE')).upper()
            if role not in _VALID_ROLES:
                role = 'CIRCUMSTANCE'

            node = SemNode(id=nid, lemma=lemma, word=word, pos='NOUN',
                           role=role, role_ru=SEM_LABELS[role])
            graph.nodes.append(node)

            e_lbl, e_lbl_ru = ROLE_EDGE.get(role, ('adverb_of', 'обстоятельство'))
            if role in SUBJ_ROLES:
                graph.edges.append(SemEdge(src=nid, dst=clause_pred,
                                           label=e_lbl, label_ru=e_lbl_ru))
            else:
                graph.edges.append(SemEdge(src=clause_pred, dst=nid,
                                           label=e_lbl, label_ru=e_lbl_ru))
            nid += 1

        # ── Межклаузальное ребро ─────────────────────────────────────────────
        linked = clause.get('linked_to')
        if isinstance(linked, dict):
            target_ci  = int(linked.get('clause_index', 0))
            relation   = str(linked.get('relation', 'CONJUNCT')).upper()
            if relation not in _VALID_RELATIONS:
                relation = 'CONJUNCT'
            target_nid = pred_nid.get(target_ci)
            if target_nid is not None and target_nid != pred_nid[ci]:
                e_lbl, e_lbl_ru = ROLE_EDGE.get(relation, ('conjoins', 'однородно'))
                graph.edges.append(SemEdge(
                    src=pred_nid[ci], dst=target_nid,
                    label=e_lbl, label_ru=e_lbl_ru, dep='conj',
                ))

    return graph


# ── Публичный API ─────────────────────────────────────────────────────────────

def analyze_with_groq(sentence_text: str, model: str = GROQ_MODEL) -> SemanticGraph:
    """
    Анализирует предложение через Groq и возвращает SemanticGraph.
    Ключ берётся из GROQ_API_KEY (задаётся в .env или переменных окружения).
    """
    from groq import Groq

    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            'GROQ_API_KEY не задан.\n'
            'Добавьте строку  GROQ_API_KEY=ваш_ключ  в файл .env в корне проекта.'
        )

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user',   'content': f'Предложение: {sentence_text}'},
        ],
        temperature=0.0,   # детерминированный вывод
        max_tokens=2048,
    )

    raw = response.choices[0].message.content or ''
    data = _extract_json(raw)
    return _build_graph(sentence_text, data)


def is_groq_available() -> bool:
    try:
        import groq  # noqa: F401
        return True
    except ImportError:
        return False


def is_api_key_set() -> bool:
    return bool(get_api_key())
