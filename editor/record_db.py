"""
레코드 단위 편집 엔진 — 지정 레코드만 INSERT/UPDATE/DELETE (TRUNCATE 아님).

- ensure_editable: PK 없는 테이블(rdb/ref/penalty*)에 surrogate `_pk` 부여(idempotent).
- read_law_editable: 행 + PK(__pk 숨김필드) 로드 → 에디터가 __pk 로 대상 레코드 지정.
- insert/update/delete_record: 그 레코드 하나만 즉시 반영.
"""
import pymysql

from common.db import get_connection
from common.schema_map import SHEETS, NEEDS_SURROGATE_PK, PK_COLUMN


def _conn(code, target):
    return get_connection(database=f"ldb_{code}", target=target)


def ensure_editable(code: str, target: str = "dev") -> None:
    """PK 없는 테이블에 편집용 _pk 추가. 이미 있으면 no-op."""
    conn = _conn(code, target)
    try:
        with conn.cursor() as cur:
            for sheet in NEEDS_SURROGATE_PK:
                table = SHEETS[sheet][0]
                try:
                    cur.execute(
                        f"ALTER TABLE `{table}` ADD COLUMN IF NOT EXISTS "
                        f"`_pk` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST"
                    )
                except pymysql.err.ProgrammingError:
                    pass  # 테이블 자체가 없음(penalty 미사용 등)
        conn.commit()
    finally:
        conn.close()


def read_law_editable(code: str, target: str = "dev") -> dict:
    """{sheet: [{col: val, ..., '__pk': pk}, ...]}  (PK 포함 로드)."""
    conn = _conn(code, target)
    data: dict = {}
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            for sheet, (table, cols) in SHEETS.items():
                pk = PK_COLUMN[sheet]
                sel = ", ".join(f"`{c}`" for c in dict.fromkeys([pk] + cols))
                order = " ORDER BY `seq`" if "seq" in cols else f" ORDER BY `{pk}`"
                try:
                    cur.execute(f"SELECT {sel} FROM `{table}`{order}")
                    rows = []
                    for r in cur.fetchall():
                        row = {c: r[c] for c in cols}
                        row["__pk"] = r[pk]
                        rows.append(row)
                    data[sheet] = rows
                except pymysql.err.ProgrammingError:
                    data[sheet] = []
    finally:
        conn.close()
    return data


def insert_record(code: str, sheet: str, row: dict, target: str = "dev"):
    """한 레코드 INSERT → 새 PK 반환."""
    table, cols = SHEETS[sheet]
    collist = ", ".join(f"`{c}`" for c in cols)
    ph = ", ".join(["%s"] * len(cols))
    conn = _conn(code, target)
    try:
        with conn.cursor() as cur:
            cur.execute(f"INSERT INTO `{table}` ({collist}) VALUES ({ph})",
                        [row.get(c) for c in cols])
            new_pk = cur.lastrowid
        conn.commit()
        return new_pk
    finally:
        conn.close()


def update_record(code: str, sheet: str, pk, row: dict, target: str = "dev") -> int:
    """PK로 지정한 한 레코드만 UPDATE. 영향 행수 반환."""
    table, cols = SHEETS[sheet]
    pkcol = PK_COLUMN[sheet]
    setclause = ", ".join(f"`{c}`=%s" for c in cols)
    conn = _conn(code, target)
    try:
        with conn.cursor() as cur:
            n = cur.execute(f"UPDATE `{table}` SET {setclause} WHERE `{pkcol}`=%s",
                            [row.get(c) for c in cols] + [pk])
        conn.commit()
        return n
    finally:
        conn.close()


def delete_record(code: str, sheet: str, pk, target: str = "dev") -> int:
    table, _cols = SHEETS[sheet]
    pkcol = PK_COLUMN[sheet]
    conn = _conn(code, target)
    try:
        with conn.cursor() as cur:
            n = cur.execute(f"DELETE FROM `{table}` WHERE `{pkcol}`=%s", (pk,))
        conn.commit()
        return n
    finally:
        conn.close()
