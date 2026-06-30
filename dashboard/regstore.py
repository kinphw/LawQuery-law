"""법령 노출 레지스트리(ldb_auth.law_registry) — dev/prod 편집.

editor.registry_db 의 연결-주입 코어(_ensure/_list/_upsert/_delete)를 재사용.
prod 는 직접연결이 안 되므로 replicate 의 SSH 터널을 태워 접속(dbstate 와 동일 방식).
"""
import pymysql

from common import db as _db
from common import replicate as _rep
from editor import registry_db

from . import dbstate


def _open(target: str):
    """(conn, tunnel) — dev: 직접, prod: SSH 터널. tunnel 은 호출자가 stop()."""
    if target == "prod":
        tunnel, port = _rep._open_tunnel(lambda *a, **k: None)
        conf = _db._conf("prod")
        if tunnel:
            conf["host"], conf["port"] = "127.0.0.1", port
        conf["database"] = registry_db.AUTH_DB
        return pymysql.connect(**conf), tunnel
    return _db.get_connection(database=registry_db.AUTH_DB, target="dev"), None


def overview(target: str) -> dict:
    """등록 행 + 미등록(ldb_* 존재하나 레지스트리에 없는) 코드."""
    conn, tunnel = _open(target)
    try:
        registry_db._ensure(conn)
        conn.commit()
        rows = registry_db._list(conn)
        registered = {r["code"] for r in rows}
        unregistered = [c for c in dbstate._law_codes(conn) if c not in registered]
        return {"target": target, "rows": rows, "unregistered": unregistered}
    finally:
        conn.close()
        if tunnel:
            tunnel.stop()


def save(target: str, code: str, label, sort_order: int, enabled: bool, kind: str) -> None:
    conn, tunnel = _open(target)
    try:
        registry_db._ensure(conn)
        registry_db._upsert(conn, code, label, sort_order, enabled, kind)
        conn.commit()
    finally:
        conn.close()
        if tunnel:
            tunnel.stop()


def remove(target: str, code: str) -> int:
    conn, tunnel = _open(target)
    try:
        n = registry_db._delete(conn, code)
        conn.commit()
        return n
    finally:
        conn.close()
        if tunnel:
            tunnel.stop()


# ── 개발 → 운영 일괄 복제(운영 레지스트리를 개발과 동일하게) ──────────────────
_FIELDS = ("label", "sort_order", "enabled", "kind")


def _dev_rows() -> list[dict]:
    conn = _db.get_connection(database=registry_db.AUTH_DB, target="dev")
    try:
        registry_db._ensure(conn)
        conn.commit()
        return registry_db._list(conn)
    finally:
        conn.close()


def _diff(dev_rows: list[dict], prod_rows: list[dict]) -> dict:
    """운영을 개발에 맞출 때의 추가/변경/삭제 코드 분류."""
    dmap = {r["code"]: r for r in dev_rows}
    pmap = {r["code"]: r for r in prod_rows}
    added = [c for c in dmap if c not in pmap]
    removed = [c for c in pmap if c not in dmap]
    changed = [c for c, d in dmap.items()
               if c in pmap and any(d.get(k) != pmap[c].get(k) for k in _FIELDS)]
    return {"added": sorted(added), "removed": sorted(removed), "changed": sorted(changed)}


def _summary(dev_rows, prod_rows, prod_codes) -> dict:
    d = _diff(dev_rows, prod_rows)
    # 운영에 ldb_<code> 본문 DB 가 아직 없는데 노출(enabled)될 코드 → 렌더 안 될 수 있음
    d["missing_db"] = sorted(r["code"] for r in dev_rows
                             if r["enabled"] and r["code"] not in prod_codes)
    d["dev_count"] = len(dev_rows)
    d["prod_count"] = len(prod_rows)
    d["unchanged"] = not (d["added"] or d["removed"] or d["changed"])
    return d


def replicate_preview() -> dict:
    """개발→운영 복제 시 적용될 변경 미리보기(쓰기 없음)."""
    dev_rows = _dev_rows()
    conn, tunnel = _open("prod")
    try:
        registry_db._ensure(conn)
        conn.commit()
        prod_rows = registry_db._list(conn)
        prod_codes = set(dbstate._law_codes(conn))
    finally:
        conn.close()
        if tunnel:
            tunnel.stop()
    return _summary(dev_rows, prod_rows, prod_codes)


def replicate_to_prod() -> dict:
    """운영 law_registry 를 개발과 **완전히 동일**하게 만든다(전체 교체, 단일 트랜잭션)."""
    dev_rows = _dev_rows()
    conn, tunnel = _open("prod")
    try:
        registry_db._ensure(conn)
        conn.commit()
        prod_rows = registry_db._list(conn)          # 적용 전 상태(요약용)
        prod_codes = set(dbstate._law_codes(conn))
        with conn.cursor() as cur:
            cur.execute("DELETE FROM law_registry")
        for r in dev_rows:
            registry_db._upsert(conn, r["code"], r.get("label"), r["sort_order"],
                                r["enabled"], r.get("kind") or "law")
        conn.commit()
        s = _summary(dev_rows, prod_rows, prod_codes)
        s["copied"] = len(dev_rows)
        return s
    finally:
        conn.close()
        if tunnel:
            tunnel.stop()
