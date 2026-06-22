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


def read_artifact(code: str, name: str) -> dict:
    return json.loads((job_dir(code) / name).read_text(encoding="utf-8"))


def write_artifact(code: str, name: str, obj) -> Path:
    p = job_dir(code) / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return p
