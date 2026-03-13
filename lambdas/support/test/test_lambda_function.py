import csv
import os
import pytest
from pathlib import Path
from app.graphs.orchestrate_graph import app_graph

DATA_DIR = Path(__file__).resolve().parent / "data"
QUESTIONS_CSV = DATA_DIR / "first_timer_questions.csv"
RESULTS_CSV = DATA_DIR / "result.csv"

_results = []


def _load_questions():
    with open(QUESTIONS_CSV, newline="") as f:
        return list(csv.DictReader(f))


_questions = _load_questions()


def _invoke_graph(message: str) -> dict:
    from app.tools import mongo_tool
    uid = os.environ.get("SUPPORT_CONTEXT_USER_EMAIL", "android.user@yopmail.com")
    user = mongo_tool.get_user_info(uid) or {}
    return app_graph.invoke({
        "message": message,
        "messages": [],
        "session_id": "test-session",
        "previous_node": None,
        "next": "",
        "persona": "",
        "plan": "",
        "reply": "",
        "handoff": False,
        "user": user,
    })


@pytest.fixture(scope="session", autouse=True)
def write_results_csv():
    yield
    fieldnames = [
        "id", "message", "expected_persona", "actual_persona",
        "sub_intent", "reply", "passed",
    ]
    with open(RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_results)


@pytest.mark.parametrize(
    "case",
    _questions,
    ids=[f"{q['id']}_{q['sub_intent']}" for q in _questions],
)
def test_persona_classification(case):
    state = _invoke_graph(case["message"])

    actual = state.get("persona", "")
    reply = state.get("reply", "")
    passed = actual == case["expected_persona"]

    _results.append({
        "id": case["id"],
        "message": case["message"],
        "expected_persona": case["expected_persona"],
        "actual_persona": actual,
        "sub_intent": case["sub_intent"],
        "reply": reply,
        "passed": str(passed),
    })

    assert passed, f"Expected '{case['expected_persona']}' but got '{actual}' for: {case['message']}"
