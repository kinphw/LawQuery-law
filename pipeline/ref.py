"""ref: 조문이 인용한 다른 조 → 참조 엣지.

  - 외부법: 「외부법령명」 제N조  → ref_type='text', ref_content="[법령명] 제N조[의M]"
            (전문 임베드는 선택: MCP/law_api enrich 단계 — 기본은 헤더만)
  - family 내부: job.json refers 별칭(법/규정/금융위설치법/「가족법명」) 제N조 → ref_type='db_<tier>', ref_target=노드
family 별칭은 job.sources[*].refers 에서 도출(별칭→상위단). 「」명이 family면 내부, 아니면 외부.
조 단위라 항/호 인용은 조로 매핑. (rdb=위임 트리, ref=횡적 참조 — 별개 UI)
"""
import re
import sys

from pipeline import load_job, read_artifact, write_artifact

UP = {"a": "A", "e": "E", "s": "S", "r": "R"}
_BRACKET = re.compile(r"「([^」]+)」\s*제(\d+)조(?:의(\d+))?")
# 표준 단별 별칭(가족 내부) — refers(상위 지칭)에 없는 영→e·세칙→r 까지 잡아 db_e/db_r 누락 방지
STD_ALIAS = {"a": ["법"], "e": ["영", "시행령"], "s": ["규정", "감독규정"], "r": ["세칙", "시행세칙"]}


def _family(job: dict) -> dict:
    fam = {}
    for src in job["sources"].values():                  # ① job.json refers(명시적 별칭 → 상위단)
        p = src.get("parent")
        for a in (src.get("refers", []) if p else []):
            fam[a] = p
    for tier in job["sources"]:                          # ② 표준 단별 별칭(존재하는 단만, 기존 우선)
        for a in STD_ALIAS.get(tier, []):
            fam.setdefault(a, tier)
    return fam


def build_ref(code: str) -> list[dict]:
    job = load_job(code)
    data = read_artifact(code, "data.json")
    fam = _family(job)
    nodes = {t: {r[f"id_{t}"] for r in data[t]} for t in ("a", "e", "s", "r")}
    # 괄호 없는 별칭(법·규정·금융위설치법 …)별 정규식
    bare = [(a, fam[a]) for a in fam if a[:1] != "「"]
    bare_re = {a: re.compile(rf"(?<![가-힣]){re.escape(a)}\s*제(\d+)조(?:의(\d+))?") for a, _ in bare}

    rows, seen = [], set()
    n_ext = n_int = 0
    for tier in ("a", "e", "s", "r"):
        for row in data[tier]:
            oid = row[f"id_{tier}"]
            body = row.get(f"content_{tier}") or ""
            # 1) 「법령명」 제N조 — family면 내부, 아니면 외부
            for m in _BRACKET.finditer(body):
                name = f"「{m.group(1)}」"
                jo = int(m.group(2))
                ga = m.group(3)
                if name in fam:
                    pt = fam[name]; tgt = f"{UP[pt]}{jo}" + (f"_{int(ga)}" if ga else "")
                    if tgt in nodes[pt] and (oid, f"db_{pt}", tgt) not in seen:
                        seen.add((oid, f"db_{pt}", tgt))
                        rows.append({"id": None, "id_origin": oid, "ref_type": f"db_{pt}",
                                     "ref_target": tgt, "ref_content": None}); n_int += 1
                else:
                    label = f"[{m.group(1)}] 제{jo}조" + (f"의{int(ga)}" if ga else "")
                    if (oid, "text", label) not in seen:
                        seen.add((oid, "text", label))
                        rows.append({"id": None, "id_origin": oid, "ref_type": "text",
                                     "ref_target": None, "ref_content": label}); n_ext += 1
            # 2) 괄호 없는 family 별칭(법/규정/…) 제N조 → 내부
            for a, pt in bare:
                for m in bare_re[a].finditer(body):
                    tgt = f"{UP[pt]}{int(m.group(1))}" + (f"_{int(m.group(2))}" if m.group(2) else "")
                    if tgt in nodes[pt] and (oid, f"db_{pt}", tgt) not in seen:
                        seen.add((oid, f"db_{pt}", tgt))
                        rows.append({"id": None, "id_origin": oid, "ref_type": f"db_{pt}",
                                     "ref_target": tgt, "ref_content": None}); n_int += 1
    write_artifact(code, "ref.json", rows)
    print(f"저장: jobs/{code}/ref.json  참조 {len(rows)} (외부법 text {n_ext}, 내부 db_* {n_int})")
    return rows


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build_ref(sys.argv[1] if len(sys.argv) > 1 else "g")
