# 약관부터 답변까지 — 7회차

금융 문서 특화 Agentic RAG 수업의 7회차 레포지토리입니다. 6회차 레포지토리(finance-agentic-rag-s06)와는 별개이고 새로 받습니다. 1~6회차 내용은 그대로 들어 있고, 6회차에 채운 자리 둘(`metrics.aggregate`, `judge.agreement`)은 **강사가 작성한 코드로 채워져** 있습니다. 자기 코드로 바꿔 써도 됩니다.

## 7회차에 할 일

1. 설치합니다. 6회차 폴더에서 문서·청크·모델·결과 파일·`.env` 를 복사하고 새 패키지 다섯을 설치합니다. Docker 이미지는 수업 전날 밤에 빌드합니다. → [docs/install.md](docs/install.md)
2. 수업 앞부분은 API 뼈대(`src/finrag/api/`)를 읽고, 채울 자리 둘(`main.ask`, `sse.stream_graph`)을 채웁니다. `make api` 로 서버를 띄우고 `make api-ask` · `make api-stream` 으로 응답과 스트림을 봅니다. → [docs/session7/lab.md](docs/session7/lab.md)
3. 수업 뒷부분은 인증·호출 제한·감사 로그(완성본)를 읽고, `make api-bench` 로 응답 시간 예산을 재고, `make compose-up` 으로 셋(Qdrant · API · UI)을 한 줄로 띄웁니다.
4. 과제는 필수 둘(결과 파일 커밋, 보안 질의서 답변서)에 선택 하나(런북 시나리오 1)이고, `make check-s07` 가 5/5 이면 끝입니다. → [docs/session7/homework.md](docs/session7/homework.md)

## 폴더

| 폴더 | 무엇 |
|---|---|
| `docs/install.md` | 설치. 6회차 폴더에서 복사하는 단계와 Docker 빌드 |
| `docs/session7/` | 실습 순서(lab.md)와 과제(homework.md) |
| `docs/templates/security_questionnaire.md`, `runbook.md` | 과제 템플릿. `docs/` 로 복사해 채웁니다 |
| `docs/session6/examples/` | 6회차 과제(ROI 1쪽 · 평가 리포트)의 강사 완성본 |
| `src/finrag/api/main.py` | FastAPI 앱. 라우트 셋. 채울 것 `ask`(실습 1)가 여기 있습니다 |
| `src/finrag/api/sse.py` | 스트림 이벤트. 채울 것 `stream_graph`(실습 2) |
| `src/finrag/api/schemas.py`, `auth.py`, `audit.py` | 응답 모양, 키 확인, 감사 로그. 읽기만 합니다 |
| `ui/index.html`, `ui/nginx.conf` | UI 한 쪽과 nginx 프록시 설정(스트리밍은 버퍼링을 끈다) |
| `Dockerfile`, `docker-compose.yml` | api 이미지와 셋(qdrant · api · ui)의 구성 |
| `scripts/api_ask.py`, `api_bench.py` | HTTP 클라이언트와 응답 시간 측정 |
| `scripts/locustfile.py` | 부하 테스트(선택). mock LLM 프로파일 |
| `tests/test_api.py` | 채운 것이 맞는지 보는 테스트 12개. LLM 없이 가짜 그래프로 돕니다 |
| `scripts/check_session.py` | 7회차 확인. 결과 파일이 제출물입니다 |

## 명령

```bash
make setup            # 패키지 설치. 6회차 폴더가 있으면 1~2분
make index            # 청크를 Qdrant(임베디드)에 넣는다. 10초
make test             # 자동 채점. 2~6회차 116개 + 7회차 12개. 채우기 전에는 10개 실패가 정상입니다
make api              # API 서버. http://localhost:8000 (두 번째 터미널에서)
make api-ask Q="질문"  # /ask 에 질문 하나
make api-stream Q="질문"  # /ask/stream 의 이벤트를 오는 대로
make api-bench        # 10문항 응답 시간 · 비용 → results/api_bench.json (약 3분)
make check-s07        # 7회차 확인 → results/check_s07.json
make compose-build    # api 이미지 빌드 (수업 전날, 5~15분)
make index-server     # compose 의 Qdrant 에 인덱스 (서버 모드)
make compose-up       # qdrant · api · ui → http://localhost:8080
make compose-down     # 내린다
```

6회차까지의 명령(`make compare`, `make judge`, `make ask` 등)도 그대로 있습니다. `make help`.
