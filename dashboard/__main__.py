"""`python -m dashboard` — 콘솔 로그 + 코드 변경 자동 리로드 + 브라우저 자동 오픈.
(더블클릭 진입점은 루트 `Dashboard.pyw`, 안정 모드·리로드 없음.)
"""
import os
import threading
import time
import webbrowser

import uvicorn

from . import config

if __name__ == "__main__":
    url = f"http://{config.HOST}:{config.PORT}/"

    def _open_browser():
        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(
        "dashboard.server:app",
        host=config.HOST,
        port=config.PORT,
        log_level="info",
        reload=True,                          # 코드 수정 시 자동 반영
        reload_dirs=[os.path.dirname(__file__)],
    )
