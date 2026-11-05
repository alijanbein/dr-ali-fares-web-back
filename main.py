import os
import sys

# Windows defaults redirected output to cp1252, where printing a non-Latin
# character raises and would take the request down with it.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from database import database_is_up
from routers.public_booking import router as public_booking_router
from routers.secretary import router as secretary_router

app = FastAPI(title="Dr. Ali Fares - Website Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5180").split(",") if o.strip()],
    # Lets a phone on the same network open the website's dev server.
    allow_origin_regex=r"http://(192\.168|10\.\d+|172\.(1[6-9]|2\d|3[01]))\.\d+\.\d+:5180",
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-Secretary-Key"],
)


@app.exception_handler(SQLAlchemyError)
def database_unavailable(_request: Request, exc: SQLAlchemyError):
    # The exception text can contain the connection details, so it is reduced
    # to its type here and never sent to the browser.
    print(f"Database error: {type(exc).__name__}", flush=True)
    return JSONResponse(status_code=503, content={"detail": "The booking service is temporarily unavailable."})


app.include_router(public_booking_router)
app.include_router(secretary_router)


@app.get("/health")
def health():
    return {"status": "ok", "database": "up" if database_is_up() else "down"}
