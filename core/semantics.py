"""
semantics.py — семантический анализ предложения (расширенная версия).

"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Tuple

from core.analyzer import Sentence, Token
import pymorphy2

_morph_analyzer = pymorphy2.MorphAnalyzer()

# ── Синтаксические группы зависимостей (Universal Dependencies) ───────────────

SUBJ_DEPS   = {'nsubj', 'nsubj:pass'}
OBJ_DEPS    = {'obj', 'iobj'}
OBL_DEPS    = {'obl', 'obl:agent'}
NMOD_DEPS   = {'nmod', 'nmod:poss'}
ADV_DEPS    = {'advmod'}
MOD_DEPS    = {'amod', 'nummod'}
CONJ_DEPS   = {'conj'}
CLAUSE_DEPS = {'advcl', 'ccomp', 'xcomp', 'acl', 'acl:relcl', 'parataxis'}
FLAT_DEPS   = {'flat', 'flat:name'}

# В NP-поле word включаем и детерминативы
NP_MOD_DEPS = {'amod', 'nummod', 'det'}

SKIP_DEPS = {
    'punct', 'cc', 'case', 'mark', 'aux', 'aux:pass', 'cop',
    'fixed', 'goeswith', 'list', 'discourse', 'dep', 'vocative', 'det',
}

CONTENT_POS = {'NOUN', 'VERB', 'ADJ', 'ADV', 'PROPN', 'NUM', 'PRON'}
PRED_POS    = {'VERB', 'AUX'}

# ── Экспериентивные глаголы (при них Dat-аргумент = EXPERIENCER) ──────────────

EXPERIENTIAL_VERBS: Set[str] = {
    'нравиться', 'понравиться', 'нравится', 'нравился', 'нравилось',
    'казаться', 'показаться', 'казался', 'казалось',
    'хотеться', 'хочется', 'хотелось',
    'нуждаться',
    'мерещиться', 'чудиться', 'мниться', 'привидеться',
    'удаваться', 'удаётся', 'удавалось', 'удаться',
    'везти', 'повезти',
    'надоедать', 'надоесть', 'надоедаться',
    'доставаться', 'достаться',
    'везти', 'подвезти',
    'нравиться', 'приходиться', 'прийтись',
}

# ── Творительные формы наречного происхождения (не INSTRUMENT) ───────────────

ADVERB_INSTRUMENTALS: Set[str] = {
    'шёпотом', 'бегом', 'шагом', 'галопом', 'рысью', 'ходом',
    'кубарем', 'клубком', 'вихрем', 'потоком', 'волной', 'лентой',
    'хором', 'толпой', 'стаей', 'роем', 'стадом', 'гурьбой',
    'рядами', 'цепочкой', 'гуськом', 'колонной',
    'образом', 'способом', 'путём', 'методом', 'средством',
    'силой', 'правдой', 'лаской', 'добром', 'злом',
    'случаем', 'образом', 'чудом', 'даром',
}

# ── Предлоги → семантические роли ────────────────────────────────────────────

PREP_ROLE: Dict[str, str] = {
    # МЕСТО (однозначные)
    'у':          'LOCATION',
    'около':      'LOCATION',
    'рядом':      'LOCATION',
    'позади':     'LOCATION',
    'под':        'LOCATION',
    'над':        'LOCATION',
    'между':      'LOCATION',
    'меж':        'LOCATION',
    'среди':      'LOCATION',
    'вокруг':     'LOCATION',
    'внутри':     'LOCATION',
    'вне':        'LOCATION',
    'возле':      'LOCATION',
    'близ':       'LOCATION',
    'подле':      'LOCATION',
    'напротив':   'LOCATION',
    'вблизи':     'LOCATION',
    'вдоль':      'LOCATION',
    'поперёк':    'LOCATION',
    'сквозь':     'LOCATION',
    'мимо':       'LOCATION',
    # ВРЕМЯ (однозначные)
    'через':      'TIME',
    'после':      'TIME',
    'накануне':   'TIME',
    'спустя':     'TIME',
    'прежде':     'TIME',
    'вплоть':     'TIME',
    # ЦЕЛЬ
    'для':        'PURPOSE',
    'ради':       'PURPOSE',
    # ПРИЧИНА
    'из-за':      'CAUSE',
    'благодаря':  'CAUSE',
    'вследствие': 'CAUSE',
    'ввиду':      'CAUSE',
    'вопреки':    'CAUSE',
    'несмотря':   'CAUSE',
    # ИСТОЧНИК
    'из':         'SOURCE',
    'от':         'SOURCE',
    # НАПРАВЛЕНИЕ
    'к':          'GOAL',
    'ко':         'GOAL',
}

# Леммы существительных временного значения
TIME_LEMMAS: Set[str] = {
    'год', 'месяц', 'день', 'час', 'минута', 'секунда', 'неделя',
    'эпоха', 'период', 'момент', 'пора', 'время', 'срок', 'сезон',
    'утро', 'вечер', 'ночь', 'полдень', 'полночь', 'рассвет', 'закат',
    'весна', 'лето', 'осень', 'зима', 'сутки', 'будни', 'праздник',
    'понедельник', 'вторник', 'среда', 'четверг', 'пятница',
    'суббота', 'воскресенье', 'январь', 'февраль', 'март', 'апрель',
    'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь',
    'ноябрь', 'декабрь', 'век', 'столетие', 'десятилетие', 'эра',
    'квартал', 'полугодие', 'тысячелетие', 'сумерки',
    'обед', 'ужин', 'завтрак', 'перемена', 'каникулы', 'перерыв',
}

TIME_ADVS: Set[str] = {
    'сегодня', 'вчера', 'завтра', 'тогда', 'сейчас', 'теперь',
    'прежде', 'раньше', 'позже', 'потом', 'затем', 'недавно',
    'скоро', 'вскоре', 'наконец', 'давно', 'всегда', 'иногда',
    'часто', 'редко', 'никогда', 'ежедневно', 'ночью', 'утром',
    'вечером', 'днём', 'постоянно', 'временно', 'однажды', 'впредь',
    'нынче', 'намедни', 'позавчера', 'послезавтра', 'ныне',
    'долго', 'немедленно', 'мгновенно', 'тотчас', 'вмиг', 'уже',
    'ещё', 'скоро', 'вдруг', 'сначала', 'напоследок',
}

LOCATION_ADVS: Set[str] = {
    'здесь', 'там', 'тут', 'везде', 'нигде', 'повсюду',
    'слева', 'справа', 'вверху', 'внизу', 'впереди', 'сзади',
    'дома', 'домой', 'вдали', 'поблизости', 'рядом', 'далеко',
    'близко', 'всюду', 'повсеместно', 'отовсюду', 'снаружи',
    'посередине', 'наверху', 'снизу', 'сюда', 'туда', 'отсюда',
    'оттуда', 'куда', 'откуда', 'нигде', 'везде',
}

MANNER_ADVS: Set[str] = {
    'быстро', 'медленно', 'тихо', 'громко', 'легко', 'трудно',
    'хорошо', 'плохо', 'прекрасно', 'ужасно', 'внимательно',
    'осторожно', 'аккуратно', 'небрежно', 'спокойно', 'смело',
    'уверенно', 'робко', 'открыто', 'честно', 'вежливо', 'грубо',
    'сильно', 'слабо', 'весело', 'грустно', 'старательно', 'лениво',
    'усердно', 'внезапно', 'неожиданно', 'плавно', 'резко', 'грациозно',
    'живо', 'вяло', 'бегло', 'насилу', 'едва', 'почти', 'совсем',
    'совместно', 'вместе', 'сообща', 'пешком', 'верхом', 'тайно',
    'явно', 'открыто', 'молча', 'вслух', 'ясно', 'чётко', 'верно',
}


# ── Семантические метки ───────────────────────────────────────────────────────

SEM_LABELS: Dict[str, str] = {
    'PREDICATE':    'Действие',
    'AGENT':        'Агент',
    'FORCE':        'Каузатор',
    'PATIENT':      'Объект',
    'THEME':        'Тема',
    'RECIPIENT':    'Получатель',
    'BENEFICIARY':  'Бенефициар',
    'EXPERIENCER':  'Переживающий',
    'STIMULUS':     'Стимул',
    'INSTRUMENT':   'Инструмент',
    'ATTRIBUTE':    'Признак',
    'LOCATION':     'Место',
    'SOURCE':       'Источник',
    'GOAL':         'Направление',
    'TIME':         'Время',
    'PURPOSE':      'Цель',
    'CAUSE':        'Причина',
    'MANNER':       'Образ действия',
    'COMITATIVE':   'Совместность',
    'GENITIVE':     'Принадлежность',
    'CIRCUMSTANCE': 'Обстоятельство',
    'CONJUNCT':     'Однородный',
}

EDGE_LABELS: Dict[str, str] = {
    'agent_of':       'субъект',
    'force_of':       'каузатор',
    'patient_of':     'объект',
    'theme_of':       'тема',
    'recipient_of':   'получатель',
    'beneficiary_of': 'бенефициар',
    'experiencer_of': 'переживающий',
    'stimulus_of':    'стимул',
    'instrument_of':  'инструмент',
    'has_attr':       'признак',
    'location_of':    'место',
    'source_of':      'источник',
    'goal_of':        'направление',
    'time_of':        'время',
    'purpose_of':     'цель',
    'cause_of':       'причина',
    'manner_of':      'образ',
    'comitative_of':  'совместно',
    'genitive_of':    'принадлежность',
    'adverb_of':      'обстоятельство',
    'conjoins':       'однородно',
    'clause_of':      'клауза',
}

# Роль → (метка ребра, её русское название)
ROLE_EDGE: Dict[str, Tuple[str, str]] = {
    'AGENT':        ('agent_of',       EDGE_LABELS['agent_of']),
    'FORCE':        ('force_of',       EDGE_LABELS['force_of']),
    'PATIENT':      ('patient_of',     EDGE_LABELS['patient_of']),
    'THEME':        ('theme_of',       EDGE_LABELS['theme_of']),
    'RECIPIENT':    ('recipient_of',   EDGE_LABELS['recipient_of']),
    'BENEFICIARY':  ('beneficiary_of', EDGE_LABELS['beneficiary_of']),
    'EXPERIENCER':  ('experiencer_of', EDGE_LABELS['experiencer_of']),
    'STIMULUS':     ('stimulus_of',    EDGE_LABELS['stimulus_of']),
    'INSTRUMENT':   ('instrument_of',  EDGE_LABELS['instrument_of']),
    'ATTRIBUTE':    ('has_attr',       EDGE_LABELS['has_attr']),
    'LOCATION':     ('location_of',    EDGE_LABELS['location_of']),
    'SOURCE':       ('source_of',      EDGE_LABELS['source_of']),
    'GOAL':         ('goal_of',        EDGE_LABELS['goal_of']),
    'TIME':         ('time_of',        EDGE_LABELS['time_of']),
    'PURPOSE':      ('purpose_of',     EDGE_LABELS['purpose_of']),
    'CAUSE':        ('cause_of',       EDGE_LABELS['cause_of']),
    'MANNER':       ('manner_of',      EDGE_LABELS['manner_of']),
    'COMITATIVE':   ('comitative_of',  EDGE_LABELS['comitative_of']),
    'GENITIVE':     ('genitive_of',    EDGE_LABELS['genitive_of']),
    'CIRCUMSTANCE': ('adverb_of',      EDGE_LABELS['adverb_of']),
    'CONJUNCT':     ('conjoins',       EDGE_LABELS['conjoins']),
    'PREDICATE':    ('clause_of',      EDGE_LABELS['clause_of']),
}

# Роли, в которых субъект направляет ребро к предикату (а не наоборот)
SUBJ_ROLES = {'AGENT', 'FORCE', 'EXPERIENCER'}


# ── Датаклассы ────────────────────────────────────────────────────────────────

@dataclass
class SemNode:
    id: int
    lemma: str
    word: str
    pos: str
    role: str
    role_ru: str
    is_predicate: bool = False
    implied: bool = False


@dataclass
class SemEdge:
    src: int
    dst: int
    label: str
    label_ru: str
    dep: str = ''


@dataclass
class SemanticGraph:
    sentence_text: str
    nodes: List[SemNode] = field(default_factory=list)
    edges: List[SemEdge] = field(default_factory=list)
    predicate_id: Optional[int] = None

    def node_by_id(self, nid: int) -> Optional[SemNode]:
        for n in self.nodes:
            if n.id == nid:
                return n
        return None


# ── Построитель семантического графа ─────────────────────────────────────────

class SemanticGraphBuilder:
    """
    Полный рекурсивный обход дерева зависимостей с расширенной семантической
    классификацией ролей. Использует pymorphy2 для анализа одушевлённости,
    падежную информацию из feats-словаря и словарь экспериентивных глаголов.
    """

    def __init__(self):
        self._morph = _morph_analyzer

    # ── Публичный метод ───────────────────────────────────────────────────────

    def build(self, sentence: Sentence) -> SemanticGraph:
        toks = {t.id: t for t in sentence.tokens}
        graph = SemanticGraph(sentence_text=sentence.text)

        root = self._find_root(sentence.tokens)
        if root is None:
            return graph

        added_ids:    Set[int] = set()
        absorbed_ids: Set[int] = set()

        # flat/flat:name токены поглощаются головным узлом (для имён собств.)
        for t in sentence.tokens:
            if t.dep in FLAT_DEPS:
                absorbed_ids.add(t.id)

        self._process_node(
            tok=root, parent_node=None, dep_key='root',
            sentence=sentence, toks=toks, graph=graph,
            added_ids=added_ids, absorbed_ids=absorbed_ids, depth=0,
        )
        graph.predicate_id = root.id
        self._add_implied_subjects(graph, sentence, toks)
        self._share_conj_args(graph, sentence, toks)
        return graph

    # ── Морфологические помощники ─────────────────────────────────────────────

    def _is_animate(self, tok: Token) -> bool:
        """Одушевлённость: feats парсера → pymorphy2 → дефолт для местоимений."""
        feats = tok.feats or {}
        feat_anim = feats.get('Animacy', '')
        if feat_anim == 'Anim':
            return True
        if feat_anim == 'Inan':
            return False
        # Личные и возвратные местоимения всегда одушевлённые
        # (pymorphy2 возвращает None для NPRO, поэтому нужен отдельный случай)
        if tok.pos == 'PRON':
            return True
        lemma = (tok.lemma or tok.word or '').lower()
        try:
            parses = self._morph.parse(lemma)
            if parses:
                return parses[0].tag.animacy == 'Anim'
        except Exception:
            pass
        return False

    def _is_passive(self, tok: Token, toks: Dict[int, Token]) -> bool:
        """Пассивный залог: Voice=Pass в feats или наличие дочернего aux:pass."""
        if (tok.feats or {}).get('Voice') == 'Pass':
            return True
        return any(
            t.head_id == tok.id and t.dep == 'aux:pass'
            for t in toks.values()
        )

    def _is_experiential(self, tok: Token) -> bool:
        lemma = (tok.lemma or tok.word or '').lower()
        return lemma in EXPERIENTIAL_VERBS

    def _get_case_prep(self, tok_id: int, toks: Dict[int, Token]) -> str:
        """Находит предлог (case-зависимый) для заданного узла."""
        for t in toks.values():
            if t.head_id == tok_id and t.dep == 'case':
                return (t.lemma or t.word or '').lower()
        return ''

    # ── Классификация OBL: предлог + падеж + одушевлённость ──────────────────

    def _classify_obl(
        self,
        tok: Token,
        toks: Dict[int, Token],
        parent_tok: Optional[Token] = None,
    ) -> str:
        prep  = self._get_case_prep(tok.id, toks)
        case  = (tok.feats or {}).get('Case', '')
        lemma = (tok.lemma or '').lower()

        # ── Творительный без предлога ──────────────────────────────────────
        if case == 'Ins' and not prep:
            # Агент пассивной конструкции («был написан студентом»)
            if parent_tok and self._is_passive(parent_tok, toks):
                return 'AGENT'
            if lemma in ADVERB_INSTRUMENTALS:
                return 'MANNER'
            if tok.pos in ('NOUN', 'PROPN'):
                return 'COMITATIVE' if self._is_animate(tok) else 'INSTRUMENT'
            return 'MANNER'

        # ── Дательный без предлога ─────────────────────────────────────────
        if case == 'Dat' and not prep:
            if self._is_animate(tok):
                if parent_tok and self._is_experiential(parent_tok):
                    return 'EXPERIENCER'
                return 'RECIPIENT'
            return 'CIRCUMSTANCE'

        # ── Однозначные предлоги ───────────────────────────────────────────
        if prep in PREP_ROLE:
            return PREP_ROLE[prep]

        # ── в/во/на — место vs направление ────────────────────────────────
        if prep in ('в', 'во', 'на'):
            if case == 'Acc':
                return 'GOAL'
            return 'TIME' if lemma in TIME_LEMMAS else 'LOCATION'

        # ── до — время или место ───────────────────────────────────────────
        if prep == 'до':
            return 'TIME' if lemma in TIME_LEMMAS else 'LOCATION'

        # ── за — место (Ins), направление/время (Acc) ─────────────────────
        if prep == 'за':
            if case == 'Ins':
                return 'LOCATION'
            if case == 'Acc':
                return 'TIME' if lemma in TIME_LEMMAS else 'GOAL'
            return 'LOCATION'

        # ── перед — место или время ────────────────────────────────────────
        if prep == 'перед':
            return 'TIME' if lemma in TIME_LEMMAS else 'LOCATION'

        # ── при / во время ─────────────────────────────────────────────────
        if prep in ('при', 'во'):
            return 'TIME'

        # ── по + Dat → образ действия; иначе → обстоятельство ─────────────
        if prep == 'по':
            return 'MANNER' if case == 'Dat' else 'CIRCUMSTANCE'

        # ── с/со + Ins → совместность (одуш.) или образ (неодуш.) ──────────
        # ── с/со + Gen/Acc → источник ──────────────────────────────────────
        if prep in ('с', 'со'):
            if case == 'Ins':
                return 'COMITATIVE' if self._is_animate(tok) else 'MANNER'
            return 'SOURCE'

        # ── без → образ действия (лишённость способа) ─────────────────────
        if prep == 'без':
            return 'MANNER'

        return 'CIRCUMSTANCE'

    def _classify_advmod(self, tok: Token) -> str:
        """Классификация наречного обстоятельства по лексике."""
        lemma = (tok.lemma or tok.word or '').lower()
        if lemma in TIME_ADVS:
            return 'TIME'
        if lemma in LOCATION_ADVS:
            return 'LOCATION'
        if lemma in MANNER_ADVS:
            return 'MANNER'
        return 'CIRCUMSTANCE'

    # ── Рекурсивный обход дерева зависимостей ────────────────────────────────

    def _process_node(
        self,
        tok: Token,
        parent_node: Optional[SemNode],
        dep_key: str,
        sentence: Sentence,
        toks: Dict[int, Token],
        graph: SemanticGraph,
        added_ids: Set[int],
        absorbed_ids: Set[int],
        depth: int,
    ) -> None:
        if depth > 12:
            return
        if tok.id in added_ids or tok.id in absorbed_ids:
            return

        # Функциональные слова — узел пропускается, дочерние обходятся
        if dep_key in SKIP_DEPS:
            for child in self._children(tok.id, sentence):
                self._process_node(child, parent_node, child.dep, sentence,
                                   toks, graph, added_ids, absorbed_ids, depth + 1)
            return

        # Незначимые POS — пропускаем как узел
        if tok.pos not in CONTENT_POS and dep_key != 'root':
            for child in self._children(tok.id, sentence):
                self._process_node(child, parent_node, child.dep, sentence,
                                   toks, graph, added_ids, absorbed_ids, depth + 1)
            return

        # Получаем токен-родитель для контекстной классификации
        parent_tok: Optional[Token] = (
            toks.get(parent_node.id) if parent_node is not None else None
        )

        role, role_ru, edge_lbl, edge_lbl_ru, is_pred = self._classify(
            tok, dep_key, parent_node, toks, parent_tok)

        if role is None:
            for child in self._children(tok.id, sentence):
                self._process_node(child, parent_node, child.dep, sentence,
                                   toks, graph, added_ids, absorbed_ids, depth + 1)
            return

        full_lemma, full_word = self._noun_phrase(tok, toks)
        node = SemNode(
            id=tok.id, lemma=full_lemma, word=full_word,
            pos=tok.pos, role=role, role_ru=role_ru, is_predicate=is_pred,
        )
        graph.nodes.append(node)
        added_ids.add(tok.id)

        # Поглощаем flat-дочерние (они вошли в лемму)
        for t in toks.values():
            if t.head_id == tok.id and t.dep in FLAT_DEPS:
                absorbed_ids.add(t.id)
                added_ids.add(t.id)

        # Добавляем ребро к родителю
        if parent_node is not None and edge_lbl:
            if role in SUBJ_ROLES:
                # Субъектные роли: узел → предикат
                graph.edges.append(SemEdge(
                    src=tok.id, dst=parent_node.id,
                    label=edge_lbl, label_ru=edge_lbl_ru, dep=dep_key,
                ))
            else:
                # Все остальные: предикат → зависимый
                graph.edges.append(SemEdge(
                    src=parent_node.id, dst=tok.id,
                    label=edge_lbl, label_ru=edge_lbl_ru, dep=dep_key,
                ))

        # Рекурсия в дочерние
        for child in self._children(tok.id, sentence):
            self._process_node(child, node, child.dep, sentence, toks,
                               graph, added_ids, absorbed_ids, depth + 1)

    # ── Классификация по типу зависимости ────────────────────────────────────

    def _classify(
        self,
        tok: Token,
        dep: str,
        parent: Optional[SemNode],
        toks: Dict[int, Token],
        parent_tok: Optional[Token] = None,
    ) -> Tuple[Optional[str], str, str, str, bool]:
        """Возвращает (role, role_ru, edge_label, edge_label_ru, is_predicate)."""
        pos     = tok.pos
        is_verb = pos in PRED_POS

        # ── Корень предложения ────────────────────────────────────────────────
        if dep == 'root':
            r, r_ru = self._root_role(tok)
            return r, r_ru, '', '', r == 'PREDICATE'

        # ── Подлежащее в пассиве → PATIENT (критическое исправление!) ─────────
        if dep == 'nsubj:pass':
            e, e_ru = ROLE_EDGE['PATIENT']
            return 'PATIENT', SEM_LABELS['PATIENT'], e, e_ru, False

        # ── Подлежащее в активе ───────────────────────────────────────────────
        if dep == 'nsubj':
            # При экспериентивном глаголе nom-аргумент = STIMULUS
            if parent_tok and self._is_experiential(parent_tok):
                e, e_ru = ROLE_EDGE['STIMULUS']
                return 'STIMULUS', SEM_LABELS['STIMULUS'], e, e_ru, False
            # Одушевлённый → AGENT, неодушевлённый → FORCE
            if self._is_animate(tok):
                e, e_ru = ROLE_EDGE['AGENT']
                return 'AGENT', SEM_LABELS['AGENT'], e, e_ru, False
            else:
                e, e_ru = ROLE_EDGE['FORCE']
                return 'FORCE', SEM_LABELS['FORCE'], e, e_ru, False

        # ── Истинный агент при пассиве (кем/чем) ──────────────────────────────
        if dep == 'obl:agent':
            e, e_ru = ROLE_EDGE['AGENT']
            return 'AGENT', SEM_LABELS['AGENT'], e, e_ru, False

        # ── Косвенное дополнение (iobj) ───────────────────────────────────────
        if dep == 'iobj':
            # При экспериентивном глаголе Dat-аргумент = переживающий
            if parent_tok and self._is_experiential(parent_tok):
                e, e_ru = ROLE_EDGE['EXPERIENCER']
                return 'EXPERIENCER', SEM_LABELS['EXPERIENCER'], e, e_ru, False
            if self._is_animate(tok):
                e, e_ru = ROLE_EDGE['RECIPIENT']
                return 'RECIPIENT', SEM_LABELS['RECIPIENT'], e, e_ru, False
            e, e_ru = ROLE_EDGE['BENEFICIARY']
            return 'BENEFICIARY', SEM_LABELS['BENEFICIARY'], e, e_ru, False

        # ── Прямое дополнение (obj) ───────────────────────────────────────────
        if dep == 'obj':
            if parent_tok and self._is_experiential(parent_tok):
                e, e_ru = ROLE_EDGE['STIMULUS']
                return 'STIMULUS', SEM_LABELS['STIMULUS'], e, e_ru, False
            e, e_ru = ROLE_EDGE['PATIENT']
            return 'PATIENT', SEM_LABELS['PATIENT'], e, e_ru, False

        # ── OBL (косвенное дополнение / обстоятельство) ───────────────────────
        if dep == 'obl':
            if is_verb:
                e, e_ru = ROLE_EDGE['PREDICATE']
                return 'PREDICATE', SEM_LABELS['PREDICATE'], e, e_ru, True
            role = self._classify_obl(tok, toks, parent_tok)
            e, e_ru = ROLE_EDGE[role]
            return role, SEM_LABELS[role], e, e_ru, False

        # ── Наречное обстоятельство ───────────────────────────────────────────
        if dep in ADV_DEPS:
            if is_verb:
                e, e_ru = ROLE_EDGE['PREDICATE']
                return 'PREDICATE', SEM_LABELS['PREDICATE'], e, e_ru, True
            role = self._classify_advmod(tok)
            e, e_ru = ROLE_EDGE[role]
            return role, SEM_LABELS[role], e, e_ru, False

        # ── Придаточные клаузы ────────────────────────────────────────────────
        if dep in CLAUSE_DEPS:
            if is_verb:
                e, e_ru = ROLE_EDGE['PREDICATE']
                return 'PREDICATE', SEM_LABELS['PREDICATE'], e, e_ru, True
            e, e_ru = ROLE_EDGE['CIRCUMSTANCE']
            return 'CIRCUMSTANCE', SEM_LABELS['CIRCUMSTANCE'], e, e_ru, False

        # ── Именные зависимые (nmod / nmod:poss) ─────────────────────────────
        if dep in NMOD_DEPS:
            prep = self._get_case_prep(tok.id, toks)
            case = (tok.feats or {}).get('Case', '')
            lemma_l = (tok.lemma or '').lower()

            if prep in ('для', 'ради'):
                e, e_ru = ROLE_EDGE['PURPOSE']
                return 'PURPOSE', SEM_LABELS['PURPOSE'], e, e_ru, False
            if prep in ('из-за', 'благодаря', 'вследствие', 'ввиду', 'вопреки'):
                e, e_ru = ROLE_EDGE['CAUSE']
                return 'CAUSE', SEM_LABELS['CAUSE'], e, e_ru, False
            if prep in ('из', 'от'):
                e, e_ru = ROLE_EDGE['SOURCE']
                return 'SOURCE', SEM_LABELS['SOURCE'], e, e_ru, False
            if prep in ('к', 'ко'):
                e, e_ru = ROLE_EDGE['GOAL']
                return 'GOAL', SEM_LABELS['GOAL'], e, e_ru, False
            if prep == 'без':
                e, e_ru = ROLE_EDGE['MANNER']
                return 'MANNER', SEM_LABELS['MANNER'], e, e_ru, False
            if prep and prep in PREP_ROLE:
                role = PREP_ROLE[prep]
                e, e_ru = ROLE_EDGE[role]
                return role, SEM_LABELS[role], e, e_ru, False
            if prep in ('в', 'во', 'на', 'за', 'перед'):
                if case == 'Acc':
                    e, e_ru = ROLE_EDGE['GOAL']
                    return 'GOAL', SEM_LABELS['GOAL'], e, e_ru, False
                role = 'TIME' if lemma_l in TIME_LEMMAS else 'LOCATION'
                e, e_ru = ROLE_EDGE[role]
                return role, SEM_LABELS[role], e, e_ru, False
            # Творительный без предлога в роли nmod → инструмент/совместность
            if case == 'Ins' and not prep:
                if tok.pos in ('NOUN', 'PROPN'):
                    if self._is_animate(tok):
                        e, e_ru = ROLE_EDGE['COMITATIVE']
                        return 'COMITATIVE', SEM_LABELS['COMITATIVE'], e, e_ru, False
                    e, e_ru = ROLE_EDGE['INSTRUMENT']
                    return 'INSTRUMENT', SEM_LABELS['INSTRUMENT'], e, e_ru, False
                e, e_ru = ROLE_EDGE['MANNER']
                return 'MANNER', SEM_LABELS['MANNER'], e, e_ru, False
            if case == 'Gen' or dep == 'nmod:poss' or not prep:
                e, e_ru = ROLE_EDGE['GENITIVE']
                return 'GENITIVE', SEM_LABELS['GENITIVE'], e, e_ru, False
            e, e_ru = ROLE_EDGE['THEME']
            return 'THEME', SEM_LABELS['THEME'], e, e_ru, False

        # ── Определение (прил., числит.) → ATTRIBUTE ─────────────────────────
        if dep in MOD_DEPS:
            e, e_ru = ROLE_EDGE['ATTRIBUTE']
            return 'ATTRIBUTE', SEM_LABELS['ATTRIBUTE'], e, e_ru, False

        # ── Однородные члены наследуют роль головы ────────────────────────────
        if dep in CONJ_DEPS:
            if is_verb:
                e, e_ru = ROLE_EDGE['PREDICATE']
                return 'PREDICATE', SEM_LABELS['PREDICATE'], e, e_ru, True
            if parent is not None:
                return (parent.role, parent.role_ru,
                        'conjoins', EDGE_LABELS['conjoins'], False)
            e, e_ru = ROLE_EDGE['CONJUNCT']
            return 'CONJUNCT', SEM_LABELS['CONJUNCT'], e, e_ru, False

        # ── Fallback по части речи ────────────────────────────────────────────
        if pos in ('NOUN', 'PROPN', 'PRON'):
            e, e_ru = ROLE_EDGE['THEME']
            return 'THEME', SEM_LABELS['THEME'], e, e_ru, False
        if pos in PRED_POS:
            e, e_ru = ROLE_EDGE['PREDICATE']
            return 'PREDICATE', SEM_LABELS['PREDICATE'], e, e_ru, True
        if pos == 'ADJ':
            e, e_ru = ROLE_EDGE['ATTRIBUTE']
            return 'ATTRIBUTE', SEM_LABELS['ATTRIBUTE'], e, e_ru, False
        if pos == 'ADV':
            role = self._classify_advmod(tok)
            e, e_ru = ROLE_EDGE[role]
            return role, SEM_LABELS[role], e, e_ru, False

        return None, '', '', '', False

    # ── Pro-drop: подразумеваемые субъекты ───────────────────────────────────

    _IMPLIED: Dict[tuple, str] = {
        ('Imp', '',  'Sing'): 'ты',
        ('Imp', '',  'Plur'): 'вы',
        ('Imp', '',  ''):     'вы',
        ('Imp', '2', 'Sing'): 'ты',
        ('Imp', '2', 'Plur'): 'вы',
        ('Ind', '1', 'Sing'): 'я',
        ('Ind', '1', 'Plur'): 'мы',
        ('Ind', '2', 'Sing'): 'ты',
        ('Ind', '2', 'Plur'): 'вы',
    }

    def _add_implied_subjects(
        self,
        graph: SemanticGraph,
        sentence: Sentence,
        toks: Dict[int, Token],
    ) -> None:
        """Добавляет подразумеваемые субъекты (pro-drop) для глаголов без агента."""
        has_subj: Set[int] = {
            e.dst for e in graph.edges
            if e.label in ('agent_of', 'force_of', 'experiencer_of')
        }
        virtual_id = -(max(toks.keys(), default=0) + 100)

        for pred_node in list(graph.nodes):
            if pred_node.pos not in PRED_POS and not pred_node.is_predicate:
                continue
            if pred_node.id in has_subj:
                continue
            tok = toks.get(pred_node.id)
            if tok is None:
                continue
            # Пассивные глаголы — без подразумеваемого агента
            if self._is_passive(tok, toks):
                continue
            feats  = tok.feats or {}
            mood   = feats.get('Mood',   '')
            person = feats.get('Person', '')
            number = feats.get('Number', '')
            pron = (
                self._IMPLIED.get((mood, person, number)) or
                self._IMPLIED.get((mood, '',     number)) or
                self._IMPLIED.get((mood, '',     ''))
            )
            if pron is None:
                continue
            impl_node = SemNode(
                id=virtual_id, lemma=pron, word=pron,
                pos='PRON', role='AGENT', role_ru=SEM_LABELS['AGENT'],
                is_predicate=False, implied=True,
            )
            graph.nodes.append(impl_node)
            graph.edges.append(SemEdge(
                src=virtual_id, dst=pred_node.id,
                label='agent_of', label_ru=EDGE_LABELS['agent_of'],
                dep='implied',
            ))
            virtual_id -= 1

    # ── Разделение аргументов при однородных предикатах ──────────────────────

    def _share_conj_args(
        self,
        graph: SemanticGraph,
        sentence: Sentence,
        toks: Dict[int, Token],
    ) -> None:
        """
        Если два глагола соединены conj и у второго нет субъекта,
        создаём ребро-«копию» от субъекта первого ко второму предикату.
        Пример: «Студент пришёл и сел.» — «студент» агент обоих.
        """
        predicates = [n for n in graph.nodes if n.is_predicate]
        if len(predicates) < 2:
            return

        # Карта: predicate_id → список id субъектных узлов
        pred_subj: Dict[int, List[int]] = {p.id: [] for p in predicates}
        for edge in graph.edges:
            if edge.label in ('agent_of', 'force_of', 'experiencer_of'):
                if edge.dst in pred_subj:
                    pred_subj[edge.dst].append(edge.src)

        # Ищем conj-пары предикатов
        conj_pairs: List[Tuple[int, int]] = []
        for t in sentence.tokens:
            if t.dep in CONJ_DEPS and t.pos in PRED_POS:
                head = toks.get(t.head_id)
                if head and head.pos in PRED_POS:
                    conj_pairs.append((t.head_id, t.id))

        existing = {(e.src, e.dst) for e in graph.edges}
        node_ids  = {n.id for n in graph.nodes}

        for head_pid, conj_pid in conj_pairs:
            if conj_pid not in pred_subj:
                continue
            if pred_subj.get(conj_pid):
                continue  # у конъюнкта уже есть свой субъект
            for subj_id in pred_subj.get(head_pid, []):
                if (subj_id, conj_pid) in existing or subj_id not in node_ids:
                    continue
                subj_node = next((n for n in graph.nodes if n.id == subj_id), None)
                lbl = 'agent_of' if (subj_node and subj_node.role == 'AGENT') else 'force_of'
                graph.edges.append(SemEdge(
                    src=subj_id, dst=conj_pid,
                    label=lbl, label_ru=EDGE_LABELS[lbl],
                    dep='conj:shared',
                ))
                existing.add((subj_id, conj_pid))

    # ── Вспомогательные методы ────────────────────────────────────────────────

    @staticmethod
    def _root_role(tok: Token) -> Tuple[str, str]:
        if tok.pos in ('VERB', 'AUX'):
            return 'PREDICATE', SEM_LABELS['PREDICATE']
        # Workaround: natasha иногда неверно тегирует императив как PROPN.
        # Если feats содержат глагольные признаки — это предикат.
        if tok.pos == 'PROPN':
            feats = tok.feats or {}
            if feats.get('VerbForm') or feats.get('Mood') or feats.get('Tense'):
                return 'PREDICATE', SEM_LABELS['PREDICATE']
            return 'AGENT', SEM_LABELS['AGENT']
        if tok.pos in ('NOUN', 'PRON'):
            return 'THEME', SEM_LABELS['THEME']
        if tok.pos == 'ADJ':
            return 'ATTRIBUTE', SEM_LABELS['ATTRIBUTE']
        return 'THEME', SEM_LABELS['THEME']

    @staticmethod
    def _find_root(tokens: List[Token]) -> Optional[Token]:
        # 1. Явный root
        for t in tokens:
            if t.dep == 'root':
                return t
        # 2. Обнаружение цикла (баг natasha): A→B и B→A; берём VERB
        id_map = {t.id: t for t in tokens}
        for t in tokens:
            if t.pos in PRED_POS and t.dep in CLAUSE_DEPS:
                head = id_map.get(t.head_id)
                if head is not None and head.head_id == t.id:
                    return t
        # 3. Последний резерв: первый VERB
        for t in tokens:
            if t.pos == 'VERB':
                return t
        return None

    @staticmethod
    def _noun_phrase(head: Token, toks: Dict[int, Token]) -> Tuple[str, str]:
        """
        Возвращает (lemma, word):
        - lemma : лемма головного слова + flat-части (для имён собств.)
        - word  : полная именная группа с amod/nummod/det-модификаторами
        """
        head_lemma = head.lemma or head.word

        flat_lemmas: List[str] = []
        pre_words:   List[str] = []   # модификаторы/flat перед головой
        post_words:  List[str] = []   # flat-части после головы

        for t in sorted(toks.values(), key=lambda x: x.id):
            if t.head_id != head.id:
                continue
            if t.dep in FLAT_DEPS:
                flat_lemmas.append(t.lemma or t.word)
                if t.id < head.id:
                    pre_words.append(t.word)
                else:
                    post_words.append(t.word)
            elif t.dep in NP_MOD_DEPS:
                if t.id < head.id:
                    pre_words.append(t.word)
                else:
                    post_words.append(t.word)

        lemma = head_lemma
        if flat_lemmas:
            lemma = head_lemma + ' ' + ' '.join(flat_lemmas)

        word_parts = pre_words + [head.word] + post_words
        word = ' '.join(word_parts)
        return lemma, word

    @staticmethod
    def _children(tok_id: int, sentence: Sentence) -> List[Token]:
        return [t for t in sentence.tokens
                if t.head_id == tok_id and t.id != tok_id]


# ── Публичный API ─────────────────────────────────────────────────────────────

_builder = SemanticGraphBuilder()


def build_semantic_graph(sentence: Sentence) -> SemanticGraph:
    """Строит семантический граф для одного предложения."""
    return _builder.build(sentence)
