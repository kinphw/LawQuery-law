"""dev/prod 해외법령(fin_law_db) 현황 — 법(code)별 지문으로 운영 지체 비교.

국내(dbstate)는 ldb_<code> DB별 db_meta 를 읽지만, 해외는 단일 fin_law_db 안의
law + law_provision 을 GROUP 해 법별 지문을 만든다:
  provision_count(구조) · ko_count(번역 커버리지) · content_sig(원문/번역 내용 CRC 합).
dev/prod 지문이 다르면 '운영 지체'. 운영(prod)은 replicate 의 SSH 터널을 재사용해 접속.

preview(code): 이관 전 미리보기 — dev/prod 를 seg 논리키((article_no,seg_index))로
대조해 조(article) 단위로 신규/변경/삭제를 집계한다(메모 키와 동일한 안정 앵커).
"""
import re

import pymysql

from common import db as _db
from common import replicate as _rep
from common.replicate_foreign import FIN_DB, _SIG_COLS

JURIS_ORDER = "'eu','us','jp','hk','sg','other'"
# seg 내용 지문에 쓰는 컬럼(article_no 는 키라 제외)
_SEG_SIG_COLS = [c for c in _SIG_COLS if c != "article_no"]
_PREVIEW_CAP = 25  # 조 샘플 최대 표시 수


def _sig_expr(conn) -> str:
    """law_provision 의 실존 컬럼만으로 행별 내용 지문(CRC32 합) 식을 만든다."""
    with conn.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM law_provision")
        cols = {r[0] for r in cur.fetchall()}
    use = [c for c in _SIG_COLS if c in cols]
    parts = ", ".join(f"COALESCE(p.`{c}`,'')" for c in use)
    # 행별 CRC32 의 합(순서 무관) → 원문/번역 어떤 변경에도 민감, COUNT 와 함께 강한 지문
    return f"CAST(SUM(CRC32(CONCAT_WS(CHAR(31), {parts}))) AS UNSIGNED)"


def _collect(conn) -> list:
    sig = _sig_expr(conn)
    sql = f"""
        SELECT l.code, l.jurisdiction, l.title_ko, l.abbrev, l.status,
               l.law_type, l.is_crypto,
               COUNT(p.id) AS provision_count,
               CAST(SUM(p.text_ko IS NOT NULL AND p.text_ko <> '') AS UNSIGNED) AS ko_count,
               COALESCE({sig}, 0) AS content_sig
          FROM law l
          LEFT JOIN law_provision p ON p.law_id = l.id
         GROUP BY l.id
         ORDER BY FIELD(l.jurisdiction, {JURIS_ORDER}), l.code
    """
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    for r in rows:
        # JSON 직렬화 안전 + 프론트 비교용 정규화(content_sig 는 문자열로 정밀 비교)
        r["provision_count"] = int(r["provision_count"] or 0)
        r["ko_count"] = int(r["ko_count"] or 0)
        r["is_crypto"] = int(r["is_crypto"] or 0)
        r["content_sig"] = str(r["content_sig"] or "0")
    return rows


def dev_state() -> dict:
    conn = pymysql.connect(**{**_db._conf("dev"), "database": FIN_DB})
    try:
        return {"target": "dev", "laws": _collect(conn)}
    finally:
        conn.close()


def prod_state() -> dict:
    """SSH 터널(replicate 재사용)로 운영 MySQL 의 fin_law_db 에 붙어 현황을 읽는다."""
    tunnel, port = _rep._open_tunnel(lambda *a, **k: None)
    try:
        conf = _db._conf("prod")
        conf["database"] = FIN_DB
        if tunnel:
            conf["host"], conf["port"] = "127.0.0.1", port
        conn = pymysql.connect(**conf)
        try:
            return {"target": "prod", "laws": _collect(conn)}
        finally:
            conn.close()
    finally:
        if tunnel:
            tunnel.stop()


