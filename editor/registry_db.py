"""
법령 목록(law_registry) 관리 — 공용 DB `ldb_auth` 의 카탈로그 테이블.

per-law(ldb_<code>) 콘텐츠 편집(record_db)과는 **별개의 관리자 영역**이다.
웹앱의 GET /api/law/list 가 이 표를 단일 출처로 읽어 드롭다운/설정을 구성한다.
새 법령 = ldb_<code> 적재 + 여기 1행 등록.
"""
import os
import pymysql

from common.db import get_connection

# 웹 백엔드와 동일 컨벤션(.env AUTH_DB, 없으면 ldb_auth)
AUTH_DB = os.getenv("AUTH_DB") or "ldb_auth"

# db/law_registry.sql 과 동일. 관리창을 열면 없을 때 자동 생성(idempotent).
_DDL = """
CREATE TABLE IF NOT EXISTS law_registry (
  code        VARCHAR(16)  NOT NULL,
  label       VARCHAR(200) NULL,
  sort_order  INT          NOT NULL DEFAULT 100,
  enabled     TINYINT      NOT NULL DEFAULT 1,
  kind        VARCHAR(20)  NOT NULL DEFAULT 'law',
  PRIMARY KEY (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci
"""


def _conn(target: str):
    return get_connection(database=AUTH_DB, target=target)


def ensure_table(target: str = "dev") -> None:
    conn = _conn(target)
    try:
        with conn.cursor() as cur:
            cur.execute(_DDL)
        conn.commit()
    finally:
        conn.close()


def list_registry(target: str = "dev") -> list[dict]:
    conn = _conn(target)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT code, label, sort_order, enabled, kind "
                "FROM law_registry ORDER BY sort_order, code"
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def upsert(code: str, label, sort_order: int, enabled: bool, kind: str, target: str = "dev") -> None:
    conn = _conn(target)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO law_registry (code, label, sort_order, enabled, kind) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "  label=VALUES(label), sort_order=VALUES(sort_order), "
                "  enabled=VALUES(enabled), kind=VALUES(kind)",
                (code, (label or None), int(sort_order), 1 if enabled else 0, (kind or "law")),
            )
        conn.commit()
    finally:
        conn.close()


def delete(code: str, target: str = "dev") -> int:
    conn = _conn(target)
    try:
        with conn.cursor() as cur:
            n = cur.execute("DELETE FROM law_registry WHERE code=%s", (code,))
        conn.commit()
        return n
    finally:
        conn.close()


def unregistered_codes(target: str = "dev") -> list[str]:
    """서버에 존재하는 ldb_* DB 중 아직 law_registry 에 없는 코드(추가 도우미용)."""
    conn = get_connection(target=target)  # 서버 레벨
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA "
                "WHERE SCHEMA_NAME LIKE 'ldb\\_%'"
            )
            names = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()
    skip = {"ldb_auth", "ldb_i"}  # 공용/유권해석 DB는 법령 아님
    codes = [n[4:] for n in names if n not in skip]  # 'ldb_' 제거
    registered = {r["code"] for r in list_registry(target)}
    return sorted(c for c in codes if c not in registered)
