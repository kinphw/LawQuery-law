"""
rdb 매핑 점검/편집 데이터층 — 하위규정 조문별로 '상위규정 위임(rdb)' 현황을 보고 직접 수정.

rdb: id_start(상위) → id_end(하위). 실무는 "전체 하위규정에 대해 상위규정을 찾아 매핑"이라,
하위 단(db_e/s/r/b)을 조문별로 펼쳐 각 id 를 id_end 로 갖는 엣지를 보여주고 추가/수정/삭제한다.
편집용 surrogate _pk 는 record_db.ensure_editable 로 보장.
"""
import pymysql

from common.db import get_connection
from editor import record_db

_LEVELS = ["a", "e", "s", "r", "b"]


def _conn(code, target):
    return get_connection(database=f"ldb_{code}", target=target)


def ensure_pk(code, target="dev"):
    """rdb 등 PK 없는 테이블에 surrogate _pk 부여(idempotent)."""
    record_db.ensure_editable(code, target)


def levels(code, target="dev") -> list[str]:
    """db_meta 에 존재하는 레벨(a/e/s/r/b) 순서."""
    conn = _conn(code, target)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT origin FROM db_meta")
            present = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()
    return [lv for lv in _LEVELS if lv in present]


def lower_rows(code, level, target="dev") -> list[dict]:
    """선택 하위 단의 조문 행: [{id, content, seq}] (id 있는 행만, seq 순)."""
    conn = _conn(code, target)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                f"SELECT seq, id_{level} AS id, content_{level} AS content "
                f"FROM db_{level} "
                f"WHERE id_{level} IS NOT NULL AND content_{level} IS NOT NULL "
                f"ORDER BY seq"
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def mapped_id_ends(code, target="dev") -> set:
    """rdb 에 id_end 로 한 번이라도 나오는 id 집합(미매핑 판별용)."""
    conn = _conn(code, target)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT id_end FROM rdb")
            return {r[0] for r in cur.fetchall()}
    finally:
        conn.close()


def upstream(code, id_end, present_levels, target="dev") -> list[dict]:
    """id_end(하위 조문) 를 받는 rdb 엣지 + 상위 본문: [{pk, id_start, content}]."""
    joins = " ".join(
        f"LEFT JOIN db_{lv} x_{lv} ON x_{lv}.id_{lv} = r.id_start" for lv in present_levels
    )
    coal = "COALESCE(" + ", ".join(f"x_{lv}.content_{lv}" for lv in present_levels) + ")"
    conn = _conn(code, target)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                f"SELECT r._pk AS pk, r.id_start AS id_start, {coal} AS content "
                f"FROM rdb r {joins} WHERE r.id_end = %s ORDER BY r.id_start",
                (id_end,),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def search_upper(code, level, query, target="dev", limit=300) -> list[dict]:
    """상위 단(level) 본문 검색 → [{id, content}] (픽커용). query 비면 전체(상위 limit)."""
    conn = _conn(code, target)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            if query:
                cur.execute(
                    f"SELECT id_{level} AS id, content_{level} AS content FROM db_{level} "
                    f"WHERE id_{level} IS NOT NULL AND content_{level} LIKE %s ORDER BY seq LIMIT %s",
                    (f"%{query}%", limit),
                )
            else:
                cur.execute(
                    f"SELECT id_{level} AS id, content_{level} AS content FROM db_{level} "
                    f"WHERE id_{level} IS NOT NULL ORDER BY seq LIMIT %s",
                    (limit,),
                )
            return list(cur.fetchall())
    finally:
        conn.close()


def _level_of(id_value: str) -> str:
    return (id_value[:1] or "").lower()


def exists(code, id_value, target="dev") -> bool:
    """id_value 가 해당 단 테이블에 실제 존재하나(dangling 방지)."""
    lv = _level_of(id_value)
    if lv not in _LEVELS:
        return False
    conn = _conn(code, target)
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(f"SELECT 1 FROM db_{lv} WHERE id_{lv}=%s LIMIT 1", (id_value,))
            except pymysql.err.ProgrammingError:
                return False  # 그 단 테이블 자체가 없음
            return cur.fetchone() is not None
    finally:
        conn.close()


def edge_exists(code, id_start, id_end, target="dev") -> bool:
    conn = _conn(code, target)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM rdb WHERE id_start=%s AND id_end=%s LIMIT 1", (id_start, id_end)
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def _validate(code, id_start, id_end, target):
    """추가/수정 공통 검증. 통과 못하면 ValueError."""
    if not id_start:
        raise ValueError("상위 id 가 비었습니다.")
    if not exists(code, id_start, target):
        raise ValueError(f"상위 조문 id '{id_start}' 가 존재하지 않습니다 (dangling).")
    if edge_exists(code, id_start, id_end, target):
        raise ValueError(f"이미 있는 매핑입니다: {id_start} → {id_end}")


def add_edge(code, id_start, id_end, target="dev") -> int:
    """검증 후 rdb INSERT. id 컬럼은 MAX+1. 새 _pk 반환(로그용)."""
    _validate(code, id_start, id_end, target)
    conn = _conn(code, target)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM rdb")
            next_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO rdb (id, id_start, id_end) VALUES (%s, %s, %s)",
                (next_id, id_start, id_end),
            )
            pk = cur.lastrowid  # surrogate _pk(AUTO_INCREMENT)
        conn.commit()
        return pk
    finally:
        conn.close()


def update_start(code, pk, new_id_start, id_end, target="dev") -> int:
    """엣지(_pk) 의 상위(id_start) 교체. 동일 검증. 영향 행수 반환(0이면 변경 없음)."""
    _validate(code, new_id_start, id_end, target)
    conn = _conn(code, target)
    try:
        with conn.cursor() as cur:
            n = cur.execute("UPDATE rdb SET id_start=%s WHERE _pk=%s", (new_id_start, pk))
        conn.commit()
        return n
    finally:
        conn.close()


def delete_edge(code, pk, target="dev") -> int:
    """rdb 엣지 삭제. 영향 행수 반환(0이면 이미 없음)."""
    conn = _conn(code, target)
    try:
        with conn.cursor() as cur:
            n = cur.execute("DELETE FROM rdb WHERE _pk=%s", (pk,))
        conn.commit()
        return n
    finally:
        conn.close()
