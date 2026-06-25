"""build: job.json 의 4개(이상) source 를 fetch → 조 단위 노드 + ID + meta → data.json.

- 법/시행령(kind=law): law_api.get_law_text → 구조화 조/항/호 → 조 단위로 합쳐 1행.
- 감독규정/세칙(kind=admrul): law_api.get_admin_rule_text(문자열) → splitter 로 조 분리.
항/호는 조 본문에 합쳐 보관(조 단위만 구별). ID 규약은 lawparse.ids.
"""
import sys

from fetcher import law_api
from lawparse import splitter
from lawparse.ids import rows_for_tier
from common.schema_map import SHEETS
from pipeline import load_job, write_artifact


def _join_law_article(a: dict) -> str:
    parts = [a["조문내용"]]
    for h in a["항목록"]:
        if h["항내용"]:
            parts.append(h["항내용"])
        for ho in h["호목록"]:
            if ho["호내용"]:
                parts.append("  " + ho["호내용"])
            for m in ho["목목록"]:
                if m["목내용"]:
                    parts.append("    " + m["목내용"])
    return "\n".join(p for p in parts if p)


def _law_articles(src: dict):
    if src.get("mst") and src.get("ef_yd"):           # 연혁(구버전) MST+efYd
        t = law_api.get_law_text(mst=src["mst"], ef_yd=src["ef_yd"])
    else:
        t = law_api.get_law_text(src["id"])           # 현행 ID
    arts = []
    for a in t["조문목록"]:
        jo, ga = a["조문번호"], a["조문가지번호"]
        title = f"제{jo}조" + (f"의{ga}" if ga else "") + (f"({a['조제목']})" if a["조제목"] else "")
        arts.append({"jo": jo, "ga": ga, "title": title, "stem": _join_law_article(a), "items": []})
    return t.get("법령명") or "", t.get("시행일자") or "", arts


def _admin_articles(serial: str):
    t = law_api.get_admin_rule_text(serial)
    body = splitter.format_admin_body(t["조문내용"])   # 항/호/목 한 줄 붙음 → 개행 삽입
    arts = []
    for u in splitter.split_body(body):
        if u["type"] != "article":
            continue
        content = u["stem"] + ("\n" + "\n".join(u["items"]) if u["items"] else "")
        arts.append({"jo": u["jo"], "ga": u["ga"], "title": u["head"], "stem": content, "items": []})
    return t.get("행정규칙명") or "", t.get("시행일자") or "", arts


def build(code: str) -> dict:
    job = load_job(code)
    data = {sh: [] for sh in SHEETS}
    meta = []
    for tier, src in job["sources"].items():
        if src["kind"] == "law":
            name, eff, arts = _law_articles(src)
        else:
            name, eff, arts = _admin_articles(src["id"])
        data[tier] = rows_for_tier(tier, arts)
        meta.append({"origin": tier, "full_name": f"{name}\n[시행 {eff}]",
                     "short_name": src.get("short", tier)})
        ref = src.get("id") or f"MST{src.get('mst')}@{src.get('ef_yd')}"
        print(f"  {tier} ({src['kind']} {ref}): {name} — {len(arts)}조")
    data["meta"] = meta
    write_artifact(code, "data.json", data)
    print(f"저장: jobs/{code}/data.json  (a:{len(data['a'])} e:{len(data['e'])} "
          f"s:{len(data['s'])} r:{len(data['r'])})")
    return data


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build(sys.argv[1] if len(sys.argv) > 1 else "g")
