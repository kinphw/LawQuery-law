# legacy/ — 허브로 대체된 기존 진입점 보관소

루트를 단일 현관(`Dashboard.pyw`)으로 정리하면서, 더블클릭 진입점 `.pyw` 들을 여기로 옮겼다.

| 파일 | 상태 | 비고 |
|------|------|------|
| `NewLaw.pyw` | **대체됨** | 인테이크 폼 → 허브 **법령 인테이크** 웹페이지로 흡수. 로직은 `dashboard/intake_store.py`. |
| `LawEditor.pyw` | **사용 중(런치)** | 레코드 편집 GUI. 허브 **도구** 탭이 이 파일을 런치. Phase 2 에서 웹페이지로 흡수 후 제거 예정. |

- 둘 다 실행 시 부모(프로젝트 루트)를 기준으로 동작하도록 경로를 보정해 두었다(직접 더블클릭해도 정상).
- CLI 는 그대로: `python legacy/LawEditor.pyw {template|ingest|export|gui}` 또는 `python run.py …`.
- 권장 진입점은 루트 `Dashboard.pyw`(허브).
