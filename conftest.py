"""Repository-root conftest: test environment, frozen spec clock for Phase 1, and mock/live tier handling.

Phase 1 clock: the POC's Phase 1 tests were written for 2026-06-18 and call /dashboard without a period (current month).
Production keeps strict current-month semantics; only the clock source is patched, only for tests under tests/phase1/
(opt out with @pytest.mark.real_clock). Patching the module attribute survives the spec fixture's
app.dependency_overrides.clear().

Test tiers: tests marked live_gemini / live_langsmith need real credentials and are SKIPPED (never counted as passed)
without them. Everything else runs offline with fakes ("mock" tier). The summary prints the two tiers separately.
"""
import datetime
import os
import sys

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production-0123456789")
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ["LANGCHAIN_TRACING_V2"] = "false"

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests"))

import pytest  # noqa: E402

SPEC_TODAY = datetime.date(2026, 6, 18)


@pytest.fixture(autouse=True)
def _frozen_clock_for_phase1(request, monkeypatch):
    path = str(request.node.fspath).replace("\\", "/")
    if "real_clock" in request.keywords or "/tests/phase1/" not in path:
        return
    import app.core.clock as clock

    monkeypatch.setattr(clock, "_real_today", lambda: SPEC_TODAY)


def pytest_collection_modifyitems(config, items):
    skip_gemini = pytest.mark.skip(reason="SKIPPED(no GOOGLE_API_KEY): live Gemini verification pending")
    skip_smith = pytest.mark.skip(reason="SKIPPED(no LANGCHAIN_API_KEY): live LangSmith verification pending")
    for item in items:
        if "live_gemini" in item.keywords and not os.getenv("GOOGLE_API_KEY"):
            item.add_marker(skip_gemini)
        if "live_langsmith" in item.keywords and not os.getenv("LANGCHAIN_API_KEY"):
            item.add_marker(skip_smith)


def pytest_terminal_summary(terminalreporter):
    tr = terminalreporter
    live_name, mock_name = "LIVE (Gemini/LangSmith)", "mock/offline"
    tiers = {mock_name: [0, 0, 0], live_name: [0, 0, 0]}  # passed, failed, skipped

    def bucket(rep):
        return live_name if ("live_gemini" in rep.keywords or "live_langsmith" in rep.keywords) else mock_name

    for rep in tr.stats.get("passed", []):
        if rep.when == "call":
            tiers[bucket(rep)][0] += 1
    for rep in tr.stats.get("failed", []):
        tiers[bucket(rep)][1] += 1
    for rep in tr.stats.get("skipped", []):
        tiers[bucket(rep)][2] += 1
    tr.write_sep("=", "TEST TIERS (mock results are not live verification)")
    for name, (p, f, s) in tiers.items():
        tr.write_line(f"{name:26} passed={p} failed={f} skipped={s}")
    if tiers[live_name][2]:
        tr.write_line("LIVE tier SKIPPED: provide GOOGLE_API_KEY (and LANGCHAIN_API_KEY) to verify real Gemini/LangSmith integration.")
