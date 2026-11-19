# Topdim backend

Node.js 20 + Express + PostgreSQL. The API is designed to fail closed: no persistent database means no public submissions.

## Install / run
```sh
npm install
npm start
```

## Required environment
- `DATABASE_URL`: PostgreSQL connection string. Use a provider/region approved for your data-processing conditions.
- `ADMIN_TOKEN`: random secret of at least 32 characters. Store only in the hosting provider's secret environment settings; never commit it.
- `RATE_LIMIT_SECRET`: optional independent random secret for one-way IP hashing.
- `DATABASE_SSL`: leave unset for normal TLS verification; only set to `disable` for a verified local database that does not use TLS.

## API
- `GET /api/health` — readiness and database state (no secrets).
- `GET /api/listings?q=&category=&kind=` — approved listings only.
- `GET /api/listings/:id/photo` — photo only for approved listings.
- `POST /api/listings` — multipart form with `photo`, `title`, `category`, `kind`, `area`, `date`, `description`; creates pending item.
- `GET /api/admin/submissions` — bearer token, pending queue.
- `PATCH /api/admin/submissions/:id` — bearer token and JSON `{"status":"approved"}` or `{"status":"rejected"}`.

## Security included
- Parameterized SQL; strict allowlists and validation.
- Image upload MIME allowlist, file size/pixel limits, image decode and WebP re-encoding (metadata stripped).
- No public phone numbers or exact coordinates; pending listings are never public.
- Database-backed rate limits with hashed client IP, security headers/CSP, no CORS wildcard.
- Admin token uses constant-time comparison; audit log for moderation.
- Public responses expose only approved records and approved images.
- Request IDs and non-sensitive server errors.

## Not yet production-certified
No user accounts, password reset, claim/ownership verification, SMS, user editing, QR quota, report/appeal workflow, malware scanning, object storage, automated backup/restore test, or formal penetration test. Admin token is a single-operator MVP gate, not a full staff identity system. Database and hosting must be configured and tested before enabling live submissions. Cloudflare can add DNS proxy/WAF/rate controls, but it is not a substitute for server-side validation or application authorization.

## Data protection
The law changed on 27 March 2026 (Law No. ZRU-1125). The amended Article 27¹ requires biometric data, genetic data, and telecom-operator subscriber data to be stored in Uzbekistan. Other personal data may be processed abroad only if one of the statutory conditions is met (adequacy, approved standard contractual terms/binding corporate rules, or listed international standards). Get local legal advice on whether the chosen host/provider and processing arrangement meet a condition before storing real users' data. See LexUZ: https://www.lex.uz/ru/docs/8104580

For a real launch, involve a parent/guardian in accounts, contracts, payments, and legal arrangements.
