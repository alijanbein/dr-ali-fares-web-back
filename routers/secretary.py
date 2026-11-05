"""
The secretary's inbox of booking requests. Protected by one shared key
(SECRETARY_KEY in .env), because this backend has no staff accounts of its own.
"""
import hmac
import os
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models import BookingRequest
from questionnaires import get_config, resolved_answers
from rate_limit import check_rate_limit, client_ip
from schemas import BookingRequestUpdate, Status

FAILED_KEY_LIMIT = 10
FAILED_KEY_WINDOW_SECONDS = 600


def require_secretary(request: Request, x_secretary_key: Optional[str] = Header(default=None)) -> None:
    expected = os.getenv("SECRETARY_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="SECRETARY_KEY is not configured.")
    if x_secretary_key and hmac.compare_digest(x_secretary_key.encode(), expected.encode()):
        return
    check_rate_limit(
        f"secretary-key:{client_ip(request)}", FAILED_KEY_LIMIT, FAILED_KEY_WINDOW_SECONDS,
        "Too many attempts. Please wait a few minutes.",
    )
    raise HTTPException(status_code=401, detail="Invalid key.")


router = APIRouter(prefix="/api/secretary", tags=["Secretary"], dependencies=[Depends(require_secretary)])


def whatsapp_number(phone: str) -> Optional[str]:
    """Digits for a wa.me link. Patients usually type Lebanese numbers in local
    form (03 123456, 81 931988), which wa.me can't open without the country code."""
    trimmed = phone.strip()
    digits = re.sub(r"\D", "", trimmed)
    if trimmed.startswith("+"):
        pass
    elif digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = "961" + digits[1:]
    elif len(digits) <= 8:
        digits = "961" + digits
    return digits if 8 <= len(digits) <= 15 else None


def _iso(value: datetime) -> str:
    # SQLite hands datetimes back without a timezone; they are always UTC.
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def _summary(b: BookingRequest) -> dict:
    return {
        "reference": b.reference,
        "status": b.status,
        "createdAt": _iso(b.createdAt),
        "name": b.name,
        "phone": b.phone,
        "whatsappNumber": whatsapp_number(b.phone),
        "contactMethod": b.contactMethod,
        "bodyArea": b.bodyArea,
        "urgent": b.urgent,
        "language": b.language,
        "preferredDate": b.preferredDate,
        "preferredTime": b.preferredTime,
    }


def _get_or_404(reference: str, db: Session) -> BookingRequest:
    booking = db.query(BookingRequest).filter(BookingRequest.reference == reference).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Request not found.")
    return booking


@router.get("/requests")
def list_requests(status: Optional[Status] = None, db: Session = Depends(get_db)):
    query = db.query(BookingRequest)
    if status:
        query = query.filter(BookingRequest.status == status)
    rows = query.order_by(BookingRequest.urgent.desc(), BookingRequest.createdAt.desc()).limit(200).all()
    return [_summary(b) for b in rows]


@router.get("/requests/{reference}")
def get_request(reference: str, db: Session = Depends(get_db)):
    b = _get_or_404(reference, db)
    config = get_config(b.bodyArea)
    return {
        **_summary(b),
        "age": b.age,
        "gender": b.gender,
        "side": b.side,
        "chiefComplaint": b.chiefComplaint,
        "onset": b.onset,
        "mechanism": b.mechanism,
        "history": b.history,
        "redFlags": b.redFlags,
        "notes": b.notes,
        "secretaryNote": b.secretaryNote,
        "painScore": b.painScore,
        "promName": b.promName,
        "score": b.score,
        "maxScore": b.maxScore,
        "finalScore": b.finalScore,
        "scoreDirection": b.scoreDirection,
        "interpretation": b.interpretation,
        "answers": resolved_answers(config, b.answers) if config else [],
    }


@router.patch("/requests/{reference}")
def update_request(reference: str, body: BookingRequestUpdate, db: Session = Depends(get_db)):
    b = _get_or_404(reference, db)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("status") is None:
        changes.pop("status", None)
    for key, value in changes.items():
        setattr(b, key, value)
    b.updatedAt = datetime.now(timezone.utc)
    db.commit()
    return _summary(b)
