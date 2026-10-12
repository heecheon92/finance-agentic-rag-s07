#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""회차별 자동 확인.

    python scripts/check_session.py 3        →  results/check_s03.json

학생은 회차 끝에 이걸 돌려서 나온 JSON 을 커밋한다. 강사는 collect_results.py 로
6명분을 표로 모아 빨간 칸만 본다. 사람이 하나씩 열어 보는 일을 없애려는 장치다.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def ok(cond: bool, detail: str = "") -> dict:
    return {"ok": bool(cond), "detail": detail}


def _json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _lines(path: Path) -> int:
    try:
        return sum(1 for l in path.open(encoding="utf-8") if l.strip())
    except Exception:
        return 0


def check_s00() -> dict:
    """0회차. 판정 로직은 check_env.py 한 곳에만 두고 여기서는 불러 쓴다.

    같은 검사를 두 벌 유지하면 반드시 어긋난다. 예전 판정은 data/raw 파일 개수만 셌는데,
    bundled 문서는 data/bundled 로 가고 열화본은 raw 에 같이 있어서 개수가 맞아도
    빠진 문서가 있을 수 있었다.
    """
    import check_env as ce               # 같은 scripts/ 안에 있다

    env = ce.read_env_file(ROOT / ".env")
    corpus_status, corpus_detail = ce.check_corpus()
    model_status, model_detail = ce.check_models(env)

    report = _json(ROOT / "results" / "check_env.json")
    failed = [name for name, c in (report or {}).get("checks", {}).items()
              if c.get("required") and c.get("status") == "fail"]
    return {
        "환경 점검 실행": ok(report is not None,
                       "results/check_env.json" if report else
                       "없음 → python scripts/check_env.py 를 먼저 돌리세요"),
        "환경 점검 통과": ok(bool(report and report.get("required_ok")),
                       f"미통과: {', '.join(failed)}" if failed else
                       (report or {}).get("platform", "")),
        "코퍼스": ok(corpus_status == ce.OK, corpus_detail),
        "모델 캐시": ok(model_status == ce.OK, model_detail),
    }


# 디스커버리 노트에 반드시 있어야 하는 절. 템플릿의 제목과 같아야 한다.
DISCOVERY_SECTIONS = ["이해관계자", "현재 워크플로우", "성공 지표", "데이터와 망 제약",
                      "비범위", "리스크", "PoC 범위", "데이터 소싱", "SOW-lite"]
# 품질 분류표에서 학생이 판단해 채우는 열
QUALITY_JUDGED = ["형식분류", "수집상태", "처리방침", "우선순위", "근거"]


def check_s01() -> dict:
    # 1회차는 제출물이 없다(강사 시연 + 문서 살펴보기). 확인할 것이 없으므로 항상 통과한다.
    return {"1회차": ok(True, "제출물이 없습니다. 확인할 항목이 없습니다")}


# 청크 ID 는 {doc_id}#{조항}#{seq} 로 결정적이어야 한다. 같은 입력이면 같은 ID 가
# 나와야 골든셋의 gold_chunk_ids 가 다음 회차에도 그대로 가리킨다.
CHUNK_ID = re.compile(r"^[^#]+#[^#]*#\d+$")
GATE_VERDICTS = {"pass", "reparse", "ocr"}


