# Topdim MVP

Lost & found platform prototype for Uzbekistan.

## Stack
- FastAPI + SQLAlchemy
- PostgreSQL (Neon) / SQLite local fallback
- Responsive HTML/CSS/JS frontend
- GSAP animations (CDN)
- RU / UZ / EN UI

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r topdim/requirements.txt
uvicorn app:app --app-dir topdim --reload
```

Open http://127.0.0.1:8000

## Important prototype limitations
This is a demo MVP, not a production lost-property operator. Do not enter real personal data, document images, phone numbers, email addresses, exact addresses, or sensitive item identifiers. Claim requests are stored but are not yet routed to verified organizations; there is no identity verification, secure messaging, moderation dashboard, or legally compliant production data residency setup. Do not use this with real users until privacy, security, moderation, and Uzbekistan legal requirements have been reviewed with a parent/legal representative and qualified counsel.

## API
- GET /api/health
- GET /api/listings
- POST /api/listings
- POST /api/listings/{id}/claims
- GET /api/organizations
- GET /api/docs
