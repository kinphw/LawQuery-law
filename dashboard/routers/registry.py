"""법령 노출 레지스트리 — dev/prod law_registry CRUD (기존 GUI '법령 목록 관리' 흡수)."""
import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .. import regstore

router = APIRouter(prefix="/api/registry", tags=["registry"])
CODE_RE = re.compile(r"[a-z0-9_]{1,16}")


class RegistryIn(BaseModel):
    code: str
    label: str = ""
    sort_order: int = 100
    enabled: bool = True
    kind: str = "law"


def _guard(target: str):
    if target not in ("dev", "prod"):
        raise HTTPException(400, "target 은 dev|prod")


def _wrap(target: str, fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        hint = " (운영 접속은 .env SSH_*/MYSQL_*_PROD 필요)" if target == "prod" else ""
        raise HTTPException(503, f"{target} 레지스트리 접속 실패: {e}{hint}")


@router.get("")
def overview(target: str = Query("dev")):
    _guard(target)
    return _wrap(target, lambda: regstore.overview(target))


@router.post("")
def save(body: RegistryIn, target: str = Query("dev")):
    _guard(target)
    code = body.code.strip().lower()
    if not CODE_RE.fullmatch(code):
        raise HTTPException(400, "코드는 영소문자/숫자/_ 1~16자")
    _wrap(target, lambda: regstore.save(
        target, code, body.label.strip() or None, int(body.sort_order),
        bool(body.enabled), body.kind.strip() or "law"))
    return {"ok": True}


@router.delete("/{code}")
def remove(code: str, target: str = Query("dev")):
    _guard(target)
    _wrap(target, lambda: regstore.remove(target, code))
    return {"ok": True}
