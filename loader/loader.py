"""
적재기. CREATE DATABASE ldb_<코드> → DDL → 시트별 TRUNCATE + INSERT (트랜잭션).

idempotent: 매 실행마다 TRUNCATE 후 재적재(전체 리로드).
--recreate 면 DB 자체를 DROP 후 재생성(스키마까지 깨끗).
"""
from pathlib import Path

from common.db import get_connection
from common.schema_map import SHEETS, LOAD_ORDER, AUTO_ID_SHEETS

DDL_PATH = Path(__file__).resolve().parent.parent / "schema" / "ddl.sql"


def _statements(sql_text: str):
    return [s.strip() for s in sql_text.split(";") if s.strip()]


def load(law_code: str, data: dict, target: str = "dev", recreate: bool = False):
    dbname = f"ldb_{law_code}"

    # 1) 서버 레벨: DB 생성
    server = get_connection(target=target)
    try:
        with server.cursor() as cur:
            if recreate:
                cur.execute(f"DROP DATABASE IF EXISTS `{dbname}`")
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{dbname}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_uca1400_ai_ci"
            )
        server.commit()
    finally:
        server.close()

    # 2) DB 레벨: DDL + 적재 (한 트랜잭션)
    conn = get_connection(database=dbname, target=target)
    counts: dict[str, int] = {}
    try:
        with conn.cursor() as cur:
            for stmt in _statements(DDL_PATH.read_text(encoding="utf-8")):
                cur.execute(stmt)

            for sheet in LOAD_ORDER:
                if sheet not in data:
                    continue
                table, cols = SHEETS[sheet]
                rows = data[sheet]
                cur.execute(f"TRUNCATE TABLE `{table}`")
                if not rows:
                    counts[sheet] = 0
                    continue

                # id 가 단순 순번인 테이블: 비어있으면 1..N 자동부여
                if sheet in AUTO_ID_SHEETS and "id" in cols:
                    for i, row in enumerate(rows, 1):
                        if row.get("id") in (None, ""):
                            row["id"] = i

                collist = ", ".join(f"`{c}`" for c in cols)
                placeholders = ", ".join(["%s"] * len(cols))
                sql = f"INSERT INTO `{table}` ({collist}) VALUES ({placeholders})"
                values = [tuple(row.get(c) for c in cols) for row in rows]
                cur.executemany(sql, values)
                counts[sheet] = len(values)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return dbname, counts
