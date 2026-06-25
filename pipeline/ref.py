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
from fetcher import law_api

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


def _fetch_external(name: str) -> dict:
    """외부법명 → {(조번호,가지번호): 조본문}. 법령(eflaw)→없으면 행정규칙(admrul). 못 찾으면 {}."""
    from pipeline.build import _join_law_article
    try:                                                  # ① 법령(eflaw)
        hits = law_api.search_law(name)
        hit = next((h for h in hits if h.get("법령명") == name), hits[0] if hits else None)
        if hit and hit.get("법령ID"):
            t = law_api.get_law_text(hit["법령ID"])
            return {(a["조문번호"], a["조문가지번호"]): _join_law_article(a)
                    for a in t["조문목록"] if "전문" not in a}
    except Exception:
        pass
    try:                                                  # ② 행정규칙(규정·세칙 등 — 문자열→splitter)
        from lawparse import splitter
        hits = law_api.search_admin_rule(name)
        hit = next((h for h in hits if h.get("행정규칙명") == name), hits[0] if hits else None)
        if hit and hit.get("행정규칙일련번호"):
            body = splitter.format_admin_body(
                law_api.get_admin_rule_text(hit["행정규칙일련번호"])["조문내용"])
            return {(u["jo"], u["ga"]): u["stem"] + ("\n" + "\n".join(u["items"]) if u["items"] else "")
                    for u in splitter.split_body(body) if u["type"] == "article"}
    except Exception:
        pass
    return {}


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
    ext_cache = {}                                   # 외부법 본문 캐시(법명당 1회 fetch)

    def _ext_body(name, jo, ga):
        if name not in ext_cache:
            ext_cache[name] = _fetch_external(name)
        return ext_cache[name].get((jo, ga))

    def _ints(g):
        return tuple(int(x) if x else None for x in g)

    def emit_db(oid, pt, g):
        jo, ga, hang, ho = _ints(g)
        tgt = resolve_node(pt, jo, ga, hang, ho, nodes[pt])    # 최세밀 노드(항/호)
        if tgt and tgt != oid and (oid, f"db_{pt}", tgt) not in seen:
            seen.add((oid, f"db_{pt}", tgt))
            rows.append({"id": None, "id_origin": oid, "ref_type": f"db_{pt}",
                         "ref_target": tgt, "ref_content": None})

    def emit_text(oid, name, g):                 # 외부법 → 라벨+본문(임베드) + law.go.kr 링크
        label = _label(name, g)
        jo, ga, _, _ = _ints(g)
        if (oid, "text", label) in seen:
            return
        seen.add((oid, "text", label))
        body = _ext_body(name, jo, ga)
        content = label + ("\n" + body if body else "")
        url = f"https://www.law.go.kr/법령/{name}/제{jo}조" + (f"의{ga}" if ga else "")
        rows.append({"id": None, "id_origin": oid, "ref_type": "text",
                     "ref_target": url, "ref_content": content})

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
                    emit_text(oid, m.group(1), m.groups()[1:])
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
