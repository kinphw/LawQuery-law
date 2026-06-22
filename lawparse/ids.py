"""
정규화 Article → 단별 DB 행(+ID, seq). ID 규약은 CLAUDE.md.

Article(공통 입력 — API/텍스트 둘 다 이 형태로 정규화):
  {'jo':2, 'ga':None, 'title':'제2조(정의)', 'stem':'제2조(정의) …', 'items':[' 1. …', ' 2. …']}
  {'type':'title', 'title':'제1장 총칙'}   # 장/절 (db_a 만)
"""
_UP = {'a': 'A', 'e': 'E', 's': 'S', 'r': 'R'}


def stem_id(tier: str, jo, ga=None) -> str:
    base = f"{_UP[tier]}{jo}"
    return f"{base}_{ga}" if ga else base


def rows_for_tier(tier: str, articles: list[dict]) -> list[dict]:
    rows: list[dict] = []
    seq = 0
    for art in articles:
        if art.get('type') == 'title':
            if tier == 'a':  # 장/절 제목행은 db_a 만
                seq += 1
                rows.append({'seq': seq, 'id_aa': None, 'id_a': None,
                             'title_a': art['title'], 'content_a': art['title'],
                             'content_a_sched': None, 'sched_date': None})
            continue
        sid = stem_id(tier, art['jo'], art.get('ga'))
        seq += 1
        rows.append(_row(tier, seq, sid, sid, art['title'], art['stem']))
        for k, item in enumerate(art.get('items', []), 1):
            seq += 1
            rows.append(_row(tier, seq, sid, f"{sid}_{k}h", art['title'], item))
    return rows


def _row(tier, seq, id_aa, node_id, title, content):
    if tier == 'a':
        return {'seq': seq, 'id_aa': id_aa, 'id_a': node_id, 'title_a': title,
                'content_a': content, 'content_a_sched': None, 'sched_date': None}
    return {'seq': seq, f'id_{tier}': node_id, f'content_{tier}': content,
            f'content_{tier}_sched': None, 'sched_date': None}
