"""
llm_semantics.py — семантический анализ через Groq API (модель Google Gemma 2).

Ключ читается из переменной окружения GROQ_API_KEY.
Если в корне проекта лежит файл .env — он загружается автоматически.
"""

from __future__ import annotations
import json
import os
import re
from pathlib import Path

from core.semantics import (
    SemanticGraph, SemNode, SemEdge,
    SEM_LABELS, ROLE_EDGE, SUBJ_ROLES,
)

GROQ_MODEL = 'llama-3.3-70b-versatile'

_VALID_ROLES = set(SEM_LABELS.keys()) - {'PREDICATE', 'CONJUNCT'}

# ── Загрузка .env ─────────────────────────────────────────────────────────────

def _load_env_file() -> None:
    """Парсит .env в корне проекта и добавляет переменные в os.environ."""
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
    """Возвращает GROQ_API_KEY из окружения или пустую строку."""
    return os.environ.get('GROQ_API_KEY', '')


# ── Системный промпт ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
Ты — эксперт по семантическому анализу русского языка.
Проанализируй предложение и верни ТОЛЬКО валидный JSON (без пояснений, без markdown) в формате:
{
  "predicate": {"word": "<словоформа>", "lemma": "<начальная форма>"},
  "roles": [
    {"role": "<РОЛЬ>", "word": "<словоформа>", "lemma": "<начальная форма>"}
  ]
}

Допустимые значения role (используй ТОЛЬКО эти константы):
AGENT       — одушевлённый деятель (кто выполняет действие)
FORCE       — неодушевлённый причинитель (что вызывает действие)
PATIENT     — прямой объект действия (на кого/что направлено)
THEME       — тема / содержание высказывания
RECIPIENT   — получатель / адресат
BENEFICIARY — бенефициар (в чью пользу)
EXPERIENCER — переживающий (при нравиться, казаться и т.п.)
STIMULUS    — стимул переживания (что нравится / кажется)
INSTRUMENT  — орудие / средство
LOCATION    — место события
SOURCE      — источник / исходная точка (откуда)
GOAL        — направление / конечная точка (куда / к кому)
TIME        — временной ориентир
PURPOSE     — цель / назначение
CAUSE       — причина / основание
MANNER      — образ действия
COMITATIVE  — совместность (вместе с кем)
ATTRIBUTE   — признак / определение
GENITIVE    — принадлежность
CIRCUMSTANCE — прочее обстоятельство

Правила:
1. НЕ включай предикат в список roles.
2. Каждое смысловое слово — отдельный элемент roles.
3. Предлоги, союзы, знаки препинания не включай.
4. Если роль неоднозначна — выбери наиболее вероятную.
5. Отвечай ТОЛЬКО JSON, никакого текста вокруг.
"""


# ── Внутренние утилиты ────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    m = re.search(r'\{[\s\S]*\}', text)
    if not m:
        raise ValueError('Модель не вернула JSON')
    return json.loads(m.group())


def _build_graph(sentence_text: str, data: dict) -> SemanticGraph:
    graph = SemanticGraph(sentence_text=sentence_text)
    nid = 0

    pred_info  = data.get('predicate') or {}
    pred_word  = str(pred_info.get('word',  '') or sentence_text.split()[0])
    pred_lemma = str(pred_info.get('lemma', '') or pred_word.lower())

    pred_node = SemNode(
        id=nid, lemma=pred_lemma, word=pred_word, pos='VERB',
        role='PREDICATE', role_ru=SEM_LABELS['PREDICATE'], is_predicate=True,
    )
    graph.nodes.append(pred_node)
    graph.predicate_id = nid
    nid += 1

    for item in data.get('roles', []):
        role = str(item.get('role', 'CIRCUMSTANCE')).upper()
        if role not in _VALID_ROLES:
            role = 'CIRCUMSTANCE'

        node = SemNode(
            id=nid,
            lemma=str(item.get('lemma', '') or item.get('word', '')).lower(),
            word=str(item.get('word', '')),
            pos='NOUN', role=role, role_ru=SEM_LABELS[role],
        )
        graph.nodes.append(node)

        edge_label, edge_label_ru = ROLE_EDGE.get(role, ('adverb_of', 'обстоятельство'))
        if role in SUBJ_ROLES:
            graph.edges.append(SemEdge(src=nid, dst=pred_node.id,
                                       label=edge_label, label_ru=edge_label_ru))
        else:
            graph.edges.append(SemEdge(src=pred_node.id, dst=nid,
                                       label=edge_label, label_ru=edge_label_ru))
        nid += 1

    return graph


# ── Публичный API ─────────────────────────────────────────────────────────────

def analyze_with_groq(sentence_text: str, model: str = GROQ_MODEL) -> SemanticGraph:
    """
    Отправляет предложение в Groq и возвращает SemanticGraph.
    Ключ читается из GROQ_API_KEY (задаётся в .env или переменных окружения).
    """
    from groq import Groq

    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            'GROQ_API_KEY не задан.\n'
            'Добавьте строку GROQ_API_KEY=ваш_ключ в файл .env в корне проекта.'
        )

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user',   'content': f'Предложение: {sentence_text}'},
        ],
        temperature=0.1,
        max_tokens=1024,
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
