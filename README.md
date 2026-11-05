# Doctor website backend

The backend for Dr. Ali Fares's website (`../doctor-portfolio`). It serves the
pre-visit questionnaire, saves appointment requests and powers the secretary's
inbox. It is separate from the hospital system (`../orthopedic-opd-ai-test`).

## Run

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill it in
python -m uvicorn main:app --reload --port 8001
```

On Windows, `start_backend.bat` does the install and the start.
`GET /health` reports whether the database can be reached.

## Settings (`.env`)

| Name | Purpose |
| --- | --- |
| `DATABASE_URL` | Where requests are saved. For now, the hospital's database. |
| `SECRETARY_KEY` | The password for the inbox at `/secretary` on the website. |
| `ALLOWED_ORIGINS` | The website addresses allowed to call this API, comma-separated. |
| `TRUST_PROXY` | Set to `true` when deployed behind a proxy such as Render. |

## The database

This backend only ever creates and uses one table, `doctor_booking_requests`.
It never reads or writes a hospital table, even while sharing the hospital's
database. To move to another database later:

1. Copy the rows of `doctor_booking_requests` to the new database.
2. Change `DATABASE_URL`.

## The questionnaires

`data/questionnaires.json` is a copy of the 8 instruments in the hospital's
`backend/seed_proms.py`, so questionnaires keep working once the databases are
separate. If an instrument changes there, regenerate the copy:

```bash
python scripts/export_questionnaires.py
```

`scoring.py` is a port of the hospital's `frontend/src/utils/scoring.js`. Change
both together, so a score means the same thing in both systems. Scores are
always computed here and are not accepted from the browser.

## API

Public:

- `GET /api/booking/questionnaires` lists the body areas.
- `GET /api/booking/questionnaires/{bodyArea}` returns the questions, without scoring.
- `POST /api/booking/requests` saves a request and returns its reference code.

Needs the `X-Secretary-Key` header:

- `GET /api/secretary/requests?status=` lists requests, urgent ones first.
- `GET /api/secretary/requests/{reference}` returns the full request with readable answers.
- `PATCH /api/secretary/requests/{reference}` updates `status` and `secretaryNote`.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests
```

The tests use a temporary SQLite file and never touch `DATABASE_URL` from `.env`.

## Known limits

- Rate limits are kept in memory, which suits one server process only.
- The inbox has one shared key rather than individual staff accounts.
- Nothing alerts the secretary to a new request. A patient who chooses "call me"
  and doesn't get in touch is only seen when someone opens the inbox.
- A request doesn't create a Patient or Assessment in the hospital system. The
  columns already match, so that link can be added later.
