"""qa: 적재 전 검증. 행정규칙(admrul) 원문의 조 헤더 ↔ data.json 노드 일치 확인.

splitter 가 조(가지조문·삭제조 포함)를 빠짐없이 잡았는지 원문과 대조한다.
법(law)단은 구조화 API가 권위 — 개수만 보고.
"""
import re
import sys

from fetcher import law_api
from lawparse import splitter
from pipeline import load_job, read_artifact

_HDR = re.compile(r"(?:^|\n)제(\d+)조(?:의(\d+))?\s*(?:\(|삭\s*제)")


def check(code: str) -> bool:
    job = load_job(code)
    data = read_artifact(code, "data.json")
    ok = True
    for tier, src in job["sources"].items():
        have = {r[f"id_{tier}"] for r in data[tier]}
        if src["kind"] == "law":
            print(f"  {tier}(law): {len(have)}조 (구조화 API)")
            continue
        body = splitter._norm(law_api.get_admin_rule_text(src["id"])["조문내용"])
        want = {f"{tier.upper()}{int(jo)}" + (f"_{int(ga)}" if ga else "")
                for jo, ga in _HDR.findall("\n" + body)}
        miss, extra = want - have, have - want
        status = "OK" if not miss and not extra else "❌"
        if miss or extra:
            ok = False
        print(f"  {tier}(admrul): 원문 {len(want)} / 데이터 {len(have)} {status}"
              + (f"  누락={sorted(miss)}" if miss else "")
              + (f"  과잉={sorted(extra)}" if extra else ""))
    print("QA " + ("통과" if ok else "실패"))
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if check(sys.argv[1] if len(sys.argv) > 1 else "g") else 1)
