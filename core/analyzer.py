"""
analyzer.py — NLP-ядро: морфология, синтаксис, NER, тональность.
Использует: natasha, pymorphy2.
"""
import time, re
from dataclasses import dataclass, field
from typing import List, Dict, Optional

import pymorphy2
from natasha import (
    Segmenter, MorphVocab, NewsEmbedding,
    NewsMorphTagger, NewsSyntaxParser, NewsNERTagger, Doc,
)

# ── Словари переводов ─────────────────────────────────────────────────────────

POS_RU: Dict[str, str] = {
    'NOUN': 'существительное', 'VERB': 'глагол', 'ADJ': 'прилагательное',
    'ADV': 'наречие', 'PRON': 'местоимение', 'DET': 'детерминатив',
    'ADP': 'предлог', 'CCONJ': 'союз', 'SCONJ': 'союз', 'CONJ': 'союз',
    'PART': 'частица', 'INTJ': 'междометие', 'NUM': 'числительное',
    'PROPN': 'имя собств.', 'PUNCT': 'пунктуация',
    'AUX': 'вспом. глагол', 'X': 'иное',
}

DEP_RU: Dict[str, str] = {
    'nsubj': 'подлежащее', 'nsubj:pass': 'подлежащее (пасс.)',
    'root': 'корень/сказуемое', 'obj': 'доп. прямое', 'iobj': 'доп. косвенное',
    'amod': 'определение', 'advmod': 'обстоятельство',
    'nmod': 'несогл. определение', 'obl': 'доп./обст.',
    'compound': 'составная часть', 'flat': 'именная группа',
    'flat:name': 'имя', 'case': 'предлог', 'det': 'детерминатив',
    'punct': 'пунктуация', 'cc': 'сочин. союз', 'conj': 'однородный член',
    'ccomp': 'доп. (клауза)', 'xcomp': 'открытое доп.',
    'acl': 'прич. оборот', 'acl:relcl': 'прид. опр.',
    'advcl': 'прид. обст.', 'mark': 'подч. союз', 'aux': 'вспомогательный',
    'cop': 'связка', 'appos': 'приложение', 'nummod': 'числ. модификатор',
    'parataxis': 'паратаксис', 'vocative': 'обращение', 'dep': 'зависимость',
    'discourse': 'дискурс', 'fixed': 'фикс. выражение', 'list': 'перечисление',
    'orphan': 'сирота',
}

NER_RU: Dict[str, str] = {
    'PER': 'Персона', 'ORG': 'Организация', 'LOC': 'Место',
    'DATE': 'Дата', 'MONEY': 'Деньги',
}

# ── Тональность (лексикон) ────────────────────────────────────────────────────

POS_LEX = {
    'хорошо', 'отлично', 'прекрасно', 'замечательно', 'великолепно',
    'радость', 'счастье', 'успех', 'победа', 'любовь', 'красивый',
    'добрый', 'светлый', 'лучший', 'прекрасный', 'удивительный',
    'позитивный', 'доволен', 'выгодно', 'полезно', 'важно',
    'достижение', 'рост', 'развитие', 'улучшение', 'нравиться',
    'восхитительно', 'блестяще', 'надёжный', 'перспективный', 'верный',
    'бодрый', 'честный', 'яркий', 'интересный', 'уютный', 'гармония',
}

NEG_LEX = {
    'плохо', 'ужасно', 'отвратительно', 'провал', 'катастрофа',
    'проблема', 'беда', 'ошибка', 'кризис', 'трагедия', 'несчастье',
    'злой', 'грустный', 'тёмный', 'худший', 'негативный', 'недовольный',
    'убыток', 'потеря', 'упасть', 'снижаться', 'ухудшение', 'ненависть',
    'страх', 'боль', 'тяжело', 'невозможно', 'штраф', 'угроза',
    'опасность', 'запрет', 'нарушение', 'виновный', 'скандал', 'авария',
    'страдать', 'горький', 'жестокий', 'мрачный', 'тревога', 'паника',
}

# ── Датаклассы ────────────────────────────────────────────────────────────────

@dataclass
class Token:
    id: int
    sentence_id: int
    word: str
    lemma: str
    pos: str
    pos_ru: str
    dep: str
    dep_ru: str
    head_id: int
    feats: Dict = field(default_factory=dict)

    def to_dict(self):
        return {
            'id': self.id, 'sentence_id': self.sentence_id,
            'word': self.word, 'lemma': self.lemma,
            'pos': self.pos, 'pos_ru': self.pos_ru,
            'dep': self.dep, 'dep_ru': self.dep_ru,
            'head_id': self.head_id, 'feats': self.feats,
        }


@dataclass
class Sentence:
    id: int
    text: str
    tokens: List[Token] = field(default_factory=list)


@dataclass
class Entity:
    text: str
    label: str
    label_ru: str
    start: int
    stop: int


@dataclass
class AnalysisResult:
    sentences: List[Sentence]
    entities: List[Entity]
    stats: Dict
    sentiment: Dict
    elapsed_ms: float


# ── Основной класс ────────────────────────────────────────────────────────────