def check_s02() -> dict:
    from finrag.settings import get_settings
    s = get_settings()
    path = s.chunks_dir / "chunks.jsonl"
    chunks = [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()] if path.exists() else []
    sample = chunks[:500]

    required = {"chunk_id", "doc_id", "text", "article", "page_start"}
    missing_fields = [c.get("chunk_id", "?") for c in sample if not required <= set(c)]
    meta_required = {"doc_type", "issuer", "effective_from", "parser", "validation"}
    missing_meta = [c.get("chunk_id", "?") for c in sample
                    if not meta_required <= set(c.get("meta", {}))]
    bad_verdict = [c.get("chunk_id", "?") for c in sample
                   if c.get("meta", {}).get("validation") not in GATE_VERDICTS]

    ids = [c["chunk_id"] for c in chunks if "chunk_id" in c]
    dup = len(ids) - len(set(ids))
    bad_id = [i for i in ids if not CHUNK_ID.match(i)]

    # 1회차 질문에 근거 청크를 붙였는가. 붙였다면 그 ID 가 실제로 존재해야 한다.
    q = s.golden_dir / "student_q.jsonl"
    qs = []
    if q.exists():
        for line in q.open(encoding="utf-8"):
            if line.strip():
                try:
                    qs.append(json.loads(line))
                except json.JSONDecodeError:
                    qs.append({})
    id_set = set(ids)
    with_gold = [r for r in qs if r.get("gold_chunk_ids")]
    dangling = [g for r in with_gold for g in r["gold_chunk_ids"] if g not in id_set]

    return {
        "청크 생성": ok(len(chunks) >= 1000, f"{len(chunks):,}개"),
        "청크 필수 필드": ok(not missing_fields,
                      f"누락 {len(missing_fields)}건: {', '.join(missing_fields[:2])}"
                      if missing_fields else f"{sorted(required)}"),
        "메타데이터 부착": ok(not missing_meta,
                       f"누락 {len(missing_meta)}건: {', '.join(missing_meta[:2])}"
                       if missing_meta else f"{sorted(meta_required)}"),
        "게이트 판정 기록": ok(bool(sample) and not bad_verdict,
                        f"판정 없는 청크 {len(bad_verdict)}건" if bad_verdict else
                        # 분포는 표본이 아니라 전체로 센다. 앞 500개는 대개 한 문서에서
                        # 나와 "reparse 500" 처럼 한쪽으로 쏠려 보인다.
                        ", ".join(f"{k} {v:,}" for k, v in sorted(
                            Counter(c.get("meta", {}).get("validation") for c in chunks).items()
                            if chunks else []))),
        "청크 ID 유일·형식": ok(dup == 0 and not bad_id,
                          f"중복 {dup}건 · 형식 위반 {len(bad_id)}건"),
        "질문에 근거 청크": ok(len(with_gold) >= 3 and not dangling,
                        f"{len(with_gold)}/{len(qs)}문항에 gold_chunk_ids"
                        + (f" · 없는 ID {len(dangling)}건" if dangling else "")),
    }


def _qdrant_points() -> tuple[int, str]:
    """포인트 수를 센다.

    임베디드 Qdrant 는 한 프로세스만 붙을 수 있다. API 서버가 떠 있으면 여기서
    잠금 오류가 난다. 그럴 때는 /health 로 물어본다. "API 를 끄고 다시 하세요"는
    답이 아니다 — 확인 스크립트는 서버가 떠 있든 아니든 돌아야 한다.
    """
    from finrag.index import qdrant
    try:
        return qdrant.count(), "직접 조회"
    except Exception as e:
        if "already accessed" not in str(e):
            return 0, f"오류: {type(e).__name__}"
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as r:
            return json.loads(r.read()).get("points", 0), "API /health 경유"
    except Exception:
        return 0, "임베디드 잠금 + API 미기동 (API 를 끄거나 켜고 다시 실행)"


def check_s03() -> dict:
    from finrag.settings import get_settings
    s = get_settings()
    rep = _json(s.data / "ingest_report.json") or {}
    res = _json(s.results_dir / "baseline.json") or {}
    points, how = _qdrant_points()

    routes = rep.get("routes", {})
    routed = sum(routes.values())
    verdicts = rep.get("verdicts", {})
    overall = res.get("overall", {})

    # ADR-002 는 3회차 과제다. 템플릿을 복사만 하고 빈칸(______)을 남겨 두면 안 낸 것이다.
    adr = s.root / "docs" / "adr" / "ADR-002-ingestion-graph.md"
    if not adr.exists():
        adr_ok = ok(False, "docs/adr/ADR-002-ingestion-graph.md 가 없다 (docs/templates/adr.md 를 복사해 채운다)")
    else:
        blanks = adr.read_text(encoding="utf-8").count("______")
        adr_ok = ok(blanks == 0, f"빈칸 {blanks}곳 남음" if blanks else f"{len(adr.read_text(encoding='utf-8')):,}자")

    # 코퍼스 전체를 돌렸는지 본다. 경로 합 = 문서 수만 보면 --only 로 1건만 돌려도
    # 통과한다(실제로 그렇게 통과했다).
    corpus = max(_lines(s.data / "documents.csv") - 1, 0)
    n_doc = rep.get("documents") or 0

    return {
        "인제스천 전체 처리": ok(routed == n_doc and corpus and n_doc >= corpus * 0.9,
                          f"문서 {n_doc}/{corpus}건 · 경로 합 {routed}"
                          + (f" · {routes}" if routes else "")
                          + ("  → --only 없이 전체를 돌리세요" if 0 < n_doc < corpus * 0.9 else "")),
        "게이트 3분기 동작": ok(len({v for v in verdicts if verdicts.get(v)}) >= 3,
                         f"{verdicts}" if verdicts else "판정 기록 없음"),
        "Qdrant 포인트": ok(points > 0, f"{points:,}개 ({how})"),
        "baseline Recall@5": ok(overall.get("recall@5") is not None,
                                f"{overall.get('recall@5')} (MRR {overall.get('mrr')})"),
        "유형별 분해": ok(len(res.get("by_type", {})) >= 5,
                     f"{len(res.get('by_type', {}))}개 유형"),
        "ADR-002": adr_ok,
    }


