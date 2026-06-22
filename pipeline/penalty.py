"""penalty: 벌칙·과태료·과징금 조 → 형량 + '위반 대상 조' 재분류.

핵심: "제N조[의M]…을/를 위반하여" → 처벌 대상(위반) 조(id_a) 추출.
      형량/금액: "N년 이하의 징역", "N원 이하의 벌금|과태료|과징금" 패턴.
산출:
  db_penalty   : 벌칙 조 → 형량 요약(penalty_a_phy, penalty_a_log)
  db_penalty_a : 위반조별 상세(category, item_a_*, content_pa, id_a=위반조)
과태료 금액이 시행령 별표(표)로 정의되는 경우(전자금융 등)는 별도 검토 — 본 모듈은 본문형.
"""
import re
import sys

from pipeline import load_job, read_artifact, write_artifact

UP = {"a": "A", "e": "E"}
_KIND = re.compile(r"(벌칙|과태료|과징금)")
_VIOL = re.compile(r"제(\d+)조(?:의(\d+))?(?:제\d+항)?(?:제\d+호)?(?:을|를)\s*위반")
_AMOUNT = re.compile(r"\d+년\s*이하의\s*징역|[\d천만억,]+\s*원\s*이하의\s*(?:벌금|과태료|과징금)")
_JO = re.compile(r"제\d+조(?:의\d+)?")


def build_penalty(code: str) -> dict:
    job = load_job(code)
    data = read_artifact(code, "data.json")
    nodes_a = {r["id_a"] for r in data["a"]}
    penalty, penalty_a = [], []

    for tier in ("a", "e"):
        if tier not in data:
            continue
        for row in data[tier]:
            nid = row.get(f"id_{tier}")
            body = row.get(f"content_{tier}") or ""
            title = row.get("title_a") if tier == "a" else ""
            k = _KIND.search(title or body[:30])
            if not k:
                continue
            amounts = _AMOUNT.findall(body)
            log = " 또는 ".join(dict.fromkeys(amounts)) or None
            viols = []
            for m in _VIOL.finditer(body):
                vid = f"A{int(m.group(1))}" + (f"_{int(m.group(2))}" if m.group(2) else "")
                if vid in nodes_a and vid not in viols:
                    viols.append(vid)
            if not amounts and not viols:
                continue  # 제목만 '벌칙'(공무원 의제 등) — 실제 처벌규정 아님
            jo = _JO.search(body)
            item_log = ("법 " + jo.group(0)) if jo else None
            penalty.append({"id": None, "penalty_a_phy": nid, "penalty_a_log": log})
            for vid in viols:
                penalty_a.append({"id": None, "category": k.group(1), "item_a_phy": nid,
                                  "item_a_log": item_log, "content_pa": body[:200],
                                  "penalty_a_phy": nid, "id_a": vid})
            print(f"  {nid}({k.group(1)}): 형량={log} / 위반조={viols}")

    write_artifact(code, "penalty.json", {"penalty": penalty, "penalty_a": penalty_a, "penalty_e": []})
    print(f"저장: jobs/{code}/penalty.json  db_penalty {len(penalty)}, db_penalty_a {len(penalty_a)}")
    return {"penalty": penalty, "penalty_a": penalty_a}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build_penalty(sys.argv[1] if len(sys.argv) > 1 else "g")
