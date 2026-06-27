"""인테이크 CRUD — intake/<code>.json. (NewLaw.pyw 폼을 웹으로 흡수)"""
import datetime
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import dbstate, intake_store

router = APIRouter(prefix="/api/intake", tags=["intake"])
CODE_RE = re.compile(r"[a-z0-9]{1,16}")


class IntakeIn(BaseModel):
    code: str
    kind: str = "new"          # new | update
    tiers: int = 4             # 4 | 5(+별표)
    names: dict = {}           # {a,e,s,r}
    options: dict = {}         # {sched: bool}
    notes: str = ""


@router.get("/meta")
def meta():
    return {"tiers": [{"code": c, "label": l, "kind": k} for c, l, k in intake_store.TIERS]}


@router.get("/list")
def list_():
    return intake_store.overview()


@router.get("/{code}")
def get(code: str):
    d = intake_store.load_intake(code)
    if d:
        return {**d, "_built": False}
    job = intake_store.load_job(code)
    if job:
        try:
            meta = dbstate.dev_law(code)        # db_meta 정식 법령명·시행일
        except Exception:
            meta = None
        return {"code": code, "_built": True, "job": job, "meta": meta}
    raise HTTPException(404, "해당 약자의 인테이크/job.json 이 없습니다.")


@router.post("")
def create(body: IntakeIn):
    code = body.code.strip().lower()
    if not CODE_RE.fullmatch(code):
        raise HTTPException(400, "약자(code)는 영소문자/숫자 1~16자여야 합니다. 예: j, y, g")
    if not (body.names.get("a") or "").strip():
        raise HTTPException(400, "최소한 법(A)의 정확한 명칭은 입력해야 합니다.")

    built = {b["code"] for b in intake_store.list_built()}
    kind = body.kind if not (code in built and body.kind == "new") else "update"

    data = {
        "code": code,
        "kind": kind,
        "tiers": int(body.tiers),
        "names": {k: (v or "").strip() for k, v in body.names.items()},
        "options": body.options or {"sched": False},
        "notes": (body.notes or "").strip(),
        "created": datetime.date.today().isoformat(),
        "_status": "pending",
    }
    intake_store.save_intake(data)
    rel = f"intake/{code}.json"
    return {"ok": True, "path": rel, "handoff": f"{rel} 읽고 작업해줘", "data": data}


@router.delete("/{code}")
def delete(code: str):
    if not intake_store.delete_intake(code):
        raise HTTPException(404, "삭제할 인테이크 파일이 없습니다.")
    return {"ok": True}
