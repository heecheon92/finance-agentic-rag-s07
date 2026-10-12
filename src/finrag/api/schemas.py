# -*- coding: utf-8 -*-
"""응답 스키마.

금융 답변은 "무엇을 답했는가"만큼 "무엇을 근거로, 어느 시점 기준으로 답했는가"가
중요하다. 그래서 답변 문자열만 돌려주지 않는다. 아래 필드는 감사·컴플라이언스
요구에서 나온 것이지 예쁘라고 넣은 것이 아니다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Source(BaseModel):
    chunk_id: str
    doc_id: str
    doc_type: str = ""
    issuer: str = ""
    article: str = ""
    article_title: str = ""
    page_start: int = 0
    effective_from: str = ""
    review_expiry: str = ""
    expired: bool = False
    synthetic_degraded: bool = False
    excerpt: str = ""
    score: float = 0.0


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    as_of: str | None = Field(None, description="기준일(YYYY-MM-DD). 없으면 오늘")
    stream: bool = False


class AskResponse(BaseModel):
    ai_generated: bool = True
    answer: str
    notices: list[str] = []
    basis_date: str
    sources: list[Source] = []
    abstained: bool = False
    abstain_reason: str = ""
    escalation_reason: str = ""
    policy_version: str = ""
    request_id: str = ""
    latency_ms: float = 0.0
    retry_count: int = 0
    usage: dict = {}          # 모델별 토큰. 요청 하나가 얼마인지는 여기서 계산한다(eval/cost.py)


class HealthResponse(BaseModel):
    status: str
    collection: str
    points: int
    llm: str
    policy_version: str
