"""
Python port of the hospital's scoring (orthopedic-opd-ai-test/frontend/src/
utils/scoring.js computeFinalScore), so a score here means the same as a score
there. The score is always computed here rather than accepted from the browser.
"""
import math
from typing import Optional

from questionnaires import all_questions


def _js_round(value: float) -> int:
    # Math.round rounds .5 up; Python's round() rounds it to the nearest even
    # number, which would make some scores differ from the hospital's by one.
    return math.floor(value + 0.5)


def _odi_ndi_interpretation(score: float) -> dict:
    if score <= 20:
        return {"label": "Minimal disability", "severity": "mild", "range": "0–20%"}
    if score <= 40:
        return {"label": "Moderate disability", "severity": "moderate", "range": "21–40%"}
    if score <= 60:
        return {"label": "Severe disability", "severity": "severe", "range": "41–60%"}
    if score <= 80:
        return {"label": "Crippled", "severity": "very_severe", "range": "61–80%"}
    return {"label": "Bed-bound or symptom exaggeration", "severity": "critical", "range": "81–100%"}


def compute_final_score(config: dict, answers: dict) -> Optional[dict]:
    scored = [q for q in all_questions(config) if q.get("scoreValues")]
    answered = [q for q in scored if answers.get(q["id"]) is not None]
    if not answered:
        return None

    raw = sum(q["scoreValues"][int(answers[q["id"]])] for q in answered)
    calculation = config["scoreCalculation"]
    raw_max = len(answered) * 5 if calculation == "odi_ndi" else config["rawMax"]

    if calculation == "quickdash":
        final = _js_round((raw / len(answered) - 1) * 25 * 10) / 10
    elif calculation == "odi_ndi":
        final = _js_round(raw / raw_max * 1000) / 10
    elif calculation == "koos_hoos_jr":
        final = _js_round(config["conversionTable"][str(raw)])
    else:
        final = _js_round(raw / raw_max * 100)

    return {
        "raw": raw,
        "rawMax": raw_max,
        "final": final,
        "direction": config["scoreDirection"],
        "promCode": calculation,
        "promName": config["promName"],
        "interpretation": _odi_ndi_interpretation(final) if calculation == "odi_ndi" else None,
    }
