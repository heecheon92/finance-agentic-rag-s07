.PHONY: api api-ask api-stream api-bench check-s07 index-server compose-build compose-up compose-down compose-logs help setup download models models-rerank embeddings notebook test compare judge judge-calibrate calc-e2e filter-accuracy roi gate-off compare-gate agentic-sample agentic adversarial graph ask ingest-sample ingest index baseline bm25-compare hybrid-norerank hybrid rerank-sweep chunk chunk-sample profile
PY := .venv/bin/python
export HF_HOME := ./models
EMB_URL := https://github.com/hyeonsikseo/finance-agentic-rag-s03/releases/download/s03/BAAI_bge-m3.npz
SAMPLE := --only hana_credit_terms_2009 --only fss_deposit_terms_2024_pdf --only knia_3500_scan --only kakao_deposit_terms_2024 --only hanacard_std_2017 --only law_silson_std_hwp

help:
	@echo "make setup           파이썬 3.12 와 패키지 설치 (5회차 폴더가 있으면 1분)"
	@echo "make api             API 서버를 띄운다 (http://localhost:8000, 모델 적재 25초). 끄려면 Ctrl+C"
	@echo "make api-ask Q=\"질문\"  /ask 에 질문 하나 → 근거 · 고지 · 답변 · 토큰 (서버가 떠 있어야)"
	@echo "make api-stream Q=\"질문\"  /ask/stream 의 이벤트를 오는 대로"
	@echo "make api-bench       답할 수 있는 10문항을 /ask 로 → 평균 · p95 · 문항당 비용 → results/api_bench.json (약 3분)"
	@echo "make check-s07       7회차 확인 → results/check_s07.json (이 파일을 제출)"
	@echo "make compose-build   api 이미지 빌드 (수업 전날. 5~15분)"
	@echo "make index-server    compose 의 Qdrant 에 인덱스 넣기 (서버 모드, 10초)"
	@echo "make compose-up      qdrant · api · ui 셋을 띄운다 → http://localhost:8080"
	@echo "make compose-down    셋을 내린다"
	@echo "--- 6회차 명령 ---"
	@echo "make notebook        평가 노트북 열기 (수업 1~2부)"
	@echo "make test            자동 채점. 2~5회차 102개 + 6회차 검사 14개 (채우기 전에는 실패가 정상)"
	@echo "make compare         결과 파일 셋(baseline · hybrid · agentic)을 한 표로 → results/compare.csv (실습 1 뒤)"
	@echo "make judge           자기 답변 20문항을 LLM-as-Judge 로 채점 → results/judge.json (1~2분)"
	@echo "make judge-calibrate 강사 답변 17개를 같은 judge 로 채점해 강사 라벨과 일치도 → results/judge_calibration.json (1~2분)"
	@echo "make calc-e2e        계산 골든셋 15문항을 에이전트로 → results/calc_e2e.json (약 5분. 휴식에)"
	@echo "make filter-accuracy Self-Query 필터 정확도 → results/filter_accuracy.json (1초)"
	@echo "make roi             토큰 → 문항당 비용 → 월 비용 · 3년 TCO → results/roi.json (1초)"
	@echo "make check-s06       6회차 확인 → results/check_s06.json (이 파일을 제출)"
	@echo "--- 강사 시연 · 선택 ---"
	@echo "make gate-off        검증 게이트를 끈 청크와 Qdrant 컬렉션을 만든다 (임베딩 10~25분)"
	@echo "make compare-gate    게이트 ON/OFF Recall 비교 → results/gate_comparison.json"
	@echo "--- 5회차 명령. 그대로 남겨 둡니다 ---"
	@echo "make agentic         40문항 전부 → results/agentic.json (약 12분)"
	@echo "make adversarial     적대적 5문항 → results/adversarial.json (1분)"
	@echo "make ask Q=\"질문\"    질문 하나를 에이전트에 넣고 경로·판정·근거·답변을 본다"

setup:
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -r requirements.txt

download:
	$(PY) data/download_corpus.py

models:
	$(PY) scripts/pull_models.py --only embed

models-rerank:
	$(PY) scripts/pull_models.py --only rerank

embeddings:
	mkdir -p data/embeddings
	curl -L --fail -o data/embeddings/BAAI_bge-m3.npz $(EMB_URL)
	@ls -la data/embeddings/BAAI_bge-m3.npz

notebook:
	$(PY) -m jupyter lab notebooks/s06_eval.ipynb

test:
	$(PY) -m pytest -q

# ── 7회차 명령 ──
api:
	$(PY) -m uvicorn finrag.api.main:app --host 0.0.0.0 --port 8000 --app-dir src

api-ask:
	$(PY) scripts/api_ask.py "$(Q)"

api-stream:
	$(PY) scripts/api_ask.py --stream "$(Q)"

api-bench:
	$(PY) scripts/api_bench.py $(if $(N),--n $(N),)

check-s07:
	$(PY) scripts/check_session.py 7

index-server:
	QDRANT_URL=http://localhost:6333 $(PY) scripts/build_index.py

compose-build:
	docker compose build

compose-up:
	docker compose up -d && docker compose ps

compose-down:
	docker compose down

compose-logs:
	docker compose logs -f api

# ── 6회차 명령 ──

compare:
	$(PY) -c "import sys;sys.path.insert(0,'src');from finrag.eval import report;sys.exit(report.main())"

judge:
	$(PY) scripts/judge_run.py

judge-calibrate:
	$(PY) scripts/judge_run.py --calibrate

calc-e2e:
	$(PY) scripts/calc_e2e.py

filter-accuracy:
	$(PY) scripts/filter_accuracy.py

roi:
	$(PY) scripts/roi.py

gate-off:
	$(PY) -c "import sys;sys.path.insert(0,'scripts');sys.path.insert(0,'src');import make_snapshot as m;m.build_gate_off_chunks()"
	$(PY) scripts/build_index.py --chunks data/chunks/chunks_gate_off.jsonl --collection finrag_gate_off

compare-gate:
	$(PY) scripts/compare_gate.py

check-s%:
	$(PY) scripts/check_session.py $*

# ── 5회차 명령. 그대로 남겨 둡니다 ──

ask:
	$(PY) scripts/ask.py "$(Q)"

graph:
	$(PY) scripts/agent_graph.py

agentic-sample:
	$(PY) pipelines/agentic.py --limit 10 --verbose

agentic:
	$(PY) pipelines/agentic.py --verbose

adversarial:
	$(PY) scripts/adversarial_run.py

# ── 4회차 명령 ──

bm25-compare:
	$(PY) scripts/bm25_compare.py

hybrid-norerank:
	$(PY) pipelines/hybrid.py --no-rerank

hybrid:
	$(PY) pipelines/hybrid.py

rerank-sweep:
	$(PY) scripts/rerank_sweep.py

# ── 3회차 명령 ──
ingest-sample:
	$(PY) pipelines/ingest.py --no-checkpoint $(SAMPLE)

ingest:
	$(PY) pipelines/ingest.py

index:
	$(PY) scripts/build_index.py

baseline:
	$(PY) pipelines/baseline.py

# ── 2회차 명령 ──
chunk-sample:
	$(PY) pipelines/chunk_only.py --verbose $(SAMPLE)

chunk:
	$(PY) pipelines/chunk_only.py --verbose

profile:
	$(PY) scripts/profile_docs.py
