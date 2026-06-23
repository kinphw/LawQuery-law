"""수동 큐레이션 오버라이드 — 자동생성 rdb 위에 사람의 add/remove 델타를 재적용.

개념(= Kustomize base+overlay / git rebase):
  rdb.json(순수 자동) = 결정론 베이스.  overrides.json = 사람 델타(add/remove).
  적재    = apply(자동, 오버라이드).      → 규정 갱신(--force) 후에도 큐레이션 영속.
  capture = 라이브 DB rdb ⊖ rdb.json.    → GUI/Workbench 편집을 코드(델타)로 박제.

안정 ID(A37/S17…) 덕에 델타가 재생성을 건너뛰어 유효. add 대상 노드가 갱신으로 사라지면
스킵+경고(= git rebase 충돌). overrides.json 은 git 추적(큐레이션 = 소스).
"""
import json
import sys

from pipeline import job_dir, read_artifact, write_artifact


def load_overrides(code: str) -> dict:
    p = job_dir(code) / "overrides.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"rdb": {"add": [], "remove": []}}


def apply_rdb_overrides(auto_edges: list[dict], overrides: dict,
                        valid_nodes: set, log=print) -> list[dict]:
    """자동 엣지에 오버라이드 적용 → 최종 엣지. (remove 빼고 add 더함, 노드검증)"""
    edges = {(e["id_start"], e["id_end"]) for e in auto_edges}
    o = overrides.get("rdb", {})
    rem = {tuple(x) for x in o.get("remove", [])}
    add = {tuple(x) for x in o.get("add", [])}
    n_rem = len(edges & rem)
    edges -= rem
    skipped, n_add = [], 0
    for s, e in add:
        if s in valid_nodes and e in valid_nodes:
            if (s, e) not in edges:
                edges.add((s, e)); n_add += 1
        else:
            skipped.append([s, e])
    if rem or add:
        msg = f"[overrides] 적용: remove {n_rem}, add {n_add}"
        if skipped:
            msg += f", ⚠스킵(노드부재) {len(skipped)} {skipped[:5]}"
        log(msg)
    return [{"id_start": s, "id_end": e} for s, e in sorted(edges)]


def capture(code: str, target: str = "dev", log=print) -> dict:
    """라이브 ldb_<code>.rdb ⊖ 자동(rdb.json) → overrides.json 기록(델타 박제)."""
    from common.db import get_connection
    auto = read_artifact(code, "rdb.json")["edges"]
    auto_set = {(e["id_start"], e["id_end"]) for e in auto}
    conn = get_connection(f"ldb_{code}", target=target)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_start, id_end FROM rdb")
            live = {(s, e) for s, e in cur.fetchall()}
    finally:
        conn.close()
    add = sorted(live - auto_set)
    remove = sorted(auto_set - live)
    ov = {"rdb": {"add": [list(x) for x in add], "remove": [list(x) for x in remove]}}
    write_artifact(code, "overrides.json", ov)
    log(f"[capture] overrides.json — add {len(add)}, remove {len(remove)} (라이브 ⊖ 자동)")
    return ov


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    capture(sys.argv[1] if len(sys.argv) > 1 else "g")
