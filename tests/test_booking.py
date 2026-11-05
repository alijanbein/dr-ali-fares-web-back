import os
import sys
import tempfile
from pathlib import Path

# Never the real database: DATABASE_URL is set before anything imports it.
_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_db_dir) / 'test.db'}"
os.environ["SECRETARY_KEY"] = "test-key"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

import rate_limit
from main import app
from questionnaires import BODY_AREAS, all_questions, get_config
from routers.secretary import whatsapp_number

client = TestClient(app)
KEY = {"X-Secretary-Key": "test-key"}


@pytest.fixture(autouse=True)
def clear_rate_limits():
    rate_limit._hits.clear()


def answers_for(area: str, option: int = 1) -> dict:
    answers = {}
    for q in all_questions(get_config(area)):
        answers[q["id"]] = 5 if q["type"] == "numeric" else option
    return answers


def payload(submission_id: str, area: str = "Knee", **overrides) -> dict:
    return {
        "submissionId": submission_id,
        "language": "en",
        "consent": True,
        "name": "Test Patient",
        "age": 40,
        "gender": "female",
        "phone": "03 123456",
        "contactMethod": "whatsapp",
        "bodyArea": area,
        "side": "left",
        "chiefComplaint": "Pain on stairs",
        "onset": "under_month",
        "mechanism": "gradual",
        "redFlags": [],
        "answers": answers_for(area),
        "preferredTime": "morning",
        **overrides,
    }


def test_every_body_area_has_a_questionnaire_without_scoring_exposed():
    assert len(BODY_AREAS) == 8
    for area in BODY_AREAS:
        res = client.get(f"/api/booking/questionnaires/{area}")
        assert res.status_code == 200
        questions = [q for s in res.json()["sections"] for q in s["questions"]]
        assert questions and all("scoreValues" not in q for q in questions)


@pytest.mark.parametrize("area", BODY_AREAS)
def test_submit_and_read_back_for_every_area(area):
    submission = "submit-" + "".join(c for c in area if c.isalnum())
    res = client.post("/api/booking/requests", json=payload(submission, area))
    assert res.status_code == 201, res.text
    detail = client.get(f"/api/secretary/requests/{res.json()['reference']}", headers=KEY).json()
    assert detail["bodyArea"] == area
    assert detail["finalScore"] is not None
    assert detail["painScore"] == 5
    assert len(detail["answers"]) == len(all_questions(get_config(area)))


def test_score_from_the_browser_is_ignored():
    res = client.post("/api/booking/requests", json=payload("forged-score", finalScore=99, score=99))
    detail = client.get(f"/api/secretary/requests/{res.json()['reference']}", headers=KEY).json()
    # KOOS-JR: 7 items answered "Mild" = raw 7, which the Rasch table maps to 68.
    assert (detail["score"], detail["finalScore"]) == (7, 68)


def test_retrying_a_submission_does_not_duplicate_it():
    first = client.post("/api/booking/requests", json=payload("retry-12345")).json()
    second = client.post("/api/booking/requests", json=payload("retry-12345")).json()
    assert first["reference"] == second["reference"]


@pytest.mark.parametrize("change", [
    {"answers": {"pain_scale": 5}},
    {"answers": {**answers_for("Knee"), "kj_S6": 99}},
    {"answers": {**answers_for("Knee"), "pain_scale": 11}},
    {"answers": {**answers_for("Knee"), "not_a_question": 1}},
    {"bodyArea": "Head"},
    {"consent": False},
    {"phone": "abc"},
    {"age": 300},
])
def test_invalid_submissions_are_rejected(change):
    assert client.post("/api/booking/requests", json=payload("invalid-123", **change)).status_code == 422


def test_red_flags_mark_the_request_urgent_and_sort_it_first():
    plain = client.post("/api/booking/requests", json=payload("sort-plain")).json()
    urgent = client.post("/api/booking/requests", json=payload("sort-urgent", redFlags=["open_wound"])).json()
    assert urgent["urgent"] is True and plain["urgent"] is False
    rows = client.get("/api/secretary/requests", headers=KEY).json()
    assert rows[0]["urgent"] is True


def test_honeypot_is_not_saved():
    res = client.post("/api/booking/requests", json=payload("honeypot-1", website="http://spam"))
    assert res.status_code == 201
    assert client.get(f"/api/secretary/requests/{res.json()['reference']}", headers=KEY).status_code == 404


def test_secretary_routes_need_the_key():
    assert client.get("/api/secretary/requests").status_code == 401
    assert client.get("/api/secretary/requests", headers={"X-Secretary-Key": "wrong"}).status_code == 401


def test_wrong_keys_get_locked_out():
    for _ in range(10):
        client.get("/api/secretary/requests", headers={"X-Secretary-Key": "wrong"})
    assert client.get("/api/secretary/requests", headers={"X-Secretary-Key": "wrong"}).status_code == 429


def test_secretary_updates_status_and_note():
    reference = client.post("/api/booking/requests", json=payload("update-123")).json()["reference"]
    res = client.patch(f"/api/secretary/requests/{reference}", json={"status": "booked", "secretaryNote": "Tue 10:00"}, headers=KEY)
    assert res.status_code == 200
    detail = client.get(f"/api/secretary/requests/{reference}", headers=KEY).json()
    assert (detail["status"], detail["secretaryNote"]) == ("booked", "Tue 10:00")
    assert client.patch(f"/api/secretary/requests/{reference}", json={"status": "bogus"}, headers=KEY).status_code == 422


def test_submissions_are_rate_limited():
    for i in range(20):
        client.post("/api/booking/requests", json=payload(f"limit-{i:04d}"))
    assert client.post("/api/booking/requests", json=payload("limit-over")).status_code == 429


@pytest.mark.parametrize("raw,expected", [
    ("03 123456", "9613123456"),
    ("81 931988", "96181931988"),
    ("+961 81 931 988", "96181931988"),
    ("00961 3 123456", "9613123456"),
    ("+33 6 12 34 56 78", "33612345678"),
])
def test_whatsapp_number(raw, expected):
    assert whatsapp_number(raw) == expected
