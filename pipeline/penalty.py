"""penalty: 벌칙·과태료·과징금 → 형량 / 위반조 / 별표 부과기준.

  db_penalty   : 처벌 조의 **항별 형량**(penalty_a_phy=항노드 A49_1h, penalty_a_log=형량 요약)
  db_penalty_a : 처벌 조의 **호별 위반조**(category, item_a_log=위치 '법 제51조제1항제1호',
                 penalty_a_phy=항, id_a=위반조)
  db_penalty_e : 시행령 **'과태료의 부과기준' 별표** 표 파싱(위반행위·근거법조·금액)

법본문은 항/호로 분리(article_split)해 항=형량·호=위반조. 별표는 lawparse.penalty_table.
'벌칙'만 있고 형량/위반조/별표 없으면(공무원 의제 등) 제외.
"""
import re
import sys

from pipeline import load_job, read_artifact, write_artifact
from fetcher import law_api
from lawparse.article_split import split_article
from lawparse.penalty_table import parse_penalty_annex

_KIND = re.compile(r"(벌칙|과태료|과징금)")
_AMOUNT = re.compile(r"\d+년\s*이하의\s*징역|[\d천백만억,]+\s*원\s*이하의\s*(?:벌금|과태료|과징금)")
_VIOL = re.compile(r"(?<!」\s)(?<!」)제(\d+)조(?:의(\d+))?")   # 가족 조 인용(「외부법」 직후 제외)
_HANG = re.compile(r"_(\d+)h$")
_HO = re.compile(r"_(\d+)h_(\d+)(?:_\d+)?ho$")                # 호(가지호 _6_2ho 포함)


def _fetch_law(src: dict) -> dict:
    if src.get("mst") and src.get("ef_yd"):
        return law_api.get_law_text(mst=src["mst"], ef_yd=src["ef_yd"])
    return law_api.get_law_text(src["id"])


def _jo_label(nid: str) -> str:
    m = re.match(r"A(\d+)(?:_(\d+))?$", nid)
    return f"제{m.group(1)}조" + (f"의{m.group(2)}" if m.group(2) else "")


def build_penalty(code: str) -> dict:
    job = load_job(code)
    data = read_artifact(code, "data.json")
    nodes_a = {r["id_a"] for r in data["a"] if r.get("id_a")}
    penalty, penalty_a = [], []

    # ── 법 본문: 벌칙/과태료/과징금 조 → 항=형량, 호=위반조 ──
    for row in data["a"]:
        nid = row.get("id_a")
        title = row.get("title_a") or ""
        body = row.get("content_a") or ""
        k = _KIND.search(title)
        if not k or not nid:
            continue
        cat = k.group(1)
        jo_lbl = _jo_label(nid)
        _, children = split_article(nid, body, "hangho")     # 항+호 노드(평탄)
        had = False
        for cid, txt in children:
            mho = _HO.search(cid)
            if not mho and _HANG.search(cid):                # 항 노드 → 형량
                amts = list(dict.fromkeys(_AMOUNT.findall(txt)))
                if amts:
                    penalty.append({"id": None, "penalty_a_phy": cid,
                                    "penalty_a_log": " 또는 ".join(amts)})
                    had = True
            elif mho:                                        # 호 노드 → 위반조(다조 가능)
                if "삭제" in txt[:12]:                        # 삭제 호 제외
                    continue
                clean = re.sub(r"\([^)]*\)", "", txt)        # 준용 등 괄호 제거(과매칭 방지)
                hang = f"{nid}_{mho.group(1)}h"
                pos = f"법 {jo_lbl}제{mho.group(1)}항제{mho.group(2)}호"
                seen_v = set()
                for v in _VIOL.finditer(clean):
                    vid = f"A{int(v.group(1))}" + (f"_{int(v.group(2))}" if v.group(2) else "")
                    if vid in nodes_a and vid not in seen_v:
                        seen_v.add(vid)
                        penalty_a.append({"id": None, "category": cat, "item_a_phy": hang,
                                          "item_a_log": pos, "content_pa": txt[:200],
                                          "penalty_a_phy": hang, "id_a": vid})
                        had = True
        if had:
            print(f"  {nid}({cat}): 항 형량 + 호 위반조 추출")

    # ── 시행령(등) 별표: '과태료의 부과기준' → penalty_e ──
    penalty_e = []
    for tier in ("e", "a", "s", "r"):
        src = job["sources"].get(tier)
        if not src or src.get("kind") != "law":
            continue
        try:
            t = _fetch_law(src)
        except Exception as ex:
            print(f"  [{tier}] 별표 조회 실패: {ex}")
            continue
        for b in t.get("별표목록", []):
            tt = b.get("별표제목") or ""
            if "과태료" in tt and "부과기준" in tt:
                got = parse_penalty_annex(law_api._flat(b.get("별표내용")))
                penalty_e.extend(got)
                print(f"  [{tier}] 별표 '{tt[:30]}' → 과태료 {len(got)}행")

    write_artifact(code, "penalty.json",
                   {"penalty": penalty, "penalty_a": penalty_a, "penalty_e": penalty_e})
    print(f"저장: jobs/{code}/penalty.json  db_penalty {len(penalty)}, "
          f"db_penalty_a {len(penalty_a)}, db_penalty_e {len(penalty_e)}")
    return {"penalty": penalty, "penalty_a": penalty_a, "penalty_e": penalty_e}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build_penalty(sys.argv[1] if len(sys.argv) > 1 else "g")
