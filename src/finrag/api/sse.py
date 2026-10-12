# -*- coding: utf-8 -*-
"""SSE 이벤트 — 7회차 실습 2.

LangGraph 의 astream 은 노드 실행(updates)과 토큰(messages)을 함께 흘려보낸다. 그대로 클라이언트에
주면 rewrite · grade 노드가 만드는 토큰까지 화면에 찍힌다. 답변 노드(answer · abstain)의 토큰만 골라낸다.

이벤트 다섯: node_start(노드가 처음 시작될 때 한 번) | citation(hits 가 생겼을 때, 상위 8개) |
token(답변 노드의 글자) | done(끝. request_id · answer · abstained · notices) | error(스트림 중 예외)
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

ANSWER_NODES = {"answer", "abstain"}


def event(kind: str, data: Any) -> dict:
    return {"event": kind, "data": json.dumps(data, ensure_ascii=False)}


async def stream_graph(graph, state: dict, *, request_id: str) -> AsyncIterator[dict]:
    """실습 2. graph.astream(state, stream_mode=["updates", "messages"]) 를 이벤트로 바꾼다.

    - updates 모드: {노드이름: 바뀐 키들}. 노드가 처음 나오면 node_start 를 한 번만 보낸다(seen_nodes).
      바뀐 키에 hits 가 있으면 citation(chunk_id · doc_id · article · page_start, 상위 8개).
      바뀐 키는 final 에 모아 둔다. 마지막 done 이 여기서 answer · abstained · notices 를 읽는다.
    - messages 모드: (메시지 조각, 메타). 메타의 langgraph_node 가 ANSWER_NODES 에 있을 때만 token.
      답변 노드의 토큰은 그 노드의 updates 보다 먼저 도착하므로, 처음 보는 노드면 node_start 를 먼저 보낸다.
    - 끝에 done. 예외가 나면 error 이벤트(연결만 끊으면 클라이언트가 원인을 모른다).
    테스트는 tests/test_api.py 의 실습 2 다섯. 모두 가짜 그래프라 LLM 없이 돈다.
    """
    raise NotImplementedError("7회차 실습 2: api.sse.stream_graph 를 채우세요. 모드 둘(updates · messages)과 이벤트 다섯은 독스트링, 요구사항은 tests/test_api.py 의 실습 2 다섯")
    yield  # noqa: E303 — 이 줄이 있어야 이 함수가 async generator 로 남는다. 지우지 말고 위의 raise 를 코드로 바꾼다
