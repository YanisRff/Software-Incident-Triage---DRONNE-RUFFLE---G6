import json
import httpx
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from ticket_app.api import create_app
from ticket_app.analysis_models import Request
from ticket_app.analysis_provider import (
    InvalidModelOutput,
    LocalAnalysisProvider,
    ProviderUnavailable,
)

POLICY = json.loads(Path("scenarios/g06.json").read_text())
FIXTURES = json.loads(Path("tests/fixtures/g06.json").read_text())

GOOD = {
    "summary": "API responses are slow",
    "category": "performance",
    "priority": "high",
    "next_action": "Route to the performance on-call team.",
}
VALID_INPUT = {"subject": "Valid subject", "text": "This is a valid request text."}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def force_mock_provider(monkeypatch):
    """Make sure a local .env can't switch the default tests to a real LLM."""
    monkeypatch.setenv("LLM_PROVIDER", "mock")


def model_reply(content: str) -> httpx.Response:
    """Fake inference-server response wrapping `content` as the model output."""
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def make_provider(handler) -> LocalAnalysisProvider:
    return LocalAnalysisProvider("http://lm/v1", "test-model", 5,
                                 transport=httpx.MockTransport(handler))


def make_client(tmp_path, provider=None) -> TestClient:
    return TestClient(create_app(provider=provider, policy=POLICY,
                                 db_path=str(tmp_path / "test.db")))


# Handlers simulating the different ways the model server can misbehave
def timeout_handler(req):
    raise httpx.ReadTimeout("too slow", request=req)


def malformed_handler(req):
    return model_reply("this is not json at all")


def unknown_category_handler(req):
    return model_reply(json.dumps({**GOOD, "category": "Yanis"}))


# --------------------------------------------------------------------------- #
# Mock provider: baseline + fixtures
# --------------------------------------------------------------------------- #

def test_baseline_health_and_analysis(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/health").status_code == 200
    response = client.post(
        "/api/analyze",
        json={"subject": "Help request", "text": "Please help me route this request."},
    )
    assert response.status_code == 200
    assert response.json()["requires_review"] is True


@pytest.mark.parametrize("case", FIXTURES, ids=[c["subject"] for c in FIXTURES])
def test_fixtures_are_routed_correctly(tmp_path, case):
    client = make_client(tmp_path)
    response = client.post("/api/analyze",
                           json={"subject": case["subject"], "text": case["text"]})
    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["category"] == case["expected_category"]
    assert analysis["priority"] == case["expected_priority"]


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #

INVALID_INPUTS = {
    "subject_too_short": {**VALID_INPUT, "subject": "ab"},
    "subject_too_long": {**VALID_INPUT, "subject": "x" * 101},
    "text_too_short": {**VALID_INPUT, "text": "too short"},
    "text_blank": {**VALID_INPUT, "text": "          "},
    "extra_field": {**VALID_INPUT, "unexpected": "boom"},
}


@pytest.mark.parametrize("payload", INVALID_INPUTS.values(), ids=INVALID_INPUTS.keys())
def test_invalid_input(tmp_path, payload):
    client = make_client(tmp_path)
    assert client.post("/api/analyze", json=payload).status_code == 422


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #

def test_Persistence(tmp_path):
    client = make_client(tmp_path)

    payload = {"subject": "Release blocked",
               "text": "Cannot publish the new version, users are waiting."}
    assert client.post("/api/analyze", json=payload).status_code == 200

    history = client.get("/api/history")
    assert history.status_code == 200
    items = history.json()
    assert len(items) == 1
    assert items[0]["requires_review"] is True


# --------------------------------------------------------------------------- #
# Adapter (LocalAnalysisProvider) with httpx.MockTransport
# --------------------------------------------------------------------------- #

def test_adapter_payload():
    captured = {}

    def handler(req):
        captured["body"] = json.loads(req.content)
        return model_reply(json.dumps(GOOD))

    make_provider(handler).analyze(
        Request(subject="API responses slow", text="latency doubled since 9am"), POLICY
    )

    body = captured["body"]
    assert body["model"] == "test-model"
    assert "temperature" in body  # tighten to `== 0` if that's the value you send
    assert any("latency doubled since 9am" in m["content"] for m in body["messages"])


def test_adapter_parsing():
    provider = make_provider(lambda req: model_reply(json.dumps(GOOD)))
    result = provider.analyze(
        Request(subject="API responses slow", text="p95 latency doubled since 9am"), POLICY
    )
    assert result.summary == GOOD["summary"]
    assert result.category == GOOD["category"]
    assert result.priority == GOOD["priority"]
    assert result.next_action == GOOD["next_action"]


def test_timeout_is_unavailable():
    provider = make_provider(timeout_handler)
    with pytest.raises(ProviderUnavailable):
        provider.analyze(Request(subject="Down", text="Service unavailable for all"), POLICY)


def test_malformed_json_is_invalid_output():
    provider = make_provider(malformed_handler)
    with pytest.raises(InvalidModelOutput):
        provider.analyze(Request(subject="Down", text="Service unavailable for all"), POLICY)


# --------------------------------------------------------------------------- #
# Failures seen through the API
# --------------------------------------------------------------------------- #

FAILURES = {
    "timeout": (timeout_handler, 503),
    "malformed_json": (malformed_handler, 502),
    "unknown_category": (unknown_category_handler, 502),
}


@pytest.mark.parametrize("handler,status", FAILURES.values(), ids=FAILURES.keys())
def test_api_failure_status(tmp_path, handler, status):
    client = make_client(tmp_path, provider=make_provider(handler))
    response = client.post("/api/analyze", json=VALID_INPUT)
    assert response.status_code == status


@pytest.mark.parametrize("handler,status", FAILURES.values(), ids=FAILURES.keys())
def test_no_record_on_failure(tmp_path, handler, status):
    client = make_client(tmp_path, provider=make_provider(handler))
    assert client.post("/api/analyze", json=VALID_INPUT).status_code == status

    history = client.get("/api/history")
    assert history.status_code == 200
    assert history.json() == []