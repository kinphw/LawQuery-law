"""qa: 적재 전 검증. 행정규칙(admrul) 원문의 조 헤더 ↔ data.json 노드 일치 확인.

splitter 가 조(가지조문·삭제조 포함)를 빠짐없이 잡았는지 원문과 대조한다.
법(law)단은 구조화 API가 권위 — 개수만 보고.
"""
import re
import sys

from fetcher import law_api
from lawparse import splitter
from pipeline import load_job, read_artifact, tier_units

_HDR = re.compile(r"(?:^|\n)제(\d+)(?:-(\d+))?조(?:의(\d+))?\s*(?:\(|삭\s*제)")  # g1=조(편-조면 편) g2=편-조의 조 g3=가지


def _is_tracked(i: str) -> bool:
    return bool(i) and i[0] in "RB" and len(i) > 1 and i[1].islower()


def check(code: str) -> bool:
    job = load_job(code)
    data = read_artifact(code, "data.json")
    ok = True
    for unit in tier_units(job):
        tier, track, src = unit["tier"], unit["track"], unit["src"]
        pre = f"{tier.upper()}{track}." if track else None
        belongs = (lambda i: bool(i) and i.startswith(pre)) if pre else (lambda i: bool(i) and not _is_tracked(i))
        have = {r[f"id_{tier}"] for r in data.get(tier, []) if belongs(r.get(f"id_{tier}"))}  # title행(id None) 제외
        tx = f"[{track}]" if track else ""
        if src["kind"] == "law":
            print(f"  {tier}{tx}(law): {len(have)}조 (구조화 API)")
            continue
        body = splitter.segment_admin_body(splitter._norm(law_api.get_admin_rule_text(src["id"])["조문내용"]))
        ns = f"{track}." if track else ""
        want = {f"{tier.upper()}{ns}" + (f"{jo}-{pn}" if pn else jo) + (f"_{int(ga)}" if ga else "")
                for jo, pn, ga in _HDR.findall("\n" + body)}
        miss, extra = want - have, have - want
        status = "OK" if not miss and not extra else "❌"
        if miss or extra:
            ok = False
        print(f"  {tier}{tx}(admrul): 원문 {len(want)} / 데이터 {len(have)} {status}"
              + (f"  누락={sorted(miss)}" if miss else "")
              + (f"  과잉={sorted(extra)}" if extra else ""))
    print("QA " + ("통과" if ok else "실패"))
    return ok


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if check(sys.argv[1] if len(sys.argv) > 1 else "g") else 1)
