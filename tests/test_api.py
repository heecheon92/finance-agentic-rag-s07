# -*- coding: utf-8 -*-
"""7회차 실습 1·2 자기 확인 — api.main.ask, api.sse.stream_graph. 그리고 완성본 둘(인증 · 감사 로그).

LLM 도 Qdrant 도 부르지 않는다. 그래프 자리에 가짜 그래프를 끼운다(main._graph). 채우기 전에는
실습 1·2 의 테스트 열 개가 NotImplementedError 로 실패한다. 인증 · health 의 둘은 채우기 전에도 통과한다.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from finrag.api import audit, main, sse  # noqa: E402
from finrag.settings import get_settings  # noqa: E402

HITS = [{"chunk_id": f"hana_credit_terms_2013#제{i}조#1", "doc_id": "hana_credit_terms_2013",
         "doc_type": "약관", "issuer": "하나은행", "article": f"제{i}조", "article_title": "기한의 이익 상실",
         "page_start": i, "effective_from": "2013-07-01", "review_expiry": "2014-06-30",
         "expired": i == 1, "text": "가" * 500, "rerank_score": 1.0 / i} for i in range(1, 11)]
STATE = {"answer": "제7조에 따르면 기한의 이익은 …", "hits": HITS,
         "notices": ["AI 가 생성한 답변입니다. 확정 전 원문을 확인하세요."],
         "abstained": False, "retry_count": 1, "grade": "sufficient",
         "trace": ["preprocess", "rewrite", "selfquery", "retrieve", "grade", "answer"]}
KEY = {"X-API-Key": get_settings().api_key}
Q = {"question": "하나은행 여신거래기본약관 제7조 기한의 이익 상실 사유는?"}


class Msg:
    """AIMessageChunk 흉내. content 만 있으면 된다."""
    def __init__(self, content: str):
        self.content = content


class FakeGraph:
    """invoke 는 고정 상태를, astream 은 정해진 순서의 (mode, chunk) 를 흘린다."""
    def __init__(self, state: dict | None = None, fail: bool = False):
        self.state = dict(state or STATE)
        self.fail = fail

    def invoke(self, state, config=None):
        return dict(self.state)

    async def astream(self, state, stream_mode=None):
        yield "updates", {"preprocess": {"masked_question": state["question"]}}
        yield "updates", {"rewrite": {"query": "기한의 이익 상실 사유"}}
        yield "messages", (Msg("기한의 이익 상실 사유"), {"langgraph_node": "rewrite"})   # 흘리면 안 되는 토큰
        yield "updates", {"retrieve": {"hits": self.state["hits"]}}
        yield "messages", (Msg('{"verdict":"sufficient"}'), {"langgraph_node": "grade"})  # 이것도
        yield "updates", {"grade": {"grade": "sufficient"}}
        yield "messages", (Msg("제7조에 "), {"langgraph_node": "answer"})
        yield "messages", (Msg("따르면"), {"langgraph_node": "answer"})
        if self.fail:
            raise RuntimeError("LLM 호출 실패")
        yield "updates", {"answer": {"answer": "제7조에 따르면", "abstained": False,
                                     "notices": self.state["notices"]}}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "_graph", FakeGraph())
    monkeypatch.setattr(main.qdrant, "count", lambda: 3700)
    monkeypatch.setattr(audit, "log_path", lambda: tmp_path / "audit.jsonl")
    return TestClient(main.app), tmp_path / "audit.jsonl"


# ── 완성본. 채우기 전에도 통과 ───────────────────────────────────────
def test_health_reports_collection_and_policy(client):
    c, _ = client
    d = c.get("/health").json()
    assert d["status"] == "ok" and d["points"] == 3700 and d["policy_version"]


def test_wrong_key_is_401_before_the_graph_runs(client):
    c, _ = client
    r = c.post("/ask", json=Q, headers={"X-API-Key": "wrong"})
    assert r.status_code == 401
    assert "키" in r.json()["detail"]


# ── 실습 1 · main.ask ─────────────────────────────────────────────
def test_ask_returns_answer_and_top8_sources(client):
    c, _ = client
    r = c.post("/ask", json=Q, headers=KEY)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["answer"].startswith("제7조")
    assert len(d["sources"]) == 8, "근거는 상위 8개만"
    assert d["sources"][0]["chunk_id"] == "hana_credit_terms_2013#제1조#1"
    assert len(d["sources"][0]["excerpt"]) <= 300, "발췌는 300자"
    assert d["sources"][0]["expired"] is True and d["sources"][1]["expired"] is False
    assert d["sources"][0]["effective_from"] == "2013-07-01"


def test_ask_basis_date_is_today_unless_as_of_given(client):
    c, _ = client
    assert c.post("/ask", json=Q, headers=KEY).json()["basis_date"] == date.today().isoformat()
    d = c.post("/ask", json={**Q, "as_of": "2013-07-01"}, headers=KEY).json()
    assert d["basis_date"] == "2013-07-01"


def test_ask_carries_notices_policy_version_request_id(client):
    c, _ = client
    d = c.post("/ask", json=Q, headers=KEY).json()
    assert d["notices"] == STATE["notices"]
    assert d["policy_version"] and d["ai_generated"] is True
    assert len(d["request_id"]) == 12
    assert d["retry_count"] == 1 and d["latency_ms"] >= 0
    assert d["abstained"] is False and d["abstain_reason"] == ""


def test_ask_reports_abstained_state(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(main, "_graph", FakeGraph({**STATE, "answer": "근거를 찾지 못했습니다", "abstained": True,
                                                   "abstain_reason": "근거를 찾지 못했습니다", "hits": []}))
    d = c.post("/ask", json=Q, headers=KEY).json()
    assert d["abstained"] is True
    assert d["abstain_reason"] == "근거를 찾지 못했습니다"
    assert d["sources"] == []


def test_ask_writes_one_audit_line_without_the_raw_question(client):
    c, log = client
    d = c.post("/ask", json=Q, headers=KEY).json()
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, "요청 하나에 로그 한 줄"
    rec = json.loads(lines[0])
    assert rec["request_id"] == d["request_id"]
    assert "question" not in rec and len(rec["question_sha256"]) == 64, "원문은 남기지 않는다"
    assert rec["cited_chunk_ids"][0] == "hana_credit_terms_2013#제1조#1"
    assert rec["api_key_id"] != get_settings().api_key and len(rec["api_key_id"]) == 12
    assert rec["policy_version"] == d["policy_version"]


# ── 실습 2 · sse.stream_graph ────────────────────────────────────
def events(graph) -> list[tuple[str, object]]:
    async def run():
        out = []
        async for ev in sse.stream_graph(graph, {"question": Q["question"]}, request_id="r1"):
            out.append((ev["event"], json.loads(ev["data"])))
        return out
    return asyncio.run(run())


def test_stream_node_start_once_per_node_in_order():
    ev = events(FakeGraph())
    starts = [d["node"] for k, d in ev if k == "node_start"]
    assert starts == ["preprocess", "rewrite", "retrieve", "grade", "answer"]


def test_stream_forwards_only_answer_tokens():
    ev = events(FakeGraph())
    assert [d["text"] for k, d in ev if k == "token"] == ["제7조에 ", "따르면"]


def test_stream_answer_badge_comes_before_its_first_token():
    kinds = [(k, d.get("node") if k == "node_start" else None) for k, d in events(FakeGraph())]
    i_start = kinds.index(("node_start", "answer"))
    i_tok = next(i for i, (k, _) in enumerate(kinds) if k == "token")
    assert i_start < i_tok, "답변 노드의 토큰은 updates 보다 먼저 온다. node_start 를 먼저 보낸다"


def test_stream_sends_citation_with_top8():
    cites = [d for k, d in events(FakeGraph()) if k == "citation"]
    assert len(cites) == 1 and len(cites[0]) == 8
    assert set(cites[0][0]) >= {"chunk_id", "doc_id", "article", "page_start"}


def test_stream_ends_with_done_or_error():
    ev = events(FakeGraph())
    k, d = ev[-1]
    assert k == "done" and d["request_id"] == "r1" and d["answer"] == "제7조에 따르면" and d["abstained"] is False
    k2, d2 = events(FakeGraph(fail=True))[-1]
    assert k2 == "error" and "RuntimeError" in d2["message"]
