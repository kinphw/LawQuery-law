"""해외법령(fin_law_db) — 개발계 → 운영계 **법률(code) 단위** 정확복제.

국내 ldb_<code> 와 달리 해외법령은 단일 DB `fin_law_db` 안에 모든 나라 법이
`law` + `law_provision` 행으로 공존한다. 따라서 DB 통째 덤프(다른 나라 법까지
DROP)가 아니라, **선택한 code 한 건의 law + 그 law_provision 만** 트랜잭션으로
갈아끼운다(다른 법 무해). STN dbload.upsert_law 와 같은 멱등 의미론:
prod 에서 `DELETE FROM law WHERE code=?`(FK CASCADE) → 새 id 로 재삽입.

- 물리 id 는 prod 가 새로 부여(dev id 가 prod 의 다른 법과 충돌 방지).
- 메모(`ldb_auth.foreign_memo`)는 논리키(law_code,article_no,seg_index)라 id 변경에 무관 → 손대지 않음.
- 원문·번역(text_ko/heading_ko) 컬럼을 dev asis 그대로 복사 → "운영 = dev 정확복제".

여러 code 는 **터널 1회**로 순회하며 각 code 를 독립 트랜잭션(코드별 커밋)으로 복제
→ 일부 실패해도 성공분은 보존(부분 성공). 진입점:
    python -m common.replicate_foreign <code> [<code2> ...]   (예: eu_psd2 / eu_psd2 eu_psr)
"""
import sys

import pymysql
from pymysql.cursors import DictCursor

from common import db as _db
from common.replicate import _open_tunnel

FIN_DB = "fin_law_db"
# 지문(staleness) 민감 컬럼 후보 — 실제 존재하는 것만 사용(스키마 드리프트 안전)
_SIG_COLS = ["article_no", "para_no", "heading", "heading_ko", "text_original", "text_ko"]


def _conn(target: str, tunnel=None, port=None):
    conf = _db._conf(target)
    conf["database"] = FIN_DB
    conf["cursorclass"] = DictCursor
    if tunnel:
        conf["host"], conf["port"] = "127.0.0.1", port
    return pymysql.connect(**conf)


def _columns(conn, table: str) -> set:
    with conn.cursor() as cur:
        cur.execute(f"SHOW COLUMNS FROM {table}")
        return {r["Field"] for r in cur.fetchall()}


def _collist(cols) -> str:
    return ", ".join(f"`{c}`" for c in cols)


def _read_dev(dev, code: str):
    """개발계에서 code 의 law 1행 + 그 law_provision 전부. 없으면 (None, None)."""
    with dev.cursor() as cur:
        cur.execute("SELECT * FROM law WHERE code=%s", (code,))
        law = cur.fetchone()
        if not law:
            return None, None
        cur.execute(
            "SELECT * FROM law_provision WHERE law_id=%s ORDER BY ordinal, id",
            (law["id"],),
        )
        return law, cur.fetchall()


def _write_prod(prod, code, law, provisions, law_cols_prod, prov_cols_prod, log) -> int:
    """운영계에서 code 를 한 트랜잭션으로 교체(DELETE→INSERT) 후 커밋. 새 law_id 반환."""
    # law: id 제외 + dev/prod 공통 컬럼만 / provision: id·law_id 제외(law_id 는 새 id 강제)
    law_cols = [c for c in law.keys() if c in law_cols_prod and c != "id"]
    prov_cols = ([c for c in provisions[0].keys()
                  if c in prov_cols_prod and c not in ("id", "law_id")]
                 if provisions else [])
    with prod.cursor() as cur:
        cur.execute("DELETE FROM law WHERE code=%s", (code,))   # FK CASCADE → 옛 provision 제거
        deleted = cur.rowcount
        cur.execute(
            f"INSERT INTO law ({_collist(law_cols)}) "
            f"VALUES ({', '.join(['%s'] * len(law_cols))})",
            [law[c] for c in law_cols],
        )
        new_id = cur.lastrowid
        if provisions:
            cols = ["law_id"] + prov_cols
            cur.executemany(
                f"INSERT INTO law_provision ({_collist(cols)}) "
                f"VALUES ({', '.join(['%s'] * len(cols))})",
                [[new_id] + [p[c] for c in prov_cols] for p in provisions],
            )
    prod.commit()
    log(f"[foreign] '{code}': 운영 기존 {deleted}행 교체 → law_id={new_id}, "
        f"provision {len(provisions)}행 적재 · 커밋")
    return new_id


def replicate_foreign_many(codes, log=print) -> None:
    """여러 code 를 터널 1회로 순회 복제(코드별 독립 트랜잭션 = 부분 성공 보존)."""
    codes = [c for c in codes if c]
    if not codes:
        log("[foreign] 이관할 code 가 없습니다.")
        return
    dev = _conn("dev")
    tunnel, port = _open_tunnel(log)
    prod = None
    ok, fail = [], []
    try:
        prod = _conn("prod", tunnel, port)
        law_cols_prod = _columns(prod, "law")
        prov_cols_prod = _columns(prod, "law_provision")
        for code in codes:
            try:
                law, provisions = _read_dev(dev, code)
                if not law:
                    log(f"[foreign] ⚠ '{code}': 개발계에 없음 — 건너뜀")
                    fail.append(code)
                    continue
                log(f"[foreign] dev '{code}': law 1행 + provision {len(provisions)}행 읽음")
                _write_prod(prod, code, law, provisions, law_cols_prod, prov_cols_prod, log)
                ok.append(code)
            except Exception as e:  # noqa: BLE001
                if prod:
                    prod.rollback()
                log(f"[foreign] ✖ '{code}' 실패(롤백): {e}")
                fail.append(code)
        log(f"[foreign] ✅ 완료 — 성공 {len(ok)}건"
            + (f"({', '.join(ok)})" if ok else "")
            + (f" · 실패 {len(fail)}건({', '.join(fail)})" if fail else "")
            + " · 메모는 논리키라 무영향")
    finally:
        dev.close()
        if prod:
            prod.close()
        if tunnel:
            tunnel.stop()
            log("[foreign] SSH 터널 닫힘")


def replicate_foreign(code: str, log=print) -> None:
    """dev fin_law_db 의 code 한 건을 운영 fin_law_db 로 복제(단일 = many 의 1건)."""
    replicate_foreign_many([code], log)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("사용법: python -m common.replicate_foreign <code> [<code2> ...]   (예: eu_psd2)")
        sys.exit(1)
    replicate_foreign_many(sys.argv[1:])
