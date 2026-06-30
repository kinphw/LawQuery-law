"""해외법령 카탈로그(ldb_auth.foreign_catalog) — dev/prod 편집 + 개발→운영 복제.

editor.foreign_catalog_db 의 연결-주입 코어(_ensure/_list/_upsert/_delete)를 재사용.
prod 는 직접연결이 안 되므로 replicate 의 SSH 터널을 태워 접속(regstore 와 동일 방식).
"""
import pymysql

from common import db as _db
from common import replicate as _rep
from editor import foreign_catalog_db as fcat


def _open(target: str):
    """(conn, tunnel) — dev: 직접, prod: SSH 터널. tunnel 은 호출자가 stop()."""
    if target == "prod":
        tunnel, port = _rep._open_tunnel(lambda *a, **k: None)
        conf = _db._conf("prod")
        if tunnel:
            conf["host"], conf["port"] = "127.0.0.1", port
        conf["database"] = fcat.AUTH_DB
        return pymysql.connect(**conf), tunnel
    return _db.get_connection(database=fcat.AUTH_DB, target="dev"), None


def overview(target: str) -> dict:
    """카탈로그 행 + 미등록(fin_law_db.law 에 있으나 catalog 에 없는) 법."""
    conn, tunnel = _open(target)
    try:
        fcat._ensure(conn)
        conn.commit()
        rows = fcat._list(conn)
        metas = fcat._law_metas(conn)  # cross-db: 같은 인스턴스의 fin_law_db.law
    finally:
        conn.close()
        if tunnel:
            tunnel.stop()
    have = {r["code"] for r in rows}
    unregistered = [m for m in metas if m["code"] not in have]
    return {"target": target, "rows": rows, "unregistered": unregistered, "law_total": len(metas)}


def save(target: str, row: dict) -> None:
    conn, tunnel = _open(target)
    try:
        fcat._ensure(conn)
        fcat._upsert(conn, row)
        conn.commit()
    finally:
        conn.close()
        if tunnel:
            tunnel.stop()


def remove(target: str, code: str) -> int:
    conn, tunnel = _open(target)
    try:
        n = fcat._delete(conn, code)
        conn.commit()
        return n
    finally:
        conn.close()
        if tunnel:
            tunnel.stop()


# ── 개발 → 운영 일괄 복제(운영 카탈로그를 개발과 동일하게) ──────────────────
def _dev_rows() -> list[dict]:
    conn = _db.get_connection(database=fcat.AUTH_DB, target="dev")
    try:
        fcat._ensure(conn)
        conn.commit()
        return fcat._list(conn)
    finally:
        conn.close()


def _diff(dev_rows: list[dict], prod_rows: list[dict]) -> dict:
    dmap = {r["code"]: r for r in dev_rows}
    pmap = {r["code"]: r for r in prod_rows}
    added = [c for c in dmap if c not in pmap]
    removed = [c for c in pmap if c not in dmap]
    changed = [c for c, d in dmap.items()
               if c in pmap and any(d.get(k) != pmap[c].get(k) for k in fcat.FIELDS)]
    return {"added": sorted(added), "removed": sorted(removed), "changed": sorted(changed)}


def _summary(dev_rows, prod_rows) -> dict:
    d = _diff(dev_rows, prod_rows)
    d["dev_count"] = len(dev_rows)
    d["prod_count"] = len(prod_rows)
    d["unchanged"] = not (d["added"] or d["removed"] or d["changed"])
    return d


def replicate_preview() -> dict:
    """개발→운영 복제 시 적용될 변경 미리보기(쓰기 없음)."""
    dev_rows = _dev_rows()
    conn, tunnel = _open("prod")
    try:
        fcat._ensure(conn)
        conn.commit()
        prod_rows = fcat._list(conn)
    finally:
        conn.close()
        if tunnel:
            tunnel.stop()
    return _summary(dev_rows, prod_rows)


def replicate_to_prod() -> dict:
    """운영 foreign_catalog 를 개발과 **완전히 동일**하게 만든다(전체 교체, 단일 트랜잭션)."""
    dev_rows = _dev_rows()
    conn, tunnel = _open("prod")
    try:
        fcat._ensure(conn)
        conn.commit()
        prod_rows = fcat._list(conn)  # 적용 전 상태(요약용)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM foreign_catalog")
        for r in dev_rows:
            fcat._upsert(conn, r)
        conn.commit()
        s = _summary(dev_rows, prod_rows)
        s["copied"] = len(dev_rows)
        return s
    finally:
        conn.close()
        if tunnel:
            tunnel.stop()
