"""rdb: 하위 조 본문의 상위 인용 → 엣지. 인용 없으면 엄브렐러(직전 앵커 상속).

규칙(사용자 확정):
  1) 상위법의 **특정 조를 명시 인용**한 경우만 그 조에 정밀 연결(법 이름만 통째 언급은 무인용).
  2) 무인용 조는 고아로 두지 않고, 문서순 직전 앵커(=마지막 정밀부모, 없으면 job.umbrella 시드)를 상속.
인용 별칭은 job.json sources[tier].refers (예: ["규정","「금융기관검사및제재에관한규정」"]).
상위 인용이 항까지여도 노드는 조 단위이므로 조로 매핑.
"""
import re
import sys

from pipeline import load_job, read_artifact, write_artifact
from lawparse.article_split import split_article
from lawparse.ids import resolve_node

UP = {"a": "A", "e": "E", "s": "S", "r": "R"}
_DELETED = re.compile(r"^제\d+조(?:의\d+)?\s*삭\s*제\s*<")
_HANG = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"


def _unit_at(body: str, pos: int):
    """body의 pos 위치가 속한 항/호 번호(도입부면 None). 강조 down 위치 결정용 — 같은
    인용문이 여러 항/호에 나와도 '실제 그 인용이 있는 항/호'를 위치로 정확히 집는다."""
    seg = body[:pos]
    hangs = [(seg.rfind(h), i + 1) for i, h in enumerate(_HANG) if h in seg]
    if hangs:
        return max(hangs)[1]                         # 직전(가장 뒤) 항 마커
    ms = list(re.finditer(r"(?m)^\s*(\d+)\s*\.", seg))
    return int(ms[-1].group(1)) if ms else None      # 호-직속 조: 직전 호


def _alias_re(alias: str) -> str:
    esc = re.escape(alias).replace(r"\ ", r"\s*")  # 공백 유연화
    return esc if alias[:1] == "「" else r"(?<![가-힣])" + esc


def _citation_re(refers: list[str]) -> re.Pattern:
    body = "|".join(_alias_re(a) for a in refers)
    # 조[의M] 까지로 엣지 결정 + 항/호(그룹3·4)는 강조쌍 정밀위치용
    return re.compile(rf"(?:{body})(?:\s*\([^)]*\))?\s*제(\d+)조(?:의(\d+))?(?:제(\d+)항)?(?:제(\d+)호)?")


def build_rdb(code: str) -> dict:
    job = load_job(code)
    data = read_artifact(code, "data.json")
    nodes = {t: {r[f"id_{t}"] for r in data[t]} for t in ("a", "e", "s", "r")}

    edges, inferred, deleted, multi, highlights = [], [], [], [], []
    for tier, src in job["sources"].items():
        parent = src.get("parent")
        if not parent:
            continue
        up = UP[parent]
        pat = _citation_re(src["refers"])
        up_content = {r[f"id_{parent}"]: (r.get(f"content_{parent}") or "") for r in data[parent]}
        up_split: dict = {}                          # 상위조 → 분할자식 id집합(강조 up_part 해석·캐시)
        anchor = job.get("umbrella", {}).get(tier)
        n_prec = n_inf = 0
        for row in data[tier]:
            cid = row[f"id_{tier}"]
            body = row.get(f"content_{tier}") or ""
            if _DELETED.match(body.strip()):
                deleted.append(cid)
                continue
            # 본문 등장순 상위 조 인용(존재·중복제거)
            cs, seen = [], set()
            for m in pat.finditer(body):
                nid = f"{up}{int(m.group(1))}" + (f"_{int(m.group(2))}" if m.group(2) else "")
                if nid not in nodes[parent]:
                    continue
                if nid not in seen:
                    seen.add(nid); cs.append(nid)
                # 정밀 강조쌍 — 상위 어느 항/호 ↔ 하위(자기) 어느 항/호 (항/호 인용일 때만)
                if m.group(3) or m.group(4):
                    jo = int(m.group(1)); ga = int(m.group(2)) if m.group(2) else None
                    hang = int(m.group(3)) if m.group(3) else None
                    ho = int(m.group(4)) if m.group(4) else None
                    if nid not in up_split:
                        up_split[nid] = {c for c, _ in split_article(nid, up_content.get(nid, ""), "hangho")[1]}
                    up_part = resolve_node(parent, jo, ga, hang, ho, up_split[nid])
                    if up_part and up_part != nid:       # 정밀 노드로 좁혀졌을 때만
                        # 인용이 들어있는 '실제 위치'의 항/호 — 같은 인용문이 여러 항에 나와도
                        # m.start() 위치로 정확히(도입부면 None=조 단위).
                        u = _unit_at(body, m.start())
                        down_part = f"{cid}_{u}h" if u else cid
                        highlights.append({"up": up_part, "down": down_part})
            if cs:
                edges.append({"id_start": cs[0], "id_end": cid})
                anchor = cs[0]                       # 직전 앵커 갱신
                n_prec += 1
                if len(cs) > 1:
                    multi.append({"child": cid, "primary": cs[0], "others": cs[1:]})
            elif anchor:
                edges.append({"id_start": anchor, "id_end": cid})
                inferred.append({"id_start": anchor, "id_end": cid})
                n_inf += 1
        print(f"  {tier}→{parent}: 정밀 {n_prec}, 엄브렐러 {n_inf}")

    # 강조쌍 중복 제거(여러 매치가 같은 쌍 낼 수 있음)
    highlights = [{"up": u, "down": d} for (u, d) in sorted({(h["up"], h["down"]) for h in highlights})]
    out = {"edges": edges, "inferred": inferred, "multi": multi, "deleted": deleted,
           "highlights": highlights}
    write_artifact(code, "rdb.json", out)
    print(f"저장: jobs/{code}/rdb.json  엣지 {len(edges)} "
          f"(정밀 {len(edges)-len(inferred)}, 엄브렐러 {len(inferred)}), "
          f"다중인용 {len(multi)}, 삭제조 {len(deleted)}, 강조쌍 {len(highlights)}")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build_rdb(sys.argv[1] if len(sys.argv) > 1 else "g")
