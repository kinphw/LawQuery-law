"""외부 도구 파사드 — 기존 GUI(frc·sqlhandler·법령편집기)를 단일 현관에서 런치."""
from fastapi import APIRouter, HTTPException

from .. import config, proc

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
def list_tools():
    return config.public_tools()


@router.post("/{tool_id}/launch")
def launch(tool_id: str):
    t = config.tool(tool_id)
    if not t:
        raise HTTPException(404, "알 수 없는 도구")
    import os
    if not os.path.isdir(t["cwd"]):
        raise HTTPException(400, f"경로 없음: {t['cwd']}")
    proc.launch_detached(t["cmd"], cwd=t["cwd"], use_pythonw=(t["kind"] == "gui"))
    return {"ok": True}
