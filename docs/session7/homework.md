# 7회차 과제

필수 둘, 선택 하나입니다. 끝났는지는 `make check-s07` 가 **5/5** 인지로 압니다. 30분 안쪽입니다.

## 필수 1. 수업에서 만든 결과 파일을 커밋 — 수업에서 끝냈으면 5분

채울 자리 둘(`main.ask`, `sse.stream_graph`)이 채워졌으면 이렇게 끝납니다. 서버가 떠 있어야 합니다.

```bash
make test             # 128개 전부 통과
make api              # 두 번째 터미널에서
make api-bench        # results/api_bench.json (약 3분)
make check-s07        # 4/5. 마지막 항목은 필수 2 입니다
```

Windows 는 [install.md](../install.md) 의 PowerShell 명령을 씁니다. 수업에서 못 채운 함수가 있으면 강사가 수업 뒤 올리는 **solution 브랜치**를 봅니다.

https://github.com/hyeonsikseo/finance-agentic-rag-s07/tree/solution/src/finrag/api

보고 베끼는 게 아니라 **읽고 닫은 다음 자기 손으로 다시 씁니다.**

## 필수 2. 보안 질의서 답변서 — 20분

정보보호팀이 묻는 여섯 질문에 답합니다. "안전합니다"가 아니라 **어디에 무엇이 남고 누가 볼 수 있는가**를 적는 문서입니다.

1. `docs/templates/security_questionnaire.md` 를 `docs/security_questionnaire.md` 로 복사합니다(수업에서 했으면 그 파일).
2. 빈칸(`____`)을 전부 채웁니다. `make check-s07` 가 빈칸이 남았는지 셉니다.

채울 때 볼 것:

- **1절 데이터 흐름**의 "외부로 나가는 것 / 나가지 않는 것"은 수업 4부의 감사 로그 한 줄과 `agent/policy.yaml` 의 `pii.patterns` 에서 읽습니다.
- **Q2 로그**의 "응답 본문" 칸은 `src/finrag/api/audit.py` 의 `write` 가 무엇을 남기는지 보고 적습니다(답변 본문은 남기지 않고 인용 청크 ID 만 남깁니다). 보존 기간과 접근 권한은 가정을 적되 "가정"이라고 씁니다.
- **Q3** 의 숫자 둘은 `results/agentic.json` 의 `abstain_accuracy` 와 `false_refusal_rate`, **Q4** 의 통과 수는 `results/adversarial.json` 입니다.
- **Q5 고영향 AI** 는 "약관 조회 · 안내는 대출 심사 같은 개인의 권리 · 의무를 정하는 판단이 아니다"가 비해당의 근거입니다. 재검토 시점은 서비스 범위가 바뀔 때로 적습니다.
- **Q6 망분리**는 수업 6부의 배포 모드 셋 중 자기 가정(외부 LLM API / 폐쇄망 / 클라우드)을 고르고 이유 한 줄.
- **3절 남은 위험**의 빈 행 하나는 자기 생각을 적습니다. 예: "감사 로그가 디스크 하나에만 있다".

길이는 두 쪽 안쪽. 완성 예시는 과제 마감 뒤 `docs/session7/examples/` 에 올립니다.

## 선택. 런북 시나리오 하나 — 15분

`docs/templates/runbook.md` 를 `docs/runbook.md` 로 복사하고 **공통 표와 시나리오 1(Qdrant 가 죽었다)** 만 채웁니다. 실제로 한 번 해 보고 적는 것이 좋습니다. `docker compose stop qdrant` 로 죽이고 `/health` 가 어떻게 되는지, `docker compose start qdrant` 로 살리고 `points` 가 돌아오는지. 재인덱싱 시간은 `make index-server` 를 재서 적습니다.

## 제출

**마감: 10월 14일(수) 밤.** 8회차(10월 15일 목 21:00)는 고객 readout 입니다. 오늘 잰 응답 시간 예산과 이 답변서가 발표의 운영 절입니다. 하루뿐이라 필수 1(결과 파일 커밋)은 수업 끝나고 바로 올리는 것이 좋습니다.

1. 서버를 끄고(`make api` 터미널에서 Ctrl+C, compose 는 `make compose-down`) `make check-s07` 가 5/5 인지 봅니다.
2. 커밋하고 자기 포크에 올립니다.

```bash
git add src/finrag/api/main.py src/finrag/api/sse.py results/api_bench.json results/check_s07.json docs/security_questionnaire.md
git commit -m "7회차 과제"
git push
```

3. 자기 포크 URL(`https://github.com/<계정>/finance-agentic-rag-s07`)을 디스코드에 올립니다. `.env` 와 `logs/` 는 커밋되지 않습니다(그렇게 되어 있습니다).

## check-s07 가 보는 것

| 항목 | 통과 기준 |
|---|---|
| /ask 응답 | 실제 그래프로 돌려 근거 · 기준일 · 정책 버전이 있다 |
| /ask/stream 이벤트 | node_start 와 done 이 있고 token 또는 citation 이 있다 |
| 응답 시간 측정 | `results/api_bench.json` 에 10문항 이상과 p95 |
| 감사 로그 | `logs/audit.jsonl` 이 열 줄 이상이고 질문 원문이 없다 |
| 보안 답변서 | `docs/security_questionnaire.md` 가 있고 빈칸(`____`)이 없다 |

## 8회차 전에 하나

8회차는 발표입니다. 5분 데모(질문 → 근거 인용 → 미답변 → 계산 → 스트림)와 readout 1쪽입니다. 템플릿은 `docs/templates/readout_1p.md` 에 이미 있습니다. 숫자는 전부 6·7회차 결과 파일에서 옵니다. 미리 읽어 두세요.
