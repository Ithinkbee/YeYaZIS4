"""
semantic_similarity.py — вычисление семантической близости узлов графа.

Использует sentence-transformers (модель paraphrase-multilingual-MiniLM-L12-v2,
~120 MB) для получения вектор-эмбеддингов лемм и вычисления косинусного сходства
между всеми парами узлов семантического графа.

Первый вызов скачивает модель однократно.
"""

from __future__ import annotations
from typing import Dict, Tuple, Optional
from core.semantics import SemanticGraph

MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'

_model = None   # ленивая инициализация


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def compute_similarities(graph: SemanticGraph) -> Dict[Tuple[int, int], float]:
    """
    Вычисляет косинусное сходство для всех пар узлов семантического графа.

    Возвращает словарь {(src_id, dst_id): score} только для пар
    с score > 0.35 (не включает пары с самим собой).
    Словарь симметричен: (a,b) и (b,a) имеют одинаковый score.
    """
    if not graph.nodes or len(graph.nodes) < 2:
        return {}

    import numpy as np
    model = _get_model()

    lemmas = [n.lemma for n in graph.nodes]
    ids = [n.id for n in graph.nodes]

    embs = model.encode(lemmas, normalize_embeddings=True, show_progress_bar=False)

    sims: Dict[Tuple[int, int], float] = {}
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            score = float(np.dot(embs[i], embs[j]))
            if score > 0.35:
                sims[(ids[i], ids[j])] = round(score, 3)
                sims[(ids[j], ids[i])] = round(score, 3)
    return sims


def get_top_similar(
    node_id: int,
    sims: Dict[Tuple[int, int], float],
    graph: SemanticGraph,
    top_k: int = 3,
) -> list:
    """
    Возвращает топ-k узлов, наиболее семантически близких к данному.
    Список: [(score, SemNode), ...] отсортирован по убыванию score.
    """
    id_to_node = {n.id: n for n in graph.nodes}
    candidates = []
    for (src, dst), score in sims.items():
        if src == node_id and dst != node_id:
            node = id_to_node.get(dst)
            if node:
                candidates.append((score, node))
    candidates.sort(key=lambda x: -x[0])
    return candidates[:top_k]


def is_sentence_transformers_available() -> bool:
    """Проверяет, установлен ли пакет sentence-transformers."""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False
