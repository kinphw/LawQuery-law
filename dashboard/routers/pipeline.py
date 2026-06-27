"""파이프라인 실행 — pipeline.run / pipeline.verify / common.replicate 를 SSE 로그로.

⚠ 운영 적재는 `run --prod` 가 아니라 **복제(replicate)** 로 한다(CLAUDE.md):
   dev 에서 다듬은 ldb_<code> 를 mysqldump|mysql 로 운영에 그대로 복제.
"""
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .. import config, proc

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])
CODE_RE = re.compile(r"[a-z0-9_]{1,16}")
ONLY_RE = re.compile(r"[a-z,]{1,40}")

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _stream(cmd: list):
    return StreamingResponse(
        proc.stream_command(cmd, cwd=config.ROOT),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/run")
def run(code: str, apply: bool = False, force: bool = False, only: str = ""):
    if not CODE_RE.fullmatch(code):
        raise HTTPException(400, "잘못된 code")
    cmd = ["-m", "pipeline.run", code]
    if only:
        if not ONLY_RE.fullmatch(only):
            raise HTTPException(400, "잘못된 only")
        cmd.append(f"--only={only}")
    if apply:
        cmd.append("--apply")
    if force:
        cmd.append("--force")
    return _stream(cmd)


@router.get("/verify")
def verify(code: str):
    if not CODE_RE.fullmatch(code):
        raise HTTPException(400, "잘못된 code")
    return _stream(["-m", "pipeline.verify", code])


@router.get("/replicate")
def replicate(code: str):
    """dev → 운영 정확복제(SSH 터널 + mysqldump|mysql)."""
    if not CODE_RE.fullmatch(code):
        raise HTTPException(400, "잘못된 code")
    return _stream(["-m", "common.replicate", code])
