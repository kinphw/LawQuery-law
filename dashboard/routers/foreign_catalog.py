"""해외법령 카탈로그 — dev/prod foreign_catalog CRUD + 개발→운영 복제(registry 와 동일 패턴)."""
import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .. import fcatalog_store as store

router = APIRouter(prefix="/api/foreign-catalog", tags=["foreign-catalog"])
CODE_RE = re.compile(r"[a-z0-9_]{1,48}")


class CatalogIn(BaseModel):
    code: str
    jurisdiction: str = ""
    title_ko: str = ""
    abbrev: str = ""
    status: str = ""
    law_type: str = ""
    is_crypto: bool = False
    summary: str = ""
    tags: list[str] = []
    highlights: list[str] = []
    sort_order: int = 100
    hidden: bool = False


def _guard(target: str):
    if target not in ("dev", "prod"):
        raise HTTPException(400, "target 은 dev|prod")


def _wrap(target: str, fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        hint = " (운영 접속은 .env SSH_*/MYSQL_*_PROD 필요)" if target == "prod" else ""
        raise HTTPException(503, f"{target} 카탈로그 접속 실패: {e}{hint}")


@router.get("")
def overview(target: str = Query("dev")):
    _guard(target)
    return _wrap(target, lambda: store.overview(target))


@router.post("")
def save(body: CatalogIn, target: str = Query("dev")):
    _guard(target)
    code = body.code.strip().lower()
    if not CODE_RE.fullmatch(code):
        raise HTTPException(400, "코드는 영소문자/숫자/_ 1~48자")
    row = {
        "code": code,
        "jurisdiction": body.jurisdiction.strip() or None,
        "title_ko": body.title_ko.strip() or None,
        "abbrev": body.abbrev.strip() or None,
        "status": body.status.strip() or None,
        "law_type": body.law_type.strip() or None,
        "is_crypto": bool(body.is_crypto),
        "summary": body.summary.strip() or None,
        "tags": [t.strip() for t in body.tags if t.strip()],
        "highlights": [h.strip() for h in body.highlights if h.strip()],
        "sort_order": int(body.sort_order),
        "hidden": bool(body.hidden),
    }
    _wrap(target, lambda: store.save(target, row))
    return {"ok": True}


@router.get("/replicate/preview")
def replicate_preview():
    """개발→운영 일괄 복제 시 적용될 변경 미리보기(쓰기 없음)."""
    return _wrap("prod", store.replicate_preview)


@router.post("/replicate")
def replicate():
    """운영 foreign_catalog 를 개발과 동일하게 일괄 복제(전체 교체)."""
    return _wrap("prod", store.replicate_to_prod)


@router.delete("/{code}")
def remove(code: str, target: str = Query("dev")):
    _guard(target)
    _wrap(target, lambda: store.remove(target, code))
    return {"ok": True}
