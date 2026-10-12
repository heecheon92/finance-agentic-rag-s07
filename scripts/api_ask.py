#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API 에 질문 하나를 보내고 응답을 읽는다. `make ask` 의 HTTP 판.

    python scripts/api_ask.py "하나은행 여신거래기본약관 제7조 기한의 이익 상실 사유는?"
    python scripts/api_ask.py --stream "같은 질문"      # /ask/stream 의 이벤트를 오는 대로 찍는다
    python scripts/api_ask.py --json "같은 질문"        # 응답 JSON 전체
    python scripts/api_ask.py --key wrong "같은 질문"   # 401 을 본다

서버는 먼저 떠 있어야 한다(`make api` 또는 `docker compose up -d`). 주소는 --base 또는 API_BASE 환경변수.
키는 --key, API_KEY 환경변수, .env 의 API_KEY 순서로 찾는다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def api_key(explicit: str | None) -> str:
    if explicit:
        return explicit
    if os.getenv("API_KEY"):
        return os.environ["API_KEY"]
    from finrag.settings import get_settings
    return get_settings().api_key


def won(usage: dict) -> str:
    from finrag.eval import cost
    usd = cost.cost_usd(usage)
    return f"{usd * cost.USD_KRW:.1f}원 (${usd:.4f})" if usd else "0원 (토큰 없음)"


def print_response(d: dict) -> None:
    print(f"request_id  {d.get('request_id')}   정책 {d.get('policy_version')}   기준일 {d.get('basis_date')}"
          f"   재검색 {d.get('retry_count', 0)}회   서버 {d.get('latency_ms', 0):,.0f}ms")
    u = d.get("usage") or {}
    if u:
        import re
        short = lambda m: re.sub(r"-\d{4}-\d{2}-\d{2}$", "", m.split(":")[-1].replace("gpt-5.4-", ""))  # nano · mini
        parts = [f"{short(m)} 입력 {v.get('input_tokens', 0):,} · 출력 {v.get('output_tokens', 0):,}" for m, v in u.items()]
        print(f"토큰        {' / '.join(parts)}   → {won(u)}")
    src = d.get("sources") or []
    print(f"근거 ({len(src)})")
    for i, h in enumerate(src[:8], start=1):
        tags = " ".join(t for t in (("심의필 만료" if h.get("expired") else ""), ("열화 재현본" if h.get("synthetic_degraded") else "")) if t)
        print(f"  [{i}] {h.get('doc_id')} {h.get('article') or '-'} p{h.get('page_start')}  시행 {h.get('effective_from') or '-'}"
              f"  {tags}  {' '.join((h.get('excerpt') or '').split())[:50]}")
    for n in d.get("notices") or []:
        print(f"고지        {n}")
    if d.get("escalation_reason"):
        print(f"에스컬레이션  {d['escalation_reason']}")
    print(f"\n{'거절' if d.get('abstained') else '답변'}\n{d.get('answer', '')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--base", default=os.getenv("API_BASE", "http://localhost:8000"))
    ap.add_argument("--key", default=None)
    ap.add_argument("--as-of", default=None, help="기준일 YYYY-MM-DD. 없으면 서버가 오늘로")
    ap.add_argument("--stream", action="store_true", help="/ask/stream 으로. 이벤트를 오는 대로 찍는다")
    ap.add_argument("--json", action="store_true", help="응답 JSON 전체")
    args = ap.parse_args()

    headers = {"X-API-Key": api_key(args.key)}
    body = {"question": args.question, "as_of": args.as_of}

    if not args.stream:
        t0 = time.perf_counter()
        try:
            r = httpx.post(f"{args.base}/ask", json=body, headers=headers, timeout=300)
        except httpx.ConnectError:
            print(f"{args.base} 에 연결할 수 없습니다. 먼저 `make api` 또는 `docker compose up -d`."); return 1
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code != 200:
            print(f"HTTP {r.status_code}  {r.text[:200]}"); return 1
        d = r.json()
        if args.json:
            print(json.dumps(d, ensure_ascii=False, indent=1)); return 0
        print_response(d)
        print(f"\n왕복 {ms:,.0f}ms (서버 {d.get('latency_ms', 0):,.0f}ms + 전송)")
        return 0

    # 스트림. 줄 단위로 읽어 event: / data: 를 짝지어 찍는다. UI(ui/index.html)가 하는 일과 같다.
    t0 = time.perf_counter(); ev = None; n_tok = 0; first_tok = None
    try:
        with httpx.stream("POST", f"{args.base}/ask/stream", json=body, headers=headers, timeout=300) as r:
            if r.status_code != 200:
                print(f"HTTP {r.status_code}"); return 1
            for line in r.iter_lines():
                if line.startswith("event:"):
                    ev = line[6:].strip()
                elif line.startswith("data:"):
                    d = json.loads(line[5:].strip() or "{}")
                    el = (time.perf_counter() - t0) * 1000
                    if ev == "node_start":
                        if n_tok:
                            print()
                        print(f"[{el:6,.0f}ms] node_start  {d.get('node')}")
                    elif ev == "citation":
                        print(f"[{el:6,.0f}ms] citation    근거 {len(d)}개  첫째 {d[0].get('doc_id') if d else '-'} {d[0].get('article') if d else ''}")
                    elif ev == "token":
                        if first_tok is None:
                            first_tok = el
                            print(f"[{el:6,.0f}ms] token       첫 글자. 여기부터 화면에 글자가 흐른다")
                        n_tok += 1
                        sys.stdout.write(d.get("text", "")); sys.stdout.flush()
                    elif ev == "done":
                        print(f"\n[{el:6,.0f}ms] done        request_id {d.get('request_id')}  거절 {d.get('abstained')}  고지 {len(d.get('notices') or [])}개  토큰 조각 {n_tok}개")
                    elif ev == "error":
                        print(f"\n[{el:6,.0f}ms] error       {d.get('message')}")
    except httpx.ConnectError:
        print(f"{args.base} 에 연결할 수 없습니다. 먼저 `make api` 또는 `docker compose up -d`."); return 1
    except httpx.RemoteProtocolError:
        print("\n서버가 스트림을 중간에 끊었습니다. 서버 터미널의 마지막 에러를 보세요. 코드를 바꿨으면 서버를 다시 띄웁니다."); return 1
    if first_tok is not None:
        print(f"첫 글자까지 {first_tok:,.0f}ms. /ask 는 끝날 때까지 빈 화면이고, 스트림은 이 시점부터 보인다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