def check_s04() -> dict:
    from finrag.settings import get_settings
    s = get_settings()
    base = _json(s.results_dir / "baseline.json") or {}
    hyb = _json(s.results_dir / "hybrid.json") or {}
    # 리랭커가 실제로 사 주는 것은 "순서"다. Recall@5 는 이미 baseline 이 높아
    # 더 오를 자리가 없는 유형이 있다(조항번호형 baseline 100%). 그래서 순위 품질
    # 지표(MRR·Recall@1)로 판정한다. 통과시키려고 기준을 낮추는 게 아니라,
    # 애초에 그 지표가 이 단계가 개선하는 지표다.
    def m(res: dict, t: str, k: str):
        return res.get("by_type", {}).get(t, {}).get(k) if t else res.get("overall", {}).get(k)

    b_mrr, h_mrr = m(base, "조항번호형", "mrr"), m(hyb, "조항번호형", "mrr")
    b_all, h_all = m(base, "", "mrr"), m(hyb, "", "mrr")
    b_r1, h_r1 = m(base, "", "recall@1"), m(hyb, "", "recall@1")
    # ADR-003 은 4회차 과제다. 템플릿을 복사만 하고 빈칸(______)을 남겨 두면 안 낸 것이다.
    adr = s.root / "docs" / "adr" / "ADR-003-hybrid-retrieval.md"
    if not adr.exists():
        adr_ok = ok(False, "docs/adr/ADR-003-hybrid-retrieval.md 가 없다 (docs/templates/adr.md 를 복사해 채운다)")
    else:
        blanks = adr.read_text(encoding="utf-8").count("______")
        adr_ok = ok(blanks == 0, f"빈칸 {blanks}곳 남음" if blanks else f"{len(adr.read_text(encoding='utf-8')):,}자")
    return {
        "hybrid.json 존재": ok(bool(hyb), f"{hyb.get('n', 0)}문항"),
        "조항번호형 MRR ≥ baseline": ok(b_mrr is not None and h_mrr is not None and h_mrr >= b_mrr,
                                    f"baseline {b_mrr} → hybrid {h_mrr}"),
        "전체 MRR ≥ baseline": ok(b_all is not None and h_all is not None and h_all >= b_all,
                                f"{b_all} → {h_all}"),
        "전체 Recall@1 ≥ baseline": ok(b_r1 is not None and h_r1 is not None and h_r1 >= b_r1,
                                     f"{b_r1} → {h_r1}"),
        "리랭커 지연 기록": ok(any(r.get("latency_ms") for r in hyb.get("rows", [])),
                        f"평균 {hyb.get('overall', {}).get('latency_ms_avg')}ms"),
        "ADR-003": adr_ok,
    }


