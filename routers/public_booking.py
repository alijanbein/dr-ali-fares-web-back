"""
Public routes behind the website's "Book an Appointment" page. They hand out
the questionnaires and accept finished requests, and never return anything a
patient has submitted apart from their own reference code.
"""
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import BookingRequest
from questionnaires import BODY_AREAS, get_config, public_config, validate_answers
from rate_limit import check_rate_limit, client_ip
from schemas import BookingRequestIn
from scoring import compute_final_score

router = APIRouter(prefix="/api/booking", tags=["Public booking"])

# No 0/O or 1/I/L, because patients read this code out over the phone.
REFERENCE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
SUBMIT_LIMIT = 20
SUBMIT_WINDOW_SECONDS = 3600


def _random_reference() -> str:
    return "AF-" + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(6))


def _new_reference(db: Session) -> str:
    while True:
        reference = _random_reference()
        if not db.query(BookingRequest.id).filter(BookingRequest.reference == reference).first():
            return reference


@router.get("/questionnaires")
def list_questionnaires():
    return {"bodyAreas": BODY_AREAS}


@router.get("/questionnaires/{body_area}")
def get_questionnaire(body_area: str):
    config = get_config(body_area)
    if not config:
        raise HTTPException(status_code=404, detail="Questionnaire not found.")
    return public_config(config)


@router.post("/requests", status_code=201)
def create_request(body: BookingRequestIn, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(
        f"submit:{client_ip(request)}", SUBMIT_LIMIT, SUBMIT_WINDOW_SECONDS,
        "Too many requests. Please contact the clinic directly.",
    )

    # Looks like success to a bot, so it has no reason to adapt.
    if body.website:
        return {"reference": _random_reference(), "urgent": False}

    config = get_config(body.bodyArea)
    if not config:
        raise HTTPException(status_code=422, detail="Unknown body area.")
    problem = validate_answers(config, body.answers)
    if problem:
        raise HTTPException(status_code=422, detail=problem)

    existing = db.query(BookingRequest).filter(BookingRequest.submissionId == body.submissionId).first()
    if existing:
        return {"reference": existing.reference, "urgent": existing.urgent}

    result = compute_final_score(config, body.answers)
    now = datetime.now(timezone.utc)
    booking = BookingRequest(
        id=str(uuid.uuid4()),
        reference=_new_reference(db),
        submissionId=body.submissionId,
        status="new",
        createdAt=now,
        updatedAt=now,
        language=body.language,
        name=body.name,
        age=body.age,
        gender=body.gender,
        phone=body.phone,
        contactMethod=body.contactMethod,
        bodyArea=body.bodyArea,
        side=body.side,
        chiefComplaint=body.chiefComplaint,
        onset=body.onset,
        mechanism=body.mechanism,
        history=(body.history or "").strip() or None,
        redFlags=list(body.redFlags),
        urgent=bool(body.redFlags),
        promName=config["promName"],
        promCode=result["promCode"] if result else None,
        answers=body.answers,
        painScore=body.answers.get("pain_scale"),
        score=result["raw"] if result else None,
        maxScore=result["rawMax"] if result else None,
        finalScore=result["final"] if result else None,
        scoreDirection=result["direction"] if result else None,
        interpretation=result["interpretation"] if result else None,
        preferredDate=body.preferredDate.isoformat() if body.preferredDate else None,
        preferredTime=body.preferredTime,
        notes=(body.notes or "").strip() or None,
    )
    db.add(booking)
    try:
        db.commit()
    except IntegrityError:
        # Two copies of the same submission raced each other; the first won.
        db.rollback()
        existing = db.query(BookingRequest).filter(BookingRequest.submissionId == body.submissionId).first()
        if not existing:
            raise
        return {"reference": existing.reference, "urgent": existing.urgent}

    return {"reference": booking.reference, "urgent": booking.urgent}
