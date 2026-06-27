"""dev/prod 법령 현황 — 단별 법령명·시행일자 (운영 지체 비교용)."""
from fastapi import APIRouter, HTTPException, Query

from .. import dbstate

router = APIRouter(prefix="/api/status", tags=["status"])


@router.get("/laws")
def laws(target: str = Query("dev")):
    try:
        return dbstate.prod_state() if target == "prod" else dbstate.dev_state()
    except Exception as e:  # noqa: BLE001
        hint = " (운영 접속은 .env 의 SSH_*/MYSQL_*_PROD 설정 필요)" if target == "prod" else ""
        raise HTTPException(503, f"{target} 접속 실패: {e}{hint}")
