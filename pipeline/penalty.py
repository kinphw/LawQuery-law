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
from lawparse.penalty_table import parse_penalty_annex, parse_suspension_annex, refs_in
from lawparse.ids import resolve_node

_KIND = re.compile(r"(벌칙|과태료|과징금)")
_AMOUNT = re.compile(r"\d+년\s*이하의\s*징역|[\d천백만억,]+\s*원\s*이하의\s*(?:벌금|과태료|과징금)")
_VIOL = re.compile(r"(?<!」\s)(?<!」)제(\d+)조(?:의(\d+))?(?:제(\d+)항)?(?:제(\d+)호)?")  # 위반조(「외부법」직후 제외)
_HANG = re.compile(r"_(\d+)h$")
_HO = re.compile(r"_(\d+)h_(\d+)(?:_\d+)?ho$")                # 호(가지호 _6_2ho 포함)


def _fetch_law(src: dict) -> dict:
    if src.get("mst") and src.get("ef_yd"):
        return law_api.get_law_text(mst=src["mst"], ef_yd=src["ef_yd"])
    return law_api.get_law_text(src["id"])


def _jo_label(nid: str) -> str:
    m = re.match(r"A(\d+)(?:_(\d+))?$", nid)
    return f"제{m.group(1)}조" + (f"의{m.group(2)}" if m.group(2) else "")


def _viols(txt: str, nodes_a: set) -> list[str]:
    """본문에서 가족 위반조 → **최세밀 존재 노드**(항/호). 준용 등 괄호 제거 후, 중복 없이."""
    clean = re.sub(r"\([^)]*\)", "", txt)
    out, seen = [], set()
    for v in _VIOL.finditer(clean):
        g = tuple(int(x) if x else None for x in v.groups())
        vid = resolve_node("a", *g, nodes_a)                 # 제25조의2제1항 → A25_2_1h(있으면)
        if vid and vid not in seen:
            seen.add(vid)
            out.append(vid)
    return out


def build_penalty(code: str) -> dict:
    job = load_job(code)
    data = read_artifact(code, "data.json")
    from pipeline.overrides import split_tiers
    nodes_a = {r["id_a"] for r in split_tiers(code)["a"] if r.get("id_a")}  # 분할 후 노드(항/호 위반조)
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
        hangs_with_ho = {f"{nid}_{m.group(1)}h" for cid, _ in children if (m := _HO.search(cid))}
        had = False
        for cid, txt in children:
            mho = _HO.search(cid)
            mh = _HANG.search(cid)
            if mh and not mho:                               # 항 노드
                amts = list(dict.fromkeys(_AMOUNT.findall(txt)))
                if amts:                                     # → 형량
                    penalty.append({"id": None, "penalty_a_phy": cid,
                                    "penalty_a_log": " 또는 ".join(amts)})
                    had = True
                if cid not in hangs_with_ho:                 # 호 없는 항(제46조 과징금 등) → 항에서 위반조
                    pos = f"법 {jo_lbl}제{mh.group(1)}항"
                    for vid in _viols(txt, nodes_a):
                        penalty_a.append({"id": None, "category": cat, "item_a_phy": cid,
                                          "item_a_log": pos, "content_pa": txt[:200],
                                          "penalty_a_phy": cid, "id_a": vid})
                        had = True
            elif mho:                                        # 호 노드 → 위반조(다조 가능)
                if "삭제" in txt[:12]:
                    continue
                hang = f"{nid}_{mho.group(1)}h"
                pos = f"법 {jo_lbl}제{mho.group(1)}항제{mho.group(2)}호"
                for vid in _viols(txt, nodes_a):
                    penalty_a.append({"id": None, "category": cat, "item_a_phy": cid,  # 정밀 호=별표 조인키
                                      "item_a_log": pos, "content_pa": txt[:200],
                                      "penalty_a_phy": hang, "id_a": vid})  # 항=형량 조인키
                    had = True
        if had:
            print(f"  {nid}({cat}): 항 형량 + 항/호 위반조 추출")

    # ── 시행령(등) 별표: 과태료 부과기준(3열) / 업무정지+갈음과징금(4열) ──
    penalty_e = []
    penalty_nodes = {p["penalty_a_phy"] for p in penalty}   # 형량 노드(과징금 A46_2h 등)
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
            flat = law_api._flat(b.get("별표내용"))
            if "과태료" in tt and "부과기준" in tt:           # 과태료(3열)
                got = parse_penalty_annex(flat)
                penalty_e.extend(got)
                print(f"  [{tier}] 별표 '{tt[:22]}' → 과태료 {len(got)}행")
            elif "업무정지" in tt and "과징금" in tt:          # 업무정지+갈음과징금(4열)
                n = 0
                for idx, (viol, ref, susp, gj) in enumerate(parse_suspension_annex(flat)):
                    vids = _viols(viol, nodes_a)               # 위반조(위반행위 본문)
                    phy = next((r for r in refs_in(ref) if r in penalty_nodes), None)  # 갈음과징금 형량 노드
                    if not vids or not phy:
                        continue
                    key = f"{phy}_susp{idx}"                    # 합성 조인키(유일)
                    amt = f"업무정지 {susp}" + (f" · 갈음과징금 {gj}" if gj and gj != "-" else "")
                    penalty_a.append({"id": None, "category": "과징금", "item_a_phy": key,
                                      "item_a_log": ref, "content_pa": viol[:200],
                                      "penalty_a_phy": phy, "id_a": vids[0]})
                    penalty_e.append({"content_pe": viol, "item_a_log": ref,
                                      "penalty_e_log": amt, "item_a_phy": key})
                    n += 1
                print(f"  [{tier}] 별표 '{tt[:22]}' → 업무정지/과징금 {n}행")

    write_artifact(code, "penalty.json",
                   {"penalty": penalty, "penalty_a": penalty_a, "penalty_e": penalty_e})
    print(f"저장: jobs/{code}/penalty.json  db_penalty {len(penalty)}, "
          f"db_penalty_a {len(penalty_a)}, db_penalty_e {len(penalty_e)}")
    return {"penalty": penalty, "penalty_a": penalty_a, "penalty_e": penalty_e}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build_penalty(sys.argv[1] if len(sys.argv) > 1 else "g")
