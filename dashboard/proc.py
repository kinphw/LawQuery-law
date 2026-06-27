"""서브프로세스 실행 헬퍼 — 파이프라인은 SSE 로그 스트림, 외부 GUI 는 분리 런치."""
import asyncio
import json
import os
import subprocess

from . import config


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def stream_command(cmd: list, cwd: str):
    """`PYTHON <cmd...>` 실행 후 stdout 라인을 SSE 이벤트로 흘린다.

    이벤트: {type:start,cmd} → {type:log,line}* → {type:end,code}
    asyncio.to_thread 로 블로킹 readline 을 빼서 이벤트 루프를 막지 않는다.
    """
    full = [config.PYTHON, *cmd]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    try:
        proc = subprocess.Popen(
            full, cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1, text=True, encoding="utf-8", errors="replace",
        )
    except Exception as e:  # noqa: BLE001
        yield _sse({"type": "end", "code": -1, "error": str(e)})
        return

    yield _sse({"type": "start", "cmd": " ".join(cmd)})
    try:
        while True:
            line = await asyncio.to_thread(proc.stdout.readline)
            if not line:
                break
            yield _sse({"type": "log", "line": line.rstrip("\r\n")})
    finally:
        code = await asyncio.to_thread(proc.wait)
        yield _sse({"type": "end", "code": code})


def launch_detached(cmd: list, cwd: str, use_pythonw: bool = False) -> None:
    """별창 GUI 등을 분리 실행(로그 미수집, 즉시 반환)."""
    py = config.PYTHONW if use_pythonw else config.PYTHON
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(
        [py, *cmd], cwd=cwd, creationflags=flags,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, close_fds=True,
    )
