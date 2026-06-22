"""verify: 적재된 ldb_<code> 의 rdb 연결성 점검.

  - dangling: rdb 엣지의 양끝이 실제 노드인가
  - 연결성: 법(A) 루트에서 rdb 를 타고 내려가 모든 조에 도달하는가(=고아 없음)
  - 삭제조는 엣지 없음이 정상 → 별도 분류
"""
import sys
from collections import defaultdict

from common.db import get_connection
from pipeline import read_artifact


def verify(code: str, target: str = "dev"):
    conn = get_connection(f"ldb_{code}", target=target)
    cur = conn.cursor()
    nodes = {}
    for t in ("a", "e", "s", "r"):
        cur.execute(f"SELECT id_{t} FROM db_{t} WHERE id_{t} IS NOT NULL")
        nodes[t] = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT id_start, id_end FROM rdb")
    edges = cur.fetchall()
    conn.close()
    alln = set().union(*nodes.values())

    dangling = [(s, e) for s, e in edges if s not in alln or e not in alln]

    adj = defaultdict(list)
    for s, e in edges:
        adj[s].append(e)
    seen, stack = set(nodes["a"]), list(nodes["a"])
    while stack:
        for c in adj[stack.pop()]:
            if c not in seen:
                seen.add(c); stack.append(c)

    deleted = set(read_artifact(code, "rdb.json").get("deleted", []))
    print(f"노드 {len(alln)} (a{len(nodes['a'])}/e{len(nodes['e'])}/s{len(nodes['s'])}/r{len(nodes['r'])}), "
          f"엣지 {len(edges)}, dangling {len(dangling)}")
    for s, e in dangling[:10]:
        print(f"   ⚠ dangling {s}→{e}")
    bad = 0
    for t in ("e", "s", "r"):
        unreached = nodes[t] - seen - deleted
        if unreached:
            bad += len(unreached)
            print(f"   ❌ {t} 미연결(삭제조 제외) {len(unreached)}: {sorted(unreached)[:12]}")
    print("연결성 " + ("OK — 모든 유효조가 법 루트까지 연결됨" if not bad and not dangling else "문제 있음"))

    bad += _addons(code, alln, nodes["a"], target)
    return not bad and not dangling


def _addons(code: str, alln: set, a_nodes: set, target: str) -> int:
    """부가테이블(annex/ref/penalty) 참조 무결성 — 가리키는 노드가 실제 존재하는가."""
    conn = get_connection(f"ldb_{code}", target=target)
    cur = conn.cursor()
    checks = [
        ("db_annex", "id_src", "SELECT id_src FROM db_annex WHERE id_src IS NOT NULL", alln),
        ("db_ref", "ref_target", "SELECT ref_target FROM db_ref WHERE ref_type LIKE 'db\\_%' ESCAPE '\\\\'", alln),
        ("db_penalty_a", "id_a", "SELECT id_a FROM db_penalty_a WHERE id_a IS NOT NULL", a_nodes),
    ]
    bad = 0
    for table, col, sql, valid in checks:
        try:
            cur.execute(sql)
            miss = [r[0] for r in cur.fetchall() if r[0] not in valid]
        except Exception:
            continue
        bad += len(miss)
        print(f"   {table}.{col} dangling {len(miss)}" + (f" {miss[:8]}" if miss else " ✓"))
    conn.close()
    return bad


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    verify(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "g")
