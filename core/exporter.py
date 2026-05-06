"""
exporter.py — экспорт результатов анализа в разные форматы.
"""

import json
import os
from datetime import datetime
from typing import Optional
from core.analyzer import AnalysisResult


def export_txt(result: AnalysisResult, source_name: str, path: str) -> None:
    lines = []
    lines.append(f"ОТЧЁТ СЕМАНТИКО-СИНТАКСИЧЕСКОГО АНАЛИЗА")
    lines.append(f"Источник: {source_name}")
    lines.append(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    lines.append("=" * 60)

    s = result.stats
    lines.append(f"\nСТАТИСТИКА:")
    lines.append(f"  Предложений:      {s['sentence_count']}")
    lines.append(f"  Слов:             {s['word_count']}")
    lines.append(f"  Символов:         {s['char_count']}")
    lines.append(f"  Ср. длина слова:  {s['avg_word_len']}")
    lines.append(f"  Время анализа:    {result.elapsed_ms} мс")

    sent = result.sentiment
    lines.append(f"\nТОНАЛЬНОСТЬ: {sent['overall_ru'].upper()} (оценка: {sent['score']})")
    lines.append(f"  Позитивных слов:  {sent['positive_count']}")
    lines.append(f"  Негативных слов:  {sent['negative_count']}")

    if result.entities:
        lines.append(f"\nИМЕНОВАННЫЕ СУЩНОСТИ ({len(result.entities)}):")
        for e in result.entities:
            lines.append(f"  [{e.label_ru}] {e.text}")

    lines.append(f"\nРАСПРЕДЕЛЕНИЕ ЧАСТЕЙ РЕЧИ:")
    for pos, cnt in s['pos_distribution'][:10]:
        lines.append(f"  {pos:<25} {cnt}")

    lines.append(f"\nПРЕДЛОЖЕНИЯ И ТОКЕНЫ:")
    for sent_obj in result.sentences:
        lines.append(f"\n  [{sent_obj.id + 1}] {sent_obj.text}")
        lines.append(f"  {'Слово':<20} {'Лемма':<20} {'Часть речи':<22} {'Роль'}")
        lines.append(f"  {'-'*80}")
        for t in sent_obj.tokens:
            if t.pos != 'PUNCT':
                lines.append(f"  {t.word:<20} {t.lemma:<20} {t.pos_ru:<22} {t.dep_ru}")

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def export_json(result: AnalysisResult, source_name: str, path: str) -> None:
    data = {
        'source': source_name,
        'date': datetime.now().isoformat(),
        'elapsed_ms': result.elapsed_ms,
        'stats': {
            **result.stats,
            'pos_distribution': dict(result.stats['pos_distribution']),
            'dep_distribution': dict(result.stats['dep_distribution']),
        },
        'sentiment': result.sentiment,
        'entities': [
            {'text': e.text, 'label': e.label, 'label_ru': e.label_ru}
            for e in result.entities
        ],
        'sentences': [
            {
                'id': s.id,
                'text': s.text,
                'tokens': [
                    {
                        'word': t.word, 'lemma': t.lemma,
                        'pos': t.pos, 'pos_ru': t.pos_ru,
                        'dep': t.dep, 'dep_ru': t.dep_ru,
                        'head_id': t.head_id,
                    }
                    for t in s.tokens
                ],
            }
            for s in result.sentences
        ],
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export_html(result: AnalysisResult, source_name: str, path: str) -> None:
    sent = result.sentiment
    s = result.stats

    sentiment_color = {'positive': '#2e7d32', 'negative': '#c62828', 'neutral': '#1565c0'}
    color = sentiment_color.get(sent['overall'], '#333')

    entity_rows = ''.join(
        f'<tr><td>{e.label_ru}</td><td>{e.text}</td></tr>'
        for e in result.entities
    ) or '<tr><td colspan="2">Сущности не найдены</td></tr>'

    pos_rows = ''.join(
        f'<tr><td>{pos}</td><td>{cnt}</td>'
        f'<td><div class="bar" style="width:{min(cnt*2,300)}px"></div></td></tr>'
        for pos, cnt in s['pos_distribution'][:12]
    )

    sent_rows = ''
    for sobj in result.sentences:
        token_cells = ''.join(
            f'<td class="tok" title="{t.dep_ru}">'
            f'<span class="word">{t.word}</span>'
            f'<span class="pos">{t.pos_ru}</span>'
            f'</td>'
            for t in sobj.tokens if t.pos != 'PUNCT'
        )
        sent_rows += f'<tr><td class="sidx">{sobj.id+1}</td><td>{sobj.text[:80]}…</td><td><table class="toks"><tr>{token_cells}</tr></table></td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Анализ: {source_name}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; margin: 0; background: #f5f5f5; color: #212121; }}
  .header {{ background: #1565c0; color: white; padding: 24px 32px; }}
  .header h1 {{ margin: 0; font-size: 1.6em; }}
  .header p {{ margin: 4px 0 0; opacity: .8; font-size: .9em; }}
  .content {{ padding: 24px 32px; }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
  .card {{ background: white; border-radius: 8px; padding: 16px 20px; box-shadow: 0 1px 4px rgba(0,0,0,.1); min-width: 160px; }}
  .card .val {{ font-size: 2em; font-weight: 700; color: #1565c0; }}
  .card .lbl {{ font-size: .8em; color: #666; margin-top: 4px; }}
  .sentiment {{ background: white; border-radius: 8px; padding: 16px 20px; box-shadow: 0 1px 4px rgba(0,0,0,.1); margin-bottom: 24px; }}
  .sentiment .label {{ font-size: 1.4em; font-weight: 700; color: {color}; }}
  h2 {{ color: #1565c0; margin-top: 32px; }}
  table {{ border-collapse: collapse; width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  th {{ background: #1565c0; color: white; padding: 10px 14px; text-align: left; font-size: .85em; }}
  td {{ padding: 8px 14px; border-bottom: 1px solid #eee; font-size: .9em; }}
  .bar {{ height: 14px; background: #90caf9; border-radius: 4px; }}
  .toks {{ box-shadow: none; }}
  .tok {{ vertical-align: top; padding: 2px 4px; }}
  .word {{ display: block; font-weight: 600; font-size: .85em; }}
  .pos {{ display: block; font-size: .7em; color: #888; }}
  .sidx {{ color: #999; font-size: .8em; width: 30px; }}
</style>
</head>
<body>
<div class="header">
  <h1>СинтАналитик — Отчёт анализа</h1>
  <p>Источник: <strong>{source_name}</strong> · {datetime.now().strftime('%d.%m.%Y %H:%M')} · Время анализа: {result.elapsed_ms} мс</p>
</div>
<div class="content">
  <div class="cards">
    <div class="card"><div class="val">{s['sentence_count']}</div><div class="lbl">Предложений</div></div>
    <div class="card"><div class="val">{s['word_count']}</div><div class="lbl">Слов</div></div>
    <div class="card"><div class="val">{s['char_count']}</div><div class="lbl">Символов</div></div>
    <div class="card"><div class="val">{s['avg_word_len']}</div><div class="lbl">Ср. длина слова</div></div>
    <div class="card"><div class="val">{len(result.entities)}</div><div class="lbl">Сущностей</div></div>
  </div>
  <div class="sentiment">
    <div class="label">Тональность: {sent['overall_ru'].upper()}</div>
    <p>Оценка: <strong>{sent['score']}</strong> · Позитивных слов: {sent['positive_count']} · Негативных слов: {sent['negative_count']}</p>
  </div>
  <h2>Именованные сущности</h2>
  <table><thead><tr><th>Тип</th><th>Текст</th></tr></thead><tbody>{entity_rows}</tbody></table>
  <h2>Распределение частей речи</h2>
  <table><thead><tr><th>Часть речи</th><th>Кол-во</th><th>Диаграмма</th></tr></thead><tbody>{pos_rows}</tbody></table>
  <h2>Предложения</h2>
  <table><thead><tr><th>#</th><th>Текст</th><th>Токены (наведите для роли)</th></tr></thead><tbody>{sent_rows}</tbody></table>
</div>
</body>
</html>"""

    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
