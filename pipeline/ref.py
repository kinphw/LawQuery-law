"""ref: 조문이 인용한 다른 조 → 참조 엣지.

  - 외부법: 「외부법령명」 제N조…  → ref_type='text', ref_content="[법령명] 제N조[의M][제K항][제L호]"
  - family 내부: 별칭(법/영/규정/세칙/「가족법명」) 또는 bare 제N조 → db_<tier>, ref_target=노드
입도: **분할(splits) 후 노드**를 스캔/해석 → origin·target이 항/호까지(resolve_node=최세밀 노드).
(rdb=위임 트리, ref=횡적 참조 — 별개 UI)
"""
import re
import sys

from pipeline import load_job, write_artifact
from lawparse.ids import resolve_node

_JHH = r"제(\d+)조(?:의(\d+))?(?:제(\d+)항)?(?:제(\d+)호)?"   # 조[의M][제K항][제L호]
_BRACKET = re.compile(r"「([^」]+)」\s*" + _JHH)
_SELF = re.compile(_JHH)                                     # bare 제N조 (자기 단 자기참조)
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


def _label(name: str, g) -> str:
    jo, ga, hang, ho = g
    return (f"[{name}] 제{int(jo)}조" + (f"의{int(ga)}" if ga else "")
            + (f"제{int(hang)}항" if hang else "") + (f"제{int(ho)}호" if ho else ""))


def build_ref(code: str) -> list[dict]:
    from pipeline.overrides import split_tiers
    job = load_job(code)
    tiers = split_tiers(code)                            # 분할 후 행(항/호 입도)
    fam = _family(job)
    nodes = {t: {r[f"id_{t}"] for r in tiers[t] if r.get(f"id_{t}")} for t in ("a", "e", "s", "r")}
    bare = [(a, fam[a]) for a in fam if a[:1] != "「"]
    bare_re = {a: re.compile(rf"(?<![가-힣]){re.escape(a)}\s*" + _JHH) for a, _ in bare}
    bare_words = {a.strip("「」") for a in fam}          # 별칭 뒤 제N조는 별칭참조(자기참조 아님)

    rows, seen = [], set()

    def _ints(g):
        return tuple(int(x) if x else None for x in g)

    def emit_db(oid, pt, g):
        jo, ga, hang, ho = _ints(g)
        tgt = resolve_node(pt, jo, ga, hang, ho, nodes[pt])    # 최세밀 노드(항/호)
        if tgt and tgt != oid and (oid, f"db_{pt}", tgt) not in seen:
            seen.add((oid, f"db_{pt}", tgt))
            rows.append({"id": None, "id_origin": oid, "ref_type": f"db_{pt}",
                         "ref_target": tgt, "ref_content": None})

    def emit_text(oid, label):
        if (oid, "text", label) not in seen:
            seen.add((oid, "text", label))
            rows.append({"id": None, "id_origin": oid, "ref_type": "text",
                         "ref_target": None, "ref_content": label})

    for tier in ("a", "e", "s", "r"):
        for row in tiers[tier]:
            oid = row.get(f"id_{tier}")
            if not oid:                                  # 장/절 title행
                continue
            body = row.get(f"content_{tier}") or ""
            for m in _BRACKET.finditer(body):            # 1) 「법령명」 제N조…
                name = f"「{m.group(1)}」"
                if name in fam:
                    emit_db(oid, fam[name], m.groups()[1:])
                else:
                    emit_text(oid, _label(m.group(1), m.groups()[1:]))
            for a, pt in bare:                           # 2) 별칭(법/영/규정/세칙) 제N조…
                for m in bare_re[a].finditer(body):
                    emit_db(oid, pt, m.groups())
            for m in _SELF.finditer(body):               # 3) bare 제N조 → 자기 단
                pre = body[:m.start()].rstrip()
                if pre.endswith("」") or any(pre.endswith(w) for w in bare_words):
                    continue
                emit_db(oid, tier, m.groups())
    n_ext = sum(1 for r in rows if r["ref_type"] == "text")
    write_artifact(code, "ref.json", rows)
    print(f"저장: jobs/{code}/ref.json  참조 {len(rows)} (외부법 text {n_ext}, 내부 db_* {len(rows)-n_ext})")
    return rows


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build_ref(sys.argv[1] if len(sys.argv) > 1 else "g")
