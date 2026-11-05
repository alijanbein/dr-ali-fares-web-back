import re
from datetime import date
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

RedFlag = Literal[
    "major_trauma", "deformity", "cannot_bear_weight", "hot_joint_fever", "bladder_bowel",
    "groin_numbness", "rapid_weakness", "open_wound", "post_op_infection",
]
Status = Literal["new", "contacted", "booked", "closed"]


class BookingRequestIn(BaseModel):
    submissionId: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")
    language: Literal["en", "ar"] = "en"
    consent: Literal[True]

    name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=0, le=120)
    gender: Literal["male", "female"]
    phone: str = Field(max_length=30)
    contactMethod: Literal["whatsapp", "call"]

    bodyArea: str = Field(max_length=40)
    side: Optional[Literal["left", "right", "both"]] = None
    chiefComplaint: str = Field(min_length=3, max_length=1000)
    onset: Literal["under_week", "under_month", "under_6_months", "over_6_months"]
    mechanism: Literal["injury", "gradual", "unsure"]
    history: Optional[str] = Field(default=None, max_length=1000)

    redFlags: list[RedFlag] = Field(default_factory=list, max_length=9)
    answers: dict[str, Union[int, float]]

    preferredDate: Optional[date] = None
    preferredTime: Literal["any", "morning", "afternoon", "evening"] = "any"
    notes: Optional[str] = Field(default=None, max_length=500)

    # Hidden from people by the website, so only bots fill it in.
    website: str = Field(default="", max_length=200)

    @field_validator("name", "chiefComplaint")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        digits = re.sub(r"\D", "", value)
        if not re.fullmatch(r"[+\d][\d\s().-]*", value) or not 7 <= len(digits) <= 15:
            raise ValueError("Please enter a valid phone number.")
        return value


class BookingRequestUpdate(BaseModel):
    status: Optional[Status] = None
    secretaryNote: Optional[str] = Field(default=None, max_length=2000)
