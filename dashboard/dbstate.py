"""dev/prod 법령 DB 현황 — 단별 법령명·시행일자를 읽어 운영 지체를 비교한다.

db_meta.full_name = "법령명\\n[시행 YYYYMMDD]" 에서 법령명/시행일을 추출.
origin(a/e/s/r/b)은 고정 의미가 아니라 계층 슬롯이므로 라벨은 short_name 을 쓴다.
운영(prod)은 localhost 바인딩이라 replicate 의 SSH 터널을 재사용해 접속한다.
"""
import re

import pymysql

from common import db as _db
from common import replicate as _rep

# 법이 아닌 DB(인증·해석)는 제외
EXCLUDE = {"auth", "i"}
# 시행일 형식 2가지: dev "[시행 20251216]"(압축) / prod "[시행 2025. 2. 5.]"(점·공백·한자리)
EFF_COMPACT = re.compile(r"시행\s*(\d{4})(\d{2})(\d{2})")
EFF_SPACED = re.compile(r"시행\s*(\d{4})\D{1,4}(\d{1,2})\D{1,4}(\d{1,2})")
TIER_ORDER = {"a": 0, "e": 1, "s": 2, "r": 3, "b": 4}


def _parse(full_name: str):
    fn = full_name or ""
    name = fn.split("\n")[0].strip()
    m = EFF_COMPACT.search(fn) or EFF_SPACED.search(fn)
    eff = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None
    return name, eff


def _law_codes(conn) -> list:
    with conn.cursor() as cur:
        cur.execute(r"SHOW DATABASES LIKE 'ldb\_%'")
        dbs = [row[0] for row in cur.fetchall()]
    codes = [d[4:] for d in dbs if d.startswith("ldb_") and d[4:] and d[4:] not in EXCLUDE]
    return sorted(codes)


def _meta(conn, code: str):
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT origin, short_name, full_name FROM ldb_{code}.db_meta")
            rows = cur.fetchall()
    except Exception:
        return None
    tiers = []
    for origin, short, full in rows:
        name, eff = _parse(full)
        tiers.append({"tier": origin, "label": short or origin, "name": name, "eff": eff})
    tiers.sort(key=lambda t: TIER_ORDER.get(t["tier"], 9))
    return tiers


def _collect(conn) -> list:
    return [{"code": c, "tiers": _meta(conn, c) or []} for c in _law_codes(conn)]


def dev_state() -> dict:
    conn = _db.get_connection(target="dev")
    try:
        return {"target": "dev", "laws": _collect(conn)}
    finally:
        conn.close()


def dev_law(code: str):
    """단일 법의 dev 단별 메타([{tier,label,name(정식 법령명),eff}]). 없으면 None."""
    conn = _db.get_connection(target="dev")
    try:
        return _meta(conn, code)
    finally:
        conn.close()


def prod_state() -> dict:
    """SSH 터널(replicate 재사용)로 운영 MySQL 에 붙어 현황을 읽는다."""
    tunnel, port = _rep._open_tunnel(lambda *a, **k: None)
    try:
        conf = _db._conf("prod")
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
