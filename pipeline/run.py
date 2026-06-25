"""run: 한 job(jobs/<code>/job.json) 의 파이프라인 오케스트레이션(전체/부분).

  python -m pipeline.run g                       # 전체 dry-run (적재 안 함)
  python -m pipeline.run g --apply               # 전체 적재(dev, DROP+재적재)
  python -m pipeline.run g --apply --force        # 이미 존재해도 강제 전체 재적재
  python -m pipeline.run g --only=annex --apply   # 부분: annex 만 재생성·db_annex 만 갱신
  python -m pipeline.run g --only=annex,ref --apply
  python -m pipeline.run g --apply --prod         # 운영 적재

단계: build·rdb·annex·ref·penalty (qa는 build와 함께).
- 전체(--apply): DROP+재적재 → GUI 수동편집 덮어씀 → 이미 있으면 거부, --force 만 허용.
- 부분(--only): 선택 단계만 재생성 + 그 테이블만 TRUNCATE+INSERT(recreate 안 함) → rdb 큐레이션 등
  다른 테이블 안 건드림 → 안전(가드 불필요). data.json(노드) 베이스가 먼저 있어야 함.
운영 이관은 복제(common.replicate). rdb 적재 시 overrides.json 자동 재적용.
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


ALL_STAGES = ["build", "rdb", "annex", "ref", "penalty"]
STAGE_SHEETS = {                                  # 각 단계가 적재하는 테이블(부분 적재용)
    "build":   ["meta", "a", "e", "s", "r"],
    "rdb":     ["rdb"],
    "annex":   ["annex"],
    "ref":     ["ref"],
    "penalty": ["penalty", "penalty_a", "penalty_e"],
}


def _load_data_for(code: str, stages: list) -> dict:
    """선택 단계의 산출물 → 적재용 data dict. typed 오버라이드(splits 재분리 + 델타) 적용."""
    from pipeline.overrides import build_load_data
    sheets = [s for stage in stages for s in STAGE_SHEETS[stage]]
    return build_load_data(code, sheets)


def run(code: str, apply: bool = False, target: str = "dev",
        force: bool = False, only: list | None = None):
    from pipeline import job_dir
    full = not only
    stages = ALL_STAGES if full else only
    bad = [s for s in stages if s not in ALL_STAGES]
    if bad:
        print(f"알 수 없는 단계 {bad} — 가능: {ALL_STAGES}"); return
    if not full and "build" not in stages and not (job_dir(code) / "data.json").exists():
        print("data.json(노드 베이스) 없음 — 부분 실행 전에 전체 run 으로 먼저 만드세요."); return

    # 가드: 전체 --apply 만(부분은 해당 테이블만 갱신이라 안전 — 가드 불필요)
    if full and apply and not force and _db_exists(code, target):
        print(f"⛔ ldb_{code} 가 이미 {target} 에 존재 — 전체 재적재 중단(수동편집 보호).")
        print(f"   • 규정 갱신(전체):  python -m pipeline.run {code} --apply --force")
        print(f"   • 일부만 갱신(안전): python -m pipeline.run {code} --only=annex --apply")
        print(f"   • 운영 이관:        python -m common.replicate {code}")
        return

    # ── 단계 실행 ──
    if "build" in stages:
        print(f"=== [{code}] build ===");    build(code)
        print(f"=== [{code}] qa ===")
        if not check(code):
            print("QA 실패 — 중단"); return
    if "rdb" in stages:     print(f"=== [{code}] rdb ===");     build_rdb(code)
    if "annex" in stages:   print(f"=== [{code}] annex ===");   build_annex(code)
    if "ref" in stages:     print(f"=== [{code}] ref ===");     build_ref(code)
    if "penalty" in stages: print(f"=== [{code}] penalty ==="); build_penalty(code)

    if not apply:
        print(f"\n(dry-run 완료 — 단계 {stages}. 적재하려면 --apply)")
        return

    from loader.loader import load
    load_data = _load_data_for(code, stages)
    scope = "전체(DROP+재적재)" if full else f"부분 {stages}(해당 테이블만 TRUNCATE+INSERT)"
    print(f"=== [{code}] load → ldb_{code} @ {target} [{scope}] ===")
    dbname, counts = load(code, load_data, target=target, recreate=full)
    print(f"적재 완료: {dbname}")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    only = None
    for a in args:
        if a.startswith("--only="):
            only = [s.strip() for s in a[len("--only="):].split(",") if s.strip()]
    code = next((a for a in args if not a.startswith("-")), "g")
    run(code, apply="--apply" in args, target="prod" if "--prod" in args else "dev",
        force="--force" in args, only=only)
