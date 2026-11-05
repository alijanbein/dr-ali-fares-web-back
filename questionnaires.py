"""The hospital's pre-visit instruments, one per body area. See
scripts/export_questionnaires.py for where data/questionnaires.json comes from."""
import json
from pathlib import Path
from typing import Optional

_CONFIGS: dict[str, dict] = json.loads(
    (Path(__file__).parent / "data" / "questionnaires.json").read_text(encoding="utf-8")
)

BODY_AREAS = list(_CONFIGS)


def get_config(body_area: str) -> Optional[dict]:
    return _CONFIGS.get(body_area)


def all_questions(config: dict) -> list[dict]:
    return [q for section in config["sections"] for q in section["questions"]]


def public_config(config: dict) -> dict:
    """What the patient's browser needs: the questions, without the scoring."""
    return {
        "bodyArea": config["bodyArea"],
        "title": config["title"],
        "promName": config["promName"],
        "sections": [
            {
                "id": section["id"],
                "title": section["title"],
                "questions": [{k: v for k, v in q.items() if k != "scoreValues"} for q in section["questions"]],
            }
            for section in config["sections"]
        ],
    }


def validate_answers(config: dict, answers: dict) -> Optional[str]:
    """Returns what is wrong with the answers, or None when they are complete
    and every value is one the questionnaire actually offers."""
    questions = {q["id"]: q for q in all_questions(config)}
    for qid in answers:
        if qid not in questions:
            return f"Unknown question: {qid}"
    for qid, q in questions.items():
        value = answers.get(qid)
        if value is None:
            if q.get("required"):
                return f"Missing answer: {qid}"
            continue
        if q["type"] == "radio":
            if value != int(value) or not 0 <= value < len(q["options"]):
                return f"Invalid answer: {qid}"
        elif q["type"] == "numeric" and not q["min"] <= value <= q["max"]:
            return f"Invalid answer: {qid}"
    return None


def resolved_answers(config: dict, answers: dict) -> list[dict]:
    """The answers as readable text, for the secretary and doctor."""
    rows = []
    for section in config["sections"]:
        for q in section["questions"]:
            value = answers.get(q["id"])
            if value is None:
                continue
            answer = q["options"][int(value)] if q["type"] == "radio" else f"{value:g}"
            rows.append({"id": q["id"], "section": section["title"], "question": q["text"], "answer": answer})
    return rows
