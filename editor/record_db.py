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


import re as _re

_TIER_OF = {"A": "a", "E": "e", "S": "s", "R": "r"}


def _reconnect_rdb(cur, jo_id: str, child_ids: set, level: str) -> int:
    """분리된 조가 상위(id_start)인 rdb 엣지를, 하위 본문의 '제N조제M항[제K호]' 인용 기준으로
    정밀 자식(jo_id_Mh[_Kho])에 재연결. 못 찾으면 조에 유지. 재연결 건수 반환."""
    m = _re.match(r"^([AESR])(\d+)(?:_(\d+))?$", jo_id)
    if not m:
        return 0
    jonum, ga = m.group(2), m.group(3)
    jo_pat = rf"제{jonum}조" + (rf"의{ga}" if ga else "")
    pat = _re.compile(jo_pat + r"제(\d+)항(?:제(\d+)호)?")
    cur.execute("SELECT _pk, id_end FROM rdb WHERE id_start=%s", (jo_id,))
    edges = cur.fetchall()
    cnt = 0
    for e in edges:
        end = e["id_end"]
        et = _TIER_OF.get(end[0])
        if not et:
            continue
        cur.execute(f"SELECT content_{et} AS c FROM db_{et} WHERE id_{et}=%s", (end,))
        row = cur.fetchone()
        mm = pat.search((row or {}).get("c") or "")
        if not mm:
            continue
        tgt = f"{jo_id}_{int(mm.group(1))}h"
        if mm.group(2) and level == "hangho" and f"{tgt}_{int(mm.group(2))}ho" in child_ids:
            tgt = f"{tgt}_{int(mm.group(2))}ho"
        if tgt in child_ids:
            cur.execute("UPDATE rdb SET id_start=%s WHERE _pk=%s", (tgt, e["_pk"]))
            cnt += 1
    return cnt


def split_article_op(code: str, sheet: str, parent_pk, level: str = "hang",
                     target: str = "dev") -> dict:
    """조 1개를 항/호 자식으로 분리(트랜잭션): 부모 stem UPDATE + 자식 INSERT + seq 재배열 + rdb 자동재연결."""
    from lawparse.article_split import split_article
    table, cols = SHEETS[sheet]
    idcol, ccol = f"id_{sheet}", f"content_{sheet}"
    conn = _conn(code, target)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(f"SELECT * FROM `{table}` WHERE `_pk`=%s", (parent_pk,))
            p = cur.fetchone()
            if not p or not p.get(idcol):
                raise ValueError("분리 대상 조 행을 찾을 수 없습니다(또는 장/절 제목행).")
            jo_id, seq = p[idcol], p["seq"]
            stem, children = split_article(jo_id, p[ccol] or "", level)
            if not children:
                return {"children": 0, "repointed": 0, "msg": "분리할 항/호가 없습니다."}
            n = len(children)
            cur.execute(f"UPDATE `{table}` SET `{ccol}`=%s WHERE `_pk`=%s", (stem, parent_pk))
            cur.execute(f"UPDATE `{table}` SET `seq`=`seq`+%s WHERE `seq`>%s", (n, seq))
            collist = ", ".join(f"`{c}`" for c in cols)
            ph = ", ".join(["%s"] * len(cols))
            for i, (cid, ctext) in enumerate(children, 1):
                row = {"seq": seq + i, idcol: cid, ccol: ctext}
                if sheet == "a":
                    row["id_aa"] = p.get("id_aa") or jo_id
                    row["title_a"] = p.get("title_a")
                cur.execute(f"INSERT INTO `{table}` ({collist}) VALUES ({ph})",
                            [row.get(c) for c in cols])
            repointed = _reconnect_rdb(cur, jo_id, {c for c, _ in children}, level)
        conn.commit()
        return {"children": n, "repointed": repointed, "ids": [c for c, _ in children]}
    finally:
        conn.close()
