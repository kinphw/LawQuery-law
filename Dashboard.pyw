"""LawQuery 허브 런처 — 더블클릭하면 로컬 웹 대시보드를 열어준다.

산발된 진입점(NewLaw·LawEditor·frc·sqlhandler)을 대체하는 단일 현관(파사드).
uvicorn 을 기동하고 기본 브라우저로 http://127.0.0.1:4500 을 연다.
콘솔 없음(.pyw). 의존성 미설치 시 대화상자로 안내.
종료: 브라우저 우하단 '허브 종료' 버튼 (또는 작업 관리자).
"""
import os
import sys
import threading
import time
import traceback
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # dashboard 패키지 import 가능하게

HOST, PORT = "127.0.0.1", 4500
URL = f"http://{HOST}:{PORT}/"


def _open_browser():
    time.sleep(1.3)
    webbrowser.open(URL)


def main():
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        try:
            import tkinter.messagebox as mb
            mb.showerror(
                "LawQuery 허브 — 의존성 필요",
                "FastAPI / uvicorn 이 설치돼 있지 않습니다.\n\n"
                "명령 프롬프트에서:\n    pip install fastapi uvicorn\n\n"
                "설치 후 다시 더블클릭하세요.",
            )
        except Exception:
            sys.stderr.write("pip install fastapi uvicorn\n")
        return

    try:
        import uvicorn
        threading.Thread(target=_open_browser, daemon=True).start()
        uvicorn.run("dashboard.server:app", host=HOST, port=PORT, log_level="warning")
    except Exception:
        try:
            import tkinter.messagebox as mb
            mb.showerror("LawQuery 허브 — 오류", traceback.format_exc())
        except Exception:
            sys.stderr.write(traceback.format_exc())


if __name__ == "__main__":
    main()
