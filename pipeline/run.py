"""run: 한 job(jobs/<code>/job.json) 의 전체 파이프라인 오케스트레이션.

  python -m pipeline.run g                  # build → qa → rdb (적재 안 함)
  python -m pipeline.run g --apply          # + ldb_g 적재(dev, recreate)
  python -m pipeline.run g --apply --prod   # 운영 적재
  python -m pipeline.run g --apply --force  # 이미 존재해도 강제 재적재

build/qa/rdb 는 결정론. ⚠ --apply 는 DROP+재적재라 GUI 수동편집을 전부 덮어쓴다.
그래서 ldb_<code> 가 이미 있으면 기본 거부 → 의도적 갱신만 --force. (운영 이관은 common.replicate)
"""
import sys

from pipeline import read_artifact
from pipeline.build import build
from pipeline.qa import check
from pipeline.rdb import build_rdb
from pipeline.annex import build_annex
from pipeline.ref import build_ref
from pipeline.penalty import build_penalty


def _db_exists(code: str, target: str) -> bool:
    from common.db import get_connection
    conn = get_connection(target=target)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s",
                (f"ldb_{code}",),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def run(code: str, apply: bool = False, target: str = "dev", force: bool = False):
    # ── 안전장치: 이미 존재하는 DB 를 --apply 로 덮어쓰면 GUI 수동편집(rdb 보정 등)이 사라짐 ──
    if apply and not force and _db_exists(code, target):
        print(f"⛔ ldb_{code} 가 이미 {target} 에 존재합니다 — 재적재 중단(수동편집 보호).")
        print("   --apply 는 DROP+재적재라 GUI 수정(rdb 보정·항/호 미세조정)이 전부 사라집니다.")
        print(f"   • 규정 갱신 등 의도적 재생성:  python -m pipeline.run {code} --apply --force")
        print(f"   • 운영 이관/복제(현재 DB asis): python -m common.replicate {code}")
        return
    print(f"=== [{code}] build ===");    build(code)
    print(f"=== [{code}] qa ===")
    if not check(code):
        print("QA 실패 — 적재 중단"); return
    print(f"=== [{code}] rdb ===");      build_rdb(code)
    print(f"=== [{code}] annex ===");    build_annex(code)
    print(f"=== [{code}] ref ===");      build_ref(code)
    print(f"=== [{code}] penalty ===");  build_penalty(code)
    if not apply:
        print("\n(검토용 dry-run 완료. 적재하려면 --apply)")
        return

    from loader.loader import load
    from pipeline.overrides import load_overrides, apply_rdb_overrides
    data = read_artifact(code, "data.json")
    # rdb = 자동(rdb.json) + 사람 오버라이드(overrides.json). 안정 ID라 갱신 후에도 재적용.
    valid = {row[f"id_{t}"] for t in ("a", "e", "s", "r")
             for row in data[t] if row.get(f"id_{t}")}
    final_rdb = apply_rdb_overrides(read_artifact(code, "rdb.json")["edges"],
                                    load_overrides(code), valid)
    data["rdb"] = [{"id": None, **e} for e in final_rdb]
    data["annex"] = read_artifact(code, "annex.json")
    data["ref"] = read_artifact(code, "ref.json")
    pen = read_artifact(code, "penalty.json")
    data["penalty"], data["penalty_a"], data["penalty_e"] = (
        pen["penalty"], pen["penalty_a"], pen.get("penalty_e", []))
    print(f"=== [{code}] load → ldb_{code} @ {target} ===")
    dbname, counts = load(code, data, target=target, recreate=True)
    print(f"적재 완료: {dbname}")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    code = next((a for a in args if not a.startswith("-")), "g")
    run(code, apply="--apply" in args, target="prod" if "--prod" in args else "dev",
        force="--force" in args)
