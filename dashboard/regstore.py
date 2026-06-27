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