# ── 이관 전 미리보기(diff) ────────────────────────────────────────────────
def _law_exists(conn, code: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM law WHERE code=%s LIMIT 1", (code,))
        return cur.fetchone() is not None


def _read_segs(conn, code: str) -> dict:
    """code 의 seg 를 논리키 (article_no, seg_index) → (내용 CRC, has_ko) 로 읽는다.

    seg_index = ROW_NUMBER() OVER (PARTITION BY article_no ORDER BY ordinal) — foreign_memo 앵커와 동일.
    """
    with conn.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM law_provision")
        have = {r[0] for r in cur.fetchall()}
    use = [c for c in _SEG_SIG_COLS if c in have]
    parts = ", ".join(f"COALESCE(`{c}`,'')" for c in use)
    sql = f"""
        SELECT article_no,
               ROW_NUMBER() OVER (PARTITION BY article_no ORDER BY ordinal) AS seg_index,
               CRC32(CONCAT_WS(CHAR(31), {parts})) AS sig,
               (text_ko IS NOT NULL AND text_ko <> '') AS has_ko
          FROM law_provision
         WHERE law_id = (SELECT id FROM law WHERE code=%s)
         ORDER BY article_no, seg_index
    """
    out = {}
    with conn.cursor() as cur:
        cur.execute(sql, (code,))
        for article_no, seg_index, sig, has_ko in cur.fetchall():
            out[(article_no, int(seg_index))] = (int(sig or 0), int(has_ko or 0))
    return out


def _art_key(a: str):
    """조 번호 자연 정렬용 키('5' < '62의3' < 'ANNEX I')."""
    a = a or ""
    m = re.match(r"(\d+)", a)
    return (0, int(m.group(1)), a) if m else (1, 0, a)


def _diff(code, dev_exists, prod_exists, devsegs, prodsegs) -> dict:
    dev_arts, prod_arts = {}, {}
    for (art, si), (sig, _ko) in devsegs.items():
        dev_arts.setdefault(art, {})[si] = sig
    for (art, si), (sig, _ko) in prodsegs.items():
        prod_arts.setdefault(art, {})[si] = sig
    da, pa = set(dev_arts), set(prod_arts)
    added = sorted(da - pa, key=_art_key)
    removed = sorted(pa - da, key=_art_key)
    changed = sorted([a for a in (da & pa) if dev_arts[a] != prod_arts[a]], key=_art_key)

    def samp(lst):
        return {"count": len(lst), "sample": lst[:_PREVIEW_CAP], "more": max(0, len(lst) - _PREVIEW_CAP)}

    return {
        "code": code,
        "dev_exists": dev_exists, "prod_exists": prod_exists,
        "dev_segs": len(devsegs), "prod_segs": len(prodsegs),
        "dev_ko": sum(1 for v in devsegs.values() if v[1]),
        "prod_ko": sum(1 for v in prodsegs.values() if v[1]),
        "dev_articles": len(dev_arts), "prod_articles": len(prod_arts),
        "added": samp(added), "changed": samp(changed), "removed": samp(removed),
    }


def preview(code: str) -> dict:
    """이관 전 dev↔prod 조 단위 diff. 운영(prod)은 SSH 터널로 읽는다."""
    dev = pymysql.connect(**{**_db._conf("dev"), "database": FIN_DB})
    try:
        dev_exists = _law_exists(dev, code)
        devsegs = _read_segs(dev, code) if dev_exists else {}
    finally:
        dev.close()

    tunnel, port = _rep._open_tunnel(lambda *a, **k: None)
    try:
        conf = _db._conf("prod")
        conf["database"] = FIN_DB
        if tunnel:
            conf["host"], conf["port"] = "127.0.0.1", port
        prod = pymysql.connect(**conf)
        try:
            prod_exists = _law_exists(prod, code)
            prodsegs = _read_segs(prod, code) if prod_exists else {}
        finally:
            prod.close()
    finally:
        if tunnel:
            tunnel.stop()

    return _diff(code, dev_exists, prod_exists, devsegs, prodsegs)
