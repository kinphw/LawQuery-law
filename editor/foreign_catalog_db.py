"""
해외법령 카탈로그(ldb_auth.foreign_catalog) — 표시·분류·설명 큐레이션. LawQuery 소유.

sentinel(fin_law_db.law)은 원문 적재 시 manifest 메타를 DELETE+INSERT 로 매번 덮어쓰므로,
LQ 가 편집할 메타·설명은 여기(ldb_auth.foreign_catalog)에 둔다. 웹앱 카탈로그 렌더 =
law(폴백) ⊕ foreign_catalog(우선). editor.registry_db 와 동일한 연결-주입 코어.
"""
import os
import json
import pymysql

from common.db import get_connection

AUTH_DB = os.getenv("AUTH_DB") or "ldb_auth"
FIN_DB = os.getenv("FIN_DB") or "fin_law_db"

# LawQuery/db/foreign_catalog.sql 과 동일. collation 은 fin_law_db.law(unicode_ci)와 일치해야
# 웹앱의 law ⊕ foreign_catalog cross-db JOIN 이 깨지지 않는다.
_DDL = """
CREATE TABLE IF NOT EXISTS foreign_catalog (
  code         VARCHAR(48)  NOT NULL,
  jurisdiction VARCHAR(16)  DEFAULT NULL,
  title_ko     VARCHAR(512) DEFAULT NULL,
  abbrev       VARCHAR(64)  DEFAULT NULL,
  status       VARCHAR(32)  DEFAULT NULL,
  law_type     VARCHAR(40)  DEFAULT NULL,
  is_crypto    TINYINT(1)   DEFAULT NULL,
  summary      TEXT         DEFAULT NULL,
  tags         JSON         DEFAULT NULL,
  highlights   JSON         DEFAULT NULL,
  sort_order   INT          NOT NULL DEFAULT 100,
  hidden       TINYINT(1)   NOT NULL DEFAULT 0,
  updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# 복제 diff 비교 대상 필드(code/updated_at 제외)
FIELDS = ("jurisdiction", "title_ko", "abbrev", "status", "law_type", "is_crypto",
          "summary", "tags", "highlights", "sort_order", "hidden")


def _conn(target: str):
    return get_connection(database=AUTH_DB, target=target)


def _loads(v):
    """MariaDB JSON 은 LONGTEXT alias → 문자열로 옴. 리스트로 파싱(None→[])."""
    if not v:
        return []
    if isinstance(v, list):
        return v
    try:
        a = json.loads(v)
        return a if isinstance(a, list) else []
    except Exception:
        return []


# ── 연결-주입 코어(conn 받음) — 대시보드가 SSH 터널 연결로 재사용 ──────────
def _ensure(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_DDL)


def _list(conn) -> list[dict]:
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(
            "SELECT code, jurisdiction, title_ko, abbrev, status, law_type, is_crypto, "
            "       summary, tags, highlights, sort_order, hidden "
            "FROM foreign_catalog "
            "ORDER BY FIELD(jurisdiction,'eu','us','jp','hk','sg','other'), sort_order, code"
        )
        rows = list(cur.fetchall())
    for r in rows:
        r["tags"] = _loads(r.get("tags"))
        r["highlights"] = _loads(r.get("highlights"))
        r["is_crypto"] = int(r["is_crypto"]) if r.get("is_crypto") is not None else None
        r["hidden"] = int(r.get("hidden") or 0)
    return rows


def _law_metas(conn) -> list[dict]:
    """미등록 도우미 — fin_law_db.law 의 code/제목/관할(catalog 에 없는 신규 법 표시)."""
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(
            f"SELECT code, title_ko, jurisdiction FROM {FIN_DB}.law "
            f"ORDER BY FIELD(jurisdiction,'eu','us','jp','hk','sg','other'), code"
        )
        return list(cur.fetchall())


def _upsert(conn, row: dict) -> None:
    tags = json.dumps(row.get("tags") or [], ensure_ascii=False)
    highlights = json.dumps(row.get("highlights") or [], ensure_ascii=False)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO foreign_catalog "
            "(code, jurisdiction, title_ko, abbrev, status, law_type, is_crypto, "
            " summary, tags, highlights, sort_order, hidden) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            "  jurisdiction=VALUES(jurisdiction), title_ko=VALUES(title_ko), abbrev=VALUES(abbrev), "
            "  status=VALUES(status), law_type=VALUES(law_type), is_crypto=VALUES(is_crypto), "
            "  summary=VALUES(summary), tags=VALUES(tags), highlights=VALUES(highlights), "
            "  sort_order=VALUES(sort_order), hidden=VALUES(hidden)",
            (row["code"], row.get("jurisdiction") or None, row.get("title_ko") or None,
             row.get("abbrev") or None, row.get("status") or None, row.get("law_type") or None,
             (None if row.get("is_crypto") is None else (1 if row.get("is_crypto") else 0)),
             row.get("summary") or None, tags, highlights,
             int(row.get("sort_order") or 100), 1 if row.get("hidden") else 0),
        )


def _delete(conn, code: str) -> int:
    with conn.cursor() as cur:
        return cur.execute("DELETE FROM foreign_catalog WHERE code=%s", (code,))
