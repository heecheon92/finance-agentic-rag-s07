# -*- coding: utf-8 -*-
"""감사 로그.

금융 서비스에서 "그때 그 답변이 무엇을 근거로 나왔는가"를 재구성할 수 있어야 한다.
질의 원문은 남기지 않고 해시만 남긴다(개인정보가 섞여 들어올 수 있다).
추가 전용(append-only) JSONL 이라 수정 이력이 남지 않는 것이 오히려 요건이다.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from ..settings import get_settings

_lock = threading.Lock()


def log_path() -> Path:
    p = get_settings().root / "logs" / "audit.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write(*, request_id: str, api_key_id: str, question: str, response: dict,
          model: str, policy_version: str, latency_ms: float,
          usage: dict | None = None) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "request_id": request_id,
        "api_key_id": api_key_id,
        "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
        "question_len": len(question),
        "cited_chunk_ids": [s["chunk_id"] for s in response.get("sources", [])],
        "cited_doc_ids": sorted({s["doc_id"] for s in response.get("sources", [])}),
        "abstained": response.get("abstained", False),
        "abstain_reason": response.get("abstain_reason", ""),
        "escalation_reason": response.get("escalation_reason", ""),
        "model": model,
        "policy_version": policy_version,
        "latency_ms": latency_ms,
        "usage": usage or {},
    }
    with _lock, log_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
