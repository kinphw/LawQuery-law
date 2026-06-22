"""run: 한 job(jobs/<code>/job.json) 의 전체 파이프라인 오케스트레이션.

  python -m pipeline.run g                  # build → qa → rdb (적재 안 함)
  python -m pipeline.run g --apply          # + ldb_g 적재(dev, recreate)
  python -m pipeline.run g --apply --prod   # 운영 적재

build/qa/rdb 는 결정론(재실행 안전). 적재는 TRUNCATE 후 재적재(idempotent).
"""
import sys

from pipeline import read_artifact
from pipeline.build import build
from pipeline.qa import check
from pipeline.rdb import build_rdb
from pipeline.annex import build_annex
from pipeline.ref import build_ref
from pipeline.penalty import build_penalty


def run(code: str, apply: bool = False, target: str = "dev"):
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
    data = read_artifact(code, "data.json")
    data["rdb"] = [{"id": None, **e} for e in read_artifact(code, "rdb.json")["edges"]]
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
    run(code, apply="--apply" in args, target="prod" if "--prod" in args else "dev")
