"""
LawEditor — 법령 편집기 더블클릭 실행 (콘솔 창 없음).

파이썬이 설치돼 있으면 이 파일을 더블클릭하면 GUI가 뜬다.
의존성: pip install -r requirements.txt  (최초 1회)
"""
import os
import sys

# 어디서 실행하든 패키지 import 되도록 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