def check_s05() -> dict:
    from finrag.settings import get_settings
    s = get_settings()
    ag = _json(s.results_dir / "agentic.json") or {}
    adv = _json(s.results_dir / "adversarial.json") or {}
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "tests/test_calc_golden.py", "-q"],
                           cwd=ROOT, capture_output=True, timeout=300, text=True)
        tests_ok, detail = r.returncode == 0, r.stdout.strip().splitlines()[-1] if r.stdout else ""
    except Exception as e:
        tests_ok, detail = False, str(e)
    o = ag.get("overall", {})
    abst = o.get("abstain_accuracy")
    # 정책 1쪽은 5회차 과제다. 템플릿을 복사만 하고 빈칸(____)을 남겨 두면 안 낸 것이다.
    pol = ROOT / "docs" / "agent_policy.md"
    if not pol.exists():
        pol_ok = ok(False, "docs/agent_policy.md 가 없다 (docs/templates/agent_policy.md 를 복사해 채운다)")
    else:
        blanks = pol.read_text(encoding="utf-8").count("____")
        pol_ok = ok(blanks == 0, f"빈칸 {blanks}곳 남음" if blanks else f"{len(pol.read_text(encoding='utf-8')):,}자")
    return {
        "계산 골든 테스트": ok(tests_ok, detail),
        "agentic.json 존재": ok(ag.get("n", 0) >= 40, f"{ag.get('n', 0)}문항" + (" (가짜 모델)" if ag.get("llm") == "fake" else "")),
        "미답변형 거절 기록": ok(abst is not None,
                          f"미답변 정확도 {abst}, 오거절률 {o.get('false_refusal_rate')}, 답변률 {o.get('answer_rate')}"),
        "적대적 5문항 기록": ok(adv.get("n", 0) >= 5, f"통과 {adv.get('pass_rate')}" if adv else "results/adversarial.json 없음 (make adversarial)"),
        "에이전트 정책 문서": pol_ok,
    }


def check_s06() -> dict:
    from finrag.settings import get_settings
    s = get_settings()
    cmp_path = s.results_dir / "compare.csv"
    rows = list(cmp_path.open(encoding="utf-8")) if cmp_path.exists() else []
    header = rows[0].strip().split(",") if rows else []
    has_frr = any(",false_refusal_rate," in r for r in rows)
    has_abst = any(",abstain_accuracy," in r for r in rows)
    jd = _json(s.results_dir / "judge.json") or {}
    ce = _json(s.results_dir / "calc_e2e.json") or {}
    # ROI 1쪽은 6회차 과제다. 템플릿을 복사만 하고 빈칸(____)을 남겨 두면 안 낸 것이다.
    roi = ROOT / "docs" / "roi.md"
    if not roi.exists():
        roi_ok = ok(False, "docs/roi.md 가 없다 (docs/templates/roi.md 를 복사해 채운다)")
    else:
        blanks = roi.read_text(encoding="utf-8").count("____")
        roi_ok = ok(blanks == 0, f"빈칸 {blanks}곳 남음" if blanks else f"{len(roi.read_text(encoding='utf-8')):,}자")
    return {
        "3단계 비교표": ok(len(header) >= 5 and {"baseline", "hybrid", "agentic"} <= set(header),
                      f"열 {header}" if header else "results/compare.csv 없음 (make compare)"),
        "오거절률·미답변 정확도 행": ok(has_frr and has_abst,
                              "둘 다 있음" if has_frr and has_abst else "compare.csv 에 false_refusal_rate / abstain_accuracy 행이 없다"),
        "judge 20문항": ok(jd.get("n", 0) >= 20 and jd.get("llm") != "fake",
                        f"{jd.get('n', 0)}문항 평균 {jd.get('mean_total')}/6" + (" (가짜 모델)" if jd.get("llm") == "fake" else "")
                        if jd else "results/judge.json 없음 (make judge)"),
        "계산 정확도 기록": ok(ce.get("n", 0) >= 15, f"{ce.get('matched')}/{ce.get('n')} 맞음" if ce else "results/calc_e2e.json 없음 (make calc-e2e)"),
        "ROI 문서": roi_ok,
    }


