#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API 응답 시간 측정. 골든셋 문항을 /ask 로 보내 지연과 비용을 잰다 → results/api_bench.json

    python scripts/api_bench.py                 # 답할 수 있는 문항 앞 10개
    python scripts/api_bench.py --n 20
    python scripts/api_bench.py --ids S01,S09,S20

첫 호출은 따로 센다(콜드 스타트). 서버를 막 띄웠으면 첫 요청에 모델 적재 25초가 들어간다. 그 한 건이
평균을 대표하지 않으므로 cold_start_ms 로 적고 평균 · p95 에서는 뺀다. 6회차 agentic.json 의 p95 가
있으면 "예산" 으로 나란히 찍는다. 6회차는 그래프만 잰 시간이고 오늘은 HTTP 왕복까지 포함한 시간이다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def p95(xs: list[float]) -> float:
    if not xs:
        return 0.0
    return sorted(xs)[max(int(len(xs) * 0.95) - 1, 0)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--ids", default="")
    ap.add_argument("--base", default=os.getenv("API_BASE", "http://localhost:8000"))
    ap.add_argument("--no-warmup", action="store_true", help="첫 호출을 따로 세지 않는다")
    args = ap.parse_args()

    from finrag.eval import cost, harness
    from finrag.settings import get_settings
    s = get_settings()
    headers = {"X-API-Key": os.getenv("API_KEY", s.api_key)}

    seed, _ = harness.load_golden()
    want = [x.strip() for x in args.ids.split(",") if x.strip()]
    items = [it for it in seed if it["id"] in want] if want else [it for it in seed if it.get("answerable", True)][:args.n]
    if not items:
        print("문항이 없습니다."); return 1

    try:
        httpx.get(f"{args.base}/health", timeout=10).raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"{args.base} 가 응답하지 않습니다({type(e).__name__}). 먼저 `make api` 또는 `docker compose up -d`."); return 1

    cold = None
    if not args.no_warmup:
        t0 = time.perf_counter()
        httpx.post(f"{args.base}/ask", json={"question": items[0]["question"]}, headers=headers, timeout=600)
        cold = round((time.perf_counter() - t0) * 1000, 1)
        print(f"콜드 스타트(첫 호출, 집계에서 뺌)  {cold:,.0f}ms\n")

    rows = []
    print(f"{'id':5} {'유형':10} {'왕복ms':>8} {'서버ms':>8} {'재검색':>4} {'근거':>3} {'원':>6}  답/거절")
    for it in items:
        t0 = time.perf_counter()
        r = httpx.post(f"{args.base}/ask", json={"question": it["question"]}, headers=headers, timeout=600)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        if r.status_code != 200:
            rows.append({"id": it["id"], "type": it.get("type"), "status": r.status_code, "latency_ms": ms})
            print(f"{it['id']:5} {it.get('type', '')[:10]:10} {ms:8,.0f}  HTTP {r.status_code}")
            continue
        d = r.json()
        usd = cost.cost_usd(d.get("usage") or {})
        row = {"id": it["id"], "type": it.get("type"), "status": 200, "latency_ms": ms,
               "server_ms": d.get("latency_ms"), "retry_count": d.get("retry_count", 0),
               "n_sources": len(d.get("sources") or []), "abstained": bool(d.get("abstained")),
               "cost_krw": round(usd * cost.USD_KRW, 2), "request_id": d.get("request_id")}
        rows.append(row)
        print(f"{it['id']:5} {it.get('type', '')[:10]:10} {ms:8,.0f} {row['server_ms'] or 0:8,.0f} {row['retry_count']:4d} "
              f"{row['n_sources']:3d} {row['cost_krw']:6.1f}  {'거절' if row['abstained'] else '답변'}")

    ok = [r for r in rows if r["status"] == 200]
    lat = [r["latency_ms"] for r in ok]
    res = {"n": len(rows), "n_ok": len(ok), "base": args.base,
           "latency_ms_avg": round(sum(lat) / len(lat), 1) if lat else None,
           "latency_ms_p95": round(p95(lat), 1) if lat else None,
           "latency_ms_max": round(max(lat), 1) if lat else None,
           "cold_start_ms": cold,
           "abstained": sum(1 for r in ok if r["abstained"]),
           "retry_share": round(sum(1 for r in ok if r["retry_count"]) / len(ok), 3) if ok else None,
           "cost_krw_avg": round(sum(r["cost_krw"] for r in ok) / len(ok), 2) if ok else None,
           "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rows": rows}

    budget = None
    ag = s.results_dir / "agentic.json"
    if ag.exists():
        try:
            budget = json.loads(ag.read_text(encoding="utf-8"))["overall"].get("latency_ms_p95")
        except Exception:  # noqa: BLE001
            budget = None
    res["budget_p95_ms"] = budget

    print(f"\n[api_bench] {res['n_ok']}/{res['n']}문항  평균 {res['latency_ms_avg'] or 0:,.0f}ms  p95 {res['latency_ms_p95'] or 0:,.0f}ms"
          f"  최대 {res['latency_ms_max'] or 0:,.0f}ms  거절 {res['abstained']}  재검색한 문항 {res['retry_share'] or 0:.0%}  문항당 {res['cost_krw_avg'] or 0:.1f}원")
    if budget:
        inside = (res["latency_ms_p95"] or 0) <= budget
        print(f"6회차 agentic p95 {budget:,.0f}ms (results/agentic.json, 그래프만) → 오늘 p95 는 {'그 안' if inside else '그 밖'} (HTTP 왕복 포함)")
    out = s.results_dir / "api_bench.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("→", out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
