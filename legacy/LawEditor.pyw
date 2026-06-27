"""
LawEditor — LawQuery 법령 도구 **단일 진입점**.

  • 더블클릭(인자 없음)         → GUI 편집기 (콘솔 없음, 오류는 대화상자)
  • python LawEditor.pyw <cmd>  → CLI (template / ingest / export / gui …)

의존성: pip install -r requirements.txt  (최초 1회)
CLI 구현은 run.py 모듈에 있고 여기서 위임한다(진입점은 이 파일 하나).
"""
import os
import sys

# legacy/ 에 있으므로 부모(프로젝트 루트)를 경로에 추가 → run·gui 패키지 import 가능
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_gui() -> None:
    try:
        from gui.app import main
        main()
    except Exception:
        # .pyw 는 콘솔이 없으므로 오류를 대화상자로 표시
        import traceback
        try:
            import tkinter.messagebox as mb
            mb.showerror("LawEditor 오류", traceback.format_exc())
        except Exception:
            pass


def main() -> None:
    if len(sys.argv) > 1:
        # 인자가 있으면 CLI 로 위임 (터미널: `python LawEditor.pyw ingest --law c …`)
        import run
        run.main()
    else:
        _run_gui()


if __name__ == "__main__":
    main()
