# SAQLA — Digital Purchase & Warranty Vault

MVP for Uzbekistan. Uzbek, Russian and English UI.

## Stack
- FastAPI + SQLAlchemy
- Neon PostgreSQL
- Responsive web app
- Receipts stored as private BYTEA records in PostgreSQL (5 MB limit)

## Run locally
1. Install requirements: pip install -r requirements.txt
2. Set DATABASE_URL and JWT_SECRET environment variables.
3. Run: uvicorn main:app --reload

## Render
- Root directory: saqla
- Build: pip install -r requirements.txt
- Start: uvicorn main:app --host 0.0.0.0 --port $PORT
- Environment: DATABASE_URL, JWT_SECRET

## API
- POST /api/auth/register
- POST /api/auth/login
- GET /api/auth/me
- GET /api/dashboard
- GET/POST /api/products
- PUT/DELETE /api/products/{id}
- POST/GET/DELETE /api/products/{id}/receipt
- GET /api/health