def check_s07() -> dict:
    """7회차. 서버를 따로 띄우지 않고 앱을 프로세스 안에서 부른다(TestClient). 모델 적재 25초가 든다.

    수업 끝에는 4/5 가 정상이다. 보안 질의서 답변서(docs/security_questionnaire.md)가 과제다.
    """
    from finrag.settings import get_settings
    s = get_settings()
    out = {}
    # 1 · 2: /ask 와 /ask/stream 이 실제 그래프로 돈다. 실습 1 · 2 를 안 채웠으면 NotImplementedError.
    try:
        from fastapi.testclient import TestClient
        from finrag.api.main import app
        c = TestClient(app)
        q = {"question": "예금거래기본약관 제12조는 무엇인가요?"}
        a = c.post("/ask", json=q, headers={"X-API-Key": s.api_key}).json()
        out["/ask 응답"] = ok(bool(a.get("sources")) and bool(a.get("basis_date")) and bool(a.get("policy_version")),
                            f"근거 {len(a.get('sources', []))}건 · 기준일 {a.get('basis_date')} · {a.get('latency_ms', 0):,.0f}ms")
    except Exception as e:  # noqa: BLE001
        hint = ("make api 가 떠 있습니다. 서버 터미널에서 Ctrl+C 뒤 다시(임베디드 Qdrant 는 프로세스 하나만 엽니다)"
                if "already accessed" in str(e) else f"{type(e).__name__}: {str(e)[:60]}")
        out["/ask 응답"] = ok(False, hint)
    try:
        kinds = []
        with c.stream("POST", "/ask/stream", json=q, headers={"X-API-Key": s.api_key}) as r:
            for line in r.iter_lines():
                if line.startswith("event:"):
                    kinds.append(line.split(":", 1)[1].strip())
        out["/ask/stream 이벤트"] = ok("node_start" in kinds and "done" in kinds and ("token" in kinds or "citation" in kinds),
                                  f"node_start {kinds.count('node_start')} · token {kinds.count('token')} · citation {kinds.count('citation')} · 마지막 {kinds[-1] if kinds else '-'}")
    except Exception as e:  # noqa: BLE001
        out["/ask/stream 이벤트"] = ok(False, f"{type(e).__name__}: {str(e)[:60]}")
    # 3: 응답 시간 측정 기록
    b = _json(s.results_dir / "api_bench.json") or {}
    out["응답 시간 측정"] = ok(b.get("n_ok", 0) >= 10 and b.get("latency_ms_p95") is not None,
                         f"{b.get('n_ok')}문항 p95 {b.get('latency_ms_p95', 0):,.0f}ms · 문항당 {b.get('cost_krw_avg')}원" if b
                         else "results/api_bench.json 없음 (서버를 띄우고 make api-bench)")
    # 4: 감사 로그. 열 줄 이상, 원문 없음
    log = ROOT / "logs" / "audit.jsonl"
    if log.exists():
        recs = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
        raw = sum(1 for r in recs if "question" in r)
        out["감사 로그"] = ok(len(recs) >= 10 and raw == 0 and all(len(r.get("question_sha256", "")) == 64 for r in recs),
                         f"{len(recs)}줄 · 원문 {raw}건 · 키는 해시 앞 12자")
    else:
        out["감사 로그"] = ok(False, "logs/audit.jsonl 없음 (/ask 를 열 번 이상)")
    # 5: 보안 질의서 답변서(과제)
    doc = ROOT / "docs" / "security_questionnaire.md"
    if not doc.exists():
        out["보안 답변서"] = ok(False, "docs/security_questionnaire.md 없음 (docs/templates/ 를 복사해 채운다)")
    else:
        blanks = doc.read_text(encoding="utf-8").count("____")
        out["보안 답변서"] = ok(blanks == 0, f"빈칸 {blanks}곳 남음" if blanks else f"{len(doc.read_text(encoding='utf-8')):,}자")
    return out


def check_s08() -> dict:
    return {
        "readout 1p": ok((ROOT / "docs" / "readout_1p.md").exists()),
        "README": ok((ROOT / "README.md").exists()),
        "ADR 3건 이상": ok(len(list((ROOT / "docs" / "adr").glob("*.md"))) >= 3,
                        f"{len(list((ROOT / 'docs' / 'adr').glob('*.md')))}건"),
    }


CHECKS = {i: globals()[f"check_s{i:02d}"] for i in range(9)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("session", type=int, choices=range(9))
    args = ap.parse_args()

    try:
        checks = CHECKS[args.session]()
    except Exception as e:
        checks = {"실행 실패": ok(False, f"{type(e).__name__}: {e}")}

    passed = sum(1 for v in checks.values() if v["ok"])
    print(f"\ncheck-s{args.session:02d}   {passed}/{len(checks)} 통과")
    for k, v in checks.items():
        print(f"  {'O' if v['ok'] else 'X'}  {k:28} {v['detail']}")

    out = ROOT / "results" / f"check_s{args.session:02d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "session": args.session,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "passed": passed, "total": len(checks), "checks": checks},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {out.relative_to(ROOT)}  (이 파일을 커밋하세요)")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
