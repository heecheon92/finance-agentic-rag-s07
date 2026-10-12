# 운영 런북 (템플릿)

> 장애가 났을 때 **읽으면서 따라 할 수 있는** 문서. 설명이 아니라 절차를 쓴다.
> 각 시나리오는 "어떻게 아는가 → 무엇을 하는가 → 어떻게 확인하는가" 순서로만 쓴다.

## 공통

| 항목 | 값 |
|---|---|
| 담당 | ____________ |
| 에스컬레이션 | ____________ |
| 대시보드 | ____________ |
| 로그 | `logs/audit.jsonl` (추가 전용) |
| 헬스체크 | `curl -s localhost:8000/health` |

---

## 시나리오 1. Qdrant 가 죽었다

**어떻게 아는가**
- `/health` 가 `points: 0` 이거나 500
- API 로그에 `ConnectionError` / `ResponseHandlingException`

**무엇을 하는가**
1. `docker compose ps qdrant` — 컨테이너 상태 확인
2. `docker compose logs --tail 100 qdrant` — OOM 인지 디스크인지 본다
3. 재기동: `docker compose restart qdrant`
4. 데이터가 날아갔으면 스냅샷 복원:
   ```bash
   # 서버 모드
   curl -X POST "localhost:6333/collections/finrag/snapshots/upload" -F "snapshot=@finrag.snapshot"
   # 임베디드 모드
   unzip -o data/qdrant_snapshot.zip -d data/qdrant_local
   ```
5. 그래도 안 되면 재인덱싱: `make ingest && make index` (임베딩 약 ____분)

**어떻게 확인하는가**
- `/health` 의 `points` 가 ____ 이상
- 표준 질문 1개로 `/ask` 응답에 `sources` 가 있는지

**미리 정해 둘 것**: 재인덱싱에 걸리는 시간(실측 ____분)을 알고 있어야 "지금 복원할지
재인덱싱할지"를 결정할 수 있다.

---

## 시나리오 2. LLM 쿼터 소진 또는 장애

**어떻게 아는가**
- 429 / 5xx 가 연속으로 뜬다
- 감사 로그에서 `abstained: true` 비율이 갑자기 올라간다

**무엇을 하는가 (성능 저하 운전)**
1. 즉시: `.env` 의 `LLM_MODEL_MAIN` 을 작은 모델로 내린다 → API 재기동
2. 그래도 안 되면 로컬 모델로: `LLM_MODEL_MAIN=ollama:qwen3:8b`
3. 최후: **검색 전용 모드**. 답변 생성 없이 근거 조항만 반환한다.
   (`.env` 에 `LLM_MODEL_MAIN=fake` — 가짜 모델이 검색 결과만 그대로 낸다)
4. 공지 문구: "현재 AI 답변 생성이 제한되어 관련 조항만 안내합니다."

**어떻게 확인하는가**
- `/ask` 가 200 이고 `sources` 가 채워지는가
- 답변이 없어도 서비스가 죽지 않는가

**정해 둘 것**: 어느 단계에서 사람에게 넘길 것인가 → ____________

---

## 시나리오 3. 약관 개정판이 나왔다

**어떻게 아는가**
- `python data/download_corpus.py` 가 `changed` 를 보고한다
- 실제로 겪은 예: 삼성화재 부동산담보대출 설명서 2026-08-24 갱신

**무엇을 하는가**
1. 무엇이 바뀌었는지 먼저 본다: `data/download_report.json` 의 `changed` 목록
2. 해당 문서만 다시 인제스천:
   `python pipelines/ingest.py --only <doc_id>` → 청크 ID 가 바뀌는지 확인
3. **골든셋이 깨지지 않는지 먼저 본다**: `make validate-golden`
   - 인용문이 사라졌다면 그 조항이 개정된 것이다. 문항을 고치기 전에 **무엇이 바뀌었는지**
     기록한다(그것이 고객에게 알려야 할 변화다).
4. 재인덱싱: `make index`
5. 구판을 지우지 않는다. `effective_from` 이 다른 판본으로 함께 두고, Self-Query 가
   기준일로 고르게 한다. "2013년 기준으로는?" 같은 질문이 실제로 온다.
6. 매니페스트의 `sha256` 갱신: `python data/download_corpus.py --update-hashes`

**어떻게 확인하는가**
- `make validate-golden` 통과
- 개정 조항을 묻는 질문에 새 판본이 인용되는가
- 과거 기준일 질문에 구판이 인용되는가

**정해 둘 것**: 개정 확인 주기 ____ / 알림 방법 ____________

---

## 부록. 자주 나오는 에러

| 증상 | 원인 | 대응 |
|---|---|---|
| CPU 0% 로 멈춤 | tokenizers 병렬화 교착 | `TOKENIZERS_PARALLELISM=false` (코드에 기본 적용됨) |
| `sys.meta_path is None` | qdrant 임베디드 종료 순서 | 무시해도 되나 `qdrant.close()` 로 방지 |
| 모델 로드 실패 | `HF_HOME` 미설정 | `export HF_HOME=./models` |
| 폐쇄망에서 모델 로드 실패 | 허브 접속 시도 | `HF_HUB_OFFLINE=1` |
