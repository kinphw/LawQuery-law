# intake/ — 새 법령 인테이크 큐

새 법령을 파이프라인에 태우기 **직전의 진입로**. 사람이 *아는 것*만 담긴 요청 파일이 여기 모인다.

## 흐름
```
NewLaw.pyw (더블클릭)  →  사람이 약자·단수·명칭·지시 입력  →  intake/<code>.json 저장
        │
        ▼
"intake/<code>.json 읽고 작업해줘"  (Claude 에게 지시)
        │
        ▼
Claude:  MCP 로 소스(법령ID/일련번호) 검색  →  jobs/<code>/job.json 작성
         →  python -m pipeline.run <code>  (dry)  →  --apply  →  verify  →  보정 제안
```

GUI 가 `job.json` 을 직접 만들지 않는 이유: `job.json` 의 핵심값(`sources.id`=law.go.kr
법령ID/일련번호, `refers`, `umbrella`)은 **사람이 모르는 값**이라 Claude 가 검색·판단으로 채운다.
인테이크는 사람이 아는 **명칭·약자·단수·지시**만 받는다.

## <code>.json 스키마
```jsonc
{
  "code": "k",                 // ldb_<code> · 영소문자/숫자
  "kind": "new",               // new(신규) | update(갱신=기존 재가동)
  "tiers": 4,                  // 4(법·시행령·감독규정·세칙) | 5(+별표 B)
  "names": {                   // 단별 정확한 명칭 (없는 단은 "")
    "a": "○○법",
    "e": "○○법 시행령",
    "s": "○○감독규정",
    "r": "○○감독규정 시행세칙"
  },
  "options": { "sched": false },  // 시행예정(미시행 개정) 반영
  "notes": "자유 지시사항",
  "created": "2026-06-27",
  "_status": "pending"         // pending → (Claude 가 job.json 구축 후 done 으로 갱신 가능)
}
```

## Claude 작업 지침 (이 파일을 읽었을 때)
1. `names` 의 각 단을 `mcp__law__search_law`(법/시행령) · `mcp__law__search_admin_rule`(감독규정/세칙)
   로 검색해 **정확한 항목**(법령ID/일련번호) 식별. 모호하면 사용자에게 확인.
2. `jobs/<code>/job.json` 작성 — 스키마는 `../CLAUDE.md` ★섹션. `tiers==5` 면 별표(B) 포함,
   `options.sched==true` 면 해당 law 단에 `"sched": true`.
3. `python -m pipeline.run <code>` (dry) → 검토 → `--apply` → `python -m pipeline.verify <code>`.
4. 무인용 rdb 엄브렐러 등 판단 보정 제안. 끝나면 `_status` 를 `done` 으로 갱신(선택).
5. 노출: `ldb_auth.law_registry` 1행(GUI '법령 목록 관리' 또는 `LawQuery/db/law_registry.sql`).
