"""
database.py
Централизованное хранилище данных на PostgreSQL.
Хранит историю анализов, токены, сущности и результаты тональности.

Конфигурация подключения берётся из переменных окружения
или использует дефолтные значения.
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
from typing import Optional

DB_CONFIG = {
    'dbname':          os.environ.get('DB_NAME',     'sintanalitik'),
    'user':            os.environ.get('DB_USER',     'postgres'),
    'password':        os.environ.get('DB_PASSWORD', '1111'),
    'host':            os.environ.get('DB_HOST',     'localhost'),
    'port':            int(os.environ.get('DB_PORT',  5432)),
    'client_encoding': 'utf8',
}


class AnalysisDB:
    """Управляет всеми операциями с БД анализов."""

    def __init__(self):
        self._initialize_db()

    def get_connection(self):
        try:
            return psycopg2.connect(**DB_CONFIG)
        except psycopg2.Error as e:
            print(f'[DB] Ошибка подключения: {e}')
            return None

    def _execute_write(self, query: str, params=None) -> bool:
        conn = self.get_connection()
        if conn is None:
            return False
        cur = conn.cursor()
        try:
            cur.execute(query, params)
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f'[DB] Ошибка записи: {e}')
            return False
        finally:
            cur.close()
            conn.close()

    def _execute_read(self, query: str, params=None) -> list:
        conn = self.get_connection()
        if conn is None:
            return []
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(query, params)
            return cur.fetchall()
        except Exception as e:
            print(f'[DB] Ошибка чтения: {e}')
            return []
        finally:
            cur.close()
            conn.close()

    def _initialize_db(self):
        queries = [
            '''CREATE TABLE IF NOT EXISTS analyses (
                id              SERIAL PRIMARY KEY,
                created_at      TIMESTAMP DEFAULT NOW(),
                source_name     TEXT NOT NULL,
                source_text     TEXT NOT NULL,
                sentence_count  INTEGER,
                word_count      INTEGER,
                elapsed_ms      REAL,
                sentiment       TEXT,
                sentiment_score REAL,
                notes           TEXT,
                sentences_json  TEXT
            )''',
            '''CREATE TABLE IF NOT EXISTS tokens (
                id          SERIAL PRIMARY KEY,
                analysis_id INTEGER REFERENCES analyses(id) ON DELETE CASCADE,
                word        TEXT,
                pos         TEXT,
                role        TEXT,
                sentence_id INTEGER
            )''',
            '''CREATE TABLE IF NOT EXISTS entities (
                id          SERIAL PRIMARY KEY,
                analysis_id INTEGER REFERENCES analyses(id) ON DELETE CASCADE,
                text        TEXT,
                label       TEXT,
                label_ru    TEXT
            )''',
            'CREATE INDEX IF NOT EXISTS idx_tokens_word ON tokens(lower(word))',
            'CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at DESC)',
            'CREATE INDEX IF NOT EXISTS idx_entities_label ON entities(label)',
        ]
        for q in queries:
            self._execute_write(q)

    def save_analysis(self, source_name: str, source_text: str,
                      analysis_result, sentiment: dict,
                      entities: list) -> Optional[int]:
        conn = self.get_connection()
        if conn is None:
            return None
        cur = conn.cursor()
        try:
            stats = analysis_result.stats
            sentences = analysis_result.sentences

            sentences_data = [
                {
                    'id': s.id, 'text': s.text,
                    'tokens': [
                        {'word': t.word, 'lemma': t.lemma, 'pos': t.pos,
                         'pos_ru': t.pos_ru, 'dep': t.dep, 'dep_ru': t.dep_ru,
                         'role': t.dep_ru, 'head_id': t.head_id}
                        for t in s.tokens
                    ]
                }
                for s in sentences
            ]

            cur.execute(
                '''INSERT INTO analyses
                   (source_name, source_text, sentence_count, word_count,
                    elapsed_ms, sentiment, sentiment_score, sentences_json)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                (
                    source_name,
                    source_text[:50000],
                    stats.get('sentence_count', 0),
                    stats.get('word_count', 0),
                    analysis_result.elapsed_ms,
                    sentiment.get('overall', 'neutral'),
                    sentiment.get('score', 0.0),
                    json.dumps(sentences_data, ensure_ascii=False),
                )
            )
            analysis_id = cur.fetchone()[0]

            token_rows = [
                (analysis_id, t.word, t.pos_ru, t.dep_ru, s.id)
                for s in sentences
                for t in s.tokens
                if t.pos != 'PUNCT'
            ]
            if token_rows:
                execute_batch(
                    cur,
                    'INSERT INTO tokens (analysis_id,word,pos,role,sentence_id) VALUES (%s,%s,%s,%s,%s)',
                    token_rows, page_size=500,
                )

            entity_rows = [(analysis_id, e.text, e.label, e.label_ru) for e in entities]
            if entity_rows:
                execute_batch(
                    cur,
                    'INSERT INTO entities (analysis_id,text,label,label_ru) VALUES (%s,%s,%s,%s)',
                    entity_rows,
                )

            conn.commit()
            return analysis_id
        except Exception as e:
            conn.rollback()
            print(f'[DB] Ошибка сохранения: {e}')
            return None
        finally:
            cur.close()
            conn.close()

    def get_history(self, limit: int = 50, offset: int = 0) -> list:
        return self._execute_read(
            '''SELECT id, created_at, source_name, sentence_count,
                      word_count, elapsed_ms, sentiment, sentiment_score, notes
               FROM analyses ORDER BY created_at DESC LIMIT %s OFFSET %s''',
            (limit, offset)
        )

    def get_analysis(self, analysis_id: int):
        rows = self._execute_read('SELECT * FROM analyses WHERE id=%s', (analysis_id,))
        if not rows:
            return None
        row = dict(rows[0])
        if row.get('sentences_json'):
            row['sentences'] = json.loads(row['sentences_json'])
        return row

    def get_entities_for(self, analysis_id: int) -> list:
        return self._execute_read(
            'SELECT text,label,label_ru FROM entities WHERE analysis_id=%s', (analysis_id,)
        )

    def update_notes(self, analysis_id: int, notes: str) -> bool:
        return self._execute_write('UPDATE analyses SET notes=%s WHERE id=%s', (notes, analysis_id))

    def rename_analysis(self, analysis_id: int, new_name: str) -> bool:
        return self._execute_write('UPDATE analyses SET source_name=%s WHERE id=%s', (new_name, analysis_id))

    def delete_analysis(self, analysis_id: int) -> bool:
        return self._execute_write('DELETE FROM analyses WHERE id=%s', (analysis_id,))

    def search_by_word(self, word: str) -> list:
        return self._execute_read(
            '''SELECT DISTINCT a.id, a.created_at, a.source_name,
                      a.sentence_count, a.word_count, a.sentiment
               FROM analyses a JOIN tokens t ON t.analysis_id=a.id
               WHERE lower(t.word)=lower(%s) ORDER BY a.created_at DESC''',
            (word,)
        )

    def search_by_name(self, name: str) -> list:
        return self._execute_read(
            '''SELECT id, created_at, source_name, sentence_count,
                      word_count, elapsed_ms, sentiment, sentiment_score, notes
               FROM analyses WHERE lower(source_name) LIKE lower(%s)
               ORDER BY created_at DESC''',
            (f'%{name}%',)
        )

    def search_by_entity(self, entity_text: str) -> list:
        return self._execute_read(
            '''SELECT DISTINCT a.id, a.created_at, a.source_name, e.label_ru
               FROM analyses a JOIN entities e ON e.analysis_id=a.id
               WHERE lower(e.text) LIKE lower(%s) ORDER BY a.created_at DESC''',
            (f'%{entity_text}%',)
        )

    def get_global_stats(self) -> dict:
        counts = self._execute_read('SELECT COUNT(*) as total, SUM(word_count) as words FROM analyses')
        pos_dist = self._execute_read(
            'SELECT pos, COUNT(*) as cnt FROM tokens GROUP BY pos ORDER BY cnt DESC LIMIT 10'
        )
        sentiment_dist = self._execute_read(
            'SELECT sentiment, COUNT(*) as cnt FROM analyses GROUP BY sentiment'
        )
        total = dict(counts[0]) if counts else {}
        return {
            'total_analyses':      total.get('total', 0),
            'total_words':         total.get('words', 0),
            'pos_distribution':    [dict(r) for r in pos_dist],
            'sentiment_distribution': [dict(r) for r in sentiment_dist],
        }

    def is_available(self) -> bool:
        conn = self.get_connection()
        if conn:
            conn.close()
            return True
        return False


_db_instance: Optional[AnalysisDB] = None

def get_db() -> AnalysisDB:
    global _db_instance
    if _db_instance is None:
        _db_instance = AnalysisDB()
    return _db_instance
