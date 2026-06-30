"""build: job.json 의 4개(이상) source 를 fetch → 조 단위 노드 + ID + meta → data.json.

- 법/시행령(kind=law): law_api.get_law_text → 구조화 조/항/호 → 조 단위로 합쳐 1행.
- 감독규정/세칙(kind=admrul): law_api.get_admin_rule_text(문자열) → splitter 로 조 분리.
항/호는 조 본문에 합쳐 보관(조 단위만 구별). ID 규약은 lawparse.ids.
"""
import sys

from fetcher import law_api
from lawparse import splitter
from lawparse.ids import rows_for_tier, stem_id
from common.schema_map import SHEETS
from pipeline import load_job, write_artifact, tier_units


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
        if "전문" in a:                            # 장/절 제목(조 앞 위치)
            arts.append({"type": "title", "title": a["전문"], "jo": a.get("조문번호", 0), "ga": None})
            continue
        jo, ga = a["조문번호"], a["조문가지번호"]
        title = f"제{jo}조" + (f"의{ga}" if ga else "") + (f"({a['조제목']})" if a["조제목"] else "")
        arts.append({"jo": jo, "ga": ga, "title": title, "stem": _join_law_article(a), "items": []})
    return t.get("법령명") or "", t.get("시행일자") or "", arts


def _merge_sched(tier: str, name: str, cur_eff: str, cur_arts: list):
    """시행예정(미시행 개정) 반영: 현행 arts + 신설조 병합(조번호순) + sched_map{id:(미래본문,시행일)}.
    시행예정 버전에서 조문시행일자 > 현행시행일 인 조 = 개정/신설된 조."""
    from lawparse.article_split import split_article
    sv = law_api.find_sched_version(name)
    if not sv:
        return cur_arts, {}
    st = law_api.get_law_text(mst=sv[0], ef_yd=sv[1])
    sef = sv[1]                                          # 시행예정 시행일
    cur_by = {(a["jo"], a["ga"]): a["stem"] for a in cur_arts if a.get("type") != "title"}
    sched_map, extra = {}, []
    for a in st["조문목록"]:
        if "전문" in a:                                  # 장/절 제목 무시
            continue
        key = (a["조문번호"], a["조문가지번호"])
        content = _join_law_article(a)
        cur_content = cur_by.get(key)
        if cur_content == content:
            continue                                     # 변경 없음(현행과 동일)
        jid = stem_id(tier, *key)
        sched_map[jid] = [content, sef]                  # ① 조 단위(미분리 조용)
        if cur_content is None:                          # 신설 조(아직 시행전) → 현행본문 비움.
            title = f"제{key[0]}조" + (f"의{key[1]}" if key[1] else "") + \
                    (f"({a['조제목']})" if a["조제목"] else "")
            extra.append({"jo": key[0], "ga": key[1], "title": title,
                          "stem": "", "items": []})        # content_a="" → 시행예정(gray)만 표시

        else:                                            # ② 변경 조 → 항/호 단위 diff(분리 조용)
            ch = dict(split_article(jid, cur_content, "hang")[1])
            for cid, ctext in split_article(jid, content, "hang")[1]:
                if ch.get(cid) != ctext:                 # 변경/신설된 항·호만
                    sched_map[cid] = [ctext, sef]
    merged = sorted(cur_arts + extra,
                    key=lambda x: (x.get("jo") or 0, 0 if x.get("type") == "title" else 1, x.get("ga") or 0))
    return merged, sched_map


def _admin_articles(serial: str):
    t = law_api.get_admin_rule_text(serial)
    body = splitter.format_admin_body(t["조문내용"])   # 항/호/목 한 줄 붙음 → 개행 삽입
    arts = []
    for u in splitter.split_body(body):
        if u["type"] == "title":                   # 장/절 제목
            arts.append({"type": "title", "title": u["title"]})
            continue
        content = u["stem"] + ("\n" + "\n".join(u["items"]) if u["items"] else "")
        arts.append({"jo": u["jo"], "ga": u["ga"], "title": u["head"], "stem": content, "items": []})
    return t.get("행정규칙명") or "", t.get("시행일자") or "", arts


def build(code: str) -> dict:
    job = load_job(code)
    data = {sh: [] for sh in SHEETS}
    meta = []
    sched_all = {}                                       # 시행예정 {nodeID:[미래본문,시행일]} (적용은 splits 후)
    for unit in tier_units(job):
        tier, track, src = unit["tier"], unit["track"], unit["src"]
        n_sched = 0
        if src["kind"] == "law":
            name, eff, arts = _law_articles(src)
            if src.get("sched"):
                arts, sm = _merge_sched(tier, name, eff, arts)
                sched_all.update(sm); n_sched = len(sm)
        else:
            name, eff, arts = _admin_articles(src["id"])
        data[tier].extend(rows_for_tier(tier, arts, track=track))   # 트랙별 누적(같은 tier 반복)
        meta.append({"origin": tier, "full_name": f"{name}\n[시행 {eff}]",
                     "short_name": src.get("short", tier), "track": track})
        ref = src.get("id") or f"MST{src.get('mst')}@{src.get('ef_yd')}"
        nj = sum(1 for a in arts if a.get("type") != "title")
        sx = f" (+시행예정 노드 {n_sched})" if n_sched else ""
        tx = f" [track={track}]" if track else ""
        print(f"  {tier}{tx} ({src['kind']} {ref}): {name} — {nj}조{sx}")
    data["meta"] = meta
    from pipeline import job_tracks
    data["track"] = [{"track_code": c, "label": l, "sort_order": i}
                     for i, (c, l) in enumerate(job_tracks(job).items(), 1)]
    write_artifact(code, "data.json", data)
    write_artifact(code, "sched.json", sched_all)
    sig = " ".join(f"{t}:{len(data[t])}" for t in ("a", "e", "s", "r", "b") if data.get(t))
    print(f"저장: jobs/{code}/data.json  ({sig}), 시행예정 노드 {len(sched_all)}")
    return data


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build(sys.argv[1] if len(sys.argv) > 1 else "g")
