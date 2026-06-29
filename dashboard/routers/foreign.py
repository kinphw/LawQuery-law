"""해외법령(fin_law_db) — dev/prod 현황 + 법(code) 단위 운영 복제(이관).

국내(status/pipeline 라우터)의 해외판. 상태는 법별 지문(provision_count·
ko_count·content_sig)으로 운영 지체를 비교하고, 복제는 단일 fin_law_db 안의
선택 code 만 교체(다른 나라 법 무해). 복제는 SSE 로그로 실시간 표시.
"""
import re

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from .. import config, foreignstate, proc

router = APIRouter(prefix="/api/foreign", tags=["foreign"])
# 해외 code 는 길다(jp_funds_transfer_co 등) → law.code VARCHAR(48) 에 맞춤
CODE_RE = re.compile(r"[a-z0-9_]{1,48}")
_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.get("/status")
def status(target: str = Query("dev")):
    if target not in ("dev", "prod"):
        raise HTTPException(400, "target 은 dev|prod")
    try:
        return foreignstate.prod_state() if target == "prod" else foreignstate.dev_state()
    except Exception as e:  # noqa: BLE001
        hint = " (운영 접속은 .env 의 SSH_*/MYSQL_*_PROD 필요)" if target == "prod" else ""
        raise HTTPException(503, f"해외법령 {target} 접속 실패: {e}{hint}")


@router.get("/preview")
def preview(code: str):
    """이관 전 미리보기 — dev↔prod 조 단위 신규/변경/삭제 diff(JSON)."""
    if not CODE_RE.fullmatch(code):
        raise HTTPException(400, "잘못된 code")
    try:
        return foreignstate.preview(code)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"미리보기 실패(운영 접속): {e}")


@router.get("/replicate")
def replicate(code: str):
    """dev fin_law_db 의 code 한 건을 운영 fin_law_db 로 정확복제(SSE 로그)."""
    if not CODE_RE.fullmatch(code):
        raise HTTPException(400, "잘못된 code")
    return _stream([code])


@router.get("/replicate-bulk")
def replicate_bulk(codes: str = Query("")):
    """여러 code(쉼표 구분)를 터널 1회로 일괄 복제(SSE 로그). 코드별 독립 트랜잭션."""
    items = [c.strip() for c in codes.split(",") if c.strip()]
    if not items:
        raise HTTPException(400, "codes 가 비어있습니다")
    for c in items:
        if not CODE_RE.fullmatch(c):
            raise HTTPException(400, f"잘못된 code: {c}")
    return _stream(items)


def _stream(codes: list):
    return StreamingResponse(
        proc.stream_command(["-m", "common.replicate_foreign", *codes], cwd=config.ROOT),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
