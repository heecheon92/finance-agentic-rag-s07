# -*- coding: utf-8 -*-
"""부하 테스트.

기본은 mock LLM 프로파일이다. 실 LLM 으로 부하를 걸면 비용이 나가고 429 를 맞는다.
"어디가 느린가"를 보려는 것이지 "OpenAI 가 견디는가"를 보려는 게 아니다.

    locust -f scripts/locustfile.py --host http://localhost:8000
    LLM_MODEL_MAIN=fake locust -f scripts/locustfile.py --headless -u 5 -r 1 -t 60s
"""
from __future__ import annotations

import os
import random

from locust import HttpUser, between, task

API_KEY = os.getenv("API_KEY", "change-me")

QUESTIONS = [
    "하나은행 여신거래기본약관 제7조 기한이익 상실 통지는 며칠 전까지인가요?",
    "장병내일준비적금을 7개월 만에 해지하면 중도해지이자율은?",
    "카카오뱅크 정기예금의 최소 가입금액은?",
    "KB국민카드 리볼빙 수수료율은 몇 %인가요?",
    "실손보험 통원 치료 시 공제금액은 어떻게 정해지나요?",
    "iM뱅크 가계대출은 만기까지 얼마 남으면 중도상환수수료가 면제되나요?",
]


class AskUser(HttpUser):
    wait_time = between(1, 3)

    @task(4)
    def ask(self):
        self.client.post("/ask", json={"question": random.choice(QUESTIONS)},
                         headers={"X-API-Key": API_KEY}, name="/ask")

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")