class NLPAnalyzer:
    """
    Загружает модели natasha/pymorphy2 один раз,
    предоставляет метод analyze(text) → AnalysisResult.
    """

    def __init__(self):
        self._seg   = Segmenter()
        self._emb   = NewsEmbedding()
        self._morph = NewsMorphTagger(self._emb)
        self._synt  = NewsSyntaxParser(self._emb)
        self._ner   = NewsNERTagger(self._emb)
        self._mvoc  = MorphVocab()
        self._pymorphy = pymorphy2.MorphAnalyzer()

    def analyze(self, text: str) -> AnalysisResult:
        t0 = time.perf_counter()
        text = re.sub(r'\r\n', '\n', text).strip()
        self._last_text = text   # нужен для dostoevsky батч-анализа
        doc  = Doc(text)
        doc.segment(self._seg)
        doc.tag_morph(self._morph)
        doc.parse_syntax(self._synt)
        doc.tag_ner(self._ner)
        for tok in doc.tokens:
            tok.lemmatize(self._mvoc)

        sentences = self._extract_sentences(doc)
        entities  = self._extract_entities(doc)
        stats     = self._calc_stats(sentences, text)
        sentiment = self._calc_sentiment(sentences)
        elapsed   = round((time.perf_counter() - t0) * 1000, 1)
        return AnalysisResult(sentences, entities, stats, sentiment, elapsed)

    # ── private ───────────────────────────────────────────────────────────────

    def _extract_sentences(self, doc: Doc) -> List[Sentence]:
        result = []
        for si, nsent in enumerate(doc.sents):
            tokens = []
            for ti, nt in enumerate(nsent.tokens):
                pos = nt.pos or 'X'
                dep = nt.rel or 'dep'
                try:
                    # natasha uses IDs like '1_3' (sentence_token)
                    # extract the token-within-sentence part
                    raw_hid = nt.head_id or ''
                    if '_' in str(raw_hid):
                        head = int(str(raw_hid).split('_')[1]) - 1  # 1-based → 0-based
                    else:
                        head = int(raw_hid) - 1
                except (TypeError, ValueError, IndexError):
                    head = ti
                tokens.append(Token(
                    id=ti, sentence_id=si,
                    word=nt.text,
                    lemma=nt.lemma or nt.text.lower(),
                    pos=pos, pos_ru=POS_RU.get(pos, pos),
                    dep=dep, dep_ru=DEP_RU.get(dep, dep),
                    head_id=head,
                    feats=dict(nt.feats) if nt.feats else {},
                ))
            result.append(Sentence(id=si, text=nsent.text, tokens=tokens))
        return result

    def _extract_entities(self, doc: Doc) -> List[Entity]:
        return [
            Entity(s.text, s.type, NER_RU.get(s.type, s.type), s.start, s.stop)
            for s in doc.spans
        ]

    def _calc_stats(self, sentences: List[Sentence], text: str) -> Dict:
        content_toks = [t for s in sentences for t in s.tokens if t.pos != 'PUNCT']
        pos_d: Dict[str, int] = {}
        dep_d: Dict[str, int] = {}
        for t in content_toks:
            pos_d[t.pos_ru] = pos_d.get(t.pos_ru, 0) + 1
            dep_d[t.dep_ru] = dep_d.get(t.dep_ru, 0) + 1
        words = text.split()
        avg   = sum(len(w) for w in words) / max(len(words), 1)
        return {
            'sentence_count': len(sentences),
            'word_count': len(content_toks),
            'char_count': len(text),
            'avg_word_len': round(avg, 1),
            'pos_distribution': sorted(pos_d.items(), key=lambda x: -x[1]),
            'dep_distribution': sorted(dep_d.items(), key=lambda x: -x[1])[:12],
        }

    def _calc_sentiment(self, sentences: List[Sentence]) -> Dict:
        """Использует dostoevsky (FastText RuSentiment), при недоступности — лексику."""
        try:
            from core.sentiment import analyse_text
            return analyse_text(self._last_text, sentences)
        except Exception as e:
            print(f'[sentiment] dostoevsky fallback: {e}')
            # Лексический резерв
            all_lemmas = [
                t.lemma.lower() for s in sentences for t in s.tokens
                if t.pos not in ('PUNCT', 'ADP', 'CCONJ', 'SCONJ', 'PART')
            ]
            pos_n = sum(1 for l in all_lemmas if l in POS_LEX)
            neg_n = sum(1 for l in all_lemmas if l in NEG_LEX)
            score = (pos_n - neg_n) / max(pos_n + neg_n, 1)
            label = ('positive' if score > .2 else
                     'negative' if score < -.2 else 'neutral')
            RU = {'positive': 'позитивный', 'negative': 'негативный', 'neutral': 'нейтральный'}
            per = []
            for s in sentences:
                ll = [t.lemma.lower() for t in s.tokens if t.pos != 'PUNCT']
                p  = sum(1 for l in ll if l in POS_LEX)
                n  = sum(1 for l in ll if l in NEG_LEX)
                per.append({'id': s.id, 'score': round((p - n) / max(p + n, 1), 3),
                            'label': label, 'label_ru': RU[label], 'scores': {}})
            return {
                'overall': label, 'overall_ru': RU[label],
                'score': round(score, 3),
                'positive_count': pos_n, 'negative_count': neg_n,
                'per_sentence': per, 'engine': 'lexical', 'raw_scores': {},
            }

_inst: Optional[NLPAnalyzer] = None

def get_analyzer() -> NLPAnalyzer:
    global _inst
    if _inst is None:
        _inst = NLPAnalyzer()
    return _inst