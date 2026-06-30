"""API 법령 적재 파이프라인 (job.json 구동).

jobs/<code>/job.json → build(fetch·조단위·ID) → qa(검증) → rdb(인용·엄브렐러) → load(ldb_<code>).
재사용 모듈: fetcher.law_api(API), lawparse.splitter/ids(파싱·ID), loader.loader(적재).
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "jobs"


def job_dir(code: str) -> Path:
    return JOBS / code


def load_job(code: str) -> dict:
    return json.loads((job_dir(code) / "job.json").read_text(encoding="utf-8"))


def tier_units(job: dict) -> list[dict]:
    """job → 처리 단위 리스트 [{tier, track, src}].

    단일트랙: sources(a/e/s/r/b) 각각 track=None.
    멀티트랙(행정규칙 병렬): sources(a/e/s) 공유(track=None) + tracks.<code>.<tier> 각각 track=<code>.
    같은 tier(r/b)가 트랙마다 반복되며 ID는 track 네임스페이스로 유일(stem_id track 인자)."""
    units = [{"tier": t, "track": None, "src": s} for t, s in job.get("sources", {}).items()]
    for tcode, tr in job.get("tracks", {}).items():
        for tier, src in tr.items():
            if tier == "label" or not isinstance(src, dict):
                continue
            units.append({"tier": tier, "track": tcode, "src": src})
    return units


def job_tracks(job: dict) -> dict:
    """{track_code: label} (멀티트랙이면). 단일트랙이면 {}."""
    return {c: (t.get("label") or c) for c, t in job.get("tracks", {}).items()}


def read_artifact(code: str, name: str) -> dict:
    return json.loads((job_dir(code) / name).read_text(encoding="utf-8"))


def write_artifact(code: str, name: str, obj) -> Path:
    p = job_dir(code) / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return p
